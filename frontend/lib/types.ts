/**
 * TypeScript types matching backend Pydantic schemas
 */

export interface GPSCoordinates {
  lat: number;
  lon: number;
}

export interface LocationInfo {
  lat?: number;
  lon?: number;
  city?: string;
  state?: string;
  location_source?: string;
  location_confidence?: string;
}

export interface VerificationSignals {
  ground_truth?: {
    plausible?: boolean;
    confidence?: number;
    recorded_rainfall_mm?: number;
    data_source?: string;
    query_timestamp?: string;
    [key: string]: any;
  };
  image_hash?: {
    is_duplicate?: boolean;
    confidence?: number;
    closest_match_distance?: number;
    [key: string]: any;
  };
  text_dedup?: {
    is_duplicate?: boolean;
    confidence?: number;
    cluster_id?: string;
    closest_match_similarity?: number;
    [key: string]: any;
  };
  text_dedup_signal?: {
    is_duplicate?: boolean;
    confidence?: number;
    cluster_id?: string | null;
    closest_match_id?: string | null;
    closest_match_similarity?: number;
    similar_report_count?: number;
    reasoning?: string;
    [key: string]: any;
  };
  location?: {
    confidence?: number;
    within_india?: boolean;
    distance_from_city_km?: number;
    [key: string]: any;
  };
  confidence_calculation?: {
    confidence?: number;
    verification_status?: string;
    signal_confidences?: {
      ground_truth?: number | null;
      image_hash?: number | null;
      text_dedup?: number | null;
      location?: number | null;
    };
    weights_used?: {
      ground_truth?: number;
      image_hash?: number;
      text_dedup?: number;
      location?: number;
    };
    reasoning?: string;
  };
  [key: string]: any;
}

export interface Report {
  id: string;
  event_type?: string;
  description: string;
  location?: LocationInfo;
  verification_status?: string;
  confidence_score?: number;
  reported_at: string;
  media_urls?: string[];
  signals?: VerificationSignals;
}

export interface ReportDetail extends Report {
  source_type: string;
  city?: string;
  state?: string;
  cluster_id?: string;
  admin_override?: boolean;
  admin_notes?: string;
  ingested_at?: string;
  verified_at?: string;
}

export interface ReportListResponse {
  reports: Report[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReportSubmitRequest {
  event_type: string;
  description: string;
  city: string;
  state: string;
  gps?: GPSCoordinates;
  media_files?: string[];
}

export interface ReportSubmitResponse {
  report_id: string;
  status: string;
  message: string;
}

export interface DashboardStats {
  total_reports: number;
  verified_count: number;
  fake_count: number;
  disputed_count: number;
  verified_percentage: number;
}

export interface FilterParams {
  date_from?: string;
  date_to?: string;
  event_type?: string;
  state?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export type VerificationStatus = 'verified' | 'disputed' | 'fake' | 'unverified';
export type EventType = 'rainfall' | 'flooding' | 'thunderstorm' | 'heatwave' | 'fog' | 'dust_storm' | 'strong_wind';

export const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: 'rainfall', label: 'Rainfall' },
  { value: 'flooding', label: 'Flooding' },
  { value: 'thunderstorm', label: 'Thunderstorm' },
  { value: 'heatwave', label: 'Heatwave' },
  { value: 'fog', label: 'Fog' },
  { value: 'dust_storm', label: 'Dust Storm' },
  { value: 'strong_wind', label: 'Strong Wind' },
];

export const VERIFICATION_STATUSES: { value: VerificationStatus; label: string; color: string }[] = [
  { value: 'verified', label: 'Verified', color: 'green' },
  { value: 'disputed', label: 'Disputed', color: 'yellow' },
  { value: 'fake', label: 'Fake', color: 'red' },
  { value: 'unverified', label: 'Unverified', color: 'gray' },
];

export const INDIAN_STATES = [
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chhattisgarh',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
];

// Event Clustering Types
export interface EventClusterCenter {
  lat: number;
  lon: number;
}

export interface EventClusterTimeRange {
  start: string;
  end: string;
}

export interface EventClusterVerificationSummary {
  verified: number;
  disputed: number;
  fake: number;
  unverified: number;
  dominant_status: VerificationStatus;
}

export interface EventCluster {
  event_id: string;
  event_type: string;
  center: EventClusterCenter;
  report_count: number;
  report_ids: string[];
  time_range: EventClusterTimeRange;
  affected_radius_km: number;
  avg_confidence_score: number;
  verification_summary: EventClusterVerificationSummary;
}

export interface EventClustersResponse {
  clusters: EventCluster[];
  total_clusters: number;
  total_reports_analyzed: number;
  clustering_params?: {
    max_distance_km: number;
    max_time_window_hours: number;
    min_cluster_size: number;
  };
  message?: string;
}

// Risk Detection Types
export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface RiskFactors {
  event_severity: number;
  report_quality: number;
  confidence_level: number;
  geographic_impact: number;
  ground_truth_validation: number;
}

export interface RiskAssessment {
  event_id: string;
  event_type: string;
  risk_score: number;
  risk_level: RiskLevel;
  confidence: number;
  factors: RiskFactors;
  event_details: EventCluster;
  recommended_action: string;
  assessed_at: string;
}

export interface RiskAssessmentsResponse {
  assessments: RiskAssessment[];
  total_events: number;
  high_risk_count: number;
  critical_risk_count: number;
}

// Alert Types
export type AlertSeverity = 'WARNING' | 'EMERGENCY';
export type AlertStatus = 'ACTIVE' | 'MONITORING' | 'RESOLVED';
export type ResponseStatus = 'PENDING' | 'MONITORING' | 'INVESTIGATING' | 'RESPONSE_INITIATED' | 'RESOLVED';

export interface AlertLocation {
  lat: number;
  lon: number;
  description: string;
}

export interface WeatherAlert {
  alert_id: string;
  event_id: string;
  event_type: string;
  risk_level: RiskLevel;
  risk_score: number;
  severity: AlertSeverity;
  location: AlertLocation;
  affected_radius_km: number;
  report_count: number;
  verified_count: number;
  confidence: number;
  created_at: string;
  expires_at: string | null;
  status: AlertStatus;
  alert_message: string;
  recommended_action: string;
  response_status: ResponseStatus;
  response_notes: string | null;
  updated_at: string;
}

export interface ActiveAlertsResponse {
  alerts: WeatherAlert[];
  total_alerts: number;
  emergency_count: number;
  warning_count: number;
}

export interface AlertStatsResponse {
  total_active_alerts: number;
  emergency_alerts: number;
  warning_alerts: number;
  response_breakdown: {
    pending: number;
    monitoring: number;
    investigating: number;
    responding: number;
  };
}

export interface AlertUpdateRequest {
  status?: AlertStatus;
  response_status?: ResponseStatus;
  response_notes?: string;
}
