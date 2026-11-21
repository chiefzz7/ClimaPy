"""Agregador de rotas da API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.geocoding import router as geocoding_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.weather import router as weather_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(weather_router)
api_v1_router.include_router(geocoding_router)
