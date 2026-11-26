import React from "react";
import { Database } from "lucide-react";

export const Footer = () => {
  return (
    <footer className="border-t border-slate-200 bg-slate-50 py-10 dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          <div>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
              BreatheWise Evidence Guarantee
            </h4>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              We never fabricate air quality readings, station metadata, or medical claims. All recommendations derive from deterministic engineering logic, grounded strictly in validated Central Pollution Control Board (CPCB) standards.
            </p>
          </div>

          <div>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
              Verified Data Providers
            </h4>
            <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1">
              <li className="flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
                Central Pollution Control Board (CPCB)
              </li>
              <li className="flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
                OpenAQ Global Air Quality Network (v3)
              </li>
              <li className="flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
                Open-Meteo / Copernicus CAMS Grid
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
              Accessibility & Standards
            </h4>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Engineered to meet WCAG 2.2 Level AA accessibility guidelines. Featuring non-color-reliant visual hierarchy, screen-reader landmarks, and visible focus management.
            </p>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-6 text-center text-xs text-slate-500 dark:border-slate-800 dark:text-slate-500">
          © {new Date().getFullYear()} BreatheWise — PromptWars Virtual Challenge 6. Built for Indian Families and Communities.
        </div>
      </div>
    </footer>
  );
};

