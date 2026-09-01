from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task import TaskCreate, TaskUpdate, TaskUpdateStatus


async def create_task(db: AsyncSession, task_in: TaskCreate, creator: User) -> Task:
    """
    Creates and assigns a task.
    Accessible by Admin OR any user who is the direct manager of the assigned_to employee.
    """
    # Verify assignee exists
    result = await db.execute(select(User).where(User.id == task_in.assigned_to))
    assignee = result.scalar_one_or_none()
    if not assignee:
        raise ResourceNotFoundException(f"Assigned user with ID {task_in.assigned_to} not found.")

    # Business validation: Check if assignee is an employee
    if assignee.role != UserRole.EMPLOYEE:
        raise BadRequestException("Tasks can only be assigned to users with the EMPLOYEE role.")

    is_admin = creator.role == UserRole.ADMIN
    is_direct_manager = assignee.reports_to_id == creator.id

    if not (is_admin or is_direct_manager):
        raise AuthorizationException("You do not have permission to assign tasks to this employee.")

    # Defense-in-depth: Self-assignment via manager path blocked
    if not is_admin and task_in.assigned_to == creator.id:
        raise AuthorizationException(
            "You cannot assign a task to yourself via the manager assignment path."
        )

    db_task = Task(
        title=task_in.title,
        description=task_in.description,
        priority=task_in.priority,
        due_datetime=task_in.due_datetime,
        assigned_to=task_in.assigned_to,
        created_by=creator.id,
    )
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task


async def get_team_tasks(
    db: AsyncSession,
    user: User,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
) -> list[Task]:
    """
    Lists tasks assigned to any of the current user's direct reports.
    Returns an empty list if the user has no direct reports.
    """
    reports_stmt = select(User.id).where(User.reports_to_id == user.id)
    reports_res = await db.execute(reports_stmt)
    report_ids = reports_res.scalars().all()

    if not report_ids:
        return []

    stmt = select(Task).where(Task.assigned_to.in_(report_ids))

    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)

    if sort_by and hasattr(Task, sort_by):
        stmt = stmt.order_by(getattr(Task, sort_by).asc())
    else:
        stmt = stmt.order_by(Task.created_at.desc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tasks(
    db: AsyncSession,
    user: User,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
) -> list[Task]:
    """
    Lists tasks. Admins see all, employees see only their own assigned tasks.
    Supports filtering, sorting, and pagination.
    """
    stmt = select(Task)

    # Role check: Employee sees only their own assigned tasks
    if user.role == UserRole.EMPLOYEE:
        stmt = stmt.where(Task.assigned_to == user.id)

    # Filters
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)

    # Dynamic Sorting
    if sort_by:
        # Check if the sort_by column is valid on the Task model
        if hasattr(Task, sort_by):
            stmt = stmt.order_by(getattr(Task, sort_by).asc())
        else:
            raise BadRequestException(f"Invalid sort column: {sort_by}")
    else:
        # Default sort by created_at descending
        stmt = stmt.order_by(Task.created_at.desc())

    # Pagination
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_task_by_id(db: AsyncSession, task_id: int, user: User) -> Task:
    """
    Retrieves a single task by ID. Performs ownership validation for Employees.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    db_task = result.scalar_one_or_none()
    if not db_task:
        raise ResourceNotFoundException(f"Task with ID {task_id} not found.")

    # Ownership Check
    if user.role == UserRole.EMPLOYEE and db_task.assigned_to != user.id:
        raise AuthorizationException("You are not authorized to view this task.")

    return db_task


async def update_task(
    db: AsyncSession, task_id: int, task_update: TaskUpdate | TaskUpdateStatus, user: User
) -> Task:
    """
    Updates a task. Admin can update any field; Employee can only update status.
    Automatically sets completed_at timestamp when status transitions to COMPLETED.
    """
    db_task = await get_task_by_id(db, task_id, user)

    update_data = task_update.model_dump(exclude_unset=True)

    # Enforce update constraints for Employee
    if user.role == UserRole.EMPLOYEE:
        # Only status field is allowed for employees
        invalid_keys = [k for k in update_data.keys() if k != "status"]
        if invalid_keys:
            raise AuthorizationException("Employees are only permitted to update the task status.")

    # Status transition logic for completed_at timestamp
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == TaskStatus.COMPLETED and db_task.status != TaskStatus.COMPLETED:
            db_task.completed_at = datetime.now(UTC)
        elif new_status != TaskStatus.COMPLETED and db_task.status == TaskStatus.COMPLETED:
            db_task.completed_at = None

    # Apply changes
    for key, value in update_data.items():
        setattr(db_task, key, value)

    await db.commit()
    await db.refresh(db_task)
    return db_task


async def delete_task(db: AsyncSession, task_id: int, user: User) -> None:
    """
    Deletes a task. Admin only (checked at route level, but enforced here too).
    """
    if user.role != UserRole.ADMIN:
        raise AuthorizationException("Only administrators can delete tasks.")

    result = await db.execute(select(Task).where(Task.id == task_id))
    db_task = result.scalar_one_or_none()
    if not db_task:
        raise ResourceNotFoundException(f"Task with ID {task_id} not found.")

    await db.delete(db_task)
    await db.commit()
