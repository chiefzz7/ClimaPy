"""Testes dos endpoints de saúde e previsão do tempo (72h + até 16 dias + fallback)."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.wmo_codes import degrees_to_cardinal_pt
from app.providers.met_norway import MetNorwayWeatherProvider
from app.providers.open_meteo import OpenMeteoAirQualityProvider, OpenMeteoWeatherProvider
from app.services.ai.base import NoOpAIAnalyzer
from tests.conftest import (
    build_air_quality_payload,
    build_met_norway_payload,
    build_open_meteo_payload,
)


def test_health_endpoint_reports_python_312(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ClimaPy"
    assert data["python_version"].startswith("3.12")


def test_forecast_16_days_with_72h_highlight_and_cache_hit(client: TestClient) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        weather_route = router.get(OpenMeteoWeatherProvider.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=build_open_meteo_payload(days=16))
        )
        aq_route = router.get(OpenMeteoAirQualityProvider.AIR_QUALITY_URL).mock(
            return_value=httpx.Response(200, json=build_air_quality_payload())
        )

        first = client.get(
            "/api/v1/weather/forecast",
            params={"lat": -23.5512, "lon": -46.6334, "days": 16, "tz": "America/Sao_Paulo"},
        )
        assert first.status_code == 200
        body = first.json()

        assert body["latitude"] == -23.55
        assert body["longitude"] == -46.63
        assert body["requested_days"] == 16
        assert body["available_days"] == 16
        assert body["cached"] is False
        assert len(body["hourly_72h"]) == 72
        assert len(body["hourly"]) == 384
        assert len(body["daily"]) == 16
        assert body["current"]["condition"]["label_pt"] == "Parcialmente nublado"
        assert body["current"]["precipitation_probability_percent"] == 40
        assert body["current"]["wind_direction_deg"] == 67
        assert body["current"]["wind_direction_cardinal"] == "ENE"
        assert body["current"]["pressure_msl_hpa"] == 1015.2
        assert body["current"]["dew_point_c"] == 17.5
        assert body["current"]["visibility_km"] == 24.1
        assert body["daily"][0]["daylight_duration_hours"] == 13.0
        assert body["daily"][0]["sunshine_duration_hours"] == 9.0
        assert body["daily"][0]["precipitation_hours"] == 4.0
        assert body["daily"][0]["wind_direction_dominant_cardinal"] == "L"
        assert body["air_quality"]["category_pt"] == "Razoável"
        assert body["air_quality"]["carbon_monoxide"] == 210.5
        assert body["air_quality"]["sulphur_dioxide"] == 3.1
        assert body["air_quality"]["dust"] == 6.4
        assert body["attribution"]["provider"] == "open_meteo"
        assert body["attribution"]["fallback_used"] is False

        second = client.get(
            "/api/v1/weather/forecast",
            params={"lat": -23.554, "lon": -46.631, "days": 16, "tz": "America/Sao_Paulo"},
        )
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert weather_route.call_count == 1
        assert aq_route.call_count == 1


def test_forecast_fallback_to_met_norway_when_open_meteo_fails(client: TestClient) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        router.get(OpenMeteoWeatherProvider.FORECAST_URL).mock(
            return_value=httpx.Response(503, json={"error": True})
        )
        router.get(MetNorwayWeatherProvider.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=build_met_norway_payload())
        )
        router.get(OpenMeteoAirQualityProvider.AIR_QUALITY_URL).mock(
            return_value=httpx.Response(503, json={"error": True})
        )

        response = client.get(
            "/api/v1/weather/forecast",
            params={"lat": -25.43, "lon": -49.27, "days": 3, "tz": "America/Sao_Paulo"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["attribution"]["provider"] == "met_norway"
        assert body["attribution"]["fallback_used"] is True
        assert body["air_quality"] is None
        assert body["current"]["wind_speed_kmh"] == 14.4
        assert body["current"]["wind_direction_cardinal"] == "O"
        assert body["current"]["pressure_msl_hpa"] == 1014.2
        assert body["current"]["dew_point_c"] == 16.4
        assert body["current"]["condition"]["label_pt"] == "Chuva fraca"
        assert len(body["daily"]) >= 1
        assert body["daily"][0]["wind_direction_dominant_cardinal"] == "O"
        assert body["daily"][0]["precipitation_hours"] >= 1.0


def test_forecast_returns_503_when_all_providers_fail(client: TestClient) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        router.get(OpenMeteoWeatherProvider.FORECAST_URL).mock(return_value=httpx.Response(503))
        router.get(MetNorwayWeatherProvider.FORECAST_URL).mock(return_value=httpx.Response(503))

        response = client.get(
            "/api/v1/weather/forecast",
            params={"lat": -23.55, "lon": -46.63, "days": 3},
        )
        assert response.status_code == 503
        assert "indisponível" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "params",
    [
        {"lat": 91.0, "lon": -46.63, "days": 3},
        {"lat": -23.55, "lon": -181.0, "days": 3},
        {"lat": -23.55, "lon": -46.63, "days": 0},
        {"lat": -23.55, "lon": -46.63, "days": 17},
        {"lat": -23.55, "lon": -46.63, "days": 3, "tz": "Invalid/Timezone"},
    ],
)
def test_forecast_rejects_invalid_query_parameters(
    client: TestClient,
    params: dict[str, object],
) -> None:
    response = client.get("/api/v1/weather/forecast", params=params)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_noop_ai_analyzer_returns_disabled_insight() -> None:
    from app.providers.open_meteo import OpenMeteoWeatherProvider as OMProvider

    provider = OMProvider(httpx.AsyncClient(), user_agent="ClimaPy-Test/0.2")
    forecast = provider._parse_forecast(
        build_open_meteo_payload(days=3),
        latitude=-23.55,
        longitude=-46.63,
        days=3,
    )
    insight = await NoOpAIAnalyzer().analyze(forecast)
    assert insight.enabled is False


def test_forecast_compact_mode_warms_full_cache(client: TestClient) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        weather_route = router.get(OpenMeteoWeatherProvider.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=build_open_meteo_payload(days=16))
        )
        router.get(OpenMeteoAirQualityProvider.AIR_QUALITY_URL).mock(
            return_value=httpx.Response(200, json=build_air_quality_payload())
        )

        compact = client.get(
            "/api/v1/weather/forecast",
            params={
                "lat": -24.49,
                "lon": -47.84,
                "days": 16,
                "include_full_hourly": "false",
            },
        )
        assert compact.status_code == 200
        compact_body = compact.json()
        assert compact_body["cached"] is False
        assert compact_body["hourly"] == []
        assert len(compact_body["hourly_72h"]) == 72
        assert len(compact_body["daily"]) == 16

        full = client.get(
            "/api/v1/weather/forecast",
            params={
                "lat": -24.49,
                "lon": -47.84,
                "days": 16,
                "include_full_hourly": "true",
            },
        )
        assert full.status_code == 200
        full_body = full.json()
        assert full_body["cached"] is True
        assert len(full_body["hourly"]) == 384
        assert weather_route.call_count == 1


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [
        (0.0, "N"),
        (67.5, "ENE"),
        (90.0, "L"),
        (180.0, "S"),
        (270.0, "O"),
        (359.0, "N"),
        (-10.0, "N"),
        (None, None),
    ],
)
def test_degrees_to_cardinal_pt(degrees: float | None, expected: str | None) -> None:
    assert degrees_to_cardinal_pt(degrees) == expected
