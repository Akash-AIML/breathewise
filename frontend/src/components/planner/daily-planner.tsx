"use client";

import React, { useState } from "react";
import { Sunrise, Sun, Sunset, ChevronDown, ChevronUp, ShieldCheck } from "lucide-react";
import { PersonalizedPlan, RecommendationItem } from "@/types/recommendations";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface DailyPlannerProps {
  plan: PersonalizedPlan | null;
  isLoading: boolean;
}

export const DailyPlanner: React.FC<DailyPlannerProps> = ({ plan, isLoading }) => {
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-xs text-slate-500">
          Synthesizing personalized environmental routine...
        </CardContent>
      </Card>
    );
  }

  if (!plan) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-xs text-slate-500">
          Configure location and household profile to generate daily action plan.
        </CardContent>
      </Card>
    );
  }

  const renderRecommendationCard = (item: RecommendationItem) => {
    const isExpanded = expandedItem === item.id;
    const priorityVariant = {
      critical: "danger" as const,
      high: "warning" as const,
      medium: "default" as const,
      low: "neutral" as const,
    }[item.priority];

    return (
      <div
        key={item.id}
        className="rounded-xl border border-slate-200 bg-white p-4 transition-all dark:border-slate-800 dark:bg-slate-900 shadow-xs space-y-2.5"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant={priorityVariant} className="uppercase tracking-wider text-[10px]">
                {item.priority} Priority
              </Badge>
              <span className="text-[11px] font-semibold text-slate-500 uppercase">
                {item.category}
              </span>
            </div>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">{item.title}</h4>
          </div>
        </div>

        <p className="text-xs text-slate-700 dark:text-slate-300 font-medium leading-relaxed">
          {item.action}
        </p>

        <p className="text-[11px] text-slate-500 leading-normal">
          <strong>Why:</strong> {item.reason}
        </p>

        {/* Evidence Accordion */}
        <div className="border-t border-slate-100 pt-2 dark:border-slate-800">
          <button
            onClick={() => setExpandedItem(isExpanded ? null : item.id)}
            className="flex items-center justify-between w-full text-[11px] font-semibold text-emerald-700 hover:text-emerald-800 dark:text-emerald-400"
          >
            <span>Scientific Evidence & Guidelines</span>
            {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          {isExpanded && (
            <div className="mt-2 p-2.5 rounded-lg bg-emerald-50/60 text-[11px] text-emerald-950 dark:bg-emerald-950/40 dark:text-emerald-200 space-y-1">
              <p>
                <strong>Scientific Basis:</strong> {item.supporting_evidence}
              </p>
              {item.limitations && (
                <p className="text-slate-500">
                  <strong>Limitation:</strong> {item.limitations}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Risk Summary Header */}
      <Card className="border-emerald-200 bg-emerald-50/50 dark:border-emerald-800 dark:bg-emerald-950/30">
        <CardContent className="p-4 flex items-start gap-3">
          <ShieldCheck className="h-5 w-5 text-emerald-700 shrink-0 mt-0.5 dark:text-emerald-400" />
          <div className="space-y-1">
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-900 dark:text-emerald-200">
              Personalized Plan Assessment • Risk Level: {plan.environmental_assessment.risk_level.toUpperCase()}
            </h3>
            <p className="text-xs text-emerald-950 dark:text-emerald-100">
              {plan.environmental_assessment.assessment_summary}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Severe Winter Smog & Thermal Inversion Windows */}
      <Card className="border-amber-200 bg-amber-50/40 dark:border-amber-900/60 dark:bg-amber-950/20">
        <CardContent className="p-4 space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900 dark:text-amber-300">
            Winter Smog &amp; Thermal Inversion Windows
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] text-slate-700 dark:text-slate-300">
            <div className="rounded-lg bg-white/80 dark:bg-slate-900/60 p-2.5 border border-amber-100 dark:border-amber-900/40">
              <strong className="text-amber-800 dark:text-amber-300 block">6:00 – 9:30 AM • Inversion Trap</strong>
              Cold surface air traps PM2.5 &amp; vehicle soot near ground level. Avoid outdoor runs and keep windows sealed.
            </div>
            <div className="rounded-lg bg-white/80 dark:bg-slate-900/60 p-2.5 border border-sky-100 dark:border-sky-900/40">
              <strong className="text-sky-800 dark:text-sky-300 block">1:00 – 4:00 PM • Dispersion Peak</strong>
              Solar warming lifts the boundary layer. Best window for brief ventilation (if AQI &lt; 200) and essential errands.
            </div>
            <div className="rounded-lg bg-white/80 dark:bg-slate-900/60 p-2.5 border border-indigo-100 dark:border-indigo-900/40">
              <strong className="text-indigo-800 dark:text-indigo-300 block">6:30 – 10:30 PM • Evening Re-Trap</strong>
              Evening traffic emissions + cooling air re-concentrate smog. Switch to HEPA purification &amp; kitchen exhaust.
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Diurnal Time Slot Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Morning Slot */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-amber-200 dark:border-amber-900/60 text-amber-800 dark:text-amber-300">
            <Sunrise className="h-5 w-5" />
            <h3 className="text-sm font-bold">Morning Protocol (6 AM - 11 AM)</h3>
          </div>
          <div className="space-y-3">
            {plan.morning_recommendations.map(renderRecommendationCard)}
          </div>
        </div>

        {/* Afternoon Slot */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-sky-200 dark:border-sky-900/60 text-sky-800 dark:text-sky-300">
            <Sun className="h-5 w-5" />
            <h3 className="text-sm font-bold">Midday Protocol (11 AM - 5 PM)</h3>
          </div>
          <div className="space-y-3">
            {plan.afternoon_recommendations.map(renderRecommendationCard)}
          </div>
        </div>

        {/* Evening Slot */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-indigo-200 dark:border-indigo-900/60 text-indigo-800 dark:text-indigo-300">
            <Sunset className="h-5 w-5" />
            <h3 className="text-sm font-bold">Evening & Night (5 PM Onwards)</h3>
          </div>
          <div className="space-y-3">
            {plan.evening_recommendations.map(renderRecommendationCard)}
          </div>
        </div>
      </div>
    </div>
  );
};

