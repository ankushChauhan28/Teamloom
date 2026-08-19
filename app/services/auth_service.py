import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserLogin


async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    Registers a new user. Default role is EMPLOYEE.
    """
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise UserAlreadyExistsException("A user with this email already exists.")

    hashed_pwd = hash_password(user_in.password)
    db_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=hashed_pwd,
        role=UserRole.EMPLOYEE,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def authenticate_user(db: AsyncSession, login_in: UserLogin) -> User:
    """
    Authenticates a user by checking email and verifying password.
    """
    result = await db.execute(select(User).where(User.email == login_in.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise InvalidCredentialsException("Incorrect email or password.")
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
