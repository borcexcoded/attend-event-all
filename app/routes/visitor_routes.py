"""Visitor / unknown face management routes."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import numpy as np

from app.database import get_db
from app.models.visitor import Visitor
from app.models.user import User
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(tags=["Visitors"])


@router.get("/visitors")
def get_visitors(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Get all visitors / unknown faces for this org."""
    visitors = (
        db.query(Visitor)
        .filter(Visitor.org_id == admin.org_id)
        .order_by(Visitor.last_seen.desc())
        .all()
    )
    return {
        "total": len(visitors),
        "visitors": [
            {
                "id": v.id,
                "face_photo": v.face_photo,
                "label": v.label,
                "is_new_member": v.is_new_member,
                "linked_member_id": v.linked_member_id,
                "verified": v.verified,
                "visit_count": v.visit_count,
                "first_seen": v.first_seen.isoformat() if v.first_seen else None,
                "last_seen": v.last_seen.isoformat() if v.last_seen else None,
            }
            for v in visitors
        ],
    }


class VerifyRequest(BaseModel):
    action: str  # "new_member", "link_existing", "dismiss"
    label: Optional[str] = None
    member_id: Optional[int] = None


@router.post("/visitors/{visitor_id}/verify")
def verify_visitor(
    visitor_id: int,
    req: VerifyRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Verify a visitor:
    - action='new_member': label them as new and mark verified
    - action='link_existing': link to an existing member by member_id
    - action='dismiss': remove visitor record
    """
    v = db.query(Visitor).filter(Visitor.id == visitor_id, Visitor.org_id == admin.org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visitor not found")

    if req.action == "new_member":
        v.label = req.label or f"Visitor #{v.id}"
        v.is_new_member = True
        v.verified = True

        # Check for duplicate face against existing members before creating
        if v.face_embedding:
            import face_recognition
            new_enc = np.frombuffer(v.face_embedding, dtype=np.float64)
            all_users = db.query(User).filter(User.org_id == admin.org_id).all()
            for u in all_users:
                existing_enc = np.frombuffer(u.face_embedding, dtype=np.float64)
                if np.any(existing_enc != 0):
                    dist = float(face_recognition.face_distance([existing_enc], new_enc)[0])
                    if dist <= 0.45:
                        raise HTTPException(
                            status_code=409,
                            detail=f"This face closely matches existing member '{u.name}' (similarity: {round((1-dist)*100)}%). "
                                   f"Cannot register as a different person. Use 'Link to Member' instead, "
                                   f"or contact admin to override if they are truly different people."
                        )

        # Actually create a User (member) record from the visitor's face data
        new_user = User(
            org_id=admin.org_id,
            name=v.label,
            face_embedding=v.face_embedding if v.face_embedding else b'\x00' * 128 * 8,
            profile_photo=v.face_photo,
            email=None,
            phone=None,
        )
        db.add(new_user)
        db.flush()  # get the new user id
        v.linked_member_id = new_user.id
        db.commit()
        return {"message": f"Visitor registered as new member: {v.label}", "visitor_id": v.id, "member_id": new_user.id}

    elif req.action == "link_existing":
        if not req.member_id:
            raise HTTPException(400, detail="member_id required for link_existing action")
        user = db.query(User).filter(User.id == req.member_id, User.org_id == admin.org_id).first()
        if not user:
            raise HTTPException(404, detail="Member not found")
        v.linked_member_id = user.id
        v.label = user.name
        v.is_new_member = False
        v.verified = True
        db.commit()
        return {"message": f"Visitor linked to member: {user.name}", "visitor_id": v.id}

    elif req.action == "dismiss":
        db.delete(v)
        db.commit()
        return {"message": "Visitor dismissed"}

    raise HTTPException(400, detail="Invalid action. Use: new_member, link_existing, dismiss")


@router.delete("/visitors/{visitor_id}")
def delete_visitor(visitor_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    v = db.query(Visitor).filter(Visitor.id == visitor_id, Visitor.org_id == admin.org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visitor not found")
    db.delete(v)
    db.commit()
    return {"message": "Visitor removed"}


@router.get("/visitors/stats")
def visitor_stats(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Get visitor statistics."""
    total = db.query(Visitor).filter(Visitor.org_id == admin.org_id).count()
    verified = db.query(Visitor).filter(Visitor.org_id == admin.org_id, Visitor.verified == True).count()
    unverified = total - verified
    new_members = db.query(Visitor).filter(
        Visitor.org_id == admin.org_id, Visitor.is_new_member == True, Visitor.verified == True
    ).count()
    returning = db.query(Visitor).filter(
        Visitor.org_id == admin.org_id, Visitor.visit_count > 1
    ).count()
    return {
        "total": total,
        "verified": verified,
        "unverified": unverified,
        "new_members": new_members,
        "returning_visitors": returning,
    }
