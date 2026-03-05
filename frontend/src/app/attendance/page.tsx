"use client";

import { useEffect, useState } from "react";
import {
  getAttendance,
  deleteAttendanceRecord,
  type AttendanceRecord,
} from "@/lib/api";

export default function AttendancePage() {
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [dateFilter, setDateFilter] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [nameFilter, setNameFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  async function loadRecords() {
    setLoading(true);
    try {
      const data = await getAttendance({
        date: dateFilter || undefined,
        name: nameFilter || undefined,
        limit: pageSize,
        offset: page * pageSize,
      });
      setRecords(data.records);
      setTotal(data.total);
      setError("");
    } catch {
      setError("Failed to load attendance records");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRecords();
  }, [dateFilter, nameFilter, page]);

  async function handleDelete(id: number) {
    if (!confirm("Delete this attendance record?")) return;
    try {
      await deleteAttendanceRecord(id);
      await loadRecords();
    } catch {
      setError("Failed to delete record");
    }
  }

  function formatTime(isoString: string) {
    const date = new Date(isoString);
    return date.toLocaleString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">
          Records
        </h1>
        <p className="text-[15px] text-foreground-secondary mt-1">
          View and manage attendance history.
        </p>
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

      {/* Filters */}
      <div className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)]">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
              Date
            </label>
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => {
                setDateFilter(e.target.value);
                setPage(0);
              }}
              className="px-3.5 py-2 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all duration-200"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
              Name
            </label>
            <input
              type="text"
              value={nameFilter}
              onChange={(e) => {
                setNameFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Search by name..."
              className="px-3.5 py-2 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all duration-200"
            />
          </div>
          <button
            onClick={() => {
              setDateFilter("");
              setNameFilter("");
              setPage(0);
            }}
            className="px-4 py-2 text-[14px] font-medium border border-divider rounded-xl hover:bg-background-secondary transition-colors duration-200"
          >
            Clear Filters
          </button>
          <div className="ml-auto text-[13px] text-foreground-secondary tabular-nums">
            {total} record{total !== 1 ? "s" : ""} found
          </div>
        </div>
      </div>

      {/* Records Table */}
      <div className="bg-card border border-divider rounded-2xl overflow-hidden shadow-[var(--shadow-sm)]">
        {loading ? (
          <div className="p-16 text-center text-foreground-secondary text-[14px]">
            Loading records...
          </div>
        ) : records.length === 0 ? (
          <div className="p-16 text-center">
            <div className="w-16 h-16 rounded-full bg-background-secondary flex items-center justify-center mx-auto mb-5">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-foreground-secondary">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <p className="text-[17px] font-semibold text-foreground">No records found</p>
            <p className="text-[14px] text-foreground-secondary mt-1.5">
              {dateFilter
                ? "No attendance recorded for this date."
                : "No attendance records yet."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-divider">
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">
                    ID
                  </th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">
                    Member
                  </th>
                  <th className="text-left py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">
                    Time
                  </th>
                  <th className="text-right py-3.5 px-5 text-[11px] font-semibold text-foreground-secondary uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr
                    key={record.id}
                    className="border-b border-divider last:border-b-0 hover:bg-card-hover transition-colors duration-150"
                  >
                    <td className="py-3.5 px-5 text-[13px] text-foreground-secondary tabular-nums">
                      {record.id}
                    </td>
                    <td className="py-3.5 px-5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-primary/10 text-primary rounded-full flex items-center justify-center text-[12px] font-semibold flex-shrink-0">
                          {record.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="text-[14px] font-medium text-foreground">{record.name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-5 text-[13px] text-foreground-secondary">
                      {record.time ? formatTime(record.time) : "--"}
                    </td>
                    <td className="py-3.5 px-5 text-right">
                      <button
                        onClick={() => handleDelete(record.id)}
                        className="text-foreground-secondary hover:text-danger hover:bg-danger-light p-1.5 rounded-lg transition-all duration-200"
                        title="Delete record"
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > pageSize && (
          <div className="flex items-center justify-between p-5 border-t border-divider">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-4 py-2 text-[14px] font-medium border border-divider rounded-xl hover:bg-background-secondary transition-colors duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-[13px] text-foreground-secondary tabular-nums">
              Page {page + 1} of {Math.ceil(total / pageSize)}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * pageSize >= total}
              className="px-4 py-2 text-[14px] font-medium border border-divider rounded-xl hover:bg-background-secondary transition-colors duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
