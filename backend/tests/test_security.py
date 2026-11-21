"""Testes de controles de segurança, anti-SSRF, criptografia, tokens e geração de chaves."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.security import (
    decrypt_secret,
    encrypt_secret,
    generate_capability_token,
    hash_token,
    round_coordinate,
    validate_external_url,
    verify_token,
)
from scripts.generate_keys import generate_local_keys, write_keys_to_env


def test_validate_external_url_allows_known_providers() -> None:
    allowed = [
        "https://api.open-meteo.com/v1/forecast",
        "https://geocoding-api.open-meteo.com/v1/search",
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        "https://api.met.no/weatherapi/locationforecast/2.0/complete",
        "https://nominatim.openstreetmap.org/reverse",
    ]
    for url in allowed:
        assert validate_external_url(url) == url


@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://api.open-meteo.com/v1/forecast",
        "https://127.0.0.1/latest",
        "https://localhost:8000/secret",
        "https://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/v1/forecast",
        "https://api.open-meteo.com:8443/v1/forecast",
        "https://user:pass@api.open-meteo.com/v1/forecast",
    ],
)
def test_validate_external_url_blocks_ssrf_vectors(blocked_url: str) -> None:
    with pytest.raises(ValueError):
        validate_external_url(blocked_url)


def test_round_coordinate_normalizes_negative_zero() -> None:
    assert round_coordinate(-0.001) == 0.0
    assert str(round_coordinate(-0.001)) == "0.0"
    assert round_coordinate(-23.5587) == -23.56


def test_capability_token_hash_and_verification() -> None:
    token = generate_capability_token()
    digest = hash_token(token)
    assert len(token) >= 32
    assert len(digest) == 64
    assert verify_token(token, digest) is True
    assert verify_token("wrong-token", digest) is False
    assert verify_token("", digest) is False


def test_fernet_encryption_roundtrip_and_wrong_key() -> None:
    key = Fernet.generate_key().decode("ascii")
    other_key = Fernet.generate_key().decode("ascii")
    payload_json = '{"endpoint":"https://fcm.googleapis.com/fcm/send/abc"}'

    encrypted = encrypt_secret(payload_json, key)
    assert encrypted != payload_json
    assert decrypt_secret(encrypted, key) == payload_json

    with pytest.raises(ValueError):
        decrypt_secret(encrypted, other_key)


def test_security_headers_present_on_health_response(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_generate_local_keys_and_write_env(tmp_path: Path) -> None:
    keys = generate_local_keys()

    fernet = Fernet(keys.data_encryption_key.encode("ascii"))
    assert fernet.decrypt(fernet.encrypt(b"climapy")) == b"climapy"

    pub_padded = keys.vapid_public_key + "=" * (-len(keys.vapid_public_key) % 4)
    priv_padded = keys.vapid_private_key + "=" * (-len(keys.vapid_private_key) % 4)
    pub_raw = base64.urlsafe_b64decode(pub_padded)
    priv_raw = base64.urlsafe_b64decode(priv_padded)

    assert len(pub_raw) == 65
    assert pub_raw[0] == 0x04
    assert len(priv_raw) == 32

    example_path = tmp_path / ".env.example"
    example_path.write_text(
        "APP_NAME=ClimaPy\nDATA_ENCRYPTION_KEY=\nVAPID_PUBLIC_KEY=\nVAPID_PRIVATE_KEY=\n",
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    updated = write_keys_to_env(env_path=env_path, example_path=example_path)
    assert set(updated) == {"DATA_ENCRYPTION_KEY", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"}
    content = env_path.read_text(encoding="utf-8")
    assert "DATA_ENCRYPTION_KEY=" in content
    assert (env_path.stat().st_mode & 0o777) == 0o600
