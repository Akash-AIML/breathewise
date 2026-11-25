import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";

describe("HomePage tablist accessibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: null, message: "No live observation" }),
    } as Response);
  });

  it("exposes a labelled tablist with exactly one selected tab", () => {
    render(<HomePage />);
    const tablist = screen.getByRole("tablist", { name: "Dashboard Views" });
    expect(tablist).toBeInTheDocument();
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(8);
    expect(tabs.filter((tab) => tab.getAttribute("aria-selected") === "true")).toHaveLength(1);
    expect(screen.getByRole("tab", { name: /Live Dashboard/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
  });

  it("moves selection and focus with arrow keys", () => {
    render(<HomePage />);
    const overview = screen.getByRole("tab", { name: /Live Dashboard/i });
    const planner = screen.getByRole("tab", { name: /Daily Planner/i });

    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });

    expect(planner).toHaveAttribute("aria-selected", "true");
    expect(planner).toHaveFocus();
    expect(screen.getByRole("tabpanel", { name: /Daily Planner/i })).toBeInTheDocument();
  });

  it("supports Home and End keys", () => {
    render(<HomePage />);
    const first = screen.getByRole("tab", { name: /Live Dashboard/i });
    const last = screen.getByRole("tab", { name: /AI Assistant/i });

    fireEvent.keyDown(first, { key: "End" });
    expect(last).toHaveAttribute("aria-selected", "true");
    expect(last).toHaveFocus();

    fireEvent.keyDown(last, { key: "Home" });
    expect(first).toHaveAttribute("aria-selected", "true");
    expect(first).toHaveFocus();
  });
});
