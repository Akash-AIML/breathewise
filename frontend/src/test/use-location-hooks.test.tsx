import { act, renderHook, waitFor } from "@testing-library/react";
import { type FormEvent, useRef, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MapStation } from "@/components/dashboard/station-map";
import { useLocationSearch } from "@/components/dashboard/location/use-location-search";
import { useManualCoordinates } from "@/components/dashboard/location/use-manual-coordinates";
import { ExactCoordinates } from "@/components/dashboard/location/saved-coordinates";
import { GeocodedLocation, searchLocations } from "@/lib/api";

vi.mock("@/lib/api", () => ({ searchLocations: vi.fn() }));

const searchLocationsMock = vi.mocked(searchLocations);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const defaultStation: MapStation = {
  name: "Delhi (ITO)",
  station_id: "cpcb_delhi_ito",
  city: "Delhi",
  state: "Delhi",
  lat: 28.6289,
  lon: 77.2407,
};

function useLocationHooks() {
  const requestRef = useRef(0);
  const [geoStatus, setGeoStatus] = useState<string | null>(null);
  const [locationLabel, setLocationLabel] = useState<string | null>(null);
  const [selectedStation, setSelectedStation] = useState<MapStation>(defaultStation);
  const [savedCoordinates, setSavedCoordinates] = useState<ExactCoordinates | null>(null);
  const search = useLocationSearch({ requestRef, setGeoStatus, setLocationLabel, setSelectedStation });
  const manual = useManualCoordinates({
    initialManualCoordinates: "",
    requestRef,
    setSavedCoordinates,
    setGeoStatus,
    setLocationLabel,
    setLocationResults: search.setLocationResults,
    setSelectedStation,
  });
  return { requestRef, geoStatus, locationLabel, selectedStation, savedCoordinates, search, manual };
}

function formEvent() {
  return { preventDefault: vi.fn() } as unknown as FormEvent<HTMLFormElement>;
}

function place(id: number, name: string): GeocodedLocation {
  return { id, name, latitude: 28.6 + id, longitude: 77.2 + id, admin1: "Delhi", country: "India" };
}

describe("location search generations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("ignores a stale successful search after a newer search", async () => {
    const stale = deferred<GeocodedLocation[]>();
    const fresh = deferred<GeocodedLocation[]>();
    searchLocationsMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);
    const { result } = renderHook(() => useLocationHooks());

    act(() => result.current.search.setLocationQuery("Patna"));
    act(() => void result.current.search.handleLocationSearch(formEvent()));
    await waitFor(() => expect(searchLocationsMock).toHaveBeenCalledTimes(1));
    act(() => result.current.search.setLocationQuery("Pune"));
    act(() => void result.current.search.handleLocationSearch(formEvent()));
    await waitFor(() => expect(searchLocationsMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.resolve([place(2, "Pune")]);
      await fresh.promise;
    });
    await waitFor(() => expect(result.current.search.locationResults[0]?.name).toBe("Pune"));

    await act(async () => {
      stale.resolve([place(1, "Patna")]);
      await stale.promise;
    });
    expect(result.current.search.locationResults.map((item) => item.name)).toEqual(["Pune"]);
    expect(result.current.geoStatus).toContain("1 exact coordinate match(es) found.");
    expect(result.current.search.isSearchingLocation).toBe(false);
  });

  it("ignores a stale search failure after a newer search", async () => {
    const stale = deferred<GeocodedLocation[]>();
    const fresh = deferred<GeocodedLocation[]>();
    searchLocationsMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);
    const { result } = renderHook(() => useLocationHooks());

    act(() => result.current.search.setLocationQuery("Patna"));
    act(() => void result.current.search.handleLocationSearch(formEvent()));
    await waitFor(() => expect(searchLocationsMock).toHaveBeenCalledTimes(1));
    act(() => result.current.search.setLocationQuery("Pune"));
    act(() => void result.current.search.handleLocationSearch(formEvent()));
    await waitFor(() => expect(searchLocationsMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.resolve([place(2, "Pune")]);
      await fresh.promise;
    });
    await waitFor(() => expect(result.current.search.locationResults[0]?.name).toBe("Pune"));

    await act(async () => {
      stale.reject(new Error("stale search failure"));
      await stale.promise.catch(() => undefined);
    });
    expect(result.current.geoStatus).toContain("1 exact coordinate match(es) found.");
    expect(result.current.geoStatus).not.toContain("stale search failure");
    expect(result.current.search.locationResults.map((item) => item.name)).toEqual(["Pune"]);
    expect(result.current.search.isSearchingLocation).toBe(false);
  });

  it("ignores a pending search after manual coordinates are applied", async () => {
    const pending = deferred<GeocodedLocation[]>();
    searchLocationsMock.mockReturnValueOnce(pending.promise);
    const { result } = renderHook(() => useLocationHooks());

    act(() => result.current.search.setLocationQuery("Patna"));
    act(() => void result.current.search.handleLocationSearch(formEvent()));
    await waitFor(() => expect(searchLocationsMock).toHaveBeenCalledTimes(1));
    act(() => result.current.manual.setManualCoordinates("12.9716, 77.5946"));
    act(() => void result.current.manual.handleManualCoordinates(formEvent()));
    expect(result.current.geoStatus).toMatch(/Using manually entered coordinates/);

    await act(async () => {
      pending.resolve([place(1, "Patna")]);
      await pending.promise;
    });
    expect(result.current.search.locationResults).toEqual([]);
    expect(result.current.geoStatus).toMatch(/Using manually entered coordinates/);
    expect(result.current.selectedStation.lat).toBe(12.9716);
    expect(result.current.search.isSearchingLocation).toBe(false);
  });

  it("invalidates pending searches when saved coordinates are cleared", async () => {
    const pending = deferred<GeocodedLocation[]>();
    searchLocationsMock.mockReturnValueOnce(pending.promise);
    const { result } = renderHook(() => useLocationHooks());

    act(() => result.current.search.setLocationQuery("Patna"));
    act(() => void result.current.search.handleLocationSearch(formEvent()));
    await waitFor(() => expect(searchLocationsMock).toHaveBeenCalledTimes(1));
    const generation = result.current.requestRef.current;
    act(() => result.current.manual.clearSavedCoordinates());
    expect(result.current.requestRef.current).toBe(generation + 1);

    await act(async () => {
      pending.resolve([place(1, "Patna")]);
      await pending.promise;
    });
    expect(result.current.search.locationResults).toEqual([]);
    expect(result.current.geoStatus).toMatch(/Saved coordinates cleared/);
    expect(result.current.search.isSearchingLocation).toBe(false);
  });
});
