"""Contratos Pydantic v2 para previsão atual, horária (72h/16d), diária e qualidade do ar."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ProviderAttribution


class WeatherCondition(BaseModel):
    """Descrição normalizada da condição atmosférica."""

    code: int
    key: str
    label_pt: str
    icon: str


class CurrentWeather(BaseModel):
    """Condições meteorológicas do momento atual."""

    time: str
    is_day: bool
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    dew_point_c: float | None = None
    relative_humidity_percent: float | None = None
    pressure_msl_hpa: float | None = None
    surface_pressure_hpa: float | None = None
    visibility_km: float | None = None
    precipitation_probability_percent: int | None = None
    precipitation_mm: float | None = None
    rain_mm: float | None = None
    showers_mm: float | None = None
    cloud_cover_percent: int | None = None
    wind_speed_kmh: float | None = None
    wind_gusts_kmh: float | None = None
    wind_direction_deg: int | None = None
    wind_direction_cardinal: str | None = None
    uv_index: float | None = None
    condition: WeatherCondition


class HourlyForecastItem(BaseModel):
    """Ponto horário normalizado de previsão do tempo."""

    time: str
    is_day: bool
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    dew_point_c: float | None = None
    relative_humidity_percent: float | None = None
    pressure_msl_hpa: float | None = None
    surface_pressure_hpa: float | None = None
    visibility_km: float | None = None
    precipitation_probability_percent: int | None = None
    precipitation_mm: float | None = None
    rain_mm: float | None = None
    showers_mm: float | None = None
    cloud_cover_percent: int | None = None
    wind_speed_kmh: float | None = None
    wind_gusts_kmh: float | None = None
    wind_direction_deg: int | None = None
    wind_direction_cardinal: str | None = None
    uv_index: float | None = None
    condition: WeatherCondition


class DailyForecastItem(BaseModel):
    """Resumo diário de previsão para até 16 dias."""

    date: str
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    apparent_temperature_max_c: float | None = None
    apparent_temperature_min_c: float | None = None
    precipitation_probability_max_percent: int | None = None
    precipitation_sum_mm: float | None = None
    precipitation_hours: float | None = None
    wind_speed_max_kmh: float | None = None
    wind_gusts_max_kmh: float | None = None
    wind_direction_dominant_deg: int | None = None
    wind_direction_dominant_cardinal: str | None = None
    uv_index_max: float | None = None
    daylight_duration_hours: float | None = None
    sunshine_duration_hours: float | None = None
    sunrise: str | None = None
    sunset: str | None = None
    condition: WeatherCondition


class AirQualityCurrent(BaseModel):
    """Indicadores complementares de qualidade do ar."""

    time: str | None = None
    european_aqi: int | None = None
    us_aqi: int | None = None
    category_pt: str | None = None
    pm2_5: float | None = None
    pm10: float | None = None
    carbon_monoxide: float | None = None
    nitrogen_dioxide: float | None = None
    sulphur_dioxide: float | None = None
    ozone: float | None = None
    dust: float | None = None


class WeatherForecastResponse(BaseModel):
    """Resposta unificada de previsão climática para web e mobile."""

    latitude: float
    longitude: float
    timezone: str
    timezone_abbreviation: str
    utc_offset_seconds: int = 0
    requested_days: int = Field(ge=1, le=16)
    available_days: int = Field(ge=1, le=16)
    generated_at: datetime
    cached: bool = False
    current: CurrentWeather
    hourly_72h: list[HourlyForecastItem]
    hourly: list[HourlyForecastItem]
    daily: list[DailyForecastItem]
    air_quality: AirQualityCurrent | None = None
    attribution: ProviderAttribution
