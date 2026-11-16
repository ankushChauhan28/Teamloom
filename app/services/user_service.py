import asyncio
import logging
import secrets
import string
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    BadRequestException,
    SupervisorDeactivationConflictException,
    UserAlreadyExistsException,
)
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.user import EmployeeCreate, UserDeactivateRequest, UserUpdate
from app.services.common import get_scoped_or_404

logger = logging.getLogger(__name__)


async def update_user_profile(db: AsyncSession, user: User, user_update: UserUpdate) -> User:
    """
    Updates the profile of the target user.
    """
    updated = False
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
        updated = True
    if user_update.designation is not None:
        user.designation = user_update.designation
        updated = True

    if updated:
        await db.commit()
        await db.refresh(user)
    return user


async def get_employees(
    db: AsyncSession,
    organization_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    return_total: bool = False,
) -> list[User] | tuple[list[User], int]:
    """
    Fetches all users with role EMPLOYEE scoped to the given organization. Admin scope.
    """
    capped_limit = min(max(1, limit), 100)
    conditions = [User.role == UserRole.EMPLOYEE]
    if organization_id is not None:
        conditions.append(User.organization_id == organization_id)

    if return_total:
        stmt = (
            select(User, func.count(User.id).over().label("total_count"))
            .where(*conditions)
            .order_by(User.id.asc())
            .offset(skip)
            .limit(capped_limit)
        )
    else:
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.id.asc())
            .offset(skip)
            .limit(capped_limit)
        )
    result = await db.execute(stmt)

    if return_total:
        rows = result.all()
        if rows:
            employees = [row[0] for row in rows]
            total_count = int(rows[0][1])
        else:
            employees = []
            if skip == 0:
                total_count = 0
            else:
                count_stmt = select(func.count(User.id)).where(*conditions)
                total_count = (await db.execute(count_stmt)).scalar() or 0
        return employees, total_count

    return list(result.scalars().all())


def _generate_next_employee_code(db: AsyncSession | None = None) -> str:
    """
    Generates a cryptographically secure, random 10-digit numeric User ID
    formatted as a zero-padded string (e.g. '0481927361').
    """
    return f"{secrets.randbelow(10**10):010d}"


def _generate_temp_password(length: int = 14) -> str:
    """
    Generates a cryptographically secure random temporary password containing
    upper, lower, digits, and punctuation characters.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    for _ in range(length - 4):
        pwd.append(secrets.choice(alphabet))
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


async def create_employee(
    db: AsyncSession,
    employee_in: EmployeeCreate,
    organization_id: int | None = None,
) -> tuple[User, str]:
    """
    Creates a new employee account:
    - Verifies email uniqueness (case-insensitive).
    - Resolves organization_id.
    - Validates reports_to_id belongs to the same organization if provided.
    - Generates 10-digit random numeric User ID with savepoint-based retry loop for collision safety.
    - Generates temporary password via secrets module and hashes it off the event loop.
    - Sets must_change_password = True.
    - Sets is_email_verified = True (admin-created employees do not require email verification).
    - Returns tuple of (created_user, temp_password).
    """
    norm_email = employee_in.email.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == norm_email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise UserAlreadyExistsException("A user with this email address already exists.")

    if organization_id is None:
        org_res = await db.execute(
            select(Organization.id).where(Organization.is_internal.is_(True)).limit(1)
        )
        org_id = org_res.scalar_one_or_none()
        if org_id is None:
            fallback_res = await db.execute(select(Organization.id).limit(1))
            org_id = fallback_res.scalar_one_or_none()
        if org_id is None:
            default_org = Organization(
                name="Internal / free forever",
                status="active",
                is_internal=True,
            )
            db.add(default_org)
            await db.flush()
            org_id = default_org.id
        organization_id = org_id

    if employee_in.reports_to_id is not None:
        await get_scoped_or_404(
            db=db,
            model=User,
            id_val=employee_in.reports_to_id,
            organization_id=organization_id,
            error_msg="Reports-to supervisor user not found.",
        )

    temp_password = _generate_temp_password()
    hashed_pwd = await asyncio.to_thread(hash_password, temp_password)

    max_attempts = 10
    new_user = None
    for attempt in range(max_attempts):
        emp_code = _generate_next_employee_code(db)
        try:
            async with db.begin_nested():
                new_user = User(
                    full_name=employee_in.full_name,
                    email=norm_email,
                    hashed_password=hashed_pwd,
                    role=UserRole.EMPLOYEE,
                    access_level=employee_in.access_level or 3,
                    reports_to_id=employee_in.reports_to_id,
                    designation=employee_in.designation,
                    employee_code=emp_code,
                    must_change_password=True,
                    is_email_verified=True,
                    email_verified_at=datetime.now(UTC),
                    organization_id=organization_id,
                )
                db.add(new_user)
                await db.flush()
            await db.commit()
            await db.refresh(new_user)
            break

        except IntegrityError as exc:
            logger.warning(
                f"User ID collision on attempt {attempt + 1}/{max_attempts} for code {emp_code}: {exc}"
            )
            if attempt == max_attempts - 1:
                raise AppException(
                    message="Failed to generate a unique employee code after multiple attempts — please retry",
                    status_code=500,
                ) from exc
        except Exception:
            await db.rollback()
            if attempt == max_attempts - 1:
                raise

    if new_user is None:
        raise AppException(
            message="Failed to generate a unique employee code after multiple attempts — please retry",
            status_code=500,
        )

    return new_user, temp_password


async def reset_employee_temp_password(
    db: AsyncSession, target_user_id: int, organization_id: int | None = None
) -> tuple[User, str]:
    """
    Resets an employee's password to a new temporary password and sets must_change_password = True.
    Hashes password off the event loop. Returns (user, temp_password). Scoped by organization_id.
    """
    user = await get_scoped_or_404(
        db=db,
        model=User,
        id_val=target_user_id,
        organization_id=organization_id,
        error_msg="User not found.",
    )

    temp_password = _generate_temp_password()
    user.hashed_password = await asyncio.to_thread(hash_password, temp_password)
    user.must_change_password = True
    await db.commit()
    await db.refresh(user)

    return user, temp_password


async def set_user_reports_to(
    db: AsyncSession,
    target_user_id: int,
    reports_to_id: int | None,
    organization_id: int | None = None,
) -> User:
    """
    Sets or updates the reports_to_id of target_user_id within the organization.
    Enforces validation rules:
    1. Target user exists in the organization.
    2. Proposed supervisor exists in the same organization (if reports_to_id is not None).
    3. User cannot report to themselves (reports_to_id != target_user_id).
    4. Circular reporting chain detection (walking up the chain from proposed supervisor within same org).
    """
    target_user = await get_scoped_or_404(
        db=db,
        model=User,
        id_val=target_user_id,
        organization_id=organization_id,
        error_msg="User not found.",
    )

    if reports_to_id is None:
        target_user.reports_to_id = None
        await db.commit()
        await db.refresh(target_user)
        return target_user

    if reports_to_id == target_user_id:
        raise BadRequestException("A user cannot report to themselves.")

    org_to_check = organization_id if organization_id is not None else target_user.organization_id
    proposed_supervisor = await get_scoped_or_404(
        db=db,
        model=User,
        id_val=reports_to_id,
        organization_id=org_to_check,
        error_msg="Reports-to supervisor user not found.",
    )

    # Cycle detection: walk up the chain starting from proposed_supervisor
    curr_supervisor = proposed_supervisor
    visited_ids = {target_user_id}
    while curr_supervisor:
        if curr_supervisor.id in visited_ids:
            raise BadRequestException("Circular reporting hierarchy is not allowed.")
        visited_ids.add(curr_supervisor.id)
        if curr_supervisor.reports_to_id is None:
            break
        if curr_supervisor.reports_to_id == target_user_id:
            raise BadRequestException("Circular reporting hierarchy is not allowed.")
        res = await db.execute(
            select(User).where(
                User.id == curr_supervisor.reports_to_id,
                User.organization_id == target_user.organization_id,
            )
        )
        curr_supervisor = res.scalar_one_or_none()

    target_user.reports_to_id = reports_to_id
    await db.commit()
    await db.refresh(target_user)
    return target_user


async def get_user_direct_reports(
    db: AsyncSession,
    user_id: int,
    organization_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    return_total: bool = False,
) -> list[User] | tuple[list[User], int]:
    """
    Retrieves all active users where reports_to_id == user_id within the organization.
    """
    capped_limit = min(max(1, limit), 100)
    conditions = [User.reports_to_id == user_id, User.is_active.is_(True)]
    if organization_id is not None:
        conditions.append(User.organization_id == organization_id)

    if return_total:
        stmt = (
            select(User, func.count(User.id).over().label("total_count"))
            .where(*conditions)
            .order_by(User.full_name.asc(), User.id.asc())
            .offset(skip)
            .limit(capped_limit)
        )
    else:
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.full_name.asc(), User.id.asc())
            .offset(skip)
            .limit(capped_limit)
        )
    result = await db.execute(stmt)

    if return_total:
        rows = result.all()
        if rows:
            reports = [row[0] for row in rows]
            total_count = int(rows[0][1])
        else:
            reports = []
            if skip == 0:
                total_count = 0
            else:
                count_stmt = select(func.count(User.id)).where(*conditions)
                total_count = (await db.execute(count_stmt)).scalar() or 0
        return reports, total_count

    return list(result.scalars().all())


async def deactivate_user(
    db: AsyncSession,
    current_admin_id: int,
    target_user_id: int,
    organization_id: int | None = None,
    deactivate_in: UserDeactivateRequest | None = None,
) -> User:
    """
    Deactivates a user account (is_active = False).
    Admin cannot deactivate their own account.
    If the user has active direct reports, requires explicit reassignment for all of them
    (or a default_new_manager_id, or explicit null = no manager).
    If any active direct reports are unresolved, raises SupervisorDeactivationConflictException (HTTP 409).
    All reassignments and deactivation occur in a single atomic database transaction.
    """
    if current_admin_id == target_user_id:
        raise BadRequestException("An admin cannot deactivate their own account.")

    target_user = await get_scoped_or_404(
        db=db,
        model=User,
        id_val=target_user_id,
        organization_id=organization_id,
        error_msg="User not found.",
    )

    # Query all active direct reports within the same organization
    report_conditions = [
        User.reports_to_id == target_user_id,
        User.is_active.is_(True),
    ]
    if target_user.organization_id is not None:
        report_conditions.append(User.organization_id == target_user.organization_id)

    reports_stmt = select(User).where(*report_conditions).order_by(User.id.asc())
    active_reports = list((await db.execute(reports_stmt)).scalars().all())
    active_reports_dict = {report.id: report for report in active_reports}

    # Determine default reassignment (distinguishing 'field not provided' from 'explicitly null')
    has_default = (
        deactivate_in is not None
        and "default_new_manager_id" in deactivate_in.model_fields_set
    )
    default_manager_id = deactivate_in.default_new_manager_id if has_default else None

    raw_reassignments = (
        deactivate_in.reassignments
        if deactivate_in and deactivate_in.reassignments is not None
        else {}
    )

    # Validate that all subordinates specified in raw_reassignments are active direct reports
    for sub_id in raw_reassignments:
        if sub_id not in active_reports_dict:
            # Check if user exists in the org (raises 404 if not found or cross-org)
            await get_scoped_or_404(
                db=db,
                model=User,
                id_val=sub_id,
                organization_id=target_user.organization_id,
                error_msg="Subordinate user not found.",
            )
            raise BadRequestException(
                f"User {sub_id} is not an active direct report of the user being deactivated."
            )

    # Resolve mapping for every active direct report
    unresolved = []
    resolved_mapping: dict[int, int | None] = {}
    for report in active_reports:
        if report.id in raw_reassignments:
            resolved_mapping[report.id] = raw_reassignments[report.id]
        elif has_default:
            resolved_mapping[report.id] = default_manager_id
        else:
            unresolved.append(
                {
                    "id": report.id,
                    "full_name": report.full_name,
                    "designation": report.designation,
                }
            )

    if unresolved:
        raise SupervisorDeactivationConflictException(
            message="Cannot deactivate user with active direct reports. Please reassign subordinates.",
            unresolved_subordinates=unresolved,
        )

    # Validate every new manager in resolved_mapping
    managers_cache: dict[int, User] = {}
    for sub_id, new_mgr_id in resolved_mapping.items():
        if new_mgr_id is None:
            continue

        if new_mgr_id == sub_id:
            raise BadRequestException("A user cannot report to themselves.")

        if new_mgr_id == target_user_id:
            raise BadRequestException("Cannot assign subordinate to the user being deactivated.")

        if new_mgr_id not in managers_cache:
            mgr = await get_scoped_or_404(
                db=db,
                model=User,
                id_val=new_mgr_id,
                organization_id=target_user.organization_id,
                error_msg="Reports-to supervisor user not found.",
            )
            if not mgr.is_active:
                raise BadRequestException(f"Proposed supervisor (ID: {new_mgr_id}) is inactive.")
            managers_cache[new_mgr_id] = mgr

    # Cycle detection across the new hierarchy graph
    for sub_id, new_mgr_id in resolved_mapping.items():
        if new_mgr_id is None:
            continue

        visited = {sub_id}
        curr = new_mgr_id
        while curr is not None:
            if curr in visited:
                raise BadRequestException("Circular reporting hierarchy is not allowed.")
            visited.add(curr)

            if curr in resolved_mapping:
                curr = resolved_mapping[curr]
            else:
                if curr in managers_cache:
                    curr_user = managers_cache[curr]
                else:
                    res = await db.execute(
                        select(User).where(
                            User.id == curr,
                            User.organization_id == target_user.organization_id,
                        )
                    )
                    curr_user = res.scalar_one_or_none()
                    if curr_user:
                        managers_cache[curr] = curr_user

                if not curr_user or curr_user.reports_to_id is None:
                    break
                curr = curr_user.reports_to_id

    # Apply all reassignments atomically
    for report in active_reports:
        report.reports_to_id = resolved_mapping[report.id]

    target_user.is_active = False

    await db.commit()
    await db.refresh(target_user)
    return target_user


async def reactivate_user(
    db: AsyncSession, target_user_id: int, organization_id: int | None = None
) -> User:
    """
    Reactivates a user account (is_active = True). Scoped by organization_id.
    """
    target_user = await get_scoped_or_404(
        db=db,
        model=User,
        id_val=target_user_id,
        organization_id=organization_id,
        error_msg="User not found.",
    )

    target_user.is_active = True
    await db.commit()
    await db.refresh(target_user)
    return target_user
