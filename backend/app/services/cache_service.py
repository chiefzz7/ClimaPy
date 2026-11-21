"""Serviço de cache em memória com TTL para reduzir chamadas externas e proteger limites."""

from __future__ import annotations

from cachetools import TTLCache

from app.core.security import round_coordinate
from app.schemas.geocoding import GeocodingSearchResponse, ReverseGeocodingResponse
from app.schemas.weather import WeatherForecastResponse


class CacheService:
    """Gerencia caches com TTL para previsão do tempo e geocodificação."""

    def __init__(
        self,
        *,
        weather_ttl_seconds: int = 900,
        geocoding_ttl_seconds: int = 86400,
        max_weather_entries: int = 512,
        max_geocoding_entries: int = 1024,
    ) -> None:
        self._weather_cache: TTLCache[str, WeatherForecastResponse] = TTLCache(
            maxsize=max_weather_entries,
            ttl=weather_ttl_seconds,
        )
        self._geocoding_cache: TTLCache[str, GeocodingSearchResponse] = TTLCache(
            maxsize=max_geocoding_entries,
            ttl=geocoding_ttl_seconds,
        )
        self._reverse_cache: TTLCache[str, ReverseGeocodingResponse] = TTLCache(
            maxsize=max_geocoding_entries,
            ttl=geocoding_ttl_seconds,
        )

    @staticmethod
    def _weather_key(
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
        include_air_quality: bool,
    ) -> str:
        lat_r = round_coordinate(latitude)
        lon_r = round_coordinate(longitude)
        return f"{lat_r:.2f}:{lon_r:.2f}:{days}:{timezone}:{int(include_air_quality)}"

    @staticmethod
    def _geocoding_key(query: str, count: int, lang: str) -> str:
        normalized = " ".join(query.strip().lower().split())
        return f"{normalized}:{count}:{lang.lower()}"

    @staticmethod
    def _reverse_key(latitude: float, longitude: float) -> str:
        lat_r = round_coordinate(latitude)
        lon_r = round_coordinate(longitude)
        return f"rev:{lat_r:.2f}:{lon_r:.2f}"

    def get_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
        include_air_quality: bool,
    ) -> WeatherForecastResponse | None:
        """Retorna previsão em cache marcada com cached=True ou None."""
        key = self._weather_key(latitude, longitude, days, timezone, include_air_quality)
        entry = self._weather_cache.get(key)
        if entry is None:
            return None
        return entry.model_copy(update={"cached": True})

    def set_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
        include_air_quality: bool,
        value: WeatherForecastResponse,
    ) -> None:
        """Armazena previsão normalizada no cache TTL."""
        key = self._weather_key(latitude, longitude, days, timezone, include_air_quality)
        self._weather_cache[key] = value.model_copy(update={"cached": False})

    def get_geocoding(self, *, query: str, count: int, lang: str) -> GeocodingSearchResponse | None:
        """Retorna busca de cidades em cache marcada com cached=True."""
        key = self._geocoding_key(query, count, lang)
        entry = self._geocoding_cache.get(key)
        if entry is None:
            return None
        return entry.model_copy(update={"cached": True})

    def set_geocoding(
        self,
        *,
        query: str,
        count: int,
        lang: str,
        value: GeocodingSearchResponse,
    ) -> None:
        """Armazena busca de cidades no cache TTL."""
        key = self._geocoding_key(query, count, lang)
        self._geocoding_cache[key] = value.model_copy(update={"cached": False})

    def get_reverse_geocoding(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> ReverseGeocodingResponse | None:
        """Retorna localidade reversa em cache marcada com cached=True."""
        key = self._reverse_key(latitude, longitude)
        entry = self._reverse_cache.get(key)
        if entry is None:
            return None
        return entry.model_copy(update={"cached": True})

    def set_reverse_geocoding(
        self,
        *,
        latitude: float,
        longitude: float,
        value: ReverseGeocodingResponse,
    ) -> None:
        """Armazena resultado de geocodificação reversa no cache TTL."""
        key = self._reverse_key(latitude, longitude)
        self._reverse_cache[key] = value.model_copy(update={"cached": False})
