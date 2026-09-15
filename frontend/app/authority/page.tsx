'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  fetchActiveAlerts,
  fetchAlertStats,
  fetchRiskAssessments,
  updateAlert,
} from '@/lib/api';
import {
  WeatherAlert,
  AlertStatsResponse,
  RiskAssessmentsResponse,
  ResponseStatus,
} from '@/lib/types';

export default function AuthorityDashboard() {
  const [alerts, setAlerts] = useState<WeatherAlert[]>([]);
  const [stats, setStats] = useState<AlertStatsResponse | null>(null);
  const [riskData, setRiskData] = useState<RiskAssessmentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<WeatherAlert | null>(null);
  const [updatingAlert, setUpdatingAlert] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
    // Refresh every 30 seconds
    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  async function loadDashboardData() {
    try {
      setError(null);
      const [alertsData, statsData, risksData] = await Promise.all([
        fetchActiveAlerts(),
        fetchAlertStats(),
        fetchRiskAssessments(undefined, 50),
      ]);
      setAlerts(alertsData.alerts);
      setStats(statsData);
      setRiskData(risksData);
      setLoading(false);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      setError('Failed to load dashboard data. Please try again.');
      setLoading(false);
    }
  }

  async function handleUpdateAlertStatus(
    alertId: string,
    responseStatus: ResponseStatus
  ) {
    try {
      setUpdatingAlert(alertId);
      await updateAlert(alertId, { response_status: responseStatus });
      await loadDashboardData();
    } catch (err) {
      console.error('Error updating alert:', err);
      alert('Failed to update alert status');
    } finally {
      setUpdatingAlert(null);
    }
  }

  function getSeverityColor(severity: string): string {
    switch (severity) {
      case 'EMERGENCY':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'WARNING':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  }

  function getRiskLevelColor(level: string): string {
    switch (level) {
      case 'CRITICAL':
        return 'text-red-600 bg-red-50';
      case 'HIGH':
        return 'text-orange-600 bg-orange-50';
      case 'MODERATE':
        return 'text-yellow-600 bg-yellow-50';
      case 'LOW':
        return 'text-green-600 bg-green-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  }

  function getResponseStatusColor(status: ResponseStatus): string {
    switch (status) {
      case 'RESOLVED':
        return 'bg-green-100 text-green-800';
      case 'RESPONSE_INITIATED':
        return 'bg-blue-100 text-blue-800';
      case 'INVESTIGATING':
        return 'bg-purple-100 text-purple-800';
      case 'MONITORING':
        return 'bg-yellow-100 text-yellow-800';
      case 'PENDING':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading Authority Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Authority Dashboard
              </h1>
              <p className="text-sm text-gray-500">
                Weather Event Monitoring & Response System
              </p>
            </div>
            <Link
              href="/"
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              ← Back to Main Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
            <button
              onClick={loadDashboardData}
              className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-red-500">
            <div className="text-sm font-medium text-gray-500">
              Emergency Alerts
            </div>
            <div className="mt-2 text-3xl font-bold text-red-600">
              {stats?.emergency_alerts || 0}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-orange-500">
            <div className="text-sm font-medium text-gray-500">
              Warning Alerts
            </div>
            <div className="mt-2 text-3xl font-bold text-orange-600">
              {stats?.warning_alerts || 0}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
            <div className="text-sm font-medium text-gray-500">
              Total Active Alerts
            </div>
            <div className="mt-2 text-3xl font-bold text-blue-600">
              {stats?.total_active_alerts || 0}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-purple-500">
            <div className="text-sm font-medium text-gray-500">
              High-Risk Events
            </div>
            <div className="mt-2 text-3xl font-bold text-purple-600">
              {(riskData?.high_risk_count || 0) +
                (riskData?.critical_risk_count || 0)}
            </div>
          </div>
        </div>

        {/* Response Status Breakdown */}
        {stats && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Response Status Overview
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-700">
                  {stats.response_breakdown.pending}
                </div>
                <div className="text-sm text-gray-500">Pending</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">
                  {stats.response_breakdown.monitoring}
                </div>
                <div className="text-sm text-gray-500">Monitoring</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {stats.response_breakdown.investigating}
                </div>
                <div className="text-sm text-gray-500">Investigating</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {stats.response_breakdown.responding}
                </div>
                <div className="text-sm text-gray-500">Responding</div>
              </div>
            </div>
          </div>
        )}

        {/* Active Alerts */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Active Alerts ({alerts.length})
            </h2>
          </div>
          <div className="divide-y divide-gray-200">
            {alerts.length === 0 ? (
              <div className="px-6 py-8 text-center text-gray-500">
                No active alerts at this time.
              </div>
            ) : (
              alerts.map((alert) => (
                <div key={alert.alert_id} className="px-6 py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className={`px-3 py-1 text-xs font-semibold rounded-full border ${getSeverityColor(
                            alert.severity
                          )}`}
                        >
                          {alert.severity}
                        </span>
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded ${getRiskLevelColor(
                            alert.risk_level
                          )}`}
                        >
                          {alert.risk_level} RISK
                        </span>
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded ${getResponseStatusColor(
                            alert.response_status
                          )}`}
                        >
                          {alert.response_status.replace('_', ' ')}
                        </span>
                      </div>
                      <h3 className="text-lg font-medium text-gray-900">
                        {alert.event_type.toUpperCase()} Event
                      </h3>
                      <p className="text-sm text-gray-600 mt-1">
                        {alert.location.description} • Radius:{' '}
                        {alert.affected_radius_km.toFixed(1)} km
                      </p>
                      <div className="mt-2 text-sm text-gray-700">
                        <span className="font-medium">
                          {alert.report_count} reports
                        </span>
                        <span className="text-gray-500 mx-2">•</span>
                        <span>
                          {alert.verified_count} verified (
                          {((alert.verified_count / alert.report_count) * 100).toFixed(0)}
                          %)
                        </span>
                        <span className="text-gray-500 mx-2">•</span>
                        <span>Confidence: {(alert.confidence * 100).toFixed(0)}%</span>
                        <span className="text-gray-500 mx-2">•</span>
                        <span>Risk Score: {alert.risk_score.toFixed(1)}/100</span>
                      </div>
                      <p className="mt-2 text-sm text-gray-600">
                        {alert.recommended_action}
                      </p>
                      {alert.response_notes && (
                        <div className="mt-2 p-2 bg-blue-50 rounded text-sm text-blue-800">
                          <span className="font-medium">Notes: </span>
                          {alert.response_notes}
                        </div>
                      )}
                    </div>
                    <div className="ml-4 flex flex-col gap-2">
                      {alert.response_status === 'PENDING' && (
                        <>
                          <button
                            onClick={() =>
                              handleUpdateAlertStatus(alert.alert_id, 'MONITORING')
                            }
                            disabled={updatingAlert === alert.alert_id}
                            className="px-3 py-1 text-xs font-medium text-yellow-700 bg-yellow-100 rounded hover:bg-yellow-200 disabled:opacity-50"
                          >
                            Start Monitoring
                          </button>
                          <button
                            onClick={() =>
                              handleUpdateAlertStatus(alert.alert_id, 'INVESTIGATING')
                            }
                            disabled={updatingAlert === alert.alert_id}
                            className="px-3 py-1 text-xs font-medium text-purple-700 bg-purple-100 rounded hover:bg-purple-200 disabled:opacity-50"
                          >
                            Investigate
                          </button>
                        </>
                      )}
                      {(alert.response_status === 'MONITORING' ||
                        alert.response_status === 'INVESTIGATING') && (
                        <button
                          onClick={() =>
                            handleUpdateAlertStatus(
                              alert.alert_id,
                              'RESPONSE_INITIATED'
                            )
                          }
                          disabled={updatingAlert === alert.alert_id}
                          className="px-3 py-1 text-xs font-medium text-blue-700 bg-blue-100 rounded hover:bg-blue-200 disabled:opacity-50"
                        >
                          Initiate Response
                        </button>
                      )}
                      <button
                        onClick={() => setSelectedAlert(alert)}
                        className="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
                      >
                        View Details
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-gray-500">
                    Created: {new Date(alert.created_at).toLocaleString()} •
                    Updated: {new Date(alert.updated_at).toLocaleString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Alert Details Modal */}
        {selectedAlert && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
            onClick={() => setSelectedAlert(null)}
          >
            <div
              className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Alert Details
                  </h3>
                  <p className="text-sm text-gray-500">{selectedAlert.alert_id}</p>
                </div>
                <button
                  onClick={() => setSelectedAlert(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              <div className="px-6 py-4">
                <div className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 p-4 rounded">
                  {selectedAlert.alert_message}
                </div>
                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="font-medium text-gray-700">Event ID:</span>
                    <span className="text-gray-600">{selectedAlert.event_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-medium text-gray-700">Location:</span>
                    <span className="text-gray-600">
                      {selectedAlert.location.lat.toFixed(3)}°N,{' '}
                      {selectedAlert.location.lon.toFixed(3)}°E
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-medium text-gray-700">
                      Affected Radius:
                    </span>
                    <span className="text-gray-600">
                      {selectedAlert.affected_radius_km.toFixed(1)} km
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
