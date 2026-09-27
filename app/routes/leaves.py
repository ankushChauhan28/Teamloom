from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_password_change_cleared
from app.db.session import get_db
from app.models.leave import LeaveStatus
from app.models.user import User
from app.schemas.leave import LeaveCreate, LeaveRead, LeaveUpdateStatus
from app.services import leave_service
from app.services.permission_service import check_access_level_dependency

router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.post("/", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
async def create_leave(
    leave_in: LeaveCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    Submit a leave request. Accessible by any logged-in user (employee_id matches own ID).
    """
    return await leave_service.create_leave_request(
        db=db, leave_in=leave_in, employee_id=current_user.id
    )


@router.get("/", response_model=list[LeaveRead])
async def list_leaves(
    status: LeaveStatus | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    List leave requests. Admin sees all requests; Employees see only their own.
    Supports filtering by status, dynamic sorting, and pagination.
    """
    return await leave_service.get_leaves(
        db=db,
        user=current_user,
        status=status,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.get("/team", response_model=list[LeaveRead])
async def list_team_leaves(
    status: LeaveStatus | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    List leave requests submitted by any of the current user's direct reports.
    Returns all statuses if status is None. Returns an empty list if the user has no direct reports.
    """
    return await leave_service.get_team_leave_requests(
        db=db,
        user=current_user,
        status=status,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.patch("/{id}", response_model=LeaveRead)
async def review_leave(
    id: int,
    review_in: LeaveUpdateStatus,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Approve or reject a leave request.
    Accessible by Tier 1 Admin only.
    Sets the status and updates the reviewer ID to the current user's ID.
    """
    return await leave_service.review_leave_request(
        db=db, leave_id=id, review_in=review_in, reviewer=current_admin
    )
