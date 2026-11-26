"use client";

import { useCallback, useState } from "react";
import { HouseholdProfile } from "@/types/recommendations";

const DEFAULT_PROFILE: HouseholdProfile = {
  has_children: true,
  has_elderly: false,
  has_respiratory_sensitivity: true,
  has_cardiovascular_sensitivity: false,
  occupation_type: "indoor",
  commute_method: "two_wheeler",
  exercise_routine: "morning_outdoor",
  indoor_ventilation: "natural",
  has_air_purifier: false,
  home_area_sqft: 650,
};

export interface ProfileState {
  profile: HouseholdProfile;
  isProfileOpen: boolean;
  openProfile: () => void;
  closeProfile: () => void;
  saveProfile: (updated: HouseholdProfile) => void;
  setHomeArea: (area: number) => void;
}

export function useProfileState(): ProfileState {
  const [profile, setProfile] = useState<HouseholdProfile>(DEFAULT_PROFILE);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const openProfile = useCallback(() => setIsProfileOpen(true), []);
  const closeProfile = useCallback(() => setIsProfileOpen(false), []);
  const saveProfile = useCallback((updated: HouseholdProfile) => setProfile(updated), []);
  const setHomeArea = useCallback(
    (area: number) => setProfile((current) => ({ ...current, home_area_sqft: area })),
    []
  );

  return { profile, isProfileOpen, openProfile, closeProfile, saveProfile, setHomeArea };
}
