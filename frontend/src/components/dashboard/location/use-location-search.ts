"use client";

import {
  type Dispatch,
  type FormEvent,
  type RefObject,
  type SetStateAction,
  useCallback,
  useRef,
  useState,
} from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { GeocodedLocation, searchLocations } from "@/lib/api";

interface LocationSearchDeps {
  requestRef: RefObject<number>;
  setGeoStatus: (status: string | null) => void;
  setLocationLabel: (label: string | null) => void;
  setSelectedStation: Dispatch<SetStateAction<MapStation>>;
}

/** Name search and exact geocoded selection: no hardcoded city snapping. */
export function useLocationSearch({
  requestRef,
  setGeoStatus,
  setLocationLabel,
  setSelectedStation,
}: LocationSearchDeps) {
  const [locationQuery, setLocationQuery] = useState("");
  const [locationResults, setLocationResultsState] = useState<GeocodedLocation[]>([]);
  const [isSearchingLocation, setIsSearchingLocation] = useState(false);
  // Tracks this hook's own searches so a stale completion cannot clear the
  // loading state of a newer search; the shared ref tracks selection changes.
  const searchGenerationRef = useRef(0);

  const handleLocationSearch = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const query = locationQuery.trim();
      if (query.length < 2) {
        setGeoStatus("Enter at least two characters to search for a place.");
        return;
      }
      // A newer search, manual entry, geolocation fix or station selection
      // invalidates this generation via the shared request counter.
      const searchId = ++searchGenerationRef.current;
      const requestId = ++requestRef.current;
      setIsSearchingLocation(true);
      try {
        const results = await searchLocations(query);
        if (searchId !== searchGenerationRef.current || requestId !== requestRef.current) return;
        setLocationResultsState(results);
        setGeoStatus(
          results.length === 0
            ? `No place matched "${locationQuery}". Try a nearby city or use your device location.`
            : `${results.length} exact coordinate match(es) found. Pick one below.`
        );
      } catch (err) {
        if (searchId !== searchGenerationRef.current || requestId !== requestRef.current) return;
        setLocationResultsState([]);
        setGeoStatus(err instanceof Error ? err.message : "Location search failed.");
      } finally {
        if (searchId === searchGenerationRef.current) setIsSearchingLocation(false);
      }
    },
    [locationQuery, requestRef, setGeoStatus]
  );

  const selectGeocodedLocation = useCallback(
    (place: GeocodedLocation) => {
      requestRef.current += 1;
      const region = [place.admin1, place.country].filter(Boolean).join(", ");
      setSelectedStation({
        name: region ? `${place.name}, ${region}` : place.name,
        station_id: `geocode_${place.id}`,
        city: place.name,
        state: place.admin1 ?? "",
        lat: place.latitude,
        lon: place.longitude,
      });
      setGeoStatus(
        `Using exact coordinates for ${place.name} (${place.latitude.toFixed(4)}, ${place.longitude.toFixed(4)}).`
      );
      setLocationLabel(`${place.name}${region ? `, ${region}` : ""}`);
      setLocationResultsState([]);
    },
    [requestRef, setGeoStatus, setLocationLabel, setSelectedStation]
  );

  return {
    locationQuery,
    setLocationQuery,
    locationResults,
    setLocationResults: setLocationResultsState,
    isSearchingLocation,
    handleLocationSearch,
    selectGeocodedLocation,
  };
}
