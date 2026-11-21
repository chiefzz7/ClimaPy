"""Contratos Pydantic v2 para busca de cidades e geocodificação reversa."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ProviderAttribution


class LocationResult(BaseModel):
    """Localidade normalizada com coordenadas arredondadas para privacidade/cache."""

    id: int | None = None
    name: str
    display_name: str
    admin1: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float
    longitude: float
    timezone: str | None = None


class GeocodingSearchResponse(BaseModel):
    """Resultado de busca textual de cidades."""

    query: str
    cached: bool = False
    results: list[LocationResult]
    attribution: ProviderAttribution


class ReverseGeocodingResponse(BaseModel):
    """Resultado de geocodificação reversa por GPS."""

    cached: bool = False
    location: LocationResult
    attribution: ProviderAttribution
