from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, ForeignKey, Boolean
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)  # Home branch
    name = Column(String, nullable=False)
    face_embedding = Column(LargeBinary, nullable=False)
    profile_photo = Column(String, nullable=True)  # path to photo
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_global = Column(Boolean, default=True)  # If True, recognized across all branches
    created_at = Column(DateTime, default=datetime.utcnow)
