from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.task import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    title: str
    description: str
    priority: TaskPriority
    due_datetime: datetime


class TaskCreate(TaskBase):
    assigned_to: int


class TaskUpdate(BaseModel):
    version: int
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_datetime: datetime | None = None
    assigned_to: int | None = None


class TaskUpdateStatus(BaseModel):
    version: int
    status: TaskStatus


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    status: TaskStatus
    assigned_to: int
    created_by: int
    created_at: datetime
    completed_at: datetime | None = None
