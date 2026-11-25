import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import HomePage from "@/app/page";
import { HouseholdProfileDialog } from "@/components/profile/household-profile-dialog";
import { HouseholdProfile } from "@/types/recommendations";

// jsdom does not implement real layout or colour computation, so axe cannot
// evaluate contrast here. Every other applicable axe rule is left enabled.
const jsdomAxeOptions = {
  rules: {
    "color-contrast": { enabled: false },
  },
};

const profile: HouseholdProfile = {
  has_children: true,
  has_elderly: false,
  has_respiratory_sensitivity: true,
  has_cardiovascular_sensitivity: false,
  occupation_type: "indoor",
  commute_method: "two_wheeler",
  exercise_routine: "morning_outdoor",
  indoor_ventilation: "natural",
  has_air_purifier: false,
  home_area_sqft: 650,
};

// jsdom has no canvas implementation; axe probes canvas for icon-font detection.
// Returning null is the same "no context available" answer a headless DOM gives.
beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext;
});

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ success: true, data: null, message: "No live observation" }),
  } as Response);
});

const auditResults: Record<string, unknown> = {};

afterAll(() => {
  const dir = path.resolve(process.cwd(), "../docs/artifacts");
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    path.join(dir, "axe-results.json"),
    JSON.stringify({ generatedAt: new Date().toISOString(), results: auditResults }, null, 2)
  );
});

describe("axe accessibility audit (jsdom)", () => {
  it("HomePage has no axe violations in the default overview tab", async () => {
    const { container } = render(<HomePage />);
    await waitFor(() => {
      expect(screen.queryByText(/Fetching genuine environmental sensor telemetry/)).toBeNull();
    });

    const results = await axe(container, jsdomAxeOptions);
    auditResults.HomePage = {
      passes: results.passes.length,
      violations: results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => n.target),
      })),
    };
    expect(results).toHaveNoViolations();
  });

  it("HouseholdProfileDialog has no axe violations when open", async () => {
    const { container } = render(
      <HouseholdProfileDialog
        isOpen={true}
        onClose={vi.fn()}
        profile={profile}
        onSave={vi.fn()}
      />
    );

    const results = await axe(container, jsdomAxeOptions);
    auditResults.HouseholdProfileDialog = {
      passes: results.passes.length,
      violations: results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => n.target),
      })),
    };
    expect(results).toHaveNoViolations();
  });
});
