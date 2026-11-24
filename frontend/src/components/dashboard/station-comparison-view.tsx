"use client";

import React, { useState } from "react";
import { GitCompare, CheckCircle, AlertTriangle, ArrowRight, ShieldAlert } from "lucide-react";
import { fetchStationComparison } from "@/lib/api";
import { ComparisonApiResponse } from "@/types/observation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AQIBadge } from "@/components/aqi/aqi-badge";

const PRESET_COMPARISONS = [
  {
    name: "Delhi Comparison: Central (ITO) vs Industrial (Anand Vihar)",
    ids: ["cpcb_delhi_ito", "cpcb_delhi_anand_vihar"],
  },
  {
    name: "Metropolitan Cross-City: Delhi vs Mumbai vs Bengaluru",
    ids: ["cpcb_delhi_ito", "cpcb_mumbai_bandra", "cpcb_bengaluru_btm"],
  },
  {
    name: "Indo-Gangetic Plain: Delhi vs Lucknow vs Kolkata",
    ids: ["cpcb_delhi_ito", "cpcb_lucknow_lalbagh", "cpcb_kolkata_victoria"],
  },
];

export const StationComparisonView: React.FC = () => {
  const [selectedPreset, setSelectedPreset] = useState(PRESET_COMPARISONS[0]);
  const [comparisonData, setComparisonData] = useState<ComparisonApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async (stationIds: string[]) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchStationComparison(stationIds);
      if (res.success) {
        setComparisonData(res);
      } else {
        setError("Failed to compare stations.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to compare stations.");
      setComparisonData(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          Station Differential Comparison
        </CardTitle>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Compare multi-point pollution exposure across residential, commercial, and industrial corridors.
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Comparison Presets */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            Select Comparison Preset:
          </label>
          <div className="flex flex-wrap gap-2">
            {PRESET_COMPARISONS.map((preset) => {
              const isSelected = selectedPreset.name === preset.name;
              return (
                <Button
                  key={preset.name}
                  variant={isSelected ? "primary" : "outline"}
                  size="sm"
                  onClick={() => {
                    setSelectedPreset(preset);
                    handleCompare(preset.ids);
                  }}
                  className="text-xs"
                >
                  {preset.name}
                </Button>
              );
            })}
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="py-8 text-center text-xs text-slate-500">
            Evaluating comparative multi-station telemetry...
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg bg-red-50 p-4 text-xs text-red-800 dark:bg-red-950/60 dark:text-red-200">
            <AlertTriangle className="h-4 w-4 inline mr-1 text-red-600" />
            {error}
          </div>
        )}

        {/* Results */}
        {!isLoading && comparisonData && (
          <div className="space-y-4">
            {/* Differential Summary Banner */}
            {comparisonData.differential && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-800 dark:bg-emerald-950/40">
                <div className="flex items-start gap-3">
                  <ShieldAlert className="h-5 w-5 text-emerald-700 shrink-0 mt-0.5 dark:text-emerald-400" aria-hidden="true" />
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-900 dark:text-emerald-200">
                      Differential Exposure Assessment
                    </h4>
                    <p className="text-xs text-emerald-950 dark:text-emerald-100 leading-relaxed">
                      {comparisonData.differential.summary}
                    </p>
                    <div className="flex flex-wrap gap-4 pt-1 text-[11px] font-semibold text-emerald-800 dark:text-emerald-300">
                      <span>
                        AQI Spread: <strong>{comparisonData.differential.aqi_difference} points</strong>
                      </span>
                      {comparisonData.differential.pm25_difference_ug_m3 !== undefined && (
                        <span>
                          PM2.5 Delta: <strong>{comparisonData.differential.pm25_difference_ug_m3} µg/m³</strong>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Side-by-Side Station Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {comparisonData.observations.map((obs) => (
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
        )}
      </CardContent>
    </Card>
  );
};
