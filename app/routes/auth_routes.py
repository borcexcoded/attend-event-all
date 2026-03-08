"""Auth routes – signup and login with branch support."""

import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organization import Organization, Admin
from app.models.branch import Branch
from app.auth import hash_password, verify_password, create_token, get_current_admin

router = APIRouter(tags=["Auth"])


class SignupRequest(BaseModel):
    org_name: str
    org_type: str = "church"
    full_name: str
    email: str
    password: str
    branch_name: Optional[str] = None  # optional first branch


class LoginRequest(BaseModel):
    email: str
    password: str
    branch_id: Optional[int] = None  # login to a specific branch


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

    # Create a default HQ branch for the organization
    branch_name = req.branch_name or f"{req.org_name} HQ"
    branch_code = _slugify(branch_name).upper().replace("-", "")[:10] or "HQ"
    branch = Branch(
        org_id=org.id,
        name=branch_name,
        code=branch_code,
        is_headquarters=True,
    )
    db.add(branch)
    db.flush()

    admin = Admin(
        org_id=org.id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
        branch_id=branch.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = create_token(admin.id, org.id, branch.id)
    return {
        "token": token,
        "admin": {"id": admin.id, "email": admin.email, "full_name": admin.full_name, "role": admin.role},
        "org": {"id": org.id, "name": org.name, "slug": org.slug, "type": org.org_type},
        "branch": {"id": branch.id, "name": branch.name, "code": branch.code},
    }


@router.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == req.email).first()
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(401, "Invalid email or password")

    org = db.query(Organization).filter(Organization.id == admin.org_id).first()

    # Determine active branch
    branch_id = req.branch_id or admin.branch_id

    # Branch-scoped credentials can only operate within their assigned branch.
    if admin.role != "owner" and admin.branch_id:
        if req.branch_id and req.branch_id != admin.branch_id:
            raise HTTPException(403, "You can only access your assigned branch")
        branch_id = admin.branch_id

    branch = None
    if branch_id:
        branch = db.query(Branch).filter(
            Branch.id == branch_id, Branch.org_id == admin.org_id
        ).first()
    # If no branch set, pick the first (HQ) branch in the org
    if not branch:
        branch = db.query(Branch).filter(
            Branch.org_id == admin.org_id
        ).order_by(Branch.is_headquarters.desc(), Branch.id).first()

    # Update admin's active branch
    if branch and admin.branch_id != branch.id:
        admin.branch_id = branch.id
        db.commit()

    token = create_token(admin.id, admin.org_id, branch.id if branch else None)

    # Also return list of all branches so user can switch
    branches_query = db.query(Branch).filter(
        Branch.org_id == admin.org_id, Branch.is_active == True
    )
    if admin.role != "owner" and admin.branch_id:
        branches_query = branches_query.filter(Branch.id == admin.branch_id)
    branches = branches_query.order_by(Branch.is_headquarters.desc(), Branch.name).all()

    return {
        "token": token,
        "admin": {
            "id": admin.id, "email": admin.email,
            "full_name": admin.full_name, "role": admin.role,
            "branch_id": branch.id if branch else None,
        },
        "org": {"id": org.id, "name": org.name, "slug": org.slug, "type": org.org_type} if org else None,
        "branch": {"id": branch.id, "name": branch.name, "code": branch.code} if branch else None,
        "branches": [
            {"id": b.id, "name": b.name, "code": b.code, "is_headquarters": b.is_headquarters}
            for b in branches
        ],
    }


@router.get("/auth/me")
def me(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == admin.org_id).first()
    branch = None
    if admin.branch_id:
        branch = db.query(Branch).filter(Branch.id == admin.branch_id).first()
    branches_query = db.query(Branch).filter(
        Branch.org_id == admin.org_id, Branch.is_active == True
    )
    if admin.role != "owner" and admin.branch_id:
        branches_query = branches_query.filter(Branch.id == admin.branch_id)
    branches = branches_query.order_by(Branch.is_headquarters.desc(), Branch.name).all()
    return {
        "admin": {
            "id": admin.id, "email": admin.email,
            "full_name": admin.full_name, "role": admin.role,
            "branch_id": admin.branch_id,
        },
        "org": {"id": org.id, "name": org.name, "slug": org.slug, "type": org.org_type} if org else None,
        "branch": {"id": branch.id, "name": branch.name, "code": branch.code} if branch else None,
        "branches": [
            {"id": b.id, "name": b.name, "code": b.code, "is_headquarters": b.is_headquarters}
            for b in branches
        ],
    }


class SwitchBranchRequest(BaseModel):
    branch_id: int


@router.post("/auth/switch-branch")
def switch_branch(req: SwitchBranchRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Switch the admin's active branch and return a new token."""
    if admin.role != "owner":
        # Branch-scoped credentials are locked to one branch.
        if admin.branch_id and req.branch_id != admin.branch_id:
            raise HTTPException(403, "You can only access your assigned branch")
        branch = db.query(Branch).filter(
            Branch.id == admin.branch_id, Branch.org_id == admin.org_id, Branch.is_active == True
        ).first()
        if not branch:
            raise HTTPException(404, "Assigned branch not found")
        token = create_token(admin.id, admin.org_id, branch.id)
        return {
            "token": token,
            "branch": {"id": branch.id, "name": branch.name, "code": branch.code},
        }

    branch = db.query(Branch).filter(
        Branch.id == req.branch_id, Branch.org_id == admin.org_id, Branch.is_active == True
    ).first()
    if not branch:
        raise HTTPException(404, "Branch not found in your organization")
    admin.branch_id = branch.id
    db.commit()
    token = create_token(admin.id, admin.org_id, branch.id)
    return {
        "token": token,
        "branch": {"id": branch.id, "name": branch.name, "code": branch.code},
    }


@router.get("/auth/team")
def get_team(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Get all admins in this org."""
    admins_query = db.query(Admin).filter(Admin.org_id == admin.org_id)
    if admin.role != "owner" and admin.branch_id:
        admins_query = admins_query.filter(Admin.branch_id == admin.branch_id)
    admins = admins_query.all()
    # Build branch lookup
    branch_map = {}
    branch_ids = [a.branch_id for a in admins if a.branch_id]
    if branch_ids:
        branches = db.query(Branch).filter(Branch.id.in_(branch_ids)).all()
        branch_map = {b.id: b.name for b in branches}
    return {
        "team": [
            {
                "id": a.id, "email": a.email, "full_name": a.full_name,
                "role": a.role, "branch_id": a.branch_id,
                "branch_name": branch_map.get(a.branch_id, ""),
            }
            for a in admins
        ]
    }


class InviteRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "admin"
    branch_id: Optional[int] = None


@router.post("/auth/invite", status_code=201)
def invite_member(req: InviteRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Owner/admin can invite another admin."""
    if admin.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owners and admins can invite")
    if db.query(Admin).filter(Admin.email == req.email).first():
        raise HTTPException(409, "Email already registered")

    # Validate/resolve branch assignment.
    target_branch_id = req.branch_id
    if admin.role != "owner" and admin.branch_id:
        if target_branch_id and target_branch_id != admin.branch_id:
            raise HTTPException(403, "You can only invite users into your assigned branch")
        target_branch_id = admin.branch_id
    elif target_branch_id:
        branch = db.query(Branch).filter(
            Branch.id == target_branch_id, Branch.org_id == admin.org_id, Branch.is_active == True
        ).first()
        if not branch:
            raise HTTPException(400, "Branch not found in your organization")
    else:
        # Default to inviter's branch
        target_branch_id = admin.branch_id

    new_admin = Admin(
        org_id=admin.org_id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=req.role if req.role in ("admin", "viewer") else "viewer",
        branch_id=target_branch_id,
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
