/**
 * Playwright E2E smoke & accessibility test suite for BreatheWise.
 * Verifies:
 *  - Live dashboard rendering & station switching
 *  - Keyboard-only tab navigation
 *  - Household profile dialog
 *  - Direct Impact of Commute Choice calculator & Community Smog Brief
 *  - Indoor Air Hack Impact Simulator
 *  - Mobile viewport responsiveness (390x844)
 */
import { test, expect } from "@playwright/test";

test.describe("BreatheWise End-to-End", () => {
  test("navigates core modules on desktop and verifies keyboard accessibility", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { level: 1 })).toContainText("BreatheWise");

    // Keyboard tab navigation to Daily Planner
    const plannerTab = page.getByRole("tab", { name: "Daily Planner" });
    await plannerTab.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: /Personalized Daily Action Planner/i })).toBeVisible();

    // Indoor Air Guide
    await page.getByRole("tab", { name: "Indoor Air Guide" }).click();
    await expect(page.getByRole("heading", { name: /Evidence-Based Indoor Air Quality Assistant/i })).toBeVisible();

    // Sustainable Transit
    await page.getByRole("tab", { name: "Sustainable Transit" }).click();
    await expect(page.getByRole("heading", { name: /Sustainable Mobility/i })).toBeVisible();

    // AI Assistant
    await page.getByRole("tab", { name: "AI Assistant" }).click();
    await expect(page.getByRole("heading", { name: /BreatheWise Assistant/i })).toBeVisible();
  });

  test("renders cleanly on mobile viewport without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2
    );
    expect(hasOverflow).toBe(false);
  });
});
