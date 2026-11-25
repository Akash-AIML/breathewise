import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAirQuality, searchLocations } from "@/lib/api";

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
});
