"""Configurações tipadas da aplicação via variáveis de ambiente."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Configurações globais carregadas exclusivamente de ambiente e .env local."""

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ClimaPy"
    app_env: Literal["development", "testing", "production"] = "development"
    app_version: str = "0.2.0"
    app_user_agent: str = "ClimaPy/0.2.0 (+https://climapy.local)"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "sqlite+aiosqlite:///./climapy.db"

    weather_cache_ttl_seconds: int = Field(default=900, ge=60, le=7200)
    geocoding_cache_ttl_seconds: int = Field(default=86400, ge=300, le=604800)
    http_timeout_seconds: float = Field(default=10.0, ge=1.0, le=30.0)

    rate_limit_enabled: bool = True
    rate_limit_default: str = "60/minute"
    rate_limit_geocoding: str = "30/minute"
    rate_limit_reverse: str = "15/minute"
    rate_limit_reminders: str = "10/minute"
    rate_limit_push_test: str = "5/minute"

    scheduler_enabled: bool = True
    scheduler_poll_seconds: int = Field(default=60, ge=10, le=300)

    data_encryption_key: SecretStr | None = None
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:admin@climapy.local"

    weatherapi_key: SecretStr | None = None
    ai_provider: Literal["none", "ollama", "gemini", "openai"] = "none"

    @field_validator("app_user_agent")
    @classmethod
    def _validate_user_agent(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(ord(ch) < 32 for ch in cleaned):
            raise ValueError("APP_USER_AGENT deve ser um cabeçalho HTTP válido e não vazio.")
        return cleaned

    @field_validator("allowed_origins")
    @classmethod
    def _validate_allowed_origins(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",") if item.strip()]
        if "*" in origins:
            raise ValueError("Uso de wildcard '*' em ALLOWED_ORIGINS não é permitido.")
        return ",".join(origins)

    @field_validator("vapid_subject")
    @classmethod
    def _validate_vapid_subject(cls, value: str) -> str:
        cleaned = value.strip()
        if any(ord(ch) < 32 for ch in cleaned) or not (
            cleaned.startswith("mailto:") or cleaned.startswith("https://")
        ):
            raise ValueError("VAPID_SUBJECT deve iniciar com 'mailto:' ou 'https://'.")
        return cleaned

    @property
    def allowed_origins_list(self) -> list[str]:
        """Lista explícita de origens permitidas no CORS."""
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a instância em cache das configurações da aplicação."""
    return Settings()
