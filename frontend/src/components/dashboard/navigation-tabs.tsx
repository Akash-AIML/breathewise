"use client";

import React from "react";
import {
  Wind,
  Calendar,
  Home,
  Leaf,
  TrendingUp,
  GitCompare,
  MapPin,
  MessageCircle,
  type LucideIcon,
} from "lucide-react";

export type TabId =
  | "overview"
  | "planner"
  | "indoor"
  | "sustainability"
  | "trends"
  | "comparison"
  | "map"
  | "assistant";

export const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Live Dashboard", icon: Wind },
  { id: "planner", label: "Daily Planner", icon: Calendar },
  { id: "indoor", label: "Indoor Air Guide", icon: Home },
  { id: "sustainability", label: "Sustainable Transit", icon: Leaf },
  { id: "trends", label: "24-Hour Trends", icon: TrendingUp },
  { id: "comparison", label: "Station Comparison", icon: GitCompare },
  { id: "map", label: "Station Map", icon: MapPin },
  { id: "assistant", label: "AI Assistant", icon: MessageCircle },
];

interface NavigationTabsProps {
  activeTab: TabId;
  onTabChange: (id: TabId) => void;
}

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  activeTab,
  onTabChange,
}) => {
  const handleTabKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    index: number
  ) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = (index + 1) % TABS.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = (index - 1 + TABS.length) % TABS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = TABS.length - 1;
    }
    if (nextIndex === null) return;
    event.preventDefault();
    const nextId = TABS[nextIndex].id;
    onTabChange(nextId);
    document.getElementById(`tab-${nextId}`)?.focus();
  };

  return (
    <div className="border-b border-slate-200 dark:border-slate-800">
      <div
        role="tablist"
        aria-label="Dashboard Views"
        className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold"
      >
        {TABS.map((tab, index) => {
          const Icon = tab.icon;
          const isSelected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              type="button"
              aria-selected={isSelected}
              aria-controls={`panel-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
              className={`pb-3 border-b-2 flex items-center gap-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
                isSelected
                  ? "border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-300"
                  : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400"
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
