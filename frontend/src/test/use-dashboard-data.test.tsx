import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useDashboardData } from "@/hooks/dashboard/use-dashboard-data";
import { fetchAirQuality, fetchPersonalizedPlan } from "@/lib/api";
import { MapStation } from "@/components/dashboard/station-map";
import { AirQualityApiResponse } from "@/types/observation";
import { HouseholdProfile, PersonalizedPlan } from "@/types/recommendations";

vi.mock("@/lib/api", () => ({
  fetchAirQuality: vi.fn(),
  fetchPersonalizedPlan: vi.fn(),
}));

const fetchAirQualityMock = vi.mocked(fetchAirQuality);
const fetchPersonalizedPlanMock = vi.mocked(fetchPersonalizedPlan);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const stationA: MapStation = {
  name: "Station A",
  station_id: "a",
  city: "Delhi",
  state: "Delhi",
  lat: 28.6289,
  lon: 77.2407,
};
const stationB: MapStation = { ...stationA, name: "Station B", station_id: "b", lat: 12.9716, lon: 77.5946 };
const baseProfile: HouseholdProfile = {
  has_children: false,
  has_elderly: false,
  has_respiratory_sensitivity: false,
  has_cardiovascular_sensitivity: false,
  occupation_type: "indoor",
  commute_method: "work_from_home",
  exercise_routine: "none",
  indoor_ventilation: "natural",
  has_air_purifier: false,
};

function observation(provider: string): AirQualityApiResponse {
  return { success: true, data: { provider } } as unknown as AirQualityApiResponse;
}

function plan(generatedAt: string): PersonalizedPlan {
  return { generated_at: generatedAt } as unknown as PersonalizedPlan;
}

type HookProps = { station: MapStation; profile: HouseholdProfile };

describe("useDashboardData request generations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ignores a stale observation success after a newer request", async () => {
    const stale = deferred<AirQualityApiResponse>();
    const fresh = deferred<AirQualityApiResponse>();
    fetchAirQualityMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);
    fetchPersonalizedPlanMock.mockReturnValue(new Promise<PersonalizedPlan>(() => {}));

    const { result, rerender } = renderHook(
      ({ station, profile }: HookProps) => useDashboardData({ selectedStation: station, profile }),
      { initialProps: { station: stationA, profile: baseProfile } }
    );
    await waitFor(() => expect(fetchAirQualityMock).toHaveBeenCalledTimes(1));
    rerender({ station: stationB, profile: baseProfile });
    await waitFor(() => expect(fetchAirQualityMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.resolve(observation("fresh"));
      await fresh.promise;
    });
    await waitFor(() => expect(result.current.observation?.provider).toBe("fresh"));

    await act(async () => {
      stale.resolve(observation("stale"));
      await stale.promise;
    });
    expect(result.current.observation?.provider).toBe("fresh");
    expect(result.current.error).toBeNull();
  });

  it("ignores a stale observation failure after a newer request", async () => {
    const stale = deferred<AirQualityApiResponse>();
    const fresh = deferred<AirQualityApiResponse>();
    fetchAirQualityMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);
    fetchPersonalizedPlanMock.mockReturnValue(new Promise<PersonalizedPlan>(() => {}));

    const { result, rerender } = renderHook(
      ({ station, profile }: HookProps) => useDashboardData({ selectedStation: station, profile }),
      { initialProps: { station: stationA, profile: baseProfile } }
    );
    await waitFor(() => expect(fetchAirQualityMock).toHaveBeenCalledTimes(1));
    rerender({ station: stationB, profile: baseProfile });
    await waitFor(() => expect(fetchAirQualityMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.resolve(observation("fresh"));
      await fresh.promise;
    });
    await waitFor(() => expect(result.current.observation?.provider).toBe("fresh"));

    await act(async () => {
      stale.reject(new Error("stale service failure"));
      await stale.promise.catch(() => undefined);
    });
    expect(result.current.observation?.provider).toBe("fresh");
    expect(result.current.error).toBeNull();
  });

  it("ignores a stale plan response after a newer coordinate/profile request", async () => {
    const stale = deferred<PersonalizedPlan>();
    const fresh = deferred<PersonalizedPlan>();
    fetchPersonalizedPlanMock.mockReturnValueOnce(stale.promise).mockReturnValueOnce(fresh.promise);
    fetchAirQualityMock.mockReturnValue(new Promise<AirQualityApiResponse>(() => {}));
    const changedProfile = { ...baseProfile, has_children: true };

    const { result, rerender } = renderHook(
      ({ station, profile }: HookProps) => useDashboardData({ selectedStation: station, profile }),
      { initialProps: { station: stationA, profile: baseProfile } }
    );
    await waitFor(() => expect(fetchPersonalizedPlanMock).toHaveBeenCalledTimes(1));
    rerender({ station: stationB, profile: changedProfile });
    await waitFor(() => expect(fetchPersonalizedPlanMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      fresh.resolve(plan("fresh"));
      await fresh.promise;
    });
    await waitFor(() => expect(result.current.plan?.generated_at).toBe("fresh"));

    await act(async () => {
      stale.resolve(plan("stale"));
      await stale.promise;
    });
    expect(result.current.plan?.generated_at).toBe("fresh");
    expect(result.current.isPlanLoading).toBe(false);
  });
});
