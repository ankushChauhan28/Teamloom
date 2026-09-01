from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationException,
    InvalidCredentialsException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import PasswordChange, UserLogin

# Pre-computed dummy hash to guarantee constant-time bcrypt execution for non-existent users
DUMMY_HASH = hash_password("dummy_password_for_constant_time_verification")


async def authenticate_user(db: AsyncSession, login_in: UserLogin) -> User:
    """
    Authenticates a user by checking employee_code and verifying password.
    Enforces account lockout: 5 consecutive failed attempts lock the account for 15 minutes.
    Responses for non-existent employee, wrong password, or locked account are indistinguishable
    in both HTTP response payload and timing (bcrypt execution runs on all 3 paths).
    """
    result = await db.execute(select(User).where(User.employee_code == login_in.employee_code))
    user = result.scalar_one_or_none()

    generic_error = InvalidCredentialsException("Incorrect employee ID or password.")

    # 1. Non-existent user: run dummy bcrypt & commit to match timing and DB I/O profile
    if not user:
        verify_password(login_in.password, DUMMY_HASH)
        await db.commit()
        raise generic_error

    now = datetime.now(UTC)

    # 2. Check if account is currently locked
    if user.locked_until is not None:
        lock_until = (
            user.locked_until
            if user.locked_until.tzinfo is not None
            else user.locked_until.replace(tzinfo=UTC)
        )
        if lock_until > now:
            # Account is locked: run bcrypt & commit to match timing and DB I/O profile of wrong password path
            verify_password(login_in.password, user.hashed_password)
            await db.commit()
            raise generic_error

    # 3. Verify password
    if not verify_password(login_in.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
        await db.commit()
        raise generic_error

    # 4. Successful login: reset lockout counter and locked_until timestamp
    if user.failed_login_attempts != 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

    return user


async def change_password(db: AsyncSession, user: User, pwd_in: PasswordChange) -> User:
    """
    Validates current password, updates user's password to new_password,
    and clears must_change_password flag to False.
    """
    if not verify_password(pwd_in.current_password, user.hashed_password):
        raise InvalidCredentialsException("Current password is incorrect.")

    user.hashed_password = hash_password(pwd_in.new_password)
    user.must_change_password = False
    await db.commit()
    await db.refresh(user)
    return user


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """
    Exchanges a valid refresh token for a new access token and rotates the refresh token.
    Returns tuple of (new_access_token, new_refresh_token).
    """
    try:
        payload = decode_refresh_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("Refresh token has expired.")
    except jwt.InvalidTokenError:
        raise AuthenticationException("Invalid refresh token.")

    email = payload.get("sub")
    if not email:
        raise AuthenticationException("Invalid refresh token payload.")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationException("User not found.")

    new_access_token = create_access_token(email=user.email, role=user.role.value)
    new_refresh_token = create_refresh_token(email=user.email, role=user.role.value)
    return new_access_token, new_refresh_token
