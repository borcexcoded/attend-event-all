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
    visitor_count: Optional[int] = 0


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
    attendance_trend: Optional[dict] = None  # {trend_direction, trend_percentage, average_attendance}
    overall_lateness_rate: Optional[float] = None


# --- Endpoints ---

@router.get("/overview", response_model=OverallAnalytics)
async def get_analytics_overview(
    days: int = Query(30, ge=7, le=365),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get overall organization analytics."""
    org_id = admin.org_id
    branch_filter = admin.branch_id if admin.role != "owner" and admin.branch_id else None
    cutoff = datetime.utcnow() - timedelta(days=days)
    half_cutoff = datetime.utcnow() - timedelta(days=days // 2)

    # Total members
    members_q = db.query(User).filter(User.org_id == org_id)
    if branch_filter:
        members_q = members_q.filter(User.branch_id == branch_filter)
    total_members = members_q.count()

    # Total visitors
    visitors_q = db.query(Visitor).filter(Visitor.org_id == org_id)
    if branch_filter:
        visitors_q = visitors_q.filter(Visitor.branch_id == branch_filter)
    total_visitors = visitors_q.count()

    # Total attendance records in period
    att_q = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    )
    if branch_filter:
        att_q = att_q.filter(Attendance.branch_id == branch_filter)
    total_records = att_q.count()

    # Attendance in first half vs second half for growth
    fh_q = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
        Attendance.time < half_cutoff
    )
    if branch_filter:
        fh_q = fh_q.filter(Attendance.branch_id == branch_filter)
    first_half = fh_q.count()

    sh_q = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= half_cutoff
    )
    if branch_filter:
        sh_q = sh_q.filter(Attendance.branch_id == branch_filter)
    second_half = sh_q.count()

    growth_rate = 0.0
    if first_half > 0:
        growth_rate = round(((second_half - first_half) / first_half) * 100, 1)

    # Average weekly attendance
    weeks = max(days // 7, 1)
    avg_weekly = round(total_records / weeks, 1)

    # Late percentage
    late_q = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
        Attendance.is_late == True
    )
    if branch_filter:
        late_q = late_q.filter(Attendance.branch_id == branch_filter)
    late_count = late_q.count()
    late_pct = round((late_count / total_records * 100) if total_records > 0 else 0, 1)

    # Visitor to member conversion (visitors who became members)
    conv_q = db.query(Visitor).filter(
        Visitor.org_id == org_id,
        Visitor.linked_member_id.isnot(None)
    )
    if branch_filter:
        conv_q = conv_q.filter(Visitor.branch_id == branch_filter)
    converted = conv_q.count()
    conversion_rate = round((converted / total_visitors * 100) if total_visitors > 0 else 0, 1)

    # Most active branch
    branch_q = db.query(
        Branch.name,
        func.count(Attendance.id).label('count')
    ).join(Attendance, Attendance.branch_id == Branch.id).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    )
    if branch_filter:
        branch_q = branch_q.filter(Attendance.branch_id == branch_filter)
    branch_stats = branch_q.group_by(Branch.id).order_by(func.count(Attendance.id).desc()).first()

    most_active_branch = branch_stats[0] if branch_stats else None

    # Most popular meeting
    meet_q = db.query(
        Meeting.name,
        func.count(Attendance.id).label('count')
    ).join(Attendance, Attendance.meeting_id == Meeting.id).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff
    )
    if branch_filter:
        meet_q = meet_q.filter(Attendance.branch_id == branch_filter)
    meeting_stats = meet_q.group_by(Meeting.id).order_by(func.count(Attendance.id).desc()).first()

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
        attendance_trend={
            "trend_direction": "up" if growth_rate > 2 else ("down" if growth_rate < -2 else "stable"),
            "trend_percentage": growth_rate,
            "average_attendance": avg_weekly,
        },
        overall_lateness_rate=round(late_count / total_records, 3) if total_records > 0 else 0,
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
    if admin.role != "owner" and admin.branch_id:
        branch_id = admin.branch_id
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
    if admin.role != "owner" and admin.branch_id:
        branch_id = admin.branch_id
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

    branches_q = db.query(Branch).filter(Branch.org_id == org_id, Branch.is_active == True)
    if admin.role != "owner" and admin.branch_id:
        branches_q = branches_q.filter(Branch.id == admin.branch_id)
    branches = branches_q.all()

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

        # Visitors at branch
        visitor_count = db.query(Visitor).filter(
            Visitor.branch_id == branch.id
        ).count()

        results.append(BranchAnalytics(
            branch_id=branch.id,
            branch_name=branch.name,
            total_members=total_members,
            total_attendance=attendance,
            avg_attendance=round(attendance / max(days // 7, 1), 1),
            growth_rate=growth,
            top_meeting=top_meeting[0] if top_meeting else None,
            visitor_count=visitor_count,
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
    if admin.role != "owner" and admin.branch_id:
        branch_id = admin.branch_id
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


@router.get("/daily-trends")
async def get_daily_trends(
    days: int = Query(30, ge=7, le=365),
    meeting_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get daily attendance trend data for charts."""
    org_id = admin.org_id
    if admin.role != "owner" and admin.branch_id:
        branch_id = admin.branch_id
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(Attendance).filter(
        Attendance.org_id == org_id,
        Attendance.time >= cutoff,
    )
    if meeting_id:
        query = query.filter(Attendance.meeting_id == meeting_id)
    if branch_id:
        query = query.filter(Attendance.branch_id == branch_id)

    records = query.all()

    # Group by date
    daily = {}
    for r in records:
        if not r.time:
            continue
        date_key = r.time.strftime("%Y-%m-%d")
        if date_key not in daily:
            daily[date_key] = {"members": set(), "visitors": set(), "total": 0, "late": 0}
        daily[date_key]["total"] += 1
        if r.member_type == "visitor":
            daily[date_key]["visitors"].add(r.visitor_id or r.name)
        else:
            daily[date_key]["members"].add(r.user_id or r.name)
        if r.is_late:
            daily[date_key]["late"] += 1

    # Build sorted results
    dates = sorted(daily.keys())
    return {
        "period_days": days,
        "data": [
            {
                "date": d,
                "day_name": datetime.strptime(d, "%Y-%m-%d").strftime("%A"),
                "total": daily[d]["total"],
                "members": len(daily[d]["members"]),
                "visitors": len(daily[d]["visitors"]),
                "late": daily[d]["late"],
            }
            for d in dates
        ],
    }


@router.get("/member-retention")
async def get_member_retention(
    weeks: int = Query(8, ge=4, le=52),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Calculate member retention rates over time."""
    org_id = admin.org_id
    branch_filter = admin.branch_id if admin.role != "owner" and admin.branch_id else None
    now = datetime.utcnow()

    retention = []
    for w in range(weeks - 1, -1, -1):
        week_end = now - timedelta(weeks=w)
        week_start = week_end - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        # Members who attended this week
        this_week_q = db.query(Attendance.user_id).filter(
                Attendance.org_id == org_id,
                Attendance.time >= week_start,
                Attendance.time < week_end,
                Attendance.user_id.isnot(None),
            )
        if branch_filter:
            this_week_q = this_week_q.filter(Attendance.branch_id == branch_filter)
        this_week = set(r.user_id for r in this_week_q.all())

        # Members who attended previous week
        prev_week_q = db.query(Attendance.user_id).filter(
                Attendance.org_id == org_id,
                Attendance.time >= prev_week_start,
                Attendance.time < week_start,
                Attendance.user_id.isnot(None),
            )
        if branch_filter:
            prev_week_q = prev_week_q.filter(Attendance.branch_id == branch_filter)
        prev_week = set(r.user_id for r in prev_week_q.all())

        retained = len(this_week & prev_week)
        rate = round((retained / len(prev_week)) * 100, 1) if prev_week else 0

        retention.append({
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": week_end.strftime("%Y-%m-%d"),
            "active_members": len(this_week),
            "retained_from_prev": retained,
            "retention_rate": rate,
            "new_this_week": len(this_week - prev_week),
            "churned": len(prev_week - this_week),
        })

    return {"weeks": weeks, "data": retention}


@router.get("/meeting-comparison")
async def get_meeting_comparison(
    days: int = Query(30, ge=7, le=365),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Compare attendance across all meetings."""
    org_id = admin.org_id
    branch_filter = admin.branch_id if admin.role != "owner" and admin.branch_id else None
    cutoff = datetime.utcnow() - timedelta(days=days)

    meetings_q = db.query(Meeting).filter(
        Meeting.org_id == org_id, Meeting.is_active == True
    )
    if branch_filter:
        meetings_q = meetings_q.filter((Meeting.branch_id == branch_filter) | (Meeting.branch_id == None))
    meetings = meetings_q.all()

    comparisons = []
    for m in meetings:
        records = db.query(Attendance).filter(
            Attendance.meeting_id == m.id,
            Attendance.time >= cutoff,
        )
        if branch_filter:
            records = records.filter(Attendance.branch_id == branch_filter)
        records = records.all()

        if not records:
            comparisons.append({
                "id": m.id, "name": m.name, "color": m.color,
                "total": 0, "unique_members": 0, "unique_visitors": 0,
                "sessions": 0, "avg_per_session": 0,
            })
            continue

        dates = set()
        members = set()
        visitors = set()
        for r in records:
            if r.time:
                dates.add(r.time.strftime("%Y-%m-%d"))
            if r.member_type == "visitor":
                visitors.add(r.visitor_id or r.name)
            else:
                members.add(r.user_id or r.name)

        sessions = len(dates)
        comparisons.append({
            "id": m.id, "name": m.name, "color": m.color,
            "total": len(records),
            "unique_members": len(members),
            "unique_visitors": len(visitors),
            "sessions": sessions,
            "avg_per_session": round(len(records) / sessions, 1) if sessions else 0,
        })

    return {"period_days": days, "meetings": sorted(comparisons, key=lambda x: x["total"], reverse=True)}


@router.get("/growth-metrics")
async def get_growth_metrics(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get monthly growth metrics for the organization."""
    org_id = admin.org_id
    branch_filter = admin.branch_id if admin.role != "owner" and admin.branch_id else None
    now = datetime.utcnow()

    months = []
    for i in range(11, -1, -1):
        month_start = (now - timedelta(days=i * 30)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        new_members_q = db.query(User).filter(
            User.org_id == org_id,
            User.created_at >= month_start,
            User.created_at < month_end,
        )
        if branch_filter:
            new_members_q = new_members_q.filter(User.branch_id == branch_filter)
        new_members = new_members_q.count()

        attendance_q = db.query(Attendance).filter(
            Attendance.org_id == org_id,
            Attendance.time >= month_start,
            Attendance.time < month_end,
        )
        if branch_filter:
            attendance_q = attendance_q.filter(Attendance.branch_id == branch_filter)
        attendance = attendance_q.count()

        visitors_q = db.query(Visitor).filter(
            Visitor.org_id == org_id,
            Visitor.first_seen >= month_start,
            Visitor.first_seen < month_end,
        )
        if branch_filter:
            visitors_q = visitors_q.filter(Visitor.branch_id == branch_filter)
        visitors = visitors_q.count()

        months.append({
            "month": month_start.strftime("%Y-%m"),
            "month_name": month_start.strftime("%B %Y"),
            "new_members": new_members,
            "total_attendance": attendance,
            "new_visitors": visitors,
        })

    return {"months": months}


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get org-wide dashboard summary with per-branch breakdown (owner view)."""
    org_id = admin.org_id
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    cutoff_30 = datetime.utcnow() - timedelta(days=30)

    branches = db.query(Branch).filter(
        Branch.org_id == org_id, Branch.is_active == True
    ).order_by(Branch.is_headquarters.desc(), Branch.name).all()

    branch_data = []
    total_members_org = 0
    total_today_org = 0

    for b in branches:
        members = db.query(func.count(User.id)).filter(User.branch_id == b.id).scalar() or 0
        today_att = (
            db.query(func.count(func.distinct(Attendance.name)))
            .filter(Attendance.branch_id == b.id, Attendance.time >= today, Attendance.time < tomorrow)
            .scalar() or 0
        )
        att_30d = (
            db.query(func.count(Attendance.id))
            .filter(Attendance.branch_id == b.id, Attendance.time >= cutoff_30)
            .scalar() or 0
        )
        meetings = db.query(func.count(Meeting.id)).filter(Meeting.branch_id == b.id, Meeting.is_active == True).scalar() or 0

        total_members_org += members
        total_today_org += today_att

        branch_data.append({
            "id": b.id,
            "name": b.name,
            "code": b.code,
            "is_headquarters": b.is_headquarters,
            "members": members,
            "today_attendance": today_att,
            "attendance_30d": att_30d,
            "meetings": meetings,
        })

    return {
        "total_members": total_members_org,
        "total_today": total_today_org,
        "total_branches": len(branches),
        "branches": branch_data,
    }
