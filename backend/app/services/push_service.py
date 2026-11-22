"""Serviço seguro de formatação e envio de notificações Web Push (VAPID)."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from pywebpush import WebPushException, webpush

from app.core.security import is_ip_blocked, validate_push_endpoint
from app.schemas.weather import WeatherForecastResponse

logger = logging.getLogger(__name__)


class PushConfigurationError(Exception):
    """Chaves VAPID não configuradas para envio Web Push."""


class PushDeliveryError(Exception):
    """Falha temporária ou erro no provedor de Web Push."""


class PushSubscriptionGoneError(PushDeliveryError):
    """Inscrição Web Push expirada ou revogada pelo navegador (HTTP 404/410)."""


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """Conteúdo formatado para disparo de notificação climática."""

    title: str
    body: str
    tag: str
    url: str = "/"


PushSenderCallable = Callable[[dict[str, Any], str, str, dict[str, str], float], None]
DnsCheckerCallable = Callable[[str], Awaitable[None]]


def _resolve_and_check_dns(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise PushDeliveryError("Hostname do endpoint Web Push ausente.")

    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PushDeliveryError("Falha ao resolver DNS do endpoint Web Push.") from exc

    if not infos:
        raise PushDeliveryError("Nenhum endereço retornado pelo DNS para o endpoint Web Push.")

    for info in infos:
        ip_str = str(info[4][0])
        if is_ip_blocked(ip_str):
            raise PushDeliveryError("Endpoint Web Push resolveu para endereço de rede bloqueado.")


async def _default_dns_check(endpoint: str) -> None:
    await asyncio.to_thread(_resolve_and_check_dns, endpoint)


def _default_webpush_sender(
    subscription_info: dict[str, Any],
    data: str,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
    timeout_seconds: float,
) -> None:
    webpush(
        subscription_info=subscription_info,
        data=data,
        vapid_private_key=vapid_private_key,
        vapid_claims=vapid_claims,
        timeout=timeout_seconds,
    )


def _fmt_temp(value: float | None) -> str:
    return f"{round(value)}°C" if value is not None else "--°C"


def _fmt_mm(value: float | None) -> str:
    return f"{value:.1f} mm" if value is not None else "0.0 mm"


def build_weather_notification(
    *,
    location_name: str,
    forecast: WeatherForecastResponse,
    window: str,
    min_rain_probability: int | None,
    ignore_rain_threshold: bool = False,
) -> NotificationMessage | None:
    """Constrói mensagem climática resumida e aplica filtro opcional de chance de chuva."""
    daily = forecast.daily
    if window == "next_3_days":
        slice_days = daily[:3] if daily else []
        if slice_days:
            mins = [d.temperature_min_c for d in slice_days if d.temperature_min_c is not None]
            maxs = [d.temperature_max_c for d in slice_days if d.temperature_max_c is not None]
            probs = [
                d.precipitation_probability_max_percent
                for d in slice_days
                if d.precipitation_probability_max_percent is not None
            ]
            sums = [
                d.precipitation_sum_mm for d in slice_days if d.precipitation_sum_mm is not None
            ]
            rain_prob = max(probs) if probs else forecast.current.precipitation_probability_percent
            rain_mm = round(sum(sums), 1) if sums else None
            t_min = min(mins) if mins else forecast.current.temperature_c
            t_max = max(maxs) if maxs else forecast.current.temperature_c
            cond = slice_days[0].condition.label_pt
        else:
            rain_prob = forecast.current.precipitation_probability_percent
            rain_mm = forecast.current.precipitation_mm
            t_min = forecast.current.temperature_c
            t_max = forecast.current.temperature_c
            cond = forecast.current.condition.label_pt

        if (
            min_rain_probability is not None
            and not ignore_rain_threshold
            and (rain_prob or 0) < min_rain_probability
        ):
            return None

        prob_txt = f"{rain_prob}%" if rain_prob is not None else "--%"
        return NotificationMessage(
            title=f"ClimaPy • {location_name} (3 dias)",
            body=(
                f"{cond}. Temperaturas entre {_fmt_temp(t_min)} e {_fmt_temp(t_max)}. "
                f"Chuva até {prob_txt} ({_fmt_mm(rain_mm)})."
            ),
            tag=f"climapy-{location_name.lower()}-3d",
        )

    day_index = 1 if window == "tomorrow" and len(daily) > 1 else 0
    window_label = "amanhã" if day_index == 1 else "hoje"

    if daily:
        target_day = daily[day_index]
        rain_prob = target_day.precipitation_probability_max_percent
        rain_mm = target_day.precipitation_sum_mm
        t_min = target_day.temperature_min_c
        t_max = target_day.temperature_max_c
        cond = target_day.condition.label_pt
    else:
        rain_prob = forecast.current.precipitation_probability_percent
        rain_mm = forecast.current.precipitation_mm
        t_min = forecast.current.temperature_c
        t_max = forecast.current.temperature_c
        cond = forecast.current.condition.label_pt

    if (
        min_rain_probability is not None
        and not ignore_rain_threshold
        and (rain_prob or 0) < min_rain_probability
    ):
        return None

    prob_txt = f"{rain_prob}%" if rain_prob is not None else "--%"
    return NotificationMessage(
        title=f"ClimaPy • {location_name} ({window_label})",
        body=(
            f"{cond} ({_fmt_temp(t_min)} a {_fmt_temp(t_max)}). "
            f"Chance de chuva: {prob_txt} ({_fmt_mm(rain_mm)})."
        ),
        tag=f"climapy-{location_name.lower()}-{window_label}",
    )


class WebPushService:
    """Envia notificações Web Push assinadas via VAPID sem vazar subscriptions em logs."""

    def __init__(
        self,
        *,
        vapid_public_key: str | None,
        vapid_private_key: str | None,
        vapid_subject: str,
        timeout_seconds: float = 10.0,
        sender: PushSenderCallable | None = None,
        dns_checker: DnsCheckerCallable | None = None,
    ) -> None:
        self._vapid_public_key = vapid_public_key.strip() if vapid_public_key else None
        self._vapid_private_key = vapid_private_key.strip() if vapid_private_key else None
        self._vapid_subject = vapid_subject
        self._timeout_seconds = timeout_seconds
        self._sender = sender or _default_webpush_sender
        self._dns_checker = dns_checker or _default_dns_check

    @property
    def is_configured(self) -> bool:
        """Indica se as chaves VAPID estão disponíveis para assinatura."""
        return bool(self._vapid_public_key and self._vapid_private_key)

    @property
    def public_key(self) -> str | None:
        """Retorna a chave pública VAPID para uso no navegador."""
        return self._vapid_public_key if self.is_configured else None

    async def send_notification(
        self,
        *,
        subscription_info: dict[str, Any],
        message: NotificationMessage,
    ) -> None:
        """Valida endpoint anti-SSRF e envia push VAPID em thread separada."""
        if not self.is_configured or self._vapid_private_key is None:
            raise PushConfigurationError("Chaves VAPID não configuradas no servidor.")

        endpoint_raw = subscription_info.get("endpoint")
        if not isinstance(endpoint_raw, str):
            raise PushDeliveryError("Subscription armazenada sem endpoint válido.")

        try:
            safe_endpoint = validate_push_endpoint(endpoint_raw)
        except ValueError as exc:
            raise PushDeliveryError("Endpoint Web Push rejeitado pela política anti-SSRF.") from exc

        await self._dns_checker(safe_endpoint)

        payload_json = json.dumps(
            {
                "title": message.title,
                "body": message.body,
                "tag": message.tag,
                "url": message.url,
            },
            ensure_ascii=False,
        )

        try:
            await asyncio.to_thread(
                self._sender,
                subscription_info,
                payload_json,
                self._vapid_private_key,
                {"sub": self._vapid_subject},
                self._timeout_seconds,
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {404, 410}:
                raise PushSubscriptionGoneError(
                    "Subscription Web Push expirada ou removida."
                ) from exc
            logger.warning("Falha ao entregar Web Push (status=%s).", status_code)
            raise PushDeliveryError("Falha ao entregar notificação no provedor Web Push.") from exc
        except PushDeliveryError:
            raise
        except Exception as exc:
            logger.warning("Erro inesperado ao enviar Web Push (%s).", type(exc).__name__)
            raise PushDeliveryError("Erro ao enviar notificação Web Push.") from exc
