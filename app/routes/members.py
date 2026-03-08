from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.organization import Admin
from app.models.branch import Branch
from app.models.registration_field import RegistrationField, MemberCustomData
from app.auth import get_current_admin

router = APIRouter(tags=["Members"])


def _is_owner(admin: Admin) -> bool:
    return admin.role == "owner"


def _enforce_branch_scope(admin: Admin, requested_branch_id: Optional[int]) -> Optional[int]:
    """Resolve effective branch with strict branch scoping for non-owner credentials."""
    if _is_owner(admin):
        return requested_branch_id
    if admin.branch_id:
        if requested_branch_id and requested_branch_id != admin.branch_id:
            raise HTTPException(status_code=403, detail="You can only access your assigned branch")
        return admin.branch_id
    return requested_branch_id


def _ensure_member_visible(admin: Admin, user: User) -> None:
    if _is_owner(admin):
        return
    if admin.branch_id and user.branch_id != admin.branch_id:
        raise HTTPException(status_code=404, detail="Member not found")


class MemberUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[int] = None
    custom_fields: Optional[dict] = None


@router.get("/members")
def get_members(
    branch_id: Optional[int] = Query(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all registered members for this org, optionally filtered by branch."""
    query = db.query(User).filter(User.org_id == admin.org_id)
    # Branch isolation: non-owners only see their own assigned branch members.
    effective_branch = _enforce_branch_scope(admin, branch_id)
    if effective_branch:
        query = query.filter(User.branch_id == effective_branch)
    users = query.order_by(User.name).all()

    # Build branch name lookup
    branch_ids = set(u.branch_id for u in users if u.branch_id)
    branch_map = {}
    if branch_ids:
        branches = db.query(Branch).filter(Branch.id.in_(branch_ids)).all()
        branch_map = {b.id: b.name for b in branches}

    return {
        "total": len(users),
        "members": [
            {
                "id": u.id,
                "name": u.name,
                "profile_photo": u.profile_photo,
                "email": u.email,
                "phone": u.phone,
                "branch_id": getattr(u, 'branch_id', None),
                "branch_name": branch_map.get(getattr(u, 'branch_id', None), ""),
            }
            for u in users
        ],
    }


@router.get("/members/{member_id}")
def get_member(member_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == member_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")
    _ensure_member_visible(admin, user)

    branch_name = None
    if user.branch_id:
        branch = db.query(Branch).filter(Branch.id == user.branch_id, Branch.org_id == admin.org_id).first()
        branch_name = branch.name if branch else None

    custom_rows = (
        db.query(MemberCustomData, RegistrationField)
        .join(RegistrationField, RegistrationField.id == MemberCustomData.field_id)
        .filter(
            MemberCustomData.org_id == admin.org_id,
            MemberCustomData.user_id == user.id,
            RegistrationField.is_active == True,
        )
        .all()
    )
    custom_fields = {str(d.field_id): d.value for d, _ in custom_rows}

    return {
        "id": user.id,
        "name": user.name,
        "profile_photo": user.profile_photo,
        "email": user.email,
        "phone": user.phone,
        "branch_id": user.branch_id,
        "branch_name": branch_name,
        "custom_fields": custom_fields,
    }


@router.put("/members/{member_id}")
def update_member(
    member_id: int,
    req: MemberUpdateRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == member_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")
    _ensure_member_visible(admin, user)

    # Branch update permissions
    if req.branch_id is not None:
        target_branch_id = _enforce_branch_scope(admin, req.branch_id)
        if target_branch_id is not None:
            branch = db.query(Branch).filter(
                Branch.id == target_branch_id,
                Branch.org_id == admin.org_id,
                Branch.is_active == True,
            ).first()
            if not branch:
                raise HTTPException(status_code=400, detail="Branch not found in your organization")
        user.branch_id = target_branch_id

    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        dup = db.query(User).filter(
            User.org_id == admin.org_id,
            User.id != user.id,
            User.name == name,
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Member '{name}' already exists")
        user.name = name

    if req.email is not None:
        user.email = req.email.strip() or None
    if req.phone is not None:
        user.phone = req.phone.strip() or None

    if req.custom_fields is not None:
        active_fields = db.query(RegistrationField).filter(
            RegistrationField.org_id == admin.org_id,
            RegistrationField.is_active == True,
        ).all()
        active_field_ids = {f.id for f in active_fields}

        for raw_field_id, raw_value in req.custom_fields.items():
            try:
                field_id = int(raw_field_id)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Invalid custom field id: {raw_field_id}")

            if field_id not in active_field_ids:
                raise HTTPException(status_code=400, detail=f"Custom field {field_id} is not available")

            value = (str(raw_value).strip() if raw_value is not None else "")
            existing = db.query(MemberCustomData).filter(
                MemberCustomData.org_id == admin.org_id,
                MemberCustomData.user_id == user.id,
                MemberCustomData.field_id == field_id,
            ).first()

            if value:
                if existing:
                    existing.value = value
                else:
                    db.add(MemberCustomData(
                        org_id=admin.org_id,
                        user_id=user.id,
                        field_id=field_id,
                        value=value,
                    ))
            elif existing:
                db.delete(existing)

    db.commit()
    db.refresh(user)

    return {
        "message": f"Member '{user.name}' updated successfully.",
        "member": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "branch_id": user.branch_id,
            "profile_photo": user.profile_photo,
        },
    }


@router.delete("/members/{member_id}")
def delete_member(member_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == member_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")
    _ensure_member_visible(admin, user)
    db.delete(user)
    db.commit()
    return {"message": f"Member '{user.name}' removed successfully."}
