"""Endpoints de previsão do tempo horária (72h e até 16 dias) e diária."""

from __future__ import annotations

import math
from typing import Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.v1.deps import get_weather_service
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.schemas.weather import WeatherForecastResponse
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["Previsão do Tempo"])

_VALID_TIMEZONES: frozenset[str] = frozenset(available_timezones())
_SETTINGS = get_settings()


@router.get(
    "/forecast",
    response_model=WeatherForecastResponse,
    summary="Previsão horária (destaque 72h + até 16 dias) e qualidade do ar",
)
@rate_limit(_SETTINGS.rate_limit_default)
async def get_weather_forecast(
    request: Request,
    lat: Annotated[float, Query(ge=-90.0, le=90.0, allow_inf_nan=False, description="Latitude")],
    lon: Annotated[float, Query(ge=-180.0, le=180.0, allow_inf_nan=False, description="Longitude")],
    days: Annotated[int, Query(ge=1, le=16, description="Dias de previsão (1 a 16)")] = 16,
    tz: Annotated[
        str,
        Query(min_length=2, max_length=64, description="Fuso IANA ou 'auto'"),
    ] = "auto",
    include_air_quality: Annotated[bool, Query(description="Incluir qualidade do ar")] = True,
    include_full_hourly: Annotated[
        bool,
        Query(
            description=(
                "Incluir série horária completa de todos os dias "
                "(false envia apenas 72h + resumo diário)"
            )
        ),
    ] = True,
    weather_service: WeatherService = Depends(get_weather_service),  # noqa: B008
) -> WeatherForecastResponse:
    """Retorna previsão atual, próxima janela horária de 72h, série completa e resumo diário."""
    del request
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise HTTPException(status_code=422, detail="Coordenadas geográficas inválidas.")

    tz_clean = tz.strip()
    if tz_clean != "auto" and tz_clean not in _VALID_TIMEZONES:
        raise HTTPException(status_code=422, detail="Fuso horário IANA inválido.")

    return await weather_service.get_forecast(
        latitude=lat,
        longitude=lon,
        days=days,
        timezone=tz_clean,
        include_air_quality=include_air_quality,
        include_full_hourly=include_full_hourly,
    )
