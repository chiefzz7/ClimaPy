"""Controles de segurança: anti-SSRF, criptografia Fernet, capability tokens e headers HTTP."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

ALLOWED_EXTERNAL_HOSTS: frozenset[str] = frozenset(
    {
        "api.open-meteo.com",
        "geocoding-api.open-meteo.com",
        "air-quality-api.open-meteo.com",
        "api.met.no",
        "api.weatherapi.com",
        "nominatim.openstreetmap.org",
    }
)

ALLOWED_PUSH_BASE_DOMAINS: frozenset[str] = frozenset(
    {
        "fcm.googleapis.com",
        "push.services.mozilla.com",
        "push.apple.com",
        "notify.windows.com",
    }
)

_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'; base-uri 'none'"
)


def validate_external_url(url: str) -> str:
    """Valida URL externa contra allowlist fixa HTTPS para prevenir SSRF."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Somente conexões HTTPS são permitidas para provedores externos.")
    if parsed.username or parsed.password:
        raise ValueError("Credenciais embutidas na URL externa não são permitidas.")
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_EXTERNAL_HOSTS:
        raise ValueError(f"Host externo não autorizado pela allowlist: {hostname!r}")
    if parsed.port not in (None, 443):
        raise ValueError("Porta não autorizada para conexão HTTPS externa.")
    return url


def is_ip_blocked(ip_text: str) -> bool:
    """Retorna True para endereços privados, loopback, link-local, multicast ou reservados."""
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_push_endpoint(url: str) -> str:
    """Valida endpoint Web Push contra allowlist de provedores e vetores SSRF."""
    if not url or len(url) > 2048 or any(ch.isspace() or ord(ch) < 32 for ch in url):
        raise ValueError("Endpoint Web Push inválido.")

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Endpoint Web Push deve utilizar HTTPS.")
    if parsed.username or parsed.password:
        raise ValueError("Credenciais embutidas no endpoint Web Push não são permitidas.")
    if parsed.port not in (None, 443):
        raise ValueError("Porta não autorizada para endpoint Web Push.")

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise ValueError("Hostname ausente no endpoint Web Push.")

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Endereços IP literais não são permitidos em endpoints Web Push.")

    if not any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_PUSH_BASE_DOMAINS
    ):
        raise ValueError("Provedor de endpoint Web Push não autorizado pela política anti-SSRF.")
    return url


def round_coordinate(value: float, decimals: int = 2) -> float:
    """Arredonda coordenada (~1,1 km com 2 casas) e evita -0.0."""
    rounded = round(float(value), decimals)
    return 0.0 if rounded == 0.0 else rounded


def generate_capability_token() -> str:
    """Gera capability token criptograficamente aleatório por dispositivo/lembrete."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Calcula hash SHA-256 hexadecimal para armazenamento seguro de tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, expected_hash: str) -> bool:
    """Compara token recebido com o hash armazenado em tempo constante."""
    if not token or not expected_hash:
        return False
    candidate_hash = hash_token(token)
    return hmac.compare_digest(candidate_hash, expected_hash)


def encrypt_secret(plaintext: str, key: str) -> str:
    """Cifra conteúdo sensível em repouso com Fernet (AES-128-CBC + HMAC-SHA256)."""
    fernet = Fernet(key.encode("utf-8"))
    return fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str, key: str) -> str:
    """Decifra conteúdo previamente protegido com Fernet."""
    fernet = Fernet(key.encode("utf-8"))
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Falha ao decifrar dado protegido com chave inválida ou corrompida."
        ) from exc


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adiciona cabeçalhos de hardening HTTP em todas as respostas."""

    def __init__(self, app: ASGIApp, *, app_env: str) -> None:
        super().__init__(app)
        self._app_env = app_env

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        is_docs_route = self._app_env != "production" and request.url.path in {
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = _DOCS_CSP if is_docs_route else _API_CSP
        if self._app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
