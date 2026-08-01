from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.schemas.user import Token, TokenRefresh, UserCreate, UserLogin, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registers a new employee user. Role defaults to EMPLOYEE.
    """
    return await auth_service.register_user(db=db, user_in=user_in)


@router.post("/login", response_model=Token)
async def login(login_in: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Verifies user credentials and issues short-lived access and long-lived refresh tokens.
    Expects a JSON body with email and password.
    """
    user = await auth_service.authenticate_user(db=db, login_in=login_in)

    # Generate tokens
    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/swagger-login", response_model=Token, include_in_schema=False)
async def swagger_login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """
    Form-data endpoint specifically for Swagger UI's 'Authorize' button authentication.
    Hidden from the main OpenAPI schema documentation.
    """
    login_in = UserLogin(email=form_data.username, password=form_data.password)
    user = await auth_service.authenticate_user(db=db, login_in=login_in)

    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh(refresh_in: TokenRefresh, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a valid refresh token for a new access token.
    """
    return await auth_service.refresh_access_token(db=db, refresh_token=refresh_in.refresh_token)
