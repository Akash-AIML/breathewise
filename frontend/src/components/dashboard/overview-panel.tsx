"use client";

import React from "react";
import { AlertTriangle, MapPin, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MapStation } from "@/components/dashboard/station-map";
import { ObservationSummary } from "@/components/dashboard/observation-summary";
import { PollutantBreakdown } from "@/components/dashboard/pollutant-breakdown";
import { formatCoordinates } from "@/lib/geo";
import { NormalizedObservation } from "@/types/observation";

interface OverviewPanelProps {
  selectedStation: MapStation;
  locationLabel: string | null;
  observation: NormalizedObservation | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onRetry: () => void;
}

export const OverviewPanel: React.FC<OverviewPanelProps> = ({
  selectedStation,
  locationLabel,
  observation,
  isLoading,
  error,
  onRefresh,
  onRetry,
}) => (
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
        onClick={onRefresh}
        disabled={isLoading}
        className="self-start sm:self-auto flex items-center gap-1.5"
        aria-label="Refresh live data"
      >
        <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} aria-hidden="true" />
        Refresh Observations
      </Button>
    </div>

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
              onClick={onRetry}
            >
              Retry observation request
            </Button>
          </div>
        </div>
      </div>
    )}

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
          onClick={onRetry}
        >
          Retry observation request
        </Button>
      </div>
    )}

    {!isLoading && observation && (
      <div className="space-y-6">
        <ObservationSummary observation={observation} />
        <PollutantBreakdown readings={observation.readings} />
      </div>
    )}
  </section>
);
