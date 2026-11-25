"use client";

import React from "react";
import { Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HistoricalTrendChart } from "@/components/dashboard/historical-trend-chart";
import { DailyPlanner } from "@/components/planner/daily-planner";
import { IndoorAssistant } from "@/components/indoor/indoor-assistant";
import { SustainableAlternativesView } from "@/components/sustainability/sustainable-alternatives";
import { NormalizedObservation } from "@/types/observation";
import { IndoorGuidance, PersonalizedPlan } from "@/types/recommendations";

interface PlannerPanelProps {
  plan: PersonalizedPlan | null;
  isLoading: boolean;
  onConfigureProfile: () => void;
}

export const PlannerPanel: React.FC<PlannerPanelProps> = ({
  plan,
  isLoading,
  onConfigureProfile,
}) => (
  <section
    id="panel-planner"
    role="tabpanel"
    aria-labelledby="tab-planner"
    tabIndex={0}
    className="space-y-4 focus:outline-none"
  >
    <div className="flex items-center justify-between">
      <h2 id="planner-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
        Personalized Daily Action Planner
      </h2>
      <Button
        variant="outline"
        size="sm"
        onClick={onConfigureProfile}
        className="text-xs flex items-center gap-1.5"
      >
        <Users className="h-3.5 w-3.5" />
        Adjust Household Vulnerabilities
      </Button>
    </div>
    <DailyPlanner plan={plan} isLoading={isLoading} />
  </section>
);

interface IndoorPanelProps {
  guidance: IndoorGuidance | null;
  onAreaChange: (area: number) => void;
}

export const IndoorPanel: React.FC<IndoorPanelProps> = ({
  guidance,
  onAreaChange,
}) => (
  <section
    id="panel-indoor"
    role="tabpanel"
    aria-labelledby="tab-indoor"
    tabIndex={0}
    className="space-y-4 focus:outline-none"
  >
    <h2 id="indoor-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
      Evidence-Based Indoor Air Quality Assistant
    </h2>
    <IndoorAssistant guidance={guidance} onAreaChange={onAreaChange} />
  </section>
);

interface SustainabilityPanelProps {
  alternatives: PersonalizedPlan["sustainable_alternatives"];
}

export const SustainabilityPanel: React.FC<SustainabilityPanelProps> = ({
  alternatives,
}) => (
  <section
    id="panel-sustainability"
    role="tabpanel"
    aria-labelledby="tab-sustainability"
    tabIndex={0}
    className="space-y-4 focus:outline-none"
  >
    <h2 id="sustainability-heading" className="text-xl font-bold text-slate-900 dark:text-slate-100">
      Sustainable Mobility &amp; Emission Impact
    </h2>
    <SustainableAlternativesView alternatives={alternatives} />
  </section>
);

interface TrendsPanelProps {
  observation: NormalizedObservation | null;
  stationName: string;
}

export const TrendsPanel: React.FC<TrendsPanelProps> = ({
  observation,
  stationName,
}) => (
  <section
    id="panel-trends"
    role="tabpanel"
    aria-labelledby="tab-trends"
    tabIndex={0}
    className="space-y-6 focus:outline-none"
  >
    {observation?.hourly_trend && observation.hourly_trend.length > 0 ? (
      <HistoricalTrendChart
        data={observation.hourly_trend}
        stationName={stationName}
        sourceLabel={observation.provider}
      />
    ) : (
      <div className="py-12 text-center text-xs text-slate-500">
        No hourly trend data currently available for {stationName}.
      </div>
    )}
  </section>
);
