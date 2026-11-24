"use client";

import React, { useState } from "react";
import { Home, Wind, AlertTriangle, ShieldCheck, Check, Sparkles } from "lucide-react";
import { IndoorGuidance } from "@/types/recommendations";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface IndoorAssistantProps {
  guidance: IndoorGuidance | null;
  onAreaChange?: (area: number) => void;
}

export const IndoorAssistant: React.FC<IndoorAssistantProps> = ({ guidance, onAreaChange }) => {
  const [areaInput, setAreaInput] = useState(600);

  if (!guidance) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-xs text-slate-500">
          Loading evidence-based indoor air quality recommendations...
        </CardContent>
      </Card>
    );
  }

  const handleUpdateArea = (e: React.FormEvent) => {
    e.preventDefault();
    if (onAreaChange) onAreaChange(areaInput);
  };

  return (
    <div className="space-y-6">
      {/* HEPA CADR Sizing Tool */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Wind className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            Scientific HEPA Air Purifier Sizing Calculator (5 ACH Standard)
          </CardTitle>
          <p className="text-xs text-slate-500">
            Calculated Clean Air Delivery Rate (CADR) required to exchange domestic air 5 times per hour.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleUpdateArea} className="flex flex-wrap items-center gap-3">
            <label htmlFor="area-input" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Carpet Area (sq.ft.):
            </label>
            <input
              id="area-input"
              type="number"
              min={100}
              max={3000}
              step={50}
              value={areaInput}
              onChange={(e) => setAreaInput(parseInt(e.target.value) || 600)}
              className="w-28 rounded-lg border border-slate-300 p-1.5 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
            <Button variant="outline" size="sm" type="submit" className="text-xs">
              Recalculate
            </Button>
          </form>

          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-800 dark:bg-emerald-950/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
                Recommended Minimum CADR
              </span>
              <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                {guidance.hepa_sizing_explanation}
              </p>
            </div>
            <div className="text-right shrink-0">
              <span className="text-4xl font-black text-emerald-900 dark:text-emerald-200">
                {guidance.hepa_sizing_cadr_m3_hr}
              </span>
              <span className="text-xs font-bold text-slate-500 block">m³/hr CADR</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Houseplant Marketing Myth vs Reality Banner */}
      <Card className="border-amber-300 bg-amber-50/60 dark:border-amber-900/60 dark:bg-amber-950/30">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-bold text-amber-900 dark:text-amber-200 uppercase tracking-wider">
              Scientific Evidence Disclosure: Houseplants vs Air Purifiers
            </h4>
            <p className="text-amber-950 dark:text-amber-100 leading-relaxed">
              {guidance.houseplant_scientific_disclaimer}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Protocols Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Filter Maintenance Rules */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Filter Maintenance Rules
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-400">
              {guidance.filter_maintenance_tips.map((tip, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Cooking Smoke Precautions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Kitchen Smoke & Tadka Control
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-400">
              {guidance.cooking_smoke_precautions.map((tip, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Practical Low-Cost Precautions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Low-Cost Household Defenses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-400">
              {guidance.practical_low_cost_precautions.map((tip, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
