"""Endpoint de verificação de saúde da API."""

from __future__ import annotations

import platform

from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import get_app_settings
from app.core.config import Settings
from app.core.rate_limit import rate_limit
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Saúde"])


@router.get("/health", response_model=HealthResponse, summary="Verifica saúde da API")
@rate_limit("120/minute")
async def health_check(
    request: Request,
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> HealthResponse:
    """Retorna status operacional e versão da API e do runtime Python."""
    del request
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        python_version=platform.python_version(),
    )
