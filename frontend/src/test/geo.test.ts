import { describe, expect, it } from "vitest";
import { formatCoordinates, haversineDistanceKm, nearestNamedLocation } from "@/lib/geo";

const places = [
  { name: "Delhi (ITO)", city: "Delhi", state: "Delhi", lat: 28.6289, lon: 77.2407 },
  { name: "Chennai (Alandur)", city: "Chennai", state: "Tamil Nadu", lat: 13.0033, lon: 80.2014 },
];

describe("geo helpers", () => {
  it("computes haversine distance between nearby points", () => {
    const distance = haversineDistanceKm(28.6289, 77.2407, 28.6469, 77.316);
    expect(distance).toBeGreaterThan(7);
    expect(distance).toBeLessThan(9);
  });

  it("selects the nearest named place without altering coordinates", () => {
    const result = nearestNamedLocation(28.6322, 77.2422, places);
    expect(result?.point.name).toBe("Delhi (ITO)");
    expect(result?.distanceKm).toBeLessThan(1);
  });

  it("returns null when no valid place exists", () => {
    expect(nearestNamedLocation(0, 0, [])).toBeNull();
  });

  it("formats hemispheres correctly for southern and western coordinates", () => {
    expect(formatCoordinates(-13.5, -80.2)).toBe("13.5000°S, 80.2000°W");
    expect(formatCoordinates(28.6289, 77.2407)).toBe("28.6289°N, 77.2407°E");
  });
});
