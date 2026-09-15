'use client';

/**
 * Main Dashboard Page - National Weather Big Data Analytics Platform
 * Displays interactive map with filters and statistics
 */

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { fetchReports, fetchDashboardStats, fetchEventClusters, fetchRiskAssessments } from '@/lib/api';
import { Report, DashboardStats, FilterParams, EventCluster, RiskAssessment } from '@/lib/types';
import FilterPanel from '@/components/FilterPanel';
import StatCards from '@/components/StatCards';
import ReportsList from '@/components/ReportsList';
import WeatherEvents from '@/components/WeatherEvents';
import ActiveAlerts from '@/components/ActiveAlerts';
import HighRiskEvents from '@/components/HighRiskEvents';

// Dynamically import map to avoid SSR issues with Leaflet
const WeatherMap = dynamic(() => import('@/components/WeatherMap'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-gray-100 animate-pulse rounded-lg flex items-center justify-center">
      <p className="text-gray-500">Loading map...</p>
    </div>
  ),
});

export default function Dashboard() {
  const [reports, setReports] = useState<Report[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [eventClusters, setEventClusters] = useState<EventCluster[]>([]);
  const [riskAssessments, setRiskAssessments] = useState<RiskAssessment[]>([]);
  const [isLoadingReports, setIsLoadingReports] = useState(true);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [isLoadingClusters, setIsLoadingClusters] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentFilters, setCurrentFilters] = useState<FilterParams>({});
  const [selectedCluster, setSelectedCluster] = useState<EventCluster | null>(null);

  // Fetch reports based on filters
  const loadReports = async (filters: FilterParams = {}) => {
    setIsLoadingReports(true);
    setError(null);
    try {
      const response = await fetchReports({ ...filters, limit: 1000 });
      setReports(response.reports);
    } catch (err) {
      console.error('Failed to fetch reports:', err);
      setError('Failed to load weather reports. Please check if the backend is running.');
    } finally {
      setIsLoadingReports(false);
    }
  };

  // Fetch dashboard statistics
  const loadStats = async () => {
    setIsLoadingStats(true);
    try {
      const statsData = await fetchDashboardStats();
      setStats(statsData);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
      // Stats are optional, don't show error if they fail
    } finally {
      setIsLoadingStats(false);
    }
  };

  // Fetch event clusters and risk assessments
  const loadEventClusters = async () => {
    setIsLoadingClusters(true);
    try {
      const [clustersResponse, risksResponse] = await Promise.all([
        fetchEventClusters(currentFilters.event_type, 200),
        fetchRiskAssessments(currentFilters.event_type, 200),
      ]);
      setEventClusters(clustersResponse.clusters || []);
      setRiskAssessments(risksResponse.assessments || []);
    } catch (err) {
      console.error('Failed to fetch event clusters or risk assessments:', err);
      // Clusters are optional, don't show error if they fail
      setEventClusters([]);
      setRiskAssessments([]);
    } finally {
      setIsLoadingClusters(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadReports();
    loadStats();
    loadEventClusters();
  }, []);

  // Handle filter changes
  const handleFilterChange = (filters: FilterParams) => {
    setCurrentFilters(filters);
    loadReports(filters);
    loadEventClusters();
  };

  // Handle cluster click from map or events list
  const handleClusterClick = (cluster: EventCluster) => {
    setSelectedCluster(cluster);
    // Scroll to the event cluster info or expand reports
    const element = document.getElementById('weather-events');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-50">
      {/* Header */}
      <header className="bg-white shadow-md border-b border-blue-100">
        <div className="container mx-auto px-4 py-5">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <div className="bg-gradient-to-br from-blue-600 to-blue-700 p-3 rounded-xl shadow-lg">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                  National Weather Analytics Platform
                </h1>
                <p className="text-sm text-gray-600 mt-0.5 flex items-center gap-2">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                    <span className="font-medium text-green-700">System Online</span>
                  </span>
                  <span className="text-gray-400">•</span>
                  <span>Real-time monitoring with AI verification</span>
                </p>
              </div>
            </div>
            <Link
              href="/submit"
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold py-3 px-8 rounded-xl transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Submit Report
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">⚠️</span>
              <span>{error}</span>
            </div>
            <button
              onClick={() => {
                setError(null);
                loadReports(currentFilters);
              }}
              className="text-red-700 hover:text-red-900 font-medium"
            >
              Retry
            </button>
          </div>
        )}

        {/* Statistics Cards */}
        <StatCards stats={stats} isLoading={isLoadingStats} />

        {/* Active Alerts Section */}
        <div className="mt-6">
          <ActiveAlerts />
        </div>

        {/* High-Risk Events Section */}
        <div className="mt-6">
          <HighRiskEvents />
        </div>

        {/* Filters */}
        <FilterPanel
          onFilterChange={handleFilterChange}
          isLoading={isLoadingReports}
        />

        {/* Map Container */}
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-2.5 rounded-xl">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                  </svg>
                </div>
                <span>Weather Reports Map</span>
              </h2>
              <p className="text-sm text-gray-600 mt-1 ml-12">
                Interactive visualization of {reports.length} {reports.length === 1 ? 'report' : 'reports'} with GPS verification
              </p>
            </div>
          </div>

          <div className="w-full h-[650px] rounded-xl overflow-hidden shadow-inner border border-gray-200">
            <WeatherMap 
              reports={reports} 
              eventClusters={eventClusters}
              riskAssessments={riskAssessments}
              isLoading={isLoadingReports} 
              onClusterClick={handleClusterClick}
            />
          </div>
        </div>

        {/* Weather Events Section */}
        <div id="weather-events" className="mt-6">
          <WeatherEvents 
            selectedEventType={currentFilters.event_type}
            onEventClick={handleClusterClick}
          />
        </div>

        {/* All Weather Reports List */}
        <div className="mt-6">
          <ReportsList reports={reports} isLoading={isLoadingReports} />
        </div>

        {/* Info Panel */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-200 rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-blue-600 p-2 rounded-xl">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-bold text-blue-900 text-lg">About Platform</h3>
            </div>
            <p className="text-sm text-blue-800 leading-relaxed">
              This platform collects and verifies weather reports from citizens
              across India using AI-powered analysis and real-time monitoring.
            </p>
          </div>
          <div className="bg-gradient-to-br from-green-50 to-green-100 border-2 border-green-200 rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-green-600 p-2 rounded-xl">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-bold text-green-900 text-lg">AI Verification</h3>
            </div>
            <p className="text-sm text-green-800 leading-relaxed">
              Each report is automatically verified against satellite data, weather
              APIs, and checked for duplicates using advanced ML algorithms.
            </p>
          </div>
          <div className="bg-gradient-to-br from-purple-50 to-purple-100 border-2 border-purple-200 rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-purple-600 p-2 rounded-xl">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="font-bold text-purple-900 text-lg">High Accuracy</h3>
            </div>
            <p className="text-sm text-purple-800 leading-relaxed">
              Confidence scores combine ground-truth weather data, image analysis,
              and text deduplication for reliable results.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gradient-to-r from-gray-900 to-gray-800 border-t border-gray-700 mt-16">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">
            <div className="flex items-center justify-center gap-3 mb-3">
              <div className="bg-blue-600 p-2 rounded-lg">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
              <p className="text-lg font-bold text-white">
                SIH26069: National Weather Big Data Analytics Platform
              </p>
            </div>
            <p className="text-sm text-gray-400">
              Built with Next.js, FastAPI, PostgreSQL & ML verification pipeline
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Smart India Hackathon 2026 • Government of India Initiative
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
