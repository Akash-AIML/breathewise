"use client";

import { type RefObject, useCallback } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { fetchReverseGeocode, GeocodedLocation } from "@/lib/api";
import { haversineDistanceKm, nearestNamedLocation } from "@/lib/geo";
import { POPULAR_CITIES } from "./popular-cities";
import {
  ExactCoordinates,
  formatCoordinatesLabel,
  MAX_SAVED_DISTANCE_KM,
} from "./saved-coordinates";

// Browsers without GPS (common on laptops) often return an IP/Wi-Fi point with
// a city-sized accuracy radius. Keep those coordinates usable, but label them
// honestly instead of discarding a legitimate fix.
const LOW_ACCURACY_WARNING_METERS = 2_000;

interface GeolocationDeps {
  savedCoordinates: ExactCoordinates | null;
  requestRef: RefObject<number>;
  setGeoStatus: (status: string | null) => void;
  setLocationLabel: (label: string | null) => void;
  setLocationResults: (results: GeocodedLocation[]) => void;
  setSelectedStation: (station: MapStation) => void;
}

export function useGeolocationFix({
  savedCoordinates,
  requestRef,
  setGeoStatus,
  setLocationLabel,
  setLocationResults,
  setSelectedStation,
}: GeolocationDeps): () => void {
  return useCallback(() => {
    if (!navigator.geolocation) {
      setGeoStatus("Geolocation is not supported by your browser.");
      return;
    }

    setGeoStatus("Requesting device location...");
    const requestId = ++requestRef.current;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        // A newer manual/geocoded/station selection may already have won.
        if (requestId !== requestRef.current) return;
        const userLat = pos.coords.latitude;
        const userLon = pos.coords.longitude;
        if (!Number.isFinite(userLat) || !Number.isFinite(userLon)) {
          setGeoStatus("The device returned invalid coordinates. Search for your city or choose a station below.");
          return;
        }
        const reportedAccuracy = pos.coords.accuracy;
        const isApproximate =
          Number.isFinite(reportedAccuracy) && reportedAccuracy > LOW_ACCURACY_WARNING_METERS;
        const accuracy = Number.isFinite(reportedAccuracy)
          ? ` Device-reported accuracy: ±${Math.round(reportedAccuracy)} m.`
          : "";
        const distanceFromSavedKm = savedCoordinates
          ? haversineDistanceKm(userLat, userLon, savedCoordinates.lat, savedCoordinates.lon)
          : null;
        const rejectedBySavedCoordinates =
          savedCoordinates !== null &&
          distanceFromSavedKm !== null &&
          distanceFromSavedKm > MAX_SAVED_DISTANCE_KM;
        if (savedCoordinates && rejectedBySavedCoordinates && distanceFromSavedKm !== null) {
          setGeoStatus(
            `Browser reported (${userLat.toFixed(4)}, ${userLon.toFixed(4)}).${accuracy} That is ${distanceFromSavedKm.toFixed(0)} km from your saved coordinates (${formatCoordinatesLabel(savedCoordinates)}), so it was ignored. Keeping saved coordinates. Clear saved coordinates to use device location.`
          );
          setLocationResults([]);
          return;
        }
        const prefix = isApproximate
          ? `Using browser coordinates (${userLat.toFixed(4)}, ${userLon.toFixed(4)}).${accuracy} This may be a Wi‑Fi/IP estimate rather than an exact device fix.`
          : `Using exact device coordinates (${userLat.toFixed(4)}, ${userLon.toFixed(4)}).${accuracy}`;
        // Do not block the data fetch on naming or accuracy: coordinates are
        // still the only location input, and low accuracy is disclosed above.
        setGeoStatus(`${prefix} Resolving place name...`);
        setLocationLabel(isApproximate ? "Approximate device coordinates" : "Exact device coordinates");
        setLocationResults([]);
        setSelectedStation({
          name: "My Exact Location",
          station_id: "device_location",
          city: "Device coordinates",
          state: "",
          lat: userLat,
          lon: userLon,
        });

        void fetchReverseGeocode(userLat, userLon).then((place) => {
          if (requestId !== requestRef.current) {
            return;
          }
          // A hardcoded popular city is only a credible fallback when genuinely
          // close. Otherwise reporting "near Bengaluru" 160 km away is wrong.
          const nearby = nearestNamedLocation(userLat, userLon, POPULAR_CITIES);
          const nearbyStation = nearby && nearby.distanceKm <= 25 ? nearby : null;
          const suffix = place
            ? ` Located in ${place.name}${place.state ? `, ${place.state}` : ""} (OpenStreetMap).`
            : nearbyStation
              ? ` Nearest mapped station: ${nearbyStation.point.city} (${nearbyStation.distanceKm.toFixed(1)} km away).`
              : " No mapped place name is available for these coordinates.";
          setGeoStatus(`${prefix}${suffix}`);
          setLocationLabel(
            place
              ? `${place.name}${place.state ? `, ${place.state}` : ""} (OpenStreetMap)`
              : nearbyStation
                ? `Nearest mapped station: ${nearbyStation.point.name} (${nearbyStation.distanceKm.toFixed(1)} km away)`
                : "Exact device coordinates"
          );
        });
      },
      () => {
        if (requestId !== requestRef.current) return;
        setGeoStatus("Location access denied or timed out. Search for your city or choose a station below.");
      },
      // Do not force maximumAge: 0. On some laptops the fresh fix is much
      // worse than the browser's cached fix. Let the browser choose and report
      // the accuracy explicitly instead of silently discarding its better fix.
      { timeout: 10000, enableHighAccuracy: true }
    );
  }, [requestRef, savedCoordinates, setGeoStatus, setLocationLabel, setLocationResults, setSelectedStation]);
}
