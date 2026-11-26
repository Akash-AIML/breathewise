import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStationsState } from "@/hooks/dashboard/use-stations-state";
import { fetchStations } from "@/lib/api";
import { StationsApiResponse } from "@/types/observation";

vi.mock("@/lib/api", () => ({ fetchStations: vi.fn() }));

const fetchStationsMock = vi.mocked(fetchStations);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function liveResult(id: string): StationsApiResponse {
  return {
    success: true,
    count: 1,
    message: "Station metadata source: CPCB/data.gov.in",
    data: [
      {
        station_id: id,
        station_name: id,
        city: "Delhi",
        state: "Delhi",
        latitude: 28.6289,
        longitude: 77.2407,
      },
    ],
  };
}

describe("useStationsState request generations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ignores a stale failure that settles after a newer success", async () => {
    const stale = deferred<StationsApiResponse>();
    const fresh = deferred<StationsApiResponse>();
    fetchStationsMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);

    const { result } = renderHook(() => useStationsState());
    await waitFor(() => expect(fetchStationsMock).toHaveBeenCalledTimes(1));
    act(() => result.current.retryStationLookup());
    await waitFor(() => expect(fetchStationsMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.resolve(liveResult("newer-station"));
      await fresh.promise;
    });
    await waitFor(() => expect(result.current.liveStations[0]?.station_id).toBe("newer-station"));

    await act(async () => {
      stale.reject(new Error("stale network failure"));
      await stale.promise.catch(() => undefined);
    });

    expect(result.current.stationsSource).toBe("CPCB/data.gov.in");
    expect(result.current.liveStations.map((station) => station.station_id)).toEqual(["newer-station"]);
  });

  it("ignores a stale success that settles after a newer failure", async () => {
    const stale = deferred<StationsApiResponse>();
    const fresh = deferred<StationsApiResponse>();
    fetchStationsMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);

    const { result } = renderHook(() => useStationsState());
    await waitFor(() => expect(fetchStationsMock).toHaveBeenCalledTimes(1));
    act(() => result.current.retryStationLookup());
    await waitFor(() => expect(fetchStationsMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.reject(new Error("newer network failure"));
      await fresh.promise.catch(() => undefined);
    });
    await waitFor(() => expect(result.current.stationsSource).toBe("source unavailable"));

    await act(async () => {
      stale.resolve(liveResult("stale-station"));
      await stale.promise;
    });

    expect(result.current.stationsSource).toBe("source unavailable");
    expect(result.current.liveStations).toEqual([]);
  });
});
