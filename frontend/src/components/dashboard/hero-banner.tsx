"use client";

import React from "react";
import { CheckCircle2, Crosshair, Navigation, Search, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MapStation } from "@/components/dashboard/station-map";
import { GeocodedLocation } from "@/lib/api";
import { HouseholdProfile } from "@/types/recommendations";

interface HeroBannerProps {
  profile: HouseholdProfile;
  selectedStation: MapStation;
  locationQuery: string;
  manualCoordinates: string;
  hasSavedCoordinates: boolean;
  isSearchingLocation: boolean;
  geoStatus: string | null;
  locationResults: GeocodedLocation[];
  popularCities: (MapStation & { distance_km?: number })[];
  onConfigureProfile: () => void;
  onUseMyLocation: () => void;
  onLocationQueryChange: (value: string) => void;
  onLocationSearch: (event: React.FormEvent<HTMLFormElement>) => void;
  onManualCoordinatesChange: (value: string) => void;
  onManualCoordinatesSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onClearSavedCoordinates: () => void;
  onSelectGeocodedLocation: (place: GeocodedLocation) => void;
  onSelectStation: (station: MapStation) => void;
}

export const HeroBanner: React.FC<HeroBannerProps> = ({
  profile,
  selectedStation,
  locationQuery,
  manualCoordinates,
  hasSavedCoordinates,
  isSearchingLocation,
  geoStatus,
  locationResults,
  popularCities,
  onConfigureProfile,
  onUseMyLocation,
  onLocationQueryChange,
  onLocationSearch,
  onManualCoordinatesChange,
  onManualCoordinatesSubmit,
  onClearSavedCoordinates,
  onSelectGeocodedLocation,
  onSelectStation,
}) => (
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
          onClick={onConfigureProfile}
          className="w-full mt-2 bg-emerald-800 text-white border-emerald-600 hover:bg-emerald-700 text-xs flex items-center justify-center gap-1.5"
        >
          <Users className="h-3.5 w-3.5" />
          Configure Profile
        </Button>
      </div>
    </div>

    <div className="mt-6 pt-6 border-t border-emerald-800/80 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label htmlFor="station-selector" className="text-xs font-semibold text-emerald-200">
          Select Monitoring Station:
        </label>

        <Button
          variant="outline"
          size="sm"
          onClick={onUseMyLocation}
          className="bg-emerald-900/60 border-emerald-700 text-emerald-100 hover:bg-emerald-800 text-xs flex items-center gap-1.5"
        >
          <Navigation className="h-3.5 w-3.5" aria-hidden="true" />
          Use My Location
        </Button>
      </div>

      <form onSubmit={onLocationSearch} className="flex flex-wrap items-center gap-2">
        <label htmlFor="location-search" className="text-xs font-semibold text-emerald-200">
          Search any city or locality:
        </label>
        <input
          id="location-search"
          type="search"
          value={locationQuery}
          onChange={(event) => onLocationQueryChange(event.target.value)}
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

      <form onSubmit={onManualCoordinatesSubmit} className="flex flex-wrap items-center gap-2">
        <label htmlFor="manual-coordinates" className="text-xs font-semibold text-emerald-200">
          Exact coordinates (lat, lon):
        </label>
        <input
          id="manual-coordinates"
          type="text"
          inputMode="decimal"
          value={manualCoordinates}
          onChange={(event) => onManualCoordinatesChange(event.target.value)}
          placeholder="28.6289, 77.2407"
          className="min-w-0 flex-1 rounded-lg border border-emerald-700 bg-emerald-950/70 px-3 py-1.5 text-xs text-white placeholder-emerald-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
        />
        <Button
          type="submit"
          variant="outline"
          size="sm"
          className="bg-emerald-900/60 border-emerald-700 text-emerald-100 hover:bg-emerald-800 text-xs flex items-center gap-1.5"
        >
          <Crosshair className="h-3.5 w-3.5" aria-hidden="true" />
          Use Coordinates
        </Button>
        {hasSavedCoordinates && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClearSavedCoordinates}
            className="border-emerald-700 text-emerald-200 hover:bg-emerald-800 text-xs"
          >
            Clear saved coordinates
          </Button>
        )}
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
                onClick={() => onSelectGeocodedLocation(place)}
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
        {popularCities.map((stn) => {
          const isSelected = selectedStation.station_id === stn.station_id;
          return (
            <button
              key={stn.station_id}
              onClick={() => onSelectStation(stn)}
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
);
