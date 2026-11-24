import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { StationMap, MapStation } from "@/components/dashboard/station-map";

const mockStations: MapStation[] = [
  { name: "Delhi (ITO)", station_id: "cpcb_delhi_ito", lat: 28.6289, lon: 77.2407, city: "Delhi", state: "Delhi" },
  { name: "Mumbai (BKC)", station_id: "cpcb_mumbai_bandra", lat: 19.0657, lon: 72.8687, city: "Mumbai", state: "Maharashtra" },
];

describe("StationMap Component", () => {
  it("renders station map with station pins", () => {
    render(
      <StationMap
        stations={mockStations}
        selectedStationId="cpcb_delhi_ito"
        onSelectStation={vi.fn()}
      />
    );
    expect(screen.getByText(/Interactive Indian Environmental Monitoring Network/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Select monitoring station Delhi \(ITO\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Select monitoring station Mumbai \(BKC\)/i)).toBeInTheDocument();
  });

  it("calls onSelectStation when pin is clicked", () => {
    const handleSelect = vi.fn();
    render(
      <StationMap
        stations={mockStations}
        selectedStationId="cpcb_delhi_ito"
        onSelectStation={handleSelect}
      />
    );
    const pin = screen.getByLabelText(/Select monitoring station Mumbai \(BKC\)/i);
    fireEvent.click(pin);
    expect(handleSelect).toHaveBeenCalledWith(mockStations[1]);
  });
});
