import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";

describe("HomePage location handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/air-quality")) {
        return {
          ok: true,
          json: async () => ({ success: false, message: "No live observation in this test." }),
        } as Response;
      }
      return { ok: false, status: 503, json: async () => ({}) } as Response;
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: vi.fn((success: PositionCallback) => {
          success({
            coords: { latitude: 28.6289, longitude: 77.2407 },
          } as GeolocationPosition);
        }),
      },
    });
  });

  it("uses exact device coordinates instead of snapping to a hardcoded city", async () => {
    render(<HomePage />);

    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Using exact device coordinates \(28\.6289, 77\.2407\)/)
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/Nearest Station/i)).not.toBeInTheDocument();
    expect(screen.getByText(/My Exact Location/i)).toBeInTheDocument();

    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes("lat=28.6289") && url.includes("lon=77.2407"))).toBe(true);
    });
  });
});
