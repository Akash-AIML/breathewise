"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { NormalizedPollutantReading } from "@/types/observation";

interface PollutantBreakdownProps {
  readings: Record<string, NormalizedPollutantReading>;
}

export const PollutantBreakdown: React.FC<PollutantBreakdownProps> = ({
  readings,
}) => (
  <div>
    <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-4">
      Criteria Pollutant Breakdown
    </h3>
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {Object.entries(readings).map(([key, reading]) => (
        <Card key={key} className="p-4 text-center">
          <span className="text-xs font-semibold text-slate-500 block mb-1">
            {reading.pollutant}
          </span>
          <span className="text-2xl font-bold text-slate-900 dark:text-slate-100 block">
            {reading.value}
          </span>
          <span className="text-[10px] font-semibold text-slate-500 uppercase block">
            Average concentration
          </span>
          <span className="text-[11px] text-slate-500 block mb-2">
            {reading.unit ?? "Unit not provided by source"}
          </span>
          {(reading.min_value !== undefined || reading.max_value !== undefined) && (
            <span className="text-[10px] text-slate-500 block">
              Min {reading.min_value ?? "—"} / Max {reading.max_value ?? "—"}
            </span>
          )}
          {reading.sub_index !== undefined && reading.sub_index !== null && (
            <div className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 rounded-sm py-0.5 dark:bg-emerald-950/60 dark:text-emerald-300">
              Sub-Index: {reading.sub_index}
            </div>
          )}
        </Card>
      ))}
    </div>
  </div>
);
