from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationException,
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task import TaskCreate, TaskUpdate, TaskUpdateStatus


def create_task(db: Session, task_in: TaskCreate, creator_id: int) -> Task:
    """
    Creates and assigns a task. Only accessible by Admins (checked at route level).
    """
    # Verify assignee exists
    assignee = db.query(User).filter(User.id == task_in.assigned_to).first()
    if not assignee:
        raise ResourceNotFoundException(f"Assigned user with ID {task_in.assigned_to} not found.")

    # Optional business validation: Check if assignee is an employee
    if assignee.role != UserRole.EMPLOYEE:
        raise BadRequestException("Tasks can only be assigned to users with the EMPLOYEE role.")

    db_task = Task(
        title=task_in.title,
        description=task_in.description,
        priority=task_in.priority,
        due_date=task_in.due_date,
        assigned_to=task_in.assigned_to,
        created_by=creator_id,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_tasks(
    db: Session,
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
    query = db.query(Task)

    # Role check: Employee sees only their own assigned tasks
    if user.role == UserRole.EMPLOYEE:
        query = query.filter(Task.assigned_to == user.id)

    # Filters
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)

    # Dynamic Sorting
    if sort_by:
        # Check if the sort_by column is valid on the Task model
        if hasattr(Task, sort_by):
            query = query.order_by(getattr(Task, sort_by).asc())
        else:
            raise BadRequestException(f"Invalid sort column: {sort_by}")
    else:
        # Default sort by created_at descending
        query = query.order_by(Task.created_at.desc())

    # Pagination
    return query.offset(skip).limit(limit).all()


def get_task_by_id(db: Session, task_id: int, user: User) -> Task:
    """
    Retrieves a single task by ID. Performs ownership validation for Employees.
    """
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise ResourceNotFoundException(f"Task with ID {task_id} not found.")

    # Ownership Check
    if user.role == UserRole.EMPLOYEE and db_task.assigned_to != user.id:
        raise AuthorizationException("You are not authorized to view this task.")

    return db_task


def update_task(
    db: Session, task_id: int, task_update: TaskUpdate | TaskUpdateStatus, user: User
) -> Task:
    """
    Updates a task. Admin can update any field; Employee can only update status.
    """
    db_task = get_task_by_id(db, task_id, user)

    update_data = task_update.model_dump(exclude_unset=True)

    # Enforce update constraints for Employee
    if user.role == UserRole.EMPLOYEE:
        # Only status field is allowed for employees
        invalid_keys = [k for k in update_data.keys() if k != "status"]
        if invalid_keys:
            raise AuthorizationException("Employees are only permitted to update the task status.")

    # Apply changes
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: int, user: User) -> None:
    """
    Deletes a task. Admin only (checked at route level, but enforced here too).
    """
    if user.role != UserRole.ADMIN:
        raise AuthorizationException("Only administrators can delete tasks.")

    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise ResourceNotFoundException(f"Task with ID {task_id} not found.")

    db.delete(db_task)
    db.commit()
