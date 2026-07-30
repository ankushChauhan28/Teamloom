from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus


def create_leave_request(db: Session, leave_in: LeaveCreate, employee_id: int) -> LeaveRequest:
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
    db.commit()
    db.refresh(db_leave)
    return db_leave


def get_leaves(
    db: Session,
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
    query = db.query(LeaveRequest)

    if user.role == UserRole.EMPLOYEE:
        query = query.filter(LeaveRequest.employee_id == user.id)

    if status:
        query = query.filter(LeaveRequest.status == status)

    # Dynamic Sorting
    if sort_by:
        if hasattr(LeaveRequest, sort_by):
            query = query.order_by(getattr(LeaveRequest, sort_by).asc())
        else:
            raise BadRequestException(f"Invalid sort column: {sort_by}")
    else:
        # Default sort by created_at descending
        query = query.order_by(LeaveRequest.created_at.desc())

    # Pagination
    return query.offset(skip).limit(limit).all()


def review_leave_request(
    db: Session, leave_id: int, review_in: LeaveUpdateStatus, reviewer_id: int
) -> LeaveRequest:
    """
    Approves or rejects a leave request. Admin only (checked at route level).
    """
    db_leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
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

    db.commit()
    db.refresh(db_leave)
    return db_leave
