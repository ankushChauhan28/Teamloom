from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus


async def create_leave_request(
    db: AsyncSession, leave_in: LeaveCreate, employee_id: int
) -> LeaveRequest:
    """
    Submits a leave request. Employees create their own.
    """
    # Business validation: end date cannot be before start date
    if leave_in.end_date < leave_in.start_date:
        raise BadRequestException("End date cannot be prior to start date.")

    db_leave = LeaveRequest(
        employee_id=employee_id,
        reason=leave_in.reason,
        start_date=leave_in.start_date,
        end_date=leave_in.end_date,
        status=LeaveStatus.PENDING,
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
) -> list[LeaveRequest]:
    """
    List leave requests. Admin sees all; Employee sees only their own.
    Supports filtering by status, dynamic column sorting, and pagination.
    """
    stmt = select(LeaveRequest)

    if user.role == UserRole.EMPLOYEE:
        stmt = stmt.where(LeaveRequest.employee_id == user.id)

    if status:
        stmt = stmt.where(LeaveRequest.status == status)

    # Dynamic Sorting
    if sort_by:
        if hasattr(LeaveRequest, sort_by):
            stmt = stmt.order_by(getattr(LeaveRequest, sort_by).asc())
        else:
            raise BadRequestException(f"Invalid sort column: {sort_by}")
    else:
        # Default sort by created_at descending
        stmt = stmt.order_by(LeaveRequest.created_at.desc())

    # Pagination
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_team_leave_requests(
    db: AsyncSession,
    user: User,
    status: LeaveStatus | None = LeaveStatus.PENDING,
    sort_by: str | None = None,
    skip: int = 0,
    limit: int = 10,
) -> list[LeaveRequest]:
    """
    Lists leave requests submitted by any of the current user's direct reports.
    Defaults to PENDING status first. Returns an empty list if the user has no direct reports.
    """
    reports_stmt = select(User.id).where(User.manager_id == user.id)
    reports_res = await db.execute(reports_stmt)
    report_ids = reports_res.scalars().all()

    if not report_ids:
        return []

    stmt = select(LeaveRequest).where(LeaveRequest.employee_id.in_(report_ids))

    if status:
        stmt = stmt.where(LeaveRequest.status == status)

    if sort_by and hasattr(LeaveRequest, sort_by):
        stmt = stmt.order_by(getattr(LeaveRequest, sort_by).asc())
    else:
        stmt = stmt.order_by(LeaveRequest.created_at.desc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def review_leave_request(
    db: AsyncSession, leave_id: int, review_in: LeaveUpdateStatus, reviewer: User
) -> LeaveRequest:
    """
    Approves or rejects a leave request.
    Accessible by Admin OR the direct manager of the applicant employee.
    """
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    db_leave = result.scalar_one_or_none()
    if not db_leave:
        raise ResourceNotFoundException(f"Leave request with ID {leave_id} not found.")

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

    # Fetch applicant employee to check manager_id
    res_emp = await db.execute(select(User).where(User.id == db_leave.employee_id))
    applicant = res_emp.scalar_one_or_none()

    is_admin = (reviewer.role == UserRole.ADMIN)
    is_direct_manager = (applicant is not None and applicant.manager_id == reviewer.id)

    if not (is_admin or is_direct_manager):
        raise AuthorizationException("You do not have permission to review this leave request.")

    # Enforce reviewed_by setting
    db_leave.status = review_in.status
    db_leave.reviewed_by = reviewer.id

    await db.commit()
    await db.refresh(db_leave)
    return db_leave
