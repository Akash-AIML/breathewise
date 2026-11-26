"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { fetchAirQuality, fetchPersonalizedPlan } from "@/lib/api";
import { NormalizedObservation } from "@/types/observation";
import { HouseholdProfile, PersonalizedPlan } from "@/types/recommendations";

interface DashboardDataInput {
  selectedStation: MapStation;
  profile: HouseholdProfile;
}

export interface DashboardDataState {
  observation: NormalizedObservation | null;
  plan: PersonalizedPlan | null;
  isLoading: boolean;
  isPlanLoading: boolean;
  error: string | null;
  refreshObservation: () => void;
  retryObservation: () => void;
}

/** Observation, personalized plan and their independent loading/error state. */
export function useDashboardData({ selectedStation, profile }: DashboardDataInput): DashboardDataState {
  const [observation, setObservation] = useState<NormalizedObservation | null>(null);
  const [plan, setPlan] = useState<PersonalizedPlan | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const observationRequestRef = useRef(0);
  const planRequestRef = useRef<{ id: number; key: string }>({ id: 0, key: "" });
  const { lat, lon } = selectedStation;

  const loadData = useCallback(async (lat: number, lon: number, bypassCache = false) => {
    const requestId = ++observationRequestRef.current;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchAirQuality(lat, lon, bypassCache);
      // A refresh/retry or a newer station can supersede this response.
      if (requestId !== observationRequestRef.current) return;
      if (res.success && res.data) {
        setObservation(res.data);
        setError(null);
      } else if (res.success) {
        // Honest empty state: the provider responded but has no usable data.
        setObservation(null);
        setError(null);
      } else {
        setError(res.message || "No data available for this location.");
        setObservation(null);
      }
    } catch (err: unknown) {
      if (requestId !== observationRequestRef.current) return;
      const message =
        err instanceof Error ? err.message : "Failed to communicate with air quality service.";
      setError(message);
      setObservation(null);
    } finally {
      if (requestId === observationRequestRef.current) setIsLoading(false);
    }
  }, []);

  const loadPlan = useCallback(async (lat: number, lon: number, prof: HouseholdProfile) => {
    const key = JSON.stringify([lat, lon, prof]);
    const id = planRequestRef.current.id + 1;
    planRequestRef.current = { id, key };
    setIsPlanLoading(true);
    try {
      const planRes = await fetchPersonalizedPlan(lat, lon, prof);
      if (id !== planRequestRef.current.id || key !== planRequestRef.current.key) return;
      setPlan(planRes);
    } catch {
      if (id !== planRequestRef.current.id || key !== planRequestRef.current.key) return;
      setPlan(null);
    } finally {
      if (id === planRequestRef.current.id && key === planRequestRef.current.key) {
        setIsPlanLoading(false);
      }
    }
  }, []);

  // Observation data depends only on coordinates: renaming a station must not
  // issue another provider request.
  useEffect(() => {
    const timer = window.setTimeout(() => void loadData(lat, lon), 0);
    return () => window.clearTimeout(timer);
  }, [lat, lon, loadData]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPlan(lat, lon, profile), 0);
    return () => window.clearTimeout(timer);
  }, [lat, lon, profile, loadPlan]);

  const refreshObservation = useCallback(
    () => void loadData(lat, lon, true),
    [lat, lon, loadData]
  );
  const retryObservation = useCallback(
    () => void loadData(lat, lon, false),
    [lat, lon, loadData]
  );

  return {
    observation,
    plan,
    isLoading,
    isPlanLoading,
    error,
    refreshObservation,
    retryObservation,
  };
}
