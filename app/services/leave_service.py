from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.leave import LeaveRequest, LeaveStatus
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus
from app.core.exceptions import (
    ResourceNotFoundException,
    AuthorizationException,
    BadRequestException
)

def create_leave_request(
    db: Session,
    leave_in: LeaveCreate,
    employee_id: int
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
        status=LeaveStatus.PENDING
    )
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)
    return db_leave

def get_leaves(
    db: Session,
    user: User,
    status: Optional[LeaveStatus] = None
) -> List[LeaveRequest]:
    """
    List leave requests. Admin sees all; Employee sees only their own.
    """
    query = db.query(LeaveRequest)
    
    if user.role == UserRole.EMPLOYEE:
        query = query.filter(LeaveRequest.employee_id == user.id)
        
    if status:
        query = query.filter(LeaveRequest.status == status)
        
    return query.order_by(LeaveRequest.created_at.desc()).all()

def review_leave_request(
    db: Session,
    leave_id: int,
    review_in: LeaveUpdateStatus,
    reviewer_id: int
) -> LeaveRequest:
    """
    Approves or rejects a leave request. Admin only (checked at route level).
    """
    db_leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not db_leave:
        raise ResourceNotFoundException(f"Leave request with ID {leave_id} not found.")
        
    # Validation: leave request must be in PENDING status
    if db_leave.status != LeaveStatus.PENDING:
        raise BadRequestException("This leave request has already been reviewed and cannot be modified.")

    # Validation: only allow APPROVED or REJECTED status transitions
    if review_in.status not in [LeaveStatus.APPROVED, LeaveStatus.REJECTED]:
        raise BadRequestException("Review status must be either APPROVED or REJECTED.")
        
    # Enforce reviewed_by setting
    db_leave.status = review_in.status
    db_leave.reviewed_by = reviewer_id
    
    db.commit()
    db.refresh(db_leave)
    return db_leave
