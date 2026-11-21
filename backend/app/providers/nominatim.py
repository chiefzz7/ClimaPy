"""Provedor opcional de geocodificação reversa via Nominatim / OpenStreetMap."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.security import round_coordinate
from app.providers.base import ProviderResponseError, ReverseGeocodingProvider, safe_get_json
from app.schemas.common import ProviderAttribution
from app.schemas.geocoding import LocationResult, ReverseGeocodingResponse

_NOMINATIM_ATTRIBUTION = ProviderAttribution(
    provider="nominatim",
    provider_label="OpenStreetMap Nominatim (ODbL)",
    license="ODbL",
    url="https://nominatim.openstreetmap.org/",
    fallback_used=False,
)


def _pick_city_name(payload: dict[str, Any]) -> str:
    address = payload.get("address")
    if isinstance(address, dict):
        for key in ("city", "town", "village", "municipality", "county", "state"):
            candidate = address.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "Localização atual"


class NominatimReverseGeocodingProvider(ReverseGeocodingProvider):
    """Converte latitude e longitude arredondadas em nome de cidade em PT-BR."""

    name = "nominatim"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

    def __init__(self, client: httpx.AsyncClient, *, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent

    async def reverse(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> ReverseGeocodingResponse:
        lat_rounded = round_coordinate(latitude)
        lon_rounded = round_coordinate(longitude)
        params: dict[str, str | int | float] = {
            "lat": lat_rounded,
            "lon": lon_rounded,
            "format": "jsonv2",
            "zoom": 10,
            "addressdetails": 1,
        }
        payload = await safe_get_json(
            self._client,
            self.REVERSE_URL,
            params=params,
            headers={
                "User-Agent": self._user_agent,
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )
        if "error" in payload:
            raise ProviderResponseError(
                "Não foi possível identificar a localidade pelas coordenadas."
            )

        address = payload.get("address")
        address_dict = address if isinstance(address, dict) else {}
        city_name = _pick_city_name(payload)
        admin1 = address_dict.get("state") if isinstance(address_dict.get("state"), str) else None
        country = (
            address_dict.get("country") if isinstance(address_dict.get("country"), str) else None
        )
        country_code = (
            str(address_dict["country_code"]).upper()
            if isinstance(address_dict.get("country_code"), str)
            else None
        )
        parts = [part for part in (city_name, admin1, country) if part]

        return ReverseGeocodingResponse(
            cached=False,
            location=LocationResult(
                id=None,
                name=city_name,
                display_name=", ".join(parts),
                admin1=admin1,
                country=country,
                country_code=country_code,
                latitude=lat_rounded,
                longitude=lon_rounded,
                timezone=None,
            ),
            attribution=_NOMINATIM_ATTRIBUTION.model_copy(),
        )
