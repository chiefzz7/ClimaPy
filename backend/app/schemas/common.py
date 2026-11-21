"""Schemas comuns de saúde, atribuição legal e erros da API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Resposta do endpoint de verificação de saúde da API."""

    status: str = "ok"
    app: str
    version: str
    environment: str
    python_version: str


class ProviderAttribution(BaseModel):
    """Créditos e origem dos dados retornados ao cliente."""

    provider: str
    provider_label: str
    license: str
    url: str
    fallback_used: bool = False
    air_quality_provider: str | None = None


class ErrorResponse(BaseModel):
    """Contrato padronizado de erros sem exposição de stack trace."""

    detail: str = Field(..., min_length=1)
