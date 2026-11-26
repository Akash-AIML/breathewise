import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";
import { SAVED_COORDINATES_KEY } from "@/components/dashboard/use-location-state";

function setGeolocation(latitude: number, longitude: number, accuracy?: number) {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((success: PositionCallback) => {
        success({ coords: { latitude, longitude, accuracy } } as GeolocationPosition);
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
    window.localStorage.clear();
    mockFetch(null);
    setGeolocation(28.6289, 77.2407, 35);
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
    const options = (navigator.geolocation.getCurrentPosition as ReturnType<typeof vi.fn>).mock
      .calls[0][2] as PositionOptions;
    expect(options).toEqual(expect.objectContaining({ enableHighAccuracy: true, timeout: 10000 }));
    expect(options).not.toHaveProperty("maximumAge");
  });

  it("shows the browser-reported accuracy alongside device coordinates", async () => {
    setGeolocation(28.6289, 77.2407, 35);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    expect(
      await screen.findByText(/device-reported accuracy: ±35 m/i)
    ).toBeInTheDocument();
  });

  it("uses a city-sized laptop fix but labels it as approximate", async () => {
    setGeolocation(40.7128, -74.006, 25_000);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    const status = await screen.findByRole("status");
    expect(status.textContent).toMatch(
      /Using browser coordinates \(40\.7128, -74\.0060\).*±25000 m\./i
    );
    expect(status.textContent).toMatch(/wi[-‑]fi\/ip estimate/i);
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
    expect(urls.some((url) => url.includes("lat=40.7128") && url.includes("lon=-74.006"))).toBe(true);
    expect(screen.getByText(/Coordinates: 40\.7128°N, 74\.0060°W/i)).toBeInTheDocument();
  });

  it("uses manually entered coordinates when the laptop browser is wrong", async () => {
    render(<HomePage />);
    fireEvent.change(screen.getByLabelText(/exact coordinates \(lat, lon\)/i), {
      target: { value: "12.9716, 77.5946" },
    });
    fireEvent.click(screen.getByRole("button", { name: /use coordinates/i }));

    await waitFor(() => {
      const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("lat=12.9716") && url.includes("lon=77.5946"))).toBe(true);
    });
    expect(
      screen.getByText(/using manually entered coordinates \(12\.9716, 77\.5946\)/i)
    ).toBeInTheDocument();
    expect(window.localStorage.getItem(SAVED_COORDINATES_KEY)).toContain("12.9716");
  });

  it("rejects manual coordinates outside valid latitude and longitude ranges", async () => {
    render(<HomePage />);
    fireEvent.change(screen.getByLabelText(/exact coordinates \(lat, lon\)/i), {
      target: { value: "99.0000, 77.5946" },
    });
    fireEvent.click(screen.getByRole("button", { name: /use coordinates/i }));

    expect(await screen.findByText(/latitude must be a number between -90 and 90/i)).toBeInTheDocument();
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
    expect(urls.some((url) => url.includes("lat=99"))).toBe(false);
  });

  it("rejects invalid device coordinates instead of selecting them", async () => {
    setGeolocation(Number.NaN, Number.NaN, 35);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    expect(
      await screen.findByText(/device returned invalid coordinates/i)
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Delhi \(ITO\)/i).length).toBeGreaterThan(0);
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

  it("keeps saved coordinates when the browser reports a distant fix", async () => {
    window.localStorage.setItem(SAVED_COORDINATES_KEY, "11.4953, 77.2793");
    setGeolocation(11.2448, 75.7721, 1);
    render(<HomePage />);

    expect(
      await screen.findByText(/Using saved coordinates \(11\.4953, 77\.2793\)/i)
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    expect(
      await screen.findByText(/That is \d+ km from your saved coordinates.*Keeping saved coordinates/i)
    ).toBeInTheDocument();
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
    expect(urls.some((url) => url.includes("lat=11.2448"))).toBe(false);
    expect(screen.getByText(/Coordinates: 11\.4953°N, 77\.2793°E/i)).toBeInTheDocument();
  });

  it("clears saved coordinates on request", async () => {
    window.localStorage.setItem(SAVED_COORDINATES_KEY, "11.4953, 77.2793");
    render(<HomePage />);

    expect(
      await screen.findByText(/Using saved coordinates \(11\.4953, 77\.2793\)/i)
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Clear saved coordinates/i }));

    expect(await screen.findByText(/Saved coordinates cleared/i)).toBeInTheDocument();
    expect(window.localStorage.getItem(SAVED_COORDINATES_KEY)).toBeNull();
  });
});
