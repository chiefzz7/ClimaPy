import {
  Cloud,
  Droplets,
  Eye,
  Gauge,
  Navigation,
  Star,
  Sun,
  Sunrise,
  Sunset,
  Umbrella,
  WifiOff,
  Wind,
} from "lucide-react";
import type { SavedLocation, TemperatureUnit, WeatherForecastResponse } from "../types/weather";
import {
  formatHour,
  formatMm,
  formatPercent,
  formatPressure,
  formatTemp,
  formatVisibility,
  formatWind,
  getUvCategory,
} from "../utils/format";
import { WeatherIcon } from "./WeatherIcon";

interface CurrentWeatherHeroProps {
  location: SavedLocation;
  forecast: WeatherForecastResponse;
  unit: TemperatureUnit;
  isFavorite: boolean;
  isOfflineSnapshot: boolean;
  snapshotSavedAt: string | null;
  onToggleFavorite: () => void;
}

function getHeroGradient(icon: string, isDay: boolean): string {
  if (!isDay) {
    return "from-slate-900 via-indigo-950 to-slate-900";
  }
  if (icon === "thunderstorm") {
    return "from-slate-800 via-indigo-900 to-slate-800";
  }
  if (icon.includes("rain") || icon === "drizzle") {
    return "from-sky-800 via-slate-800 to-cyan-900";
  }
  if (icon === "sun" || icon === "sun-cloud") {
    return "from-sky-600 via-blue-700 to-indigo-800";
  }
  return "from-sky-700 via-slate-700 to-slate-800";
}

export function CurrentWeatherHero({
  location,
  forecast,
  unit,
  isFavorite,
  isOfflineSnapshot,
  snapshotSavedAt,
  onToggleFavorite,
}: CurrentWeatherHeroProps) {
  const { current, daily } = forecast;
  const today = daily[0];
  const uvMeta = getUvCategory(current.uv_index);
  const gradient = getHeroGradient(current.condition.icon, current.is_day);

  return (
    <section
      aria-label="Condições atuais"
      className={`overflow-hidden rounded-3xl bg-gradient-to-br ${gradient} p-5 text-white shadow-xl sm:p-7`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
              {location.displayName}
            </h2>
            <button
              type="button"
              onClick={onToggleFavorite}
              aria-label={isFavorite ? "Remover dos favoritos" : "Salvar nos favoritos"}
              className="rounded-full bg-white/10 p-1.5 transition hover:bg-white/20"
            >
              <Star
                className={`h-4 w-4 ${isFavorite ? "fill-amber-300 text-amber-300" : "text-white/80"}`}
              />
            </button>
          </div>
          <p className="text-xs text-white/75">
            Atualizado às {formatHour(current.time)} ({forecast.timezone_abbreviation})
            {forecast.cached && !isOfflineSnapshot ? " • Cache recente" : ""}
            {forecast.attribution.fallback_used ? " • Fonte reserva ativa" : ""}
          </p>
        </div>

        {isOfflineSnapshot && (
          <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/20 px-3 py-1 text-xs font-medium text-amber-100 ring-1 ring-amber-300/40">
            <WifiOff className="h-3.5 w-3.5" />
            <span>
              Modo offline
              {snapshotSavedAt
                ? ` (${new Date(snapshotSavedAt).toLocaleTimeString("pt-BR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })})`
                : ""}
            </span>
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-white/10 backdrop-blur-sm">
            <WeatherIcon icon={current.condition.icon} className="h-12 w-12" />
          </div>
          <div>
            <div className="text-5xl font-extrabold tracking-tight sm:text-6xl">
              {formatTemp(current.temperature_c, unit)}
            </div>
            <p className="mt-1 text-base font-semibold text-white/95">
              {current.condition.label_pt}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 text-sm text-white/90 sm:flex-col sm:items-end sm:gap-1">
          <span>
            Sensação:{" "}
            <strong className="font-semibold">
              {formatTemp(current.apparent_temperature_c, unit)}
            </strong>
          </span>
          {today && (
            <span>
              Mín{" "}
              <strong className="font-semibold">
                {formatTemp(today.temperature_min_c, unit)}
              </strong>{" "}
              / Máx{" "}
              <strong className="font-semibold">
                {formatTemp(today.temperature_max_c, unit)}
              </strong>
            </span>
          )}
          <span>
            Ponto de orvalho:{" "}
            <strong className="font-semibold">{formatTemp(current.dew_point_c, unit)}</strong>
          </span>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-xs text-white/75">
            <Droplets className="h-3.5 w-3.5" />
            <span>Umidade</span>
          </div>
          <p className="mt-1 text-base font-bold">
            {formatPercent(current.relative_humidity_percent)}
          </p>
        </div>

        <div className="rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-xs text-white/75">
            <Umbrella className="h-3.5 w-3.5" />
            <span>Chuva</span>
          </div>
          <p className="mt-1 text-base font-bold">
            {formatPercent(current.precipitation_probability_percent)}
          </p>
          <p className="text-[11px] text-white/75">{formatMm(current.precipitation_mm)}</p>
        </div>

        <div className="rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-xs text-white/75">
            <Wind className="h-3.5 w-3.5" />
            <span>Vento</span>
          </div>
          <p className="mt-1 flex items-center gap-1 text-base font-bold">
            <span>{formatWind(current.wind_speed_kmh, current.wind_direction_cardinal)}</span>
          </p>
          <p className="flex items-center gap-1 text-[11px] text-white/75">
            <Navigation
              className="h-2.5 w-2.5"
              style={{
                transform: `rotate(${current.wind_direction_deg ?? 0}deg)`,
              }}
            />
            Rajadas {formatWind(current.wind_gusts_kmh)}
          </p>
        </div>

        <div className="rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-xs text-white/75">
            <Gauge className="h-3.5 w-3.5" />
            <span>Pressão</span>
          </div>
          <p className="mt-1 text-base font-bold">{formatPressure(current.pressure_msl_hpa)}</p>
          <p className="text-[11px] text-white/75">
            Nuvens {formatPercent(current.cloud_cover_percent)}
          </p>
        </div>

        <div className="rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-xs text-white/75">
            <Sun className="h-3.5 w-3.5" />
            <span>Índice UV</span>
          </div>
          <p className="mt-1 text-base font-bold">
            {current.uv_index !== null && current.uv_index !== undefined
              ? current.uv_index.toFixed(1)
              : "--"}
          </p>
          <p className={`text-[11px] font-medium ${uvMeta.toneClass}`}>{uvMeta.label}</p>
        </div>

        <div className="rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-xs text-white/75">
            {today?.sunrise && today?.sunset ? (
              <Sunrise className="h-3.5 w-3.5" />
            ) : (
              <Eye className="h-3.5 w-3.5" />
            )}
            <span>Visibilidade / Sol</span>
          </div>
          <p className="mt-1 text-base font-bold">{formatVisibility(current.visibility_km)}</p>
          {today?.sunrise && today?.sunset ? (
            <p className="flex items-center gap-1 text-[11px] text-white/75">
              <span>{formatHour(today.sunrise)}</span>
              <span>•</span>
              <Sunset className="h-2.5 w-2.5" />
              <span>{formatHour(today.sunset)}</span>
            </p>
          ) : (
            <p className="flex items-center gap-1 text-[11px] text-white/75">
              <Cloud className="h-2.5 w-2.5" />
              <span>Cobertura {formatPercent(current.cloud_cover_percent)}</span>
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
