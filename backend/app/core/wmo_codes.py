"""Mapeamento de códigos meteorológicos WMO (PT-BR) e símbolos MET Norway."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WmoInfo:
    """Metadados normalizados de condição meteorológica."""

    key: str
    label_pt: str
    icon_day: str
    icon_night: str


_WMO_TABLE: dict[int, WmoInfo] = {
    0: WmoInfo("clear_sky", "Céu limpo", "sun", "moon"),
    1: WmoInfo("mainly_clear", "Predominantemente limpo", "sun-cloud", "moon-cloud"),
    2: WmoInfo("partly_cloudy", "Parcialmente nublado", "cloud-sun", "cloud-moon"),
    3: WmoInfo("overcast", "Nublado", "cloud", "cloud"),
    45: WmoInfo("fog", "Neblina", "fog", "fog"),
    48: WmoInfo("rime_fog", "Nevoeiro com geada", "fog", "fog"),
    51: WmoInfo("drizzle_light", "Garoa fraca", "drizzle", "drizzle"),
    53: WmoInfo("drizzle_moderate", "Garoa moderada", "drizzle", "drizzle"),
    55: WmoInfo("drizzle_dense", "Garoa intensa", "drizzle", "drizzle"),
    56: WmoInfo("freezing_drizzle_light", "Garoa congelante fraca", "sleet", "sleet"),
    57: WmoInfo("freezing_drizzle_dense", "Garoa congelante intensa", "sleet", "sleet"),
    61: WmoInfo("rain_light", "Chuva fraca", "rain-light", "rain-light"),
    63: WmoInfo("rain_moderate", "Chuva moderada", "rain", "rain"),
    65: WmoInfo("rain_heavy", "Chuva forte", "rain-heavy", "rain-heavy"),
    66: WmoInfo("freezing_rain_light", "Chuva congelante fraca", "sleet", "sleet"),
    67: WmoInfo("freezing_rain_heavy", "Chuva congelante forte", "sleet", "sleet"),
    71: WmoInfo("snow_light", "Neve fraca", "snow", "snow"),
    73: WmoInfo("snow_moderate", "Neve moderada", "snow", "snow"),
    75: WmoInfo("snow_heavy", "Neve intensa", "snow", "snow"),
    77: WmoInfo("snow_grains", "Grãos de neve", "snow", "snow"),
    80: WmoInfo("showers_light", "Pancadas de chuva fracas", "rain-light", "rain-light"),
    81: WmoInfo("showers_moderate", "Pancadas de chuva moderadas", "rain", "rain"),
    82: WmoInfo("showers_violent", "Pancadas de chuva fortes", "rain-heavy", "rain-heavy"),
    85: WmoInfo("snow_showers_light", "Pancadas de neve fracas", "snow", "snow"),
    86: WmoInfo("snow_showers_heavy", "Pancadas de neve fortes", "snow", "snow"),
    95: WmoInfo("thunderstorm", "Trovoada", "thunderstorm", "thunderstorm"),
    96: WmoInfo(
        "thunderstorm_hail_light",
        "Trovoada com granizo fraco",
        "thunderstorm",
        "thunderstorm",
    ),
    99: WmoInfo(
        "thunderstorm_hail_heavy",
        "Trovoada com granizo forte",
        "thunderstorm",
        "thunderstorm",
    ),
}

_FALLBACK_WMO = WmoInfo("unknown", "Condição variável", "cloud", "cloud")


def describe_wmo_code(code: int | None, *, is_day: bool = True) -> tuple[int, str, str, str]:
    """Retorna (codigo, chave, descricao_pt, icone) para um código WMO."""
    safe_code = code if code is not None else 3
    info = _WMO_TABLE.get(safe_code, _FALLBACK_WMO)
    icon = info.icon_day if is_day else info.icon_night
    return safe_code, info.key, info.label_pt, icon


def met_norway_symbol_to_wmo(symbol_code: str | None) -> int:
    """Converte symbol_code do MET Norway para o código WMO mais próximo."""
    if not symbol_code:
        return 3
    base = symbol_code.split("_", 1)[0].lower()

    if "thunder" in base:
        return 95
    if "sleet" in base:
        return 66
    if "snow" in base:
        if "heavy" in base:
            return 75
        if "light" in base:
            return 71
        return 73
    if "rainshowers" in base:
        if "heavy" in base:
            return 82
        if "light" in base:
            return 80
        return 81
    if "rain" in base:
        if "heavy" in base:
            return 65
        if "light" in base:
            return 61
        return 63

    direct_map = {
        "clearsky": 0,
        "fair": 1,
        "partlycloudy": 2,
        "cloudy": 3,
        "fog": 45,
    }
    return direct_map.get(base, 3)


_COMPASS_PT: tuple[str, ...] = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "L",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSO",
    "SO",
    "OSO",
    "O",
    "ONO",
    "NO",
    "NNO",
)


def degrees_to_cardinal_pt(degrees: float | None) -> str | None:
    """Converte azimute do vento (0..360°) em rosa dos ventos de 16 pontos em português."""
    if degrees is None:
        return None
    idx = int(((degrees % 360.0) + 11.25) // 22.5) % 16
    return _COMPASS_PT[idx]
