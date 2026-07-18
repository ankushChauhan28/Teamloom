from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin, UserRead, Token, TokenRefresh
from app.services import auth_service
from app.core.security import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new employee user. Role defaults to EMPLOYEE.
    """
    return auth_service.register_user(db=db, user_in=user_in)

@router.post("/login", response_model=Token)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    """
    Verifies user credentials and issues short-lived access and long-lived refresh tokens.
    """
    user = auth_service.authenticate_user(db=db, login_in=login_in)
    
    # Generate tokens
    access_token = create_access_token(email=user.email, role=user.role.value)
    refresh_token = create_refresh_token(email=user.email, role=user.role.value)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
def refresh(refresh_in: TokenRefresh, db: Session = Depends(get_db)):
    """
    Exchanges a valid refresh token for a new access token.
    """
    return auth_service.refresh_access_token(db=db, refresh_token=refresh_in.refresh_token)
