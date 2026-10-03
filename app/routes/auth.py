import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_user,
    oauth2_scheme,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import PasswordChange, Token, UserLogin, UserRead
from app.services import auth_service
from app.services.permission_service import populate_user_effective_cache

router = APIRouter(prefix="/auth", tags=["Authentication"])


def extract_client_ip(request: Request) -> str:
    """
    Extracts client IP address:
    - Only trusts X-Forwarded-For if request.client.host is in TRUSTED_PROXY_IPS.
    - Otherwise, falls back strictly to the direct connection IP (request.client.host).
    """
    client_host = request.client.host if request.client and request.client.host else "127.0.0.1"
    if client_host in settings.TRUSTED_PROXY_IPS:
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
    return client_host


def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    """
    Sets the refresh_token as an httpOnly, SameSite=Lax cookie.
    """
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
        path="/auth",
    )


@router.post("/login", response_model=Token)
async def login(
    login_in: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Verifies user credentials, enforces IP rate limiting and account lockout,
    issues access token in body and refresh token in httpOnly cookie.
    Caches direct reports in the returned user payload.
    """
    if not isinstance(rate_limiter, RateLimiter):
        rate_limiter = get_rate_limiter()

    client_ip = extract_client_ip(request)
    rate_result = await rate_limiter.check_and_increment(f"login:{client_ip}")
    if not rate_result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(rate_result.retry_after_seconds)},
        )

    user = await auth_service.authenticate_user(db=db, login_in=login_in)
    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)
    set_refresh_token_cookie(response, refresh_token)
    user_read = await populate_user_effective_cache(user, db)
    return Token(
        access_token=access_token,
        token_type="bearer",
        must_change_password=user.must_change_password,
        user=user_read,
    )


@router.post("/swagger-login", response_model=Token, include_in_schema=False)
async def swagger_login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Form-data endpoint specifically for Swagger UI's 'Authorize' button authentication.
    """
    if not isinstance(rate_limiter, RateLimiter):
        rate_limiter = get_rate_limiter()

    client_ip = extract_client_ip(request)
    rate_result = await rate_limiter.check_and_increment(f"login:{client_ip}")
    if not rate_result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(rate_result.retry_after_seconds)},
        )

    mode = "admin" if "@" in form_data.username else "employee"
    login_in = UserLogin(identifier=form_data.username, password=form_data.password, mode=mode)
    user = await auth_service.authenticate_user(db=db, login_in=login_in)
    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)
    set_refresh_token_cookie(response, refresh_token)
    user_read = await populate_user_effective_cache(user, db)
    return Token(
        access_token=access_token,
        token_type="bearer",
        must_change_password=user.must_change_password,
        user=user_read,
    )


@router.post("/refresh", response_model=Token)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a valid refresh token cookie for a new access token and rotates the refresh token cookie.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise AuthenticationException("Refresh token cookie missing.")

    new_access_token, new_refresh_token = await auth_service.refresh_access_token(
        db=db, refresh_token=refresh_token
    )
    set_refresh_token_cookie(response, new_refresh_token)
    return Token(access_token=new_access_token, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Revokes the access token and (if present) the refresh_token in database,
    and clears the httpOnly refresh_token cookie.
    Requires a valid access token in Authorization: Bearer header.
    """
    try:
        decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("Access token has expired.")
    except jwt.InvalidTokenError:
        raise AuthenticationException("Invalid access token.")

    # Always revoke the access token
    await auth_service.revoke_token(db=db, token=token)

    # Revoke the refresh token cookie if present
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await auth_service.revoke_token(db=db, token=refresh_token)

    response.delete_cookie(key="refresh_token", path="/auth")
    return {"message": "Logged out successfully"}


@router.post("/change-password", response_model=UserRead)
async def change_password(
    pwd_in: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Changes current user's password and clears must_change_password flag.
    Requires authentication (allows users with pending password change).
    """
    return await auth_service.change_password(db=db, user=current_user, pwd_in=pwd_in)
