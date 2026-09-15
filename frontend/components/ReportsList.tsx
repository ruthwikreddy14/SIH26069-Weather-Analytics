'use client';

/**
 * All Weather Reports List Component
 * Displays individual weather reports in card/table format with filtering
 */

import { useState } from 'react';
import { Report, VerificationStatus } from '@/lib/types';

interface ReportsListProps {
  reports: Report[];
  isLoading?: boolean;
}

const STATUS_COLORS = {
  verified: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-200',
  },
  disputed: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    border: 'border-yellow-200',
  },
  fake: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-200',
  },
  unverified: {
    bg: 'bg-gray-100',
    text: 'text-gray-800',
    border: 'border-gray-200',
  },
};

export default function ReportsList({ reports, isLoading }: ReportsListProps) {
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Filter reports by status
  const filteredReports = reports.filter((report) => {
    if (statusFilter === 'all') return true;
    if (statusFilter === 'unverified') {
      return !report.verification_status || report.verification_status === 'unverified';
    }
    return report.verification_status === statusFilter;
  });

  // Get status color
  const getStatusColor = (status?: string) => {
    if (!status || status === 'unverified') return STATUS_COLORS.unverified;
    return STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.unverified;
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3 mb-2">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-2.5 rounded-xl">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span>All Weather Reports</span>
          </h2>
          <p className="text-sm text-gray-600 ml-12">
            Showing {filteredReports.length} {filteredReports.length === 1 ? 'report' : 'reports'} • AI-verified weather intelligence
          </p>
        </div>

        {/* Status Filter */}
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              statusFilter === 'all'
                ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-200'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All Reports
          </button>
          <button
            onClick={() => setStatusFilter('verified')}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              statusFilter === 'verified'
                ? 'bg-gradient-to-r from-green-600 to-green-700 text-white shadow-lg shadow-green-200'
                : 'bg-green-50 text-green-700 hover:bg-green-100'
            }`}
          >
            Verified
          </button>
          <button
            onClick={() => setStatusFilter('disputed')}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              statusFilter === 'disputed'
                ? 'bg-gradient-to-r from-amber-600 to-amber-700 text-white shadow-lg shadow-amber-200'
                : 'bg-amber-50 text-amber-700 hover:bg-amber-100'
            }`}
          >
            Disputed
          </button>
          <button
            onClick={() => setStatusFilter('fake')}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              statusFilter === 'fake'
                ? 'bg-gradient-to-r from-red-600 to-red-700 text-white shadow-lg shadow-red-200'
                : 'bg-red-50 text-red-700 hover:bg-red-100'
            }`}
          >
            Fake
          </button>
          <button
            onClick={() => setStatusFilter('unverified')}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              statusFilter === 'unverified'
                ? 'bg-gradient-to-r from-gray-600 to-gray-700 text-white shadow-lg shadow-gray-200'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Unverified
          </button>
        </div>
      </div>

      {/* Reports List */}
      {filteredReports.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">No reports found</p>
          <p className="text-sm mt-2">Try adjusting your filters</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReports.map((report) => {
            const statusColor = getStatusColor(report.verification_status);
            return (
              <div
                key={report.id}
                className={`border-2 ${statusColor.border} rounded-2xl p-6 hover:shadow-2xl transition-all duration-300 bg-gradient-to-br from-white to-gray-50 group hover:-translate-y-1`}
              >
                <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                  {/* Left Column - Main Info */}
                  <div className="md:col-span-8 space-y-4">
                    {/* Header Row */}
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-3 flex-wrap">
                        <span
                          className={`px-4 py-2 rounded-xl text-sm font-bold ${statusColor.bg} ${statusColor.text} shadow-sm flex items-center gap-2`}
                        >
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          {report.verification_status || 'unverified'}
                        </span>
                        <span className="px-4 py-2 rounded-xl text-sm font-bold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 capitalize shadow-sm">
                          {report.event_type?.replace('_', ' ') || 'Weather Event'}
                        </span>
                      </div>
                      <span className="text-xs text-gray-500 font-mono bg-gray-100 px-3 py-1.5 rounded-lg">
                        ID: {report.id.substring(0, 8)}...
                      </span>
                    </div>

                    {/* Description */}
                    <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                      <p className="text-gray-900 text-base leading-relaxed font-medium">
                        {report.description}
                      </p>
                    </div>

                    {/* Location & Time */}
                    <div className="flex items-center gap-6 text-sm text-gray-700 flex-wrap">
                      {report.location?.city && (
                        <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-xl border border-gray-200 shadow-sm">
                          <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          <span className="font-medium">
                            {report.location.city}
                            {report.location.state && `, ${report.location.state}`}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-xl border border-gray-200 shadow-sm">
                        <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="font-medium">{formatDate(report.reported_at)}</span>
                      </div>
                    </div>

                    {/* GPS Coordinates */}
                    {report.location?.lat && report.location?.lon && (
                      <div className="flex items-center gap-2 text-sm text-gray-700 bg-gradient-to-r from-blue-50 to-indigo-50 px-4 py-3 rounded-xl border border-blue-200 shadow-sm">
                        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="font-mono font-semibold text-blue-900">
                          GPS: {report.location.lat.toFixed(6)}, {report.location.lon.toFixed(6)}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Right Column - Stats */}
                  <div className="md:col-span-4 space-y-4">
                    {/* Confidence Score */}
                    {report.confidence_score !== undefined && (
                      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                        <div className="flex items-center justify-between text-sm mb-2">
                          <span className="text-gray-600 font-semibold">Confidence Score</span>
                          <span className="font-bold text-gray-900 text-lg">
                            {(report.confidence_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-3 shadow-inner">
                          <div
                            className={`h-3 rounded-full transition-all shadow-sm ${
                              report.confidence_score > 0.7
                                ? 'bg-gradient-to-r from-green-500 to-green-600'
                                : report.confidence_score > 0.4
                                ? 'bg-gradient-to-r from-yellow-500 to-amber-600'
                                : 'bg-gradient-to-r from-red-500 to-red-600'
                            }`}
                            style={{ width: `${report.confidence_score * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    )}

                    {/* Verification Signals */}
                    {report.signals && report.signals.confidence_calculation && (
                      <div className="bg-gradient-to-br from-gray-50 to-white rounded-xl p-4 border border-gray-200 shadow-sm">
                        <p className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
                          <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Verification Signals
                        </p>
                        <div className="space-y-2 text-sm">
                          {/* Ground Truth Signal */}
                          {report.signals.confidence_calculation.signal_confidences?.ground_truth !== undefined &&
                            report.signals.confidence_calculation.signal_confidences.ground_truth !== null && (
                              <div className="flex justify-between items-center bg-white px-3 py-2 rounded-lg border border-gray-200">
                                <span className="text-gray-600 font-medium">Ground Truth:</span>
                                <span className="font-bold text-blue-900">
                                  {(report.signals.confidence_calculation.signal_confidences.ground_truth * 100).toFixed(0)}%
                                </span>
                              </div>
                            )}
                          
                          {/* Image Hash Signal */}
                          {report.signals.confidence_calculation.signal_confidences?.image_hash !== undefined &&
                            report.signals.confidence_calculation.signal_confidences.image_hash !== null && (
                              <div className="flex justify-between items-center bg-white px-3 py-2 rounded-lg border border-gray-200">
                                <span className="text-gray-600 font-medium">Image Check:</span>
                                <span className="font-bold text-blue-900">
                                  {(report.signals.confidence_calculation.signal_confidences.image_hash * 100).toFixed(0)}%
                                </span>
                              </div>
                            )}
                          
                          {/* Text Deduplication Signal */}
                          {report.signals.confidence_calculation.signal_confidences?.text_dedup !== undefined &&
                            report.signals.confidence_calculation.signal_confidences.text_dedup !== null && (
                              <div className="flex justify-between items-center bg-white px-3 py-2 rounded-lg border border-gray-200">
                                <span className="text-gray-600 font-medium">Text Dedup:</span>
                                <span className="font-bold text-blue-900">
                                  {(report.signals.confidence_calculation.signal_confidences.text_dedup * 100).toFixed(0)}%
                                </span>
                              </div>
                            )}
                          
                          {/* Location Signal */}
                          {report.signals.confidence_calculation.signal_confidences?.location !== undefined &&
                            report.signals.confidence_calculation.signal_confidences.location !== null && (
                              <div className="flex justify-between items-center bg-white px-3 py-2 rounded-lg border border-gray-200">
                                <span className="text-gray-600 font-medium">Location:</span>
                                <span className="font-bold text-blue-900">
                                  {(report.signals.confidence_calculation.signal_confidences.location * 100).toFixed(0)}%
                                </span>
                              </div>
                            )}
                        </div>
                        
                        {/* Confidence Calculation Reasoning */}
                        {report.signals.confidence_calculation.reasoning && (
                          <div className="mt-3 pt-3 border-t border-gray-200">
                            <p className="text-xs text-gray-600 italic leading-relaxed">
                              {report.signals.confidence_calculation.reasoning}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
