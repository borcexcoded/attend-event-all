"use client";

import { useEffect, useState } from "react";
import { getAttendanceStats, getTodayAttendance, getMembers, type AttendanceStats } from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [todayMembers, setTodayMembers] = useState<string[]>([]);
  const [totalMembers, setTotalMembers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [statsData, todayData, membersData] = await Promise.all([
          getAttendanceStats(30),
          getTodayAttendance(),
          getMembers(),
        ]);
        setStats(statsData);
        setTodayMembers(todayData.members);
        setTotalMembers(membersData.total);
      } catch (err) {
        setError(
          "Could not connect to the server. Make sure the backend is running on port 8000."
        );
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-[15px] text-foreground-secondary">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-danger-light border border-danger/20 rounded-2xl p-8 text-center max-w-lg mx-auto mt-20">
        <div className="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center mx-auto mb-4">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-danger">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <p className="text-foreground font-semibold text-[17px]">Connection Error</p>
        <p className="text-foreground-secondary text-[14px] mt-2 leading-relaxed">{error}</p>
        <p className="text-[13px] text-foreground-secondary mt-5">
          Run: <code className="bg-background-secondary px-2 py-1 rounded-md font-mono text-[12px]">python run.py</code>{" "}
          from the project root
        </p>
      </div>
    );
  }

  const maxCount = stats?.daily_breakdown
    ? Math.max(...stats.daily_breakdown.map((d) => d.count), 1)
    : 1;

  return (
    <div className="space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">
          Dashboard
        </h1>
        <p className="text-[15px] text-foreground-secondary mt-1">
          Your church attendance overview at a glance.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Today"
          value={stats?.today_count ?? 0}
          subtitle="attendance"
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          }
        />
        <StatCard
          title="Members"
          value={totalMembers}
          subtitle="registered"
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          }
        />
        <StatCard
          title="This Month"
          value={stats?.unique_members ?? 0}
          subtitle="unique members"
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          }
        />
        <StatCard
          title="Total"
          value={stats?.total_records ?? 0}
          subtitle="records (30 days)"
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Attendance */}
        <div className="bg-card border border-divider rounded-2xl p-7 shadow-[var(--shadow-sm)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] mb-5">
            Today&apos;s Members
          </h2>
          {todayMembers.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-foreground-secondary text-[14px]">
                No attendance recorded today.
              </p>
              <p className="text-foreground-secondary text-[13px] mt-1">
                Use Take Attendance to get started.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {todayMembers.map((name) => (
                <div
                  key={name}
                  className="flex items-center gap-3.5 p-3 rounded-xl hover:bg-background-secondary transition-colors duration-200"
                >
                  <div className="w-9 h-9 bg-primary/10 text-primary rounded-full flex items-center justify-center text-[14px] font-semibold">
                    {name.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-[14px] font-medium text-foreground">{name}</span>
                  <span className="ml-auto flex items-center gap-1.5 text-success text-[13px] font-medium">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    Present
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Weekly Breakdown */}
        <div className="bg-card border border-divider rounded-2xl p-7 shadow-[var(--shadow-sm)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] mb-5">
            Last 7 Days
          </h2>
          {stats?.daily_breakdown && stats.daily_breakdown.length > 0 ? (
            <div className="space-y-3">
              {stats.daily_breakdown.map((day) => {
                const pct = (day.count / maxCount) * 100;
                return (
                  <div key={day.date} className="flex items-center gap-4">
                    <span className="text-[13px] text-foreground-secondary w-[100px] flex-shrink-0 tabular-nums">
                      {new Date(day.date + "T00:00:00").toLocaleDateString("en-US", {
                        weekday: "short",
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                    <div className="flex-1 bg-background-secondary rounded-full h-[26px] overflow-hidden">
                      <div
                        className="bg-primary h-full rounded-full flex items-center justify-end pr-2.5 transition-all duration-700 ease-out"
                        style={{ width: `${Math.max(day.count > 0 ? 12 : 0, pct)}%` }}
                      >
                        {day.count > 0 && (
                          <span className="text-[11px] text-white font-semibold">
                            {day.count}
                          </span>
                        )}
                      </div>
                    </div>
                    {day.count === 0 && (
                      <span className="text-[12px] text-foreground-secondary w-4">0</span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-8 text-center">
              <p className="text-foreground-secondary text-[14px]">No data for the past week.</p>
            </div>
          )}
        </div>
      </div>

      {/* Top Attendees */}
      {stats?.top_attendees && stats.top_attendees.length > 0 && (
        <div className="bg-card border border-divider rounded-2xl p-7 shadow-[var(--shadow-sm)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] mb-5">
            Top Attendees
          </h2>
          <p className="text-[13px] text-foreground-secondary -mt-3 mb-5">Last 30 days</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {stats.top_attendees.map((attendee, i) => (
              <div
                key={attendee.name}
                className="flex items-center gap-3 p-3.5 rounded-xl bg-background-secondary hover:shadow-[var(--shadow-sm)] transition-all duration-200"
              >
                <span className="text-[15px] font-bold text-foreground-secondary tabular-nums w-5">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-[14px] font-medium text-foreground truncate">{attendee.name}</p>
                  <p className="text-[12px] text-foreground-secondary">{attendee.count} times</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon,
}: {
  title: string;
  value: number;
  subtitle?: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-divider rounded-2xl p-6 shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] transition-shadow duration-300">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[13px] font-medium text-foreground-secondary uppercase tracking-wide">
          {title}
        </span>
        <span className="w-9 h-9 rounded-xl bg-background-secondary flex items-center justify-center text-foreground-secondary">
          {icon}
        </span>
      </div>
      <p className="text-[32px] font-bold tracking-[-0.04em] text-foreground leading-none">
        {value}
      </p>
      {subtitle && (
        <p className="text-[12px] text-foreground-secondary mt-1.5">{subtitle}</p>
      )}
    </div>
  );
}
