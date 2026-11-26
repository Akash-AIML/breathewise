"use client";

import React, { useState } from "react";
import { Leaf, ShieldCheck, Users, Copy, Check, Calculator } from "lucide-react";
import { HouseholdProfile, SustainableAlternative } from "@/types/recommendations";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SustainableAlternativesProps {
  alternatives: SustainableAlternative[];
  profile?: HouseholdProfile;
  currentAqi?: number | null;
  stationName?: string;
}

const COMMUTE_EMISSION_FACTORS: Record<HouseholdProfile["commute_method"], { label: string; gPerKm: number; exposureNote: string }> = {
  car_ac: { label: "Solo Petrol/Diesel Car (AC)", gPerKm: 150, exposureNote: "Cabin recirculation cuts PM2.5 ~35%, highest tailpipe CO₂." },
  two_wheeler: { label: "Two-Wheeler (Scooter/Bike)", gPerKm: 65, exposureNote: "Highest roadside diesel & PM2.5 inhalation (up to 3× ambient)." },
  bus: { label: "Public Bus (CNG / Electric)", gPerKm: 32, exposureNote: "79% lower CO₂ per passenger-km than a solo car." },
  metro_train: { label: "Electric Metro / Rail", gPerKm: 14, exposureNote: "91% lower CO₂ than a solo car; filtered carriages cut PM2.5 by 50–70%." },
  walking_cycling: { label: "Walking / Cycling", gPerKm: 0, exposureNote: "Zero tailpipe CO₂; avoid during AQI > 200 due to 4× breathing rate." },
  work_from_home: { label: "Work from Home / Remote", gPerKm: 0, exposureNote: "Eliminates 100% of commute emissions and roadside smog exposure." },
};

const TARGET_OPTIONS: { id: "metro_train" | "bus" | "work_from_home"; label: string }[] = [
  { id: "metro_train", label: "Electric Metro" },
  { id: "bus", label: "Public CNG/EV Bus" },
  { id: "work_from_home", label: "Remote / Carpool Split" },
];

export const SustainableAlternativesView: React.FC<SustainableAlternativesProps> = ({
  alternatives,
  profile,
  currentAqi,
  stationName = "your area",
}) => {
  const [dailyKm, setDailyKm] = useState<number>(16);
  const [targetMode, setTargetMode] = useState<"metro_train" | "bus" | "work_from_home">("metro_train");
  const [copied, setCopied] = useState(false);

  const currentMode = profile?.commute_method ?? "two_wheeler";
  const currentFactor = COMMUTE_EMISSION_FACTORS[currentMode];
  const targetFactor = COMMUTE_EMISSION_FACTORS[targetMode];

  // 22 commute days/month, 260 days/year
  const deltaGPerKm = Math.max(0, currentFactor.gPerKm - targetFactor.gPerKm);
  const monthlyCo2SavedKg = Number(((deltaGPerKm * dailyKm * 22) / 1000).toFixed(1));
  const annualCo2SavedKg = Number(((deltaGPerKm * dailyKm * 260) / 1000).toFixed(0));
  const isHighSmog = (currentAqi ?? 0) > 200;

  const communityBrief =
    `BreatheWise Community & School Smog Brief (${stationName}` +
    `${currentAqi != null ? ` • Live AQI ${currentAqi}` : ""}):\n` +
    (isHighSmog
      ? "• Schools/RWAs: Move morning assemblies & outdoor sports indoors during 6–10 AM thermal inversion.\n" +
        "• Residents: Form 2–4 person Metro/AC carpools; strictly halt open leaf/waste burning & check DG exhaust.\n" +
        "• Vulnerable groups: Use N95/FFP2 masks outdoors and keep HEPA/kitchen exhaust active."
      : "• Schools/RWAs: Schedule outdoor play during 1–4 PM dispersion window; monitor AQI before evening events.\n" +
        "• Residents: Prefer Metro/bus/carpools for daily errands and maintain zero open biomass burning.");

  const handleCopyBrief = async () => {
    try {
      await navigator.clipboard.writeText(communityBrief);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Direct Impact of Your Choices Calculator */}
      <Card className="border-emerald-200 bg-emerald-50/40 dark:border-emerald-800 dark:bg-emerald-950/20 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Calculator className="h-4 w-4 text-emerald-700 dark:text-emerald-400" aria-hidden="true" />
            Direct Impact of Your Commute Choice
          </CardTitle>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Tailored to your profile ({currentFactor.label}). Adjust your daily round-trip distance to see the direct emissions and inhalation impact.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="daily-commute-km" className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Daily Round-Trip Distance: <strong>{dailyKm} km/day</strong>
              </label>
              <input
                id="daily-commute-km"
                type="range"
                min={4}
                max={60}
                step={2}
                value={dailyKm}
                aria-valuetext={`${dailyKm} kilometers per day`}
                onChange={(e) => setDailyKm(Number(e.target.value))}
                className="w-full accent-emerald-700"
              />
            </div>

            <div>
              <span className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Compare Switching To:
              </span>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Target low-emission commute mode">
                {TARGET_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setTargetMode(opt.id)}
                    aria-pressed={targetMode === opt.id}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors ${
                      targetMode === opt.id
                        ? "bg-emerald-700 text-white border-emerald-700"
                        : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-700"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-xl border border-emerald-200 bg-white p-3 dark:border-emerald-800 dark:bg-slate-900">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Monthly CO₂ Saved</span>
              <p className="text-xl font-black text-emerald-700 dark:text-emerald-400">
                {monthlyCo2SavedKg} kg
              </p>
              <span className="text-[11px] text-slate-500">Across 22 commute days</span>
            </div>

            <div className="rounded-xl border border-emerald-200 bg-white p-3 dark:border-emerald-800 dark:bg-slate-900">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Annual CO₂ Cut</span>
              <p className="text-xl font-black text-emerald-700 dark:text-emerald-400">
                {annualCo2SavedKg} kg/yr
              </p>
              <span className="text-[11px] text-slate-500">ARAI/CEA baseline delta</span>
            </div>

            <div className="rounded-xl border border-emerald-200 bg-white p-3 dark:border-emerald-800 dark:bg-slate-900">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Personal PM2.5 Impact</span>
              <p className="text-xs font-bold text-slate-800 dark:text-slate-200 mt-1 leading-snug">
                {targetFactor.exposureNote}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Documented Transit Table */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Leaf className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            Sustainable Low-Emission Mobility &amp; Exposure Analysis
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

      {/* Community & Neighborhood Smog Action Brief */}
      <Card className="border-indigo-200 bg-indigo-50/40 dark:border-indigo-900/60 dark:bg-indigo-950/20 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-700 dark:text-indigo-400" aria-hidden="true" />
              Community, RWA &amp; School Smog Action Brief
            </CardTitle>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              Shareable neighborhood guidance for {stationName} to coordinate carpools, school recess, and zero waste burning.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCopyBrief}
            className="shrink-0 text-xs flex items-center gap-1.5"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied Brief" : "Copy Community Brief"}
          </Button>
        </CardHeader>
        <CardContent>
          <pre className="whitespace-pre-wrap font-sans text-xs text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-indigo-100 dark:border-indigo-900 rounded-lg p-3 leading-relaxed">
            {communityBrief}
          </pre>
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
