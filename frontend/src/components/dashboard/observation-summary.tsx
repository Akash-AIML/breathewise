"use client";

import React from "react";
import { Clock, Database } from "lucide-react";
import { AQIBadge } from "@/components/aqi/aqi-badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { formatCoordinates } from "@/lib/geo";
import { NormalizedObservation } from "@/types/observation";

interface ObservationSummaryProps {
  observation: NormalizedObservation;
}

const getRelativeTime = (isoString?: string) => {
  if (!isoString) return "";
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.max(0, Math.floor(diffMs / 60000));
  if (mins < 60) return `${mins} mins ago`;
  const hours = Math.floor(mins / 60);
  return `${hours} hour${hours > 1 ? "s" : ""} ago`;
};

export const ObservationSummary: React.FC<ObservationSummaryProps> = ({
  observation,
}) => (
  <>
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
            Data Provenance &amp; Sensor Verification
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
  </>
);
