from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(tags=["Members"])


@router.get("/members")
def get_members(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Get all registered members for this org."""
    users = db.query(User).filter(User.org_id == admin.org_id).all()
    return {
        "total": len(users),
        "members": [
            {
                "id": u.id,
                "name": u.name,
                "profile_photo": u.profile_photo,
                "email": u.email,
                "phone": u.phone,
            }
            for u in users
        ],
    }


@router.get("/members/{member_id}")
def get_member(member_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == member_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"id": user.id, "name": user.name, "profile_photo": user.profile_photo, "email": user.email, "phone": user.phone}


@router.delete("/members/{member_id}")
def delete_member(member_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == member_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(user)
    db.commit()
    return {"message": f"Member '{user.name}' removed successfully."}
