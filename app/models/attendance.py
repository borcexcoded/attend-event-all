from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from datetime import datetime
from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)  # Branch where marked
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Linked member (if member)
    visitor_id = Column(Integer, ForeignKey("visitors.id"), nullable=True, index=True)  # Linked visitor (if visitor)
    name = Column(String, nullable=False)
    profile_photo = Column(String, nullable=True)  # member's profile photo path
    member_type = Column(String, default="member")  # "member", "visitor", "new_member"
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    meeting_name = Column(String, nullable=True)               # denormalized for fast display
    is_late = Column(Boolean, default=False)                   # Arrived after meeting start
    late_minutes = Column(Integer, default=0)                  # How late in minutes
    marked_at_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)  # Different if visiting another branch
    is_joint_service = Column(Boolean, default=False)          # Marked during joint service
    joint_service_id = Column(Integer, ForeignKey("joint_services.id"), nullable=True)
    time = Column(DateTime, default=datetime.utcnow)
