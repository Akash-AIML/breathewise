import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { HistoricalTrendChart } from "@/components/dashboard/historical-trend-chart";
import { HourlyTrendPoint } from "@/types/observation";

const mockHourlyData: HourlyTrendPoint[] = [
  {
    time: "2026-11-24T10:00:00Z",
    aqi: 145,
    pm2_5: 65.0,
    pm10: 120.0,
    category: "Moderate",
  },
  {
    time: "2026-11-24T11:00:00Z",
    aqi: 160,
    pm2_5: 75.0,
    pm10: 140.0,
    category: "Moderate",
  },
];

describe("HistoricalTrendChart Component", () => {
  it("renders station title and metric selector", () => {
    render(<HistoricalTrendChart data={mockHourlyData} stationName="Delhi (ITO)" />);
    expect(screen.getByText(/24-Hour Observation Trend — Delhi \(ITO\)/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AQI" })).toBeInTheDocument();
  });

  it("toggles accessible table view on button click", () => {
    render(<HistoricalTrendChart data={mockHourlyData} stationName="Delhi (ITO)" />);
    const tableToggleBtn = screen.getByLabelText("Show accessible data table view");
    fireEvent.click(tableToggleBtn);

    // Should now show table view with AQI values
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("145")).toBeInTheDocument();
    expect(screen.getByText("160")).toBeInTheDocument();
  });

  it("renders missing trend values as an em dash rather than zero", () => {
    render(
      <HistoricalTrendChart
        data={[{ time: "2026-11-24T12:00:00Z", aqi: null, pm2_5: null, pm10: 42 }]}
        stationName="Delhi (ITO)"
        sourceLabel="openmeteo_cams"
      />
    );
    fireEvent.click(screen.getByLabelText("Show accessible data table view"));
    const row = screen.getByRole("table").querySelector("tbody tr") as HTMLTableRowElement;
    expect(row).toBeTruthy();
    expect(row.querySelectorAll("td")[1]).toHaveTextContent("—");
    expect(row.querySelectorAll("td")[2]).toHaveTextContent("—");
    expect(row.querySelectorAll("td")[3]).toHaveTextContent("42");
    expect(screen.getByText(/openmeteo_cams/)).toBeInTheDocument();
  });

  it("handles empty data gracefully", () => {
    render(<HistoricalTrendChart data={[]} stationName="Delhi (ITO)" />);
    expect(screen.getByText(/No historical hourly records/i)).toBeInTheDocument();
  });
});

