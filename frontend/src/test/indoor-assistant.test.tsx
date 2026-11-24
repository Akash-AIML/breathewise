import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { IndoorAssistant } from "@/components/indoor/indoor-assistant";
import { IndoorGuidance } from "@/types/recommendations";

const mockGuidance: IndoorGuidance = {
  hepa_sizing_cadr_m3_hr: 697,
  hepa_sizing_explanation: "For a domestic carpet area of ~600 sq.ft., CADR must be 697 m3/hr.",
  filter_maintenance_tips: [
    "Vacuum pre-filter every 2-3 weeks",
    "Never wash True HEPA filters with water",
  ],
  ventilation_advice: "Seal windows during morning smog inversion.",
  cooking_smoke_precautions: ["Always turn on kitchen chimney before tadka"],
  practical_low_cost_precautions: ["Use wet microfiber mopping over dry sweeping"],
  houseplant_scientific_disclaimer: "Scientific Reality: Ordinary indoor houseplants cannot replace mechanical HEPA filters.",
};

describe("IndoorAssistant Component", () => {
  it("renders CADR sizing calculator and value", () => {
    render(<IndoorAssistant guidance={mockGuidance} />);
    expect(screen.getByText("697")).toBeInTheDocument();
    expect(screen.getByText("m³/hr CADR")).toBeInTheDocument();
  });

  it("renders houseplant scientific reality banner", () => {
    render(<IndoorAssistant guidance={mockGuidance} />);
    expect(screen.getByText(/Scientific Evidence Disclosure: Houseplants vs Air Purifiers/i)).toBeInTheDocument();
    expect(screen.getByText(/cannot replace mechanical HEPA filters/i)).toBeInTheDocument();
  });

  it("renders filter maintenance rules and cooking precautions", () => {
    render(<IndoorAssistant guidance={mockGuidance} />);
    expect(screen.getByText("Never wash True HEPA filters with water")).toBeInTheDocument();
    expect(screen.getByText("Always turn on kitchen chimney before tadka")).toBeInTheDocument();
  });
});
