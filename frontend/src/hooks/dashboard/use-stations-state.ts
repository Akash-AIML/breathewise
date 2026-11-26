"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { fetchStations } from "@/lib/api";
import { StationsApiResponse, StationMetadata } from "@/types/observation";

export interface StationsState {
  liveStations: MapStation[];
  stationsSource: string | null;
  retryStationLookup: () => void;
}

const LIVE_CPCB_SOURCE = "CPCB/data.gov.in";

function isLiveCpcb(result: StationsApiResponse): boolean {
  return result.message?.includes(LIVE_CPCB_SOURCE) ?? false;
}

function toMapStation(station: StationMetadata): MapStation {
  return {
    name: station.station_name,
    station_id: station.station_id,
    city: station.city,
    state: station.state,
    lat: station.latitude,
    lon: station.longitude,
  };
}

/** Only real, finite CPCB coordinates become map markers. */
function liveMapStations(result: StationsApiResponse): MapStation[] {
  if (!isLiveCpcb(result)) return [];
  return result.data
    .filter((station) => Number.isFinite(station.latitude) && Number.isFinite(station.longitude))
    .map(toMapStation);
}

/** Live monitoring stations, or an honest empty state with a retry action. */
export function useStationsState(): StationsState {
  const [liveStations, setLiveStations] = useState<MapStation[]>([]);
  const [stationsSource, setStationsSource] = useState<string | null>(null);
  // One generation counter covers the initial request, every retry and unmount.
  const requestRef = useRef(0);

  const applyStations = useCallback((requestId: number, result: StationsApiResponse) => {
    if (requestId !== requestRef.current) return;
    setStationsSource(isLiveCpcb(result) ? LIVE_CPCB_SOURCE : result.message ?? "source unavailable");
    setLiveStations(liveMapStations(result));
  }, []);

  const reportUnavailable = useCallback((requestId: number) => {
    if (requestId !== requestRef.current) return;
    setStationsSource("source unavailable");
    setLiveStations([]);
  }, []);

  const requestStations = useCallback(() => {
    const requestId = ++requestRef.current;
    void fetchStations()
      .then((result) => applyStations(requestId, result))
      .catch(() => reportUnavailable(requestId));
  }, [applyStations, reportUnavailable]);

  useEffect(() => {
    requestStations();
    return () => {
      // Invalidate any in-flight lookup so it cannot settle after unmount.
      requestRef.current += 1;
    };
  }, [requestStations]);

  const retryStationLookup = useCallback(() => requestStations(), [requestStations]);

  return { liveStations, stationsSource, retryStationLookup };
}
