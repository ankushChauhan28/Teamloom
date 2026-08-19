from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.schemas.user import Token, UserCreate, UserLogin, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


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


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registers a new employee user. Role defaults to EMPLOYEE.
    """
    return await auth_service.register_user(db=db, user_in=user_in)


@router.post("/login", response_model=Token)
async def login(
    login_in: UserLogin, response: Response, db: AsyncSession = Depends(get_db)
):
    """
    Verifies user credentials, issues access token in body and refresh token in httpOnly cookie.
    """
    user = await auth_service.authenticate_user(db=db, login_in=login_in)
    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)
    set_refresh_token_cookie(response, refresh_token)
    return Token(access_token=access_token, token_type="bearer")


@router.post("/swagger-login", response_model=Token, include_in_schema=False)
async def swagger_login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Form-data endpoint specifically for Swagger UI's 'Authorize' button authentication.
    """
    login_in = UserLogin(email=form_data.username, password=form_data.password)
    user = await auth_service.authenticate_user(db=db, login_in=login_in)
    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)
    set_refresh_token_cookie(response, refresh_token)
    return Token(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
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
async def logout(response: Response):
    """
    Clears the httpOnly refresh_token cookie.
    """
    response.delete_cookie(key="refresh_token", path="/auth")
    return {"message": "Logged out successfully"}
