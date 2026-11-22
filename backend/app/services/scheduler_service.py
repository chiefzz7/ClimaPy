"""Motor periódico de avaliação e disparo de lembretes climáticos (APScheduler)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import decrypt_secret
from app.db.models import Reminder
from app.providers.base import ProviderError
from app.services.push_service import (
    PushConfigurationError,
    PushDeliveryError,
    PushSubscriptionGoneError,
    WebPushService,
    build_weather_notification,
)
from app.services.reminder_service import parse_days_of_week
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SchedulerRunStats:
    """Métricas de uma varredura do agendador (sem dados sensíveis)."""

    checked: int
    due: int
    sent: int
    skipped_rain: int
    deleted_gone: int
    failed: int


def is_reminder_due(reminder: Reminder, now_utc: datetime) -> bool:
    """Avalia se um lembrete deve disparar no minuto local correspondente a now_utc."""
    if not reminder.enabled:
        return False

    try:
        tz = ZoneInfo(reminder.timezone)
    except ZoneInfoNotFoundError:
        return False

    aware_now = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=UTC)
    local_now = aware_now.astimezone(tz)
    if local_now.strftime("%H:%M") != reminder.time_of_day:
        return False

    if reminder.last_sent_at is not None:
        last_aware = (
            reminder.last_sent_at
            if reminder.last_sent_at.tzinfo is not None
            else reminder.last_sent_at.replace(tzinfo=UTC)
        )
        if last_aware.astimezone(tz).strftime("%Y-%m-%d %H:%M") == local_now.strftime(
            "%Y-%m-%d %H:%M"
        ):
            return False

    if reminder.schedule_type == "daily":
        return True
    if reminder.schedule_type == "weekly":
        return local_now.weekday() in parse_days_of_week(reminder.days_of_week)
    if reminder.schedule_type == "once":
        return reminder.once_date == local_now.strftime("%Y-%m-%d")
    return False


class SchedulerService:
    """Orquestra varreduras periódicas de lembretes e disparo via Web Push."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        weather_service: WeatherService,
        push_service: WebPushService,
        data_encryption_key: str | None,
        poll_seconds: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._weather_service = weather_service
        self._push_service = push_service
        self._encryption_key = data_encryption_key.strip() if data_encryption_key else None
        self._poll_seconds = poll_seconds
        self._scheduler = AsyncIOScheduler(timezone=UTC)
        self._started = False

    def start(self) -> None:
        """Inicia o job periódico em background."""
        if self._started:
            return
        self._scheduler.add_job(
            self.process_due_reminders,
            trigger=IntervalTrigger(seconds=self._poll_seconds),
            id="climapy_reminder_poll",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        self._started = True

    def shutdown(self) -> None:
        """Encerra o agendador de forma limpa no desligamento da API."""
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False

    async def process_due_reminders(
        self,
        *,
        now_utc: datetime | None = None,
    ) -> SchedulerRunStats:
        """Processa todos os lembretes elegíveis no minuto corrente."""
        if not self._encryption_key or not self._push_service.is_configured:
            return SchedulerRunStats(
                checked=0,
                due=0,
                sent=0,
                skipped_rain=0,
                deleted_gone=0,
                failed=0,
            )

        current_utc = now_utc or datetime.now(UTC)
        checked = 0
        due = 0
        sent = 0
        skipped_rain = 0
        deleted_gone = 0
        failed = 0

        async with self._session_factory() as session:
            result = await session.execute(select(Reminder).where(Reminder.enabled.is_(True)))
            reminders = list(result.scalars().all())
            checked = len(reminders)

            for reminder in reminders:
                if not is_reminder_due(reminder, current_utc):
                    continue
                due += 1

                try:
                    forecast = await self._weather_service.get_forecast(
                        latitude=reminder.latitude,
                        longitude=reminder.longitude,
                        days=3,
                        timezone=reminder.timezone,
                        include_air_quality=False,
                        include_full_hourly=False,
                    )
                    message = build_weather_notification(
                        location_name=reminder.location_name,
                        forecast=forecast,
                        window=reminder.forecast_window,
                        min_rain_probability=reminder.min_rain_probability,
                        ignore_rain_threshold=False,
                    )
                    if message is None:
                        reminder.last_sent_at = current_utc
                        reminder.last_error = None
                        if reminder.schedule_type == "once":
                            reminder.enabled = False
                        skipped_rain += 1
                        continue

                    raw_sub = decrypt_secret(reminder.subscription_encrypted, self._encryption_key)
                    sub_info = json.loads(raw_sub)
                    if not isinstance(sub_info, dict):
                        raise ValueError("Subscription cifrada inválida.")

                    await self._push_service.send_notification(
                        subscription_info=sub_info,
                        message=message,
                    )
                    reminder.last_sent_at = current_utc
                    reminder.last_error = None
                    if reminder.schedule_type == "once":
                        reminder.enabled = False
                    sent += 1

                except PushSubscriptionGoneError:
                    await session.delete(reminder)
                    deleted_gone += 1
                except (
                    ProviderError,
                    PushDeliveryError,
                    PushConfigurationError,
                    ValueError,
                ) as exc:
                    reminder.last_error = type(exc).__name__[:120]
                    failed += 1
                    logger.warning(
                        "Falha ao processar lembrete %s (%s).",
                        reminder.id,
                        type(exc).__name__,
                    )

            await session.commit()

        return SchedulerRunStats(
            checked=checked,
            due=due,
            sent=sent,
            skipped_rain=skipped_rain,
            deleted_gone=deleted_gone,
            failed=failed,
        )
