'use client';

import { useState, useEffect } from 'react';
import { fetchRiskAssessments } from '@/lib/api';
import { RiskAssessment } from '@/lib/types';

export default function HighRiskEvents() {
  const [riskData, setRiskData] = useState<RiskAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRiskData();
    const interval = setInterval(loadRiskData, 30000);
    return () => clearInterval(interval);
  }, []);

  async function loadRiskData() {
    try {
      const data = await fetchRiskAssessments(undefined, 50);
      // Filter to show only HIGH and CRITICAL risks
      const highRisks = data.assessments.filter(
        (a) => a.risk_level === 'HIGH' || a.risk_level === 'CRITICAL'
      );
      setRiskData(highRisks);
      setLoading(false);
      setError(null);
    } catch (err) {
      console.error('Error loading risk data:', err);
      setError('Failed to load risk assessments');
      setLoading(false);
    }
  }

  function getRiskLevelColor(level: string): string {
    switch (level) {
      case 'CRITICAL':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'HIGH':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  }

  function getRiskLevelBadge(level: string): string {
    return level === 'CRITICAL' ? '🔴' : '🟠';
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          High-Risk Weather Events
        </h2>
        <div className="text-center py-8 text-gray-500">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2">Loading risk assessments...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          High-Risk Weather Events
        </h2>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
          <p className="text-red-800">{error}</p>
          <button
            onClick={loadRiskData}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            High-Risk Weather Events
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Events rated HIGH or CRITICAL by AI risk detection
          </p>
        </div>
      </div>

      {riskData.length === 0 ? (
        <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">
          <div className="text-4xl mb-2">🌤️</div>
          <p className="font-medium">No High-Risk Events</p>
          <p className="text-sm mt-1">All current weather events are low to moderate risk</p>
        </div>
      ) : (
        <div className="space-y-4">
          {riskData.map((assessment) => (
            <div
              key={assessment.event_id}
              className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{getRiskLevelBadge(assessment.risk_level)}</span>
                    <span
                      className={`px-3 py-1 text-xs font-semibold rounded-full border ${getRiskLevelColor(
                        assessment.risk_level
                      )}`}
                    >
                      {assessment.risk_level} RISK
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {assessment.event_type.toUpperCase()} Event
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {assessment.event_details.center.lat.toFixed(3)}°N,{' '}
                    {assessment.event_details.center.lon.toFixed(3)}°E
                    <span className="mx-2">•</span>
                    Radius: {assessment.event_details.affected_radius_km.toFixed(1)} km
                  </p>
                </div>
                <div className="text-right ml-4">
                  <div className="text-3xl font-bold text-red-600">
                    {assessment.risk_score.toFixed(0)}
                  </div>
                  <div className="text-xs text-gray-500">Risk Score</div>
                </div>
              </div>

              {/* Event Stats */}
              <div className="grid grid-cols-4 gap-2 mb-3 text-center">
                <div className="bg-gray-50 rounded p-2">
                  <div className="text-lg font-semibold text-gray-900">
                    {assessment.event_details.report_count}
                  </div>
                  <div className="text-xs text-gray-500">Reports</div>
                </div>
                <div className="bg-green-50 rounded p-2">
                  <div className="text-lg font-semibold text-green-700">
                    {assessment.event_details.verification_summary.verified}
                  </div>
                  <div className="text-xs text-gray-500">Verified</div>
                </div>
                <div className="bg-blue-50 rounded p-2">
                  <div className="text-lg font-semibold text-blue-700">
                    {(assessment.confidence * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-500">Confidence</div>
                </div>
                <div className="bg-purple-50 rounded p-2">
                  <div className="text-lg font-semibold text-purple-700">
                    {(assessment.event_details.avg_confidence_score * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-500">Avg Quality</div>
                </div>
              </div>

              {/* Risk Factors */}
              <div className="mb-3">
                <div className="text-xs font-semibold text-gray-700 mb-2">Risk Factors:</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Event Severity:</span>
                    <span className="font-semibold">
                      {assessment.factors.event_severity.toFixed(1)}/25
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Report Quality:</span>
                    <span className="font-semibold">
                      {assessment.factors.report_quality.toFixed(1)}/25
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Confidence:</span>
                    <span className="font-semibold">
                      {assessment.factors.confidence_level.toFixed(1)}/20
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Geographic Impact:</span>
                    <span className="font-semibold">
                      {assessment.factors.geographic_impact.toFixed(1)}/15
                    </span>
                  </div>
                  <div className="flex justify-between col-span-2">
                    <span className="text-gray-600">Ground Truth:</span>
                    <span className="font-semibold">
                      {assessment.factors.ground_truth_validation.toFixed(1)}/15
                    </span>
                  </div>
                </div>
              </div>

              {/* Recommended Action */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="text-xs font-semibold text-blue-900 mb-1">
                  Recommended Action:
                </div>
                <div className="text-sm text-blue-800">{assessment.recommended_action}</div>
              </div>

              {/* Timestamp */}
              <div className="mt-2 pt-2 border-t border-gray-200 text-xs text-gray-500">
                Time Range: {new Date(assessment.event_details.time_range.start).toLocaleString()}{' '}
                - {new Date(assessment.event_details.time_range.end).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
