from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    profile_photo = Column(String, nullable=True)  # member's profile photo path
    member_type = Column(String, default="member")  # "member" or "new_member"
    meeting_id = Column(Integer, nullable=True, index=True)   # links to meetings.id
    meeting_name = Column(String, nullable=True)               # denormalized for fast display
    time = Column(DateTime, default=datetime.utcnow)
