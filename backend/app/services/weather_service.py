"""Serviço orquestrador de previsão do tempo com cache, fallback e qualidade do ar."""

from __future__ import annotations

import logging

from app.core.security import round_coordinate
from app.providers.base import (
    AirQualityProvider,
    ProviderError,
    ProviderUnavailableError,
    WeatherProvider,
)
from app.schemas.weather import WeatherForecastResponse
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class WeatherService:
    """Coordena provedor primário, fallback automático e enriquecimento de qualidade do ar."""

    def __init__(
        self,
        *,
        primary_provider: WeatherProvider,
        fallback_provider: WeatherProvider,
        air_quality_provider: AirQualityProvider | None,
        cache: CacheService,
    ) -> None:
        self._primary = primary_provider
        self._fallback = fallback_provider
        self._air_quality = air_quality_provider
        self._cache = cache

    async def get_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        days: int = 16,
        timezone: str = "auto",
        include_air_quality: bool = True,
        include_full_hourly: bool = True,
    ) -> WeatherForecastResponse:
        """Obtém previsão com cache TTL, fallback transparente e qualidade do ar opcional."""
        lat_rounded = round_coordinate(latitude)
        lon_rounded = round_coordinate(longitude)

        cached_response = self._cache.get_weather(
            latitude=lat_rounded,
            longitude=lon_rounded,
            days=days,
            timezone=timezone,
            include_air_quality=include_air_quality,
        )
        if cached_response is not None:
            if not include_full_hourly:
                return cached_response.model_copy(update={"hourly": []})
            return cached_response

        forecast: WeatherForecastResponse
        try:
            forecast = await self._primary.fetch_forecast(
                latitude=lat_rounded,
                longitude=lon_rounded,
                days=days,
                timezone=timezone,
            )
        except ProviderError as primary_exc:
            logger.warning(
                "Provedor primário %s indisponível (%s). Acionando fallback %s.",
                self._primary.name,
                type(primary_exc).__name__,
                self._fallback.name,
            )
            try:
                forecast = await self._fallback.fetch_forecast(
                    latitude=lat_rounded,
                    longitude=lon_rounded,
                    days=days,
                    timezone=timezone,
                )
            except ProviderError as fallback_exc:
                logger.error(
                    "Provedor fallback %s também falhou (%s).",
                    self._fallback.name,
                    type(fallback_exc).__name__,
                )
                raise ProviderUnavailableError(
                    "Serviços de previsão do tempo temporariamente indisponíveis."
                ) from fallback_exc

        if include_air_quality and self._air_quality is not None:
            try:
                air_quality = await self._air_quality.fetch_air_quality(
                    latitude=lat_rounded,
                    longitude=lon_rounded,
                    timezone=timezone,
                )
                if air_quality is not None:
                    updated_attribution = forecast.attribution.model_copy(
                        update={"air_quality_provider": self._air_quality.name}
                    )
                    forecast = forecast.model_copy(
                        update={
                            "air_quality": air_quality,
                            "attribution": updated_attribution,
                        }
                    )
            except ProviderError as aq_exc:
                logger.info(
                    "Qualidade do ar indisponível (%s); prosseguindo sem bloqueio.",
                    type(aq_exc).__name__,
                )

        self._cache.set_weather(
            latitude=lat_rounded,
            longitude=lon_rounded,
            days=days,
            timezone=timezone,
            include_air_quality=include_air_quality,
            value=forecast,
        )
        if not include_full_hourly:
            return forecast.model_copy(update={"hourly": []})
        return forecast
