import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AQIBadge } from "@/components/aqi/aqi-badge";

describe("AQIBadge Component", () => {
  it("renders Good AQI correctly with category and value", () => {
    render(<AQIBadge category="Good" aqi={35} />);
    expect(screen.getByRole("status")).toHaveTextContent("Good • 35 AQI");
    expect(screen.getByLabelText("Air Quality Index 35, Category: Good")).toBeInTheDocument();
  });

  it("renders Moderate AQI correctly", () => {
    render(<AQIBadge category="Moderate" aqi={145} />);
    expect(screen.getByRole("status")).toHaveTextContent("Moderate • 145 AQI");
  });

  it("renders Severe AQI correctly", () => {
    render(<AQIBadge category="Severe" aqi={440} />);
    expect(screen.getByRole("status")).toHaveTextContent("Severe • 440 AQI");
  });

  it("renders Unavailable state when category or aqi is missing", () => {
    render(<AQIBadge category={null} aqi={null} />);
    expect(screen.getByText("AQI Unavailable")).toBeInTheDocument();
  });
});
