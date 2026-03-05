"""Visitor / unknown face model – for faces detected but not yet matched to a member."""

from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, Boolean, ForeignKey
from datetime import datetime
from app.database import Base


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)  # First seen at branch
    face_photo = Column(String, nullable=False)  # path to cropped face image
    face_embedding = Column(LargeBinary, nullable=True)  # 128-d encoding
    label = Column(String, nullable=True)  # admin-assigned name / label
    is_new_member = Column(Boolean, default=True)  # True if confirmed as a new person
    linked_member_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # links to users.id if matched
    verified = Column(Boolean, default=False)  # admin verified
    visit_count = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    last_seen_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)  # Last branch visited
