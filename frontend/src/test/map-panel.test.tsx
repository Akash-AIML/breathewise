import { type ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";
import { MapPanel } from "@/components/dashboard/map-panel";
import { MapStation } from "@/components/dashboard/station-map";

const liveStation: MapStation = {
  name: "ITO",
  station_id: "cpcb_delhi_ito",
  city: "Delhi",
  state: "Delhi",
  lat: 28.6289,
  lon: 77.2407,
};

function renderPanel(overrides: Partial<ComponentProps<typeof MapPanel>> = {}) {
  const onRetryStations = vi.fn();
  render(
    <MapPanel
      liveStations={[]}
      stationsSource="source unavailable"
      selectedStationId="none"
      onSelectStation={vi.fn()}
      onRetryStations={onRetryStations}
      {...overrides}
    />
  );
  return { onRetryStations };
}

describe("MapPanel failure paths", () => {
  it("reports an unavailable source without fabricating map markers", () => {
    renderPanel();

    expect(screen.getByRole("status")).toHaveTextContent(
      /Live station coordinates are unavailable \(source unavailable\)/i
    );
    expect(screen.getByText(/map is intentionally hidden instead of plotting estimated/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Select monitoring station/i })).not.toBeInTheDocument();
  });

  it("exposes an explicit retry action for a failed station lookup", () => {
    const { onRetryStations } = renderPanel({ stationsSource: null });

    expect(screen.getByRole("status")).toHaveTextContent(/unknown source/i);
    fireEvent.click(screen.getByRole("button", { name: /Retry station lookup/i }));
    expect(onRetryStations).toHaveBeenCalledTimes(1);
  });

  it("keeps the map hidden when no live coordinates are supplied", () => {
    renderPanel({ stationsSource: "Station metadata source: CPCB/data.gov.in" });

    expect(screen.getByText(/map is intentionally hidden/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Select monitoring station/i })).not.toBeInTheDocument();
  });

  it("renders only the stations actually supplied by the caller", () => {
    renderPanel({ liveStations: [liveStation], stationsSource: "CPCB/data.gov.in" });

    expect(screen.getByRole("button", { name: /Select monitoring station ITO in Delhi/i })).toBeInTheDocument();
    expect(screen.getByText(/Markers use reported CPCB station coordinates/i)).toBeInTheDocument();
    expect(screen.queryByText(/map is intentionally hidden/i)).not.toBeInTheDocument();
  });
});

describe("HomePage station lookup failure and retry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("recovers from a failed lookup and plots only the returned CPCB stations", async () => {
    let stationRequests = 0;
    global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/stations")) {
        stationRequests += 1;
        if (stationRequests === 1) {
          throw new Error("station network failure");
        }
        return {
          ok: true,
          json: async () => ({
            success: true,
            count: 1,
            data: [
              {
                station_id: liveStation.station_id,
                station_name: liveStation.name,
                city: liveStation.city,
                state: liveStation.state,
                latitude: liveStation.lat,
                longitude: liveStation.lon,
              },
            ],
            message: "Station metadata source: CPCB/data.gov.in",
          }),
        } as Response;
      }
      if (url.includes("/api/v1/air-quality")) {
        return {
          ok: true,
          json: async () => ({ success: true, data: null, message: "No live observation" }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    });

    render(<HomePage />);
    fireEvent.click(screen.getByRole("tab", { name: /Station Map/i }));

    expect(await screen.findByText(/map is intentionally hidden/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Select monitoring station/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Retry station lookup/i }));

    expect(
      await screen.findByRole("button", { name: /Select monitoring station ITO in Delhi/i })
    ).toBeInTheDocument();
    expect(stationRequests).toBe(2);
  });
});
