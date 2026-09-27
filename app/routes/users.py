from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationException
from app.core.security import require_password_change_cleared
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    EmployeeCreate,
    EmployeeCreateResponse,
    UserRead,
    UserReportsToUpdate,
    UserUpdate,
)
from app.services import user_service
from app.services.permission_service import (
    check_access_level_dependency,
    populate_user_effective_cache,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
async def get_me(
    current_user: User = Depends(require_password_change_cleared),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the current logged-in user's profile with cached direct reports.
    """
    return await populate_user_effective_cache(current_user, db)


@router.get("/me/reports", response_model=list[UserRead])
async def get_my_direct_reports(
    current_user: User = Depends(require_password_change_cleared),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the list of direct report employees managed by the current user.
    Returns an empty list if the user has no direct reports.
    """
    return await user_service.get_user_direct_reports(db=db, user_id=current_user.id)


@router.get("/{user_id}/direct-reports", response_model=list[UserRead])
async def get_direct_reports_by_user_id(
    user_id: int,
    current_user: User = Depends(require_password_change_cleared),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves direct reports for a specific manager ID.
    Accessible by Tier 1 / Admins or the manager themselves.
    """
    is_admin = getattr(current_user, "access_level", None) == 1 or current_user.role == UserRole.ADMIN
    if not is_admin and current_user.id != user_id:
        raise AuthorizationException("You are not authorized to view this user's direct reports.")
    return await user_service.get_user_direct_reports(db=db, user_id=user_id)


@router.patch("/me", response_model=UserRead)
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(require_password_change_cleared),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the basic profile details of the current logged-in user.
    Only allows updating non-sensitive fields (like full_name, designation).
    """
    return await user_service.update_user_profile(db=db, user=current_user, user_update=user_update)


@router.get("/", response_model=list[UserRead])
async def list_employees(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    List all employees in the system. Accessible by Tier 1 only.
    """
    return await user_service.get_employees(db=db)


@router.post(
    "/employees", response_model=EmployeeCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_employee(
    employee_in: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Add a new employee account. Accessible by Tier 1 only.
    Generates employee_code, temporary password, and sends welcome email.
    Never returns plaintext password in API response.
    """
    new_user, email_sent = await user_service.create_employee(db=db, employee_in=employee_in)
    return EmployeeCreateResponse(
        id=new_user.id,
        full_name=new_user.full_name,
        email=new_user.email,
        employee_code=new_user.employee_code,
        role=new_user.role,
        access_level=new_user.access_level,
        reports_to_id=new_user.reports_to_id,
        designation=new_user.designation,
        must_change_password=new_user.must_change_password,
        created_at=new_user.created_at,
        email_sent=email_sent,
    )


@router.post("/{user_id}/reset-temp-password")
async def reset_employee_temp_password(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Resets an employee's password to a new temporary password and resends email.
    Accessible by Tier 1 only.
    """
    user, email_sent = await user_service.reset_employee_temp_password(
        db=db, target_user_id=user_id
    )
    return {"id": user.id, "email_sent": email_sent}


@router.patch("/{user_id}/reports-to", response_model=UserRead)
async def set_user_reports_to(
    user_id: int,
    reports_to_in: UserReportsToUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Set or update a user's reports-to supervisor. Accessible by Tier 1 only.
    """
    return await user_service.set_user_reports_to(
        db=db, target_user_id=user_id, reports_to_id=reports_to_in.reports_to_id
    )


@router.patch("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Deactivates a user account (is_active = False). Accessible by Tier 1 only.
    An admin cannot deactivate their own account.
    """
    return await user_service.deactivate_user(
        db=db, current_admin_id=current_admin.id, target_user_id=user_id
    )


@router.patch("/{user_id}/reactivate", response_model=UserRead)
async def reactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Reactivates a user account (is_active = True). Accessible by Tier 1 only.
    """
    return await user_service.reactivate_user(db=db, target_user_id=user_id)


