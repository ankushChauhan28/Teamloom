import enum

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    EMPLOYEE = "EMPLOYEE"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships (relationships mapped as strings to avoid circular import issues)
    assigned_tasks = relationship(
        "Task",
        foreign_keys="[Task.assigned_to]",
        back_populates="assigned_employee",
        cascade="all, delete-orphan",
    )
    created_tasks = relationship(
        "Task",
        foreign_keys="[Task.created_by]",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    leave_requests = relationship(
        "LeaveRequest",
        foreign_keys="[LeaveRequest.employee_id]",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    reviewed_leaves = relationship(
        "LeaveRequest", foreign_keys="[LeaveRequest.reviewed_by]", back_populates="reviewer"
    )
