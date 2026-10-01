from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus
from app.services.common import get_scoped_or_404


async def create_leave_request(
    db: AsyncSession,
    leave_in: LeaveCreate,
    employee_id: int,
    organization_id: int | None = None,
) -> LeaveRequest:
    """
    Submits a leave request. Employees create their own.
    """
    # Business validation: end date cannot be before start date
    if leave_in.end_date < leave_in.start_date:
        raise BadRequestException("End date cannot be prior to start date.")

    # Overlap validation: query existing PENDING or APPROVED leave requests for employee
    stmt = select(LeaveRequest).where(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
    )
    result = await db.execute(stmt)
    existing_leaves = result.scalars().all()

    for existing in existing_leaves:
        if leave_in.start_date <= existing.end_date and leave_in.end_date >= existing.start_date:
            raise BadRequestException(
                detail=f"Leave request dates overlap with existing request (ID: {existing.id}). Please choose different dates."
            )

    if organization_id is None:
        user_res = await db.execute(select(User.organization_id).where(User.id == employee_id))
        organization_id = user_res.scalar_one_or_none()

    db_leave = LeaveRequest(
        employee_id=employee_id,
        reason=leave_in.reason,
        start_date=leave_in.start_date,
        end_date=leave_in.end_date,
        status=LeaveStatus.PENDING,
        organization_id=organization_id,
    )
    db.add(db_leave)
    await db.commit()
    await db.refresh(db_leave)
    return db_leave


async def get_leaves(
    db: AsyncSession,
    user: User,
    status: LeaveStatus | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    return_total: bool = False,
) -> list[LeaveRequest] | tuple[list[LeaveRequest], int]:
    """
    List leave requests scoped to the user's organization.
    Admin sees all requests in org; Employee sees only their own.
    Supports filtering by status, deterministic column sorting, and pagination.
    """
    capped_limit = min(max(1, limit), 100)
    conditions = [LeaveRequest.organization_id == user.organization_id]

    # Scoping: Tier 1 sees all in org, others see only their own requests
    is_admin = getattr(user, "access_level", None) == 1 or user.role == UserRole.ADMIN
    if not is_admin:
        conditions.append(LeaveRequest.employee_id == user.id)

    if status:
        conditions.append(LeaveRequest.status == status)

    if return_total:
        stmt = select(LeaveRequest, func.count(LeaveRequest.id).over().label("total_count")).where(*conditions)
    else:
        stmt = select(LeaveRequest).where(*conditions)

    # Dynamic Sorting with secondary deterministic column
    if sort_by:
        if hasattr(LeaveRequest, sort_by):
            stmt = stmt.order_by(getattr(LeaveRequest, sort_by).asc(), LeaveRequest.id.asc())
        else:
            raise BadRequestException(f"Invalid sort column: {sort_by}")
    else:
        # Default sort by created_at descending, then id descending
        stmt = stmt.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())

    # Pagination
    stmt = stmt.offset(skip).limit(capped_limit)
    result = await db.execute(stmt)

    if return_total:
        rows = result.all()
        if rows:
            leaves = [row[0] for row in rows]
            total_count = int(rows[0][1])
        else:
            leaves = []
            if skip == 0:
                total_count = 0
            else:
                count_stmt = select(func.count(LeaveRequest.id)).where(*conditions)
                total_count = (await db.execute(count_stmt)).scalar() or 0
        return leaves, total_count

    return list(result.scalars().all())


async def get_team_leave_requests(
    db: AsyncSession,
    user: User,
    status: LeaveStatus | None = None,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
    return_total: bool = False,
) -> list[LeaveRequest] | tuple[list[LeaveRequest], int]:
    """
    Lists leave requests submitted by any of the current user's direct reports in the same organization.
    Returns all statuses if status is None. Returns an empty list if the user has no direct reports.
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
        LeaveRequest.organization_id == user.organization_id,
        LeaveRequest.employee_id.in_(report_ids),
    ]

    if status:
        conditions.append(LeaveRequest.status == status)

    if return_total:
        stmt = select(LeaveRequest, func.count(LeaveRequest.id).over().label("total_count")).where(*conditions)
    else:
        stmt = select(LeaveRequest).where(*conditions)

    if sort_by and hasattr(LeaveRequest, sort_by):
        stmt = stmt.order_by(getattr(LeaveRequest, sort_by).asc(), LeaveRequest.id.asc())
    else:
        stmt = stmt.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())

    stmt = stmt.offset(skip).limit(capped_limit)
    result = await db.execute(stmt)

    if return_total:
        rows = result.all()
        if rows:
            leaves = [row[0] for row in rows]
            total_count = int(rows[0][1])
        else:
            leaves = []
            if skip == 0:
                total_count = 0
            else:
                count_stmt = select(func.count(LeaveRequest.id)).where(*conditions)
                total_count = (await db.execute(count_stmt)).scalar() or 0
        return leaves, total_count

    return list(result.scalars().all())


async def review_leave_request(
    db: AsyncSession, leave_id: int, review_in: LeaveUpdateStatus, reviewer: User
) -> LeaveRequest:
    """
    Approves or rejects a leave request scoped to reviewer's organization.
    Accessible by Tier 1 Admin only.
    """
    db_leave = await get_scoped_or_404(
        db=db,
        model=LeaveRequest,
        id_val=leave_id,
        organization_id=reviewer.organization_id,
        error_msg=f"Leave request with ID {leave_id} not found.",
    )

    # Validation: leave request must be in PENDING status
    if db_leave.status != LeaveStatus.PENDING:
        raise BadRequestException(
            "This leave request has already been reviewed and cannot be modified."
        )

    # Validation: only allow APPROVED or REJECTED status transitions
    if review_in.status not in [LeaveStatus.APPROVED, LeaveStatus.REJECTED]:
        raise BadRequestException("Review status must be either APPROVED or REJECTED.")

    # Defense-in-depth: Cannot approve own leave request
    if db_leave.employee_id == reviewer.id:
        raise AuthorizationException("You cannot approve or reject your own leave request.")

    is_admin = getattr(reviewer, "access_level", None) == 1 or reviewer.role == UserRole.ADMIN
    if not is_admin:
        raise AuthorizationException("Only Tier 1 Administrators can review leave requests.")

    # Enforce reviewed_by setting
    db_leave.status = review_in.status
    db_leave.reviewed_by = reviewer.id

    await db.commit()
    await db.refresh(db_leave)
    return db_leave
