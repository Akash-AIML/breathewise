import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DailyPlanner } from "@/components/planner/daily-planner";
import { PersonalizedPlan } from "@/types/recommendations";

const mockPlan: PersonalizedPlan = {
  environmental_assessment: {
    risk_level: "severe",
    aqi: 420,
    category: "Severe",
    dominant_pollutant: "PM2.5",
    data_quality: "verified",
    confidence: 0.95,
    is_stale: false,
    assessment_summary: "Severe air emergency test.",
  },
  household_profile: {
    has_children: true,
    has_elderly: false,
    has_respiratory_sensitivity: true,
    has_cardiovascular_sensitivity: false,
    occupation_type: "indoor",
    commute_method: "bus",
    exercise_routine: "morning_outdoor",
    indoor_ventilation: "natural",
    has_air_purifier: true,
    home_area_sqft: 600,
  },
  morning_recommendations: [
    {
      id: "rec_1",
      category: "planner",
      title: "Shift Morning Workouts Indoors",
      time_of_day: "morning",
      action: "Avoid outdoor jogging before 9:00 AM.",
      priority: "critical",
      reason: "Cool morning inversion layer traps exhaust.",
      supporting_evidence: "CPCB diurnal profiles.",
      expected_impact: "positive_exposure_reduction",
    },
  ],
  afternoon_recommendations: [
    {
      id: "rec_2",
      category: "planner",
      title: "Midday Boundary Layer Ventilation Window",
      time_of_day: "afternoon",
      action: "Open windows for 10 minutes between 1 PM and 3 PM.",
      priority: "medium",
      reason: "Solar heating expands boundary layer.",
      supporting_evidence: "Atmospheric mixing physics.",
      expected_impact: "positive_exposure_reduction",
    },
  ],
  evening_recommendations: [
    {
      id: "rec_3",
      category: "indoor",
      title: "Pre-Sleep Bedroom Air Purifier Boost",
      time_of_day: "evening",
      action: "Turn air purifier to high speed 45 mins before bedtime.",
      priority: "high",
      reason: "Cleans bedroom air before sleep.",
      supporting_evidence: "Infiltration sleep trials.",
      expected_impact: "positive_exposure_reduction",
    },
  ],
  indoor_guidance: {
    hepa_sizing_cadr_m3_hr: 697,
    hepa_sizing_explanation: "CADR explanation",
    filter_maintenance_tips: ["Vacuum pre-filter"],
    ventilation_advice: "Ventilation advice",
    cooking_smoke_precautions: ["Exhaust on for tadka"],
    practical_low_cost_precautions: ["Wet mopping"],
    houseplant_scientific_disclaimer: "Plants cannot purify real rooms",
  },
  sustainable_alternatives: [],
  generated_at: "2026-11-24T12:00:00Z",
};

describe("DailyPlanner Component", () => {
  it("renders all three diurnal protocol slots", () => {
    render(<DailyPlanner plan={mockPlan} isLoading={false} />);
    expect(screen.getByText(/Morning Protocol/i)).toBeInTheDocument();
    expect(screen.getByText(/Midday Protocol/i)).toBeInTheDocument();
    expect(screen.getByText(/Evening & Night/i)).toBeInTheDocument();
  });

  it("renders recommendation details and priorities", () => {
    render(<DailyPlanner plan={mockPlan} isLoading={false} />);
    expect(screen.getByText("Shift Morning Workouts Indoors")).toBeInTheDocument();
    expect(screen.getByText(/CRITICAL Priority/i)).toBeInTheDocument();
  });

  it("expands evidence accordion on click", () => {
    render(<DailyPlanner plan={mockPlan} isLoading={false} />);
    const accordionBtn = screen.getAllByText("Scientific Evidence & Guidelines")[0];
    fireEvent.click(accordionBtn);
    expect(screen.getByText(/CPCB diurnal profiles/i)).toBeInTheDocument();
  });
});

