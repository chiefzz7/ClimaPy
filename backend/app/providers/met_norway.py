"""Provedor fallback MET Norway (Yr.no Locationforecast 2.0)."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.core.security import round_coordinate
from app.core.wmo_codes import (
    degrees_to_cardinal_pt,
    describe_wmo_code,
    met_norway_symbol_to_wmo,
)
from app.providers.base import ProviderResponseError, WeatherProvider, safe_get_json
from app.schemas.common import ProviderAttribution
from app.schemas.weather import (
    CurrentWeather,
    DailyForecastItem,
    HourlyForecastItem,
    WeatherCondition,
    WeatherForecastResponse,
)

_MET_NORWAY_ATTRIBUTION = ProviderAttribution(
    provider="met_norway",
    provider_label="MET Norway (CC BY 4.0)",
    license="CC BY 4.0",
    url="https://api.met.no/",
    fallback_used=True,
)


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _ms_to_kmh(value: Any) -> float | None:
    val = _to_float(value)
    return round(val * 3.6, 1) if val is not None else None


def _resolve_tz(timezone: str) -> tuple[str, tzinfo]:
    if timezone == "auto" or timezone.upper() == "UTC":
        return "UTC", UTC
    try:
        return timezone, ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return "UTC", UTC


def _make_condition(code: int, *, is_day: bool) -> WeatherCondition:
    wmo_code, key, label_pt, icon = describe_wmo_code(code, is_day=is_day)
    return WeatherCondition(code=wmo_code, key=key, label_pt=label_pt, icon=icon)


def _dominant_wind_direction(directions: list[int]) -> int | None:
    if not directions:
        return None
    sin_sum = sum(math.sin(math.radians(deg)) for deg in directions)
    cos_sum = sum(math.cos(math.radians(deg)) for deg in directions)
    if math.hypot(sin_sum, cos_sum) < 1e-6:
        return directions[0] % 360
    return int(round(math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0)) % 360


class MetNorwayWeatherProvider(WeatherProvider):
    """Fallback automático usando MET Norway Locationforecast 2.0."""

    name = "met_norway"
    FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"

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
            "lat": round_coordinate(latitude),
            "lon": round_coordinate(longitude),
        }
        payload = await safe_get_json(
            self._client,
            self.FORECAST_URL,
            params=params,
            headers={"User-Agent": self._user_agent},
        )
        return self._parse_forecast(
            payload,
            latitude=latitude,
            longitude=longitude,
            days=days,
            timezone=timezone,
        )

    def _parse_forecast(
        self,
        payload: dict[str, Any],
        *,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
    ) -> WeatherForecastResponse:
        properties = payload.get("properties")
        if not isinstance(properties, dict):
            raise ProviderResponseError("Resposta do MET Norway sem bloco properties.")
        timeseries = properties.get("timeseries")
        if not isinstance(timeseries, list) or not timeseries:
            raise ProviderResponseError("Resposta do MET Norway sem timeseries.")

        tz_label, target_tz = _resolve_tz(timezone)
        hourly_items: list[HourlyForecastItem] = []
        grouped_daily: dict[str, list[HourlyForecastItem]] = defaultdict(list)

        for entry in timeseries:
            if not isinstance(entry, dict):
                continue
            raw_time = entry.get("time")
            data = entry.get("data")
            if not isinstance(raw_time, str) or not isinstance(data, dict):
                continue

            try:
                dt_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except ValueError:
                continue
            dt_local = dt_utc.astimezone(target_tz)
            iso_local = dt_local.strftime("%Y-%m-%dT%H:%M")
            day_key = dt_local.strftime("%Y-%m-%d")
            is_day = 6 <= dt_local.hour < 18

            instant = data.get("instant")
            instant_details = instant.get("details", {}) if isinstance(instant, dict) else {}
            if not isinstance(instant_details, dict):
                instant_details = {}

            next_block = data.get("next_1_hours") or data.get("next_6_hours") or {}
            if not isinstance(next_block, dict):
                next_block = {}
            summary = next_block.get("summary")
            symbol_code = (
                summary.get("symbol_code")
                if isinstance(summary, dict) and isinstance(summary.get("symbol_code"), str)
                else None
            )
            next_details = next_block.get("details")
            if not isinstance(next_details, dict):
                next_details = {}

            wmo_code = met_norway_symbol_to_wmo(symbol_code)
            precip_prob_raw = _to_float(next_details.get("probability_of_precipitation"))
            cloud_raw = _to_float(instant_details.get("cloud_area_fraction"))
            wind_dir_raw = _to_float(instant_details.get("wind_from_direction"))
            wind_dir_deg = int(round(wind_dir_raw)) % 360 if wind_dir_raw is not None else None

            item = HourlyForecastItem(
                time=iso_local,
                is_day=is_day,
                temperature_c=_to_float(instant_details.get("air_temperature")),
                apparent_temperature_c=_to_float(instant_details.get("air_temperature")),
                dew_point_c=_to_float(instant_details.get("dew_point_temperature")),
                relative_humidity_percent=_to_float(instant_details.get("relative_humidity")),
                pressure_msl_hpa=_to_float(instant_details.get("air_pressure_at_sea_level")),
                precipitation_probability_percent=(
                    int(round(precip_prob_raw)) if precip_prob_raw is not None else None
                ),
                precipitation_mm=_to_float(next_details.get("precipitation_amount")),
                rain_mm=_to_float(next_details.get("precipitation_amount")),
                showers_mm=None,
                cloud_cover_percent=int(round(cloud_raw)) if cloud_raw is not None else None,
                wind_speed_kmh=_ms_to_kmh(instant_details.get("wind_speed")),
                wind_gusts_kmh=_ms_to_kmh(instant_details.get("wind_speed_of_gust")),
                wind_direction_deg=wind_dir_deg,
                wind_direction_cardinal=degrees_to_cardinal_pt(wind_dir_raw),
                uv_index=_to_float(instant_details.get("ultraviolet_index_clear_sky")),
                condition=_make_condition(wmo_code, is_day=is_day),
            )
            if len(grouped_daily) < days or day_key in grouped_daily:
                hourly_items.append(item)
                grouped_daily[day_key].append(item)

        if not hourly_items:
            raise ProviderResponseError("Série temporal do MET Norway vazia.")

        first = hourly_items[0]
        current = CurrentWeather(
            time=first.time,
            is_day=first.is_day,
            temperature_c=first.temperature_c,
            apparent_temperature_c=first.apparent_temperature_c,
            dew_point_c=first.dew_point_c,
            relative_humidity_percent=first.relative_humidity_percent,
            pressure_msl_hpa=first.pressure_msl_hpa,
            precipitation_probability_percent=first.precipitation_probability_percent,
            precipitation_mm=first.precipitation_mm,
            rain_mm=first.rain_mm,
            showers_mm=first.showers_mm,
            cloud_cover_percent=first.cloud_cover_percent,
            wind_speed_kmh=first.wind_speed_kmh,
            wind_gusts_kmh=first.wind_gusts_kmh,
            wind_direction_deg=first.wind_direction_deg,
            wind_direction_cardinal=first.wind_direction_cardinal,
            uv_index=first.uv_index,
            condition=first.condition,
        )

        daily_items: list[DailyForecastItem] = []
        for day_key, items in list(grouped_daily.items())[:days]:
            temps = [x.temperature_c for x in items if x.temperature_c is not None]
            probs = [
                x.precipitation_probability_percent
                for x in items
                if x.precipitation_probability_percent is not None
            ]
            precips = [x.precipitation_mm for x in items if x.precipitation_mm is not None]
            winds = [x.wind_speed_kmh for x in items if x.wind_speed_kmh is not None]
            gusts = [x.wind_gusts_kmh for x in items if x.wind_gusts_kmh is not None]
            wind_dirs = [x.wind_direction_deg for x in items if x.wind_direction_deg is not None]
            dom_dir = _dominant_wind_direction(wind_dirs)
            uvs = [x.uv_index for x in items if x.uv_index is not None]
            mid_item = items[len(items) // 2]

            daily_items.append(
                DailyForecastItem(
                    date=day_key,
                    temperature_max_c=max(temps) if temps else None,
                    temperature_min_c=min(temps) if temps else None,
                    apparent_temperature_max_c=max(temps) if temps else None,
                    apparent_temperature_min_c=min(temps) if temps else None,
                    precipitation_probability_max_percent=max(probs) if probs else None,
                    precipitation_sum_mm=round(sum(precips), 2) if precips else None,
                    precipitation_hours=float(
                        sum(1 for x in items if x.precipitation_mm and x.precipitation_mm > 0.0)
                    ),
                    wind_speed_max_kmh=max(winds) if winds else None,
                    wind_gusts_max_kmh=max(gusts) if gusts else None,
                    wind_direction_dominant_deg=dom_dir,
                    wind_direction_dominant_cardinal=degrees_to_cardinal_pt(
                        float(dom_dir) if dom_dir is not None else None
                    ),
                    uv_index_max=max(uvs) if uvs else None,
                    sunrise=None,
                    sunset=None,
                    condition=_make_condition(mid_item.condition.code, is_day=True),
                )
            )

        offset_delta = datetime.now(target_tz).utcoffset()
        utc_offset_seconds = int(offset_delta.total_seconds()) if offset_delta else 0

        return WeatherForecastResponse(
            latitude=round_coordinate(latitude),
            longitude=round_coordinate(longitude),
            timezone=tz_label,
            timezone_abbreviation=tz_label,
            utc_offset_seconds=utc_offset_seconds,
            requested_days=days,
            available_days=max(1, min(16, len(daily_items))),
            generated_at=datetime.now(UTC),
            cached=False,
            current=current,
            hourly_72h=hourly_items[:72],
            hourly=hourly_items,
            daily=daily_items,
            air_quality=None,
            attribution=_MET_NORWAY_ATTRIBUTION.model_copy(),
        )
