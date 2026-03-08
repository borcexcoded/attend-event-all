"""Branch model – supports multi-branch church organizations."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Branch(Base):
    """A branch/location within an organization (e.g., Main Campus, City Campus)."""
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True, index=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    is_headquarters = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    timezone = Column(String, default="Africa/Lagos")
    created_at = Column(DateTime, default=datetime.utcnow)


class BranchAdmin(Base):
    """Links admins to specific branches they can manage."""
    __tablename__ = "branch_admins"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    role = Column(String, default="admin")
    can_manage_members = Column(Boolean, default=True)
    can_view_analytics = Column(Boolean, default=True)
    can_view_all_branches = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class JointService(Base):
    """Records when branches hold a combined service at one location."""
    __tablename__ = "joint_services"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    host_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    service_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class JointServiceBranch(Base):
    """Participating branches in a joint service."""
    __tablename__ = "joint_service_branches"

    id = Column(Integer, primary_key=True, index=True)
    joint_service_id = Column(Integer, ForeignKey("joint_services.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
