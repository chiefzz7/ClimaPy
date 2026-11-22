"""Serviço CRUD e disparo de teste para lembretes climáticos sem login."""

from __future__ import annotations

import json
import uuid
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    decrypt_secret,
    encrypt_secret,
    generate_capability_token,
    hash_token,
    round_coordinate,
    verify_token,
)
from app.db.models import Reminder
from app.schemas.reminder import (
    ForecastWindow,
    PushTestResponse,
    ReminderCreateRequest,
    ReminderCreateResponse,
    ReminderResponse,
    ReminderUpdateRequest,
    ScheduleType,
    validate_schedule_rule,
)
from app.services.push_service import (
    PushSubscriptionGoneError,
    WebPushService,
    build_weather_notification,
)
from app.services.weather_service import WeatherService


class ReminderNotFoundError(Exception):
    """Lembrete inexistente ou token de autorização inválido."""


class ReminderConfigurationError(Exception):
    """Chave de criptografia ausente ou mal configurada."""


class ReminderValidationError(Exception):
    """Regra de agendamento inconsistente após atualização parcial."""


def _serialize_days(days: list[int]) -> str:
    return ",".join(str(day) for day in sorted(set(days)))


def parse_days_of_week(serialized: str) -> list[int]:
    """Converte string persistida '0,2,4' para lista ordenada de inteiros."""
    if not serialized.strip():
        return []
    result: list[int] = []
    for chunk in serialized.split(","):
        cleaned = chunk.strip()
        if cleaned.isdigit():
            day = int(cleaned)
            if 0 <= day <= 6:
                result.append(day)
    return sorted(set(result))


def reminder_to_response(model: Reminder) -> ReminderResponse:
    """Converte modelo ORM em contrato público sem vazar segredos."""
    return ReminderResponse(
        id=model.id,
        label=model.label,
        location_name=model.location_name,
        latitude=model.latitude,
        longitude=model.longitude,
        timezone=model.timezone,
        schedule_type=cast(ScheduleType, model.schedule_type),
        time_of_day=model.time_of_day,
        days_of_week=parse_days_of_week(model.days_of_week),
        once_date=model.once_date,
        forecast_window=cast(ForecastWindow, model.forecast_window),
        min_rain_probability=model.min_rain_probability,
        enabled=model.enabled,
        last_sent_at=model.last_sent_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class ReminderService:
    """Gerencia lembretes no SQLite/SQLAlchemy 2.0 com proteção anti-IDOR e Fernet."""

    def __init__(
        self,
        *,
        data_encryption_key: str | None,
        weather_service: WeatherService,
        push_service: WebPushService,
    ) -> None:
        self._encryption_key = data_encryption_key.strip() if data_encryption_key else None
        self._weather_service = weather_service
        self._push_service = push_service

    def _require_encryption_key(self) -> str:
        if not self._encryption_key:
            raise ReminderConfigurationError("DATA_ENCRYPTION_KEY não configurada no servidor.")
        return self._encryption_key

    def decrypt_subscription(self, encrypted_payload: str) -> dict[str, Any]:
        """Decifra payload de PushSubscription protegido em repouso."""
        key = self._require_encryption_key()
        raw_json = decrypt_secret(encrypted_payload, key)
        parsed = json.loads(raw_json)
        if not isinstance(parsed, dict):
            raise ValueError("Payload de subscription inválido.")
        return parsed

    async def _get_authorized_model(
        self,
        session: AsyncSession,
        *,
        reminder_id: str,
        token: str,
    ) -> Reminder:
        try:
            uuid.UUID(reminder_id)
        except ValueError as exc:
            raise ReminderNotFoundError("Lembrete não encontrado.") from exc

        model = await session.get(Reminder, reminder_id)
        if model is None or not verify_token(token, model.token_hash):
            raise ReminderNotFoundError("Lembrete não encontrado.")
        return model

    async def create_reminder(
        self,
        session: AsyncSession,
        *,
        payload: ReminderCreateRequest,
    ) -> ReminderCreateResponse:
        """Cria lembrete anônimo cifrando a subscription e retornando token único."""
        key = self._require_encryption_key()
        capability_token = generate_capability_token()
        encrypted_sub = encrypt_secret(payload.subscription.model_dump_json(), key)

        model = Reminder(
            token_hash=hash_token(capability_token),
            label=payload.label,
            location_name=payload.location_name,
            latitude=round_coordinate(payload.latitude),
            longitude=round_coordinate(payload.longitude),
            timezone=payload.timezone,
            schedule_type=payload.schedule_type,
            time_of_day=payload.time_of_day,
            days_of_week=_serialize_days(payload.days_of_week),
            once_date=payload.once_date,
            forecast_window=payload.forecast_window,
            min_rain_probability=payload.min_rain_probability,
            subscription_encrypted=encrypted_sub,
            enabled=True,
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)
        return ReminderCreateResponse(
            reminder=reminder_to_response(model),
            reminder_token=capability_token,
        )

    async def get_reminder(
        self,
        session: AsyncSession,
        *,
        reminder_id: str,
        token: str,
    ) -> ReminderResponse:
        """Obtém um lembrete após validação do capability token."""
        model = await self._get_authorized_model(session, reminder_id=reminder_id, token=token)
        return reminder_to_response(model)

    async def update_reminder(
        self,
        session: AsyncSession,
        *,
        reminder_id: str,
        token: str,
        payload: ReminderUpdateRequest,
    ) -> ReminderResponse:
        """Atualiza parcialmente um lembrete preservando invariantes de agenda e segurança."""
        model = await self._get_authorized_model(session, reminder_id=reminder_id, token=token)
        fields_set = payload.model_fields_set

        next_schedule_type = (
            payload.schedule_type if payload.schedule_type is not None else model.schedule_type
        )
        next_days = (
            payload.days_of_week
            if "days_of_week" in fields_set and payload.days_of_week is not None
            else parse_days_of_week(model.days_of_week)
        )
        next_once_date = payload.once_date if "once_date" in fields_set else model.once_date

        try:
            validate_schedule_rule(
                schedule_type=next_schedule_type,
                days_of_week=next_days,
                once_date=next_once_date,
            )
        except ValueError as exc:
            raise ReminderValidationError(str(exc)) from exc

        if payload.label is not None:
            model.label = payload.label
        if payload.location_name is not None:
            model.location_name = payload.location_name
        if payload.latitude is not None:
            model.latitude = round_coordinate(payload.latitude)
        if payload.longitude is not None:
            model.longitude = round_coordinate(payload.longitude)
        if payload.timezone is not None:
            model.timezone = payload.timezone
        if payload.time_of_day is not None:
            model.time_of_day = payload.time_of_day
        if payload.forecast_window is not None:
            model.forecast_window = payload.forecast_window
        if "min_rain_probability" in fields_set:
            model.min_rain_probability = payload.min_rain_probability
        if payload.enabled is not None:
            model.enabled = payload.enabled
        if payload.subscription is not None:
            key = self._require_encryption_key()
            model.subscription_encrypted = encrypt_secret(
                payload.subscription.model_dump_json(),
                key,
            )

        model.schedule_type = next_schedule_type
        model.days_of_week = _serialize_days(next_days)
        model.once_date = next_once_date

        await session.commit()
        await session.refresh(model)
        return reminder_to_response(model)

    async def delete_reminder(
        self,
        session: AsyncSession,
        *,
        reminder_id: str,
        token: str,
    ) -> None:
        """Executa remoção definitiva do lembrete após checagem do token."""
        model = await self._get_authorized_model(session, reminder_id=reminder_id, token=token)
        await session.delete(model)
        await session.commit()

    async def send_test_notification(
        self,
        session: AsyncSession,
        *,
        reminder_id: str,
        token: str,
    ) -> PushTestResponse:
        """Dispara notificação de teste usando previsão atualizada da localidade."""
        model = await self._get_authorized_model(session, reminder_id=reminder_id, token=token)
        subscription_info = self.decrypt_subscription(model.subscription_encrypted)

        forecast = await self._weather_service.get_forecast(
            latitude=model.latitude,
            longitude=model.longitude,
            days=3,
            timezone=model.timezone,
            include_air_quality=False,
            include_full_hourly=False,
        )
        message = build_weather_notification(
            location_name=model.location_name,
            forecast=forecast,
            window=model.forecast_window,
            min_rain_probability=model.min_rain_probability,
            ignore_rain_threshold=True,
        )
        if message is None:
            raise ReminderValidationError("Não foi possível compor a mensagem de teste.")

        try:
            await self._push_service.send_notification(
                subscription_info=subscription_info,
                message=message,
            )
        except PushSubscriptionGoneError:
            await session.delete(model)
            await session.commit()
            raise

        return PushTestResponse(
            delivered=True,
            title=message.title,
            body=message.body,
        )
