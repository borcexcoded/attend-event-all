import csv
import io
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from sqlalchemy import or_
from app.database import get_db
from app.models.attendance import Attendance
from app.models.user import User
from app.models.meeting import Meeting
from app.models.organization import Admin
from app.models.branch import Branch
from app.models.visitor import Visitor
from app.auth import get_current_admin

router = APIRouter(tags=["Attendance"])


def _effective_branch(admin: Admin, requested_branch_id: Optional[int]) -> Optional[int]:
    """Resolve branch for request, forcing branch-scoped accounts to their own branch."""
    if admin.role == "owner":
        return requested_branch_id
    if admin.branch_id:
        if requested_branch_id and requested_branch_id != admin.branch_id:
            raise HTTPException(status_code=403, detail="You can only access your assigned branch")
        return admin.branch_id
    return requested_branch_id


@router.get("/attendance")
def get_attendance(
    date: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    meeting_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Attendance).filter(Attendance.org_id == admin.org_id)

    # Branch isolation: branch-scoped credentials only see their assigned branch.
    effective_branch = _effective_branch(admin, branch_id)
    if effective_branch:
        query = query.filter(
            or_(
                Attendance.branch_id == effective_branch,
                Attendance.marked_at_branch_id == effective_branch,
            )
        )

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            next_day = target_date + timedelta(days=1)
            query = query.filter(Attendance.time >= target_date, Attendance.time < next_day)
        except ValueError:
            pass

    if name:
        query = query.filter(Attendance.name.ilike(f"%{name}%"))

    if meeting_id:
        query = query.filter(Attendance.meeting_id == meeting_id)

    total = query.count()
    records = query.order_by(Attendance.time.desc()).offset(offset).limit(limit).all()

    # Build branch name lookup
    branch_ids = set()
    for r in records:
        if r.branch_id: branch_ids.add(r.branch_id)
        if r.marked_at_branch_id: branch_ids.add(r.marked_at_branch_id)
    branch_map = {}
    if branch_ids:
        branches = db.query(Branch).filter(Branch.id.in_(branch_ids)).all()
        branch_map = {b.id: b.name for b in branches}

    return {
        "total": total,
        "records": [
            {
                "id": r.id,
                "name": r.name,
                "profile_photo": r.profile_photo,
                "member_type": r.member_type or "member",
                "meeting_id": r.meeting_id,
                "meeting_name": r.meeting_name,
                "time": r.time.isoformat() if r.time else None,
                "branch_id": r.branch_id,
                "branch_name": branch_map.get(r.branch_id, ""),
                "marked_at_branch_id": r.marked_at_branch_id,
                "marked_at_branch_name": branch_map.get(r.marked_at_branch_id, ""),
            }
            for r in records
        ],
    }


@router.get("/attendance/today")
def get_today_attendance(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    query = (
        db.query(Attendance)
        .filter(Attendance.org_id == admin.org_id, Attendance.time >= today, Attendance.time < tomorrow)
    )
    # Branch isolation
    if admin.role != "owner" and admin.branch_id:
        query = query.filter(
            or_(
                Attendance.branch_id == admin.branch_id,
                Attendance.marked_at_branch_id == admin.branch_id,
            )
        )
    records = query.order_by(Attendance.time.desc()).all()

    unique_names = list(set(r.name for r in records))

    return {
        "date": today.strftime("%Y-%m-%d"),
        "total_records": len(records),
        "unique_members": len(unique_names),
        "members": unique_names,
        "records": [
            {
                "id": r.id,
                "name": r.name,
                "profile_photo": r.profile_photo,
                "member_type": r.member_type or "member",
                "meeting_id": r.meeting_id,
                "meeting_name": r.meeting_name,
                "time": r.time.isoformat() if r.time else None,
            }
            for r in records
        ],
    }


@router.get("/attendance/stats")
def get_attendance_stats(
    days: int = Query(30, ge=1, le=365),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)

    base_filter = [Attendance.org_id == admin.org_id, Attendance.time >= cutoff]
    if admin.role != "owner" and admin.branch_id:
        base_filter.append(
            or_(
                Attendance.branch_id == admin.branch_id,
                Attendance.marked_at_branch_id == admin.branch_id,
            )
        )

    total_records = (
        db.query(func.count(Attendance.id))
        .filter(*base_filter)
        .scalar()
    )

    unique_members = (
        db.query(func.count(func.distinct(Attendance.name)))
        .filter(*base_filter)
        .scalar()
    )

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    today_filter = [Attendance.org_id == admin.org_id, Attendance.time >= today, Attendance.time < tomorrow]
    if admin.role != "owner" and admin.branch_id:
        today_filter.append(
            or_(
                Attendance.branch_id == admin.branch_id,
                Attendance.marked_at_branch_id == admin.branch_id,
            )
        )

    today_count = (
        db.query(func.count(func.distinct(Attendance.name)))
        .filter(*today_filter)
        .scalar()
    )

    daily_data = []
    for i in range(min(days, 7)):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_filter = [Attendance.org_id == admin.org_id, Attendance.time >= day_start, Attendance.time < day_end]
        if admin.role != "owner" and admin.branch_id:
            day_filter.append(
                or_(
                    Attendance.branch_id == admin.branch_id,
                    Attendance.marked_at_branch_id == admin.branch_id,
                )
            )
        count = (
            db.query(func.count(func.distinct(Attendance.name)))
            .filter(*day_filter)
            .scalar()
        )
        daily_data.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})

    top_attendees = (
        db.query(Attendance.name, func.count(Attendance.id).label("count"))
        .filter(*base_filter)
        .group_by(Attendance.name)
        .order_by(func.count(Attendance.id).desc())
        .limit(10)
        .all()
    )

    return {
        "period_days": days,
        "total_records": total_records,
        "unique_members": unique_members,
        "today_count": today_count,
        "daily_breakdown": daily_data,
        "top_attendees": [{"name": name, "count": count} for name, count in top_attendees],
    }


# ── Manual attendance schemas ──

class ManualAttendanceRequest(BaseModel):
    member_ids: List[int]
    meeting_id: Optional[int] = None
    branch_id: Optional[int] = None
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today


class ManualAttendanceByNameRequest(BaseModel):
    name: str
    meeting_id: Optional[int] = None
    branch_id: Optional[int] = None
    member_type: str = "member"  # member, visitor, new_member


@router.post("/attendance/manual")
def manual_add_attendance(
    req: ManualAttendanceRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin manually adds attendance for one or more members."""
    effective_branch = _effective_branch(admin, req.branch_id)

    meeting = None
    meeting_name = None
    if req.meeting_id:
        meeting = db.query(Meeting).filter(
            Meeting.id == req.meeting_id, Meeting.org_id == admin.org_id
        ).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        if admin.role != "owner" and admin.branch_id and meeting.branch_id not in (admin.branch_id, None):
            raise HTTPException(status_code=403, detail="You can only use meetings in your assigned branch")
        meeting_name = meeting.name

    # Parse date or use now
    now = datetime.utcnow()
    if req.date:
        try:
            now = datetime.strptime(req.date, "%Y-%m-%d").replace(hour=12, minute=0)
        except ValueError:
            pass

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    marked = []
    already = []
    not_found = []

    for member_id in req.member_ids:
        user = db.query(User).filter(
            User.id == member_id, User.org_id == admin.org_id
        ).first()
        if not user:
            not_found.append(member_id)
            continue

        if admin.role != "owner" and admin.branch_id and user.branch_id != admin.branch_id:
            not_found.append(member_id)
            continue

        # Check if already marked for this meeting today
        dup_q = db.query(Attendance).filter(
            Attendance.org_id == admin.org_id,
            Attendance.user_id == user.id,
            Attendance.time >= today_start,
            Attendance.time < today_start + timedelta(days=1),
        )
        if req.meeting_id:
            dup_q = dup_q.filter(Attendance.meeting_id == req.meeting_id)
        if dup_q.first():
            already.append(user.name)
            continue

        db.add(Attendance(
            org_id=admin.org_id,
            name=user.name,
            time=now,
            profile_photo=user.profile_photo or "",
            member_type="member",
            meeting_id=req.meeting_id,
            meeting_name=meeting_name,
            user_id=user.id,
            branch_id=effective_branch or getattr(user, 'branch_id', None),
            marked_at_branch_id=effective_branch,
        ))
        marked.append(user.name)

    db.commit()
    return {
        "marked": marked,
        "already_marked": already,
        "not_found": not_found,
        "total_marked": len(marked),
    }


@router.post("/attendance/manual-name")
def manual_add_by_name(
    req: ManualAttendanceByNameRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin manually adds attendance by name (for non-registered attendees)."""
    effective_branch = _effective_branch(admin, req.branch_id)

    member_type = (req.member_type or "member").strip().lower()
    if member_type not in {"member", "visitor", "new_member"}:
        raise HTTPException(status_code=400, detail="member_type must be one of: member, visitor, new_member")

    meeting_name = None
    if req.meeting_id:
        meeting = db.query(Meeting).filter(
            Meeting.id == req.meeting_id, Meeting.org_id == admin.org_id
        ).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        if admin.role != "owner" and admin.branch_id and meeting.branch_id not in (admin.branch_id, None):
            raise HTTPException(status_code=403, detail="You can only use meetings in your assigned branch")
        meeting_name = meeting.name

    now = datetime.utcnow()

    attendance_name = req.name.strip()
    profile_photo = None
    user_id = None
    visitor_id = None

    if member_type == "member":
        user_query = db.query(User).filter(
            User.org_id == admin.org_id,
            func.lower(User.name) == attendance_name.lower(),
        )
        if admin.role != "owner" and admin.branch_id:
            user_query = user_query.filter(User.branch_id == admin.branch_id)
        user = user_query.first()
        if user:
            attendance_name = user.name
            profile_photo = user.profile_photo
            user_id = user.id
    else:
        visitor_query = db.query(Visitor).filter(
            Visitor.org_id == admin.org_id,
            func.lower(Visitor.label) == attendance_name.lower(),
        )
        if admin.role != "owner" and admin.branch_id:
            visitor_query = visitor_query.filter(Visitor.branch_id == admin.branch_id)
        visitor = visitor_query.first()
        if not visitor:
            visitor = Visitor(
                org_id=admin.org_id,
                face_photo="",
                label=attendance_name,
                verified=False,
                is_new_member=(member_type == "new_member"),
                visit_count=1,
                branch_id=effective_branch,
                first_seen=now,
                last_seen=now,
                last_seen_branch_id=effective_branch,
            )
            db.add(visitor)
            db.flush()
        else:
            visitor.visit_count = (visitor.visit_count or 0) + 1
            visitor.last_seen = now
            visitor.last_seen_branch_id = effective_branch
            if member_type == "new_member":
                visitor.is_new_member = True
        visitor_id = visitor.id
        profile_photo = visitor.face_photo

    db.add(Attendance(
        org_id=admin.org_id,
        name=attendance_name,
        time=now,
        profile_photo=profile_photo,
        member_type=member_type,
        meeting_id=req.meeting_id,
        meeting_name=meeting_name,
        user_id=user_id,
        visitor_id=visitor_id,
        branch_id=effective_branch,
        marked_at_branch_id=effective_branch,
    ))
    db.commit()
    return {
        "message": f"Attendance added for '{attendance_name}'",
        "member_type": member_type,
        "user_id": user_id,
        "visitor_id": visitor_id,
    }


@router.delete("/attendance/bulk-delete")
def bulk_delete_attendance(
    record_ids: List[int] = Query(...),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete multiple attendance records at once."""
    deleted = 0
    for rid in record_ids:
        record = db.query(Attendance).filter(
            Attendance.id == rid, Attendance.org_id == admin.org_id
        ).first()
        if record:
            db.delete(record)
            deleted += 1
    db.commit()
    return {"message": f"{deleted} records deleted", "deleted": deleted}


@router.delete("/attendance/{record_id}")
def delete_attendance(record_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    record = db.query(Attendance).filter(Attendance.id == record_id, Attendance.org_id == admin.org_id).first()
    if not record:
        return {"error": "Record not found"}
    db.delete(record)
    db.commit()
    return {"message": "Record deleted"}


@router.get("/attendance/export")
def export_attendance_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Export attendance records as CSV."""
    query = db.query(Attendance).filter(Attendance.org_id == admin.org_id)
    if admin.role != "owner" and admin.branch_id:
        query = query.filter(
            or_(
                Attendance.branch_id == admin.branch_id,
                Attendance.marked_at_branch_id == admin.branch_id,
            )
        )

    if date_from:
        try:
            query = query.filter(Attendance.time >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Attendance.time < datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass

    records = query.order_by(Attendance.time.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Date", "Time", "Type", "Meeting"])
    for r in records:
        writer.writerow([
            r.id,
            r.name,
            r.time.strftime("%Y-%m-%d") if r.time else "",
            r.time.strftime("%H:%M:%S") if r.time else "",
            r.member_type or "member",
            r.meeting_name or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )
