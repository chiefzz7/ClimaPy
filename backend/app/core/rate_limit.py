"""Configuração de rate limiting por IP via slowapi."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

F = TypeVar("F", bound=Callable[..., Any])

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    enabled=_settings.rate_limit_enabled,
)


def rate_limit(limit_value: str) -> Callable[[F], F]:
    """Decorator tipado para aplicar limites de taxa por rota."""
    return cast(Callable[[F], F], limiter.limit(limit_value))
