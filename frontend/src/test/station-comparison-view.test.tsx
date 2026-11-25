import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StationComparisonView } from "@/components/dashboard/station-comparison-view";
import { NormalizedObservation } from "@/types/observation";

function observation(stationId: string, name: string, aqi: number): NormalizedObservation {
  return {
    provider: "openmeteo_cams",
    station: {
      station_id: stationId,
      station_name: name,
      city: "Delhi",
      state: "Delhi",
      latitude: 28.6289,
      longitude: 77.2407,
      provider: "fallback_registry_coordinate",
    },
    readings: {
      "PM2.5": {
        pollutant: "PM2.5",
        value: 45,
        unit: null,
      },
    },
    calculated_aqi: aqi,
    dominant_pollutant: null,
    aqi_category: null,
    data_sufficiency_met: true,
    measurement_timestamp: "2026-11-25T10:00:00Z",
    retrieval_timestamp: "2026-11-25T10:05:00Z",
    data_quality_status: "verified",
    notes: "Coordinate-grid estimate at a registered location, not a physical station observation.",
  };
}

describe("StationComparisonView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/stations/comparison-presets")) {
        return {
          ok: true,
          json: async () => ({
            success: true,
            source: "fallback_registry_coordinate_grid",
            message: "Live station coordinates are unavailable.",
            presets: [
              {
                key: "delhi-corridors",
                name: "Grid estimate: ITO corridor vs Anand Vihar corridor",
                description: "Grid comparison",
                ids: ["grid:cpcb_delhi_ito", "grid:cpcb_delhi_anand_vihar"],
                basis: "coordinate_estimate",
                source: "fallback_registry_coordinate_grid",
                candidates: [],
              },
            ],
          }),
        } as Response;
      }
      if (url.includes("/api/v1/stations/compare")) {
        return {
          ok: true,
          json: async () => ({
            success: true,
            stations_count: 2,
            observations: [
              observation("grid:cpcb_delhi_ito", "ITO corridor (grid estimate)", 120),
              observation("grid:cpcb_delhi_anand_vihar", "Anand Vihar corridor (grid estimate)", 180),
            ],
            differential: {
              cleanest_station_name: "ITO corridor (grid estimate)",
              most_polluted_station_name: "Anand Vihar corridor (grid estimate)",
              aqi_difference: 60,
              pm25_difference_ug_m3: 12.5,
              summary: "Grid estimates: ITO corridor reports cleaner air compared to Anand Vihar.",
            },
            basis: "coordinate_estimate",
            source: "fallback_registry_coordinate_grid",
            requested_ids: ["grid:cpcb_delhi_ito", "grid:cpcb_delhi_anand_vihar"],
            unresolved_ids: [],
            message: "Coordinate-grid estimates, not physical station observations.",
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    });
  });

  it("renders backend-provided presets and labels grid estimates honestly", async () => {
    render(<StationComparisonView />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: /Grid estimate: ITO corridor vs Anand Vihar corridor/i,
        })
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/Delhi Comparison: Central \(ITO\)/i)).toBeNull();
    expect(screen.getByText(/not physical station observations/i)).toBeInTheDocument();
    expect(screen.getByText(/ITO corridor \(grid estimate\)/i)).toBeInTheDocument();

    const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) =>
      String(call[0])
    );
    expect(calls.some((url) => url.includes("/api/v1/stations/comparison-presets"))).toBe(true);
    expect(calls.some((url) => url.includes("/api/v1/stations/compare"))).toBe(true);
  });
});
