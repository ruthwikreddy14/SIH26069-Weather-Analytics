'use client';

/**
 * Interactive weather map component with Leaflet
 * Displays color-coded markers based on verification status
 * Includes click-to-place-pin feature for location selection
 */

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Report, EventCluster, RiskAssessment } from '@/lib/types';

// Fix for default marker icon in Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface WeatherMapProps {
  reports: Report[];
  eventClusters?: EventCluster[];
  riskAssessments?: RiskAssessment[];
  isLoading?: boolean;
  onClusterClick?: (cluster: EventCluster) => void;
}

interface SelectedLocation {
  lat: number;
  lon: number;
}

// Custom colored icons based on verification status
const createColoredIcon = (color: string) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="background-color: ${color}; width: 25px; height: 25px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>`,
    iconSize: [25, 25],
    iconAnchor: [12, 12],
  });
};

// Custom icon for selected location (distinct from weather reports)
const createSelectedLocationIcon = () => {
  return L.divIcon({
    className: 'selected-location-marker',
    html: `<div style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); width: 32px; height: 32px; border-radius: 50%; border: 4px solid white; box-shadow: 0 4px 10px rgba(59, 130, 246, 0.5); display: flex; align-items: center; justify-content: center; color: white; font-size: 16px;">📍</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16],
  });
};

// Custom icon for event clusters with risk level indicators
const createEventClusterIcon = (reportCount: number, dominantStatus: string, riskLevel?: string, riskScore?: number) => {
  const getStatusColor = () => {
    switch (dominantStatus) {
      case 'verified':
        return '#10b981';
      case 'disputed':
        return '#f59e0b';
      case 'fake':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const getRiskIndicator = () => {
    if (!riskLevel) return '';
    
    switch (riskLevel) {
      case 'CRITICAL':
        return '<div style="position: absolute; top: -6px; right: -6px; background: #dc2626; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-center; font-size: 14px; box-shadow: 0 2px 6px rgba(220, 38, 38, 0.5); border: 2px solid white; animation: pulse 2s infinite;">🚨</div>';
      case 'HIGH':
        return '<div style="position: absolute; top: -6px; right: -6px; background: #ea580c; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-center; font-size: 14px; box-shadow: 0 2px 6px rgba(234, 88, 12, 0.5); border: 2px solid white;">⚠️</div>';
      case 'MODERATE':
        return '<div style="position: absolute; top: -6px; right: -6px; background: #eab308; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-center; font-size: 10px; box-shadow: 0 2px 4px rgba(234, 179, 8, 0.5); border: 2px solid white;">⚡</div>';
      default:
        return '<div style="position: absolute; top: -4px; right: -4px; background: white; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">⚡</div>';
    }
  };

  const color = getStatusColor();
  return L.divIcon({
    className: 'event-cluster-marker',
    html: `<div style="position: relative; width: 48px; height: 48px;">
            <div style="background: ${color}; width: 48px; height: 48px; border-radius: 50%; border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 14px; position: relative;">
              ${reportCount}
            </div>
            ${getRiskIndicator()}
          </div>`,
    iconSize: [48, 48],
    iconAnchor: [24, 24],
    popupAnchor: [0, -24],
  });
};

const getMarkerColor = (status?: string): string => {
  switch (status) {
    case 'verified':
      return '#10b981'; // green
    case 'disputed':
      return '#f59e0b'; // yellow/amber
    case 'fake':
      return '#ef4444'; // red
    default:
      return '#6b7280'; // gray
  }
};

// Component to handle map clicks for location selection
function MapClickHandler({
  isSelectionMode,
  onLocationSelect,
}: {
  isSelectionMode: boolean;
  onLocationSelect: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(e) {
      if (isSelectionMode) {
        onLocationSelect(e.latlng.lat, e.latlng.lng);
      }
    },
  });

  return null;
}

// Component to fit map bounds to markers
function MapBounds({ reports }: { reports: Report[] }) {
  const map = useMap();

  useEffect(() => {
    if (reports.length > 0) {
      const validReports = reports.filter(
        (r) => r.location?.lat && r.location?.lon
      );

      if (validReports.length > 0) {
        const bounds = L.latLngBounds(
          validReports.map((r) => [r.location!.lat!, r.location!.lon!])
        );
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
      }
    }
  }, [reports, map]);

  return null;
}

export default function WeatherMap({ reports, eventClusters = [], riskAssessments = [], isLoading, onClusterClick }: WeatherMapProps) {
  const [mounted, setMounted] = useState(false);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLocationSelect = (lat: number, lon: number) => {
    setSelectedLocation({ lat, lon });
  };

  const handleClearSelection = () => {
    setSelectedLocation(null);
  };

  const toggleSelectionMode = () => {
    setIsSelectionMode(!isSelectionMode);
  };

  // Create lookup map for risk assessments
  const riskByEventId = new Map(
    riskAssessments.map((r) => [r.event_id, r])
  );

  if (!mounted) {
    return (
      <div className="w-full h-full bg-gray-100 animate-pulse rounded-lg flex items-center justify-center">
        <p className="text-gray-500">Loading map...</p>
      </div>
    );
  }

  const validReports = reports.filter(
    (report) => report.location?.lat && report.location?.lon
  );

  return (
    <div className="w-full h-full rounded-lg overflow-hidden shadow-lg relative">
      {isLoading && (
        <div className="absolute top-4 right-4 bg-white px-4 py-2 rounded-md shadow-md z-[1000] flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
          <span className="text-sm text-gray-700">Loading reports...</span>
        </div>
      )}

      {/* Location Selection Controls */}
      <div className="absolute top-4 left-4 z-[1000] flex flex-col gap-2">
        <button
          onClick={toggleSelectionMode}
          className={`px-4 py-2 rounded-lg font-semibold text-sm shadow-lg transition-all duration-200 flex items-center gap-2 ${
            isSelectionMode
              ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white'
              : 'bg-white text-gray-700 hover:bg-gray-100'
          }`}
          title={isSelectionMode ? 'Selection mode active - click map to place pin' : 'Enable location selection'}
        >
          <span className="text-lg">📍</span>
          <span>{isSelectionMode ? 'Selection Active' : 'Select Location'}</span>
        </button>

        {selectedLocation && (
          <button
            onClick={handleClearSelection}
            className="px-4 py-2 rounded-lg font-semibold text-sm shadow-lg transition-all duration-200 bg-white text-red-600 hover:bg-red-50 flex items-center gap-2"
            title="Clear selected location"
          >
            <span className="text-lg">✕</span>
            <span>Clear Selection</span>
          </button>
        )}
      </div>

      {/* Cursor hint when selection mode is active */}
      {isSelectionMode && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-[1000] bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm font-medium animate-pulse">
          Click anywhere on the map to place a pin
        </div>
      )}

      <MapContainer
        center={[20.5937, 78.9629]} // Center of India
        zoom={5}
        style={{ height: '100%', width: '100%', cursor: isSelectionMode ? 'crosshair' : 'grab' }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapBounds reports={validReports} />

        <MapClickHandler isSelectionMode={isSelectionMode} onLocationSelect={handleLocationSelect} />

        {/* Event Cluster Markers with Risk Indicators */}
        {eventClusters.map((cluster) => {
          const riskAssessment = riskByEventId.get(cluster.event_id);
          return (
            <Marker
              key={cluster.event_id}
              position={[cluster.center.lat, cluster.center.lon]}
              icon={createEventClusterIcon(
                cluster.report_count, 
                cluster.verification_summary.dominant_status,
                riskAssessment?.risk_level,
                riskAssessment?.risk_score
              )}
              eventHandlers={{
                click: () => onClusterClick?.(cluster),
              }}
            >
              <Popup maxWidth={350}>
                <div className="p-3">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2">
                      <span className="text-xl">⚡</span>
                      {cluster.event_type.replace('_', ' ').toUpperCase()} Event
                    </h3>
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-bold uppercase ${
                        cluster.verification_summary.dominant_status === 'verified'
                          ? 'bg-green-100 text-green-800'
                          : cluster.verification_summary.dominant_status === 'disputed'
                          ? 'bg-yellow-100 text-yellow-800'
                          : cluster.verification_summary.dominant_status === 'fake'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {cluster.verification_summary.dominant_status}
                    </span>
                  </div>

                  {/* Risk Assessment Banner */}
                  {riskAssessment && (
                    <div className={`mb-3 p-3 rounded-lg border-2 ${
                      riskAssessment.risk_level === 'CRITICAL'
                        ? 'bg-red-50 border-red-300'
                        : riskAssessment.risk_level === 'HIGH'
                        ? 'bg-orange-50 border-orange-300'
                        : riskAssessment.risk_level === 'MODERATE'
                        ? 'bg-yellow-50 border-yellow-300'
                        : 'bg-green-50 border-green-300'
                    }`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs font-semibold text-gray-600 mb-1">AI Risk Level</div>
                          <div className={`text-lg font-bold ${
                            riskAssessment.risk_level === 'CRITICAL'
                              ? 'text-red-700'
                              : riskAssessment.risk_level === 'HIGH'
                              ? 'text-orange-700'
                              : riskAssessment.risk_level === 'MODERATE'
                              ? 'text-yellow-700'
                              : 'text-green-700'
                          }`}>
                            {riskAssessment.risk_level}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-semibold text-gray-600 mb-1">Risk Score</div>
                          <div className={`text-2xl font-bold ${
                            riskAssessment.risk_level === 'CRITICAL'
                              ? 'text-red-700'
                              : riskAssessment.risk_level === 'HIGH'
                              ? 'text-orange-700'
                              : riskAssessment.risk_level === 'MODERATE'
                              ? 'text-yellow-700'
                              : 'text-green-700'
                          }`}>
                            {riskAssessment.risk_score.toFixed(0)}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="bg-gray-50 rounded-lg p-3 mb-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Total Reports</p>
                        <p className="text-2xl font-bold text-gray-900">{cluster.report_count}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Avg Confidence</p>
                        <p className="text-2xl font-bold text-gray-900">
                          {(cluster.avg_confidence_score * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 text-sm mb-3">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">✓ Verified:</span>
                      <span className="font-bold text-green-600">
                        {cluster.verification_summary.verified}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">⚠ Disputed:</span>
                      <span className="font-bold text-yellow-600">
                        {cluster.verification_summary.disputed}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">✗ Fake:</span>
                      <span className="font-bold text-red-600">{cluster.verification_summary.fake}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">? Unverified:</span>
                      <span className="font-bold text-gray-600">
                        {cluster.verification_summary.unverified}
                      </span>
                    </div>
                  </div>

                  <div className="border-t border-gray-200 pt-3 space-y-2 text-xs text-gray-600">
                    <div>
                      <strong>Center:</strong> {cluster.center.lat.toFixed(4)}°N,{' '}
                      {cluster.center.lon.toFixed(4)}°E
                    </div>
                    <div>
                      <strong>Affected Radius:</strong> {cluster.affected_radius_km} km
                    </div>
                    <div>
                      <strong>Time Range:</strong>
                      <br />
                      {new Date(cluster.time_range.start).toLocaleString('en-IN', {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })}{' '}
                      -{' '}
                      {new Date(cluster.time_range.end).toLocaleString('en-IN', {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })}
                    </div>
                    <div>
                      <strong>Event ID:</strong> <span className="font-mono text-xs">{cluster.event_id}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => onClusterClick?.(cluster)}
                    className="mt-3 w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white text-center px-4 py-2 rounded-lg font-semibold hover:from-blue-700 hover:to-blue-800 transition-all text-sm"
                  >
                    View All {cluster.report_count} Reports
                  </button>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Selected Location Marker (distinct from weather reports) */}
        {selectedLocation && (
          <Marker
            position={[selectedLocation.lat, selectedLocation.lon]}
            icon={createSelectedLocationIcon()}
          >
            <Popup maxWidth={250}>
              <div className="p-3">
                <h3 className="font-bold text-lg text-blue-900 mb-3 flex items-center gap-2">
                  <span className="text-xl">📍</span>
                  Selected Location
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between bg-blue-50 px-3 py-2 rounded-lg">
                    <span className="text-gray-600 font-medium">Latitude:</span>
                    <span className="font-mono font-bold text-blue-900">
                      {selectedLocation.lat.toFixed(6)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-blue-50 px-3 py-2 rounded-lg">
                    <span className="text-gray-600 font-medium">Longitude:</span>
                    <span className="font-mono font-bold text-blue-900">
                      {selectedLocation.lon.toFixed(6)}
                    </span>
                  </div>
                  <a
                    href={`/submit?lat=${selectedLocation.lat}&lon=${selectedLocation.lon}`}
                    className="block mt-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white text-center px-4 py-2 rounded-lg font-semibold hover:from-blue-700 hover:to-blue-800 transition-all"
                  >
                    Submit Report Here
                  </a>
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Weather Report Markers (unchanged) */}
        <MarkerClusterGroup chunkedLoading maxClusterRadius={50}>
          {validReports.map((report) => (
            <Marker
              key={report.id}
              position={[report.location!.lat!, report.location!.lon!]}
              icon={createColoredIcon(getMarkerColor(report.verification_status))}
            >
              <Popup maxWidth={300}>
                <div className="p-2">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-lg capitalize">
                      {report.event_type?.replace('_', ' ') || 'Weather Event'}
                    </h3>
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        report.verification_status === 'verified'
                          ? 'bg-green-100 text-green-800'
                          : report.verification_status === 'disputed'
                          ? 'bg-yellow-100 text-yellow-800'
                          : report.verification_status === 'fake'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {report.verification_status || 'unverified'}
                    </span>
                  </div>

                  <p className="text-sm text-gray-700 mb-2 line-clamp-3">
                    {report.description}
                  </p>

                  <div className="text-xs text-gray-500 space-y-1 mb-2">
                    {report.location?.city && (
                      <p>
                        📍 {report.location.city}
                        {report.location.state && `, ${report.location.state}`}
                      </p>
                    )}
                    {report.location?.lat && report.location?.lon && (
                      <p className="font-mono">
                        🌐 {report.location.lat.toFixed(6)}, {report.location.lon.toFixed(6)}
                      </p>
                    )}
                    <p>
                      🕐 {new Date(report.reported_at).toLocaleString('en-IN')}
                    </p>
                  </div>

                  {report.confidence_score !== undefined && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-gray-600">Confidence Score</span>
                        <span className="font-semibold">
                          {(report.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            report.confidence_score > 0.7
                              ? 'bg-green-500'
                              : report.confidence_score > 0.4
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${report.confidence_score * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  )}

                  {report.signals && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs font-semibold text-gray-600 mb-2">
                        Verification Signals:
                      </p>
                      <div className="space-y-1 text-xs">
                        {report.signals.ground_truth && report.signals.ground_truth.confidence !== undefined && (
                          <div className="flex justify-between">
                            <span>Ground Truth:</span>
                            <span className="font-medium">
                              {(report.signals.ground_truth.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        )}
                        {report.signals.image_hash && report.signals.image_hash.confidence !== undefined && (
                          <div className="flex justify-between">
                            <span>Image Check:</span>
                            <span className="font-medium">
                              {(report.signals.image_hash.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        )}
                        {report.signals.text_dedup && report.signals.text_dedup.confidence !== undefined && (
                          <div className="flex justify-between">
                            <span>Text Dedup:</span>
                            <span className="font-medium">
                              {(report.signals.text_dedup.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
        </MarkerClusterGroup>
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-white p-3 rounded-lg shadow-md z-[1000]">
        <h4 className="text-xs font-semibold text-gray-700 mb-2">
          Verification Status
        </h4>
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span>Verified ({reports.filter((r) => r.verification_status === 'verified').length})</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <span>Disputed ({reports.filter((r) => r.verification_status === 'disputed').length})</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span>Fake ({reports.filter((r) => r.verification_status === 'fake').length})</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full bg-gray-500"></div>
            <span>Unverified ({reports.filter((r) => !r.verification_status || r.verification_status === 'unverified').length})</span>
          </div>
        </div>
      </div>
    </div>
  );
}
