"""Ponto de entrada FastAPI do backend ClimaPy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.core.security import SecurityHeadersMiddleware
from app.db.base import create_engine_and_sessionmaker, init_db
from app.providers.base import ProviderError
from app.providers.met_norway import MetNorwayWeatherProvider
from app.providers.nominatim import NominatimReverseGeocodingProvider
from app.providers.open_meteo import (
    OpenMeteoAirQualityProvider,
    OpenMeteoGeocodingProvider,
    OpenMeteoWeatherProvider,
)
from app.services.cache_service import CacheService
from app.services.push_service import WebPushService
from app.services.reminder_service import ReminderService
from app.services.scheduler_service import SchedulerService
from app.services.weather_service import WeatherService


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """Fábrica da aplicação FastAPI com dependências seguras e middlewares."""
    settings = settings_override or get_settings()
    limiter.enabled = settings.rate_limit_enabled

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
        await init_db(engine)

        timeout = httpx.Timeout(
            connect=5.0,
            read=settings.http_timeout_seconds,
            write=5.0,
            pool=5.0,
        )
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as http_client:
            cache_service = CacheService(
                weather_ttl_seconds=settings.weather_cache_ttl_seconds,
                geocoding_ttl_seconds=settings.geocoding_cache_ttl_seconds,
            )
            primary_weather = OpenMeteoWeatherProvider(
                http_client,
                user_agent=settings.app_user_agent,
            )
            fallback_weather = MetNorwayWeatherProvider(
                http_client,
                user_agent=settings.app_user_agent,
            )
            air_quality_provider = OpenMeteoAirQualityProvider(
                http_client,
                user_agent=settings.app_user_agent,
            )
            geocoding_provider = OpenMeteoGeocodingProvider(
                http_client,
                user_agent=settings.app_user_agent,
            )
            reverse_provider = NominatimReverseGeocodingProvider(
                http_client,
                user_agent=settings.app_user_agent,
            )
            weather_service = WeatherService(
                primary_provider=primary_weather,
                fallback_provider=fallback_weather,
                air_quality_provider=air_quality_provider,
                cache=cache_service,
            )
            encryption_key = (
                settings.data_encryption_key.get_secret_value()
                if settings.data_encryption_key is not None
                else None
            )
            vapid_private_key = (
                settings.vapid_private_key.get_secret_value()
                if settings.vapid_private_key is not None
                else None
            )
            push_service = WebPushService(
                vapid_public_key=settings.vapid_public_key,
                vapid_private_key=vapid_private_key,
                vapid_subject=settings.vapid_subject,
                timeout_seconds=settings.http_timeout_seconds,
            )
            reminder_service = ReminderService(
                data_encryption_key=encryption_key,
                weather_service=weather_service,
                push_service=push_service,
            )
            scheduler_service = SchedulerService(
                session_factory=session_factory,
                weather_service=weather_service,
                push_service=push_service,
                data_encryption_key=encryption_key,
                poll_seconds=settings.scheduler_poll_seconds,
            )

            application.state.settings = settings
            application.state.db_engine = engine
            application.state.session_factory = session_factory
            application.state.http_client = http_client
            application.state.cache_service = cache_service
            application.state.weather_service = weather_service
            application.state.geocoding_provider = geocoding_provider
            application.state.reverse_geocoding_provider = reverse_provider
            application.state.push_service = push_service
            application.state.reminder_service = reminder_service
            application.state.scheduler_service = scheduler_service

            if settings.scheduler_enabled:
                scheduler_service.start()
            try:
                yield
            finally:
                scheduler_service.shutdown()
                await engine.dispose()

    is_production = settings.app_env == "production"
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )

    application.state.limiter = limiter
    application.add_middleware(SecurityHeadersMiddleware, app_env=settings.app_env)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Reminder-Token"],
    )

    @application.exception_handler(ProviderError)
    async def handle_provider_error(request: Request, exc: ProviderError) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=503,
            content={"detail": "Provedor meteorológico externo temporariamente indisponível."},
        )

    @application.exception_handler(RateLimitExceeded)
    async def handle_rate_limit_exceeded(
        request: Request,
        exc: RateLimitExceeded,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=429,
            content={"detail": "Muitas requisições em sequência. Aguarde alguns instantes."},
        )

    application.include_router(api_v1_router)
    return application


app = create_app()
