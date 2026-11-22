import { describe, expect, it } from "vitest";
import {
  convertTemp,
  formatDayShort,
  formatHour,
  formatHours,
  formatMm,
  formatPressure,
  formatTemp,
  formatVisibility,
  formatWind,
  getAqiStyle,
  getUvCategory,
  urlBase64ToUint8Array,
} from "./format";

describe("utils/format", () => {
  it("converts and formats temperatures in C and F", () => {
    expect(convertTemp(0, "f")).toBe(32);
    expect(convertTemp(25, "c")).toBe(25);
    expect(formatTemp(24.6, "c")).toBe("25°");
    expect(formatTemp(25, "f")).toBe("77°");
    expect(formatTemp(null, "c")).toBe("--°");
  });

  it("formats rainfall, wind, pressure, visibility and hours", () => {
    expect(formatMm(1.25)).toBe("1,3 mm");
    expect(formatWind(14.4, "ENE")).toBe("14 km/h ENE");
    expect(formatPressure(1015.2)).toBe("1015 hPa");
    expect(formatVisibility(24.1)).toBe("24,1 km");
    expect(formatHours(13.5)).toBe("13h30");
    expect(formatHour("2026-11-21T21:45")).toBe("21:45");
  });

  it("formats relative day labels in PT-BR", () => {
    expect(formatDayShort("2026-11-21", "2026-11-21")).toBe("Hoje");
    expect(formatDayShort("2026-11-22", "2026-11-21")).toBe("Amanhã");
    expect(formatDayShort("2026-11-23", "2026-11-21")).toContain("23/11");
  });

  it("classifies UV and AQI ranges cleanly", () => {
    expect(getUvCategory(1.5).label).toBe("Baixo");
    expect(getUvCategory(9.2).label).toBe("Muito alto");
    expect(getAqiStyle(18).label).toBe("Boa");
    expect(getAqiStyle(75).label).toBe("Ruim");
  });

  it("decodes URL-safe base64 VAPID keys into Uint8Array", () => {
    const bytes = urlBase64ToUint8Array("AQIDBA");
    expect(Array.from(bytes)).toEqual([1, 2, 3, 4]);
  });
});
