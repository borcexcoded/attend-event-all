import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.attendance import Attendance
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(tags=["Attendance"])


@router.get("/attendance")
def get_attendance(
    date: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    meeting_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Attendance).filter(Attendance.org_id == admin.org_id)

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
            }
            for r in records
        ],
    }


@router.get("/attendance/today")
def get_today_attendance(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    records = (
        db.query(Attendance)
        .filter(Attendance.org_id == admin.org_id, Attendance.time >= today, Attendance.time < tomorrow)
        .order_by(Attendance.time.desc())
        .all()
    )

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

    total_records = (
        db.query(func.count(Attendance.id))
        .filter(Attendance.org_id == admin.org_id, Attendance.time >= cutoff)
        .scalar()
    )

    unique_members = (
        db.query(func.count(func.distinct(Attendance.name)))
        .filter(Attendance.org_id == admin.org_id, Attendance.time >= cutoff)
        .scalar()
    )

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    today_count = (
        db.query(func.count(func.distinct(Attendance.name)))
        .filter(Attendance.org_id == admin.org_id, Attendance.time >= today, Attendance.time < tomorrow)
        .scalar()
    )

    daily_data = []
    for i in range(min(days, 7)):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = (
            db.query(func.count(func.distinct(Attendance.name)))
            .filter(Attendance.org_id == admin.org_id, Attendance.time >= day_start, Attendance.time < day_end)
            .scalar()
        )
        daily_data.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})

    top_attendees = (
        db.query(Attendance.name, func.count(Attendance.id).label("count"))
        .filter(Attendance.org_id == admin.org_id, Attendance.time >= cutoff)
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
