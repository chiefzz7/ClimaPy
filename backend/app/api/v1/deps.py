"""Dependências de injeção para os endpoints da API v1."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.core.config import Settings
from app.providers.base import GeocodingProvider, ReverseGeocodingProvider
from app.services.cache_service import CacheService
from app.services.weather_service import WeatherService


def get_app_settings(request: Request) -> Settings:
    """Retorna configurações ativas da instância FastAPI."""
    return cast(Settings, request.app.state.settings)


def get_cache_service(request: Request) -> CacheService:
    """Retorna serviço de cache compartilhado da aplicação."""
    return cast(CacheService, request.app.state.cache_service)


def get_weather_service(request: Request) -> WeatherService:
    """Retorna orquestrador de previsão do tempo."""
    return cast(WeatherService, request.app.state.weather_service)


def get_geocoding_provider(request: Request) -> GeocodingProvider:
    """Retorna provedor de busca textual de cidades."""
    return cast(GeocodingProvider, request.app.state.geocoding_provider)


def get_reverse_geocoding_provider(request: Request) -> ReverseGeocodingProvider:
    """Retorna provedor de geocodificação reversa por coordenadas."""
    return cast(ReverseGeocodingProvider, request.app.state.reverse_geocoding_provider)
