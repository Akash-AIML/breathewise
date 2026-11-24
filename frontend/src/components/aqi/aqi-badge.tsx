import React from "react";
import { AQICategory } from "@/types/observation";
import { cn } from "@/lib/utils";
import { ShieldCheck, AlertCircle, AlertTriangle, Flame, Skull } from "lucide-react";

interface AQIBadgeProps {
  category?: AQICategory | null;
  aqi?: number | null;
  className?: string;
}

export const AQIBadge: React.FC<AQIBadgeProps> = ({ category, aqi, className }) => {
  if (!category || aqi === undefined || aqi === null) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700",
          className
        )}
        aria-label="Air Quality Index Data Unavailable"
      >
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        <span>AQI Unavailable</span>
      </span>
    );
  }

  // Accessible colors with WCAG 2.2 AA contrast ratios (>4.5:1 text-to-background)
  const categoryStyles: Record<
    AQICategory,
    { bg: string; text: string; border: string; icon: React.ReactNode }
  > = {
    Good: {
      bg: "bg-emerald-50 dark:bg-emerald-950/60",
      text: "text-emerald-900 dark:text-emerald-200",
      border: "border-emerald-300 dark:border-emerald-800",
      icon: <ShieldCheck className="h-4 w-4 text-emerald-700 dark:text-emerald-300" aria-hidden="true" />,
    },
    Satisfactory: {
      bg: "bg-lime-50 dark:bg-lime-950/60",
      text: "text-lime-900 dark:text-lime-200",
      border: "border-lime-300 dark:border-lime-800",
      icon: <ShieldCheck className="h-4 w-4 text-lime-700 dark:text-lime-300" aria-hidden="true" />,
    },
    Moderate: {
      bg: "bg-amber-50 dark:bg-amber-950/60",
      text: "text-amber-900 dark:text-amber-200",
      border: "border-amber-300 dark:border-amber-800",
      icon: <AlertTriangle className="h-4 w-4 text-amber-700 dark:text-amber-300" aria-hidden="true" />,
    },
    Poor: {
      bg: "bg-orange-50 dark:bg-orange-950/60",
      text: "text-orange-950 dark:text-orange-200",
      border: "border-orange-300 dark:border-orange-800",
      icon: <AlertCircle className="h-4 w-4 text-orange-700 dark:text-orange-300" aria-hidden="true" />,
    },
    "Very Poor": {
      bg: "bg-red-50 dark:bg-red-950/60",
      text: "text-red-950 dark:text-red-200",
      border: "border-red-300 dark:border-red-800",
      icon: <Flame className="h-4 w-4 text-red-700 dark:text-red-300" aria-hidden="true" />,
    },
    Severe: {
      bg: "bg-rose-100 dark:bg-rose-950",
      text: "text-rose-950 dark:text-rose-100",
      border: "border-rose-400 dark:border-rose-700",
      icon: <Skull className="h-4 w-4 text-rose-800 dark:text-rose-200" aria-hidden="true" />,
    },
  };

  const style = categoryStyles[category];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-lg border px-3 py-1 text-sm font-semibold shadow-xs",
        style.bg,
        style.text,
        style.border,
        className
      )}
      role="status"
      aria-label={`Air Quality Index ${aqi}, Category: ${category}`}
    >
      {style.icon}
      <span>
        {category} • <strong className="font-bold">{aqi}</strong> AQI
      </span>
    </span>
  );
};
