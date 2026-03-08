"""Custom registration fields – admin-configurable per org."""

from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from datetime import datetime
from app.database import Base


class RegistrationField(Base):
    """Defines a custom field that appears on the member registration form."""
    __tablename__ = "registration_fields"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    field_name = Column(String, nullable=False)          # e.g. "Address", "Date of Birth"
    field_label = Column(String, nullable=False)          # Display label
    field_type = Column(String, nullable=False, default="text")  # text, email, phone, date, select, textarea
    is_required = Column(Boolean, default=False)
    options = Column(Text, nullable=True)                 # JSON array for select type: '["Male","Female"]'
    field_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemberCustomData(Base):
    """Stores custom field values for each member."""
    __tablename__ = "member_custom_data"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = Column(Integer, ForeignKey("registration_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(Text, nullable=True)
