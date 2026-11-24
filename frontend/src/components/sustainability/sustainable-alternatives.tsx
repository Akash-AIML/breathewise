"use client";

import React from "react";
import { Leaf, Train, Bus, Bike, AlertTriangle, ShieldCheck } from "lucide-react";
import { SustainableAlternative } from "@/types/recommendations";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface SustainableAlternativesProps {
  alternatives: SustainableAlternative[];
}

export const SustainableAlternativesView: React.FC<SustainableAlternativesProps> = ({
  alternatives,
}) => {
  return (
    <div className="space-y-6">
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Leaf className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            Sustainable Low-Emission Mobility & Exposure Analysis
          </CardTitle>
          <p className="text-xs text-slate-500">
            Documented emission factors based on ARAI and Central Electricity Authority (CEA) baselines (solo car baseline: 150 g CO2/km).
          </p>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600 dark:text-slate-400" aria-label="Sustainable mobility comparison">
              <thead className="bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                <tr>
                  <th scope="col" className="px-4 py-3">Transit Mode</th>
                  <th scope="col" className="px-4 py-3">Emission Factor</th>
                  <th scope="col" className="px-4 py-3">CO₂ Reduction</th>
                  <th scope="col" className="px-4 py-3">Personal Inhalation Exposure Trade-Off</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {alternatives.map((alt, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-900/50">
                    <td className="px-4 py-3 font-semibold text-slate-900 dark:text-slate-100">
                      {alt.mode}
                    </td>
                    <td className="px-4 py-3">
                      <strong>{alt.emission_factor_g_co2_per_km}</strong> g CO₂/pass-km
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="success">
                        -{alt.estimated_emission_reduction_pct}% CO₂
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-[11px] leading-relaxed">
                      <p>{alt.personal_exposure_mitigation}</p>
                      {alt.condition_dependent_note && (
                        <p className="mt-1 font-semibold text-amber-700 dark:text-amber-400">
                          {alt.condition_dependent_note}
                        </p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Critical Distinction Banner */}
      <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4 dark:border-sky-900/60 dark:bg-sky-950/30 flex items-start gap-3">
        <ShieldCheck className="h-5 w-5 text-sky-700 shrink-0 mt-0.5 dark:text-sky-300" />
        <div className="space-y-1 text-xs text-sky-950 dark:text-sky-100">
          <h4 className="font-bold uppercase tracking-wider">
            Critical Environmental Engineering Principle: Emission vs. Exposure
          </h4>
          <p className="leading-relaxed">
            Reducing city-wide carbon emissions (societal benefit) must not come at the expense of acute personal particulate inhalation (individual health hazard). During severe smog episodes, cycling or walking along congested diesel thoroughfares increases inhaled toxic particulate dose by over 400% compared to remaining inside an air-filtered electric metro carriage.
          </p>
        </div>
      </div>
    </div>
  );
};

