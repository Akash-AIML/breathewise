import { MapStation } from "@/components/dashboard/station-map";
import { POPULAR_CITIES } from "./popular-cities";

// A confirmed coordinate pair is more trustworthy than a laptop browser fix,
// including fixes that claim unrealistically small accuracy.
export const SAVED_COORDINATES_KEY = "breathewise.exactCoordinates";
export const MAX_SAVED_DISTANCE_KM = 25;

export interface ExactCoordinates {
  lat: number;
  lon: number;
}

export function formatCoordinatesLabel(coords: ExactCoordinates): string {
  return `${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}`;
}

export function parseCoordinates(value: string): ExactCoordinates | null {
  const parts = value.trim().split(/[\s,]+/).filter(Boolean);
  if (parts.length !== 2) return null;
  const lat = Number(parts[0]);
  const lon = Number(parts[1]);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  return { lat, lon };
}

export type CoordinateValidation =
  | { coords: ExactCoordinates; error: null }
  | { coords: null; error: string };

export function validateCoordinateInput(value: string): CoordinateValidation {
  const parts = value.trim().split(/[\s,]+/).filter(Boolean);
  if (parts.length !== 2) {
    return {
      coords: null,
      error: "Enter latitude and longitude separated by a comma, e.g. 28.6289, 77.2407.",
    };
  }
  const lat = Number(parts[0]);
  const lon = Number(parts[1]);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
    return { coords: null, error: "Latitude must be a number between -90 and 90." };
  }
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
    return { coords: null, error: "Longitude must be a number between -180 and 180." };
  }
  return { coords: { lat, lon }, error: null };
}

/** Read once, before first render, so no post-mount state reset is needed. */
export function readSavedCoordinates(): ExactCoordinates | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SAVED_COORDINATES_KEY);
    return raw ? parseCoordinates(raw) : null;
  } catch {
    // Storage can be disabled or throw in private browsing; start with defaults.
    return null;
  }
}

/** Returns false when persistence is unavailable; callers keep coordinates in memory. */
export function storeSavedCoordinates(coords: ExactCoordinates): boolean {
  try {
    window.localStorage.setItem(SAVED_COORDINATES_KEY, `${coords.lat.toFixed(6)}, ${coords.lon.toFixed(6)}`);
    return true;
  } catch {
    return false;
  }
}

/** Returns false when storage could not be cleared. */
export function removeSavedCoordinates(): boolean {
  try {
    window.localStorage.removeItem(SAVED_COORDINATES_KEY);
    return true;
  } catch {
    return false;
  }
}

export interface InitialLocationSnapshot {
  selectedStation: MapStation;
  geoStatus: string | null;
  locationLabel: string | null;
  manualCoordinates: string;
  savedCoordinates: ExactCoordinates | null;
}

export function initialLocationSnapshot(): InitialLocationSnapshot {
  const coords = readSavedCoordinates();
  if (!coords) {
    return {
      selectedStation: POPULAR_CITIES[0],
      geoStatus: null,
      locationLabel: null,
      manualCoordinates: "",
      savedCoordinates: null,
    };
  }

  const label = formatCoordinatesLabel(coords);
  return {
    selectedStation: {
      name: "Saved Coordinates",
      station_id: "saved_coordinates",
      city: "Saved coordinates",
      state: "",
      lat: coords.lat,
      lon: coords.lon,
    },
    geoStatus: `Using saved coordinates (${label}). Enter new coordinates or clear them to change this location.`,
    locationLabel: label,
    manualCoordinates: label,
    savedCoordinates: coords,
  };
}
