"""Contratos abstratos e cliente HTTP seguro anti-SSRF para provedores externos."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.security import validate_external_url
from app.schemas.geocoding import GeocodingSearchResponse, ReverseGeocodingResponse
from app.schemas.weather import AirQualityCurrent, WeatherForecastResponse


class ProviderError(Exception):
    """Erro base para falhas de provedores externos."""


class ProviderUnavailableError(ProviderError):
    """Provedor indisponível, com timeout ou erro 5xx."""


class ProviderRateLimitError(ProviderError):
    """Limite de requisições do provedor atingido (HTTP 429)."""


class ProviderResponseError(ProviderError):
    """Payload externo inesperado ou inválido."""


class WeatherProvider(ABC):
    """Contrato único para provedores de previsão do tempo."""

    name: str

    @abstractmethod
    async def fetch_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
    ) -> WeatherForecastResponse:
        """Obtém previsão atual, horária (72h e estendida) e diária normalizada."""


class AirQualityProvider(ABC):
    """Contrato para provedores de qualidade do ar."""

    name: str

    @abstractmethod
    async def fetch_air_quality(
        self,
        *,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> AirQualityCurrent | None:
        """Obtém indicadores atuais de qualidade do ar."""


class GeocodingProvider(ABC):
    """Contrato para busca de cidades por texto."""

    name: str

    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        count: int,
        lang: str,
    ) -> GeocodingSearchResponse:
        """Pesquisa localidades pelo nome."""


class ReverseGeocodingProvider(ABC):
    """Contrato para conversão de coordenadas em nome de cidade."""

    name: str

    @abstractmethod
    async def reverse(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> ReverseGeocodingResponse:
        """Obtém nome da localidade para latitude e longitude informadas."""


async def safe_get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str | int | float] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Executa GET HTTPS validado contra allowlist e retorna JSON objeto."""
    try:
        safe_url = validate_external_url(url)
    except ValueError as exc:
        raise ProviderResponseError(
            "URL de provedor externo rejeitada pela política de segurança."
        ) from exc

    try:
        response = await client.get(
            safe_url,
            params=params,
            headers=headers,
            follow_redirects=False,
        )
    except httpx.TimeoutException as exc:
        raise ProviderUnavailableError("Timeout ao consultar provedor externo.") from exc
    except httpx.HTTPError as exc:
        raise ProviderUnavailableError("Falha de comunicação com provedor externo.") from exc

    if response.status_code == 429:
        raise ProviderRateLimitError("Limite de requisições do provedor externo atingido.")
    if response.status_code >= 500 or response.status_code in {301, 302, 303, 307, 308}:
        raise ProviderUnavailableError(f"Provedor externo retornou status {response.status_code}.")
    if response.status_code >= 400:
        raise ProviderResponseError(
            f"Requisição rejeitada pelo provedor (status {response.status_code})."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderResponseError("Resposta JSON inválida recebida do provedor.") from exc

    if not isinstance(payload, dict):
        raise ProviderResponseError("Formato JSON inesperado recebido do provedor.")
    return payload
