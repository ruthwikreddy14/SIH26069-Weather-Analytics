'use client';

import React, { useEffect, useState } from 'react';
import { EventCluster, EventClustersResponse } from '@/lib/types';
import { fetchEventClusters } from '@/lib/api';

interface WeatherEventsProps {
  selectedEventType?: string;
  onEventClick?: (cluster: EventCluster) => void;
}

const WeatherEvents: React.FC<WeatherEventsProps> = ({ selectedEventType, onEventClick }) => {
  const [clusters, setClusters] = useState<EventCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalClusters, setTotalClusters] = useState(0);
  const [totalReportsAnalyzed, setTotalReportsAnalyzed] = useState(0);

  useEffect(() => {
    loadClusters();
  }, [selectedEventType]);

  const loadClusters = async () => {
    try {
      setLoading(true);
      setError(null);
      const response: EventClustersResponse = await fetchEventClusters(selectedEventType, 200);
      setClusters(response.clusters || []);
      setTotalClusters(response.total_clusters || 0);
      setTotalReportsAnalyzed(response.total_reports_analyzed || 0);
    } catch (err) {
      console.error('Error loading event clusters:', err);
      setError('Failed to load event clusters');
      setClusters([]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'disputed':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'fake':
        return 'bg-red-100 text-red-800 border-red-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getStatusBadge = (status: string) => {
    const colorClass = getStatusColor(status);
    const label = status.charAt(0).toUpperCase() + status.slice(1);
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded border ${colorClass}`}>
        {label}
      </span>
    );
  };

  const formatEventType = (type: string) => {
    return type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatTimeRange = (start: string, end: string) => {
    const startDate = new Date(start);
    const endDate = new Date(end);
    
    const formatDate = (date: Date) => {
      return date.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      });
    };

    if (startDate.toDateString() === endDate.toDateString()) {
      return `${formatDate(startDate)} - ${endDate.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      })}`;
    }

    return `${formatDate(startDate)} - ${formatDate(endDate)}`;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Loading weather events...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="text-center">
          <p className="text-red-600 font-medium">{error}</p>
          <button
            onClick={loadClusters}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (clusters.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="mt-2 text-lg font-medium text-gray-900">No Event Clusters</h3>
          <p className="mt-1 text-sm text-gray-500">
            {totalReportsAnalyzed > 0
              ? `Analyzed ${totalReportsAnalyzed} reports, but insufficient data to form event clusters.`
              : 'No reports available for clustering.'}
          </p>
          <p className="mt-2 text-xs text-gray-400">
            Clusters require at least 2 reports within 50km and 24 hours with the same event type.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Detected Weather Events</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              {totalClusters} event{totalClusters !== 1 ? 's' : ''} detected from {totalReportsAnalyzed} reports
            </p>
          </div>
          <button
            onClick={loadClusters}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            title="Refresh clusters"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Event Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {clusters.map((cluster) => (
          <div
            key={cluster.event_id}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => onEventClick?.(cluster)}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <h4 className="font-semibold text-gray-900 text-base mb-1">
                  {formatEventType(cluster.event_type)} Event
                </h4>
                <p className="text-xs text-gray-500">ID: {cluster.event_id}</p>
              </div>
              {getStatusBadge(cluster.verification_summary.dominant_status)}
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <p className="text-xs text-gray-500">Reports</p>
                <p className="text-lg font-semibold text-gray-900">{cluster.report_count}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Avg Confidence</p>
                <p className="text-lg font-semibold text-gray-900">
                  {(cluster.avg_confidence_score * 100).toFixed(0)}%
                </p>
              </div>
            </div>

            {/* Verification Summary */}
            <div className="flex items-center gap-2 mb-3 text-xs">
              {cluster.verification_summary.verified > 0 && (
                <span className="text-green-600 font-medium">
                  ✓ {cluster.verification_summary.verified}
                </span>
              )}
              {cluster.verification_summary.disputed > 0 && (
                <span className="text-yellow-600 font-medium">
                  ⚠ {cluster.verification_summary.disputed}
                </span>
              )}
              {cluster.verification_summary.fake > 0 && (
                <span className="text-red-600 font-medium">
                  ✗ {cluster.verification_summary.fake}
                </span>
              )}
              {cluster.verification_summary.unverified > 0 && (
                <span className="text-gray-500 font-medium">
                  ? {cluster.verification_summary.unverified}
                </span>
              )}
            </div>

            {/* Location & Radius */}
            <div className="mb-3">
              <div className="flex items-center text-xs text-gray-600 mb-1">
                <svg className="w-3.5 h-3.5 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>
                  {cluster.center.lat.toFixed(3)}°N, {cluster.center.lon.toFixed(3)}°E
                </span>
              </div>
              <div className="flex items-center text-xs text-gray-600">
                <svg className="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                  />
                </svg>
                <span>Radius: {cluster.affected_radius_km} km</span>
              </div>
            </div>

            {/* Time Range */}
            <div className="pt-3 border-t border-gray-100">
              <div className="flex items-start text-xs text-gray-600">
                <svg className="w-3.5 h-3.5 mr-1 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span className="leading-tight">
                  {formatTimeRange(cluster.time_range.start, cluster.time_range.end)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WeatherEvents;
