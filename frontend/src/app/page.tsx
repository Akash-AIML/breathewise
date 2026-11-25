"use client";

import React, { useState, useEffect } from "react";
import { MapStation } from "@/components/dashboard/station-map";
import { HeroBanner } from "@/components/dashboard/hero-banner";
import { NavigationTabs, TabId } from "@/components/dashboard/navigation-tabs";
import { OverviewPanel } from "@/components/dashboard/overview-panel";
import {
  PlannerPanel,
  IndoorPanel,
  SustainabilityPanel,
  TrendsPanel,
} from "@/components/dashboard/insights-panels";
import { MapPanel } from "@/components/dashboard/map-panel";
import { ComparisonPanel, AssistantPanel } from "@/components/dashboard/secondary-panels";
import { HouseholdProfileDialog } from "@/components/profile/household-profile-dialog";
import {
  useLocationState,
  POPULAR_CITIES,
} from "@/components/dashboard/use-location-state";
import {
  fetchAirQuality,
  fetchPersonalizedPlan,
  fetchStations,
} from "@/lib/api";
import { NormalizedObservation } from "@/types/observation";
import { HouseholdProfile, PersonalizedPlan } from "@/types/recommendations";

export default function HomePage() {
  const {
    selectedStation,
    setSelectedStation,
    geoStatus,
    locationLabel,
    locationQuery,
    setLocationQuery,
    locationResults,
    isSearchingLocation,
    handleUseMyLocation,
    handleLocationSearch,
    selectGeocodedLocation,
    handleSelectStation,
  } = useLocationState();
  const [observation, setObservation] = useState<NormalizedObservation | null>(null);
  const [plan, setPlan] = useState<PersonalizedPlan | null>(null);
  const [profile, setProfile] = useState<HouseholdProfile>({
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
  });
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveStations, setLiveStations] = useState<MapStation[]>([]);
  const [stationsSource, setStationsSource] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const loadData = async (lat: number, lon: number, bypassCache = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchAirQuality(lat, lon, bypassCache);
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
    } catch (err: any) {
      setError(err.message || "Failed to communicate with air quality service.");
      setObservation(null);
    } finally {
      setIsLoading(false);
    }
  };

  const loadPlan = async (lat: number, lon: number, prof: HouseholdProfile) => {
    setIsPlanLoading(true);
    try {
      const planRes = await fetchPersonalizedPlan(lat, lon, prof);
      setPlan(planRes);
    } catch (err) {
      setPlan(null);
    } finally {
      setIsPlanLoading(false);
    }
  };

  useEffect(() => {
    loadData(selectedStation.lat, selectedStation.lon);
    loadPlan(selectedStation.lat, selectedStation.lon, profile);
  }, [selectedStation, profile]);

  useEffect(() => {
    let cancelled = false;
    fetchStations()
      .then((result) => {
        if (cancelled) return;
        const isLiveCpcb = result.message?.includes("CPCB/data.gov.in") ?? false;
        setStationsSource(isLiveCpcb ? "CPCB/data.gov.in" : result.message ?? "source unavailable");
        setLiveStations(
          isLiveCpcb
            ? result.data
                .filter(
                  (station) =>
                    Number.isFinite(station.latitude) &&
                    Number.isFinite(station.longitude)
                )
                .map((station) => ({
                  name: station.station_name,
                  station_id: station.station_id,
                  city: station.city,
                  state: station.state,
                  lat: station.latitude,
                  lon: station.longitude,
                }))
            : []
        );
      })
      .catch(() => {
        if (!cancelled) {
          setStationsSource("source unavailable");
          setLiveStations([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const retryStationLookup = () => {
    fetchStations()
      .then((result) => {
        const isLiveCpcb = result.message?.includes("CPCB/data.gov.in") ?? false;
        setStationsSource(isLiveCpcb ? "CPCB/data.gov.in" : result.message ?? "source unavailable");
        setLiveStations(
          isLiveCpcb
            ? result.data.map((station) => ({
                name: station.station_name,
                station_id: station.station_id,
                city: station.city,
                state: station.state,
                lat: station.latitude,
                lon: station.longitude,
              }))
            : []
        );
      })
      .catch(() => setStationsSource("source unavailable"));
  };

  const handleMapSelectStation = (stn: MapStation) => {
    setSelectedStation(stn);
    setActiveTab("overview");
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      <HeroBanner
        profile={profile}
        selectedStation={selectedStation}
        locationQuery={locationQuery}
        isSearchingLocation={isSearchingLocation}
        geoStatus={geoStatus}
        locationResults={locationResults}
        popularCities={POPULAR_CITIES}
        onConfigureProfile={() => setIsProfileOpen(true)}
        onUseMyLocation={handleUseMyLocation}
        onLocationQueryChange={setLocationQuery}
        onLocationSearch={handleLocationSearch}
        onSelectGeocodedLocation={selectGeocodedLocation}
        onSelectStation={handleSelectStation}
      />

      <NavigationTabs activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === "overview" && (
        <OverviewPanel
          selectedStation={selectedStation}
          locationLabel={locationLabel}
          observation={observation}
          isLoading={isLoading}
          error={error}
          onRefresh={() => loadData(selectedStation.lat, selectedStation.lon, true)}
          onRetry={() => loadData(selectedStation.lat, selectedStation.lon, false)}
        />
      )}

      {activeTab === "planner" && (
        <PlannerPanel
          plan={plan}
          isLoading={isPlanLoading}
          onConfigureProfile={() => setIsProfileOpen(true)}
        />
      )}

      {activeTab === "indoor" && (
        <IndoorPanel
          guidance={plan?.indoor_guidance ?? null}
          onAreaChange={(newArea) => {
            setProfile((p) => ({ ...p, home_area_sqft: newArea }));
          }}
        />
      )}

      {activeTab === "sustainability" && (
        <SustainabilityPanel alternatives={plan?.sustainable_alternatives ?? []} />
      )}

      {activeTab === "trends" && (
        <TrendsPanel observation={observation} stationName={selectedStation.name} />
      )}

      {activeTab === "comparison" && <ComparisonPanel />}

      {activeTab === "map" && (
        <MapPanel
          liveStations={liveStations}
          stationsSource={stationsSource}
          selectedStationId={selectedStation.station_id}
          onSelectStation={handleMapSelectStation}
          onRetryStations={retryStationLookup}
        />
      )}

      {activeTab === "assistant" && (
        <AssistantPanel
          lat={selectedStation.lat}
          lon={selectedStation.lon}
          currentAqi={observation?.calculated_aqi}
          profile={profile}
        />
      )}

      <HouseholdProfileDialog
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        profile={profile}
        onSave={(updated) => {
          setProfile(updated);
        }}
      />
    </div>
  );
}
