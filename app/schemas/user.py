from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    designation: str | None = None


class UserReportsToUpdate(BaseModel):
    reports_to_id: int | None = None


class EmployeeCreate(BaseModel):
    full_name: str
    email: EmailStr
    reports_to_id: int | None = None
    designation: str | None = None


class EmployeeCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    employee_code: str
    role: UserRole
    reports_to_id: int | None = None
    designation: str | None = None
    must_change_password: bool
    is_active: bool = True
    created_at: datetime
    email_sent: bool = False


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserLogin(BaseModel):
    employee_code: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False
    user: "UserRead | None" = None


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    email: str | None = None
    role: UserRole | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    reports_to_id: int | None = None
    designation: str | None = None
    employee_code: str | None = None
    must_change_password: bool = False
    is_active: bool = True
    created_at: datetime


UserResponse = UserRead
