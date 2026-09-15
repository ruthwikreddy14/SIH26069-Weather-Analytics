/**
 * API client for connecting to the backend Reports API
 */

import axios, { AxiosInstance } from 'axios';
import {
  Report,
  ReportDetail,
  ReportListResponse,
  ReportSubmitRequest,
  ReportSubmitResponse,
  DashboardStats,
  FilterParams,
  EventClustersResponse,
  RiskAssessmentsResponse,
  RiskAssessment,
  ActiveAlertsResponse,
  WeatherAlert,
  AlertStatsResponse,
  AlertUpdateRequest,
} from './types';

// API base URL - can be configured via environment variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

/**
 * Fetch reports with optional filters
 */
export async function fetchReports(filters?: FilterParams): Promise<ReportListResponse> {
  const params = new URLSearchParams();

  if (filters) {
    if (filters.date_from) params.append('date_from', filters.date_from);
    if (filters.date_to) params.append('date_to', filters.date_to);
    if (filters.event_type) params.append('event_type', filters.event_type);
    if (filters.state) params.append('state', filters.state);
    if (filters.status) params.append('status', filters.status);
    if (filters.limit) params.append('limit', filters.limit.toString());
    if (filters.offset) params.append('offset', filters.offset.toString());
  }

  const response = await apiClient.get<ReportListResponse>(
    `/api/reports${params.toString() ? `?${params.toString()}` : ''}`
  );
  return response.data;
}

/**
 * Fetch a single report by ID
 */
export async function fetchReportById(reportId: string): Promise<ReportDetail> {
  const response = await apiClient.get<ReportDetail>(`/api/reports/${reportId}`);
  return response.data;
}

/**
 * Submit a new weather report
 */
export async function submitReport(data: ReportSubmitRequest): Promise<ReportSubmitResponse> {
  const response = await apiClient.post<ReportSubmitResponse>('/api/reports/submit', data);
  return response.data;
}

/**
 * Fetch dashboard statistics
 */
export async function fetchDashboardStats(): Promise<DashboardStats> {
  const response = await apiClient.get<DashboardStats>('/api/analytics/stats');
  return response.data;
}

/**
 * Check API health
 */
export async function checkHealth(): Promise<{ status: string; database: string }> {
  const response = await apiClient.get('/health');
  return response.data;
}

/**
 * Fetch weather event clusters
 */
export async function fetchEventClusters(eventType?: string, limit?: number): Promise<EventClustersResponse> {
  const params = new URLSearchParams();
  if (eventType) params.append('event_type', eventType);
  if (limit) params.append('limit', limit.toString());

  const response = await apiClient.get<EventClustersResponse>(
    `/api/events/clusters${params.toString() ? `?${params.toString()}` : ''}`
  );
  return response.data;
}

/**
 * Fetch risk assessments for all events
 */
export async function fetchRiskAssessments(eventType?: string, limit?: number): Promise<RiskAssessmentsResponse> {
  const params = new URLSearchParams();
  if (eventType) params.append('event_type', eventType);
  if (limit) params.append('limit', limit.toString());

  const response = await apiClient.get<RiskAssessmentsResponse>(
    `/api/risk/assess${params.toString() ? `?${params.toString()}` : ''}`
  );
  return response.data;
}

/**
 * Fetch risk assessment for a specific event
 */
export async function fetchEventRiskAssessment(eventId: string): Promise<RiskAssessment> {
  const response = await apiClient.get<RiskAssessment>(`/api/risk/assess/${eventId}`);
  return response.data;
}

/**
 * Fetch active weather alerts
 */
export async function fetchActiveAlerts(): Promise<ActiveAlertsResponse> {
  const response = await apiClient.get<ActiveAlertsResponse>('/api/alerts/active');
  return response.data;
}

/**
 * Fetch specific alert by ID
 */
export async function fetchAlertById(alertId: string): Promise<WeatherAlert> {
  const response = await apiClient.get<WeatherAlert>(`/api/alerts/${alertId}`);
  return response.data;
}

/**
 * Update alert status
 */
export async function updateAlert(alertId: string, update: AlertUpdateRequest): Promise<WeatherAlert> {
  const response = await apiClient.patch<WeatherAlert>(`/api/alerts/${alertId}`, update);
  return response.data;
}

/**
 * Resolve an alert
 */
export async function resolveAlert(alertId: string, notes?: string): Promise<WeatherAlert> {
  const response = await apiClient.post<WeatherAlert>(
    `/api/alerts/${alertId}/resolve`,
    null,
    { params: { notes } }
  );
  return response.data;
}

/**
 * Fetch alert statistics
 */
export async function fetchAlertStats(): Promise<AlertStatsResponse> {
  const response = await apiClient.get<AlertStatsResponse>('/api/alerts/summary/stats');
  return response.data;
}

export default apiClient;
