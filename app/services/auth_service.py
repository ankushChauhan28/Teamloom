import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    BadRequestException,
    InvalidCredentialsException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.email_verification_token import EmailVerificationToken
from app.models.organization import Organization, OrgStatus
from app.models.revoked_token import RevokedToken
from app.models.user import User, UserRole
from app.schemas.user import PasswordChange, SignupRequest, UserLogin

# Pre-computed dummy hash to guarantee constant-time bcrypt execution for non-existent users
DUMMY_HASH = hash_password("dummy_password_for_constant_time_verification")


async def generate_and_store_verification_token(db: AsyncSession, user_id: int) -> str:
    """
    Generates a cryptographically secure 32-byte urlsafe token,
    hashes it via SHA-256, invalidates any existing unused tokens for this user,
    and inserts the new token record with 24-hour expiry into email_verification_tokens.
    Returns the raw unhashed token string to be dispatched in email.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)

    # Invalidate existing unused tokens for this user
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    token_record = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=None,
    )
    db.add(token_record)
    await db.commit()
    return raw_token


async def signup_organization_and_admin(
    db: AsyncSession, signup_in: SignupRequest
) -> tuple[bool, str | None, str | None, str | None]:
    """
    Handles self-serve organization and admin registration (FR-2, A6).
    1. Normalizes and validates email uniqueness (case-insensitive).
    2. Anti-enumeration: if email already exists, runs dummy hash verification and
       returns (True, None, None, None) to avoid revealing account existence.
    3. Creates Organization in 'pending_payment' status.
    4. Creates Tier-1 Admin User (access_level=1, is_email_verified=False).
    5. Generates verification token and returns (True, email, full_name, raw_token)
       for asynchronous email delivery via background tasks.
    """
    norm_email = signup_in.email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == norm_email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()

    if existing_user is not None:
        # Anti-enumeration: execute dummy hash verification to equalize timing
        verify_password(signup_in.password, DUMMY_HASH)
        return True, None, None, None

    # Create Organization
    org = Organization(
        name=signup_in.company_name.strip(),
        status=OrgStatus.PENDING_PAYMENT.value,
        is_internal=False,
    )
    db.add(org)
    await db.flush()

    # Create Tier-1 Admin
    hashed_pwd = hash_password(signup_in.password)
    user = User(
        full_name=signup_in.full_name.strip(),
        email=norm_email,
        hashed_password=hashed_pwd,
        role=UserRole.ADMIN,
        access_level=1,
        is_email_verified=False,
        email_verified_at=None,
        organization_id=org.id,
        employee_code=None,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()

    # Generate verification token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)

    token_record = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=None,
    )
    db.add(token_record)
    await db.commit()
    await db.refresh(user)

    return True, norm_email, user.full_name, raw_token


async def verify_email(db: AsyncSession, token: str) -> User:
    """
    Verifies user email using the provided token (POST /auth/verify-email).
    1. Computes SHA-256 hash of token.
    2. Looks up token record; rejects if not found, already used, or expired.
    3. Generic error returned for all invalid cases.
    4. On success: marks token used_at=now, sets user.is_email_verified=True,
       and email_verified_at=now.
    """
    if not token or not token.strip():
        raise BadRequestException("Invalid or expired verification token.")

    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(UTC)

    stmt = select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    token_record = (await db.execute(stmt)).scalar_one_or_none()

    if not token_record or token_record.used_at is not None:
        raise BadRequestException("Invalid or expired verification token.")

    exp = (
        token_record.expires_at
        if token_record.expires_at.tzinfo is not None
        else token_record.expires_at.replace(tzinfo=UTC)
    )
    if exp < now:
        raise BadRequestException("Invalid or expired verification token.")

    user_stmt = select(User).where(User.id == token_record.user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise BadRequestException("Invalid or expired verification token.")

    token_record.used_at = now
    user.is_email_verified = True
    user.email_verified_at = now
    await db.commit()
    await db.refresh(user)
    return user


async def resend_verification_email(
    db: AsyncSession, email: str
) -> tuple[bool, str | None, str | None, str | None]:
    """
    Resends verification email to an unverified admin (FR-2, anti-enumeration).
    If email does not exist or is already verified, returns generic success without sending email.
    """
    norm_email = email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == norm_email, User.access_level == 1)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None or user.is_email_verified:
        verify_password("dummy_password", DUMMY_HASH)
        return True, None, None, None

    raw_token = await generate_and_store_verification_token(db=db, user_id=user.id)
    return True, norm_email, user.full_name, raw_token


async def authenticate_user(db: AsyncSession, login_in: UserLogin) -> User:
    """
    Authenticates a user based on mode:
    - mode == "admin": look up by lower(trim(identifier)) == lower(users.email) AND access_level == 1.
    - mode == "employee": look up by users.employee_code == identifier.strip() AND access_level > 1.
    Enforces account lockout: 5 consecutive failed attempts lock the account for 15 minutes.
    Enforces email verification for admins (unverified admins receive generic error).
    Responses for wrong credentials, wrong mode, non-existent user, unverified admin, or locked account
    are indistinguishable in both HTTP response payload and timing (bcrypt execution runs on all paths).
    """
    generic_error = InvalidCredentialsException("Incorrect credentials.")

    if login_in.mode == "admin":
        norm_identifier = login_in.identifier.strip().lower()
        stmt = select(User).where(
            func.lower(User.email) == norm_identifier,
            User.access_level == 1,
        )
    else:
        norm_identifier = login_in.identifier.strip()
        stmt = select(User).where(
            User.employee_code == norm_identifier,
            User.access_level > 1,
        )

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # 1. Non-existent user or wrong mode match: run dummy bcrypt & commit to match timing and DB I/O profile
    if not user:
        verify_password(login_in.password, DUMMY_HASH)
        await db.commit()
        raise generic_error

    # 1b. Deactivated user: run bcrypt & commit to match timing and DB I/O profile, return generic error
    if not user.is_active:
        verify_password(login_in.password, user.hashed_password)
        await db.commit()
        raise generic_error

    # 1c. Unverified Admin user: run dummy bcrypt & commit to match timing and DB I/O profile, return generic error
    if login_in.mode == "admin" and not user.is_email_verified:
        verify_password(login_in.password, user.hashed_password)
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


async def revoke_token(db: AsyncSession, token: str) -> None:
    """
    Extracts token_jti and expiration timestamp from JWT payload and inserts it into
    the revoked_tokens table. Handles malformed or already-revoked tokens gracefully and idempotently.
    """
    payload = None
    try:
        payload = decode_access_token(token)
    except Exception:
        pass

    if not payload:
        try:
            payload = decode_refresh_token(token)
        except Exception:
            pass

    if not payload:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return

    jti = payload.get("jti") or hashlib.sha256(token.encode("utf-8")).hexdigest()
    exp = payload.get("exp")

    if exp:
        exp_dt = datetime.fromtimestamp(exp, tz=UTC)
    else:
        exp_dt = datetime.now(UTC) + timedelta(days=7)

    existing = await db.execute(select(RevokedToken).where(RevokedToken.token_jti == jti))
    if existing.scalar_one_or_none() is not None:
        return

    revoked = RevokedToken(token_jti=jti, exp_timestamp=exp_dt)
    db.add(revoked)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """
    Exchanges a valid refresh token for a new access token and rotates the refresh token.
    Checks whether the refresh token has been revoked before issuing new tokens.
    Returns tuple of (new_access_token, new_refresh_token).
    """
    try:
        payload = decode_refresh_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("Refresh token has expired.")
    except jwt.InvalidTokenError:
        raise AuthenticationException("Invalid refresh token.")

    token_jti = payload.get("jti") or hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    revoked_result = await db.execute(
        select(RevokedToken).where(RevokedToken.token_jti == token_jti)
    )
    if revoked_result.scalar_one_or_none() is not None:
        raise AuthenticationException("Refresh token has been revoked.")

    email = payload.get("sub")
    if not email:
        raise AuthenticationException("Invalid refresh token payload.")

    norm_email = email.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == norm_email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationException("User not found.")

    new_access_token = create_access_token(email=user.email, role=user.role.value)
    new_refresh_token = create_refresh_token(email=user.email, role=user.role.value)

    # Revoke old refresh token post-rotation so it cannot be reused
    await revoke_token(db=db, token=refresh_token)

    return new_access_token, new_refresh_token


async def cleanup_expired_revocations(db: AsyncSession) -> int:
    """
    Deletes rows from revoked_tokens where exp_timestamp < current UTC time.
    Returns count of deleted records.
    """
    now = datetime.now(UTC)
    stmt = delete(RevokedToken).where(RevokedToken.exp_timestamp < now)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def cleanup_unverified_signups(db: AsyncSession) -> int:
    """
    Cleans up unverified signups older than 7 days and their organizations (X1, B8).
    Deletes organizations in 'pending_payment' status where the creator admin has remained
    unverified for >= 7 days and no other users exist.
    Cascade deletion cleans up the associated user and email verification tokens.
    Returns the number of deleted unverified organizations/signups.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=7)

    # Find unverified Tier-1 admin users created before the 7-day cutoff
    stmt = select(User).where(
        User.is_email_verified.is_(False),
        User.access_level == 1,
        User.created_at < cutoff,
    )
    unverified_admins = (await db.execute(stmt)).scalars().all()
    deleted_count = 0

    for admin in unverified_admins:
        org_id = admin.organization_id
        if org_id is None:
            await db.delete(admin)
            deleted_count += 1
            continue

        org_stmt = select(Organization).where(Organization.id == org_id)
        org = (await db.execute(org_stmt)).scalar_one_or_none()
        if not org or org.is_internal:
            continue

        # Check if organization is still in pending_payment and has no other users
        users_count_stmt = select(func.count(User.id)).where(User.organization_id == org_id)
        users_count = (await db.execute(users_count_stmt)).scalar() or 0

        if users_count <= 1 and org.status == OrgStatus.PENDING_PAYMENT.value:
            # Delete organization (cascade deletes user and verification tokens)
            await db.delete(org)
            deleted_count += 1

    if deleted_count > 0:
        await db.commit()

    return deleted_count

