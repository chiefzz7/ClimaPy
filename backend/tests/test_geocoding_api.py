"""Testes dos endpoints de busca de cidades e geocodificação reversa."""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from app.providers.nominatim import NominatimReverseGeocodingProvider
from app.providers.open_meteo import OpenMeteoGeocodingProvider


def test_geocoding_search_returns_portuguese_results_and_uses_cache(client: TestClient) -> None:
    sample_payload = {
        "results": [
            {
                "id": 3448439,
                "name": "São Paulo",
                "latitude": -23.5475,
                "longitude": -46.63611,
                "country_code": "BR",
                "country": "Brasil",
                "admin1": "São Paulo",
                "timezone": "America/Sao_Paulo",
            }
        ]
    }
    with respx.mock(assert_all_mocked=True) as router:
        route = router.get(OpenMeteoGeocodingProvider.GEOCODING_URL).mock(
            return_value=httpx.Response(200, json=sample_payload)
        )

        first = client.get("/api/v1/geocoding/search", params={"q": "São Paulo", "lang": "pt"})
        assert first.status_code == 200
        body = first.json()
        assert body["cached"] is False
        assert len(body["results"]) == 1
        assert body["results"][0]["display_name"] == "São Paulo, São Paulo, Brasil"
        assert body["results"][0]["latitude"] == -23.55
        assert body["results"][0]["longitude"] == -46.64

        second = client.get(
            "/api/v1/geocoding/search",
            params={"q": "  são   paulo ", "lang": "pt"},
        )
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert route.call_count == 1


def test_geocoding_search_rejects_short_or_control_input(client: TestClient) -> None:
    short_resp = client.get("/api/v1/geocoding/search", params={"q": "a"})
    assert short_resp.status_code == 422

    spaces_resp = client.get("/api/v1/geocoding/search", params={"q": "  "})
    assert spaces_resp.status_code == 422

    ctrl_resp = client.get("/api/v1/geocoding/search", params={"q": "Curitiba\n"})
    assert ctrl_resp.status_code == 422


def test_reverse_geocoding_rounds_coordinates_and_caches(client: TestClient) -> None:
    nominatim_payload = {
        "name": "Curitiba",
        "address": {
            "city": "Curitiba",
            "state": "Paraná",
            "country": "Brasil",
            "country_code": "br",
        },
    }
    with respx.mock(assert_all_mocked=True) as router:
        route = router.get(NominatimReverseGeocodingProvider.REVERSE_URL).mock(
            return_value=httpx.Response(200, json=nominatim_payload)
        )

        first = client.get("/api/v1/geocoding/reverse", params={"lat": -25.4284, "lon": -49.2733})
        assert first.status_code == 200
        body = first.json()
        assert body["cached"] is False
        assert body["location"]["name"] == "Curitiba"
        assert body["location"]["latitude"] == -25.43
        assert body["location"]["longitude"] == -49.27
        assert body["attribution"]["provider"] == "nominatim"

        second = client.get(
            "/api/v1/geocoding/reverse",
            params={"lat": -25.4299, "lon": -49.2711},
        )
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert route.call_count == 1
