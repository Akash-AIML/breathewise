import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HouseholdProfileDialog } from "@/components/profile/household-profile-dialog";
import { HouseholdProfile } from "@/types/recommendations";

const initialProfile: HouseholdProfile = {
  has_children: false,
  has_elderly: false,
  has_respiratory_sensitivity: false,
  has_cardiovascular_sensitivity: false,
  occupation_type: "indoor",
  commute_method: "metro_train",
  exercise_routine: "none",
  indoor_ventilation: "natural",
  has_air_purifier: false,
  home_area_sqft: 600,
};

describe("HouseholdProfileDialog Component", () => {
  it("renders profile dialog when open", () => {
    render(
      <HouseholdProfileDialog
        isOpen={true}
        onClose={vi.fn()}
        profile={initialProfile}
        onSave={vi.fn()}
      />
    );
    expect(screen.getByText("Household Profile & Vulnerabilities")).toBeInTheDocument();
    expect(screen.getByText("Children under 12 yrs")).toBeInTheDocument();
    expect(screen.getByText("Asthma / Bronchitis / Allergy")).toBeInTheDocument();
  });

  it("calls onSave with updated demographics upon submission", () => {
    const handleSave = vi.fn();
    render(
      <HouseholdProfileDialog
        isOpen={true}
        onClose={vi.fn()}
        profile={initialProfile}
        onSave={handleSave}
      />
    );

    // Toggle children checkbox
    const childrenCheckbox = screen.getByLabelText("Children under 12 yrs");
    fireEvent.click(childrenCheckbox);

    // Submit form
    const submitBtn = screen.getByRole("button", { name: "Save Household Profile" });
    fireEvent.click(submitBtn);

    expect(handleSave).toHaveBeenCalledTimes(1);
    expect(handleSave).toHaveBeenCalledWith(
      expect.objectContaining({
        has_children: true,
      })
    );
  });
});

