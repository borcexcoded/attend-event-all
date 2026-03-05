"""Auth routes – signup and login."""

import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organization import Organization, Admin
from app.auth import hash_password, verify_password, create_token, get_current_admin

router = APIRouter(tags=["Auth"])


class SignupRequest(BaseModel):
    org_name: str
    org_type: str = "church"
    full_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug


@router.post("/auth/signup", status_code=201)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(Admin).filter(Admin.email == req.email).first():
        raise HTTPException(409, "Email already registered")

    # Create org
    slug = _slugify(req.org_name)
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(name=req.org_name, slug=slug, org_type=req.org_type)
    db.add(org)
    db.flush()

    admin = Admin(
        org_id=org.id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = create_token(admin.id, org.id)
    return {
        "token": token,
        "admin": {"id": admin.id, "email": admin.email, "full_name": admin.full_name, "role": admin.role},
        "org": {"id": org.id, "name": org.name, "slug": org.slug, "type": org.org_type},
    }


@router.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == req.email).first()
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(401, "Invalid email or password")

    org = db.query(Organization).filter(Organization.id == admin.org_id).first()
    token = create_token(admin.id, admin.org_id)
    return {
        "token": token,
        "admin": {"id": admin.id, "email": admin.email, "full_name": admin.full_name, "role": admin.role},
        "org": {"id": org.id, "name": org.name, "slug": org.slug, "type": org.org_type} if org else None,
    }


@router.get("/auth/me")
def me(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == admin.org_id).first()
    return {
        "admin": {"id": admin.id, "email": admin.email, "full_name": admin.full_name, "role": admin.role},
        "org": {"id": org.id, "name": org.name, "slug": org.slug, "type": org.org_type} if org else None,
    }


@router.get("/auth/team")
def get_team(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Get all admins in this org."""
    admins = db.query(Admin).filter(Admin.org_id == admin.org_id).all()
    return {
        "team": [
            {"id": a.id, "email": a.email, "full_name": a.full_name, "role": a.role}
            for a in admins
        ]
    }


class InviteRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "admin"


@router.post("/auth/invite", status_code=201)
def invite_member(req: InviteRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Owner/admin can invite another admin."""
    if admin.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owners and admins can invite")
    if db.query(Admin).filter(Admin.email == req.email).first():
        raise HTTPException(409, "Email already registered")

    new_admin = Admin(
        org_id=admin.org_id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=req.role if req.role in ("admin", "viewer") else "viewer",
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return {"message": f"{req.full_name} invited as {new_admin.role}", "id": new_admin.id}


@router.delete("/auth/team/{admin_id}")
def remove_team_member(admin_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    if admin.role != "owner":
        raise HTTPException(403, "Only owners can remove team members")
    target = db.query(Admin).filter(Admin.id == admin_id, Admin.org_id == admin.org_id).first()
    if not target:
        raise HTTPException(404, "Team member not found")
    if target.id == admin.id:
        raise HTTPException(400, "Cannot remove yourself")
    db.delete(target)
    db.commit()
    return {"message": "Team member removed"}
