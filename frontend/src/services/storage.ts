import type {
  CachedForecastSnapshot,
  ReminderResponse,
  SavedLocation,
  StoredReminderRef,
  TemperatureUnit,
  ThemeMode,
  WeatherForecastResponse,
} from "../types/weather";

const STORAGE_KEYS = {
  theme: "climapy:theme:v1",
  unit: "climapy:unit:v1",
  activeLocation: "climapy:active_location:v1",
  favorites: "climapy:favorites:v1",
  snapshots: "climapy:snapshots:v1",
  reminders: "climapy:reminders:v1",
} as const;

export const DEFAULT_LOCATION: SavedLocation = {
  name: "São Paulo",
  displayName: "São Paulo, São Paulo, Brasil",
  latitude: -23.55,
  longitude: -46.63,
  timezone: "America/Sao_Paulo",
};

const MAX_SNAPSHOTS = 6;

export function roundCoord(value: number): number {
  const rounded = Math.round(value * 100) / 100;
  return rounded === 0 ? 0 : rounded;
}

export function locationKey(lat: number, lon: number): string {
  return `${roundCoord(lat).toFixed(2)}:${roundCoord(lon).toFixed(2)}`;
}

function readStorage(key: string): string | null {
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    globalThis.localStorage?.setItem(key, value);
  } catch {
    // Ignora falhas de quota ou modo privado restritivo
  }
}

function parseJson<T>(raw: string | null, fallback: T): T {
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function loadTheme(): ThemeMode {
  const saved = readStorage(STORAGE_KEYS.theme);
  if (saved === "light" || saved === "dark") {
    return saved;
  }
  if (
    typeof globalThis.matchMedia === "function" &&
    globalThis.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    return "dark";
  }
  return "light";
}

export function saveTheme(theme: ThemeMode): void {
  writeStorage(STORAGE_KEYS.theme, theme);
}

export function loadUnit(): TemperatureUnit {
  return readStorage(STORAGE_KEYS.unit) === "f" ? "f" : "c";
}

export function saveUnit(unit: TemperatureUnit): void {
  writeStorage(STORAGE_KEYS.unit, unit);
}

export function loadActiveLocation(): SavedLocation {
  const parsed = parseJson<SavedLocation | null>(
    readStorage(STORAGE_KEYS.activeLocation),
    null
  );
  if (
    parsed &&
    typeof parsed.name === "string" &&
    typeof parsed.latitude === "number" &&
    typeof parsed.longitude === "number"
  ) {
    return parsed;
  }
  return DEFAULT_LOCATION;
}

export function saveActiveLocation(location: SavedLocation): void {
  writeStorage(STORAGE_KEYS.activeLocation, JSON.stringify(location));
}

export function loadFavorites(): SavedLocation[] {
  const parsed = parseJson<SavedLocation[]>(readStorage(STORAGE_KEYS.favorites), []);
  return Array.isArray(parsed) ? parsed : [];
}

export function toggleFavoriteLocation(location: SavedLocation): SavedLocation[] {
  const current = loadFavorites();
  const targetKey = locationKey(location.latitude, location.longitude);
  const exists = current.some((item) => locationKey(item.latitude, item.longitude) === targetKey);
  const next = exists
    ? current.filter((item) => locationKey(item.latitude, item.longitude) !== targetKey)
    : [
        {
          ...location,
          latitude: roundCoord(location.latitude),
          longitude: roundCoord(location.longitude),
        },
        ...current,
      ].slice(0, 12);
  writeStorage(STORAGE_KEYS.favorites, JSON.stringify(next));
  return next;
}

export function isFavoriteLocation(favorites: SavedLocation[], location: SavedLocation): boolean {
  const targetKey = locationKey(location.latitude, location.longitude);
  return favorites.some((item) => locationKey(item.latitude, item.longitude) === targetKey);
}

export function saveForecastSnapshot(
  location: SavedLocation,
  forecast: WeatherForecastResponse
): void {
  const key = locationKey(location.latitude, location.longitude);
  const map = parseJson<Record<string, CachedForecastSnapshot>>(
    readStorage(STORAGE_KEYS.snapshots),
    {}
  );
  map[key] = {
    savedAt: new Date().toISOString(),
    location,
    forecast,
  };
  const entries = Object.entries(map).sort((a, b) =>
    b[1].savedAt.localeCompare(a[1].savedAt)
  );
  const trimmed = Object.fromEntries(entries.slice(0, MAX_SNAPSHOTS));
  writeStorage(STORAGE_KEYS.snapshots, JSON.stringify(trimmed));
}

export function loadForecastSnapshot(location: SavedLocation): CachedForecastSnapshot | null {
  const key = locationKey(location.latitude, location.longitude);
  const map = parseJson<Record<string, CachedForecastSnapshot>>(
    readStorage(STORAGE_KEYS.snapshots),
    {}
  );
  return map[key] ?? null;
}

export function loadReminderRefs(): StoredReminderRef[] {
  const parsed = parseJson<StoredReminderRef[]>(readStorage(STORAGE_KEYS.reminders), []);
  return Array.isArray(parsed)
    ? parsed.filter((item) => typeof item?.id === "string" && typeof item?.token === "string")
    : [];
}

export function saveReminderRefs(refs: StoredReminderRef[]): void {
  writeStorage(STORAGE_KEYS.reminders, JSON.stringify(refs));
}

export function upsertReminderRef(ref: StoredReminderRef): StoredReminderRef[] {
  const current = loadReminderRefs();
  const filtered = current.filter((item) => item.id !== ref.id);
  const next = [ref, ...filtered];
  saveReminderRefs(next);
  return next;
}

export function updateCachedReminder(reminder: ReminderResponse): StoredReminderRef[] {
  const current = loadReminderRefs();
  const next = current.map((item) =>
    item.id === reminder.id ? { ...item, cached: reminder } : item
  );
  saveReminderRefs(next);
  return next;
}

export function removeReminderRef(id: string): StoredReminderRef[] {
  const next = loadReminderRefs().filter((item) => item.id !== id);
  saveReminderRefs(next);
  return next;
}
