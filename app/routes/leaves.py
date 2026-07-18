from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.leave import LeaveStatus
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus, LeaveRead
from app.services import leave_service
from app.core.security import get_current_user, require_role

router = APIRouter(prefix="/leaves", tags=["Leaves"])

@router.post("/", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
def create_leave(
    leave_in: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a leave request. Accessible by any logged-in user (employee_id matches own ID).
    """
    return leave_service.create_leave_request(db=db, leave_in=leave_in, employee_id=current_user.id)

@router.get("/", response_model=List[LeaveRead])
def list_leaves(
    status: Optional[LeaveStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List leave requests. Admin sees all requests (optional status filtering);
    Employees see only their own requests.
    """
    return leave_service.get_leaves(db=db, user=current_user, status=status)

@router.patch("/{id}", response_model=LeaveRead)
def review_leave(
    id: int,
    review_in: LeaveUpdateStatus,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Approve or reject a leave request. Admin only.
    Sets the status and updates the reviewer ID to the current admin's ID.
    """
    return leave_service.review_leave_request(
        db=db,
        leave_id=id,
        review_in=review_in,
        reviewer_id=current_admin.id
    )
