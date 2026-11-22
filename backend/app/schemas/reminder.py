"""Contratos Pydantic v2 para lembretes climáticos e notificações Web Push."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.security import validate_push_endpoint

ScheduleType = Literal["daily", "weekly", "once"]
ForecastWindow = Literal["today", "tomorrow", "next_3_days"]

_VALID_TIMEZONES: frozenset[str] = frozenset(available_timezones())


def _clean_text(value: str, *, field_name: str, min_len: int) -> str:
    if any(ord(ch) < 32 for ch in value):
        raise ValueError(f"{field_name} contém caracteres de controle inválidos.")
    cleaned = " ".join(value.strip().split())
    if len(cleaned) < min_len:
        raise ValueError(f"{field_name} deve ter pelo menos {min_len} caracteres.")
    return cleaned


def _clean_key_token(value: str, *, field_name: str) -> str:
    cleaned = value.strip()
    if any(ch.isspace() or ord(ch) < 32 for ch in cleaned):
        raise ValueError(f"{field_name} possui formato inválido.")
    return cleaned


def _validate_timezone_name(value: str) -> str:
    cleaned = value.strip()
    if cleaned not in _VALID_TIMEZONES:
        raise ValueError("Fuso horário IANA inválido.")
    return cleaned


def _validate_days_of_week(values: list[int]) -> list[int]:
    for day in values:
        if day < 0 or day > 6:
            raise ValueError("Dias da semana devem estar entre 0 (segunda) e 6 (domingo).")
    return sorted(set(values))


def _validate_once_date(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    try:
        date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("once_date deve estar no formato válido YYYY-MM-DD.") from exc
    return cleaned


class PushSubscriptionKeys(BaseModel):
    """Chaves criptográficas públicas do navegador para Web Push."""

    p256dh: str = Field(min_length=16, max_length=256)
    auth: str = Field(min_length=8, max_length=128)

    @field_validator("p256dh")
    @classmethod
    def _check_p256dh(cls, value: str) -> str:
        return _clean_key_token(value, field_name="p256dh")

    @field_validator("auth")
    @classmethod
    def _check_auth(cls, value: str) -> str:
        return _clean_key_token(value, field_name="auth")


class PushSubscriptionInput(BaseModel):
    """Inscrição W3C PushSubscription validada contra SSRF."""

    endpoint: str = Field(min_length=12, max_length=2048)
    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def _check_endpoint(cls, value: str) -> str:
        return validate_push_endpoint(value.strip())


class ReminderCreateRequest(BaseModel):
    """Requisição de criação de lembrete climático anônimo."""

    label: str = Field(min_length=2, max_length=80)
    location_name: str = Field(min_length=2, max_length=120)
    latitude: float = Field(ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float = Field(ge=-180.0, le=180.0, allow_inf_nan=False)
    timezone: str = Field(default="America/Sao_Paulo", min_length=2, max_length=64)
    schedule_type: ScheduleType
    time_of_day: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days_of_week: list[int] = Field(default_factory=list, max_length=7)
    once_date: str | None = Field(default=None, min_length=10, max_length=10)
    forecast_window: ForecastWindow = "today"
    min_rain_probability: int | None = Field(default=None, ge=0, le=100)
    subscription: PushSubscriptionInput

    @field_validator("label")
    @classmethod
    def _check_label(cls, value: str) -> str:
        return _clean_text(value, field_name="label", min_len=2)

    @field_validator("location_name")
    @classmethod
    def _check_location_name(cls, value: str) -> str:
        return _clean_text(value, field_name="location_name", min_len=2)

    @field_validator("latitude", "longitude")
    @classmethod
    def _check_finite_coord(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Coordenada geográfica inválida.")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        return _validate_timezone_name(value)

    @field_validator("days_of_week")
    @classmethod
    def _check_days_of_week(cls, value: list[int]) -> list[int]:
        return _validate_days_of_week(value)

    @field_validator("once_date")
    @classmethod
    def _check_once_date(cls, value: str | None) -> str | None:
        return _validate_once_date(value)

    @model_validator(mode="after")
    def _check_schedule_consistency(self) -> ReminderCreateRequest:
        validate_schedule_rule(
            schedule_type=self.schedule_type,
            days_of_week=self.days_of_week,
            once_date=self.once_date,
        )
        return self


class ReminderUpdateRequest(BaseModel):
    """Requisição parcial de atualização de lembrete climático."""

    label: str | None = Field(default=None, min_length=2, max_length=80)
    location_name: str | None = Field(default=None, min_length=2, max_length=120)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0, allow_inf_nan=False)
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    schedule_type: ScheduleType | None = None
    time_of_day: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days_of_week: list[int] | None = Field(default=None, max_length=7)
    once_date: str | None = Field(default=None, min_length=10, max_length=10)
    forecast_window: ForecastWindow | None = None
    min_rain_probability: int | None = Field(default=None, ge=0, le=100)
    enabled: bool | None = None
    subscription: PushSubscriptionInput | None = None

    @field_validator("label")
    @classmethod
    def _check_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(value, field_name="label", min_len=2)

    @field_validator("location_name")
    @classmethod
    def _check_location_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(value, field_name="location_name", min_len=2)

    @field_validator("latitude", "longitude")
    @classmethod
    def _check_finite_coord(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Coordenada geográfica inválida.")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_timezone_name(value)

    @field_validator("days_of_week")
    @classmethod
    def _check_days_of_week(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        return _validate_days_of_week(value)

    @field_validator("once_date")
    @classmethod
    def _check_once_date(cls, value: str | None) -> str | None:
        return _validate_once_date(value)


def validate_schedule_rule(
    *,
    schedule_type: str,
    days_of_week: list[int],
    once_date: str | None,
) -> None:
    """Garante consistência entre schedule_type, days_of_week e once_date."""
    if schedule_type == "weekly":
        if not days_of_week:
            raise ValueError("Lembretes semanais exigem ao menos um dia em days_of_week.")
        if once_date is not None:
            raise ValueError("Lembretes semanais não devem informar once_date.")
    elif schedule_type == "once":
        if not once_date:
            raise ValueError("Lembretes pontuais exigem once_date no formato YYYY-MM-DD.")
        if days_of_week:
            raise ValueError("Lembretes pontuais não devem informar days_of_week.")
    elif schedule_type == "daily":
        if days_of_week:
            raise ValueError("Lembretes diários não devem informar days_of_week.")
        if once_date is not None:
            raise ValueError("Lembretes diários não devem informar once_date.")


class ReminderResponse(BaseModel):
    """Visão pública segura do lembrete (nunca expõe token nem subscription)."""

    id: str
    label: str
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    schedule_type: ScheduleType
    time_of_day: str
    days_of_week: list[int]
    once_date: str | None
    forecast_window: ForecastWindow
    min_rain_probability: int | None
    enabled: bool
    last_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReminderCreateResponse(BaseModel):
    """Resposta única de criação contendo o capability token do dispositivo."""

    reminder: ReminderResponse
    reminder_token: str


class VapidPublicKeyResponse(BaseModel):
    """Chave pública VAPID usada pelo Service Worker para assinar Web Push."""

    configured: bool
    public_key: str | None = None


class PushTestResponse(BaseModel):
    """Resultado do disparo de teste sob demanda."""

    delivered: bool
    title: str
    body: str
