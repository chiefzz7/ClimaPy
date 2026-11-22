import { ChevronDown, ChevronUp, Loader2, Sun, Sunrise, Sunset, Umbrella, Wind } from "lucide-react";
import { useState } from "react";
import type {
  DailyForecastItem,
  HourlyForecastItem,
  TemperatureUnit,
} from "../types/weather";
import {
  extractDatePrefix,
  formatDayFull,
  formatHour,
  formatHours,
  formatMm,
  formatPercent,
  formatTemp,
  formatWind,
} from "../utils/format";
import { WeatherIcon } from "./WeatherIcon";

interface DailyForecastSectionProps {
  daily: DailyForecastItem[];
  hourlyFull: HourlyForecastItem[];
  hourly72h: HourlyForecastItem[];
  referenceToday: string;
  unit: TemperatureUnit;
  loadingFullHourly: boolean;
  onRequestFullHourly: () => Promise<void>;
}

export function DailyForecastSection({
  daily,
  hourlyFull,
  hourly72h,
  referenceToday,
  unit,
  loadingFullHourly,
  onRequestFullHourly,
}: DailyForecastSectionProps) {
  const [expandedDate, setExpandedDate] = useState<string | null>(daily[0]?.date ?? null);

  if (daily.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        Sem dados diários disponíveis.
      </div>
    );
  }

  const allMins = daily.map((d) => d.temperature_min_c ?? 15);
  const allMaxs = daily.map((d) => d.temperature_max_c ?? 30);
  const globalMin = Math.min(...allMins);
  const globalMax = Math.max(...allMaxs);
  const span = Math.max(1, globalMax - globalMin);

  async function handleToggleDay(date: string) {
    if (expandedDate === date) {
      setExpandedDate(null);
      return;
    }
    setExpandedDate(date);
    if (hourlyFull.length === 0) {
      const hasIn72h = hourly72h.some((h) => extractDatePrefix(h.time) === date);
      if (!hasIn72h) {
        await onRequestFullHourly();
      }
    }
  }

  const sourceHourly = hourlyFull.length > 0 ? hourlyFull : hourly72h;

  return (
    <section aria-label="Previsão estendida de até 16 dias" className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Previsão Estendida (Até {daily.length} dias)
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Toque em qualquer dia para abrir detalhes solares e a linha horária daquele dia.
        </p>
      </div>

      <div className="space-y-2.5">
        {daily.map((day) => {
          const isOpen = expandedDate === day.date;
          const dMin = day.temperature_min_c ?? globalMin;
          const dMax = day.temperature_max_c ?? globalMax;
          const leftPct = ((dMin - globalMin) / span) * 100;
          const widthPct = Math.max(10, ((dMax - dMin) / span) * 100);
          const dayHours = sourceHourly.filter((h) => extractDatePrefix(h.time) === day.date);

          return (
            <div
              key={day.date}
              className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition dark:border-slate-800 dark:bg-slate-900"
            >
              <button
                type="button"
                onClick={() => void handleToggleDay(day.date)}
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800/50"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <WeatherIcon icon={day.condition.icon} className="h-7 w-7 shrink-0" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                      {formatDayFull(day.date, referenceToday)}
                    </p>
                    <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                      {day.condition.label_pt}
                    </p>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-3 sm:gap-5">
                  <div className="hidden text-right text-xs text-sky-600 dark:text-sky-400 sm:block">
                    <span className="inline-flex items-center gap-1 font-semibold">
                      <Umbrella className="h-3.5 w-3.5" />
                      {formatPercent(day.precipitation_probability_max_percent)}
                    </span>
                    <p className="text-[11px] text-slate-400">{formatMm(day.precipitation_sum_mm)}</p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="w-8 text-right text-xs font-semibold text-slate-500 dark:text-slate-400">
                      {formatTemp(day.temperature_min_c, unit)}
                    </span>
                    <div className="relative hidden h-2 w-20 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800 sm:block">
                      <div
                        className="absolute bottom-0 top-0 rounded-full bg-gradient-to-r from-sky-400 via-amber-400 to-orange-500"
                        style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-sm font-extrabold text-slate-900 dark:text-slate-100">
                      {formatTemp(day.temperature_max_c, unit)}
                    </span>
                  </div>

                  {isOpen ? (
                    <ChevronUp className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  )}
                </div>
              </button>

              {isOpen && (
                <div className="border-t border-slate-100 bg-slate-50/70 px-4 py-3.5 dark:border-slate-800 dark:bg-slate-950/40">
                  <div className="grid grid-cols-2 gap-2.5 text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white p-2.5 dark:bg-slate-900">
                      <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                        <Umbrella className="h-3.5 w-3.5 text-sky-500" />
                        Chuva máxima
                      </span>
                      <p className="mt-1 font-bold text-slate-900 dark:text-slate-100">
                        {formatPercent(day.precipitation_probability_max_percent)} •{" "}
                        {formatMm(day.precipitation_sum_mm)}
                      </p>
                      {day.precipitation_hours !== null && (
                        <p className="text-[11px] text-slate-400">
                          {day.precipitation_hours.toFixed(0)}h com precipitação
                        </p>
                      )}
                    </div>

                    <div className="rounded-xl bg-white p-2.5 dark:bg-slate-900">
                      <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                        <Wind className="h-3.5 w-3.5 text-teal-500" />
                        Vento máximo
                      </span>
                      <p className="mt-1 font-bold text-slate-900 dark:text-slate-100">
                        {formatWind(day.wind_speed_max_kmh, day.wind_direction_dominant_cardinal)}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        Rajadas até {formatWind(day.wind_gusts_max_kmh)}
                      </p>
                    </div>

                    <div className="rounded-xl bg-white p-2.5 dark:bg-slate-900">
                      <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                        <Sun className="h-3.5 w-3.5 text-amber-500" />
                        UV & Insolação
                      </span>
                      <p className="mt-1 font-bold text-slate-900 dark:text-slate-100">
                        UV máx {day.uv_index_max !== null ? day.uv_index_max.toFixed(1) : "--"}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        Sol {formatHours(day.sunshine_duration_hours)} / Luz{" "}
                        {formatHours(day.daylight_duration_hours)}
                      </p>
                    </div>

                    <div className="rounded-xl bg-white p-2.5 dark:bg-slate-900">
                      <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                        <Sunrise className="h-3.5 w-3.5 text-orange-400" />
                        Sol (Nascer / Pôr)
                      </span>
                      <p className="mt-1 flex items-center gap-1.5 font-bold text-slate-900 dark:text-slate-100">
                        <span>{formatHour(day.sunrise)}</span>
                        <span>•</span>
                        <Sunset className="h-3.5 w-3.5 text-indigo-400" />
                        <span>{formatHour(day.sunset)}</span>
                      </p>
                    </div>
                  </div>

                  <div className="mt-3">
                    <p className="mb-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
                      Horários do dia
                    </p>
                    {loadingFullHourly && dayHours.length === 0 ? (
                      <div className="flex items-center gap-2 py-2 text-xs text-slate-500">
                        <Loader2 className="h-4 w-4 animate-spin text-sky-500" />
                        Carregando detalhe horário completo dos 16 dias...
                      </div>
                    ) : dayHours.length > 0 ? (
                      <div className="flex gap-2 overflow-x-auto pb-1">
                        {dayHours.map((hr) => (
                          <div
                            key={hr.time}
                            className="flex min-w-[76px] shrink-0 flex-col items-center rounded-xl border border-slate-200 bg-white px-2 py-2 text-center dark:border-slate-800 dark:bg-slate-900"
                          >
                            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                              {formatHour(hr.time)}
                            </span>
                            <WeatherIcon icon={hr.condition.icon} className="my-1 h-5 w-5" />
                            <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                              {formatTemp(hr.temperature_c, unit)}
                            </span>
                            <span className="text-[10px] font-medium text-sky-600 dark:text-sky-400">
                              {hr.precipitation_probability_percent ?? 0}%
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {formatMm(hr.precipitation_mm)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">
                        Série horária detalhada indisponível para este dia no provedor atual.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
