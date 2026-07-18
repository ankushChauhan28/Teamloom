from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.task import TaskStatus, TaskPriority

class TaskBase(BaseModel):
    title: str
    description: str
    priority: TaskPriority
    due_date: date

class TaskCreate(TaskBase):
    assigned_to: int

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None
    assigned_to: Optional[int] = None

class TaskUpdateStatus(BaseModel):
    status: TaskStatus

class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TaskStatus
    assigned_to: int
    created_by: int
    created_at: datetime
