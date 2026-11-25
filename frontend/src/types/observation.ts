export type PollutantType =
  | "PM2.5"
  | "PM10"
  | "NO2"
  | "SO2"
  | "CO"
  | "O3"
  | "NH3"
  | "Pb";

export type AQICategory =
  | "Good"
  | "Satisfactory"
  | "Moderate"
  | "Poor"
  | "Very Poor"
  | "Severe";

export type DataQualityStatus =
  | "verified"
  | "estimated"
  | "delayed"
  | "insufficient"
  | "stale"
  | "unavailable";

export interface NormalizedPollutantReading {
  pollutant: PollutantType;
  value: number;
  unit: string | null;
  sub_index?: number | null;
  averaging_period_hours?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  source_pollutant_id?: string | null;
}

export interface HourlyTrendPoint {
  time: string;
  pm2_5?: number | null;
  pm10?: number | null;
  no2?: number | null;
  so2?: number | null;
  co?: number | null;
  o3?: number | null;
  aqi?: number | null;
  category?: AQICategory | null;
}

export interface StationMetadata {
  station_id: string;
  station_name: string;
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  distance_km?: number | null;
  elevation_m?: number | null;
  provider?: string | null;
  source_observation_time?: string | null;
}

export interface NormalizedObservation {
  provider: string;
  station: StationMetadata;
  readings: Record<string, NormalizedPollutantReading>;
  calculated_aqi?: number | null;
  dominant_pollutant?: PollutantType | null;
  aqi_category?: AQICategory | null;
  data_sufficiency_met: boolean;
  measurement_timestamp: string;
  retrieval_timestamp: string;
  data_quality_status: DataQualityStatus;
  notes?: string | null;
  hourly_trend?: HourlyTrendPoint[];
}

export interface AirQualityApiResponse {
  success: boolean;
  data: NormalizedObservation | null;
  message?: string | null;
}

export interface StationsApiResponse {
  success: boolean;
  count: number;
  data: StationMetadata[];
  message?: string | null;
}

export interface ComparisonDifferential {
  cleanest_station_id?: string | null;
  cleanest_station_name?: string | null;
  most_polluted_station_id?: string | null;
  most_polluted_station_name?: string | null;
  aqi_difference?: number | null;
  pm25_difference_ug_m3?: number | null;
  summary: string;
}

export type ComparisonBasis = "live_station" | "coordinate_estimate" | "mixed";

export interface ComparisonCandidate {
  id: string;
  label: string;
  city?: string | null;
  state?: string | null;
  latitude: number;
  longitude: number;
  basis: "live_station" | "coordinate_estimate";
  source: string;
}

export interface ComparisonPreset {
  key: string;
  name: string;
  description: string;
  ids: string[];
  basis: "live_station" | "coordinate_estimate";
  source: string;
  candidates: ComparisonCandidate[];
}

export interface ComparisonPresetsResponse {
  success: boolean;
  source: string;
  presets: ComparisonPreset[];
  message: string;
}

export interface ComparisonApiResponse {
  success: boolean;
  stations_count: number;
  observations: NormalizedObservation[];
  differential?: ComparisonDifferential | null;
  basis?: ComparisonBasis;
  source?: string;
  requested_ids?: string[];
  unresolved_ids?: string[];
  message?: string;
}
