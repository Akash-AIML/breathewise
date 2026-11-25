"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Wind,
  MapPin,
  Clock,
  Database,
  Search,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Navigation,
  GitCompare,
  TrendingUp,
  Calendar,
  Home,
  Leaf,
  Users,
  MessageCircle,
  type LucideIcon,
} from "lucide-react";
import { AQIBadge } from "@/components/aqi/aqi-badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { HistoricalTrendChart } from "@/components/dashboard/historical-trend-chart";
import { StationComparisonView } from "@/components/dashboard/station-comparison-view";
import { StationMap, MapStation } from "@/components/dashboard/station-map";
import { HouseholdProfileDialog } from "@/components/profile/household-profile-dialog";
import { DailyPlanner } from "@/components/planner/daily-planner";
import { IndoorAssistant } from "@/components/indoor/indoor-assistant";
import { SustainableAlternativesView } from "@/components/sustainability/sustainable-alternatives";
import { ChatAssistant } from "@/components/assistant/chat-assistant";
import {
  fetchAirQuality,
  fetchPersonalizedPlan,
  fetchReverseGeocode,
  fetchStations,
  searchLocations,
  GeocodedLocation,
} from "@/lib/api";
import { formatCoordinates, nearestNamedLocation } from "@/lib/geo";
import { NormalizedObservation } from "@/types/observation";
import { HouseholdProfile, PersonalizedPlan } from "@/types/recommendations";

const POPULAR_CITIES: (MapStation & { distance_km?: number })[] = [
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

type TabId =
  | "overview"
  | "planner"
  | "indoor"
  | "sustainability"
  | "trends"
  | "comparison"
  | "map"
  | "assistant";

const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Live Dashboard", icon: Wind },
  { id: "planner", label: "Daily Planner", icon: Calendar },
  { id: "indoor", label: "Indoor Air Guide", icon: Home },
  { id: "sustainability", label: "Sustainable Transit", icon: Leaf },
  { id: "trends", label: "24-Hour Trends", icon: TrendingUp },
  { id: "comparison", label: "Station Comparison", icon: GitCompare },
  { id: "map", label: "Station Map", icon: MapPin },
  { id: "assistant", label: "AI Assistant", icon: MessageCircle },
];

export default function HomePage() {
  const [selectedStation, setSelectedStation] = useState<MapStation>(POPULAR_CITIES[0]);
  const [observation, setObservation] = useState<NormalizedObservation | null>(null);
  const [plan, setPlan] = useState<PersonalizedPlan | null>(null);
  const [profile, setProfile] = useState<HouseholdProfile>({
    has_children: true,
    has_elderly: false,
    has_respiratory_sensitivity: true,
    has_cardiovascular_sensitivity: false,
    occupation_type: "indoor",
    commute_method: "two_wheeler",
    exercise_routine: "morning_outdoor",
    indoor_ventilation: "natural",
    has_air_purifier: false,
    home_area_sqft: 650,
  });
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [geoStatus, setGeoStatus] = useState<string | null>(null);
  const [locationLabel, setLocationLabel] = useState<string | null>(null);
  // Guards against a slow reverse lookup overwriting a newer user selection.
  const locationRequestRef = useRef(0);
  const [locationQuery, setLocationQuery] = useState("");
  const [locationResults, setLocationResults] = useState<GeocodedLocation[]>([]);
  const [isSearchingLocation, setIsSearchingLocation] = useState(false);
  const [liveStations, setLiveStations] = useState<MapStation[]>([]);
  const [stationsSource, setStationsSource] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "trends" | "planner" | "indoor" | "sustainability" | "comparison" | "map" | "assistant"
  >("overview");

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = (index + 1) % TABS.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = (index - 1 + TABS.length) % TABS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = TABS.length - 1;
    }
    if (nextIndex === null) return;
    event.preventDefault();
    const nextId = TABS[nextIndex].id;
    setActiveTab(nextId);
    document.getElementById(`tab-${nextId}`)?.focus();
  };

  const loadData = async (lat: number, lon: number, bypassCache = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchAirQuality(lat, lon, bypassCache);
      if (res.success && res.data) {
        setObservation(res.data);
        setError(null);
      } else if (res.success) {
        // Honest empty state: the provider responded but has no usable data.
        setObservation(null);
        setError(null);
      } else {
        setError(res.message || "No data available for this location.");
        setObservation(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to communicate with air quality service.");
      setObservation(null);
    } finally {
      setIsLoading(false);
    }
  };

  const loadPlan = async (lat: number, lon: number, prof: HouseholdProfile) => {
    setIsPlanLoading(true);
    try {
      const planRes = await fetchPersonalizedPlan(lat, lon, prof);
      setPlan(planRes);
    } catch (err) {
      setPlan(null);
    } finally {
      setIsPlanLoading(false);
    }
  };

  useEffect(() => {
    loadData(selectedStation.lat, selectedStation.lon);
    loadPlan(selectedStation.lat, selectedStation.lon, profile);
  }, [selectedStation, profile]);

  useEffect(() => {
    let cancelled = false;
    fetchStations()
      .then((result) => {
        if (cancelled) return;
        const isLiveCpcb = result.message?.includes("CPCB/data.gov.in") ?? false;
        setStationsSource(isLiveCpcb ? "CPCB/data.gov.in" : result.message ?? "source unavailable");
        setLiveStations(
          isLiveCpcb
            ? result.data
                .filter(
                  (station) =>
                    Number.isFinite(station.latitude) &&
                    Number.isFinite(station.longitude)
                )
                .map((station) => ({
                  name: station.station_name,
                  station_id: station.station_id,
                  city: station.city,
                  state: station.state,
                  lat: station.latitude,
                  lon: station.longitude,
                }))
            : []
        );
      })
      .catch(() => {
        if (!cancelled) {
          setStationsSource("source unavailable");
          setLiveStations([]);
        }
      });
    return () => {
      cancelled = true;
    };
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
        const prefix = `Using exact device coordinates (${userLat.toFixed(4)}, ${userLon.toFixed(4)}).`;
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
      { timeout: 10000, enableHighAccuracy: true }
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

  const getRelativeTime = (isoString?: string) => {
    if (!isoString) return "";
    const diffMs = Date.now() - new Date(isoString).getTime();
    const mins = Math.max(0, Math.floor(diffMs / 60000));
    if (mins < 60) return `${mins} mins ago`;
    const hours = Math.floor(mins / 60);
    return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      {/* Hero Environmental Intelligence Banner */}
      <section className="rounded-2xl bg-gradient-to-br from-emerald-950 via-emerald-900 to-teal-950 p-6 sm:p-8 text-white shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold tracking-wide text-emerald-200 backdrop-blur-xs">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Source-Attributed Environmental Data • No Synthetic AQI Generation
            </div>
            <h1 className="text-3xl font-extrabold sm:text-4xl tracking-tight">
              BreatheWise — Evidence-Based Air Quality Assistant
            </h1>
            <p className="text-emerald-100 text-sm sm:text-base leading-relaxed">
              Empowering Indian families with source-attributed CPCB/CAMS air data, deterministic health precautions, and personalized low-emission routines.
            </p>
          </div>

          {/* Household Profile Button */}
          <div className="shrink-0 bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 space-y-2">
            <span className="text-[11px] font-bold text-emerald-200 uppercase tracking-wider block">
              Active Household Profile
            </span>
            <div className="text-xs text-white space-y-0.5">
              <p>• {profile.has_children ? "Children at home" : "No young children"}</p>
              <p>• {profile.has_respiratory_sensitivity ? "Respiratory Sensitivity (Asthma)" : "Standard Sensitivity"}</p>
              <p>• Commute: {profile.commute_method.replace("_", " ")}</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsProfileOpen(true)}
              className="w-full mt-2 bg-emerald-800 text-white border-emerald-600 hover:bg-emerald-700 text-xs flex items-center justify-center gap-1.5"
            >
              <Users className="h-3.5 w-3.5" />
              Configure Profile
            </Button>
          </div>
        </div>

        {/* Location & Quick Select Controls */}
        <div className="mt-6 pt-6 border-t border-emerald-800/80 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label htmlFor="station-selector" className="text-xs font-semibold text-emerald-200">
              Select Monitoring Station:
            </label>

            <Button
              variant="outline"
              size="sm"
              onClick={handleUseMyLocation}
              className="bg-emerald-900/60 border-emerald-700 text-emerald-100 hover:bg-emerald-800 text-xs flex items-center gap-1.5"
            >
              <Navigation className="h-3.5 w-3.5" aria-hidden="true" />
              Use My Location
            </Button>
          </div>

          <form onSubmit={handleLocationSearch} className="flex flex-wrap items-center gap-2">
            <label htmlFor="location-search" className="text-xs font-semibold text-emerald-200">
              Search any city or locality:
            </label>
            <input
              id="location-search"
              type="search"
              value={locationQuery}
              onChange={(event) => setLocationQuery(event.target.value)}
              placeholder="e.g. Patna, Pune, Kochi"
              className="min-w-0 flex-1 rounded-lg border border-emerald-700 bg-emerald-950/70 px-3 py-1.5 text-xs text-white placeholder-emerald-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
            />
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={isSearchingLocation}
              className="bg-emerald-900/60 border-emerald-700 text-emerald-100 hover:bg-emerald-800 text-xs flex items-center gap-1.5"
            >
              <Search className="h-3.5 w-3.5" aria-hidden="true" />
              {isSearchingLocation ? "Searching…" : "Find Exact Place"}
            </Button>
          </form>

          {geoStatus && (
            <p className="text-[11px] text-emerald-300 italic" role="status">
              {geoStatus}
            </p>
          )}

          {locationResults.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Exact location search results">
              {locationResults.map((place) => (
                <li key={place.id}>
                  <button
                    type="button"
                    onClick={() => selectGeocodedLocation(place)}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium bg-emerald-800/80 text-emerald-100 hover:bg-emerald-700"
                  >
                    {place.name}
                    {place.admin1 ? `, ${place.admin1}` : ""}
                    <span className="ml-1 text-emerald-300">
                      ({place.latitude.toFixed(3)}, {place.longitude.toFixed(3)})
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div id="station-selector" className="flex flex-wrap gap-2" role="group" aria-label="Monitored Stations">
            {POPULAR_CITIES.map((stn) => {
              const isSelected = selectedStation.station_id === stn.station_id;
              return (
                <button
                  key={stn.station_id}
                  onClick={() => {
                    locationRequestRef.current += 1;
                    setLocationLabel(null);
                    setSelectedStation(stn);
                  }}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    isSelected
                      ? "bg-white text-emerald-950 shadow-md font-bold"
                      : "bg-emerald-900/80 text-emerald-200 hover:bg-emerald-800"
                  }`}
                  aria-pressed={isSelected}
                >
                  {stn.name}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* Navigation Tabs for All Modules */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <div
          role="tablist"
          aria-label="Dashboard Views"
          className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold"
        >
          {TABS.map((tab, index) => {
            const Icon = tab.icon;
            const isSelected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                role="tab"
                type="button"
                aria-selected={isSelected}
                aria-controls={`panel-${tab.id}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => setActiveTab(tab.id)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                className={`pb-3 border-b-2 flex items-center gap-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
                  isSelected
                    ? "border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-300"
                    : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400"
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* TAB 1: LIVE DASHBOARD OVERVIEW */}
      {activeTab === "overview" && (
        <section
          id="panel-overview"
          role="tabpanel"
          aria-labelledby="tab-overview"
          tabIndex={0}
          className="space-y-6 focus:outline-none"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 id="live-aqi-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <MapPin className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                Active Station: {selectedStation.name}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Coordinates: {formatCoordinates(selectedStation.lat, selectedStation.lon)} •{" "}
                {locationLabel ?? `City: ${selectedStation.city}${selectedStation.state ? `, ${selectedStation.state}` : ""}`}
              </p>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => loadData(selectedStation.lat, selectedStation.lon, true)}
              disabled={isLoading}
              className="self-start sm:self-auto flex items-center gap-1.5"
              aria-label="Refresh live data"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} aria-hidden="true" />
              Refresh Observations
            </Button>
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="rounded-xl border border-slate-200 bg-white p-12 text-center dark:border-slate-800 dark:bg-slate-900">
              <RefreshCw className="h-8 w-8 animate-spin text-emerald-600 mx-auto mb-3" aria-hidden="true" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                Fetching genuine environmental sensor telemetry...
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Verifying CPCB sub-index linear interpolation and multi-pollutant sufficiency rules.
              </p>
            </div>
          )}

          {/* Error State */}
          {!isLoading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200" role="alert">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" aria-hidden="true" />
                <div className="flex-1">
                  <h3 className="text-sm font-bold">Observation Telemetry Unavailable</h3>
                  <p className="text-xs mt-1 leading-relaxed">{error}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 border-red-400 text-red-800 hover:bg-red-100 dark:text-red-200 dark:border-red-700"
                    onClick={() => loadData(selectedStation.lat, selectedStation.lon, false)}
                  >
                    Retry observation request
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Empty State: distinct from zero pollution */}
          {!isLoading && !error && !observation && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200" role="status">
              <h3 className="text-sm font-bold">No observation available</h3>
              <p className="text-xs mt-1">
                No provider returned a usable reading for these exact coordinates. This is not a
                zero-pollution result. Try another location or retry the request.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3 border-amber-400"
                onClick={() => loadData(selectedStation.lat, selectedStation.lon, false)}
              >
                Retry observation request
              </Button>
            </div>
          )}

          {/* Real-Time Observation Content */}
          {!isLoading && observation && (
            <div className="space-y-6">
              {(observation.data_quality_status === "stale" ||
                observation.data_quality_status === "delayed" ||
                observation.data_quality_status === "unavailable") && (
                <div
                  className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
                  role="status"
                >
                  <strong className="uppercase">{observation.data_quality_status} data:</strong>{" "}
                  Do not treat this observation as live. Check the source timestamp before acting.
                </div>
              )}

              {observation.notes && (
                <p className="text-[11px] text-slate-500 dark:text-slate-400 whitespace-pre-line">
                  {observation.notes}
                </p>
              )}

              {/* Summary Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="md:col-span-1 flex flex-col justify-between border-slate-300 shadow-md">
                  <CardHeader>
                    <CardTitle className="text-sm font-medium text-slate-500 dark:text-slate-400">
                      Official CPCB AQI
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-baseline gap-3">
                      <span className="text-5xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
                        {observation.calculated_aqi ?? "Unavailable"}
                      </span>
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        {observation.calculated_aqi === null || observation.calculated_aqi === undefined
                          ? "Insufficient verified averaging data"
                          : "Index Value"}
                      </span>
                    </div>

                    <div>
                      <AQIBadge
                        category={observation.aqi_category}
                        aqi={observation.calculated_aqi}
                      />
                    </div>

                    {observation.dominant_pollutant && (
                      <p className="text-xs text-slate-600 dark:text-slate-400 border-t border-slate-100 pt-3 dark:border-slate-800">
                        Dominant Pollutant:{" "}
                        <strong className="text-slate-900 dark:text-slate-200 font-bold">
                          {observation.dominant_pollutant}
                        </strong>
                      </p>
                    )}
                  </CardContent>
                </Card>

                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <Database className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                      Data Provenance & Sensor Verification
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-1">
                      <span className="text-slate-500">Provider Source:</span>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">
                        {observation.provider}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-slate-500">Reporting Station:</span>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">
                        {observation.station.station_name}, {observation.station.city},{" "}
                        {observation.station.state}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        Station coordinates:{" "}
                        {formatCoordinates(
                          observation.station.latitude,
                          observation.station.longitude
                        )}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-slate-500">Retrieved At:</span>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">
                        {new Date(observation.retrieval_timestamp).toLocaleString("en-IN", {
                          timeZone: "Asia/Kolkata",
                        })}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-slate-500">Measured At:</span>
                      <p className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                        {new Date(observation.measurement_timestamp).toLocaleString("en-IN", {
                          timeZone: "Asia/Kolkata",
                        })}{" "}
                        <span className="text-emerald-700 font-bold dark:text-emerald-400">
                          ({getRelativeTime(observation.measurement_timestamp)})
                        </span>
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-slate-500">CPCB Data Sufficiency:</span>
                      <p className="font-semibold text-emerald-700 dark:text-emerald-400">
                        {observation.data_sufficiency_met
                          ? "Satisfied (≥ 3 Pollutants + Particulates)"
                          : "Insufficient"}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-slate-500">Data Freshness:</span>
                      <p className="font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        {observation.data_quality_status}
                      </p>
                    </div>

                    {observation.station.distance_km !== undefined && (
                      <div className="space-y-1">
                        <span className="text-slate-500">Station Distance:</span>
                        <p className="font-semibold text-slate-800 dark:text-slate-200">
                          {observation.station.distance_km} km away
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Criteria Pollutant Breakdown Grid */}
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-4">
                  Criteria Pollutant Breakdown
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                  {Object.entries(observation.readings).map(([key, reading]) => (
                    <Card key={key} className="p-4 text-center">
                      <span className="text-xs font-semibold text-slate-500 block mb-1">
                        {reading.pollutant}
                      </span>
                      <span className="text-2xl font-bold text-slate-900 dark:text-slate-100 block">
                        {reading.value}
                      </span>
                      <span className="text-[10px] font-semibold text-slate-500 uppercase block">
                        Average concentration
                      </span>
                      <span className="text-[11px] text-slate-500 block mb-2">
                        {reading.unit ?? "Unit not provided by source"}
                      </span>
                      {(reading.min_value !== undefined ||
                        reading.max_value !== undefined) && (
                        <span className="text-[10px] text-slate-500 block">
                          Min {reading.min_value ?? "—"} / Max {reading.max_value ?? "—"}
                        </span>
                      )}
                      {reading.sub_index !== undefined && reading.sub_index !== null && (
                        <div className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 rounded-sm py-0.5 dark:bg-emerald-950/60 dark:text-emerald-300">
                          Sub-Index: {reading.sub_index}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* TAB 2: DAILY ACTION PLANNER */}
      {activeTab === "planner" && (
        <section
          id="panel-planner"
          role="tabpanel"
          aria-labelledby="tab-planner"
          tabIndex={0}
          className="space-y-4 focus:outline-none"
        >
          <div className="flex items-center justify-between">
            <h2 id="planner-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Personalized Daily Action Planner
            </h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsProfileOpen(true)}
              className="text-xs flex items-center gap-1.5"
            >
              <Users className="h-3.5 w-3.5" />
              Adjust Household Vulnerabilities
            </Button>
          </div>
          <DailyPlanner plan={plan} isLoading={isPlanLoading} />
        </section>
      )}

      {/* TAB 3: INDOOR AIR QUALITY ASSISTANT */}
      {activeTab === "indoor" && (
        <section
          id="panel-indoor"
          role="tabpanel"
          aria-labelledby="tab-indoor"
          tabIndex={0}
          className="space-y-4 focus:outline-none"
        >
          <h2 id="indoor-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
            Evidence-Based Indoor Air Quality Assistant
          </h2>
          <IndoorAssistant
            guidance={plan?.indoor_guidance ?? null}
            onAreaChange={(newArea) => {
              setProfile((p) => ({ ...p, home_area_sqft: newArea }));
            }}
          />
        </section>
      )}

      {/* TAB 4: SUSTAINABLE ALTERNATIVES */}
      {activeTab === "sustainability" && (
        <section
          id="panel-sustainability"
          role="tabpanel"
          aria-labelledby="tab-sustainability"
          tabIndex={0}
          className="space-y-4 focus:outline-none"
        >
          <h2 id="sustainability-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
            Sustainable Mobility & Emission Impact
          </h2>
          <SustainableAlternativesView
            alternatives={plan?.sustainable_alternatives ?? []}
          />
        </section>
      )}

      {/* TAB 5: 24-HOUR TRENDS */}
      {activeTab === "trends" && (
        <section
          id="panel-trends"
          role="tabpanel"
          aria-labelledby="tab-trends"
          tabIndex={0}
          className="space-y-6 focus:outline-none"
        >
          {observation?.hourly_trend && observation.hourly_trend.length > 0 ? (
            <HistoricalTrendChart
              data={observation.hourly_trend}
              stationName={selectedStation.name}
              sourceLabel={observation.provider}
            />
          ) : (
            <div className="py-12 text-center text-xs text-slate-500">
              No hourly trend data currently available for {selectedStation.name}.
            </div>
          )}
        </section>
      )}

      {/* TAB 6: STATION COMPARISON */}
      {activeTab === "comparison" && (
        <section
          id="panel-comparison"
          role="tabpanel"
          aria-labelledby="tab-comparison"
          tabIndex={0}
          className="focus:outline-none"
        >
          <StationComparisonView />
        </section>
      )}

      {/* TAB 7: STATION MAP */}
      {activeTab === "map" && (
        <section
          id="panel-map"
          role="tabpanel"
          aria-labelledby="tab-map"
          tabIndex={0}
          className="space-y-3 focus:outline-none"
        >
          <h2 id="map-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
            Monitoring Station Map
          </h2>
          {liveStations.length > 0 ? (
            <>
              <p className="text-xs text-slate-500">
                Markers use reported CPCB station coordinates from {stationsSource}.
              </p>
              <StationMap
                stations={liveStations}
                selectedStationId={selectedStation.station_id}
                onSelectStation={(stn) => {
                  setSelectedStation(stn);
                  setActiveTab("overview");
                }}
              />
            </>
          ) : (
            <div
              className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
              role="status"
            >
              Live station coordinates are unavailable ({stationsSource ?? "unknown source"}). The
              map is intentionally hidden instead of plotting estimated city-centre positions.
              <Button
                variant="outline"
                size="sm"
                className="ml-3 border-amber-400"
                onClick={() =>
                  fetchStations()
                    .then((result) => {
                      const isLiveCpcb = result.message?.includes("CPCB/data.gov.in") ?? false;
                      setStationsSource(isLiveCpcb ? "CPCB/data.gov.in" : result.message ?? "source unavailable");
                      setLiveStations(
                        isLiveCpcb
                          ? result.data.map((station) => ({
                              name: station.station_name,
                              station_id: station.station_id,
                              city: station.city,
                              state: station.state,
                              lat: station.latitude,
                              lon: station.longitude,
                            }))
                          : []
                      );
                    })
                    .catch(() => setStationsSource("source unavailable"))
                }
              >
                Retry station lookup
              </Button>
            </div>
          )}
        </section>
      )}

      {/* TAB 8: AI ASSISTANT */}
      {activeTab === "assistant" && (
        <section
          id="panel-assistant"
          role="tabpanel"
          aria-labelledby="tab-assistant"
          tabIndex={0}
          className="h-[72vh] flex flex-col rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-sm focus:outline-none"
        >
          <h2 id="assistant-heading" className="sr-only">
            BreatheWise AI Assistant
          </h2>
          <ChatAssistant
            lat={selectedStation.lat}
            lon={selectedStation.lon}
            currentAqi={observation?.calculated_aqi}
            profile={profile}
            className="flex-1"
          />
        </section>
      )}

      {/* Household Profile Dialog Modal */}
      <HouseholdProfileDialog
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        profile={profile}
        onSave={(updated) => {
          setProfile(updated);
        }}
      />
    </div>
  );
}
