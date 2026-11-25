import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";
import { NormalizedObservation } from "@/types/observation";

const cpcbObservation: NormalizedObservation = {
  provider: "CPCB/data.gov.in",
  station: {
    station_id: "cpcb_tamil_nadu_chennai_velachery",
    station_name: "Velachery",
    city: "Chennai",
    state: "Tamil Nadu",
    latitude: 12.9815,
    longitude: 80.2182,
    distance_km: 3.2,
    provider: "CPCB/data.gov.in",
    source_observation_time: "2026-11-25T05:30:00Z",
  },
  readings: {
    "PM2.5": {
      pollutant: "PM2.5",
      value: 45.5,
      unit: null,
      averaging_period_hours: null,
      min_value: 10,
      max_value: 90,
      source_pollutant_id: "PM2.5",
    },
  },
  calculated_aqi: null,
  dominant_pollutant: null,
  aqi_category: null,
  data_sufficiency_met: false,
  measurement_timestamp: "2026-11-25T05:30:00Z",
  retrieval_timestamp: "2026-11-25T06:00:00Z",
  data_quality_status: "stale",
  notes: "Official CPCB AQI unavailable: averaging period not verified.",
};

function mockFetch(observation: NormalizedObservation | null = cpcbObservation) {
  global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/air-quality")) {
      return {
        ok: true,
        json: async () => ({
          success: true,
          data: observation,
          message: observation ? "CPCB observation" : "No live observation",
        }),
      } as Response;
    }
    if (url.includes("/api/v1/stations")) {
      return {
        ok: true,
        json: async () => ({
          success: true,
          count: 0,
          data: [],
          message: "Station metadata source: fallback_registry",
        }),
      } as Response;
    }
    return { ok: true, json: async () => ({}) } as Response;
  });
}

describe("HomePage CPCB observation display", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch();
  });

  it("shows station identity, source time, unverified unit, and stale warning", async () => {
    render(<HomePage />);

    await waitFor(() => {
      expect(screen.getByText(/CPCB\/data.gov.in/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Velachery, Chennai, Tamil Nadu/)).toBeInTheDocument();
    expect(screen.getByText(/Unit not provided by source/)).toBeInTheDocument();
    expect(screen.getByText(/Min 10 \/ Max 90/)).toBeInTheDocument();
    expect(screen.getByText(/stale data:/i)).toBeInTheDocument();
    expect(screen.getByText(/AQI Unavailable/)).toBeInTheDocument();
    expect(
      screen.getByText(/averaging period not verified/)
    ).toBeInTheDocument();
  });

  it("hides the map instead of plotting fallback city-centre coordinates", async () => {
    render(<HomePage />);
    await waitFor(() => expect(screen.getByText(/CPCB\/data.gov.in/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("tab", { name: /Station Map/i }));

    expect(
      screen.getByText(/map is intentionally hidden instead of plotting estimated/i)
    ).toBeInTheDocument();
  });

  it("distinguishes no data from zero pollution and offers retry", async () => {
    mockFetch(null);
    render(<HomePage />);

    await waitFor(() => {
      expect(screen.getByText(/No observation available/)).toBeInTheDocument();
    });
    expect(screen.getByText(/not a zero-pollution result/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Retry observation request/i }).length).toBeGreaterThan(0);
  });
});
