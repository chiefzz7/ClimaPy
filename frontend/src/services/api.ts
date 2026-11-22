import type {
  GeocodingSearchResponse,
  PushTestResponse,
  ReminderCreateRequest,
  ReminderCreateResponse,
  ReminderResponse,
  ReminderUpdateRequest,
  ReverseGeocodingResponse,
  VapidPublicKeyResponse,
  WeatherForecastResponse,
} from "../types/weather";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function resolveBaseUrl(): string {
  const envObj = (import.meta as { env?: Record<string, string | undefined> }).env;
  const raw = envObj?.VITE_API_BASE_URL?.trim() ?? "";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 12000
): Promise<T> {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await globalThis.fetch(`${resolveBaseUrl()}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (response.status === 204) {
      return undefined as T;
    }

    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      const detail =
        payload &&
        typeof payload === "object" &&
        "detail" in payload &&
        typeof (payload as { detail: unknown }).detail === "string"
          ? (payload as { detail: string }).detail
          : `Erro na requisição (${response.status}).`;
      throw new ApiError(response.status, detail);
    }

    return payload as T;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError(408, "Tempo limite excedido ao consultar o servidor.");
    }
    throw new ApiError(0, "Sem conexão com o servidor do ClimaPy.");
  } finally {
    globalThis.clearTimeout(timer);
  }
}

export interface FetchForecastParams {
  lat: number;
  lon: number;
  days?: number;
  tz?: string;
  includeAirQuality?: boolean;
  includeFullHourly?: boolean;
}

export async function fetchForecast({
  lat,
  lon,
  days = 16,
  tz = "auto",
  includeAirQuality = true,
  includeFullHourly = false,
}: FetchForecastParams): Promise<WeatherForecastResponse> {
  const search = new URLSearchParams({
    lat: lat.toFixed(2),
    lon: lon.toFixed(2),
    days: String(days),
    tz,
    include_air_quality: String(includeAirQuality),
    include_full_hourly: String(includeFullHourly),
  });
  return requestJson<WeatherForecastResponse>(`/api/v1/weather/forecast?${search.toString()}`);
}

export async function searchLocations(
  query: string,
  count = 6,
  lang = "pt"
): Promise<GeocodingSearchResponse> {
  const search = new URLSearchParams({
    q: query.trim(),
    count: String(count),
    lang,
  });
  return requestJson<GeocodingSearchResponse>(`/api/v1/geocoding/search?${search.toString()}`);
}

export async function reverseGeocode(lat: number, lon: number): Promise<ReverseGeocodingResponse> {
  const search = new URLSearchParams({
    lat: lat.toFixed(2),
    lon: lon.toFixed(2),
  });
  return requestJson<ReverseGeocodingResponse>(`/api/v1/geocoding/reverse?${search.toString()}`);
}

export async function fetchVapidPublicKey(): Promise<VapidPublicKeyResponse> {
  return requestJson<VapidPublicKeyResponse>("/api/v1/reminders/vapid-public-key");
}

export async function createReminder(
  payload: ReminderCreateRequest
): Promise<ReminderCreateResponse> {
  return requestJson<ReminderCreateResponse>("/api/v1/reminders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getReminder(id: string, token: string): Promise<ReminderResponse> {
  return requestJson<ReminderResponse>(`/api/v1/reminders/${encodeURIComponent(id)}`, {
    headers: { "X-Reminder-Token": token },
  });
}

export async function updateReminder(
  id: string,
  token: string,
  payload: ReminderUpdateRequest
): Promise<ReminderResponse> {
  return requestJson<ReminderResponse>(`/api/v1/reminders/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "X-Reminder-Token": token },
    body: JSON.stringify(payload),
  });
}

export async function deleteReminder(id: string, token: string): Promise<void> {
  await requestJson<void>(`/api/v1/reminders/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { "X-Reminder-Token": token },
  });
}

export async function sendTestReminder(id: string, token: string): Promise<PushTestResponse> {
  return requestJson<PushTestResponse>(`/api/v1/reminders/${encodeURIComponent(id)}/test`, {
    method: "POST",
    headers: { "X-Reminder-Token": token },
  });
}
