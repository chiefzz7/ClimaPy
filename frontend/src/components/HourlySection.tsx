import { Droplets, Eye, Gauge, Navigation, Sun, Umbrella, Wind } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { HourlyForecastItem, TemperatureUnit } from "../types/weather";
import {
  extractDatePrefix,
  formatDayShort,
  formatHour,
  formatMm,
  formatPercent,
  formatPressure,
  formatTemp,
  formatVisibility,
  formatWind,
  getUvCategory,
} from "../utils/format";
import { HourlyCharts } from "./HourlyCharts";
import { WeatherIcon } from "./WeatherIcon";

interface HourlySectionProps {
  hourly72h: HourlyForecastItem[];
  referenceToday: string;
  unit: TemperatureUnit;
}

export function HourlySection({ hourly72h, referenceToday, unit }: HourlySectionProps) {
  const [selectedDay, setSelectedDay] = useState<string>("all");
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  const dayFilters = useMemo(() => {
    const seen = new Set<string>();
    const days: string[] = [];
    for (const item of hourly72h) {
      const dateKey = extractDatePrefix(item.time);
      if (!seen.has(dateKey)) {
        seen.add(dateKey);
        days.push(dateKey);
      }
      if (days.length >= 4) break;
    }
    return days;
  }, [hourly72h]);

  const filteredItems = useMemo(() => {
    if (selectedDay === "all") {
      return hourly72h;
    }
    return hourly72h.filter((item) => extractDatePrefix(item.time) === selectedDay);
  }, [hourly72h, selectedDay]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [selectedDay, hourly72h]);

  const safeIndex = Math.min(selectedIndex, Math.max(0, filteredItems.length - 1));
  const activeHour = filteredItems[safeIndex];

  if (hourly72h.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        Sem dados horários disponíveis para esta localidade no momento.
      </div>
    );
  }

  const uvMeta = getUvCategory(activeHour?.uv_index);

  return (
    <section aria-label="Previsão horária de 72 horas" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
            Previsão Hora a Hora (Próximas 72h)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Acompanhe temperatura, umidade, chance e volume de chuva a cada hora.
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setSelectedDay("all")}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              selectedDay === "all"
                ? "bg-sky-600 text-white shadow-sm"
                : "border border-slate-200 bg-white text-slate-600 hover:border-sky-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
            }`}
          >
            Todas (72h)
          </button>
          {dayFilters.map((day) => (
            <button
              key={day}
              type="button"
              onClick={() => setSelectedDay(day)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                selectedDay === day
                  ? "bg-sky-600 text-white shadow-sm"
                  : "border border-slate-200 bg-white text-slate-600 hover:border-sky-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
              }`}
            >
              {formatDayShort(day, referenceToday)}
            </button>
          ))}
        </div>
      </div>

      <HourlyCharts
        items={filteredItems}
        unit={unit}
        selectedIndex={safeIndex}
        onSelectIndex={setSelectedIndex}
      />

      <div className="flex gap-2.5 overflow-x-auto pb-2">
        {filteredItems.map((item, idx) => {
          const isSelected = idx === safeIndex;
          const rainProb = item.precipitation_probability_percent ?? 0;
          return (
            <button
              key={item.time}
              type="button"
              onClick={() => setSelectedIndex(idx)}
              className={`flex min-w-[94px] shrink-0 flex-col items-center rounded-2xl border p-3 text-center transition ${
                isSelected
                  ? "border-sky-500 bg-sky-500/10 ring-2 ring-sky-500/20 dark:bg-sky-500/15"
                  : "border-slate-200 bg-white hover:border-sky-300 dark:border-slate-800 dark:bg-slate-900"
              }`}
            >
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                {formatDayShort(extractDatePrefix(item.time), referenceToday)}
              </span>
              <span className="text-sm font-bold text-slate-900 dark:text-slate-100">
                {formatHour(item.time)}
              </span>
              <WeatherIcon icon={item.condition.icon} className="my-2 h-7 w-7" />
              <span className="text-base font-extrabold text-slate-900 dark:text-slate-100">
                {formatTemp(item.temperature_c, unit)}
              </span>
              <span className="mt-1 inline-flex items-center gap-0.5 text-[11px] font-semibold text-sky-600 dark:text-sky-400">
                <Umbrella className="h-3 w-3" />
                {rainProb}%
              </span>
              <span className="text-[10px] text-slate-400">
                {formatMm(item.precipitation_mm)}
              </span>
            </button>
          );
        })}
      </div>

      {activeHour && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800">
            <div className="flex items-center gap-2.5">
              <WeatherIcon icon={activeHour.condition.icon} className="h-8 w-8" />
              <div>
                <p className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  {formatDayShort(extractDatePrefix(activeHour.time), referenceToday)} às{" "}
                  {formatHour(activeHour.time)} — {activeHour.condition.label_pt}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Sensação de {formatTemp(activeHour.apparent_temperature_c, unit)} • Ponto de
                  orvalho {formatTemp(activeHour.dew_point_c, unit)}
                </p>
              </div>
            </div>
            <span className="text-2xl font-extrabold text-slate-900 dark:text-slate-100">
              {formatTemp(activeHour.temperature_c, unit)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Droplets className="h-3.5 w-3.5 text-sky-500" />
                Umidade
              </span>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-slate-100">
                {formatPercent(activeHour.relative_humidity_percent)}
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Umbrella className="h-3.5 w-3.5 text-sky-500" />
                Chuva ({formatPercent(activeHour.precipitation_probability_percent)})
              </span>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-slate-100">
                {formatMm(activeHour.precipitation_mm)}
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Wind className="h-3.5 w-3.5 text-teal-500" />
                Vento
              </span>
              <p className="mt-1 flex items-center gap-1 text-sm font-bold text-slate-900 dark:text-slate-100">
                <Navigation
                  className="h-3 w-3 text-teal-500"
                  style={{ transform: `rotate(${activeHour.wind_direction_deg ?? 0}deg)` }}
                />
                {formatWind(activeHour.wind_speed_kmh, activeHour.wind_direction_cardinal)}
              </p>
              <p className="text-[11px] text-slate-400">
                Rajadas {formatWind(activeHour.wind_gusts_kmh)}
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Gauge className="h-3.5 w-3.5 text-indigo-500" />
                Pressão MSL
              </span>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-slate-100">
                {formatPressure(activeHour.pressure_msl_hpa)}
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Sun className="h-3.5 w-3.5 text-amber-500" />
                Índice UV
              </span>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-slate-100">
                {activeHour.uv_index !== null && activeHour.uv_index !== undefined
                  ? activeHour.uv_index.toFixed(1)
                  : "--"}{" "}
                <span className={`text-xs font-medium ${uvMeta.toneClass}`}>({uvMeta.label})</span>
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Eye className="h-3.5 w-3.5 text-slate-400" />
                Visibilidade
              </span>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-slate-100">
                {formatVisibility(activeHour.visibility_km)}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
