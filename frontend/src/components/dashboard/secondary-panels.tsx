"use client";

import React from "react";
import { StationComparisonView } from "@/components/dashboard/station-comparison-view";
import { ChatAssistant } from "@/components/assistant/chat-assistant";
import { HouseholdProfile } from "@/types/recommendations";

interface ComparisonPanelProps {}

export const ComparisonPanel: React.FC<ComparisonPanelProps> = () => (
  <section
    id="panel-comparison"
    role="tabpanel"
    aria-labelledby="tab-comparison"
    tabIndex={0}
    className="focus:outline-none"
  >
    <StationComparisonView />
  </section>
);

interface AssistantPanelProps {
  lat: number;
  lon: number;
  currentAqi?: number | null;
  profile: HouseholdProfile;
}

export const AssistantPanel: React.FC<AssistantPanelProps> = ({
  lat,
  lon,
  currentAqi,
  profile,
}) => (
  <section
    id="panel-assistant"
    role="tabpanel"
    aria-labelledby="tab-assistant"
    tabIndex={0}
    className="h-[72vh] flex flex-col rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-sm focus:outline-none"
  >
    <h2 id="assistant-heading" className="sr-only">
      BreatheWise AI Assistant
    </h2>
    <ChatAssistant
      lat={lat}
      lon={lon}
      currentAqi={currentAqi}
      profile={profile}
      className="flex-1"
    />
  </section>
);
