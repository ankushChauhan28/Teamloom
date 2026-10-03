from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    AuthenticationException,
    AuthorizationException,
    BadRequestException,
    InvalidCredentialsException,
    ResourceNotFoundException,
    UserAlreadyExistsException,
)
from app.core.scheduler import shutdown_scheduler, start_scheduler
from app import models as _models  # noqa: F401 - Register all SQLAlchemy models at startup
from app.routes import analytics, auth, leaves, tasks, users

# Configure application logging (drives level via LOG_LEVEL setting and ensures app.* loggers output to stdout)
logging_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
root_logger = logging.getLogger()
root_logger.setLevel(logging_level)
if not root_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    root_logger.addHandler(handler)
logging.getLogger("app").setLevel(logging_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Teamloom API",
    description="A clean, modular FastAPI backend for portfolio and learning demonstration.",
    version="1.0.0",
    lifespan=lifespan,
)

# Explicit CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Register routes
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(leaves.router)
app.include_router(analytics.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Teamloom API", "docs_url": "/docs"}


# Centralized Exception Handlers
@app.exception_handler(ResourceNotFoundException)
def resource_not_found_handler(request: Request, exc: ResourceNotFoundException):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.message})


@app.exception_handler(UserAlreadyExistsException)
def user_already_exists_handler(request: Request, exc: UserAlreadyExistsException):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.message})


@app.exception_handler(InvalidCredentialsException)
def invalid_credentials_handler(request: Request, exc: InvalidCredentialsException):
    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": exc.message})


@app.exception_handler(AuthenticationException)
def authentication_exception_handler(request: Request, exc: AuthenticationException):
    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": exc.message})


@app.exception_handler(AuthorizationException)
def authorization_exception_handler(request: Request, exc: AuthorizationException):
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": exc.message})


@app.exception_handler(BadRequestException)
def bad_request_handler(request: Request, exc: BadRequestException):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.message})


@app.exception_handler(AppException)
def app_exception_handler(request: Request, exc: AppException):
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = getattr(exc, "detail", getattr(exc, "message", "An internal server error occurred."))
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )
