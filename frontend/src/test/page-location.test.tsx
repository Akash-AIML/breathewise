import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";

function setGeolocation(latitude: number, longitude: number) {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((success: PositionCallback) => {
        success({ coords: { latitude, longitude } } as GeolocationPosition);
      }),
    },
  });
}

function mockFetch(reversePlace: unknown) {
  global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/locations/reverse")) {
      return { ok: true, json: async () => ({ place: reversePlace }) } as Response;
    }
    if (url.includes("/air-quality")) {
      return {
        ok: true,
        json: async () => ({ success: false, message: "No live observation in this test." }),
      } as Response;
    }
    return { ok: false, status: 503, json: async () => ({}) } as Response;
  });
}

describe("HomePage location handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch(null);
    setGeolocation(28.6289, 77.2407);
  });

  it("uses exact device coordinates instead of snapping to a hardcoded city", async () => {
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes("lat=28.6289") && url.includes("lon=77.2407"))).toBe(true);
    });
    expect(screen.queryByText(/Nearest Station/i)).not.toBeInTheDocument();
    expect(screen.getByText(/My Exact Location/i)).toBeInTheDocument();
  });

  it("shows the reverse-geocoded tier-2 locality, not a distant popular city", async () => {
    setGeolocation(11.4953, 77.2793);
    mockFetch({
      name: "Sathyamangalam",
      state: "Tamil Nadu",
      country: "India",
      display_name: "Sathyamangalam, Erode, Tamil Nadu, India",
      source: "OpenStreetMap Nominatim",
    });
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Using exact device coordinates \(11\.4953, 77\.2793\).*Located in Sathyamangalam, Tamil Nadu \(OpenStreetMap\)/i)
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Coordinates: 11\.4953°N, 77\.2793°E/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Sathyamangalam, Tamil Nadu \(OpenStreetMap\)/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/near Bengaluru/i)).not.toBeInTheDocument();
  });

  it("does not invent a nearby city when no map place is available", async () => {
    setGeolocation(11.4953, 77.2793);
    mockFetch(null);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Using exact device coordinates \(11\.4953, 77\.2793\).*No mapped place name is available/i)
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/near Bengaluru/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Nearest mapped station: Bengaluru/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Coordinates: 11\.4953°N, 77\.2793°E/i)).toBeInTheDocument();
  });

  it("uses the mapped station label only when genuinely nearby", async () => {
    mockFetch(null);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Using exact device coordinates \(28\.6289, 77\.2407\).*Nearest mapped station: Delhi \(0\.0 km away\)/i)
      ).toBeInTheDocument();
    });
  });
});
