'use client';

import { useEffect, useState } from 'react';
import {
  getAnalyticsOverview,
  getWeeklyTrends,
  getTopAttendees,
  getBranchAnalytics,
  getLatenessReport,
  type OverallAnalytics,
  type WeeklyTrend,
  type TopAttendee,
  type BranchAnalytics,
  type LatenessReport,
} from '@/lib/api';
import {
  AnalyticsOverviewShimmer,
  ChartShimmer,
  TableShimmer,
} from '@/components/Shimmer';

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<OverallAnalytics | null>(null);
  const [weeklyTrends, setWeeklyTrends] = useState<WeeklyTrend[]>([]);
  const [topAttendees, setTopAttendees] = useState<TopAttendee[]>([]);
  const [branches, setBranches] = useState<BranchAnalytics[]>([]);
  const [latenessReport, setLatenessReport] = useState<LatenessReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'trends' | 'members' | 'lateness'>('overview');

  async function loadAnalytics() {
    setLoading(true);
    try {
      const [overviewData, trendsData, topData, branchData, lateData] = await Promise.all([
        getAnalyticsOverview(),
        getWeeklyTrends(undefined, 4),
        getTopAttendees(10),
        getBranchAnalytics(),
        getLatenessReport(30),
      ]);
      setOverview(overviewData);
      setWeeklyTrends(trendsData);
      setTopAttendees(topData);
      setBranches(branchData);
      setLatenessReport(lateData);
      setError('');
    } catch {
      setError('Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalytics();
  }, []);

  function formatTrend(trend: string) {
    if (trend === 'up') return { icon: '↑', color: 'text-green-600', bg: 'bg-green-50' };
    if (trend === 'down') return { icon: '↓', color: 'text-red-600', bg: 'bg-red-50' };
    return { icon: '→', color: 'text-gray-600', bg: 'bg-gray-50' };
  }

  // Calculate max value for chart scaling
  const maxAttendance = Math.max(...weeklyTrends.map(t => t.attendance_count), 1);

  if (loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">Analytics</h1>
          <p className="text-[15px] text-foreground-secondary mt-1">Attendance insights and trends.</p>
        </div>
        <AnalyticsOverviewShimmer />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">Analytics</h1>
          <p className="text-[15px] text-foreground-secondary mt-1">Attendance insights and trends.</p>
        </div>
        <button
          onClick={loadAnalytics}
          className="px-4 py-2 text-[14px] font-medium border border-divider rounded-xl hover:bg-background-secondary transition-colors duration-200"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-danger-light border border-danger/20 rounded-2xl p-5 flex items-start gap-3">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-danger flex-shrink-0 mt-0.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p className="text-[14px] text-danger">{error}</p>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-primary">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-foreground-secondary uppercase tracking-wider">Total Members</p>
              <p className="text-[24px] font-bold text-foreground">{overview?.total_members || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-600">
                <path d="M9 11l3 3L22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-foreground-secondary uppercase tracking-wider">Total Attendance</p>
              <p className="text-[24px] font-bold text-foreground">{overview?.total_attendance || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-blue-600">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <line x1="19" y1="8" x2="19" y2="14" />
                <line x1="22" y1="11" x2="16" y2="11" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-foreground-secondary uppercase tracking-wider">Visitors</p>
              <p className="text-[24px] font-bold text-foreground">{overview?.total_visitors || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-amber-600">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-foreground-secondary uppercase tracking-wider">Lateness Rate</p>
              <p className="text-[24px] font-bold text-foreground">{((overview?.overall_lateness_rate || 0) * 100).toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Trend Card */}
      {overview?.attendance_trend && (
        <div className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center gap-4">
            <div className={`px-3 py-1.5 rounded-lg ${formatTrend(overview.attendance_trend.trend_direction).bg}`}>
              <span className={`text-[20px] font-bold ${formatTrend(overview.attendance_trend.trend_direction).color}`}>
                {formatTrend(overview.attendance_trend.trend_direction).icon} {Math.abs(overview.attendance_trend.trend_percentage).toFixed(1)}%
              </span>
            </div>
            <div>
              <p className="text-[14px] font-medium text-foreground">
                Attendance {overview.attendance_trend.trend_direction === 'up' ? 'increased' : overview.attendance_trend.trend_direction === 'down' ? 'decreased' : 'stable'}
              </p>
              <p className="text-[13px] text-foreground-secondary">
                Avg: {overview.attendance_trend.average_attendance.toFixed(0)} per service
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-divider pb-2">
        {[
          { key: 'overview', label: 'Weekly Trends' },
          { key: 'members', label: 'Top Members' },
          { key: 'lateness', label: 'Lateness Report' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as 'overview' | 'members' | 'lateness')}
            className={`px-4 py-2 text-[14px] font-medium rounded-lg transition-colors duration-200 ${
              activeTab === tab.key
                ? 'bg-primary text-white'
                : 'text-foreground-secondary hover:bg-background-secondary'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Weekly Trends Chart */}
      {activeTab === 'overview' && (
        <div className="bg-card border border-divider rounded-2xl p-6 shadow-[var(--shadow-sm)]">
          <h3 className="text-[17px] font-semibold text-foreground mb-6">Weekly Attendance Trend</h3>
          
          {weeklyTrends.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-foreground-secondary">
              No trend data available
            </div>
          ) : (
            <div className="space-y-4">
              {/* Chart */}
              <div className="h-64 flex items-end gap-2">
                {weeklyTrends.map((trend, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-2">
                    <div className="w-full flex flex-col items-center gap-1">
                      <span className="text-[11px] font-medium text-foreground-secondary">
                        {trend.attendance_count}
                      </span>
                      <div
                        className="w-full bg-primary rounded-t-lg transition-all duration-500 hover:bg-primary/80"
                        style={{
                          height: `${(trend.attendance_count / maxAttendance) * 200}px`,
                          minHeight: '4px',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              
              {/* X-axis labels */}
              <div className="flex gap-2">
                {weeklyTrends.map((trend, i) => (
                  <div key={i} className="flex-1 text-center">
                    <p className="text-[11px] font-medium text-foreground">{trend.day}</p>
                    <p className="text-[10px] text-foreground-secondary">{trend.date}</p>
                  </div>
                ))}
              </div>

              {/* Legend */}
              <div className="flex items-center gap-6 pt-4 border-t border-divider">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-primary rounded" />
                  <span className="text-[12px] text-foreground-secondary">Attendance</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-blue-400 rounded" />
                  <span className="text-[12px] text-foreground-secondary">Unique Members</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-400 rounded" />
                  <span className="text-[12px] text-foreground-secondary">Visitors</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Top Attendees */}
      {activeTab === 'members' && (
        <div className="bg-card border border-divider rounded-2xl overflow-hidden shadow-[var(--shadow-sm)]">
          <div className="p-5 border-b border-divider">
            <h3 className="text-[17px] font-semibold text-foreground">Top Attendees</h3>
            <p className="text-[13px] text-foreground-secondary mt-1">Members with highest attendance rates</p>
          </div>
          
          {topAttendees.length === 0 ? (
            <div className="p-16 text-center text-foreground-secondary">
              No attendance data available
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-divider bg-background-secondary/50">
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Rank</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Member</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Attendance</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Rate</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Late</th>
                </tr>
              </thead>
              <tbody>
                {topAttendees.map((attendee, index) => (
                  <tr key={attendee.member_id} className="border-b border-divider last:border-b-0 hover:bg-card-hover transition-colors">
                    <td className="py-3.5 px-5">
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold ${
                        index === 0 ? 'bg-amber-100 text-amber-700' :
                        index === 1 ? 'bg-gray-200 text-gray-700' :
                        index === 2 ? 'bg-orange-100 text-orange-700' :
                        'bg-background-secondary text-foreground-secondary'
                      }`}>
                        {index + 1}
                      </div>
                    </td>
                    <td className="py-3.5 px-5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-primary/10 text-primary rounded-full flex items-center justify-center text-[12px] font-semibold">
                          {attendee.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="text-[14px] font-medium text-foreground">{attendee.name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-5 text-[14px] text-foreground tabular-nums">
                      {attendee.attendance_count}
                    </td>
                    <td className="py-3.5 px-5">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 max-w-[100px] h-2 bg-background-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded-full transition-all duration-500"
                            style={{ width: `${attendee.attendance_rate * 100}%` }}
                          />
                        </div>
                        <span className="text-[12px] text-foreground-secondary tabular-nums">
                          {(attendee.attendance_rate * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-5 text-[14px] text-foreground-secondary tabular-nums">
                      {attendee.late_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Lateness Report */}
      {activeTab === 'lateness' && (
        <div className="bg-card border border-divider rounded-2xl overflow-hidden shadow-[var(--shadow-sm)]">
          <div className="p-5 border-b border-divider">
            <h3 className="text-[17px] font-semibold text-foreground">Lateness Report</h3>
            <p className="text-[13px] text-foreground-secondary mt-1">Members who have been late (last 30 days)</p>
          </div>
          
          {latenessReport.length === 0 ? (
            <div className="p-16 text-center text-foreground-secondary">
              No lateness data available
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-divider bg-background-secondary/50">
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Member</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Total Present</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Times Late</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Lateness Rate</th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">Avg Late By</th>
                </tr>
              </thead>
              <tbody>
                {latenessReport.map((report) => (
                  <tr key={report.member_id} className="border-b border-divider last:border-b-0 hover:bg-card-hover transition-colors">
                    <td className="py-3.5 px-5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center text-[12px] font-semibold">
                          {report.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="text-[14px] font-medium text-foreground">{report.name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-5 text-[14px] text-foreground tabular-nums">
                      {report.total_attendance}
                    </td>
                    <td className="py-3.5 px-5 text-[14px] text-amber-600 font-medium tabular-nums">
                      {report.late_count}
                    </td>
                    <td className="py-3.5 px-5">
                      <span className={`px-2 py-1 rounded-full text-[12px] font-medium ${
                        report.lateness_rate > 0.5 ? 'bg-red-100 text-red-700' :
                        report.lateness_rate > 0.25 ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {(report.lateness_rate * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3.5 px-5 text-[14px] text-foreground-secondary tabular-nums">
                      {report.average_late_minutes.toFixed(0)} min
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Branch Analytics */}
      {branches.length > 1 && (
        <div className="bg-card border border-divider rounded-2xl overflow-hidden shadow-[var(--shadow-sm)]">
          <div className="p-5 border-b border-divider">
            <h3 className="text-[17px] font-semibold text-foreground">Branch Comparison</h3>
            <p className="text-[13px] text-foreground-secondary mt-1">Attendance across all branches</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-5">
            {branches.map((branch) => (
              <div key={branch.branch_id} className="bg-background-secondary/50 rounded-xl p-4">
                <h4 className="text-[15px] font-semibold text-foreground mb-3">{branch.branch_name}</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-[13px]">
                    <span className="text-foreground-secondary">Members</span>
                    <span className="font-medium text-foreground">{branch.total_members}</span>
                  </div>
                  <div className="flex justify-between text-[13px]">
                    <span className="text-foreground-secondary">Total Attendance</span>
                    <span className="font-medium text-foreground">{branch.total_attendance}</span>
                  </div>
                  <div className="flex justify-between text-[13px]">
                    <span className="text-foreground-secondary">Avg Attendance</span>
                    <span className="font-medium text-foreground">{branch.average_attendance.toFixed(0)}</span>
                  </div>
                  <div className="flex justify-between text-[13px]">
                    <span className="text-foreground-secondary">Visitors</span>
                    <span className="font-medium text-foreground">{branch.visitor_count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
