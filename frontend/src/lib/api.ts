const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

export interface Member {
  id: number;
  name: string;
}

export type MembersResponse = { total: number; members: Member[] };

export interface AttendanceRecord {
  id: number;
  name: string;
  time: string | null;
}

export interface AttendanceStats {
  period_days: number;
  total_records: number;
  unique_members: number;
  today_count: number;
  daily_breakdown: { date: string; count: number }[];
  top_attendees: { name: string; count: number }[];
}

export interface RecognitionResult {
  recognized: string[];
  attendance_marked: string[];
  total_faces: number;
}

// --- Members ---
export async function getMembers(): Promise<{ total: number; members: Member[] }> {
  const res = await fetch(`${API_BASE}/members`);
  if (!res.ok) throw new Error("Failed to fetch members");
  return res.json();
}

export async function registerMember(name: string, photo: File): Promise<{ message: string; id: number }> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("file", photo);

  const res = await fetch(`${API_BASE}/register`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Registration failed");
  }
  return res.json();
}

export async function deleteMember(id: number): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/members/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete member");
  return res.json();
}

// --- Attendance ---
export async function getAttendance(params?: {
  date?: string;
  name?: string;
  limit?: number;
  offset?: number;
}): Promise<{ total: number; records: AttendanceRecord[] }> {
  const searchParams = new URLSearchParams();
  if (params?.date) searchParams.set("date", params.date);
  if (params?.name) searchParams.set("name", params.name);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const res = await fetch(`${API_BASE}/attendance?${searchParams.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch attendance");
  return res.json();
}

export async function getTodayAttendance(): Promise<{
  date: string;
  total_records: number;
  unique_members: number;
  members: string[];
  records: AttendanceRecord[];
}> {
  const res = await fetch(`${API_BASE}/attendance/today`);
  if (!res.ok) throw new Error("Failed to fetch today's attendance");
  return res.json();
}

export async function getAttendanceStats(days?: number): Promise<AttendanceStats> {
  const params = days ? `?days=${days}` : "";
  const res = await fetch(`${API_BASE}/attendance/stats${params}`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function deleteAttendanceRecord(id: number): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/attendance/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete record");
  return res.json();
}

// --- Recognition ---
export async function recognizeFaces(photo: File): Promise<RecognitionResult> {
  const formData = new FormData();
  formData.append("file", photo);

  const res = await fetch(`${API_BASE}/recognize`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Recognition failed");
  }
  return res.json();
}

// --- Health ---
export async function healthCheck(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("API not available");
  return res.json();
}

// --- Analytics ---
export interface WeeklyTrend {
  day: string;
  date: string;
  attendance_count: number;
  unique_members: number;
  visitor_count: number;
}

export interface AttendanceTrend {
  period: string;
  total_attendance: number;
  average_attendance: number;
  trend_percentage: number;
  trend_direction: "up" | "down" | "stable";
}

export interface TopAttendee {
  member_id: number;
  name: string;
  attendance_count: number;
  attendance_rate: number;
  profile_photo: string | null;
  late_count: number;
}

export interface MeetingAnalytics {
  meeting_id: number;
  meeting_name: string;
  total_sessions: number;
  total_attendance: number;
  average_attendance: number;
  unique_attendees: number;
  lateness_rate: number;
  trend: AttendanceTrend;
}

export interface BranchAnalytics {
  branch_id: number;
  branch_name: string;
  total_members: number;
  total_attendance: number;
  average_attendance: number;
  visitor_count: number;
  member_retention_rate: number;
}

export interface OverallAnalytics {
  total_members: number;
  total_attendance: number;
  average_daily_attendance: number;
  total_visitors: number;
  conversion_rate: number;
  overall_lateness_rate: number;
  weekly_trends: WeeklyTrend[];
  attendance_trend: AttendanceTrend;
}

export interface LatenessReport {
  member_id: number;
  name: string;
  total_attendance: number;
  late_count: number;
  lateness_rate: number;
  average_late_minutes: number;
}

export async function getAnalyticsOverview(branchId?: number): Promise<OverallAnalytics> {
  const params = branchId ? `?branch_id=${branchId}` : "";
  const res = await fetch(`${API_BASE}/analytics/overview${params}`);
  if (!res.ok) throw new Error("Failed to fetch analytics overview");
  return res.json();
}

export async function getWeeklyTrends(
  branchId?: number,
  weeks?: number
): Promise<WeeklyTrend[]> {
  const searchParams = new URLSearchParams();
  if (branchId) searchParams.set("branch_id", String(branchId));
  if (weeks) searchParams.set("weeks", String(weeks));
  const params = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const res = await fetch(`${API_BASE}/analytics/weekly-trends${params}`);
  if (!res.ok) throw new Error("Failed to fetch weekly trends");
  return res.json();
}

export async function getTopAttendees(
  limit?: number,
  branchId?: number
): Promise<TopAttendee[]> {
  const searchParams = new URLSearchParams();
  if (limit) searchParams.set("limit", String(limit));
  if (branchId) searchParams.set("branch_id", String(branchId));
  const params = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const res = await fetch(`${API_BASE}/analytics/top-attendees${params}`);
  if (!res.ok) throw new Error("Failed to fetch top attendees");
  return res.json();
}

export async function getMeetingAnalytics(meetingId: number): Promise<MeetingAnalytics> {
  const res = await fetch(`${API_BASE}/analytics/meeting/${meetingId}`);
  if (!res.ok) throw new Error("Failed to fetch meeting analytics");
  return res.json();
}

export async function getBranchAnalytics(): Promise<BranchAnalytics[]> {
  const res = await fetch(`${API_BASE}/analytics/branches`);
  if (!res.ok) throw new Error("Failed to fetch branch analytics");
  return res.json();
}

export async function getLatenessReport(
  days?: number,
  branchId?: number
): Promise<LatenessReport[]> {
  const searchParams = new URLSearchParams();
  if (days) searchParams.set("days", String(days));
  if (branchId) searchParams.set("branch_id", String(branchId));
  const params = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const res = await fetch(`${API_BASE}/analytics/lateness-report${params}`);
  if (!res.ok) throw new Error("Failed to fetch lateness report");
  return res.json();
}

// --- Branches ---
export interface Branch {
  id: number;
  name: string;
  code: string;
  address: string | null;
  city: string | null;
  country: string | null;
  timezone: string;
  is_headquarters: boolean;
  is_active: boolean;
  member_count: number;
  meeting_count: number;
}

export interface BranchCreate {
  name: string;
  code: string;
  address?: string;
  city?: string;
  country?: string;
  timezone?: string;
  is_headquarters?: boolean;
  org_id?: number;
}

export async function getBranches(activeOnly?: boolean): Promise<Branch[]> {
  const params = activeOnly === false ? "?active_only=false" : "";
  const res = await fetch(`${API_BASE}/branches${params}`);
  if (!res.ok) throw new Error("Failed to fetch branches");
  return res.json();
}

export async function createBranch(branch: BranchCreate): Promise<Branch> {
  const res = await fetch(`${API_BASE}/branches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(branch),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to create branch");
  }
  return res.json();
}

export async function getBranch(branchId: number): Promise<Branch> {
  const res = await fetch(`${API_BASE}/branches/${branchId}`);
  if (!res.ok) throw new Error("Failed to fetch branch");
  return res.json();
}

export async function updateBranch(
  branchId: number,
  data: Partial<Branch>
): Promise<Branch> {
  const res = await fetch(`${API_BASE}/branches/${branchId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update branch");
  return res.json();
}

export async function deleteBranch(branchId: number): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/branches/${branchId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete branch");
  return res.json();
}

export async function getBranchMembers(
  branchId: number,
  includeGlobal?: boolean
): Promise<Member[]> {
  const params = includeGlobal === false ? "?include_global=false" : "";
  const res = await fetch(`${API_BASE}/branches/${branchId}/members${params}`);
  if (!res.ok) throw new Error("Failed to fetch branch members");
  return res.json();
}
