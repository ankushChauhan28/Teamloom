import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    LOG_LEVEL: str = "INFO"

    # Email & Verification Configuration (NFR-3)
    EMAIL_BACKEND: str = "auto"  # "auto", "smtp", or "console"
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    EMAIL_VERIFICATION_URL: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_APP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"

    @property
    def verification_base_url(self) -> str:
        return self.EMAIL_VERIFICATION_URL or f"{self.FRONTEND_URL}/verify-email"

    # CORS Origins can be a JSON-formatted list or a comma-separated string
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Trusted Proxy IPs (e.g. Nginx, Cloudflare reverse proxy IPs)
    TRUSTED_PROXY_IPS: list[str] = []

    # Rate Limiting Configuration (Level 1 Dual-Key Limiter)
    RATE_LIMIT_AUTH_ATTEMPTS: int = 10
    RATE_LIMIT_AUTH_WINDOW_SECONDS: int = 900  # 15 minutes
    RATE_LIMIT_IP_CEILING_ATTEMPTS: int = 100
    RATE_LIMIT_IP_CEILING_WINDOW_SECONDS: int = 900  # 15 minutes
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMITER_BACKEND: str = "memory"

    # Slice 4e invite & password-reset rate limits
    INVITE_RATE_LIMIT_PER_ADMIN: int = 30         # invites per admin per hour
    INVITE_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    RESEND_INVITE_PER_USER_LIMIT: int = 3          # resends per target user per hour
    RESEND_INVITE_PER_ADMIN_LIMIT: int = 30
    RESEND_INVITE_WINDOW_SECONDS: int = 3600
    SEND_RESET_PER_USER_LIMIT: int = 5
    SEND_RESET_PER_ADMIN_LIMIT: int = 50
    SEND_RESET_WINDOW_SECONDS: int = 3600
    FORGOT_PASSWORD_COMPOUND_LIMIT: int = 3        # per {IP, email} per 15 min
    FORGOT_PASSWORD_COMPOUND_WINDOW: int = 900
    FORGOT_PASSWORD_IP_LIMIT: int = 20             # per IP per 15 min
    FORGOT_PASSWORD_IP_WINDOW: int = 900
    ACCEPT_INVITE_IP_LIMIT: int = 10
    ACCEPT_INVITE_IP_WINDOW: int = 900
    RESET_PASSWORD_IP_LIMIT: int = 10
    RESET_PASSWORD_IP_WINDOW: int = 900
    INVITE_TOKEN_EXPIRE_HOURS: int = 48
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            try:
                decoded = json.loads(v)
                if isinstance(decoded, list):
                    return decoded
            except json.JSONDecodeError:
                pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("TRUSTED_PROXY_IPS", mode="before")
    @classmethod
    def assemble_trusted_proxy_ips(cls, v: str | list[str] | None) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            try:
                decoded = json.loads(v)
                if isinstance(decoded, list):
                    return decoded
            except json.JSONDecodeError:
                pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


settings = Settings()
