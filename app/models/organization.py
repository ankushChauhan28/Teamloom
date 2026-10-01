import enum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class OrgStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(
        String(50),
        CheckConstraint(
            "status IN ('pending_payment', 'active', 'suspended')",
            name="check_org_status",
        ),
        default=OrgStatus.ACTIVE.value,
        nullable=False,
    )
    is_internal = Column(Boolean, default=False, nullable=False)
    gst_number = Column(String(50), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="organization", cascade="all, delete-orphan")
    leave_requests = relationship(
        "LeaveRequest", back_populates="organization", cascade="all, delete-orphan"
    )
