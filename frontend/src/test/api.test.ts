import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchAirQuality, searchLocations } from "@/lib/api";
import { fetchWithTimeout } from "@/lib/api/client";

const observation = {
  provider: "CPCB/data.gov.in",
  station: {
    station_id: "cpcb_delhi_ito",
    station_name: "ITO",
    city: "Delhi",
    state: "Delhi",
    latitude: 28.6289,
    longitude: 77.2407,
    latitude_source: "reported_cpcb_metadata",
  },
  readings: {
    "PM2.5": {
      pollutant: "PM2.5",
      value: 45.5,
      unit: null,
      sub_index: 90,
      averaging_period_hours: 24,
      min_value: 10,
      max_value: 90,
      source_pollutant_id: "PM2.5",
    },
  },
  calculated_aqi: 120,
  dominant_pollutant: "PM2.5",
  aqi_category: "Moderate",
  data_sufficiency_met: true,
  measurement_timestamp: "2026-11-25T05:30:00Z",
  retrieval_timestamp: "2026-11-25T06:00:00Z",
  data_quality_status: "verified",
  notes: "Official CPCB observation.",
  hourly_trend: [{ time: "2026-11-25T05:00:00Z", pm2_5: 45.5, aqi: 120, category: "Moderate" }],
  schema_version: "v1",
};

function jsonResponse(payload: unknown) {
  return { ok: true, json: async () => payload } as Response;
}

describe("API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends exact decimal coordinates to the air-quality endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse({ success: true, data: observation }));

    await fetchAirQuality(28.6289, 77.2407);

    const url = String((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(url).toContain("/api/v1/air-quality");
    expect(url).toContain("lat=28.6289");
    expect(url).toContain("lon=77.2407");
    expect(url).not.toContain("localhost:8000");
  });

  it("searches geocoding through the same-origin backend proxy", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      jsonResponse({
        results: [
          {
            id: 1,
            name: "Patna",
            latitude: 25.5941,
            longitude: 85.1376,
            admin1: "Bihar",
            country: "India",
          },
        ],
      })
    );

    const results = await searchLocations("Patna");

    expect(results).toHaveLength(1);
    expect(results[0].latitude).toBe(25.5941);
    expect(results[0].admin1).toBe("Bihar");
    const url = String((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(url).toContain("/api/v1/locations/search");
    expect(url).toContain("name=Patna");
  });

  it("validates the response and preserves backend fields instead of casting", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      jsonResponse({ success: true, data: observation, message: "CPCB observation" })
    );

    const result = await fetchAirQuality(28.6289, 77.2407);

    expect(result.data).toEqual(observation);
    expect(result.data?.readings["PM2.5"].sub_index).toBe(90);
    expect(result.data?.hourly_trend?.[0].category).toBe("Moderate");
  });

  it("rejects an invalid air-quality payload with a safe fixed message", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      jsonResponse({ success: true, data: { provider: "<script>alert(1)</script>" } })
    );

    await expect(fetchAirQuality(28.6, 77.2)).rejects.toMatchObject({
      name: "ApiError",
      message: "Failed to fetch air quality data. The response was invalid.",
    });
  });

  it("rejects malformed JSON without surfacing parser text", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => {
        throw new SyntaxError("unexpected token <script>");
      },
    } as unknown as Response);

    await expect(fetchAirQuality(28.6, 77.2)).rejects.toMatchObject({
      name: "ApiError",
      message: "Failed to fetch air quality data. The response was malformed.",
    });
  });

  it("rejects geocoding results with invalid coordinates", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      jsonResponse({ results: [{ id: 1, name: "Patna", latitude: "not-a-number", longitude: 85 }] })
    );

    await expect(searchLocations("Patna")).rejects.toMatchObject({
      name: "ApiError",
      message: "Location search returned an invalid response. The response was invalid.",
    });
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
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ success: true, data: observation }));
    global.fetch = fetchMock as unknown as typeof fetch;

    await fetchAirQuality(28.6, 77.2);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("keeps the abort deadline active while the response body is consumed", async () => {
    let requestSignal: AbortSignal | undefined;
    const stalledBody = {
      ok: true,
      status: 200,
      json: () =>
        new Promise<unknown>((_resolve, reject) => {
          requestSignal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
    } as unknown as Response;
    global.fetch = vi.fn().mockImplementation(async (_url: string, init?: RequestInit) => {
      requestSignal = init?.signal ?? undefined;
      return stalledBody;
    }) as unknown as typeof fetch;

    await expect(
      fetchWithTimeout("/stalled", {}, async (response) => response.json(), 20)
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(requestSignal?.aborted).toBe(true);
  });
});
