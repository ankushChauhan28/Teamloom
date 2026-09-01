from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TrailItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    state: Literal["on_time", "late", "overdue", "pending"]
    due_datetime: datetime
    completed_at: datetime | None = None


class PerformanceStats(BaseModel):
    scope: Literal["self", "team", "org", "employee"]
    employee_id: int | None = None
    total_tasks: int
    on_time_count: int
    late_count: int
    overdue_count: int
    pending_count: int
    completion_rate: (
        float  # on_time_count / (on_time_count + late_count); 0.0 if no completed tasks
    )
    milestone_trail: list[TrailItem]
