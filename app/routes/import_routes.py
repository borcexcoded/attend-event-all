"""Bulk import routes – CSV and file-based member registration."""

import csv
import io
import os
import uuid
import asyncio

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np

from app.database import get_db
from app.models.user import User
from app.models.organization import Admin
from app.auth import get_current_admin
from app.face_engine import get_engine, encode_embedding

router = APIRouter(tags=["Import"])


def _encode_face(image_data: bytes) -> np.ndarray | None:
    """Get first face encoding from image bytes using InsightFace."""
    try:
        import cv2
        nparr = np.frombuffer(image_data, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        engine = get_engine()
        results = engine.detect_and_encode_multi_pass(rgb)
        return results[0]["embedding"] if results else None
    except Exception:
        return None


@router.post("/members/import-csv")
async def import_members_csv(
    file: UploadFile = File(...),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Import members from CSV.
    CSV must have a 'name' column. Optional columns: email, phone.
    Members imported via CSV won't have face data until a photo is uploaded.
    """
    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    imported = []
    skipped = []
    errors = []

    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or row.get("Name") or "").strip()
        if not name:
            errors.append(f"Row {i}: missing name")
            continue

        email = (row.get("email") or row.get("Email") or "").strip() or None
        phone = (row.get("phone") or row.get("Phone") or "").strip() or None

        # Check duplicate
        if db.query(User).filter(User.name == name, User.org_id == admin.org_id).first():
            skipped.append(name)
            continue

        # Create a 512-d zero encoding (placeholder – needs photo later)
        dummy_encoding = np.zeros(512, dtype=np.float32).tobytes()

        user = User(
            org_id=admin.org_id,
            name=name,
            face_embedding=dummy_encoding,
            email=email,
            phone=phone,
            branch_id=admin.branch_id if admin.role != "owner" else None,
            is_global=False if (admin.role != "owner" and admin.branch_id) else True,
        )
        db.add(user)
        imported.append(name)

    db.commit()

    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "errors": len(errors),
        "imported_names": imported,
        "skipped_names": skipped,
        "error_details": errors,
    }


@router.get("/members/export-csv")
def export_members_csv(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Export members as CSV."""
    from fastapi.responses import StreamingResponse
    from datetime import datetime

    users_query = db.query(User).filter(User.org_id == admin.org_id)
    if admin.role != "owner" and admin.branch_id:
        users_query = users_query.filter(User.branch_id == admin.branch_id)
    users = users_query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Phone"])
    for u in users:
        writer.writerow([u.id, u.name, u.email or "", u.phone or ""])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=members_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@router.post("/members/{member_id}/photo")
async def update_member_photo(
    member_id: int,
    file: UploadFile = File(...),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Upload/update a member's face photo and re-encode their face."""
    user = db.query(User).filter(User.id == member_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(404, "Member not found")
    if admin.role != "owner" and admin.branch_id and user.branch_id != admin.branch_id:
        raise HTTPException(403, "You can only update members in your assigned branch")

    image_data = await file.read()
    encoding = await asyncio.to_thread(_encode_face, image_data)
    if encoding is None:
        raise HTTPException(400, "No face detected in the photo")

    photo_dir = f"app/static/photos/{admin.org_id}"
    os.makedirs(photo_dir, exist_ok=True)
    photo_filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = f"{photo_dir}/{photo_filename}"
    with open(photo_path, "wb") as f:
        f.write(image_data)

    user.face_embedding = encode_embedding(encoding)
    user.profile_photo = f"/static/photos/{admin.org_id}/{photo_filename}"
    db.commit()

    return {"message": f"Photo updated for {user.name}", "profile_photo": user.profile_photo}
