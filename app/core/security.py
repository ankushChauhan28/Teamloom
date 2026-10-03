import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.db.session import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User


def hash_password(password: str) -> str:
    """
    Hashes a password using bcrypt.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a password against its bcrypt hash.
    """
    password_bytes = password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_jwt_token(
    subject: str, role: str, secret_key: str, expires_delta: timedelta, token_type: str
) -> str:
    """
    Generic function to create encoded JWT.
    """
    now = datetime.now(UTC)
    expire = now + expires_delta
    to_encode = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(to_encode, secret_key, algorithm="HS256")


def create_access_token(email: str, role: str, expires_delta: timedelta | None = None) -> str:
    """
    Generates a short-lived access token.
    """
    norm_email = email.strip().lower()
    if expires_delta:
        expire = expires_delta
    else:
        expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    return create_jwt_token(
        subject=norm_email,
        role=role,
        secret_key=settings.JWT_SECRET_KEY,
        expires_delta=expire,
        token_type="access",
    )


def create_refresh_token(email: str, role: str, expires_delta: timedelta | None = None) -> str:
    """
    Generates a long-lived refresh token.
    """
    norm_email = email.strip().lower()
    if expires_delta:
        expire = expires_delta
    else:
        expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    return create_jwt_token(
        subject=norm_email,
        role=role,
        secret_key=settings.JWT_REFRESH_SECRET_KEY,
        expires_delta=expire,
        token_type="refresh",
    )


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.
    """
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token is not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    """
    Decodes and validates a JWT refresh token.
    """
    payload = jwt.decode(token, settings.JWT_REFRESH_SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Token is not a refresh token")
    return payload


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/swagger-login")


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    FastAPI dependency that extracts and validates the user from the Bearer token.
    """
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("Access token has expired.")
    except jwt.InvalidTokenError:
        raise AuthenticationException("Invalid access token.")

    token_jti = payload.get("jti") or hashlib.sha256(token.encode("utf-8")).hexdigest()
    revoked_result = await db.execute(
        select(RevokedToken).where(RevokedToken.token_jti == token_jti)
    )
    if revoked_result.scalar_one_or_none() is not None:
        raise AuthenticationException("Token has been revoked.")

    email = payload.get("sub")
    if not email:
        raise AuthenticationException("Invalid access token payload.")

    norm_email = email.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == norm_email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationException("User not found.")

    return user


async def require_password_change_cleared(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that blocks access if current_user.must_change_password is True.
    Raises AuthorizationException("password_change_required") returning 403.
    """
    if current_user.must_change_password:
        raise AuthorizationException("password_change_required")
    return current_user
