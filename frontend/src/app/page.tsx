"use client";

import { MapStation } from "@/components/dashboard/station-map";
import { HeroBanner } from "@/components/dashboard/hero-banner";
import { NavigationTabs } from "@/components/dashboard/navigation-tabs";
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
import { useActiveTab } from "@/hooks/dashboard/use-active-tab";
import { useDashboardData } from "@/hooks/dashboard/use-dashboard-data";
import { useProfileState } from "@/hooks/dashboard/use-profile-state";
import { useStationsState } from "@/hooks/dashboard/use-stations-state";
import { useLocationState, POPULAR_CITIES } from "@/components/dashboard/use-location-state";

export default function HomePage() {
  const location = useLocationState();
  const { activeTab, setActiveTab } = useActiveTab();
  const profile = useProfileState();
  const dashboardData = useDashboardData({
    selectedStation: location.selectedStation,
    profile: profile.profile,
  });
  const stations = useStationsState();

  const handleMapSelectStation = (stn: MapStation) => {
    location.setSelectedStation(stn);
    setActiveTab("overview");
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      <HeroBanner
        profile={profile.profile}
        selectedStation={location.selectedStation}
        locationQuery={location.locationQuery}
        manualCoordinates={location.manualCoordinates}
        hasSavedCoordinates={location.hasSavedCoordinates}
        isSearchingLocation={location.isSearchingLocation}
        geoStatus={location.geoStatus}
        locationResults={location.locationResults}
        popularCities={POPULAR_CITIES}
        onConfigureProfile={profile.openProfile}
        onUseMyLocation={location.handleUseMyLocation}
        onLocationQueryChange={location.setLocationQuery}
        onLocationSearch={location.handleLocationSearch}
        onManualCoordinatesChange={location.setManualCoordinates}
        onManualCoordinatesSubmit={location.handleManualCoordinates}
        onClearSavedCoordinates={location.clearSavedCoordinates}
        onSelectGeocodedLocation={location.selectGeocodedLocation}
        onSelectStation={location.handleSelectStation}
      />

      <NavigationTabs activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === "overview" && (
        <OverviewPanel
          selectedStation={location.selectedStation}
          locationLabel={location.locationLabel}
          observation={dashboardData.observation}
          isLoading={dashboardData.isLoading}
          error={dashboardData.error}
          onRefresh={dashboardData.refreshObservation}
          onRetry={dashboardData.retryObservation}
        />
      )}

      {activeTab === "planner" && (
        <PlannerPanel
          plan={dashboardData.plan}
          isLoading={dashboardData.isPlanLoading}
          onConfigureProfile={profile.openProfile}
        />
      )}

      {activeTab === "indoor" && (
        <IndoorPanel guidance={dashboardData.plan?.indoor_guidance ?? null} onAreaChange={profile.setHomeArea} />
      )}

      {activeTab === "sustainability" && (
        <SustainabilityPanel
          alternatives={dashboardData.plan?.sustainable_alternatives ?? []}
          profile={profile.profile}
          currentAqi={dashboardData.observation?.calculated_aqi}
          stationName={location.selectedStation.name}
        />
      )}

      {activeTab === "trends" && (
        <TrendsPanel observation={dashboardData.observation} stationName={location.selectedStation.name} />
      )}

      {activeTab === "comparison" && <ComparisonPanel />}

      {activeTab === "map" && (
        <MapPanel
          liveStations={stations.liveStations}
          stationsSource={stations.stationsSource}
          selectedStationId={location.selectedStation.station_id}
          onSelectStation={handleMapSelectStation}
          onRetryStations={stations.retryStationLookup}
        />
      )}

      {activeTab === "assistant" && (
        <AssistantPanel
          lat={location.selectedStation.lat}
          lon={location.selectedStation.lon}
          currentAqi={dashboardData.observation?.calculated_aqi}
          profile={profile.profile}
        />
      )}

      <HouseholdProfileDialog
        isOpen={profile.isProfileOpen}
        onClose={profile.closeProfile}
        profile={profile.profile}
        onSave={profile.saveProfile}
      />
    </div>
  );
}
