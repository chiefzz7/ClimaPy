"""Endpoints de busca de cidades e geocodificação reversa com cache."""

from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.v1.deps import (
    get_cache_service,
    get_geocoding_provider,
    get_reverse_geocoding_provider,
)
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.core.security import round_coordinate
from app.providers.base import GeocodingProvider, ReverseGeocodingProvider
from app.schemas.geocoding import GeocodingSearchResponse, ReverseGeocodingResponse
from app.services.cache_service import CacheService

router = APIRouter(prefix="/geocoding", tags=["Localização"])
_SETTINGS = get_settings()


@router.get(
    "/search",
    response_model=GeocodingSearchResponse,
    summary="Busca cidades pelo nome",
)
@rate_limit(_SETTINGS.rate_limit_geocoding)
async def search_locations(
    request: Request,
    q: Annotated[str, Query(min_length=2, max_length=100, description="Nome da cidade")],
    count: Annotated[int, Query(ge=1, le=10, description="Máximo de resultados")] = 5,
    lang: Annotated[str, Query(pattern=r"^[a-z]{2}$", description="Idioma ISO 639-1")] = "pt",
    cache: CacheService = Depends(get_cache_service),  # noqa: B008
    provider: GeocodingProvider = Depends(get_geocoding_provider),  # noqa: B008
) -> GeocodingSearchResponse:
    """Pesquisa cidades com normalização e cache de 24h."""
    del request
    if any(ord(ch) < 32 for ch in q):
        raise HTTPException(status_code=422, detail="Termo de busca contém caracteres inválidos.")
    cleaned_query = " ".join(q.strip().split())
    if len(cleaned_query) < 2:
        raise HTTPException(status_code=422, detail="Informe pelo menos 2 caracteres para busca.")

    cached = cache.get_geocoding(query=cleaned_query, count=count, lang=lang)
    if cached is not None:
        return cached

    result = await provider.search(query=cleaned_query, count=count, lang=lang)
    cache.set_geocoding(query=cleaned_query, count=count, lang=lang, value=result)
    return result


@router.get(
    "/reverse",
    response_model=ReverseGeocodingResponse,
    summary="Identifica cidade pelas coordenadas arredondadas",
)
@rate_limit(_SETTINGS.rate_limit_reverse)
async def reverse_geocode(
    request: Request,
    lat: Annotated[float, Query(ge=-90.0, le=90.0, allow_inf_nan=False, description="Latitude")],
    lon: Annotated[float, Query(ge=-180.0, le=180.0, allow_inf_nan=False, description="Longitude")],
    cache: CacheService = Depends(get_cache_service),  # noqa: B008
    provider: ReverseGeocodingProvider = Depends(get_reverse_geocoding_provider),  # noqa: B008
) -> ReverseGeocodingResponse:
    """Converte coordenadas arredondadas (~1,1 km) em nome de localidade com cache de 24h."""
    del request
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise HTTPException(status_code=422, detail="Coordenadas geográficas inválidas.")

    lat_rounded = round_coordinate(lat)
    lon_rounded = round_coordinate(lon)
    cached = cache.get_reverse_geocoding(latitude=lat_rounded, longitude=lon_rounded)
    if cached is not None:
        return cached

    result = await provider.reverse(latitude=lat_rounded, longitude=lon_rounded)
    cache.set_reverse_geocoding(latitude=lat_rounded, longitude=lon_rounded, value=result)
    return result
