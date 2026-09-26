from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    ResourceNotFoundException,
)
from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.schemas.analytics import PerformanceStats, TrailItem


def _classify_task_state(
    task: Task, now_dt: datetime
) -> Literal["on_time", "late", "overdue", "pending"]:
    """
    Canonical classification rule for task performance states:
    - on_time: status == COMPLETED and completed_at <= due_datetime
    - late: status == COMPLETED and completed_at > due_datetime
    - overdue: status != COMPLETED and due_datetime < now
    - pending: status != COMPLETED and due_datetime >= now

    Note: This Python classification function strictly mirrors the SQL CASE expressions
    used in server-side conditional aggregation.
    """
    if task.status == TaskStatus.COMPLETED:
        if task.completed_at:
            comp = (
                task.completed_at
                if task.completed_at.tzinfo is not None
                else task.completed_at.replace(tzinfo=UTC)
            )
            due = (
                task.due_datetime
                if task.due_datetime.tzinfo is not None
                else task.due_datetime.replace(tzinfo=UTC)
            )
            if comp <= due:
                return "on_time"
            return "late"
        return "late"
    else:
        due = (
            task.due_datetime
            if task.due_datetime.tzinfo is not None
            else task.due_datetime.replace(tzinfo=UTC)
        )
        if due < now_dt:
            return "overdue"
        return "pending"


async def get_performance_analytics(
    db: AsyncSession,
    user: User,
    employee_id: int | None = None,
    trail_limit: int = 10,
) -> PerformanceStats:
    """
    Computes performance analytics (on-time rate, categorized counts, milestone trail)
    using server-side SQL conditional aggregations.

    Enforces authorization and scoping:
    - EMPLOYEE (no reports): Sees only self. Passing non-matching employee_id -> 403.
    - Manager (has reports):
        - Without employee_id -> team aggregate across direct reports (scope="team").
        - With employee_id == user.id -> manager's personal stats (scope="self").
        - With employee_id of direct report -> individual report's stats (scope="employee").
        - With employee_id of non-report OR non-existent employee -> 403 Forbidden (identical status & body to prevent ID enumeration).
    - ADMIN: Without employee_id -> org-wide (scope="org"). With employee_id -> individual employee's stats (scope="employee", 404 if user not found).
    """
    # Enforce hard cap on trail_limit (1 <= trail_limit <= 50)
    capped_trail_limit = max(1, min(trail_limit, 50))
    now = datetime.now(UTC)

    # Check for direct reports
    reports_stmt = select(User.id).where(User.reports_to_id == user.id)
    reports_res = await db.execute(reports_stmt)
    report_ids = list(reports_res.scalars().all())
    has_reports = len(report_ids) > 0

    resolved_scope: Literal["self", "team", "org", "employee"] = "self"
    target_employee_id: int | None = None
    filter_stmt = None

    is_admin = getattr(user, "access_level", None) == 1 or user.role == UserRole.ADMIN

    if not is_admin:
        if not has_reports:
            if employee_id is not None and employee_id != user.id:
                raise AuthorizationException(
                    "You do not have permission to view performance analytics for other employees."
                )
            resolved_scope = "self"
            filter_stmt = Task.assigned_to == user.id
        else:
            if employee_id is None:
                resolved_scope = "team"
                filter_stmt = Task.assigned_to.in_(report_ids)
            elif employee_id == user.id:
                resolved_scope = "self"
                filter_stmt = Task.assigned_to == user.id
            elif employee_id in report_ids:
                resolved_scope = "employee"
                target_employee_id = employee_id
                filter_stmt = Task.assigned_to == employee_id
            else:
                # Returns generic 403 for both non-existent ID and non-report ID to prevent ID enumeration
                raise AuthorizationException(
                    "You do not have permission to view performance analytics for this employee."
                )
    else:
        if employee_id is None:
            resolved_scope = "org"
            filter_stmt = None
        else:
            emp_res = await db.execute(select(User).where(User.id == employee_id))
            target_emp = emp_res.scalar_one_or_none()
            if not target_emp:
                raise ResourceNotFoundException(f"User with ID {employee_id} not found.")
            resolved_scope = "employee"
            target_employee_id = employee_id
            filter_stmt = Task.assigned_to == employee_id

    # SQL-side conditional aggregations (must mirror _classify_task_state)
    on_time_case = case(
        (
            (Task.status == TaskStatus.COMPLETED) & (Task.completed_at <= Task.due_datetime),
            1,
        ),
        else_=0,
    )
    late_case = case(
        (
            (Task.status == TaskStatus.COMPLETED) & (Task.completed_at > Task.due_datetime),
            1,
        ),
        else_=0,
    )
    overdue_case = case(
        (
            (Task.status != TaskStatus.COMPLETED) & (Task.due_datetime < now),
            1,
        ),
        else_=0,
    )
    pending_case = case(
        (
            (Task.status != TaskStatus.COMPLETED) & (Task.due_datetime >= now),
            1,
        ),
        else_=0,
    )

    # Defensive guard: exclude legacy/corrupted rows with NULL due_datetime from aggregation
    stats_stmt = select(
        func.count(Task.id).label("total_tasks"),
        func.coalesce(func.sum(on_time_case), 0).label("on_time_count"),
        func.coalesce(func.sum(late_case), 0).label("late_count"),
        func.coalesce(func.sum(overdue_case), 0).label("overdue_count"),
        func.coalesce(func.sum(pending_case), 0).label("pending_count"),
    ).where(Task.due_datetime.is_not(None))

    if filter_stmt is not None:
        stats_stmt = stats_stmt.where(filter_stmt)

    result = await db.execute(stats_stmt)
    row = result.one()

    total_tasks = row.total_tasks or 0
    on_time_count = int(row.on_time_count or 0)
    late_count = int(row.late_count or 0)
    overdue_count = int(row.overdue_count or 0)
    pending_count = int(row.pending_count or 0)

    # completion_rate calculation: on_time_count / total_completed (completed = on_time_count + late_count).
    # Guarded against division-by-zero to 0.0 when total_completed == 0.
    total_completed = on_time_count + late_count
    if total_completed > 0:
        completion_rate = round(on_time_count / total_completed, 4)
    else:
        completion_rate = 0.0

    # Fetch milestone trail ordered by Task.due_datetime desc (most recent upcoming and completed deadlines first)
    trail_stmt = select(Task).where(Task.due_datetime.is_not(None))
    if filter_stmt is not None:
        trail_stmt = trail_stmt.where(filter_stmt)
    trail_stmt = trail_stmt.order_by(Task.due_datetime.desc()).limit(capped_trail_limit)

    trail_res = await db.execute(trail_stmt)
    trail_tasks = list(trail_res.scalars().all())

    milestone_trail = [
        TrailItem(
            id=task.id,
            title=task.title,
            state=_classify_task_state(task, now),
            due_datetime=task.due_datetime,
            completed_at=task.completed_at,
        )
        for task in trail_tasks
    ]

    return PerformanceStats(
        scope=resolved_scope,
        employee_id=target_employee_id,
        total_tasks=total_tasks,
        on_time_count=on_time_count,
        late_count=late_count,
        overdue_count=overdue_count,
        pending_count=pending_count,
        completion_rate=completion_rate,
        milestone_trail=milestone_trail,
    )
