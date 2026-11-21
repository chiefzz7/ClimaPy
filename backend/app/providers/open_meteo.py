"""Provedores Open-Meteo: previsão até 16 dias, qualidade do ar e geocoding em PT."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.security import round_coordinate
from app.core.wmo_codes import degrees_to_cardinal_pt, describe_wmo_code
from app.providers.base import (
    AirQualityProvider,
    GeocodingProvider,
    ProviderResponseError,
    WeatherProvider,
    safe_get_json,
)
from app.schemas.common import ProviderAttribution
from app.schemas.geocoding import GeocodingSearchResponse, LocationResult
from app.schemas.weather import (
    AirQualityCurrent,
    CurrentWeather,
    DailyForecastItem,
    HourlyForecastItem,
    WeatherCondition,
    WeatherForecastResponse,
)

_OPEN_METEO_ATTRIBUTION = ProviderAttribution(
    provider="open_meteo",
    provider_label="Open-Meteo (CC BY 4.0)",
    license="CC BY 4.0",
    url="https://open-meteo.com/",
    fallback_used=False,
)


def _as_list(container: dict[str, Any], key: str) -> list[Any]:
    value = container.get(key)
    return value if isinstance(value, list) else []


def _at_float(values: list[Any], idx: int) -> float | None:
    if idx >= len(values):
        return None
    item = values[idx]
    if isinstance(item, bool) or item is None:
        return None
    if isinstance(item, (int, float)):
        return float(item)
    return None


def _at_int(values: list[Any], idx: int) -> int | None:
    val = _at_float(values, idx)
    return int(round(val)) if val is not None else None


def _at_str(values: list[Any], idx: int) -> str | None:
    if idx >= len(values):
        return None
    item = values[idx]
    return item if isinstance(item, str) else None


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_int(value: Any) -> int | None:
    val = _to_float(value)
    return int(round(val)) if val is not None else None


def _meters_to_km(value: float | None) -> float | None:
    return round(value / 1000.0, 1) if value is not None else None


def _seconds_to_hours(value: float | None) -> float | None:
    return round(value / 3600.0, 2) if value is not None else None


def _make_condition(code: int | None, *, is_day: bool) -> WeatherCondition:
    wmo_code, key, label_pt, icon = describe_wmo_code(code, is_day=is_day)
    return WeatherCondition(code=wmo_code, key=key, label_pt=label_pt, icon=icon)


def _classify_european_aqi(aqi: int | None) -> str | None:
    if aqi is None:
        return None
    if aqi <= 20:
        return "Boa"
    if aqi <= 40:
        return "Razoável"
    if aqi <= 60:
        return "Moderada"
    if aqi <= 80:
        return "Ruim"
    if aqi <= 100:
        return "Muito Ruim"
    return "Extremamente Ruim"


class OpenMeteoWeatherProvider(WeatherProvider):
    """Provedor primário de previsão horária e diária (até 16 dias, sem API key)."""

    name = "open_meteo"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, client: httpx.AsyncClient, *, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent

    async def fetch_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
    ) -> WeatherForecastResponse:
        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": days,
            "timezone": timezone,
            "wind_speed_unit": "kmh",
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
                "precipitation,rain,showers,weather_code,cloud_cover,"
                "pressure_msl,surface_pressure,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
            ),
            "hourly": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,"
                "pressure_msl,surface_pressure,visibility,"
                "precipitation_probability,precipitation,rain,showers,weather_code,"
                "cloud_cover,wind_speed_10m,wind_gusts_10m,wind_direction_10m,uv_index,is_day"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "apparent_temperature_max,apparent_temperature_min,sunrise,sunset,"
                "daylight_duration,sunshine_duration,uv_index_max,"
                "precipitation_sum,precipitation_hours,precipitation_probability_max,"
                "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant"
            ),
        }
        payload = await safe_get_json(
            self._client,
            self.FORECAST_URL,
            params=params,
            headers={"User-Agent": self._user_agent},
        )
        return self._parse_forecast(payload, latitude=latitude, longitude=longitude, days=days)

    def _parse_forecast(
        self,
        payload: dict[str, Any],
        *,
        latitude: float,
        longitude: float,
        days: int,
    ) -> WeatherForecastResponse:
        current_raw = payload.get("current")
        hourly_raw = payload.get("hourly")
        daily_raw = payload.get("daily")
        if (
            not isinstance(current_raw, dict)
            or not isinstance(hourly_raw, dict)
            or not isinstance(daily_raw, dict)
        ):
            raise ProviderResponseError("Resposta da Open-Meteo sem blocos esperados.")

        hourly_times = _as_list(hourly_raw, "time")
        if not hourly_times:
            raise ProviderResponseError("Resposta da Open-Meteo sem série horária.")

        temps = _as_list(hourly_raw, "temperature_2m")
        apparents = _as_list(hourly_raw, "apparent_temperature")
        dew_points = _as_list(hourly_raw, "dew_point_2m")
        humidities = _as_list(hourly_raw, "relative_humidity_2m")
        pressures_msl = _as_list(hourly_raw, "pressure_msl")
        surface_pressures = _as_list(hourly_raw, "surface_pressure")
        visibilities = _as_list(hourly_raw, "visibility")
        precip_probs = _as_list(hourly_raw, "precipitation_probability")
        precips = _as_list(hourly_raw, "precipitation")
        rains = _as_list(hourly_raw, "rain")
        showers = _as_list(hourly_raw, "showers")
        codes = _as_list(hourly_raw, "weather_code")
        clouds = _as_list(hourly_raw, "cloud_cover")
        winds = _as_list(hourly_raw, "wind_speed_10m")
        gusts = _as_list(hourly_raw, "wind_gusts_10m")
        wind_dirs = _as_list(hourly_raw, "wind_direction_10m")
        uvs = _as_list(hourly_raw, "uv_index")
        is_days = _as_list(hourly_raw, "is_day")

        hourly_items: list[HourlyForecastItem] = []
        for idx, raw_time in enumerate(hourly_times):
            if not isinstance(raw_time, str):
                continue
            is_day_val = _at_int(is_days, idx)
            is_day_bool = True if is_day_val is None else bool(is_day_val)
            wind_dir_raw = _at_float(wind_dirs, idx)
            wind_dir_deg = int(round(wind_dir_raw)) % 360 if wind_dir_raw is not None else None
            hourly_items.append(
                HourlyForecastItem(
                    time=raw_time,
                    is_day=is_day_bool,
                    temperature_c=_at_float(temps, idx),
                    apparent_temperature_c=_at_float(apparents, idx),
                    dew_point_c=_at_float(dew_points, idx),
                    relative_humidity_percent=_at_float(humidities, idx),
                    pressure_msl_hpa=_at_float(pressures_msl, idx),
                    surface_pressure_hpa=_at_float(surface_pressures, idx),
                    visibility_km=_meters_to_km(_at_float(visibilities, idx)),
                    precipitation_probability_percent=_at_int(precip_probs, idx),
                    precipitation_mm=_at_float(precips, idx),
                    rain_mm=_at_float(rains, idx),
                    showers_mm=_at_float(showers, idx),
                    cloud_cover_percent=_at_int(clouds, idx),
                    wind_speed_kmh=_at_float(winds, idx),
                    wind_gusts_kmh=_at_float(gusts, idx),
                    wind_direction_deg=wind_dir_deg,
                    wind_direction_cardinal=degrees_to_cardinal_pt(wind_dir_raw),
                    uv_index=_at_float(uvs, idx),
                    condition=_make_condition(_at_int(codes, idx), is_day=is_day_bool),
                )
            )

        if not hourly_items:
            raise ProviderResponseError("Série horária vazia na resposta da Open-Meteo.")

        current_time = str(current_raw.get("time") or hourly_items[0].time)
        start_idx = 0
        current_hour_prefix = current_time[:13]
        for idx, item in enumerate(hourly_items):
            if item.time[:13] >= current_hour_prefix:
                start_idx = idx
                break

        hourly_72h = hourly_items[start_idx : start_idx + 72]
        current_hour_ref = hourly_items[start_idx]

        current_is_day_raw = _to_int(current_raw.get("is_day"))
        current_is_day = True if current_is_day_raw is None else bool(current_is_day_raw)
        current_pressure_msl = _to_float(current_raw.get("pressure_msl"))
        current_surface_pressure = _to_float(current_raw.get("surface_pressure"))
        current_wind_dir_raw = _to_float(current_raw.get("wind_direction_10m"))
        if current_wind_dir_raw is not None:
            current_wind_dir_deg: int | None = int(round(current_wind_dir_raw)) % 360
            current_wind_dir_card = degrees_to_cardinal_pt(current_wind_dir_raw)
        else:
            current_wind_dir_deg = current_hour_ref.wind_direction_deg
            current_wind_dir_card = current_hour_ref.wind_direction_cardinal

        current = CurrentWeather(
            time=current_time,
            is_day=current_is_day,
            temperature_c=_to_float(current_raw.get("temperature_2m")),
            apparent_temperature_c=_to_float(current_raw.get("apparent_temperature")),
            dew_point_c=current_hour_ref.dew_point_c,
            relative_humidity_percent=_to_float(current_raw.get("relative_humidity_2m")),
            pressure_msl_hpa=(
                current_pressure_msl
                if current_pressure_msl is not None
                else current_hour_ref.pressure_msl_hpa
            ),
            surface_pressure_hpa=(
                current_surface_pressure
                if current_surface_pressure is not None
                else current_hour_ref.surface_pressure_hpa
            ),
            visibility_km=current_hour_ref.visibility_km,
            precipitation_probability_percent=current_hour_ref.precipitation_probability_percent,
            precipitation_mm=_to_float(current_raw.get("precipitation")),
            rain_mm=_to_float(current_raw.get("rain")),
            showers_mm=_to_float(current_raw.get("showers")),
            cloud_cover_percent=_to_int(current_raw.get("cloud_cover")),
            wind_speed_kmh=_to_float(current_raw.get("wind_speed_10m")),
            wind_gusts_kmh=_to_float(current_raw.get("wind_gusts_10m")),
            wind_direction_deg=current_wind_dir_deg,
            wind_direction_cardinal=current_wind_dir_card,
            uv_index=current_hour_ref.uv_index,
            condition=_make_condition(
                _to_int(current_raw.get("weather_code")),
                is_day=current_is_day,
            ),
        )

        daily_times = _as_list(daily_raw, "time")
        d_codes = _as_list(daily_raw, "weather_code")
        d_tmax = _as_list(daily_raw, "temperature_2m_max")
        d_tmin = _as_list(daily_raw, "temperature_2m_min")
        d_app_max = _as_list(daily_raw, "apparent_temperature_max")
        d_app_min = _as_list(daily_raw, "apparent_temperature_min")
        d_sunrise = _as_list(daily_raw, "sunrise")
        d_sunset = _as_list(daily_raw, "sunset")
        d_daylight = _as_list(daily_raw, "daylight_duration")
        d_sunshine = _as_list(daily_raw, "sunshine_duration")
        d_uv_max = _as_list(daily_raw, "uv_index_max")
        d_precip_sum = _as_list(daily_raw, "precipitation_sum")
        d_precip_hours = _as_list(daily_raw, "precipitation_hours")
        d_precip_prob = _as_list(daily_raw, "precipitation_probability_max")
        d_wind_max = _as_list(daily_raw, "wind_speed_10m_max")
        d_gust_max = _as_list(daily_raw, "wind_gusts_10m_max")
        d_wind_dom = _as_list(daily_raw, "wind_direction_10m_dominant")

        daily_items: list[DailyForecastItem] = []
        for idx, raw_date in enumerate(daily_times):
            if not isinstance(raw_date, str):
                continue
            dom_raw = _at_float(d_wind_dom, idx)
            dom_deg = int(round(dom_raw)) % 360 if dom_raw is not None else None
            daily_items.append(
                DailyForecastItem(
                    date=raw_date,
                    temperature_max_c=_at_float(d_tmax, idx),
                    temperature_min_c=_at_float(d_tmin, idx),
                    apparent_temperature_max_c=_at_float(d_app_max, idx),
                    apparent_temperature_min_c=_at_float(d_app_min, idx),
                    precipitation_probability_max_percent=_at_int(d_precip_prob, idx),
                    precipitation_sum_mm=_at_float(d_precip_sum, idx),
                    precipitation_hours=_at_float(d_precip_hours, idx),
                    wind_speed_max_kmh=_at_float(d_wind_max, idx),
                    wind_gusts_max_kmh=_at_float(d_gust_max, idx),
                    wind_direction_dominant_deg=dom_deg,
                    wind_direction_dominant_cardinal=degrees_to_cardinal_pt(dom_raw),
                    uv_index_max=_at_float(d_uv_max, idx),
                    daylight_duration_hours=_seconds_to_hours(_at_float(d_daylight, idx)),
                    sunshine_duration_hours=_seconds_to_hours(_at_float(d_sunshine, idx)),
                    sunrise=_at_str(d_sunrise, idx),
                    sunset=_at_str(d_sunset, idx),
                    condition=_make_condition(_at_int(d_codes, idx), is_day=True),
                )
            )

        available_days = max(1, min(16, len(daily_items) if daily_items else days))
        tz_name = str(payload.get("timezone") or "UTC")
        tz_abbr = str(payload.get("timezone_abbreviation") or "UTC")
        utc_offset = _to_int(payload.get("utc_offset_seconds")) or 0

        return WeatherForecastResponse(
            latitude=round_coordinate(latitude),
            longitude=round_coordinate(longitude),
            timezone=tz_name,
            timezone_abbreviation=tz_abbr,
            utc_offset_seconds=utc_offset,
            requested_days=days,
            available_days=available_days,
            generated_at=datetime.now(UTC),
            cached=False,
            current=current,
            hourly_72h=hourly_72h,
            hourly=hourly_items,
            daily=daily_items,
            air_quality=None,
            attribution=_OPEN_METEO_ATTRIBUTION.model_copy(),
        )


class OpenMeteoAirQualityProvider(AirQualityProvider):
    """Provedor complementar de qualidade do ar (Open-Meteo / CAMS)."""

    name = "open_meteo_air_quality"
    AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(self, client: httpx.AsyncClient, *, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent

    async def fetch_air_quality(
        self,
        *,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> AirQualityCurrent | None:
        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "current": (
                "european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,"
                "nitrogen_dioxide,sulphur_dioxide,ozone,dust"
            ),
        }
        payload = await safe_get_json(
            self._client,
            self.AIR_QUALITY_URL,
            params=params,
            headers={"User-Agent": self._user_agent},
        )
        current = payload.get("current")
        if not isinstance(current, dict):
            return None

        eaqi = _to_int(current.get("european_aqi"))
        return AirQualityCurrent(
            time=current.get("time") if isinstance(current.get("time"), str) else None,
            european_aqi=eaqi,
            us_aqi=_to_int(current.get("us_aqi")),
            category_pt=_classify_european_aqi(eaqi),
            pm2_5=_to_float(current.get("pm2_5")),
            pm10=_to_float(current.get("pm10")),
            carbon_monoxide=_to_float(current.get("carbon_monoxide")),
            nitrogen_dioxide=_to_float(current.get("nitrogen_dioxide")),
            sulphur_dioxide=_to_float(current.get("sulphur_dioxide")),
            ozone=_to_float(current.get("ozone")),
            dust=_to_float(current.get("dust")),
        )


class OpenMeteoGeocodingProvider(GeocodingProvider):
    """Provedor de busca textual de cidades com suporte a idioma português."""

    name = "open_meteo_geocoding"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    def __init__(self, client: httpx.AsyncClient, *, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent

    async def search(
        self,
        *,
        query: str,
        count: int,
        lang: str,
    ) -> GeocodingSearchResponse:
        params: dict[str, str | int | float] = {
            "name": query,
            "count": count,
            "language": lang,
            "format": "json",
        }
        payload = await safe_get_json(
            self._client,
            self.GEOCODING_URL,
            params=params,
            headers={"User-Agent": self._user_agent},
        )
        raw_results = payload.get("results")
        items: list[LocationResult] = []
        if isinstance(raw_results, list):
            for entry in raw_results:
                if not isinstance(entry, dict):
                    continue
                lat_val = _to_float(entry.get("latitude"))
                lon_val = _to_float(entry.get("longitude"))
                name_val = entry.get("name")
                if lat_val is None or lon_val is None or not isinstance(name_val, str):
                    continue
                admin1 = entry.get("admin1") if isinstance(entry.get("admin1"), str) else None
                country = entry.get("country") if isinstance(entry.get("country"), str) else None
                parts = [part for part in (name_val, admin1, country) if part]
                items.append(
                    LocationResult(
                        id=_to_int(entry.get("id")),
                        name=name_val,
                        display_name=", ".join(parts),
                        admin1=admin1,
                        country=country,
                        country_code=(
                            entry.get("country_code")
                            if isinstance(entry.get("country_code"), str)
                            else None
                        ),
                        latitude=round_coordinate(lat_val),
                        longitude=round_coordinate(lon_val),
                        timezone=(
                            entry.get("timezone")
                            if isinstance(entry.get("timezone"), str)
                            else None
                        ),
                    )
                )

        return GeocodingSearchResponse(
            query=query,
            cached=False,
            results=items,
            attribution=_OPEN_METEO_ATTRIBUTION.model_copy(),
        )
