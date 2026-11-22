"""Fixtures e payloads simulados para testes offline do backend ClimaPy."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from scripts.generate_keys import generate_local_keys


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Retorna configurações isoladas para execução de testes offline."""
    keys = generate_local_keys()
    return Settings(
        app_env="testing",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'climapy_test.db'}",
        rate_limit_enabled=False,
        scheduler_enabled=False,
        weather_cache_ttl_seconds=900,
        geocoding_cache_ttl_seconds=86400,
        http_timeout_seconds=5.0,
        data_encryption_key=SecretStr(keys.data_encryption_key),
        vapid_public_key=keys.vapid_public_key,
        vapid_private_key=SecretStr(keys.vapid_private_key),
        vapid_subject="mailto:test@climapy.local",
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """Cria cliente HTTP de teste com ciclo completo de lifespan."""
    app = create_app(settings_override=test_settings)
    with TestClient(app) as test_client:
        yield test_client


def build_open_meteo_payload(days: int = 16) -> dict[str, Any]:
    """Gera payload realista da Open-Meteo para até 16 dias horários."""
    base_dt = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    total_hours = days * 24

    hourly_times: list[str] = []
    temps: list[float] = []
    apparents: list[float] = []
    dew_points: list[float] = []
    humidities: list[int] = []
    pressures_msl: list[float] = []
    surface_pressures: list[float] = []
    visibilities: list[float] = []
    precip_probs: list[int] = []
    precips: list[float] = []
    rains: list[float] = []
    showers: list[float] = []
    codes: list[int] = []
    clouds: list[int] = []
    winds: list[float] = []
    gusts: list[float] = []
    wind_dirs: list[int] = []
    uvs: list[float] = []
    is_days: list[int] = []

    for hour_idx in range(total_hours):
        dt = base_dt + timedelta(hours=hour_idx)
        hourly_times.append(dt.strftime("%Y-%m-%dT%H:%M"))
        temps.append(round(22.0 + (hour_idx % 8) * 0.8, 1))
        apparents.append(round(23.0 + (hour_idx % 8) * 0.8, 1))
        dew_points.append(round(17.5 + (hour_idx % 4) * 0.5, 1))
        humidities.append(65 + (hour_idx % 20))
        pressures_msl.append(1015.4)
        surface_pressures.append(1012.8)
        visibilities.append(24100.0)
        precip_probs.append(40 if hour_idx % 3 == 0 else 10)
        precips.append(1.2 if hour_idx % 6 == 0 else 0.0)
        rains.append(1.2 if hour_idx % 6 == 0 else 0.0)
        showers.append(0.0)
        codes.append(61 if hour_idx % 6 == 0 else 2)
        clouds.append(55)
        winds.append(14.5)
        gusts.append(24.0)
        wind_dirs.append(67)
        uvs.append(6.2 if 6 <= dt.hour < 18 else 0.0)
        is_days.append(1 if 6 <= dt.hour < 18 else 0)

    daily_dates: list[str] = []
    for day_idx in range(days):
        daily_dates.append((base_dt + timedelta(days=day_idx)).strftime("%Y-%m-%d"))

    return {
        "latitude": -23.55,
        "longitude": -46.63,
        "utc_offset_seconds": -10800,
        "timezone": "America/Sao_Paulo",
        "timezone_abbreviation": "GMT-3",
        "current": {
            "time": "2026-11-20T12:15",
            "temperature_2m": 24.5,
            "relative_humidity_2m": 68,
            "apparent_temperature": 25.1,
            "is_day": 1,
            "precipitation": 0.0,
            "rain": 0.0,
            "showers": 0.0,
            "weather_code": 2,
            "cloud_cover": 45,
            "pressure_msl": 1015.2,
            "surface_pressure": 1012.6,
            "wind_speed_10m": 13.0,
            "wind_gusts_10m": 22.0,
            "wind_direction_10m": 67,
        },
        "hourly": {
            "time": hourly_times,
            "temperature_2m": temps,
            "relative_humidity_2m": humidities,
            "apparent_temperature": apparents,
            "dew_point_2m": dew_points,
            "pressure_msl": pressures_msl,
            "surface_pressure": surface_pressures,
            "visibility": visibilities,
            "precipitation_probability": precip_probs,
            "precipitation": precips,
            "rain": rains,
            "showers": showers,
            "weather_code": codes,
            "cloud_cover": clouds,
            "wind_speed_10m": winds,
            "wind_gusts_10m": gusts,
            "wind_direction_10m": wind_dirs,
            "uv_index": uvs,
            "is_day": is_days,
        },
        "daily": {
            "time": daily_dates,
            "weather_code": [61 if i % 2 == 0 else 1 for i in range(days)],
            "temperature_2m_max": [28.0 for _ in range(days)],
            "temperature_2m_min": [18.5 for _ in range(days)],
            "apparent_temperature_max": [29.2 for _ in range(days)],
            "apparent_temperature_min": [18.0 for _ in range(days)],
            "sunrise": [f"{d}T05:20" for d in daily_dates],
            "sunset": [f"{d}T18:35" for d in daily_dates],
            "daylight_duration": [46800.0 for _ in range(days)],
            "sunshine_duration": [32400.0 for _ in range(days)],
            "uv_index_max": [8.0 for _ in range(days)],
            "precipitation_sum": [4.5 if i % 2 == 0 else 0.0 for i in range(days)],
            "precipitation_hours": [4.0 if i % 2 == 0 else 0.0 for i in range(days)],
            "precipitation_probability_max": [70 if i % 2 == 0 else 15 for i in range(days)],
            "wind_speed_10m_max": [20.0 for _ in range(days)],
            "wind_gusts_10m_max": [34.0 for _ in range(days)],
            "wind_direction_10m_dominant": [90 for _ in range(days)],
        },
    }


def build_air_quality_payload() -> dict[str, Any]:
    """Gera payload simulado da Open-Meteo Air Quality API."""
    return {
        "latitude": -23.55,
        "longitude": -46.63,
        "current": {
            "time": "2026-11-20T12:00",
            "european_aqi": 28,
            "us_aqi": 42,
            "pm10": 18.4,
            "pm2_5": 9.8,
            "carbon_monoxide": 210.5,
            "nitrogen_dioxide": 14.2,
            "sulphur_dioxide": 3.1,
            "ozone": 48.0,
            "dust": 6.4,
        },
    }


def build_met_norway_payload() -> dict[str, Any]:
    """Gera payload simulado do provedor fallback MET Norway Locationforecast 2.0."""
    base_dt = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
    series: list[dict[str, Any]] = []
    for hour_idx in range(48):
        dt = base_dt + timedelta(hours=hour_idx)
        series.append(
            {
                "time": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {
                    "instant": {
                        "details": {
                            "air_temperature": 21.0 + (hour_idx % 5),
                            "dew_point_temperature": 16.4,
                            "relative_humidity": 72.0,
                            "air_pressure_at_sea_level": 1014.2,
                            "cloud_area_fraction": 50.0,
                            "wind_speed": 4.0,
                            "wind_speed_of_gust": 7.5,
                            "wind_from_direction": 270.0,
                            "ultraviolet_index_clear_sky": 3.5,
                        }
                    },
                    "next_1_hours": {
                        "summary": {"symbol_code": "lightrain_day"},
                        "details": {
                            "precipitation_amount": 0.6,
                            "probability_of_precipitation": 55.0,
                        },
                    },
                },
            }
        )
    return {
        "type": "Feature",
        "properties": {"timeseries": series},
    }
