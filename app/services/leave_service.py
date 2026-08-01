from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
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


async def review_leave_request(
    db: AsyncSession, leave_id: int, review_in: LeaveUpdateStatus, reviewer_id: int
) -> LeaveRequest:
    """
    Approves or rejects a leave request. Admin only (checked at route level).
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

    # Enforce reviewed_by setting
    db_leave.status = review_in.status
    db_leave.reviewed_by = reviewer_id

    await db.commit()
    await db.refresh(db_leave)
    return db_leave
