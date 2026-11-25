"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { MapStation, StationMap } from "@/components/dashboard/station-map";

interface MapPanelProps {
  liveStations: MapStation[];
  stationsSource: string | null;
  selectedStationId: string;
  onSelectStation: (station: MapStation) => void;
  onRetryStations: () => void;
}

export const MapPanel: React.FC<MapPanelProps> = ({
  liveStations,
  stationsSource,
  selectedStationId,
  onSelectStation,
  onRetryStations,
}) => (
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
          selectedStationId={selectedStationId}
          onSelectStation={onSelectStation}
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
          onClick={onRetryStations}
        >
          Retry station lookup
        </Button>
      </div>
    )}
  </section>
);
