"use client";

import { type Dispatch, type FormEvent, type SetStateAction, useCallback, useRef, useState } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { GeocodedLocation } from "@/lib/api";
import { useGeolocationFix } from "./location/use-geolocation-fix";
import { useLocationSearch } from "./location/use-location-search";
import { useManualCoordinates } from "./location/use-manual-coordinates";
import { ExactCoordinates, initialLocationSnapshot } from "./location/saved-coordinates";

export { POPULAR_CITIES } from "./location/popular-cities";
export { SAVED_COORDINATES_KEY } from "./location/saved-coordinates";

export interface LocationState {
  selectedStation: MapStation;
  setSelectedStation: Dispatch<SetStateAction<MapStation>>;
  geoStatus: string | null;
  locationLabel: string | null;
  setLocationLabel: Dispatch<SetStateAction<string | null>>;
  locationQuery: string;
  setLocationQuery: Dispatch<SetStateAction<string>>;
  manualCoordinates: string;
  setManualCoordinates: Dispatch<SetStateAction<string>>;
  hasSavedCoordinates: boolean;
  clearSavedCoordinates: () => void;
  locationResults: GeocodedLocation[];
  isSearchingLocation: boolean;
  handleUseMyLocation: () => void;
  handleLocationSearch: (event: FormEvent<HTMLFormElement>) => void;
  handleManualCoordinates: (event: FormEvent<HTMLFormElement>) => void;
  selectGeocodedLocation: (place: GeocodedLocation) => void;
  handleSelectStation: (stn: MapStation) => void;
}

/** Compatible facade over the focused location hooks. */
export function useLocationState(): LocationState {
  // Saved coordinates are read once, in a lazy initializer: no effect resets
  // state after mount, and no browser fix can override a confirmed pair.
  const [initial] = useState(initialLocationSnapshot);
  const [selectedStation, setSelectedStation] = useState<MapStation>(initial.selectedStation);
  const [geoStatus, setGeoStatus] = useState<string | null>(initial.geoStatus);
  const [locationLabel, setLocationLabel] = useState<string | null>(initial.locationLabel);
  const [savedCoordinates, setSavedCoordinates] = useState<ExactCoordinates | null>(
    initial.savedCoordinates
  );
  // Guards against a slow reverse lookup overwriting a newer user selection.
  const locationRequestRef = useRef(0);

  const search = useLocationSearch({
    requestRef: locationRequestRef,
    setGeoStatus,
    setLocationLabel,
    setSelectedStation,
  });

  const handleUseMyLocation = useGeolocationFix({
    savedCoordinates,
    requestRef: locationRequestRef,
    setGeoStatus,
    setLocationLabel,
    setLocationResults: search.setLocationResults,
    setSelectedStation,
  });

  const manual = useManualCoordinates({
    initialManualCoordinates: initial.manualCoordinates,
    requestRef: locationRequestRef,
    setSavedCoordinates,
    setGeoStatus,
    setLocationLabel,
    setLocationResults: search.setLocationResults,
    setSelectedStation,
  });

  const handleSelectStation = useCallback((stn: MapStation) => {
    locationRequestRef.current += 1;
    setLocationLabel(null);
    setSelectedStation(stn);
  }, []);

  return {
    selectedStation,
    setSelectedStation,
    geoStatus,
    locationLabel,
    setLocationLabel,
    locationQuery: search.locationQuery,
    setLocationQuery: search.setLocationQuery,
    manualCoordinates: manual.manualCoordinates,
    setManualCoordinates: manual.setManualCoordinates,
    hasSavedCoordinates: savedCoordinates !== null,
    clearSavedCoordinates: manual.clearSavedCoordinates,
    locationResults: search.locationResults,
    isSearchingLocation: search.isSearchingLocation,
    handleUseMyLocation,
    handleLocationSearch: search.handleLocationSearch,
    handleManualCoordinates: manual.handleManualCoordinates,
    selectGeocodedLocation: search.selectGeocodedLocation,
    handleSelectStation,
  };
}
