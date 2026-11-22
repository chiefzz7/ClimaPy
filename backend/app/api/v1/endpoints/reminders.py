"""Endpoints de lembretes climáticos sem login e notificações Web Push VAPID."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db_session, get_push_service, get_reminder_service
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.schemas.reminder import (
    PushTestResponse,
    ReminderCreateRequest,
    ReminderCreateResponse,
    ReminderResponse,
    ReminderUpdateRequest,
    VapidPublicKeyResponse,
)
from app.services.push_service import (
    PushConfigurationError,
    PushDeliveryError,
    PushSubscriptionGoneError,
    WebPushService,
)
from app.services.reminder_service import (
    ReminderConfigurationError,
    ReminderNotFoundError,
    ReminderService,
    ReminderValidationError,
)

router = APIRouter(prefix="/reminders", tags=["Lembretes e Notificações"])
_SETTINGS = get_settings()


def _require_token(token: str | None) -> str:
    if token is None or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Reminder-Token obrigatório.",
        )
    return token.strip()


@router.get(
    "/vapid-public-key",
    response_model=VapidPublicKeyResponse,
    summary="Obtém chave pública VAPID para inscrição Web Push",
)
@rate_limit(_SETTINGS.rate_limit_default)
async def get_vapid_public_key(
    request: Request,
    push_service: WebPushService = Depends(get_push_service),  # noqa: B008
) -> VapidPublicKeyResponse:
    """Informa se Web Push está configurado e retorna a chave pública VAPID."""
    del request
    return VapidPublicKeyResponse(
        configured=push_service.is_configured,
        public_key=push_service.public_key,
    )


@router.post(
    "",
    response_model=ReminderCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria lembrete climático anônimo com Web Push",
)
@rate_limit(_SETTINGS.rate_limit_reminders)
async def create_reminder(
    request: Request,
    payload: ReminderCreateRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reminder_service: ReminderService = Depends(get_reminder_service),  # noqa: B008
) -> ReminderCreateResponse:
    """Cria regra de lembrete cifrada e retorna token único de posse do dispositivo."""
    del request
    try:
        return await reminder_service.create_reminder(session, payload=payload)
    except ReminderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de lembretes não configurado neste servidor.",
        ) from exc


@router.get(
    "/{reminder_id}",
    response_model=ReminderResponse,
    summary="Consulta detalhes do lembrete via capability token",
)
@rate_limit(_SETTINGS.rate_limit_default)
async def get_reminder(
    request: Request,
    reminder_id: str,
    x_reminder_token: Annotated[str | None, Header(alias="X-Reminder-Token")] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reminder_service: ReminderService = Depends(get_reminder_service),  # noqa: B008
) -> ReminderResponse:
    """Retorna os metadados do lembrete apenas para o portador do token válido."""
    del request
    token = _require_token(x_reminder_token)
    try:
        return await reminder_service.get_reminder(session, reminder_id=reminder_id, token=token)
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lembrete não encontrado.",
        ) from exc


@router.patch(
    "/{reminder_id}",
    response_model=ReminderResponse,
    summary="Atualiza horário, dias, filtro ou pausa lembrete",
)
@rate_limit(_SETTINGS.rate_limit_reminders)
async def update_reminder(
    request: Request,
    reminder_id: str,
    payload: ReminderUpdateRequest,
    x_reminder_token: Annotated[str | None, Header(alias="X-Reminder-Token")] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reminder_service: ReminderService = Depends(get_reminder_service),  # noqa: B008
) -> ReminderResponse:
    """Atualiza parcialmente um lembrete após validar posse pelo token."""
    del request
    token = _require_token(x_reminder_token)
    try:
        return await reminder_service.update_reminder(
            session,
            reminder_id=reminder_id,
            token=token,
            payload=payload,
        )
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lembrete não encontrado.",
        ) from exc
    except ReminderValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ReminderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de lembretes não configurado neste servidor.",
        ) from exc


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove definitivamente um lembrete",
)
@rate_limit(_SETTINGS.rate_limit_reminders)
async def delete_reminder(
    request: Request,
    reminder_id: str,
    x_reminder_token: Annotated[str | None, Header(alias="X-Reminder-Token")] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reminder_service: ReminderService = Depends(get_reminder_service),  # noqa: B008
) -> Response:
    """Executa exclusão definitiva do lembrete e sua inscrição cifrada."""
    del request
    token = _require_token(x_reminder_token)
    try:
        await reminder_service.delete_reminder(session, reminder_id=reminder_id, token=token)
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lembrete não encontrado.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{reminder_id}/test",
    response_model=PushTestResponse,
    summary="Envia notificação Web Push de teste imediata",
)
@rate_limit(_SETTINGS.rate_limit_push_test)
async def test_reminder_push(
    request: Request,
    reminder_id: str,
    x_reminder_token: Annotated[str | None, Header(alias="X-Reminder-Token")] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reminder_service: ReminderService = Depends(get_reminder_service),  # noqa: B008
) -> PushTestResponse:
    """Dispara imediatamente a previsão resumida do lembrete para validar Web Push."""
    del request
    token = _require_token(x_reminder_token)
    try:
        return await reminder_service.send_test_notification(
            session,
            reminder_id=reminder_id,
            token=token,
        )
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lembrete não encontrado.",
        ) from exc
    except (ReminderConfigurationError, PushConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Web Push não configurado neste servidor.",
        ) from exc
    except PushSubscriptionGoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Inscrição Web Push expirada; lembrete removido automaticamente.",
        ) from exc
    except PushDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha ao entregar notificação no provedor Web Push.",
        ) from exc
