import type { TemperatureUnit } from "../types/weather";

export function convertTemp(tempC: number, unit: TemperatureUnit): number {
  return unit === "f" ? (tempC * 9) / 5 + 32 : tempC;
}

export function formatTemp(tempC: number | null | undefined, unit: TemperatureUnit): string {
  if (tempC === null || tempC === undefined || Number.isNaN(tempC)) {
    return "--°";
  }
  return `${Math.round(convertTemp(tempC, unit))}°`;
}

export function formatTempWithUnit(tempC: number | null | undefined, unit: TemperatureUnit): string {
  if (tempC === null || tempC === undefined || Number.isNaN(tempC)) {
    return unit === "f" ? "--°F" : "--°C";
  }
  return `${Math.round(convertTemp(tempC, unit))}°${unit.toUpperCase()}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--%";
  }
  return `${Math.round(value)}%`;
}

export function formatMm(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "0,0 mm";
  }
  return `${value.toFixed(1).replace(".", ",")} mm`;
}

export function formatWind(
  speedKmh: number | null | undefined,
  cardinal?: string | null
): string {
  if (speedKmh === null || speedKmh === undefined || Number.isNaN(speedKmh)) {
    return "-- km/h";
  }
  const base = `${Math.round(speedKmh)} km/h`;
  return cardinal ? `${base} ${cardinal}` : base;
}

export function formatPressure(hpa: number | null | undefined): string {
  if (hpa === null || hpa === undefined || Number.isNaN(hpa)) {
    return "-- hPa";
  }
  return `${Math.round(hpa)} hPa`;
}

export function formatVisibility(km: number | null | undefined): string {
  if (km === null || km === undefined || Number.isNaN(km)) {
    return "-- km";
  }
  return `${km.toFixed(1).replace(".", ",")} km`;
}

export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined || Number.isNaN(hours)) {
    return "--h";
  }
  const whole = Math.floor(hours);
  const mins = Math.round((hours - whole) * 60);
  return `${whole}h${String(mins).padStart(2, "0")}`;
}

export function formatHour(isoDateTime: string | null | undefined): string {
  if (!isoDateTime || isoDateTime.length < 16) {
    return "--:--";
  }
  return isoDateTime.slice(11, 16);
}

export function extractDatePrefix(isoDateTime: string): string {
  return isoDateTime.slice(0, 10);
}

const WEEKDAYS_SHORT = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const MONTHS_SHORT = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

function parseIsoDateParts(dateStr: string): { year: number; month: number; day: number } | null {
  const parts = dateStr.slice(0, 10).split("-");
  if (parts.length !== 3) {
    return null;
  }
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  const day = Number(parts[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
    return null;
  }
  return { year, month, day };
}

function addDaysIso(dateStr: string, offset: number): string {
  const parsed = parseIsoDateParts(dateStr);
  if (!parsed) {
    return dateStr;
  }
  const dt = new Date(Date.UTC(parsed.year, parsed.month - 1, parsed.day + offset));
  return dt.toISOString().slice(0, 10);
}

export function formatDayShort(dateStr: string, referenceToday?: string): string {
  if (referenceToday && dateStr === referenceToday) {
    return "Hoje";
  }
  if (referenceToday && dateStr === addDaysIso(referenceToday, 1)) {
    return "Amanhã";
  }
  const parsed = parseIsoDateParts(dateStr);
  if (!parsed) {
    return dateStr;
  }
  const dt = new Date(Date.UTC(parsed.year, parsed.month - 1, parsed.day));
  const wd = WEEKDAYS_SHORT[dt.getUTCDay()] ?? "";
  return `${wd}, ${String(parsed.day).padStart(2, "0")}/${String(parsed.month).padStart(2, "0")}`;
}

export function formatDayFull(dateStr: string, referenceToday?: string): string {
  const parsed = parseIsoDateParts(dateStr);
  if (!parsed) {
    return dateStr;
  }
  const monthName = MONTHS_SHORT[parsed.month - 1] ?? "";
  const prefix =
    referenceToday && dateStr === referenceToday
      ? "Hoje"
      : referenceToday && dateStr === addDaysIso(referenceToday, 1)
        ? "Amanhã"
        : WEEKDAYS_SHORT[new Date(Date.UTC(parsed.year, parsed.month - 1, parsed.day)).getUTCDay()];
  return `${prefix} • ${parsed.day} de ${monthName}`;
}

export function getUvCategory(uv: number | null | undefined): {
  label: string;
  toneClass: string;
} {
  if (uv === null || uv === undefined || Number.isNaN(uv)) {
    return { label: "Indisponível", toneClass: "text-slate-400" };
  }
  if (uv < 3) {
    return { label: "Baixo", toneClass: "text-emerald-500" };
  }
  if (uv < 6) {
    return { label: "Moderado", toneClass: "text-amber-500" };
  }
  if (uv < 8) {
    return { label: "Alto", toneClass: "text-orange-500" };
  }
  if (uv < 11) {
    return { label: "Muito alto", toneClass: "text-rose-500" };
  }
  return { label: "Extremo", toneClass: "text-purple-500" };
}

export function getAqiStyle(aqi: number | null | undefined): {
  badgeClass: string;
  barClass: string;
  label: string;
} {
  if (aqi === null || aqi === undefined) {
    return {
      badgeClass: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
      barClass: "bg-slate-400",
      label: "Sem leitura",
    };
  }
  if (aqi <= 20) {
    return {
      badgeClass: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
      barClass: "bg-emerald-500",
      label: "Boa",
    };
  }
  if (aqi <= 40) {
    return {
      badgeClass: "bg-lime-500/15 text-lime-700 dark:text-lime-300",
      barClass: "bg-lime-500",
      label: "Razoável",
    };
  }
  if (aqi <= 60) {
    return {
      badgeClass: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
      barClass: "bg-amber-500",
      label: "Moderada",
    };
  }
  if (aqi <= 80) {
    return {
      badgeClass: "bg-orange-500/15 text-orange-700 dark:text-orange-300",
      barClass: "bg-orange-500",
      label: "Ruim",
    };
  }
  return {
    badgeClass: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
    barClass: "bg-rose-500",
    label: "Muito Ruim",
  };
}

export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = globalThis.atob(base64);
  const buffer = new ArrayBuffer(rawData.length);
  const outputArray = new Uint8Array(buffer);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
