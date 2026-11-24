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
  | "insufficient"
  | "stale"
  | "unavailable";

export interface NormalizedPollutantReading {
  pollutant: PollutantType;
  value: number;
  unit: string;
  sub_index?: number | null;
  averaging_period_hours: number;
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
}
