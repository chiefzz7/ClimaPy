import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_LOCATION,
  loadActiveLocation,
  loadFavorites,
  loadReminderRefs,
  loadTheme,
  loadUnit,
  removeReminderRef,
  roundCoord,
  saveActiveLocation,
  saveTheme,
  saveUnit,
  toggleFavoriteLocation,
  upsertReminderRef,
} from "./storage";

function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
  };
}

describe("services/storage", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "localStorage", {
      value: createMemoryStorage(),
      configurable: true,
    });
  });

  it("persists theme, unit and active location safely", () => {
    expect(loadUnit()).toBe("c");
    saveUnit("f");
    expect(loadUnit()).toBe("f");

    saveTheme("dark");
    expect(loadTheme()).toBe("dark");

    expect(loadActiveLocation()).toEqual(DEFAULT_LOCATION);
    const custom = { ...DEFAULT_LOCATION, name: "Registro", latitude: -24.49, longitude: -47.84 };
    saveActiveLocation(custom);
    expect(loadActiveLocation().name).toBe("Registro");
  });

  it("deduplicates favorite cities by rounded coordinates", () => {
    const locA = {
      name: "Registro",
      displayName: "Registro, SP, Brasil",
      latitude: -24.491,
      longitude: -47.842,
      timezone: "America/Sao_Paulo",
    };
    const locSameRounded = { ...locA, latitude: -24.494, longitude: -47.844 };

    expect(toggleFavoriteLocation(locA)).toHaveLength(1);
    expect(loadFavorites()[0].latitude).toBe(roundCoord(-24.491));
    expect(toggleFavoriteLocation(locSameRounded)).toHaveLength(0);
  });

  it("manages anonymous reminder tokens locally", () => {
    upsertReminderRef({ id: "rem-1", token: "secret-token-1" });
    upsertReminderRef({ id: "rem-2", token: "secret-token-2" });
    expect(loadReminderRefs()).toHaveLength(2);

    removeReminderRef("rem-1");
    expect(loadReminderRefs()).toEqual([{ id: "rem-2", token: "secret-token-2" }]);
  });
});
