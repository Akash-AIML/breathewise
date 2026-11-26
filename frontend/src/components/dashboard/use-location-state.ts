"use client";

import React, { useState, useRef, useEffect } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { fetchReverseGeocode, searchLocations, GeocodedLocation } from "@/lib/api";
import { haversineDistanceKm, nearestNamedLocation } from "@/lib/geo";

// Browsers without GPS (common on laptops) often return an IP/Wi-Fi point with
// a city-sized accuracy radius. Keep those coordinates usable, but label them
// honestly instead of discarding a legitimate fix.
const LOW_ACCURACY_WARNING_METERS = 2_000;

// A confirmed coordinate pair is more trustworthy than a laptop browser fix,
// including fixes that claim unrealistically small accuracy.
export const SAVED_COORDINATES_KEY = "breathewise.exactCoordinates";
const MAX_SAVED_DISTANCE_KM = 25;

interface ExactCoordinates {
  lat: number;
  lon: number;
}

function parseCoordinates(value: string): ExactCoordinates | null {
  const parts = value.trim().split(/[\s,]+/).filter(Boolean);
  if (parts.length !== 2) return null;
  const lat = Number(parts[0]);
  const lon = Number(parts[1]);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  return { lat, lon };
}

function formatCoordinatesLabel(coords: ExactCoordinates): string {
  return `${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}`;
}

export const POPULAR_CITIES: (MapStation & { distance_km?: number })[] = [
  { name: "Delhi (ITO)", station_id: "cpcb_delhi_ito", city: "Delhi", state: "Delhi", lat: 28.6289, lon: 77.2407 },
  { name: "Delhi (Anand Vihar)", station_id: "cpcb_delhi_anand_vihar", city: "Delhi", state: "Delhi", lat: 28.6469, lon: 77.3160 },
  { name: "Mumbai (Bandra)", station_id: "cpcb_mumbai_bandra", city: "Mumbai", state: "Maharashtra", lat: 19.0657, lon: 72.8687 },
  { name: "Bengaluru (BTM)", station_id: "cpcb_bengaluru_btm", city: "Bengaluru", state: "Karnataka", lat: 12.9166, lon: 77.6101 },
  { name: "Kolkata (Victoria)", station_id: "cpcb_kolkata_victoria", city: "Kolkata", state: "West Bengal", lat: 22.5448, lon: 88.3426 },
  { name: "Chennai (Alandur)", station_id: "cpcb_chennai_alandur", city: "Chennai", state: "Tamil Nadu", lat: 13.0033, lon: 80.2014 },
  { name: "Hyderabad (Sanathnagar)", station_id: "cpcb_hyderabad_sanathnagar", city: "Hyderabad", state: "Telangana", lat: 17.4589, lon: 78.4347 },
  { name: "Ahmedabad (Maninagar)", station_id: "cpcb_ahmedabad_maninagar", city: "Ahmedabad", state: "Gujarat", lat: 22.9984, lon: 72.6033 },
  { name: "Pune (Shivajinagar)", station_id: "cpcb_pune_shivajinagar", city: "Pune", state: "Maharashtra", lat: 18.5314, lon: 73.8446 },
  { name: "Lucknow (Lalbagh)", station_id: "cpcb_lucknow_lalbagh", city: "Lucknow", state: "Uttar Pradesh", lat: 26.8467, lon: 80.9462 },
];

export interface LocationState {
  selectedStation: MapStation;
  setSelectedStation: React.Dispatch<React.SetStateAction<MapStation>>;
  geoStatus: string | null;
  locationLabel: string | null;
  setLocationLabel: React.Dispatch<React.SetStateAction<string | null>>;
  locationQuery: string;
  setLocationQuery: React.Dispatch<React.SetStateAction<string>>;
  manualCoordinates: string;
  setManualCoordinates: React.Dispatch<React.SetStateAction<string>>;
  hasSavedCoordinates: boolean;
  clearSavedCoordinates: () => void;
  locationResults: GeocodedLocation[];
  isSearchingLocation: boolean;
  handleUseMyLocation: () => void;
  handleLocationSearch: (event: React.FormEvent<HTMLFormElement>) => void;
  handleManualCoordinates: (event: React.FormEvent<HTMLFormElement>) => void;
  selectGeocodedLocation: (place: GeocodedLocation) => void;
  handleSelectStation: (stn: MapStation) => void;
}

export function useLocationState(): LocationState {
  const [selectedStation, setSelectedStation] = useState<MapStation>(POPULAR_CITIES[0]);
  const [geoStatus, setGeoStatus] = useState<string | null>(null);
  const [locationLabel, setLocationLabel] = useState<string | null>(null);
  // Guards against a slow reverse lookup overwriting a newer user selection.
  const locationRequestRef = useRef(0);
  const [locationQuery, setLocationQuery] = useState("");
  const [manualCoordinates, setManualCoordinates] = useState("");
  const [savedCoordinates, setSavedCoordinates] = useState<ExactCoordinates | null>(null);
  const [locationResults, setLocationResults] = useState<GeocodedLocation[]>([]);
  const [isSearchingLocation, setIsSearchingLocation] = useState(false);

  // Restore a confirmed coordinate pair before using any browser-provided fix.
  useEffect(() => {
    const raw = window.localStorage.getItem(SAVED_COORDINATES_KEY);
    const coords = raw ? parseCoordinates(raw) : null;
    if (!coords) {
      return;
    }
    setSavedCoordinates(coords);
    setManualCoordinates(formatCoordinatesLabel(coords));
    setSelectedStation({
      name: "Saved Coordinates",
      station_id: "saved_coordinates",
      city: "Saved coordinates",
      state: "",
      lat: coords.lat,
      lon: coords.lon,
    });
    setLocationLabel(formatCoordinatesLabel(coords));
    setGeoStatus(
      `Using saved coordinates (${formatCoordinatesLabel(coords)}). Enter new coordinates or clear them to change this location.`
    );
  }, []);

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setGeoStatus("Geolocation is not supported by your browser.");
      return;
    }

    setGeoStatus("Requesting device location...");
    const requestId = ++locationRequestRef.current;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
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
          if (requestId !== locationRequestRef.current) {
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
        if (requestId !== locationRequestRef.current) return;
        setGeoStatus("Location access denied or timed out. Search for your city or choose a station below.");
      },
      // Do not force maximumAge: 0. On some laptops the fresh fix is much
      // worse than the browser's cached fix. Let the browser choose and report
      // the accuracy explicitly instead of silently discarding its better fix.
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleLocationSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = locationQuery.trim();
    if (query.length < 2) {
      setGeoStatus("Enter at least two characters to search for a place.");
      return;
    }
    setIsSearchingLocation(true);
    try {
      const results = await searchLocations(query);
      setLocationResults(results);
      setGeoStatus(
        results.length === 0
          ? `No place matched "${locationQuery}". Try a nearby city or use your device location.`
          : `${results.length} exact coordinate match(es) found. Pick one below.`
      );
    } catch (err) {
      setLocationResults([]);
      setGeoStatus(err instanceof Error ? err.message : "Location search failed.");
    } finally {
      setIsSearchingLocation(false);
    }
  };

  const handleManualCoordinates = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parts = manualCoordinates.trim().split(/[\s,]+/).filter(Boolean);
    if (parts.length !== 2) {
      setGeoStatus("Enter latitude and longitude separated by a comma, e.g. 28.6289, 77.2407.");
      return;
    }
    const lat = Number(parts[0]);
    const lon = Number(parts[1]);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setGeoStatus("Latitude must be a number between -90 and 90.");
      return;
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      setGeoStatus("Longitude must be a number between -180 and 180.");
      return;
    }

    locationRequestRef.current += 1;
    window.localStorage.setItem(SAVED_COORDINATES_KEY, `${lat.toFixed(6)}, ${lon.toFixed(6)}`);
    setSavedCoordinates({ lat, lon });
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
      `Using manually entered coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)}). Saved in this browser.`
    );
    setLocationResults([]);
  };

  const clearSavedCoordinates = () => {
    window.localStorage.removeItem(SAVED_COORDINATES_KEY);
    setSavedCoordinates(null);
    setManualCoordinates("");
    setGeoStatus("Saved coordinates cleared. Use My Location will use the browser again.");
    setLocationResults([]);
  };

  const selectGeocodedLocation = (place: GeocodedLocation) => {
    locationRequestRef.current += 1;
    const region = [place.admin1, place.country].filter(Boolean).join(", ");
    setSelectedStation({
      name: region ? `${place.name}, ${region}` : place.name,
      station_id: `geocode_${place.id}`,
      city: place.name,
      state: place.admin1 ?? "",
      lat: place.latitude,
      lon: place.longitude,
    });
    setGeoStatus(`Using exact coordinates for ${place.name} (${place.latitude.toFixed(4)}, ${place.longitude.toFixed(4)}).`);
    setLocationLabel(`${place.name}${region ? `, ${region}` : ""}`);
    setLocationResults([]);
  };

  const handleSelectStation = (stn: MapStation) => {
    locationRequestRef.current += 1;
    setLocationLabel(null);
    setSelectedStation(stn);
  };

  return {
    selectedStation,
    setSelectedStation,
    geoStatus,
    locationLabel,
    setLocationLabel,
    locationQuery,
    setLocationQuery,
    manualCoordinates,
    setManualCoordinates,
    hasSavedCoordinates: savedCoordinates !== null,
    clearSavedCoordinates,
    locationResults,
    isSearchingLocation,
    handleUseMyLocation,
    handleLocationSearch,
    handleManualCoordinates,
    selectGeocodedLocation,
    handleSelectStation,
  };
}
