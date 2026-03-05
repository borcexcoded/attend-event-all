"""Meeting / scheduled service model – recurring events like Sunday Service, Bible Study, etc."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from datetime import datetime
from app.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)  # Branch-specific or org-wide if NULL
    name = Column(String, nullable=False)               # e.g. "Sunday Service", "Bible Study"
    description = Column(String, nullable=True)
    recurrence = Column(String, default="weekly")        # "daily", "weekly", "biweekly", "monthly", "once"
    day_of_week = Column(Integer, nullable=True)         # 0=Mon … 6=Sun  (for weekly/biweekly)
    day_of_month = Column(Integer, nullable=True)        # 1-31 (for monthly)
    start_time = Column(String, nullable=True)           # "09:00" HH:MM
    end_time = Column(String, nullable=True)             # "12:00" HH:MM
    late_after_minutes = Column(Integer, default=15)     # Minutes after start_time to mark as late
    color = Column(String, default="#3b82f6")            # UI accent colour
    is_active = Column(Boolean, default=True)
    track_visitors = Column(Boolean, default=True)       # whether to record visitors
    created_at = Column(DateTime, default=datetime.utcnow)
