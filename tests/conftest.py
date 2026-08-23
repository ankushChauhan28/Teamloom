"""
Pytest Central Configuration & Fixture Registry (conftest.py)

EDUCATIONAL EXPLANATION - ASYNC TEST FIXTURES & ASGI TRANSPORT:
---------------------------------------------------------------
1. Why httpx.AsyncClient & ASGITransport?
   In an asynchronous FastAPI application, `httpx.AsyncClient` coupled with `ASGITransport(app=app)`
   simulates non-blocking HTTP requests against our ASGI app directly inside the asyncio event loop.

2. In-Memory Async SQLite (`sqlite+aiosqlite:///:memory:`):
   Uses `create_async_engine` and `AsyncSession` to execute database queries asynchronously
   during test runs, guaranteeing zero pollution of development database.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole

from unittest.mock import MagicMock, patch

# In-memory SQLite async database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def mock_send_welcome_email() -> AsyncGenerator[MagicMock, None]:
    """
    Autouse Fixture (Scope: Function):
    Automatically mocks send_employee_welcome_email for ALL tests in the suite
    so no real SMTP network connections are ever attempted during pytest execution.
    """
    with patch(
        "app.services.user_service.send_employee_welcome_email",
        return_value=True,
    ) as mock_service_email, patch(
        "app.core.email.send_employee_welcome_email",
        return_value=True,
    ):
        yield mock_service_email


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async Database Session Fixture (Scope: Function)
    Creates fresh schema tables before each test and drops them post-test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    FastAPI AsyncClient Fixture with Async Dependency Override
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """
    Fixture creating a test ADMIN user asynchronously in the test database.
    """
    admin = User(
        full_name="Test System Admin",
        email="admin.test@example.com",
        hashed_password=hash_password("adminpassword123"),
        role=UserRole.ADMIN,
        employee_code="EMP-0001",
        must_change_password=False,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def employee_user(db_session: AsyncSession) -> User:
    """
    Fixture creating a test EMPLOYEE user asynchronously in the test database.
    """
    employee = User(
        full_name="Test John Employee",
        email="employee.test@example.com",
        hashed_password=hash_password("employeepassword123"),
        role=UserRole.EMPLOYEE,
        employee_code="EMP-0002",
        must_change_password=False,
    )
    db_session.add(employee)
    await db_session.commit()
    await db_session.refresh(employee)
    return employee


@pytest.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    """
    Fixture returning Authorization headers containing a valid Bearer access token for Admin.
    """
    token = create_access_token(email=admin_user.email, role=admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def employee_headers(employee_user: User) -> dict[str, str]:
    """
    Fixture returning Authorization headers containing a valid Bearer access token for Employee.
    """
    token = create_access_token(email=employee_user.email, role=employee_user.role.value)
    return {"Authorization": f"Bearer {token}"}
