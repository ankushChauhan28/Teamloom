from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import (
    AppException,
    AuthorizationException,
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task import TaskCreate, TaskUpdate, TaskUpdateStatus
from app.services.common import get_scoped_or_404
from app.services.permission_service import can_manage_specific_user


async def create_task(db: AsyncSession, task_in: TaskCreate, creator: User) -> Task:
    """
    Creates and assigns a task within the creator's organization.
    Accessible by Tier 1 OR any user who has direct-report authority over the target employee.
    """
    # Verify assignee exists in creator's organization
    assignee = await get_scoped_or_404(
        db=db,
        model=User,
        id_val=task_in.assigned_to,
        organization_id=creator.organization_id,
        error_msg=f"Assigned user with ID {task_in.assigned_to} not found.",
    )

    # Business validation: Check if assignee is an employee (cannot assign to tier 1 admin)
    is_assignee_admin = getattr(assignee, "access_level", None) == 1 or assignee.role != UserRole.EMPLOYEE
    if is_assignee_admin:
        raise BadRequestException("Tasks can only be assigned to users with the EMPLOYEE role.")

    is_admin = getattr(creator, "access_level", None) == 1 or creator.role == UserRole.ADMIN
    has_assignment_authority = can_manage_specific_user(creator, assignee)

    if not (is_admin or has_assignment_authority):
        raise AuthorizationException("You do not have permission to assign tasks to this employee.")

    # Defense-in-depth: Self-assignment via direct-report path blocked
    if not is_admin and task_in.assigned_to == creator.id:
        raise AuthorizationException(
            "You cannot assign a task to yourself via the direct-report assignment path."
        )

    db_task = Task(
        title=task_in.title,
        description=task_in.description,
        priority=task_in.priority,
        due_datetime=task_in.due_datetime,
        assigned_to=task_in.assigned_to,
        created_by=creator.id,
        organization_id=creator.organization_id,
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
    return_total: bool = False,
) -> list[Task] | tuple[list[Task], int]:
    """
    Lists tasks assigned to any of the current user's direct reports in the same organization.
    Returns an empty list if the user has no direct reports.
    """
    capped_limit = min(max(1, limit), 100)
    reports_stmt = select(User.id).where(
        User.reports_to_id == user.id,
        User.organization_id == user.organization_id,
        User.is_active.is_(True),
    )
    reports_res = await db.execute(reports_stmt)
    report_ids = reports_res.scalars().all()

    if not report_ids:
        if return_total:
            return [], 0
        return []

    conditions = [
        Task.organization_id == user.organization_id,
        Task.assigned_to.in_(report_ids),
    ]

    if status:
        conditions.append(Task.status == status)
    if priority:
        conditions.append(Task.priority == priority)

    if return_total:
        stmt = (
            select(Task, func.count(Task.id).over().label("total_count"))
            .where(*conditions)
            .options(selectinload(Task.assigned_to_user))
        )
    else:
        stmt = (
            select(Task)
            .where(*conditions)
            .options(selectinload(Task.assigned_to_user))
        )

    if sort_by and hasattr(Task, sort_by):
        stmt = stmt.order_by(getattr(Task, sort_by).asc(), Task.id.asc())
    else:
        stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())

    stmt = stmt.offset(skip).limit(capped_limit)
    result = await db.execute(stmt)

    if return_total:
        rows = result.all()
        if rows:
            tasks = [row[0] for row in rows]
            total_count = int(rows[0][1])
        else:
            tasks = []
            if skip == 0:
                total_count = 0
            else:
                count_stmt = select(func.count(Task.id)).where(*conditions)
                total_count = (await db.execute(count_stmt)).scalar() or 0
        return tasks, total_count

    return list(result.scalars().all())


async def get_tasks(
    db: AsyncSession,
    user: User,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    return_total: bool = False,
) -> list[Task] | tuple[list[Task], int]:
    """
    Lists tasks. Admins see all tasks in org, employees see only their own assigned tasks.
    Supports filtering, sorting, and deterministic pagination.
    """
    capped_limit = min(max(1, limit), 100)
    conditions = [Task.organization_id == user.organization_id]

    # Tier / Role check: Tier 1 sees all in org, others see only their own assigned tasks
    is_admin = getattr(user, "access_level", None) == 1 or user.role == UserRole.ADMIN
    if not is_admin:
        conditions.append(Task.assigned_to == user.id)

    # Filters
    if status:
        conditions.append(Task.status == status)
    if priority:
        conditions.append(Task.priority == priority)

    if return_total:
        stmt = (
            select(Task, func.count(Task.id).over().label("total_count"))
            .where(*conditions)
            .options(selectinload(Task.assigned_to_user))
        )
    else:
        stmt = select(Task).where(*conditions).options(selectinload(Task.assigned_to_user))

    # Dynamic Sorting with secondary deterministic column
    if sort_by:
        if hasattr(Task, sort_by):
            stmt = stmt.order_by(getattr(Task, sort_by).asc(), Task.id.asc())
        else:
            raise BadRequestException(f"Invalid sort column: {sort_by}")
    else:
        # Default sort by created_at descending, then id descending
        stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())

    # Pagination
    stmt = stmt.offset(skip).limit(capped_limit)
    result = await db.execute(stmt)

    if return_total:
        rows = result.all()
        if rows:
            tasks = [row[0] for row in rows]
            total_count = int(rows[0][1])
        else:
            tasks = []
            if skip == 0:
                total_count = 0
            else:
                count_stmt = select(func.count(Task.id)).where(*conditions)
                total_count = (await db.execute(count_stmt)).scalar() or 0
        return tasks, total_count

    return list(result.scalars().all())


async def get_task_by_id(db: AsyncSession, task_id: int, user: User) -> Task:
    """
    Retrieves a single task by ID scoped to the user's organization.
    Performs ownership validation for non-admin tiers.
    """
    db_task = await get_scoped_or_404(
        db=db,
        model=Task,
        id_val=task_id,
        organization_id=user.organization_id,
        error_msg=f"Task with ID {task_id} not found.",
    )

    # Ownership Check
    is_admin = getattr(user, "access_level", None) == 1 or user.role == UserRole.ADMIN
    if not is_admin and db_task.assigned_to != user.id:
        raise AuthorizationException("You are not authorized to view this task.")

    return db_task


async def update_task(
    db: AsyncSession, task_id: int, task_update: TaskUpdate | TaskUpdateStatus, user: User
) -> Task:
    """
    Updates a task scoped to the user's organization.
    Tier 1 can update any field; non-admin can only update status.
    Automatically sets completed_at timestamp when status transitions to COMPLETED.
    """
    db_task = await get_task_by_id(db, task_id, user)

    # Optimistic locking: compare incoming client version against current DB version
    if getattr(task_update, "version", None) is not None:
        if db_task.version != task_update.version:
            raise AppException(
                status_code=409,
                detail="Task was modified concurrently. Please refresh and retry.",
            )

    update_data = task_update.model_dump(exclude_unset=True)
    update_data.pop("version", None)

    # Enforce update constraints for non-admin
    is_admin = getattr(user, "access_level", None) == 1 or user.role == UserRole.ADMIN
    if not is_admin:
        # Only status field is allowed for non-admin
        invalid_keys = [k for k in update_data.keys() if k != "status"]
        if invalid_keys:
            raise AuthorizationException("Employees are only permitted to update the task status.")

    # Prevent modifications on already COMPLETED tasks
    if (db_task.status == "COMPLETED" or db_task.status == TaskStatus.COMPLETED) and "status" in update_data:
        raise AppException(status_code=400, detail="Cannot modify a completed task.")

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

    try:
        await db.commit()
        await db.refresh(db_task)
        return db_task
    except StaleDataError:
        await db.rollback()
        raise AppException(
            status_code=409,
            detail="Task was modified concurrently. Please refresh and retry.",
        )


async def delete_task(db: AsyncSession, task_id: int, user: User) -> None:
    """
    Deletes a task scoped to the user's organization. Tier 1 only.
    """
    is_admin = getattr(user, "access_level", None) == 1 or user.role == UserRole.ADMIN
    if not is_admin:
        raise AuthorizationException("Only administrators can delete tasks.")

    db_task = await get_scoped_or_404(
        db=db,
        model=Task,
        id_val=task_id,
        organization_id=user.organization_id,
        error_msg=f"Task with ID {task_id} not found.",
    )

    await db.delete(db_task)
    await db.commit()
