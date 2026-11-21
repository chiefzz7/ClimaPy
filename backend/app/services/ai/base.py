"""Contratos base da futura camada de inteligência artificial climática."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.weather import WeatherForecastResponse


class AIWeatherInsight(BaseModel):
    """Saída estruturada de análise inteligente de previsão do tempo."""

    enabled: bool = False
    summary_pt: str = ""
    alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class WeatherAIAnalyzer(ABC):
    """Contrato abstrato para provedores de IA climática na Etapa 6."""

    @abstractmethod
    async def analyze(self, forecast: WeatherForecastResponse) -> AIWeatherInsight:
        """Gera análise inteligente não-bloqueante a partir dos dados normalizados."""


class NoOpAIAnalyzer(WeatherAIAnalyzer):
    """Implementação padrão segura enquanto o módulo de IA está desativado."""

    async def analyze(self, forecast: WeatherForecastResponse) -> AIWeatherInsight:
        return AIWeatherInsight(enabled=False)
