from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.task import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    title: str
    description: str
    priority: TaskPriority
    due_date: date


class TaskCreate(TaskBase):
    assigned_to: int


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    assigned_to: int | None = None


class TaskUpdateStatus(BaseModel):
    status: TaskStatus


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TaskStatus
    assigned_to: int
    created_by: int
    created_at: datetime
