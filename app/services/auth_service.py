from sqlalchemy.orm import Session
import jwt
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserLogin
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_refresh_token
)
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    AuthenticationException
)

def register_user(db: Session, user_in: UserCreate) -> User:
    """
    Registers a new user. Default role is EMPLOYEE.
    """
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise UserAlreadyExistsException("A user with this email already exists.")
    
    hashed_pwd = hash_password(user_in.password)
    db_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=hashed_pwd,
        role=UserRole.EMPLOYEE
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, login_in: UserLogin) -> User:
    """
    Authenticates a user by checking email and verifying password.
    """
    user = db.query(User).filter(User.email == login_in.email).first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise InvalidCredentialsException("Incorrect email or password.")
    return user

def refresh_access_token(db: Session, refresh_token: str) -> dict:
    """
    Exchanges a valid refresh token for a new access token.
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
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise AuthenticationException("User not found.")
        
    new_access_token = create_access_token(email=user.email, role=user.role.value)
    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
