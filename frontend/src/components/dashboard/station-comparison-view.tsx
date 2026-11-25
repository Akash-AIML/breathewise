"use client";

import React, { useCallback, useEffect, useState } from "react";
import { GitCompare, AlertTriangle, RefreshCw } from "lucide-react";
import { fetchComparisonPresets, fetchStationComparison } from "@/lib/api";
import { ComparisonApiResponse, ComparisonPreset } from "@/types/observation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ComparisonResults } from "@/components/dashboard/comparison-results";

export const StationComparisonView: React.FC = () => {
  const [presets, setPresets] = useState<ComparisonPreset[]>([]);
  const [presetsSource, setPresetsSource] = useState<string | null>(null);
  const [presetsMessage, setPresetsMessage] = useState<string | null>(null);
  const [presetsLoading, setPresetsLoading] = useState(true);
  const [presetsError, setPresetsError] = useState<string | null>(null);
  const [selectedPresetKey, setSelectedPresetKey] = useState<string | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runComparison = useCallback(async (preset: ComparisonPreset) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchStationComparison(preset.ids);
      if (res.success) {
        setComparisonData(res);
      } else {
        setError("Failed to compare stations.");
        setComparisonData(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compare stations.");
      setComparisonData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadPresets = useCallback(async () => {
    setPresetsLoading(true);
    setPresetsError(null);
    try {
      const response = await fetchComparisonPresets();
      const loaded = response.presets ?? [];
      setPresets(loaded);
      setPresetsSource(response.source);
      setPresetsMessage(response.message);
      if (loaded.length > 0) {
        setSelectedPresetKey(loaded[0].key);
        await runComparison(loaded[0]);
      } else {
        setComparisonData(null);
      }
    } catch (err) {
      setPresetsError(err instanceof Error ? err.message : "Failed to load comparison presets.");
      setPresets([]);
      setComparisonData(null);
    } finally {
      setPresetsLoading(false);
    }
  }, [runComparison]);

  useEffect(() => {
    let active = true;
    void (async () => {
      setPresetsLoading(true);
      setPresetsError(null);
      try {
        const response = await fetchComparisonPresets();
        const loaded = response.presets ?? [];
        if (!active) return;
        setPresets(loaded);
        setPresetsSource(response.source);
        setPresetsMessage(response.message);
        if (loaded.length > 0) {
          setSelectedPresetKey(loaded[0].key);
          await runComparison(loaded[0]);
        } else {
          setComparisonData(null);
        }
      } catch (err) {
        if (!active) return;
        setPresetsError(err instanceof Error ? err.message : "Failed to load comparison presets.");
        setPresets([]);
        setComparisonData(null);
      } finally {
        if (active) setPresetsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [runComparison]);

  const selectedPreset = presets.find((preset) => preset.key === selectedPresetKey) ?? null;
  const isGrid = selectedPreset?.basis === "coordinate_estimate";

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          Station Differential Comparison
        </CardTitle>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Compare live station observations when available; otherwise compare exact registered
          coordinates as clearly labelled grid estimates.
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Select Comparison Preset:
            </label>
            {(presetsError || presets.length === 0) && !presetsLoading && (
              <Button variant="outline" size="sm" onClick={() => void loadPresets()}>
                <RefreshCw className="h-3 w-3 mr-1" aria-hidden="true" />
                Reload presets
              </Button>
            )}
          </div>

          {presetsLoading && (
            <p className="text-xs text-slate-500">Loading comparison presets…</p>
          )}

          {presetsError && (
            <div
              className="rounded-lg bg-red-50 p-3 text-xs text-red-800 dark:bg-red-950/60 dark:text-red-200"
              role="alert"
            >
              <AlertTriangle className="h-4 w-4 inline mr-1 text-red-600" aria-hidden="true" />
              {presetsError}
            </div>
          )}

          {!presetsLoading && !presetsError && presets.length === 0 && (
            <div
              className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
              role="status"
            >
              No comparison presets are available from the current station source. Live CPCB
              station coordinates may be unavailable; grid estimates are shown only when the
              backend can resolve registered coordinates.
            </div>
          )}

          {presets.length > 0 && (
            <>
              <div className="flex flex-wrap gap-2">
                {presets.map((preset) => {
                  const isSelected = selectedPresetKey === preset.key;
                  return (
                    <Button
                      key={preset.key}
                      variant={isSelected ? "primary" : "outline"}
                      size="sm"
                      onClick={() => {
                        setSelectedPresetKey(preset.key);
                        void runComparison(preset);
                      }}
                      className="text-xs"
                      aria-pressed={isSelected}
                    >
                      {preset.name}
                    </Button>
                  );
                })}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Source: {presetsSource ?? "unknown"}
                {presetsMessage ? ` — ${presetsMessage}` : ""}
              </p>
            </>
          )}
        </div>

        {isLoading && (
          <div className="py-8 text-center text-xs text-slate-500">
            Evaluating comparative multi-station telemetry…
          </div>
        )}

        {error && (
          <div
            className="rounded-lg bg-red-50 p-4 text-xs text-red-800 dark:bg-red-950/60 dark:text-red-200"
            role="alert"
          >
            <AlertTriangle className="h-4 w-4 inline mr-1 text-red-600" aria-hidden="true" />
            {error}
          </div>
        )}

        {!isLoading && comparisonData && (
          <ComparisonResults data={comparisonData} isGrid={isGrid} />
        )}
      </CardContent>
    </Card>
  );
};
