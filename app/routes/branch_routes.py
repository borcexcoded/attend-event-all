from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.branch import Branch, BranchAdmin, JointService, JointServiceBranch
from app.models.user import User
from app.models.attendance import Attendance
from app.models.meeting import Meeting
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(prefix="/branches", tags=["Branches"])


def _owner_only(admin: Admin):
    if admin.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can perform this action",
        )


def _assert_branch_scope(admin: Admin, branch: Branch):
    if admin.role == "owner":
        return
    if admin.branch_id != branch.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )


# ============ SCHEMAS ============

class BranchCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: str = "Africa/Lagos"
    is_headquarters: bool = False
    org_id: Optional[int] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    id: int
    name: str
    code: str
    address: Optional[str]
    city: Optional[str]
    country: Optional[str]
    timezone: str
    is_headquarters: bool
    is_active: bool
    member_count: int = 0
    meeting_count: int = 0

    class Config:
        from_attributes = True


class BranchAdminCreate(BaseModel):
    branch_id: int
    admin_id: int
    can_manage_members: bool = True
    can_view_analytics: bool = True


class JointServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    host_branch_id: int
    service_date: datetime
    branch_ids: List[int]


class JointServiceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    host_branch_id: int
    host_branch_name: str
    service_date: datetime
    participating_branches: List[str]
    total_attendance: int = 0

    class Config:
        from_attributes = True


# ============ BRANCH ENDPOINTS ============

@router.post("/", response_model=BranchResponse)
def create_branch(branch: BranchCreate, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Create a new branch (org owner/admin only)."""
    _owner_only(admin)
    org_id = admin.org_id

    # Check if branch code already exists within this org
    existing = db.query(Branch).filter(
        Branch.code == branch.code.upper(), Branch.org_id == org_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Branch with code '{branch.code}' already exists"
        )
    
    # If this is headquarters, unset any existing headquarters for this org
    if branch.is_headquarters:
        db.query(Branch).filter(
            Branch.is_headquarters == True, Branch.org_id == org_id
        ).update({"is_headquarters": False})
    
    new_branch = Branch(
        name=branch.name,
        code=branch.code.upper(),
        address=branch.address,
        city=branch.city,
        country=branch.country,
        timezone=branch.timezone,
        is_headquarters=branch.is_headquarters,
        org_id=org_id
    )
    db.add(new_branch)
    db.commit()
    db.refresh(new_branch)
    
    return BranchResponse(
        id=new_branch.id,
        name=new_branch.name,
        code=new_branch.code,
        address=new_branch.address,
        city=new_branch.city,
        country=new_branch.country,
        timezone=new_branch.timezone,
        is_headquarters=new_branch.is_headquarters,
        is_active=new_branch.is_active,
        member_count=0,
        meeting_count=0
    )


@router.get("/", response_model=List[BranchResponse])
def get_branches(
    active_only: bool = True,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all branches with member and meeting counts."""
    query = db.query(Branch).filter(Branch.org_id == admin.org_id)

    # Branch-scoped credentials only see their assigned branch.
    if admin.role != "owner" and admin.branch_id:
        query = query.filter(Branch.id == admin.branch_id)
    
    if active_only:
        query = query.filter(Branch.is_active == True)
    
    branches = query.order_by(Branch.is_headquarters.desc(), Branch.name).all()
    
    result = []
    for branch in branches:
        member_count = db.query(func.count(User.id)).filter(
            User.branch_id == branch.id
        ).scalar() or 0
        
        meeting_count = db.query(func.count(Meeting.id)).filter(
            Meeting.branch_id == branch.id
        ).scalar() or 0
        
        result.append(BranchResponse(
            id=branch.id,
            name=branch.name,
            code=branch.code,
            address=branch.address,
            city=branch.city,
            country=branch.country,
            timezone=branch.timezone,
            is_headquarters=branch.is_headquarters,
            is_active=branch.is_active,
            member_count=member_count,
            meeting_count=meeting_count
        ))
    
    return result


@router.get("/{branch_id}", response_model=BranchResponse)
def get_branch(
    branch_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get a specific branch by ID."""
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.org_id == admin.org_id,
    ).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    _assert_branch_scope(admin, branch)
    
    member_count = db.query(func.count(User.id)).filter(
        User.branch_id == branch.id
    ).scalar() or 0
    
    meeting_count = db.query(func.count(Meeting.id)).filter(
        Meeting.branch_id == branch.id
    ).scalar() or 0
    
    return BranchResponse(
        id=branch.id,
        name=branch.name,
        code=branch.code,
        address=branch.address,
        city=branch.city,
        country=branch.country,
        timezone=branch.timezone,
        is_headquarters=branch.is_headquarters,
        is_active=branch.is_active,
        member_count=member_count,
        meeting_count=meeting_count
    )


@router.put("/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    update_data: BranchUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update a branch."""
    _owner_only(admin)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.org_id == admin.org_id,
    ).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(branch, key, value)
    
    db.commit()
    db.refresh(branch)
    
    member_count = db.query(func.count(User.id)).filter(
        User.branch_id == branch.id
    ).scalar() or 0
    
    meeting_count = db.query(func.count(Meeting.id)).filter(
        Meeting.branch_id == branch.id
    ).scalar() or 0
    
    return BranchResponse(
        id=branch.id,
        name=branch.name,
        code=branch.code,
        address=branch.address,
        city=branch.city,
        country=branch.country,
        timezone=branch.timezone,
        is_headquarters=branch.is_headquarters,
        is_active=branch.is_active,
        member_count=member_count,
        meeting_count=meeting_count
    )


@router.delete("/{branch_id}")
def delete_branch(
    branch_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a branch (soft delete)."""
    _owner_only(admin)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.org_id == admin.org_id,
    ).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    if branch.is_headquarters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete headquarters branch"
        )
    
    branch.is_active = False
    db.commit()
    
    return {"message": f"Branch '{branch.name}' has been deactivated"}


# ============ BRANCH ADMIN ENDPOINTS ============

@router.post("/{branch_id}/admins")
def add_branch_admin(
    branch_id: int,
    req: BranchAdminCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Add an admin to a branch."""
    _owner_only(current_admin)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.org_id == current_admin.org_id,
    ).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    # Check if admin already assigned
    existing = db.query(BranchAdmin).filter(
        BranchAdmin.branch_id == branch_id,
        BranchAdmin.admin_id == req.admin_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin already assigned to this branch"
        )
    
    branch_admin = BranchAdmin(
        branch_id=branch_id,
        admin_id=req.admin_id,
        can_manage_members=req.can_manage_members,
        can_view_analytics=req.can_view_analytics
    )
    db.add(branch_admin)
    db.commit()
    
    return {"message": "Admin added to branch successfully"}


@router.get("/{branch_id}/members")
def get_branch_members(
    branch_id: int,
    include_global: bool = True,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all members belonging to a branch."""
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.org_id == admin.org_id,
    ).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    _assert_branch_scope(admin, branch)

    query = db.query(User).filter(User.org_id == admin.org_id)

    if admin.role != "owner":
        include_global = False
    
    if include_global:
        query = query.filter(
            (User.branch_id == branch_id) | (User.is_global == True)
        )
    else:
        query = query.filter(User.branch_id == branch_id)
    
    members = query.all()
    
    return [
        {
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "phone": m.phone,
            "role": m.role,
            "is_global": m.is_global,
            "profile_photo": m.profile_photo,
            "created_at": m.created_at
        }
        for m in members
    ]


# ============ JOINT SERVICE ENDPOINTS ============

@router.post("/joint-services", response_model=JointServiceResponse)
def create_joint_service(
    service: JointServiceCreate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Create a joint service across multiple branches."""
    _owner_only(admin)

    # Verify host branch exists
    host_branch = db.query(Branch).filter(
        Branch.id == service.host_branch_id,
        Branch.org_id == admin.org_id,
    ).first()
    if not host_branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host branch not found"
        )
    
    # Create joint service
    joint_service = JointService(
        org_id=admin.org_id,
        name=service.name,
        description=service.description,
        host_branch_id=service.host_branch_id,
        service_date=service.service_date
    )
    db.add(joint_service)
    db.commit()
    db.refresh(joint_service)
    
    # Add participating branches
    branch_names = []
    for branch_id in service.branch_ids:
        branch = db.query(Branch).filter(
            Branch.id == branch_id,
            Branch.org_id == admin.org_id,
        ).first()
        if branch:
            jsb = JointServiceBranch(
                joint_service_id=joint_service.id,
                branch_id=branch_id
            )
            db.add(jsb)
            branch_names.append(branch.name)
    
    db.commit()
    
    return JointServiceResponse(
        id=joint_service.id,
        name=joint_service.name,
        description=joint_service.description,
        host_branch_id=joint_service.host_branch_id,
        host_branch_name=host_branch.name,
        service_date=joint_service.service_date,
        participating_branches=branch_names,
        total_attendance=0
    )


@router.get("/joint-services")
def get_joint_services(
    upcoming_only: bool = False,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all joint services."""
    query = db.query(JointService).filter(JointService.org_id == admin.org_id)
    
    if upcoming_only:
        query = query.filter(JointService.service_date >= datetime.utcnow())
    
    services = query.order_by(JointService.service_date.desc()).all()
    
    result = []
    for service in services:
        host_branch = db.query(Branch).filter(Branch.id == service.host_branch_id).first()
        
        # Get participating branches
        jsb_records = db.query(JointServiceBranch).filter(
            JointServiceBranch.joint_service_id == service.id
        ).all()
        
        branch_names = []
        for jsb in jsb_records:
            branch = db.query(Branch).filter(Branch.id == jsb.branch_id).first()
            if branch:
                branch_names.append(branch.name)
        
        # Get attendance count
        attendance_count = db.query(func.count(Attendance.id)).filter(
            Attendance.joint_service_id == service.id
        ).scalar() or 0

        if admin.role != "owner" and admin.branch_id:
            if service.host_branch_id != admin.branch_id and admin.branch_id not in [
                jsb.branch_id for jsb in jsb_records
            ]:
                continue
        
        result.append({
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "host_branch_id": service.host_branch_id,
            "host_branch_name": host_branch.name if host_branch else "Unknown",
            "service_date": service.service_date,
            "participating_branches": branch_names,
            "total_attendance": attendance_count
        })
    
    return result


@router.get("/joint-services/{service_id}/attendance")
def get_joint_service_attendance(
    service_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get attendance breakdown for a joint service by branch."""
    service = db.query(JointService).filter(
        JointService.id == service_id,
        JointService.org_id == admin.org_id,
    ).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Joint service not found"
        )

    if admin.role != "owner" and admin.branch_id:
        if service.host_branch_id != admin.branch_id:
            participant = db.query(JointServiceBranch).filter(
                JointServiceBranch.joint_service_id == service.id,
                JointServiceBranch.branch_id == admin.branch_id,
            ).first()
            if not participant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Joint service not found",
                )
    
    # Get attendance grouped by branch
    attendance_by_branch = db.query(
        Attendance.branch_id,
        func.count(Attendance.id).label("count")
    ).filter(
        Attendance.joint_service_id == service_id
    ).group_by(Attendance.branch_id).all()
    
    result = []
    for branch_id, count in attendance_by_branch:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        result.append({
            "branch_id": branch_id,
            "branch_name": branch.name if branch else "Unknown",
            "attendance_count": count
        })
    
    return {
        "service": {
            "id": service.id,
            "name": service.name,
            "service_date": service.service_date
        },
        "attendance_by_branch": result,
        "total_attendance": sum(r["attendance_count"] for r in result)
    }
