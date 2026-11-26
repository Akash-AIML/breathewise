import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";

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
    expect(
      (navigator.geolocation.getCurrentPosition as ReturnType<typeof vi.fn>).mock.calls[0][2]
    ).toEqual(
      expect.objectContaining({ enableHighAccuracy: true, maximumAge: 0, timeout: 10000 })
    );
  });

  it("shows the browser-reported accuracy alongside device coordinates", async () => {
    setGeolocation(28.6289, 77.2407, 35);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    expect(
      await screen.findByText(/device-reported accuracy: ±35 m/i)
    ).toBeInTheDocument();
  });

  it("rejects a city-sized laptop fix instead of calling it exact", async () => {
    setGeolocation(40.7128, -74.006, 25_000);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Use My Location/i }));

    expect(
      await screen.findByText(/approximate location \(40\.7128, -74\.0060\).*±25000 m accuracy/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/not treated as your exact location/i)).toBeInTheDocument();
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
    expect(urls.some((url) => url.includes("lat=40.7128"))).toBe(false);
    expect(screen.getAllByText(/Delhi \(ITO\)/i).length).toBeGreaterThan(0);
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
});
