"""Meeting CRUD + scheduling routes."""

import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.meeting import Meeting
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(tags=["Meetings"])

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Schemas ──────────────────────────────────────────

class MeetingCreate(BaseModel):
    name: str
    description: Optional[str] = None
    recurrence: str = "weekly"          # daily, weekly, biweekly, monthly, once
    day_of_week: Optional[int] = None   # 0-6
    day_of_month: Optional[int] = None  # 1-31
    start_time: Optional[str] = None    # "HH:MM"
    end_time: Optional[str] = None
    color: Optional[str] = "#3b82f6"
    track_visitors: bool = True


class MeetingUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    recurrence: Optional[str] = None
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    track_visitors: Optional[bool] = None


# ── Helpers ──────────────────────────────────────────

def _meeting_dict(m: Meeting, attendance_count: int = 0, visitor_count: int = 0):
    return {
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "recurrence": m.recurrence,
        "day_of_week": m.day_of_week,
        "day_of_week_name": DAY_NAMES[m.day_of_week] if m.day_of_week is not None else None,
        "day_of_month": m.day_of_month,
        "start_time": m.start_time,
        "end_time": m.end_time,
        "color": m.color,
        "is_active": m.is_active,
        "track_visitors": m.track_visitors,
        "attendance_count": attendance_count,
        "visitor_count": visitor_count,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _next_occurrence(m: Meeting) -> Optional[str]:
    """Return the next scheduled date string for the meeting."""
    now = datetime.utcnow()
    today_weekday = now.weekday()

    if m.recurrence == "daily":
        return now.strftime("%Y-%m-%d")
    elif m.recurrence in ("weekly", "biweekly"):
        if m.day_of_week is not None:
            days_ahead = (m.day_of_week - today_weekday) % 7
            if days_ahead == 0:
                # today is the day — check if meeting time hasn't passed
                return now.strftime("%Y-%m-%d")
            nxt = now + timedelta(days=days_ahead)
            if m.recurrence == "biweekly":
                # simple approximation: next occurrence in 7 or 14 days
                pass
            return nxt.strftime("%Y-%m-%d")
    elif m.recurrence == "monthly":
        if m.day_of_month:
            try:
                target = now.replace(day=m.day_of_month)
                if target < now:
                    month = now.month + 1 if now.month < 12 else 1
                    year = now.year if now.month < 12 else now.year + 1
                    target = now.replace(year=year, month=month, day=m.day_of_month)
                return target.strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _ensure_meeting_access(admin: Admin, meeting: Meeting) -> None:
    """Branch-scoped credentials can only access meetings in their assigned branch."""
    if admin.role == "owner":
        return
    if admin.branch_id and meeting.branch_id != admin.branch_id:
        raise HTTPException(404, "Meeting not found")


def _apply_attendance_branch_scope(admin: Admin, query):
    if admin.role != "owner" and admin.branch_id:
        query = query.filter(
            (Attendance.branch_id == admin.branch_id)
            | (Attendance.marked_at_branch_id == admin.branch_id)
        )
    return query


# ── CRUD ─────────────────────────────────────────────

@router.post("/meetings")
def create_meeting(
    req: MeetingCreate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    m = Meeting(
        org_id=admin.org_id,
        branch_id=admin.branch_id,
        name=req.name,
        description=req.description,
        recurrence=req.recurrence,
        day_of_week=req.day_of_week,
        day_of_month=req.day_of_month,
        start_time=req.start_time,
        end_time=req.end_time,
        color=req.color or "#3b82f6",
        track_visitors=req.track_visitors,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"message": f"Meeting '{m.name}' created", "meeting": _meeting_dict(m)}


@router.get("/meetings")
def list_meetings(
    active_only: bool = Query(True),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Meeting).filter(Meeting.org_id == admin.org_id)
    if active_only:
        q = q.filter(Meeting.is_active == True)
    # Branch isolation: non-owners see only their assigned branch meetings.
    if admin.role != "owner" and admin.branch_id:
        q = q.filter(Meeting.branch_id == admin.branch_id)
    meetings = q.order_by(Meeting.created_at.desc()).all()

    result = []
    for m in meetings:
        att_count = (
            db.query(func.count(Attendance.id))
            .filter(Attendance.meeting_id == m.id)
            .scalar() or 0
        )
        vis_count = 0  # visitors linked via attendance
        d = _meeting_dict(m, att_count, vis_count)
        d["next_occurrence"] = _next_occurrence(m)
        result.append(d)

    return {"total": len(result), "meetings": result}


@router.get("/meetings/{meeting_id}")
def get_meeting(
    meeting_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    att_count_q = db.query(func.count(Attendance.id)).filter(Attendance.meeting_id == m.id)
    att_count_q = _apply_attendance_branch_scope(admin, att_count_q)
    att_count = att_count_q.scalar() or 0

    unique_q = db.query(func.count(func.distinct(Attendance.name))).filter(Attendance.meeting_id == m.id)
    unique_q = _apply_attendance_branch_scope(admin, unique_q)
    unique_members = unique_q.scalar() or 0

    d = _meeting_dict(m, att_count)
    d["unique_members"] = unique_members
    d["next_occurrence"] = _next_occurrence(m)
    return d


@router.put("/meetings/{meeting_id}")
def update_meeting(
    meeting_id: int,
    req: MeetingUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    for field, val in req.dict(exclude_unset=True).items():
        setattr(m, field, val)
    db.commit()
    db.refresh(m)
    return {"message": f"Meeting '{m.name}' updated", "meeting": _meeting_dict(m)}


@router.delete("/meetings/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)
    db.delete(m)
    db.commit()
    return {"message": f"Meeting '{m.name}' deleted"}


# ── Meeting-specific attendance ──────────────────────

@router.get("/meetings/{meeting_id}/attendance")
def get_meeting_attendance(
    meeting_id: int,
    date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get attendance records for a specific meeting, optionally filtered by date."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    q = db.query(Attendance).filter(
        Attendance.org_id == admin.org_id,
        Attendance.meeting_id == meeting_id,
    )
    q = _apply_attendance_branch_scope(admin, q)

    if date:
        try:
            target = datetime.strptime(date, "%Y-%m-%d")
            q = q.filter(Attendance.time >= target, Attendance.time < target + timedelta(days=1))
        except ValueError:
            pass

    total = q.count()
    records = q.order_by(Attendance.time.desc()).offset(offset).limit(limit).all()

    # Group by date for history view
    return {
        "meeting": {"id": m.id, "name": m.name, "color": m.color},
        "total": total,
        "records": [
            {
                "id": r.id,
                "name": r.name,
                "profile_photo": r.profile_photo,
                "member_type": r.member_type or "member",
                "time": r.time.isoformat() if r.time else None,
            }
            for r in records
        ],
    }


@router.get("/meetings/{meeting_id}/history")
def get_meeting_history(
    meeting_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get session-by-session history grouped by date."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    records = (
        db.query(Attendance)
        .filter(Attendance.org_id == admin.org_id, Attendance.meeting_id == meeting_id)
    )
    records = _apply_attendance_branch_scope(admin, records).order_by(Attendance.time.desc()).all()

    # Group by date with deduplication
    sessions = {}
    seen_per_session = {}
    for r in records:
        date_key = r.time.strftime("%Y-%m-%d") if r.time else "unknown"
        if date_key not in sessions:
            sessions[date_key] = {"date": date_key, "members": 0, "new_members": 0, "attendees": []}
            seen_per_session[date_key] = set()

        dedup_key = (r.name or "").strip().lower()
        if dedup_key in seen_per_session[date_key]:
            continue
        seen_per_session[date_key].add(dedup_key)

        sessions[date_key]["attendees"].append({
            "name": r.name,
            "member_type": r.member_type or "member",
            "profile_photo": r.profile_photo,
            "time": r.time.isoformat() if r.time else None,
        })
        if r.member_type == "new_member":
            sessions[date_key]["new_members"] += 1
        else:
            sessions[date_key]["members"] += 1

    return {
        "meeting": {"id": m.id, "name": m.name, "color": m.color, "recurrence": m.recurrence},
        "total_sessions": len(sessions),
        "sessions": list(sessions.values()),
    }


@router.get("/meetings/{meeting_id}/stats")
def meeting_stats(
    meeting_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Stats for a specific meeting."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    total_q = db.query(func.count(Attendance.id)).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.org_id == admin.org_id,
    )
    total_q = _apply_attendance_branch_scope(admin, total_q)
    total_records = total_q.scalar() or 0

    unique_q = db.query(func.count(func.distinct(Attendance.name))).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.org_id == admin.org_id,
    )
    unique_q = _apply_attendance_branch_scope(admin, unique_q)
    unique_members = unique_q.scalar() or 0
    # Session count (unique dates)
    dates_q = db.query(func.date(Attendance.time)).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.org_id == admin.org_id,
    )
    dates_q = _apply_attendance_branch_scope(admin, dates_q)
    dates = dates_q.distinct().all()
    total_sessions = len(dates)

    # Average per session
    avg_per_session = round(total_records / total_sessions, 1) if total_sessions > 0 else 0

    # New members via this meeting
    new_member_q = db.query(func.count(Attendance.id)).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.org_id == admin.org_id,
        Attendance.member_type == "new_member",
    )
    new_member_q = _apply_attendance_branch_scope(admin, new_member_q)
    new_member_count = new_member_q.scalar() or 0

    return {
        "meeting": {"id": m.id, "name": m.name},
        "total_records": total_records,
        "unique_members": unique_members,
        "total_sessions": total_sessions,
        "avg_per_session": avg_per_session,
        "new_members": new_member_count,
    }


@router.get("/meetings/{meeting_id}/full-history")
def get_meeting_full_history(
    meeting_id: int,
    period: str = Query("all", pattern="^(week|month|year|all)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get comprehensive meeting history grouped by session date.
    Each session is a single day's attendance for that meeting, sorted newest first.
    Includes per-member attendance counts, trends, and chart data.
    Supports custom date range with start_date and end_date (YYYY-MM-DD)."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    q = db.query(Attendance).filter(
        Attendance.org_id == admin.org_id,
        Attendance.meeting_id == meeting_id,
    )
    q = _apply_attendance_branch_scope(admin, q)

    # Custom date range takes priority over period filter
    now = datetime.utcnow()
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            q = q.filter(Attendance.time >= start_dt)
        except ValueError:
            pass
    elif period == "week":
        q = q.filter(Attendance.time >= now - timedelta(days=7))
    elif period == "month":
        q = q.filter(Attendance.time >= now - timedelta(days=30))
    elif period == "year":
        q = q.filter(Attendance.time >= now - timedelta(days=365))

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(Attendance.time < end_dt)
        except ValueError:
            pass

    records = q.order_by(Attendance.time.desc()).all()

    # Group by date — deduplicate attendees within each session (one entry per person per day)
    sessions = {}
    member_attendance_map = {}  # name -> list of dates
    seen_per_session = {}  # date_key -> set of names (for dedup)

    for r in records:
        date_key = r.time.strftime("%Y-%m-%d") if r.time else "unknown"
        if date_key not in sessions:
            sessions[date_key] = {
                "date": date_key,
                "day_name": r.time.strftime("%A") if r.time else "",
                "members": 0,
                "visitors": 0,
                "attendees": [],
            }
            seen_per_session[date_key] = set()

        # Deduplicate: skip if this name was already recorded for this session
        dedup_key = (r.name or "").strip().lower()
        if dedup_key in seen_per_session[date_key]:
            continue
        seen_per_session[date_key].add(dedup_key)

        member_type = r.member_type or "member"
        sessions[date_key]["attendees"].append({
            "id": r.id,
            "name": r.name,
            "member_type": member_type,
            "profile_photo": r.profile_photo,
            "time": r.time.strftime("%H:%M") if r.time else "",
        })
        if member_type == "visitor":
            sessions[date_key]["visitors"] += 1
        else:
            sessions[date_key]["members"] += 1

        # Track per-member attendance
        if r.name not in member_attendance_map:
            member_attendance_map[r.name] = []
        if date_key not in member_attendance_map[r.name]:
            member_attendance_map[r.name].append(date_key)

    # Sort attendees within each session: members first (alphabetical), then visitors
    for date_key in sessions:
        sessions[date_key]["attendees"].sort(key=lambda a: (
            0 if a["member_type"] != "visitor" else 1,
            (a["name"] or "").lower()
        ))

    # Sort sessions by date descending
    sorted_sessions = sorted(sessions.values(), key=lambda s: s["date"], reverse=True)

    # Chart data: attendance count per session date (ascending for charting)
    chart_dates = sorted(sessions.keys())
    chart_data = [
        {"date": d, "count": sessions[d]["members"] + sessions[d]["visitors"],
         "members": sessions[d]["members"], "visitors": sessions[d]["visitors"]}
        for d in chart_dates
    ]

    # Top attendees for this meeting
    top = (
        db.query(Attendance.name, func.count(func.distinct(func.date(Attendance.time))).label("sessions"))
    )
    top = _apply_attendance_branch_scope(admin, top)
    top = top.group_by(Attendance.name).order_by(
        func.count(func.distinct(func.date(Attendance.time))).desc()
    ).limit(20).all()

    # Attendance rate: percentage of sessions each member attended
    total_session_count = len(sessions)
    member_stats = []
    for name, session_count in top:
        rate = round(session_count / total_session_count * 100, 1) if total_session_count > 0 else 0
        member_stats.append({
            "name": name,
            "sessions_attended": session_count,
            "total_sessions": total_session_count,
            "attendance_rate": rate,
        })

    return {
        "meeting": {
            "id": m.id, "name": m.name, "color": m.color,
            "recurrence": m.recurrence,
            "day_of_week_name": DAY_NAMES[m.day_of_week] if m.day_of_week is not None else None,
            "start_time": m.start_time, "end_time": m.end_time,
        },
        "period": period,
        "total_sessions": total_session_count,
        "sessions": sorted_sessions,
        "chart_data": chart_data,
        "member_stats": member_stats,
    }


@router.get("/meetings/{meeting_id}/export")
def export_meeting_csv(
    meeting_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Export a meeting's full attendance history as a downloadable CSV."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == admin.org_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    _ensure_meeting_access(admin, m)

    records_q = db.query(Attendance).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.org_id == admin.org_id,
    )
    records_q = _apply_attendance_branch_scope(admin, records_q)
    records = records_q.order_by(Attendance.time.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Day", "Name", "Time", "Type"])
    for r in records:
        writer.writerow([
            r.time.strftime("%Y-%m-%d") if r.time else "",
            r.time.strftime("%A") if r.time else "",
            r.name,
            r.time.strftime("%H:%M:%S") if r.time else "",
            r.member_type or "member",
        ])

    output.seek(0)
    safe_name = m.name.replace(" ", "_").replace("/", "-")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={safe_name}_attendance_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )
