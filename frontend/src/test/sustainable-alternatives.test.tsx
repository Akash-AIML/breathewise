import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { SustainableAlternativesView } from "@/components/sustainability/sustainable-alternatives";
import { HouseholdProfile, SustainableAlternative } from "@/types/recommendations";

const SAMPLE_ALTERNATIVES: SustainableAlternative[] = [
  {
    mode: "Electric Metro / Rail",
    emission_factor_g_co2_per_km: 14,
    estimated_emission_reduction_pct: 91,
    personal_exposure_mitigation: "Filtered carriages cut PM2.5 by 50–70%.",
    condition_dependent_note: null,
  },
];

const SAMPLE_PROFILE: HouseholdProfile = {
  has_children: true,
  has_elderly: false,
  has_respiratory_sensitivity: true,
  has_cardiovascular_sensitivity: false,
  occupation_type: "indoor",
  commute_method: "car_ac",
  exercise_routine: "none",
  indoor_ventilation: "natural",
  has_air_purifier: false,
  home_area_sqft: 650,
};

describe("SustainableAlternativesView", () => {
  it("calculates direct monthly and annual CO2 savings for user's commute", () => {
    render(
      <SustainableAlternativesView
        alternatives={SAMPLE_ALTERNATIVES}
        profile={SAMPLE_PROFILE}
        currentAqi={310}
        stationName="Delhi (ITO)"
      />
    );

    expect(screen.getByText(/Direct Impact of Your Commute Choice/i)).toBeInTheDocument();
    // Solo car (150) -> Electric Metro (14) = 136 g/km * 16 km * 22 days / 1000 = 47.9 kg
    expect(screen.getByText("47.9 kg")).toBeInTheDocument();
    expect(screen.getByText(/Community, RWA & School Smog Action Brief/i)).toBeInTheDocument();
    expect(screen.getByText(/Delhi \(ITO\) • Live AQI 310/i)).toBeInTheDocument();

    // Switching target to Public Bus updates savings deterministically
    fireEvent.click(screen.getByRole("button", { name: "Public CNG/EV Bus" }));
    // (150 - 32) * 16 * 22 / 1000 = 41.5 kg
    expect(screen.getByText("41.5 kg")).toBeInTheDocument();
  });
});
