from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_password_change_cleared, require_role
from app.db.session import get_db
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    Create a new task and assign it to an employee.
    Accessible by Admin OR any user who is the direct manager of the target employee.
    """
    return await task_service.create_task(db=db, task_in=task_in, creator=current_user)


@router.get("/team", response_model=list[TaskRead])
async def list_team_tasks(
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    List tasks assigned to any of the current user's direct reports.
    Returns an empty list if the user has no direct reports.
    """
    return await task_service.get_team_tasks(
        db=db,
        user=current_user,
        status=status,
        priority=priority,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.get("/", response_model=list[TaskRead])
async def list_tasks(
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    List tasks. Admin sees all tasks; Employee sees only their assigned tasks.
    Supports filtering by status and priority, sorting, and pagination.
    """
    return await task_service.get_tasks(
        db=db,
        user=current_user,
        status=status,
        priority=priority,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.get("/{id}", response_model=TaskRead)
async def get_task(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    Retrieve details of a single task. Employees can only view their own tasks.
    """
    return await task_service.get_task_by_id(db=db, task_id=id, user=current_user)


@router.patch("/{id}", response_model=TaskRead)
async def update_task(
    id: int,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    Update a task. Admin can update any field.
    Employees can only update the status field of their assigned tasks.
    """
    return await task_service.update_task(
        db=db, task_id=id, task_update=task_update, user=current_user
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Delete a task. Admin only.
    """
    await task_service.delete_task(db=db, task_id=id, user=current_admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
