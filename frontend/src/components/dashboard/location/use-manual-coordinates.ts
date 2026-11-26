"use client";

import {
  type Dispatch,
  type FormEvent,
  type RefObject,
  type SetStateAction,
  useCallback,
  useState,
} from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { GeocodedLocation } from "@/lib/api";
import {
  ExactCoordinates,
  removeSavedCoordinates,
  storeSavedCoordinates,
  validateCoordinateInput,
} from "./saved-coordinates";

interface ManualCoordinatesDeps {
  initialManualCoordinates: string;
  requestRef: RefObject<number>;
  setSavedCoordinates: Dispatch<SetStateAction<ExactCoordinates | null>>;
  setGeoStatus: (status: string | null) => void;
  setLocationLabel: (label: string | null) => void;
  setLocationResults: Dispatch<SetStateAction<GeocodedLocation[]>>;
  setSelectedStation: Dispatch<SetStateAction<MapStation>>;
}

/** Exact manual input and the saved-coordinate override/clear flow. */
export function useManualCoordinates({
  initialManualCoordinates,
  requestRef,
  setSavedCoordinates,
  setGeoStatus,
  setLocationLabel,
  setLocationResults,
  setSelectedStation,
}: ManualCoordinatesDeps) {
  const [manualCoordinates, setManualCoordinates] = useState(initialManualCoordinates);

  const handleManualCoordinates = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const { coords, error } = validateCoordinateInput(manualCoordinates);
      if (!coords) {
        setGeoStatus(error);
        return;
      }
      const { lat, lon } = coords;

      requestRef.current += 1;
      const persisted = storeSavedCoordinates(coords);
      setSavedCoordinates(coords);
      setSelectedStation({
        name: "Manual Coordinates",
        station_id: "manual_coordinates",
        city: "Manual coordinates",
        state: "",
        lat,
        lon,
      });
      setLocationLabel(`${lat.toFixed(4)}, ${lon.toFixed(4)}`);
      setGeoStatus(
        `Using manually entered coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)}). ${
          persisted ? "Saved in this browser." : "These could not be saved in this browser."
        }`
      );
      setLocationResults([]);
    },
    [
      manualCoordinates,
      requestRef,
      setGeoStatus,
      setLocationLabel,
      setLocationResults,
      setSavedCoordinates,
      setSelectedStation,
    ]
  );

  const clearSavedCoordinates = useCallback(() => {
    // Invalidate in-flight geolocation/reverse-lookup/search work before the
    // cleared state is published.
    requestRef.current += 1;
    const removed = removeSavedCoordinates();
    setSavedCoordinates(null);
    setManualCoordinates("");
    setGeoStatus(
      removed
        ? "Saved coordinates cleared. Use My Location will use the browser again."
        : "Saved coordinates cleared for this session. They could not be removed from browser storage."
    );
    setLocationResults([]);
  }, [requestRef, setGeoStatus, setLocationResults, setSavedCoordinates]);

  return { manualCoordinates, setManualCoordinates, handleManualCoordinates, clearSavedCoordinates };
}
