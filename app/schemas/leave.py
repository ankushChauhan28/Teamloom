from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.leave import LeaveStatus


class LeaveBase(BaseModel):
    reason: str
    start_date: date
    end_date: date


class LeaveCreate(LeaveBase):
    pass


class LeaveUpdateStatus(BaseModel):
    status: LeaveStatus


class LeaveRead(LeaveBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    status: LeaveStatus
    reviewed_by: int | None = None
    created_at: datetime
