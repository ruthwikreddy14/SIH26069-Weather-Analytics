'use client';

/**
 * Statistics Cards Component - Enhanced for SIH Presentation
 * Displays total reports, verified, fake, and disputed counts
 */

import { DashboardStats } from '@/lib/types';

interface StatCardsProps {
  stats: DashboardStats | null;
  isLoading?: boolean;
}

export default function StatCards({ stats, isLoading }: StatCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white rounded-2xl p-6 shadow-lg animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-24 mb-3"></div>
            <div className="h-10 bg-gray-200 rounded w-16 mb-2"></div>
            <div className="h-3 bg-gray-200 rounded w-32"></div>
          </div>
        ))}
      </div>
    );
  }

  const statCards = [
    {
      label: 'Total Reports',
      value: stats?.total_reports || 0,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      bgColor: 'from-blue-500 to-blue-600',
      textColor: 'text-blue-600',
      lightBg: 'bg-blue-50',
      percentage: null,
      subtext: 'Submitted by citizens',
    },
    {
      label: 'Verified Reports',
      value: stats?.verified_count || 0,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      bgColor: 'from-green-500 to-green-600',
      textColor: 'text-green-600',
      lightBg: 'bg-green-50',
      percentage: stats?.verified_percentage || 0,
      subtext: 'AI-verified authentic',
    },
    {
      label: 'Disputed Reports',
      value: stats?.disputed_count || 0,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
      bgColor: 'from-yellow-500 to-amber-600',
      textColor: 'text-amber-600',
      lightBg: 'bg-amber-50',
      percentage: stats && stats.total_reports > 0 ? ((stats.disputed_count / stats.total_reports) * 100) : 0,
      subtext: 'Require review',
    },
    {
      label: 'Fake Reports',
      value: stats?.fake_count || 0,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      bgColor: 'from-red-500 to-red-600',
      textColor: 'text-red-600',
      lightBg: 'bg-red-50',
      percentage: stats && stats.total_reports > 0 ? ((stats.fake_count / stats.total_reports) * 100) : 0,
      subtext: 'Flagged as false',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {statCards.map((card, index) => (
        <div
          key={index}
          className="bg-white rounded-2xl p-6 shadow-lg hover:shadow-xl transition-all duration-300 border border-gray-100 group hover:-translate-y-1"
        >
          <div className="flex items-start justify-between mb-4">
            <div className={`${card.lightBg} p-3 rounded-xl group-hover:scale-110 transition-transform duration-300`}>
              <div className={card.textColor}>{card.icon}</div>
            </div>
            {card.percentage !== null && (
              <div className={`${card.lightBg} ${card.textColor} text-xs font-bold px-2.5 py-1 rounded-full`}>
                {card.percentage.toFixed(1)}%
              </div>
            )}
          </div>
          <h3 className="text-sm font-medium text-gray-600 mb-1">{card.label}</h3>
          <p className={`text-3xl font-bold ${card.textColor} mb-1`}>
            {card.value.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500">{card.subtext}</p>
        </div>
      ))}
    </div>
  );
}
