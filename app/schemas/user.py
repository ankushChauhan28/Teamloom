from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


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
    access_level: int | None = 3

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class EmployeeCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    employee_code: str
    role: UserRole
    access_level: int = 3
    reports_to_id: int | None = None
    designation: str | None = None
    must_change_password: bool
    is_active: bool = True
    is_email_verified: bool = False
    email_verified_at: datetime | None = None
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
    access_level: int | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    access_level: int = 3
    effective_tier: int = 3
    direct_reports_ids: list[int] = []
    reports_to_id: int | None = None
    designation: str | None = None
    employee_code: str | None = None
    is_email_verified: bool = False
    email_verified_at: datetime | None = None
    must_change_password: bool = False
    is_active: bool = True
    created_at: datetime


UserResponse = UserRead


# Email Verification Schemas
class EmailVerificationRequest(BaseModel):
    token: str


class EmailVerificationResponse(BaseModel):
    message: str
    email: EmailStr
    is_verified: bool


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v
