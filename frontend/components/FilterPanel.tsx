'use client';

/**
 * Filter panel component for dashboard
 * Allows filtering by date range, event type, state, and verification status
 */

import { useState } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import {
  FilterParams,
  EVENT_TYPES,
  VERIFICATION_STATUSES,
  INDIAN_STATES,
} from '@/lib/types';

interface FilterPanelProps {
  onFilterChange: (filters: FilterParams) => void;
  isLoading?: boolean;
}

export default function FilterPanel({ onFilterChange, isLoading }: FilterPanelProps) {
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [selectedState, setSelectedState] = useState<string>('');
  const [isExpanded, setIsExpanded] = useState(true);

  const handleEventTypeChange = (eventType: string) => {
    setSelectedEventTypes((prev) =>
      prev.includes(eventType)
        ? prev.filter((t) => t !== eventType)
        : [...prev, eventType]
    );
  };

  const handleStatusChange = (status: string) => {
    setSelectedStatuses((prev) =>
      prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
    );
  };

  const handleApplyFilters = () => {
    const filters: FilterParams = {};

    if (startDate) {
      filters.date_from = startDate.toISOString();
    }
    if (endDate) {
      filters.date_to = endDate.toISOString();
    }
    if (selectedEventTypes.length > 0) {
      filters.event_type = selectedEventTypes.join(',');
    }
    if (selectedStatuses.length > 0) {
      filters.status = selectedStatuses.join(',');
    }
    if (selectedState) {
      filters.state = selectedState;
    }

    onFilterChange(filters);
  };

  const handleReset = () => {
    setStartDate(null);
    setEndDate(null);
    setSelectedEventTypes([]);
    setSelectedStatuses([]);
    setSelectedState('');
    onFilterChange({});
  };

  const hasActiveFilters =
    startDate ||
    endDate ||
    selectedEventTypes.length > 0 ||
    selectedStatuses.length > 0 ||
    selectedState;

  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <span>🔍</span> Filters
          {hasActiveFilters && (
            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
              Active
            </span>
          )}
        </h2>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-gray-500 hover:text-gray-700 lg:hidden"
        >
          {isExpanded ? '▲' : '▼'}
        </button>
      </div>

      <div className={`space-y-4 ${isExpanded ? 'block' : 'hidden lg:block'}`}>
        {/* Date Range */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              From Date
            </label>
            <DatePicker
              selected={startDate}
              onChange={(date: Date | null) => setStartDate(date)}
              selectsStart
              startDate={startDate}
              endDate={endDate}
              dateFormat="dd/MM/yyyy"
              placeholderText="Select start date"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              isClearable
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              To Date
            </label>
            <DatePicker
              selected={endDate}
              onChange={(date: Date | null) => setEndDate(date)}
              selectsEnd
              startDate={startDate}
              endDate={endDate}
              minDate={startDate || undefined}
              dateFormat="dd/MM/yyyy"
              placeholderText="Select end date"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              isClearable
            />
          </div>
        </div>

        {/* Event Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Event Type
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {EVENT_TYPES.map((type) => (
              <label
                key={type.value}
                className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 p-2 rounded"
              >
                <input
                  type="checkbox"
                  checked={selectedEventTypes.includes(type.value)}
                  onChange={() => handleEventTypeChange(type.value)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-gray-700">{type.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Verification Status */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Verification Status
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {VERIFICATION_STATUSES.map((status) => (
              <label
                key={status.value}
                className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 p-2 rounded"
              >
                <input
                  type="checkbox"
                  checked={selectedStatuses.includes(status.value)}
                  onChange={() => handleStatusChange(status.value)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="flex items-center gap-1">
                  <span
                    className={`w-3 h-3 rounded-full ${
                      status.color === 'green'
                        ? 'bg-green-500'
                        : status.color === 'yellow'
                        ? 'bg-yellow-500'
                        : status.color === 'red'
                        ? 'bg-red-500'
                        : 'bg-gray-500'
                    }`}
                  ></span>
                  <span className="text-gray-700">{status.label}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* State Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            State
          </label>
          <select
            value={selectedState}
            onChange={(e) => setSelectedState(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All States</option>
            {INDIAN_STATES.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          <button
            onClick={handleApplyFilters}
            disabled={isLoading}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
          >
            {isLoading ? 'Loading...' : 'Apply Filters'}
          </button>
          <button
            onClick={handleReset}
            disabled={isLoading || !hasActiveFilters}
            className="px-4 py-2 border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
