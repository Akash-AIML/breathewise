import { afterEach, describe, expect, it, vi } from "vitest";
import {
  initialLocationSnapshot,
  readSavedCoordinates,
  removeSavedCoordinates,
  SAVED_COORDINATES_KEY,
  storeSavedCoordinates,
} from "@/components/dashboard/location/saved-coordinates";

describe("saved coordinate storage failures", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("falls back to defaults when reading storage throws", () => {
    window.localStorage.setItem(SAVED_COORDINATES_KEY, "28.6289, 77.2407");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });

    expect(readSavedCoordinates()).toBeNull();
    expect(initialLocationSnapshot().geoStatus).toBeNull();
    expect(initialLocationSnapshot().selectedStation.station_id).toBe("cpcb_delhi_ito");
  });

  it("reports a failed write instead of throwing", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    expect(storeSavedCoordinates({ lat: 28.6289, lon: 77.2407 })).toBe(false);
  });

  it("reports a failed removal instead of throwing", () => {
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });

    expect(removeSavedCoordinates()).toBe(false);
  });
});
