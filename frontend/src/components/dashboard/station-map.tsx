"use client";

import React from "react";
import { MapPin, Navigation } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export interface MapStation {
  name: string;
  station_id: string;
  lat: number;
  lon: number;
  city: string;
  state: string;
}

interface StationMapProps {
  stations: MapStation[];
  selectedStationId: string;
  onSelectStation: (station: MapStation) => void;
}

export const StationMap: React.FC<StationMapProps> = ({
  stations,
  selectedStationId,
  onSelectStation,
}) => {
  // SVG Geographic coordinate projection bounds for India
  // Lat: ~8.0 to 36.0, Lon: ~68.0 to 96.0
  const minLat = 8.0;
  const maxLat = 35.0;
  const minLon = 68.0;
  const maxLon = 92.0;

  const project = (lat: number, lon: number) => {
    // Invert lat for SVG y-axis
    const x = ((lon - minLon) / (maxLon - minLon)) * 100;
    const y = ((maxLat - lat) / (maxLat - minLat)) * 100;
    return { x: Math.max(5, Math.min(95, x)), y: Math.max(5, Math.min(95, y)) };
  };

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <Navigation className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          Interactive Indian Environmental Monitoring Network
        </CardTitle>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Select any verified Central Pollution Control Board (CPCB) monitoring tower across India.
        </p>
      </CardHeader>

      <CardContent>
        {/* Geographic Map Container */}
        <div className="relative w-full h-80 rounded-xl bg-slate-100 border border-slate-200 overflow-hidden dark:bg-slate-950 dark:border-slate-800">
          {/* Decorative Map Grid & Lat/Lon Cues */}
          <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:16px_16px] opacity-40 dark:bg-[radial-gradient(#334155_1px,transparent_1px)]" />

          {/* Regional labels */}
          <div className="absolute top-3 left-4 text-[10px] font-bold text-slate-400 tracking-wider">
            NORTH INDIA
          </div>
          <div className="absolute bottom-3 right-4 text-[10px] font-bold text-slate-400 tracking-wider">
            SOUTHERN CORRIDOR
          </div>

          {/* Render Station Pins */}
          {stations.map((stn) => {
            const { x, y } = project(stn.lat, stn.lon);
            const isSelected =
              stn.station_id === selectedStationId ||
              stn.name.toLowerCase().includes(selectedStationId.toLowerCase());

            return (
              <button
                key={stn.station_id}
                onClick={() => onSelectStation(stn)}
                style={{ left: `${x}%`, top: `${y}%` }}
                className={`absolute -translate-x-1/2 -translate-y-1/2 group focus:outline-none transition-transform ${
                  isSelected ? "scale-125 z-20" : "hover:scale-115 z-10"
                }`}
                aria-label={`Select monitoring station ${stn.name} in ${stn.city}`}
              >
                {/* Visual Pin */}
                <div
                  className={`flex items-center justify-center rounded-full p-1.5 shadow-md border transition-all ${
                    isSelected
                      ? "bg-emerald-600 border-white text-white ring-4 ring-emerald-400/40"
                      : "bg-white border-slate-300 text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 dark:bg-slate-800 dark:text-slate-200"
                  }`}
                >
                  <MapPin className="h-4 w-4" aria-hidden="true" />
                </div>

                {/* Floating Pin Label */}
                <div
                  className={`absolute left-1/2 -translate-x-1/2 top-full mt-1 px-2 py-0.5 rounded-md text-[10px] whitespace-nowrap font-bold shadow-xs transition-opacity ${
                    isSelected
                      ? "bg-emerald-900 text-white opacity-100"
                      : "bg-slate-800 text-white opacity-0 group-hover:opacity-100 dark:bg-slate-700"
                  }`}
                >
                  {stn.city} ({stn.lat.toFixed(1)}°N)
                </div>
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>Click any marker to inspect real-time observations</span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-600 inline-block" /> Active Station
          </span>
        </div>
      </CardContent>
    </Card>
  );
};
