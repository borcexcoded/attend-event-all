"""Analytics routes – comprehensive attendance trends, growth metrics, and reporting."""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, extract
from pydantic import BaseModel

from app.database import get_db
from app.models.attendance import Attendance
from app.models.user import User
from app.models.visitor import Visitor
from app.models.meeting import Meeting
from app.models.branch import Branch
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# --- Response Models ---

class WeeklyTrend(BaseModel):
    week_start: str
    week_end: str
    total_attendance: int
    unique_members: int
    unique_visitors: int
    avg_daily: float
    change_pct: Optional[float]  # vs previous week


class AttendanceTrend(BaseModel):
    period: str
    count: int
    members: int
    visitors: int
    late_count: int


class TopAttendee(BaseModel):
    id: int
    name: str
    attendance_count: int
    late_count: int
    attendance_rate: float  # % of total meetings attended
    profile_photo: Optional[str]


class MeetingAnalytics(BaseModel):
    meeting_id: int
    meeting_name: str
    total_sessions: int
    avg_attendance: float
    peak_attendance: int
    lowest_attendance: int
    trend: str  # "growing", "stable", "declining"
    growth_rate: float


class BranchAnalytics(BaseModel):
    branch_id: int
    branch_name: str
    total_members: int
    total_attendance: int
    avg_attendance: float
    growth_rate: float
    top_meeting: Optional[str]


class OverallAnalytics(BaseModel):
    total_members: int
    total_visitors: int
    total_attendance_records: int
    avg_weekly_attendance: float
    attendance_growth: float  # % change over period
    visitor_to_member_conversion: float
    late_percentage: float
    most_active_branch: Optional[str]
    most_popular_meeting: Optional[str]


# --- Endpoints ---

@router.get("/overview", response_model=OverallAnalytics)
async def get_analytics_overview(
    days: int = Query(30, ge=7, le=365),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get overall organization analytics."""
    org_id = admin.org_id
    cutoff = datetime.utcnow() - timedelta(days=days)
    half_cutoff = datetime.utcnow() - timedelta(days=days // 2)

    # Total members
    total_members = db.query(User).filter(User.org_id == org_id).count()

    # Total visitors
    total_visitors = db.query(Visitor).filter(Visitor.org_id == org_id).count()

    # Total attendance records in period
    total_records = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    ).count()

    # Attendance in first half vs second half for growth
    first_half = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
        Attendance.time < half_cutoff
    ).count()

    second_half = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= half_cutoff
    ).count()

    growth_rate = 0.0
    if first_half > 0:
        growth_rate = round(((second_half - first_half) / first_half) * 100, 1)

    # Average weekly attendance
    weeks = max(days // 7, 1)
    avg_weekly = round(total_records / weeks, 1)

    # Late percentage
    late_count = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
        Attendance.is_late == True
    ).count()
    late_pct = round((late_count / total_records * 100) if total_records > 0 else 0, 1)

    # Visitor to member conversion (visitors who became members)
    converted = db.query(Visitor).filter(
        Visitor.org_id == org_id,
        Visitor.linked_member_id.isnot(None)
    ).count()
    conversion_rate = round((converted / total_visitors * 100) if total_visitors > 0 else 0, 1)

    # Most active branch
    branch_stats = db.query(
        Branch.name,
        func.count(Attendance.id).label('count')
    ).join(Attendance, Attendance.branch_id == Branch.id).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    ).group_by(Branch.id).order_by(func.count(Attendance.id).desc()).first()

    most_active_branch = branch_stats[0] if branch_stats else None

    # Most popular meeting
    meeting_stats = db.query(
        Meeting.name,
        func.count(Attendance.id).label('count')
    ).join(Attendance, Attendance.meeting_id == Meeting.id).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    ).group_by(Meeting.id).order_by(func.count(Attendance.id).desc()).first()

    most_popular_meeting = meeting_stats[0] if meeting_stats else None

    return OverallAnalytics(
        total_members=total_members,
        total_visitors=total_visitors,
        total_attendance_records=total_records,
        avg_weekly_attendance=avg_weekly,
        attendance_growth=growth_rate,
        visitor_to_member_conversion=conversion_rate,
        late_percentage=late_pct,
        most_active_branch=most_active_branch,
        most_popular_meeting=most_popular_meeting,
    )


@router.get("/weekly-trends", response_model=List[WeeklyTrend])
async def get_weekly_trends(
    weeks: int = Query(8, ge=1, le=52),
    branch_id: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get week-by-week attendance trends."""
    org_id = admin.org_id
    trends = []

    for w in range(weeks - 1, -1, -1):
        week_end = datetime.utcnow() - timedelta(weeks=w)
        week_start = week_end - timedelta(days=7)

        query = db.query(Attendance).filter(
            Attendance.org_id == org_id,
            Attendance.time >= week_start,
            Attendance.time < week_end
        )

        if branch_id:
            query = query.filter(Attendance.branch_id == branch_id)

        records = query.all()

        total = len(records)
        members = len([r for r in records if r.member_type == "member"])
        visitors = len([r for r in records if r.member_type in ("visitor", "new_member")])
        unique_members = len(set(r.user_id for r in records if r.user_id))
        unique_visitors = len(set(r.visitor_id for r in records if r.visitor_id))

        # Calculate change from previous week
        change_pct = None
        if trends:
            prev_total = trends[-1].total_attendance
            if prev_total > 0:
                change_pct = round(((total - prev_total) / prev_total) * 100, 1)

        trends.append(WeeklyTrend(
            week_start=week_start.strftime("%Y-%m-%d"),
            week_end=week_end.strftime("%Y-%m-%d"),
            total_attendance=total,
            unique_members=unique_members,
            unique_visitors=unique_visitors,
            avg_daily=round(total / 7, 1),
            change_pct=change_pct,
        ))

    return trends


@router.get("/top-attendees", response_model=List[TopAttendee])
async def get_top_attendees(
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(10, ge=1, le=50),
    branch_id: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get top members by attendance."""
    org_id = admin.org_id
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Count total meetings in period for attendance rate calculation
    total_meetings_query = db.query(func.count(func.distinct(Attendance.meeting_id))).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
        Attendance.meeting_id.isnot(None)
    )
    if branch_id:
        total_meetings_query = total_meetings_query.filter(Attendance.branch_id == branch_id)
    total_meetings = total_meetings_query.scalar() or 1

    # Get attendance counts per user
    query = db.query(
        User.id,
        User.name,
        User.profile_photo,
        func.count(Attendance.id).label('attendance_count'),
        func.sum(case((Attendance.is_late == True, 1), else_=0)).label('late_count')
    ).join(Attendance, Attendance.user_id == User.id).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    )

    if branch_id:
        query = query.filter(Attendance.branch_id == branch_id)

    results = query.group_by(User.id).order_by(func.count(Attendance.id).desc()).limit(limit).all()

    return [
        TopAttendee(
            id=r.id,
            name=r.name,
            attendance_count=r.attendance_count,
            late_count=r.late_count or 0,
            attendance_rate=round((r.attendance_count / total_meetings) * 100, 1),
            profile_photo=r.profile_photo,
        )
        for r in results
    ]


@router.get("/meeting/{meeting_id}", response_model=MeetingAnalytics)
async def get_meeting_analytics(
    meeting_id: int,
    days: int = Query(30, ge=7, le=365),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get detailed analytics for a specific meeting type."""
    org_id = admin.org_id
    cutoff = datetime.utcnow() - timedelta(days=days)
    half_cutoff = datetime.utcnow() - timedelta(days=days // 2)

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.org_id == org_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    # Get attendance grouped by date
    daily_stats = db.query(
        func.date(Attendance.time).label('date'),
        func.count(Attendance.id).label('count')
    ).filter(
        Attendance.org_id == org_id,
        Attendance.meeting_id == meeting_id,
        Attendance.time >= cutoff
    ).group_by(func.date(Attendance.time)).all()

    if not daily_stats:
        return MeetingAnalytics(
            meeting_id=meeting_id,
            meeting_name=meeting.name,
            total_sessions=0,
            avg_attendance=0,
            peak_attendance=0,
            lowest_attendance=0,
            trend="stable",
            growth_rate=0,
        )

    counts = [s.count for s in daily_stats]
    total_sessions = len(counts)
    avg_attendance = round(sum(counts) / len(counts), 1)
    peak = max(counts)
    lowest = min(counts)

    # Calculate growth
    first_half = db.query(func.count(Attendance.id)).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.time >= cutoff,
        Attendance.time < half_cutoff
    ).scalar() or 0

    second_half = db.query(func.count(Attendance.id)).filter(
        Attendance.meeting_id == meeting_id,
        Attendance.time >= half_cutoff
    ).scalar() or 0

    growth_rate = 0.0
    if first_half > 0:
        growth_rate = round(((second_half - first_half) / first_half) * 100, 1)

    trend = "stable"
    if growth_rate > 10:
        trend = "growing"
    elif growth_rate < -10:
        trend = "declining"

    return MeetingAnalytics(
        meeting_id=meeting_id,
        meeting_name=meeting.name,
        total_sessions=total_sessions,
        avg_attendance=avg_attendance,
        peak_attendance=peak,
        lowest_attendance=lowest,
        trend=trend,
        growth_rate=growth_rate,
    )


@router.get("/branches", response_model=List[BranchAnalytics])
async def get_branch_analytics(
    days: int = Query(30, ge=7, le=365),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get analytics for all branches (HQ admin view)."""
    org_id = admin.org_id
    cutoff = datetime.utcnow() - timedelta(days=days)
    half_cutoff = datetime.utcnow() - timedelta(days=days // 2)

    branches = db.query(Branch).filter(Branch.org_id == org_id, Branch.is_active == True).all()

    results = []
    for branch in branches:
        # Total members at branch
        total_members = db.query(User).filter(User.branch_id == branch.id).count()

        # Attendance in period
        attendance = db.query(Attendance).filter(
            Attendance.branch_id == branch.id,
            Attendance.time >= cutoff
        ).count()

        # Growth calculation
        first_half = db.query(Attendance).filter(
            Attendance.branch_id == branch.id,
            Attendance.time >= cutoff,
            Attendance.time < half_cutoff
        ).count()

        second_half = db.query(Attendance).filter(
            Attendance.branch_id == branch.id,
            Attendance.time >= half_cutoff
        ).count()

        growth = 0.0
        if first_half > 0:
            growth = round(((second_half - first_half) / first_half) * 100, 1)

        # Top meeting at branch
        top_meeting = db.query(Meeting.name).join(
            Attendance, Attendance.meeting_id == Meeting.id
        ).filter(
            Attendance.branch_id == branch.id,
            Attendance.time >= cutoff
        ).group_by(Meeting.id).order_by(func.count(Attendance.id).desc()).first()

        results.append(BranchAnalytics(
            branch_id=branch.id,
            branch_name=branch.name,
            total_members=total_members,
            total_attendance=attendance,
            avg_attendance=round(attendance / max(days // 7, 1), 1),
            growth_rate=growth,
            top_meeting=top_meeting[0] if top_meeting else None,
        ))

    return sorted(results, key=lambda x: x.total_attendance, reverse=True)


@router.get("/lateness-report")
async def get_lateness_report(
    days: int = Query(30, ge=7, le=365),
    branch_id: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get detailed lateness analytics."""
    org_id = admin.org_id
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(
        Attendance.user_id,
        User.name,
        func.count(Attendance.id).label('total'),
        func.sum(case((Attendance.is_late == True, 1), else_=0)).label('late_count'),
        func.avg(case((Attendance.is_late == True, Attendance.late_minutes), else_=None)).label('avg_late_minutes')
    ).join(User, User.id == Attendance.user_id).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
        Attendance.user_id.isnot(None)
    )

    if branch_id:
        query = query.filter(Attendance.branch_id == branch_id)

    results = query.group_by(Attendance.user_id, User.name).having(
        func.sum(case((Attendance.is_late == True, 1), else_=0)) > 0
    ).order_by(func.sum(case((Attendance.is_late == True, 1), else_=0)).desc()).limit(20).all()

    return {
        "period_days": days,
        "chronic_latecomers": [
            {
                "user_id": r.user_id,
                "name": r.name,
                "total_attendance": r.total,
                "late_count": r.late_count,
                "late_percentage": round((r.late_count / r.total) * 100, 1) if r.total > 0 else 0,
                "avg_late_minutes": round(r.avg_late_minutes, 0) if r.avg_late_minutes else 0,
            }
            for r in results
        ]
    }
