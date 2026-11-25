"use client";

import React from "react";
import { AlertTriangle, CheckCircle, ShieldAlert } from "lucide-react";
import { AQIBadge } from "@/components/aqi/aqi-badge";
import { ComparisonApiResponse } from "@/types/observation";

interface ComparisonResultsProps {
  data: ComparisonApiResponse;
  isGrid: boolean;
}

export const ComparisonResults: React.FC<ComparisonResultsProps> = ({ data, isGrid }) => (
  <div className="space-y-4">
    <div
      className={`rounded-lg p-3 text-xs ${
        data.basis === "live_station"
          ? "bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
          : "bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
      }`}
      role="status"
    >
      {data.basis === "live_station" ? (
        <CheckCircle className="h-4 w-4 inline mr-1" aria-hidden="true" />
      ) : (
        <AlertTriangle className="h-4 w-4 inline mr-1" aria-hidden="true" />
      )}
      {data.message ||
        (data.basis === "live_station"
          ? "Live CPCB station observations."
          : "Coordinate-grid estimates, not physical station observations.")}
    </div>

    {data.differential && (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-800 dark:bg-emerald-950/40">
        <div className="flex items-start gap-3">
          <ShieldAlert
            className="h-5 w-5 text-emerald-700 shrink-0 mt-0.5 dark:text-emerald-400"
            aria-hidden="true"
          />
          <div className="space-y-1">
            <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-900 dark:text-emerald-200">
              Differential Exposure Assessment
            </h4>
            <p className="text-xs text-emerald-950 dark:text-emerald-100 leading-relaxed">
              {data.differential.summary}
            </p>
            <div className="flex flex-wrap gap-4 pt-1 text-[11px] font-semibold text-emerald-800 dark:text-emerald-300">
              <span>
                AQI Spread: <strong>{data.differential.aqi_difference} points</strong>
              </span>
              {data.differential.pm25_difference_ug_m3 !== undefined && (
                <span>
                  PM2.5 Delta:{" "}
                  <strong>{data.differential.pm25_difference_ug_m3} µg/m³</strong>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    )}

    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {data.observations.map((obs) => (
        <div
          key={obs.station.station_id}
          className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                {obs.station.station_name}
              </h4>
              <p className="text-[11px] text-slate-500">
                {obs.station.city}, {obs.station.state}
              </p>
            </div>
            <span className="text-xl font-black text-slate-900 dark:text-slate-100">
              {obs.calculated_aqi ?? "N/A"}
            </span>
          </div>

          <p className="text-[10px] text-slate-500 dark:text-slate-400">
            Provider: {obs.provider}
            {isGrid ? " · grid estimate at registered coordinates" : " · live station"}
          </p>

          <div>
            <AQIBadge category={obs.aqi_category} aqi={obs.calculated_aqi} />
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] border-t border-slate-100 pt-2 dark:border-slate-800">
            <div>
              <span className="text-slate-500">PM2.5:</span>{" "}
              <strong>{obs.readings["PM2.5"]?.value ?? "N/A"} µg/m³</strong>
            </div>
            <div>
              <span className="text-slate-500">PM10:</span>{" "}
              <strong>{obs.readings["PM10"]?.value ?? "N/A"} µg/m³</strong>
            </div>
            <div>
              <span className="text-slate-500">NO2:</span>{" "}
              <strong>{obs.readings["NO2"]?.value ?? "N/A"} µg/m³</strong>
            </div>
            <div>
              <span className="text-slate-500">Dominant:</span>{" "}
              <strong>{obs.dominant_pollutant ?? "N/A"}</strong>
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
);
