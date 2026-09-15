'use client';

/**
 * Weather Report Submission Form
 * Allows citizens to submit weather event reports
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { submitReport } from '@/lib/api';
import { EVENT_TYPES, INDIAN_STATES, ReportSubmitRequest } from '@/lib/types';

export default function SubmitReport() {
  const router = useRouter();
  const [formData, setFormData] = useState<ReportSubmitRequest>({
    event_type: '',
    description: '',
    city: '',
    state: '',
    gps: undefined,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [reportId, setReportId] = useState<string | null>(null);
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'loading' | 'success' | 'error' | 'denied' | 'unavailable'>('idle');
  const [gpsError, setGpsError] = useState<string | null>(null);

  const requestGeolocation = () => {
    if (!('geolocation' in navigator)) {
      setGpsStatus('unavailable');
      setGpsError('GPS location is currently unavailable.');
      return;
    }

    setGpsStatus('loading');
    setGpsError(null);

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setFormData((prev) => ({
          ...prev,
          gps: {
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          },
        }));
        setGpsStatus('success');
      },
      (err) => {
        console.log('Geolocation error:', err);
        if (err.code === err.PERMISSION_DENIED) {
          setGpsStatus('denied');
          setGpsError('Location permission denied. You can submit without GPS.');
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setGpsStatus('unavailable');
          setGpsError('GPS location is currently unavailable.');
        } else if (err.code === err.TIMEOUT) {
          setGpsStatus('error');
          setGpsError('Location request timed out. Please try again.');
        } else {
          setGpsStatus('error');
          setGpsError('Unable to get location. You can submit without GPS.');
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await submitReport(formData);
      setReportId(response.report_id);
      setSuccess(true);
    } catch (err: any) {
      console.error('Failed to submit report:', err);
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          // Pydantic validation errors
          const errors = err.response.data.detail.map((e: any) => e.msg).join(', ');
          setError(`Validation error: ${errors}`);
        } else {
          setError(err.response.data.detail);
        }
      } else {
        setError('Failed to submit report. Please check if the backend is running.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
          <div className="text-6xl mb-4">✅</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Report Submitted!</h2>
          <p className="text-gray-600 mb-4">
            Your weather report has been submitted successfully and is now being verified.
          </p>
          {reportId && (
            <p className="text-sm text-gray-500 mb-6">
              Report ID: <code className="bg-gray-100 px-2 py-1 rounded">{reportId}</code>
            </p>
          )}
          <div className="flex gap-4">
            <button
              onClick={() => {
                setSuccess(false);
                setReportId(null);
                setFormData({
                  event_type: '',
                  description: '',
                  city: '',
                  state: '',
                  gps: formData.gps, // Keep GPS if available
                });
              }}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              Submit Another
            </button>
            <Link
              href="/"
              className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded-lg transition-colors text-center"
            >
              View Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                📝 Submit Weather Report
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                Report weather events in your area to help monitor conditions across India
              </p>
            </div>
            <Link
              href="/"
              className="text-blue-600 hover:text-blue-700 font-medium"
            >
              ← Back to Dashboard
            </Link>
          </div>
        </div>
      </header>

      {/* Form */}
      <main className="container mx-auto px-4 py-8 max-w-2xl">
        <div className="bg-white rounded-lg shadow-md p-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
              <span className="text-xl">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Event Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Event Type <span className="text-red-500">*</span>
              </label>
              <select
                name="event_type"
                value={formData.event_type}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              >
                <option value="">Select an event type</option>
                {EVENT_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                required
                minLength={10}
                maxLength={500}
                rows={4}
                placeholder="Describe the weather event in detail (10-500 characters)"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 placeholder:text-gray-400"
              />
              <p className="text-xs text-gray-500 mt-1">
                {formData.description.length}/500 characters
              </p>
            </div>

            {/* Location */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  City <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="city"
                  value={formData.city}
                  onChange={handleChange}
                  required
                  minLength={2}
                  maxLength={100}
                  placeholder="e.g., Mumbai"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 placeholder:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  State <span className="text-red-500">*</span>
                </label>
                <select
                  name="state"
                  value={formData.state}
                  onChange={handleChange}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                >
                  <option value="">Select a state</option>
                  {INDIAN_STATES.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* GPS Coordinates */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  GPS Coordinates (Optional)
                </label>
                {gpsStatus === 'loading' && (
                  <span className="text-xs text-blue-600">📍 Detecting location...</span>
                )}
                {gpsStatus === 'success' && (
                  <span className="text-xs text-green-600">✓ Location detected</span>
                )}
              </div>
              
              {formData.gps ? (
                <div className="text-sm text-gray-900">
                  <p className="font-medium">Latitude: {formData.gps.lat.toFixed(6)}</p>
                  <p className="font-medium">Longitude: {formData.gps.lon.toFixed(6)}</p>
                  <button
                    type="button"
                    onClick={() => {
                      setFormData((prev) => ({ ...prev, gps: undefined }));
                      setGpsStatus('idle');
                      setGpsError(null);
                    }}
                    className="text-xs text-red-600 hover:text-red-700 mt-2 underline"
                  >
                    Remove GPS
                  </button>
                </div>
              ) : (
                <div>
                  <p className="text-sm text-gray-600 mb-3">
                    GPS coordinates improve verification accuracy
                  </p>
                  <button
                    type="button"
                    onClick={requestGeolocation}
                    disabled={gpsStatus === 'loading'}
                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-medium py-2 px-4 rounded-md transition-colors"
                  >
                    {gpsStatus === 'loading' ? 'Getting Location...' : '📍 Get Current Location'}
                  </button>
                  {gpsError && (
                    <p className="text-xs text-orange-600 mt-2">
                      {gpsError}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Submit Button */}
            <div className="flex gap-4">
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium py-3 px-6 rounded-lg transition-colors"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Report'}
              </button>
              <Link
                href="/"
                className="px-6 py-3 border border-gray-300 text-gray-700 hover:bg-gray-50 rounded-lg transition-colors text-center"
              >
                Cancel
              </Link>
            </div>
          </form>
        </div>

        {/* Info Panel */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900 mb-2">ℹ️ How it works</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Your report will be automatically verified against weather data</li>
            <li>• Verification typically completes within a few seconds</li>
            <li>• Reports are checked for duplicates and accuracy</li>
            <li>• You can view your submitted report on the dashboard</li>
          </ul>
        </div>
      </main>
    </div>
  );
}
