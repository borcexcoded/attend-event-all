from sqlalchemy import Column, Integer, String, LargeBinary, DateTime
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    face_embedding = Column(LargeBinary, nullable=False)
    profile_photo = Column(String, nullable=True)  # path to photo
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
