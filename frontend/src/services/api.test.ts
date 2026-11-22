import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, deleteReminder, fetchForecast, getReminder } from "./api";

describe("services/api", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("calls forecast endpoint with rounded coords and include_full_hourly flag", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ latitude: -24.49, longitude: -47.84 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    await fetchForecast({
      lat: -24.494,
      lon: -47.841,
      days: 16,
      tz: "America/Sao_Paulo",
      includeAirQuality: true,
      includeFullHourly: false,
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const calledUrl = String(mockFetch.mock.calls[0][0]);
    expect(calledUrl).toContain("/api/v1/weather/forecast?");
    expect(calledUrl).toContain("lat=-24.49");
    expect(calledUrl).toContain("lon=-47.84");
    expect(calledUrl).toContain("include_full_hourly=false");
  });

  it("sends X-Reminder-Token header and maps HTTP errors to ApiError", async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "r1", label: "Teste" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Lembrete não encontrado." }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        })
      );
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await getReminder("r1", "tok-123");
    expect(result.id).toBe("r1");
    const init = mockFetch.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Headers;
    expect(headers.get("X-Reminder-Token")).toBe("tok-123");

    await expect(deleteReminder("r1", "tok-123")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: "Lembrete não encontrado.",
    } satisfies Partial<ApiError>);
  });
});
