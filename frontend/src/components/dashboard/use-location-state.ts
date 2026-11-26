"use client";

import React, { useState, useRef } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { fetchReverseGeocode, searchLocations, GeocodedLocation } from "@/lib/api";
import { nearestNamedLocation } from "@/lib/geo";

// Browsers without GPS (common on laptops) often return an IP/Wi-Fi point with
// a city-sized accuracy radius. Do not present that as an exact device fix.
const MAX_TRUSTED_ACCURACY_METERS = 2_000;

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
  const [locationResults, setLocationResults] = useState<GeocodedLocation[]>([]);
  const [isSearchingLocation, setIsSearchingLocation] = useState(false);

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
        if (Number.isFinite(reportedAccuracy) && reportedAccuracy > MAX_TRUSTED_ACCURACY_METERS) {
          setGeoStatus(
            `Your browser returned an approximate location (${userLat.toFixed(4)}, ${userLon.toFixed(4)}) with ±${Math.round(reportedAccuracy)} m accuracy. Laptops without GPS often fall back to IP/Wi-Fi, so this is not treated as your exact location. Search for your city below or use a GPS device.`
          );
          setLocationResults([]);
          return;
        }
        const accuracy = Number.isFinite(reportedAccuracy)
          ? ` Device-reported accuracy: ±${Math.round(reportedAccuracy)} m.`
          : "";
        const prefix = `Using exact device coordinates (${userLat.toFixed(4)}, ${userLon.toFixed(4)}).${accuracy}`;
        // Do not block the data fetch on naming: exact coordinates are authoritative.
        setGeoStatus(`${prefix} Resolving place name...`);
        setLocationLabel("Exact device coordinates");
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
          if (requestId !== locationRequestRef.current) return;
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
      { timeout: 10000, enableHighAccuracy: true, maximumAge: 0 }
    );
  };

  const handleLocationSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (locationQuery.trim().length < 2) {
      setGeoStatus("Enter at least two characters to search for a place.");
      return;
    }
    setIsSearchingLocation(true);
    try {
      const results = await searchLocations(locationQuery);
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
    setSelectedStation({
      name: "Manual Coordinates",
      station_id: "manual_coordinates",
      city: "Manual coordinates",
      state: "",
      lat,
      lon,
    });
    setLocationLabel(`${lat.toFixed(4)}, ${lon.toFixed(4)}`);
    setGeoStatus(`Using manually entered coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)}).`);
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
    locationResults,
    isSearchingLocation,
    handleUseMyLocation,
    handleLocationSearch,
    handleManualCoordinates,
    selectGeocodedLocation,
    handleSelectStation,
  };
}
