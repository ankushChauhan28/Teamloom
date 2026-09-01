import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_employee_welcome_email
from app.core.exceptions import (
    BadRequestException,
    ResourceNotFoundException,
    UserAlreadyExistsException,
)
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import EmployeeCreate, UserUpdate


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


async def get_employees(db: AsyncSession) -> list[User]:
    """
    Fetches all users with role EMPLOYEE. Admin scope.
    """
    result = await db.execute(select(User).where(User.role == UserRole.EMPLOYEE))
    return list(result.scalars().all())


async def _generate_next_employee_code(db: AsyncSession) -> str:
    """
    Finds maximum numerical suffix among existing employee_code values (e.g. EMP-1005 -> 1005)
    and returns EMP-1006. If no codes exist or max <= 1000, starts at EMP-1001.
    """
    result = await db.execute(select(User.employee_code).where(User.employee_code.is_not(None)))
    codes = result.scalars().all()
    max_num = 1000
    for code in codes:
        if code and code.startswith("EMP-"):
            try:
                num = int(code.split("-")[1])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"EMP-{max_num + 1}"


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


async def create_employee(db: AsyncSession, employee_in: EmployeeCreate) -> tuple[User, bool]:
    """
    Creates a new employee account:
    - Verifies email uniqueness.
    - Validates reports_to_id if provided.
    - Generates sequential employee_code (EMP-1001, etc).
    - Generates temporary password via secrets module.
    - Hashes password and sets must_change_password = True.
    - Attempts to send welcome email via SMTP.
    - Returns tuple of (created_user, email_sent_bool).
    """
    result = await db.execute(select(User).where(User.email == employee_in.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise UserAlreadyExistsException("A user with this email address already exists.")

    if employee_in.reports_to_id is not None:
        mgr_res = await db.execute(select(User).where(User.id == employee_in.reports_to_id))
        proposed_mgr = mgr_res.scalar_one_or_none()
        if not proposed_mgr:
            raise ResourceNotFoundException("Reports-to supervisor user not found.")

    emp_code = await _generate_next_employee_code(db)
    temp_password = _generate_temp_password()
    hashed_pwd = hash_password(temp_password)

    new_user = User(
        full_name=employee_in.full_name,
        email=employee_in.email,
        hashed_password=hashed_pwd,
        role=UserRole.EMPLOYEE,
        reports_to_id=employee_in.reports_to_id,
        designation=employee_in.designation,
        employee_code=emp_code,
        must_change_password=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    email_sent = send_employee_welcome_email(
        email=new_user.email,
        full_name=new_user.full_name,
        employee_code=new_user.employee_code,
        temp_password=temp_password,
    )

    return new_user, email_sent


async def reset_employee_temp_password(db: AsyncSession, target_user_id: int) -> tuple[User, bool]:
    """
    Resets an employee's password to a new temporary password and sets must_change_password = True.
    Sends new credentials via email. Never returns plaintext password.
    """
    result = await db.execute(select(User).where(User.id == target_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ResourceNotFoundException("User not found.")

    temp_password = _generate_temp_password()
    user.hashed_password = hash_password(temp_password)
    user.must_change_password = True
    await db.commit()
    await db.refresh(user)

    email_sent = send_employee_welcome_email(
        email=user.email,
        full_name=user.full_name,
        employee_code=user.employee_code,
        temp_password=temp_password,
    )

    return user, email_sent


async def set_user_reports_to(
    db: AsyncSession, target_user_id: int, reports_to_id: int | None
) -> User:
    """
    Sets or updates the reports_to_id of target_user_id.
    Enforces validation rules:
    1. Target user exists.
    2. Proposed supervisor exists (if reports_to_id is not None).
    3. User cannot report to themselves (reports_to_id != target_user_id).
    4. Circular reporting chain detection (walking up the chain from proposed supervisor).
    """
    result = await db.execute(select(User).where(User.id == target_user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise ResourceNotFoundException("User not found.")

    if reports_to_id is None:
        target_user.reports_to_id = None
        await db.commit()
        await db.refresh(target_user)
        return target_user

    if reports_to_id == target_user_id:
        raise BadRequestException("A user cannot report to themselves.")

    result = await db.execute(select(User).where(User.id == reports_to_id))
    proposed_supervisor = result.scalar_one_or_none()
    if not proposed_supervisor:
        raise ResourceNotFoundException("Reports-to supervisor user not found.")

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
        res = await db.execute(select(User).where(User.id == curr_supervisor.reports_to_id))
        curr_supervisor = res.scalar_one_or_none()

    target_user.reports_to_id = reports_to_id
    await db.commit()
    await db.refresh(target_user)
    return target_user


# Backward compatibility alias
set_user_manager = set_user_reports_to


async def get_user_direct_reports(db: AsyncSession, user_id: int) -> list[User]:
    """
    Retrieves all users where reports_to_id == user_id.
    """
    result = await db.execute(
        select(User).where(User.reports_to_id == user_id).order_by(User.full_name.asc())
    )
    return list(result.scalars().all())
