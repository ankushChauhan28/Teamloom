import enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    priority = Column(SQLEnum(TaskPriority), nullable=False)
    due_date = Column(Date, nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    assigned_employee = relationship(
        "User", foreign_keys=[assigned_to], back_populates="assigned_tasks"
    )
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_tasks")
