"use client";

import React from "react";
import { Users, X, Heart, Shield, Home, Briefcase, Activity } from "lucide-react";
import { HouseholdProfile } from "@/types/recommendations";
import { Button } from "@/components/ui/button";

interface HouseholdProfileDialogProps {
  isOpen: boolean;
  onClose: () => void;
  profile: HouseholdProfile;
  onSave: (updated: HouseholdProfile) => void;
}

export const HouseholdProfileDialog: React.FC<HouseholdProfileDialogProps> = ({
  isOpen,
  onClose,
  profile,
  onSave,
}) => {
  const [formData, setFormData] = React.useState<HouseholdProfile>(profile);

  React.useEffect(() => {
    setFormData(profile);
  }, [profile]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-dialog-title"
    >
      <div className="relative w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900 border border-slate-200 dark:border-slate-800 my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
              <Users className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h2 id="profile-dialog-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                Household Profile & Vulnerabilities
              </h2>
              <p className="text-xs text-slate-500">
                Tailors health precautions to your family's exact members. All fields optional.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Close profile setup"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="mt-5 space-y-6">
          {/* Section 1: Vulnerable Demographics */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <Heart className="h-4 w-4 text-rose-500" />
              1. Sensitive Family Members
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label className="flex items-center gap-2.5 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.has_children}
                  onChange={(e) => setFormData({ ...formData, has_children: e.target.checked })}
                  className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                />
                <span className="font-medium text-slate-800 dark:text-slate-200">Children under 12 yrs</span>
              </label>

              <label className="flex items-center gap-2.5 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.has_elderly}
                  onChange={(e) => setFormData({ ...formData, has_elderly: e.target.checked })}
                  className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                />
                <span className="font-medium text-slate-800 dark:text-slate-200">Seniors over 65 yrs</span>
              </label>

              <label className="flex items-center gap-2.5 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.has_respiratory_sensitivity}
                  onChange={(e) =>
                    setFormData({ ...formData, has_respiratory_sensitivity: e.target.checked })
                  }
                  className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                />
                <span className="font-medium text-slate-800 dark:text-slate-200">Asthma / Bronchitis / Allergy</span>
              </label>

              <label className="flex items-center gap-2.5 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.has_cardiovascular_sensitivity}
                  onChange={(e) =>
                    setFormData({ ...formData, has_cardiovascular_sensitivity: e.target.checked })
                  }
                  className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                />
                <span className="font-medium text-slate-800 dark:text-slate-200">Cardiac / Hypertension</span>
              </label>
            </div>
          </div>

          {/* Section 2: Commute & Occupation */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <Briefcase className="h-4 w-4 text-emerald-600" />
              2. Commute & Daily Routine
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Primary Commute Method:
                </label>
                <select
                  value={formData.commute_method}
                  onChange={(e) =>
                    setFormData({ ...formData, commute_method: e.target.value as any })
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs text-slate-800 focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                >
                  <option value="metro_train">Electric Metro / Rail</option>
                  <option value="bus">Public Bus (CNG / Electric / Diesel)</option>
                  <option value="two_wheeler">Motorcycle / Scooter (Two-Wheeler)</option>
                  <option value="car_ac">Car with In-Cabin AC</option>
                  <option value="walking_cycling">Walking / Bicycle</option>
                  <option value="work_from_home">Work from Home</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Outdoor Exercise Habit:
                </label>
                <select
                  value={formData.exercise_routine}
                  onChange={(e) =>
                    setFormData({ ...formData, exercise_routine: e.target.value as any })
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs text-slate-800 focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                >
                  <option value="none">No outdoor exercise</option>
                  <option value="morning_outdoor">Early Morning Jogging / Walk</option>
                  <option value="evening_outdoor">Evening Outdoor Sports / Walk</option>
                  <option value="indoor_gym">Indoor Gym / Yoga</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 3: Domestic Air Equipment */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <Home className="h-4 w-4 text-emerald-600" />
              3. Home Environment & Purifiers
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <label className="flex items-center gap-2.5 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.has_air_purifier}
                  onChange={(e) => setFormData({ ...formData, has_air_purifier: e.target.checked })}
                  className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                />
                <span className="font-medium text-slate-800 dark:text-slate-200">We own an Air Purifier</span>
              </label>

              <div>
                <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Home Carpet Area (sq.ft.):
                </label>
                <input
                  type="number"
                  min={100}
                  max={5000}
                  step={50}
                  value={formData.home_area_sqft || 600}
                  onChange={(e) =>
                    setFormData({ ...formData, home_area_sqft: parseInt(e.target.value) || 600 })
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs text-slate-800 focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4 dark:border-slate-800">
            <Button variant="ghost" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit">
              Save Household Profile
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

