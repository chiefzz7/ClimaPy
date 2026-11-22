"""Testes de lembretes sem login, anti-IDOR, Fernet, anti-SSRF Web Push e APScheduler."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from py_vapid import Vapid
from pywebpush import WebPushException
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import decrypt_secret, is_ip_blocked, validate_push_endpoint
from app.db.models import Reminder
from app.providers.open_meteo import OpenMeteoWeatherProvider
from app.services.push_service import (
    PushDeliveryError,
    WebPushService,
    build_weather_notification,
)
from app.services.scheduler_service import SchedulerService, is_reminder_due
from scripts.generate_keys import generate_local_keys
from tests.conftest import build_open_meteo_payload

VALID_SUBSCRIPTION: dict[str, Any] = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/example-token-123456",
    "keys": {
        "p256dh": "BOr7fakePublicKeyForTests1234567890abcdef",
        "auth": "fakeAuthKey12345",
    },
}


def _create_sample_reminder(
    client: TestClient,
    *,
    label: str = "Alerta manhã",
    location_name: str = "Registro, SP",
    schedule_type: str = "daily",
    time_of_day: str = "07:30",
    days_of_week: list[int] | None = None,
    once_date: str | None = None,
    forecast_window: str = "today",
    min_rain_probability: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": label,
        "location_name": location_name,
        "latitude": -24.4945,
        "longitude": -47.8442,
        "timezone": "America/Sao_Paulo",
        "schedule_type": schedule_type,
        "time_of_day": time_of_day,
        "days_of_week": days_of_week if days_of_week is not None else [],
        "once_date": once_date,
        "forecast_window": forecast_window,
        "min_rain_probability": min_rain_probability,
        "subscription": VALID_SUBSCRIPTION,
    }
    resp = client.post("/api/v1/reminders", json=payload)
    assert resp.status_code == 201
    data: dict[str, Any] = resp.json()
    return data


def test_vapid_public_key_and_key_compatibility(
    client: TestClient,
    test_settings: Settings,
) -> None:
    response = client.get("/api/v1/reminders/vapid-public-key")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["public_key"] == test_settings.vapid_public_key

    keys = generate_local_keys()
    vapid = Vapid.from_string(keys.vapid_private_key)
    assert vapid.public_key is not None


@pytest.mark.asyncio
async def test_reminder_crud_encrypts_subscription_and_hashes_token(
    client: TestClient,
    test_settings: Settings,
) -> None:
    created = _create_sample_reminder(
        client,
        schedule_type="weekly",
        days_of_week=[4, 0, 2, 0],
        min_rain_probability=60,
    )
    reminder_id = created["reminder"]["id"]
    token = created["reminder_token"]

    assert created["reminder"]["latitude"] == -24.49
    assert created["reminder"]["longitude"] == -47.84
    assert created["reminder"]["days_of_week"] == [0, 2, 4]
    assert "subscription" not in created["reminder"]
    assert "token_hash" not in created["reminder"]

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        stored = (
            await session.execute(select(Reminder).where(Reminder.id == reminder_id))
        ).scalar_one()
        assert stored.token_hash != token
        assert len(stored.token_hash) == 64
        assert VALID_SUBSCRIPTION["endpoint"] not in stored.subscription_encrypted
        assert test_settings.data_encryption_key is not None
        decrypted = json.loads(
            decrypt_secret(
                stored.subscription_encrypted,
                test_settings.data_encryption_key.get_secret_value(),
            )
        )
        assert decrypted["endpoint"] == VALID_SUBSCRIPTION["endpoint"]

    get_resp = client.get(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-Reminder-Token": token},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["min_rain_probability"] == 60

    patch_resp = client.patch(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-Reminder-Token": token},
        json={
            "schedule_type": "daily",
            "days_of_week": [],
            "time_of_day": "08:15",
            "min_rain_probability": None,
            "enabled": False,
        },
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["schedule_type"] == "daily"
    assert patched["days_of_week"] == []
    assert patched["time_of_day"] == "08:15"
    assert patched["min_rain_probability"] is None
    assert patched["enabled"] is False

    del_resp = client.delete(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-Reminder-Token": token},
    )
    assert del_resp.status_code == 204

    after_del = client.get(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-Reminder-Token": token},
    )
    assert after_del.status_code == 404


def test_reminder_anti_idor_and_token_enforcement(client: TestClient) -> None:
    rem_a = _create_sample_reminder(client, label="Lembrete A")
    rem_b = _create_sample_reminder(client, label="Lembrete B")
    id_a = rem_a["reminder"]["id"]
    id_b = rem_b["reminder"]["id"]
    token_a = rem_a["reminder_token"]

    assert client.get(f"/api/v1/reminders/{id_a}").status_code == 401
    assert client.patch(f"/api/v1/reminders/{id_a}", json={"enabled": False}).status_code == 401
    assert client.delete(f"/api/v1/reminders/{id_a}").status_code == 401
    assert client.post(f"/api/v1/reminders/{id_a}/test").status_code == 401

    assert (
        client.get(
            f"/api/v1/reminders/{id_a}",
            headers={"X-Reminder-Token": "wrong-token"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/reminders/{id_b}",
            headers={"X-Reminder-Token": token_a},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/reminders/{id_b}",
            headers={"X-Reminder-Token": token_a},
            json={"enabled": False},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/reminders/{id_b}",
            headers={"X-Reminder-Token": token_a},
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/reminders/not-a-uuid",
            headers={"X-Reminder-Token": token_a},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "valid_endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/token-123",
        "https://updates.push.services.mozilla.com/wpush/v2/abc123",
        "https://web.push.apple.com/QWERTY123456",
        "https://wns2-bl2p.notify.windows.com/w/?token=abc",
    ],
)
def test_validate_push_endpoint_allows_official_providers(valid_endpoint: str) -> None:
    assert validate_push_endpoint(valid_endpoint) == valid_endpoint


@pytest.mark.parametrize(
    "blocked_endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/abc",
        "https://127.0.0.1/push",
        "https://[::1]/push",
        "https://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/push",
        "https://fcm.googleapis.com.evil.com/push",
        "https://fcm.googleapis.com:8443/fcm/send/abc",
        "https://user:pass@fcm.googleapis.com/fcm/send/abc",
    ],
)
def test_push_endpoint_rejects_ssrf_vectors(
    client: TestClient,
    blocked_endpoint: str,
) -> None:
    with pytest.raises(ValueError):
        validate_push_endpoint(blocked_endpoint)

    resp = client.post(
        "/api/v1/reminders",
        json={
            "label": "Teste SSRF",
            "location_name": "São Paulo",
            "latitude": -23.55,
            "longitude": -46.63,
            "timezone": "America/Sao_Paulo",
            "schedule_type": "daily",
            "time_of_day": "08:00",
            "subscription": {
                "endpoint": blocked_endpoint,
                "keys": VALID_SUBSCRIPTION["keys"],
            },
        },
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("ip_text", "expected_blocked"),
    [
        ("127.0.0.1", True),
        ("10.0.0.5", True),
        ("172.16.0.1", True),
        ("192.168.1.10", True),
        ("169.254.169.254", True),
        ("::1", True),
        ("142.250.79.10", False),
    ],
)
def test_is_ip_blocked(ip_text: str, expected_blocked: bool) -> None:
    assert is_ip_blocked(ip_text) is expected_blocked


@pytest.mark.asyncio
async def test_web_push_service_blocks_private_dns_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = generate_local_keys()
    service = WebPushService(
        vapid_public_key=keys.vapid_public_key,
        vapid_private_key=keys.vapid_private_key,
        vapid_subject="mailto:test@climapy.local",
    )

    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        del args, kwargs
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr("app.services.push_service.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(PushDeliveryError):
        await service.send_notification(
            subscription_info=VALID_SUBSCRIPTION,
            message=build_weather_notification(
                location_name="Registro",
                forecast=OpenMeteoWeatherProvider(
                    httpx.AsyncClient(),
                    user_agent="ClimaPy-Test/0.2",
                )._parse_forecast(
                    build_open_meteo_payload(days=3),
                    latitude=-24.49,
                    longitude=-47.84,
                    days=3,
                ),
                window="today",
                min_rain_probability=None,
                ignore_rain_threshold=True,
            ),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "bad_body",
    [
        {
            "schedule_type": "weekly",
            "time_of_day": "08:00",
            "days_of_week": [],
        },
        {
            "schedule_type": "once",
            "time_of_day": "08:00",
            "once_date": None,
        },
        {
            "schedule_type": "daily",
            "time_of_day": "25:99",
        },
        {
            "schedule_type": "daily",
            "time_of_day": "08:00",
            "timezone": "Invalid/Zone",
        },
    ],
)
def test_reminder_rejects_invalid_schedule_inputs(
    client: TestClient,
    bad_body: dict[str, Any],
) -> None:
    payload = {
        "label": "Alerta",
        "location_name": "São Paulo",
        "latitude": -23.55,
        "longitude": -46.63,
        "timezone": "America/Sao_Paulo",
        "subscription": VALID_SUBSCRIPTION,
        **bad_body,
    }
    resp = client.post("/api/v1/reminders", json=payload)
    assert resp.status_code == 422


def test_reminder_sql_injection_payload_stored_safely(client: TestClient) -> None:
    sqli_label = "SP'); DROP TABLE reminders; --"
    created = _create_sample_reminder(client, label=sqli_label, location_name=sqli_label)
    reminder_id = created["reminder"]["id"]
    token = created["reminder_token"]

    assert created["reminder"]["label"] == sqli_label
    resp = client.get(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-Reminder-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == sqli_label


def test_reminder_test_push_success_and_gone_auto_delete(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _create_sample_reminder(
        client,
        forecast_window="next_3_days",
        min_rain_probability=99,
    )
    reminder_id = created["reminder"]["id"]
    token = created["reminder_token"]

    sent_calls: list[dict[str, Any]] = []

    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        del args, kwargs
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.79.10", 443))]

    def fake_webpush(**kwargs: Any) -> None:
        sent_calls.append(kwargs)

    monkeypatch.setattr("app.services.push_service.socket.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr("app.services.push_service.webpush", fake_webpush)

    with respx.mock(assert_all_mocked=True) as router:
        router.get(OpenMeteoWeatherProvider.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=build_open_meteo_payload(days=3))
        )

        test_resp = client.post(
            f"/api/v1/reminders/{reminder_id}/test",
            headers={"X-Reminder-Token": token},
        )
        assert test_resp.status_code == 200
        body = test_resp.json()
        assert body["delivered"] is True
        assert "3 dias" in body["title"]
        assert len(sent_calls) == 1

        def fake_gone_webpush(**kwargs: Any) -> None:
            del kwargs
            raise WebPushException("Gone", response=SimpleNamespace(status_code=410))

        monkeypatch.setattr("app.services.push_service.webpush", fake_gone_webpush)
        gone_resp = client.post(
            f"/api/v1/reminders/{reminder_id}/test",
            headers={"X-Reminder-Token": token},
        )
        assert gone_resp.status_code == 410

    assert (
        client.get(
            f"/api/v1/reminders/{reminder_id}",
            headers={"X-Reminder-Token": token},
        ).status_code
        == 404
    )


@pytest.mark.asyncio
async def test_scheduler_processes_due_rain_threshold_dedup_and_gone(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 2026-11-23 é segunda-feira (weekday == 0)
    # 10:30 UTC == 07:30 America/Sao_Paulo (-03:00)
    rem_due = _create_sample_reminder(
        client,
        label="Disparar hoje",
        schedule_type="weekly",
        days_of_week=[0],
        time_of_day="07:30",
        forecast_window="today",
        min_rain_probability=50,
    )
    rem_skip_rain = _create_sample_reminder(
        client,
        label="Só chuva forte",
        schedule_type="daily",
        time_of_day="07:30",
        forecast_window="tomorrow",
        min_rain_probability=95,
    )
    rem_once_gone = _create_sample_reminder(
        client,
        label="Pontual expirado",
        schedule_type="once",
        once_date="2026-11-23",
        time_of_day="07:30",
    )
    rem_other_hour = _create_sample_reminder(
        client,
        label="Outro horário",
        schedule_type="daily",
        time_of_day="19:00",
    )

    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        del args, kwargs
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.79.10", 443))]

    delivered_titles: list[str] = []

    def fake_webpush(**kwargs: Any) -> None:
        payload = json.loads(kwargs["data"])
        if len(delivered_titles) == 1:
            raise WebPushException("Expired", response=SimpleNamespace(status_code=410))
        delivered_titles.append(payload["title"])

    monkeypatch.setattr("app.services.push_service.socket.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr("app.services.push_service.webpush", fake_webpush)

    scheduler: SchedulerService = client.app.state.scheduler_service  # type: ignore[attr-defined]
    now_utc = datetime(2026, 11, 23, 10, 30, tzinfo=UTC)

    with respx.mock(assert_all_mocked=True) as router:
        router.get(OpenMeteoWeatherProvider.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=build_open_meteo_payload(days=3))
        )

        stats = await scheduler.process_due_reminders(now_utc=now_utc)
        assert stats.checked == 4
        assert stats.due == 3
        assert stats.sent == 1
        assert stats.skipped_rain == 1
        assert stats.deleted_gone == 1
        assert stats.failed == 0
        assert len(delivered_titles) == 1

        # Segunda execução no mesmo minuto deve deduplicar os restantes (due == 0)
        stats_repeat = await scheduler.process_due_reminders(now_utc=now_utc)
        assert stats_repeat.due == 0
        assert stats_repeat.sent == 0

    assert (
        client.get(
            f"/api/v1/reminders/{rem_once_gone['reminder']['id']}",
            headers={"X-Reminder-Token": rem_once_gone["reminder_token"]},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/reminders/{rem_due['reminder']['id']}",
            headers={"X-Reminder-Token": rem_due["reminder_token"]},
        ).json()["last_sent_at"]
        is not None
    )
    assert (
        client.get(
            f"/api/v1/reminders/{rem_skip_rain['reminder']['id']}",
            headers={"X-Reminder-Token": rem_skip_rain["reminder_token"]},
        ).json()["last_sent_at"]
        is not None
    )
    assert (
        client.get(
            f"/api/v1/reminders/{rem_other_hour['reminder']['id']}",
            headers={"X-Reminder-Token": rem_other_hour["reminder_token"]},
        ).json()["last_sent_at"]
        is None
    )


def test_is_reminder_due_once_and_timezone() -> None:
    reminder = Reminder(
        id="00000000-0000-0000-0000-000000000001",
        token_hash="a" * 64,
        label="Pontual",
        location_name="Registro",
        latitude=-24.49,
        longitude=-47.84,
        timezone="America/Sao_Paulo",
        schedule_type="once",
        time_of_day="21:00",
        days_of_week="",
        once_date="2026-11-23",
        forecast_window="today",
        min_rain_probability=None,
        subscription_encrypted="enc",
        enabled=True,
        last_sent_at=None,
    )
    # 2026-11-24 00:00 UTC == 2026-11-23 21:00 BRT
    assert is_reminder_due(reminder, datetime(2026, 11, 24, 0, 0, tzinfo=UTC)) is True
    assert is_reminder_due(reminder, datetime(2026, 11, 24, 0, 1, tzinfo=UTC)) is False
