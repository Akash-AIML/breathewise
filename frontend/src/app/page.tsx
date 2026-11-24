"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import { AQIBadge } from "@/components/aqi/aqi-badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { HistoricalTrendChart } from "@/components/dashboard/historical-trend-chart";
import { StationComparisonView } from "@/components/dashboard/station-comparison-view";
import { StationMap, MapStation } from "@/components/dashboard/station-map";
import { fetchAirQuality, fetchStations } from "@/lib/api";
import { NormalizedObservation, StationMetadata } from "@/types/observation";

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

export default function HomePage() {
  const [selectedStation, setSelectedStation] = useState<MapStation>(POPULAR_CITIES[0]);
  const [observation, setObservation] = useState<NormalizedObservation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [geoStatus, setGeoStatus] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "trends" | "comparison" | "map">("overview");

  const loadData = async (lat: number, lon: number, bypassCache = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchAirQuality(lat, lon, bypassCache);
      if (res.success && res.data) {
        setObservation(res.data);
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

  useEffect(() => {
    loadData(selectedStation.lat, selectedStation.lon);
  }, [selectedStation]);

  // Browser Geolocation handler with graceful rejection handling
  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setGeoStatus("Geolocation is not supported by your browser.");
      return;
    }

    setGeoStatus("Requesting device location...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const userLat = pos.coords.latitude;
        const userLon = pos.coords.longitude;
        setGeoStatus(`Location found (${userLat.toFixed(2)}°N, ${userLon.toFixed(2)}°E)`);

        // Find nearest station from our registry
        const nearest = [...POPULAR_CITIES].sort((a, b) => {
          const distA = Math.hypot(a.lat - userLat, a.lon - userLon);
          const distB = Math.hypot(b.lat - userLat, b.lon - userLon);
          return distA - distB;
        })[0];

        setSelectedStation({
          ...nearest,
          name: `Nearest Station (${nearest.city})`,
        });
      },
      (err) => {
        setGeoStatus("Location access denied or timed out. You can manually choose any city below.");
      },
      { timeout: 10000 }
    );
  };

  // Compute relative time since measurement
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
        <div className="max-w-3xl space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold tracking-wide text-emerald-200 backdrop-blur-xs">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            100% Genuine Environmental Measurements • Zero Synthetic Generation
          </div>
          <h1 className="text-3xl font-extrabold sm:text-4xl tracking-tight">
            BreatheWise — Urban Air Quality Intelligence
          </h1>
          <p className="text-emerald-100 text-sm sm:text-base leading-relaxed">
            Evidence-based air pollution monitoring for Indian families. Verified CPCB sub-index formulas, continuous criteria pollutant tracking, and actionable protective routines.
          </p>
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

          {geoStatus && (
            <p className="text-[11px] text-emerald-300 italic" role="status">
              {geoStatus}
            </p>
          )}

          <div id="station-selector" className="flex flex-wrap gap-2" role="group" aria-label="Monitored Stations">
            {POPULAR_CITIES.map((stn) => {
              const isSelected = selectedStation.station_id === stn.station_id;
              return (
                <button
                  key={stn.station_id}
                  onClick={() => setSelectedStation(stn)}
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

      {/* Navigation Tabs for Dashboard Views */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <nav className="flex space-x-6 text-sm font-semibold" aria-label="Dashboard Views">
          <button
            onClick={() => setActiveTab("overview")}
            className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "overview"
                ? "border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-300"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400"
            }`}
            aria-current={activeTab === "overview" ? "page" : undefined}
          >
            <Wind className="h-4 w-4" aria-hidden="true" />
            Live Dashboard
          </button>

          <button
            onClick={() => setActiveTab("trends")}
            className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "trends"
                ? "border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-300"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400"
            }`}
            aria-current={activeTab === "trends" ? "page" : undefined}
          >
            <TrendingUp className="h-4 w-4" aria-hidden="true" />
            24-Hour Trends
          </button>

          <button
            onClick={() => setActiveTab("comparison")}
            className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "comparison"
                ? "border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-300"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400"
            }`}
            aria-current={activeTab === "comparison" ? "page" : undefined}
          >
            <GitCompare className="h-4 w-4" aria-hidden="true" />
            Station Comparison
          </button>

          <button
            onClick={() => setActiveTab("map")}
            className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "map"
                ? "border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-300"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400"
            }`}
            aria-current={activeTab === "map" ? "page" : undefined}
          >
            <MapPin className="h-4 w-4" aria-hidden="true" />
            Station Map
          </button>
        </nav>
      </div>

      {/* TAB 1: LIVE DASHBOARD OVERVIEW */}
      {activeTab === "overview" && (
        <section aria-labelledby="live-aqi-heading" className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 id="live-aqi-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <MapPin className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                Active Station: {selectedStation.name}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Coordinates: {selectedStation.lat.toFixed(4)}°N, {selectedStation.lon.toFixed(4)}°E • City: {selectedStation.city}, {selectedStation.state}
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
                <div>
                  <h3 className="text-sm font-bold">Observation Telemetry Unavailable</h3>
                  <p className="text-xs mt-1 leading-relaxed">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Real-Time Observation Content */}
          {!isLoading && observation && (
            <div className="space-y-6">
              {/* Summary Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* AQI Overview Card */}
                <Card className="md:col-span-1 flex flex-col justify-between border-slate-300 shadow-md">
                  <CardHeader>
                    <CardTitle className="text-sm font-medium text-slate-500 dark:text-slate-400">
                      National Air Quality Index (NAQI)
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-baseline gap-3">
                      <span className="text-5xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
                        {observation.calculated_aqi ?? "N/A"}
                      </span>
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Index Value
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

                {/* Provenance & Integrity Metadata Card */}
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

                    {observation.station.elevation_m !== undefined && observation.station.elevation_m !== null && (
                      <div className="space-y-1">
                        <span className="text-slate-500">Station Elevation:</span>
                        <p className="font-semibold text-slate-800 dark:text-slate-200">
                          {observation.station.elevation_m} meters ASL
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
                      <span className="text-[11px] text-slate-500 block mb-2">
                        {reading.unit}
                      </span>
                      {reading.sub_index !== undefined && reading.sub_index !== null && (
                        <div className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 rounded-sm py-0.5 dark:bg-emerald-950/60 dark:text-emerald-300">
                          Sub-Index: {reading.sub_index}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              </div>

              {/* Embedded 24-Hour Trend Chart Preview */}
              {observation.hourly_trend && observation.hourly_trend.length > 0 && (
                <HistoricalTrendChart
                  data={observation.hourly_trend}
                  stationName={selectedStation.name}
                />
              )}
            </div>
          )}
        </section>
      )}

      {/* TAB 2: 24-HOUR TRENDS */}
      {activeTab === "trends" && (
        <section aria-labelledby="trends-heading" className="space-y-6">
          {observation?.hourly_trend && observation.hourly_trend.length > 0 ? (
            <HistoricalTrendChart
              data={observation.hourly_trend}
              stationName={selectedStation.name}
            />
          ) : (
            <div className="py-12 text-center text-xs text-slate-500">
              No hourly trend data currently available for {selectedStation.name}.
            </div>
          )}
        </section>
      )}

      {/* TAB 3: STATION COMPARISON */}
      {activeTab === "comparison" && (
        <section aria-labelledby="comparison-heading">
          <StationComparisonView />
        </section>
      )}

      {/* TAB 4: STATION MAP */}
      {activeTab === "map" && (
        <section aria-labelledby="map-heading">
          <StationMap
            stations={POPULAR_CITIES}
            selectedStationId={selectedStation.station_id}
            onSelectStation={(stn) => {
              setSelectedStation(stn);
              setActiveTab("overview");
            }}
          />
        </section>
      )}
    </div>
  );
}
