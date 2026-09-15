'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { fetchActiveAlerts } from '@/lib/api';
import { WeatherAlert } from '@/lib/types';

export default function ActiveAlerts() {
  const [alerts, setAlerts] = useState<WeatherAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAlerts();
    // Refresh every 30 seconds
    const interval = setInterval(loadAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  async function loadAlerts() {
    try {
      const data = await fetchActiveAlerts();
      setAlerts(data.alerts);
      setLoading(false);
      setError(null);
    } catch (err) {
      console.error('Error loading alerts:', err);
      setError('Failed to load alerts');
      setLoading(false);
    }
  }

  function getSeverityIcon(severity: string): string {
    return severity === 'EMERGENCY' ? '🚨' : '⚠️';
  }

  function getSeverityColor(severity: string): string {
    return severity === 'EMERGENCY'
      ? 'bg-red-100 text-red-800 border-red-300'
      : 'bg-orange-100 text-orange-800 border-orange-300';
  }

  function getRiskLevelColor(level: string): string {
    switch (level) {
      case 'CRITICAL':
        return 'text-red-600';
      case 'HIGH':
        return 'text-orange-600';
      default:
        return 'text-gray-600';
    }
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Active Alerts</h2>
        </div>
        <div className="text-center py-8 text-gray-500">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2">Loading alerts...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Active Alerts</h2>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
          <p className="text-red-800">{error}</p>
          <button
            onClick={loadAlerts}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const emergencyAlerts = alerts.filter((a) => a.severity === 'EMERGENCY');
  const warningAlerts = alerts.filter((a) => a.severity === 'WARNING');

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Active Weather Alerts
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Platform-generated AI risk alerts
          </p>
        </div>
        {alerts.length > 0 && (
          <Link
            href="/authority"
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            Authority Dashboard →
          </Link>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">
          <div className="text-4xl mb-2">✅</div>
          <p className="font-medium">No Active Alerts</p>
          <p className="text-sm mt-1">All weather conditions are within normal parameters</p>
        </div>
      ) : (
        <>
          {/* Alert Summary */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🚨</span>
                <div>
                  <div className="text-2xl font-bold text-red-600">
                    {emergencyAlerts.length}
                  </div>
                  <div className="text-sm text-red-800">Emergency Alerts</div>
                </div>
              </div>
            </div>
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">⚠️</span>
                <div>
                  <div className="text-2xl font-bold text-orange-600">
                    {warningAlerts.length}
                  </div>
                  <div className="text-sm text-orange-800">Warning Alerts</div>
                </div>
              </div>
            </div>
          </div>

          {/* Alert List */}
          <div className="space-y-3">
            {alerts.slice(0, 5).map((alert) => (
              <div
                key={alert.alert_id}
                className={`border-l-4 rounded-lg p-4 ${
                  alert.severity === 'EMERGENCY'
                    ? 'border-red-500 bg-red-50'
                    : 'border-orange-500 bg-orange-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">
                        {getSeverityIcon(alert.severity)}
                      </span>
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded-full border ${getSeverityColor(
                          alert.severity
                        )}`}
                      >
                        {alert.severity}
                      </span>
                      <span
                        className={`text-xs font-bold ${getRiskLevelColor(
                          alert.risk_level
                        )}`}
                      >
                        {alert.risk_level} RISK
                      </span>
                    </div>
                    <h3 className="font-semibold text-gray-900">
                      {alert.event_type.toUpperCase()} Event
                    </h3>
                    <p className="text-sm text-gray-700 mt-1">
                      {alert.location.description} • {alert.affected_radius_km.toFixed(1)}{' '}
                      km radius
                    </p>
                    <p className="text-sm text-gray-600 mt-1">
                      {alert.report_count} reports ({alert.verified_count} verified) •
                      Confidence: {(alert.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="ml-4">
                    <div className="text-right">
                      <div
                        className={`text-2xl font-bold ${getRiskLevelColor(
                          alert.risk_level
                        )}`}
                      >
                        {alert.risk_score.toFixed(0)}
                      </div>
                      <div className="text-xs text-gray-500">Risk Score</div>
                    </div>
                  </div>
                </div>
                <div className="mt-2 text-sm text-gray-700 bg-white bg-opacity-50 rounded p-2">
                  <span className="font-medium">Action: </span>
                  {alert.recommended_action}
                </div>
              </div>
            ))}

            {alerts.length > 5 && (
              <div className="text-center pt-2">
                <Link
                  href="/authority"
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  View all {alerts.length} alerts →
                </Link>
              </div>
            )}
          </div>
        </>
      )}

      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 text-center">
          Alerts are generated automatically by AI risk detection algorithms based on
          verified citizen reports and weather data analysis.
        </p>
      </div>
    </div>
  );
}
