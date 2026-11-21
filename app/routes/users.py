from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_invite_email, send_password_reset_email
from app.core.exceptions import AuthorizationException
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.core.security import require_password_change_cleared
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    EmployeeCreate,
    EmployeeCreateResponse,
    ResendInviteResponse,
    RevokeInviteResponse,
    SendPasswordResetResponse,
    UserDeactivateRequest,
    UserRead,
    UserReportsToUpdate,
    UserUpdate,
)
from app.services import user_service
from app.services.common import get_scoped_or_404
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
    response: Response,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_password_change_cleared),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the list of direct report employees managed by the current user.
    Returns an empty list if the user has no direct reports.
    """
    reports, total_count = await user_service.get_user_direct_reports(
        db=db,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        return_total=True,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return reports


@router.get("/{user_id}/direct-reports", response_model=list[UserRead])
async def get_direct_reports_by_user_id(
    user_id: int,
    response: Response,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_password_change_cleared),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves direct reports for a specific supervisor user ID.
    Accessible by Tier 1 / Admins or the supervisor themselves.
    """
    is_admin = getattr(current_user, "access_level", None) == 1 or current_user.role == UserRole.ADMIN
    if not is_admin and current_user.id != user_id:
        raise AuthorizationException("You are not authorized to view this user's direct reports.")

    # If admin, ensure target user belongs to admin's organization
    if is_admin:
        await get_scoped_or_404(
            db=db,
            model=User,
            id_val=user_id,
            organization_id=current_user.organization_id,
            error_msg="User not found.",
        )

    reports, total_count = await user_service.get_user_direct_reports(
        db=db,
        user_id=user_id,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        return_total=True,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return reports


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
    response: Response,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    List all employees in the admin's organization. Accessible by Tier 1 only.
    """
    employees, total_count = await user_service.get_employees(
        db=db,
        organization_id=current_admin.organization_id,
        skip=skip,
        limit=limit,
        return_total=True,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return employees


@router.post(
    "/employees", response_model=EmployeeCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_employee(
    employee_in: EmployeeCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Add a new employee account. Accessible by Tier 1 only.
    Generates employee_code, sends invite email via background task.
    Never returns plaintext password in API response.
    """
    invite_key = f"invite:admin:{current_admin.id}"
    invite_res = await rate_limiter.check_and_increment(
        invite_key, settings.INVITE_RATE_LIMIT_PER_ADMIN, settings.INVITE_RATE_LIMIT_WINDOW_SECONDS
    )
    if not invite_res.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many invitations sent.",
            headers={"Retry-After": str(invite_res.retry_after_seconds)},
        )

    new_user, raw_token = await user_service.create_employee(
        db=db,
        employee_in=employee_in,
        organization_id=current_admin.organization_id,
    )

    background_tasks.add_task(
        send_invite_email,
        email=new_user.email,
        full_name=new_user.full_name,
        employee_code=new_user.employee_code,
        token=raw_token,
    )

    return EmployeeCreateResponse(
        id=new_user.id,
        full_name=new_user.full_name,
        email=new_user.email,
        employee_code=new_user.employee_code,
        role=new_user.role,
        access_level=new_user.access_level,
        reports_to_id=new_user.reports_to_id,
        designation=new_user.designation,
        invitation_status=new_user.invitation_status,
        delivery_queued=True,
        created_at=new_user.created_at,
    )


@router.post("/{user_id}/resend-invite", response_model=ResendInviteResponse)
async def resend_invite(
    user_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    # Rate limit: per target user (3/hr) + per admin (30/hr)
    user_key = f"resend_invite:user:{user_id}"
    admin_key = f"resend_invite:admin:{current_admin.id}"
    user_res = await rate_limiter.check_and_increment(user_key, settings.RESEND_INVITE_PER_USER_LIMIT, settings.RESEND_INVITE_WINDOW_SECONDS)
    if not user_res.allowed:
        raise HTTPException(429, "Too many resend attempts for this user.", headers={"Retry-After": str(user_res.retry_after_seconds)})
    admin_res = await rate_limiter.check_and_increment(admin_key, settings.RESEND_INVITE_PER_ADMIN_LIMIT, settings.RESEND_INVITE_WINDOW_SECONDS)
    if not admin_res.allowed:
        raise HTTPException(429, "Too many invite resends.", headers={"Retry-After": str(admin_res.retry_after_seconds)})
    user, raw_token = await user_service.resend_invite(db=db, target_user_id=user_id, organization_id=current_admin.organization_id)
    background_tasks.add_task(send_invite_email, email=user.email, full_name=user.full_name, employee_code=user.employee_code, token=raw_token)
    return ResendInviteResponse()


@router.post("/{user_id}/revoke-invite", response_model=RevokeInviteResponse)
async def revoke_invite(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    await user_service.revoke_invite(db=db, target_user_id=user_id, organization_id=current_admin.organization_id)
    return RevokeInviteResponse()


@router.post("/{user_id}/send-password-reset", response_model=SendPasswordResetResponse)
async def send_password_reset(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    user_key = f"send_reset:user:{user_id}"
    admin_key = f"send_reset:admin:{current_admin.id}"
    u_res = await rate_limiter.check_and_increment(user_key, settings.SEND_RESET_PER_USER_LIMIT, settings.SEND_RESET_WINDOW_SECONDS)
    if not u_res.allowed:
        raise HTTPException(429, "Too many reset requests for this user.", headers={"Retry-After": str(u_res.retry_after_seconds)})
    a_res = await rate_limiter.check_and_increment(admin_key, settings.SEND_RESET_PER_ADMIN_LIMIT, settings.SEND_RESET_WINDOW_SECONDS)
    if not a_res.allowed:
        raise HTTPException(429, "Too many password reset sends.", headers={"Retry-After": str(a_res.retry_after_seconds)})
    user, raw_token = await user_service.send_password_reset_to_employee(db=db, target_user_id=user_id, organization_id=current_admin.organization_id)
    background_tasks.add_task(send_password_reset_email, email=user.email, full_name=user.full_name, token=raw_token)
    return SendPasswordResetResponse()


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
        db=db,
        target_user_id=user_id,
        reports_to_id=reports_to_in.reports_to_id,
        organization_id=current_admin.organization_id,
    )


@router.patch("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: int,
    deactivate_in: UserDeactivateRequest | None = Body(None),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(check_access_level_dependency(1)),
):
    """
    Deactivates a user account (is_active = False). Accessible by Tier 1 only.
    An admin cannot deactivate their own account.
    """
    return await user_service.deactivate_user(
        db=db,
        current_admin_id=current_admin.id,
        target_user_id=user_id,
        organization_id=current_admin.organization_id,
        deactivate_in=deactivate_in,
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
    return await user_service.reactivate_user(
        db=db,
        target_user_id=user_id,
        organization_id=current_admin.organization_id,
    )
