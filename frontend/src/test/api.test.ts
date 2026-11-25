import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchAirQuality, searchLocations } from "@/lib/api";

describe("API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends exact decimal coordinates to the air-quality endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: {} }),
    } as Response);

    await fetchAirQuality(28.6289, 77.2407);

    const url = String((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(url).toContain("/api/v1/air-quality");
    expect(url).toContain("lat=28.6289");
    expect(url).toContain("lon=77.2407");
    expect(url).not.toContain("localhost:8000");
  });

  it("searches geocoding through the same-origin backend proxy", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [{ id: 1, name: "Patna", latitude: 25.5941, longitude: 85.1376 }],
      }),
    } as Response);

    const results = await searchLocations("Patna");

    expect(results).toHaveLength(1);
    expect(results[0].latitude).toBe(25.5941);
    const url = String((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(url).toContain("/api/v1/locations/search");
    expect(url).toContain("name=Patna");
  });

  it("does not render raw upstream error text in the UI", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ message: "<img src=x onerror=alert(1)> Call 900-xxx" }),
    } as Response);

    let caught: unknown;
    try {
      await fetchAirQuality(28.6, 77.2);
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).message).not.toContain("<img");
    expect((caught as ApiError).message).not.toContain("900-xxx");
    expect((caught as ApiError).message).toContain("temporarily unavailable");
  });

  it("uses a fixed retry message for rate limiting", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ message: "backend secret detail" }),
    } as Response);

    let caught: unknown;
    try {
      await fetchAirQuality(28.6, 77.2);
    } catch (error) {
      caught = error;
    }

    expect((caught as ApiError).status).toBe(429);
    expect((caught as ApiError).message).toBe(
      "Too many requests. Please wait a moment and try again."
    );
  });

  it("attaches an abort signal so slow requests cannot hang forever", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: {} }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await fetchAirQuality(28.6, 77.2);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });
});
