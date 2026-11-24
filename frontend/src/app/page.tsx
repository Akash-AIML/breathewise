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
  Info,
} from "lucide-react";
import { AQIBadge } from "@/components/aqi/aqi-badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { fetchAirQuality, fetchStations } from "@/lib/api";
import { NormalizedObservation, StationMetadata } from "@/types/observation";

const POPULAR_CITIES = [
  { name: "Delhi (ITO)", lat: 28.6289, lon: 77.2407 },
  { name: "Mumbai (BKC)", lat: 19.0657, lon: 72.8687 },
  { name: "Bengaluru (BTM)", lat: 12.9166, lon: 77.6101 },
  { name: "Kolkata (Victoria)", lat: 22.5448, lon: 88.3426 },
  { name: "Chennai (Alandur)", lat: 13.0033, lon: 80.2014 },
  { name: "Hyderabad (Sanathnagar)", lat: 17.4589, lon: 78.4347 },
  { name: "Pune (Shivajinagar)", lat: 18.5314, lon: 73.8446 },
  { name: "Lucknow (Lalbagh)", lat: 26.8467, lon: 80.9462 },
];

export default function HomePage() {
  const [selectedCity, setSelectedCity] = useState(POPULAR_CITIES[0]);
  const [observation, setObservation] = useState<NormalizedObservation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StationMetadata[]>([]);

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
    loadData(selectedCity.lat, selectedCity.lon);
  }, [selectedCity]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      const res = await fetchStations(searchQuery.trim());
      setSearchResults(res.data);
    } catch (err) {
      setSearchResults([]);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      {/* Hero Banner */}
      <section className="rounded-2xl bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-900 p-8 text-white shadow-lg">
        <div className="max-w-3xl space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold tracking-wide text-emerald-200 backdrop-blur-xs">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            100% Verified Sensor & Atmospheric Data • Zero AI Hallucination
          </div>
          <h1 className="text-3xl font-extrabold sm:text-4xl tracking-tight">
            Evidence-Based Urban Air Quality Assistant
          </h1>
          <p className="text-emerald-100 text-sm sm:text-base leading-relaxed">
            Empowering Indian families with genuine real-time air pollution measurements, deterministic health precautions, and personalized low-emission routines.
          </p>
        </div>

        {/* City Selector Pills */}
        <div className="mt-6 pt-6 border-t border-emerald-700/60">
          <label htmlFor="city-pills" className="block text-xs font-semibold text-emerald-200 mb-2.5">
            Quick Select Monitored City Station:
          </label>
          <div id="city-pills" className="flex flex-wrap gap-2" role="group" aria-label="Monitored Cities">
            {POPULAR_CITIES.map((city) => {
              const isSelected = selectedCity.name === city.name;
              return (
                <button
                  key={city.name}
                  onClick={() => setSelectedCity(city)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    isSelected
                      ? "bg-white text-emerald-900 shadow-md font-bold"
                      : "bg-emerald-800/80 text-emerald-100 hover:bg-emerald-700/80"
                  }`}
                  aria-pressed={isSelected}
                >
                  {city.name}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* Main Monitoring Section */}
      <section aria-labelledby="live-aqi-heading" className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 id="live-aqi-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <MapPin className="h-5 w-5 text-emerald-600" aria-hidden="true" />
              Monitoring Station: {selectedCity.name}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Coordinates: {selectedCity.lat.toFixed(4)}°N, {selectedCity.lon.toFixed(4)}°E
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => loadData(selectedCity.lat, selectedCity.lon, true)}
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
              Fetching genuine environmental sensor data...
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Verifying CPCB breakpoints and multi-pollutant sufficiency rules.
            </p>
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200" role="alert">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <h3 className="text-sm font-bold">Observation Unavailable</h3>
                <p className="text-xs mt-1 leading-relaxed">{error}</p>
                <p className="text-xs text-red-700 dark:text-red-300 mt-2">
                  Transparent Integrity Guarantee: We do not show placeholder or synthetic AQI numbers when official providers are unreachable.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Data Display */}
        {!isLoading && observation && (
          <div className="space-y-6">
            {/* Top Summary Banner */}
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
                      Index Points
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
                      Dominant Pollutant: <strong className="text-slate-900 dark:text-slate-200">{observation.dominant_pollutant}</strong>
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Provenance and Integrity Metadata */}
              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Database className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                    Data Provenance & Sensor Verification
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div className="space-y-1">
                    <span className="text-slate-500">Provider Service:</span>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">
                      {observation.provider}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-500">Measurement Timestamp:</span>
                    <p className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      {new Date(observation.measurement_timestamp).toLocaleString("en-IN", {
                        timeZone: "Asia/Kolkata",
                      })}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-500">CPCB Data Sufficiency:</span>
                    <p className="font-semibold text-emerald-700 dark:text-emerald-400">
                      {observation.data_sufficiency_met ? "Satisfied (≥ 3 Criteria Pollutants with Particulates)" : "Insufficient"}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-500">Quality Status:</span>
                    <p className="font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                      {observation.data_quality_status}
                    </p>
                  </div>
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
          </div>
        )}
      </section>
    </div>
  );
}
