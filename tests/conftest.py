"""
Pytest Central Configuration & Fixture Registry (conftest.py)

PostgreSQL Docker Test Database Setup with Alembic Migrations & Isolation.
"""

import os
import sys
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.email_verification_token import EmailVerificationToken  # noqa: F401
from app.models.leave import LeaveRequest  # noqa: F401
from app.models.organization import Organization, OrgStatus  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Test Database Configuration & Safety Guards
# ---------------------------------------------------------------------------
def _validate_test_database_safety(url_str: str) -> None:
    """
    Hard safety guard:
    Prevents tests from running against dev/production databases or wiping non-test data.
    Ensures:
    1. Database name in TEST_DATABASE_URL contains 'test'.
    2. Database name in TEST_DATABASE_URL is NOT identical to the app's DATABASE_URL database name.
    """
    test_url = make_url(url_str)
    test_db = test_url.database or ""

    app_db_url_str = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    app_url = make_url(app_db_url_str)
    app_db = app_url.database or ""

    if "test" not in test_db.lower():
        raise RuntimeError(
            f"CRITICAL SAFETY ERROR: TEST_DATABASE_URL database name '{test_db}' does not contain 'test'. "
            f"Refusing to run tests or perform TRUNCATE/migrations against a non-test database: {test_url.render_as_string(hide_password=True)}"
        )

    if test_db.lower() == app_db.lower():
        raise RuntimeError(
            f"CRITICAL SAFETY ERROR: TEST_DATABASE_URL database '{test_db}' is identical to the app's DATABASE_URL database '{app_db}'. "
            f"Tests must run against a dedicated, isolated test database to prevent data destruction."
        )


def _get_test_database_url() -> str:
    raw_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/employee_task_test_db",
    )
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    _validate_test_database_safety(raw_url)
    return raw_url


TEST_DATABASE_URL = _get_test_database_url()

from sqlalchemy.pool import NullPool

# Create async engine with NullPool so connections are bound to the active test event loop
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    poolclass=NullPool,
)
engine = test_engine

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Global list of discovered schema tables to truncate between tests
_TABLES_TO_TRUNCATE: list[str] = []


async def _ensure_test_database_exists() -> None:
    """
    Connects to the maintenance database ('postgres') to ensure the dedicated test database exists.
    If missing, creates it automatically.
    If connection fails, raises an actionable RuntimeError with troubleshooting guidance.
    """
    url = make_url(TEST_DATABASE_URL)
    target_db = url.database
    if not target_db:
        raise RuntimeError(f"Invalid TEST_DATABASE_URL without database name: {TEST_DATABASE_URL}")

    # Administrative maintenance DB URL (connect to 'postgres' system database)
    admin_url = url.set(database="postgres")
    try:
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": target_db},
            )
            exists = result.scalar() is not None
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{target_db}"'))
        await admin_engine.dispose()
    except Exception as exc:
        # Check if we can connect to the target database directly (in case user lacks permission to 'postgres' DB)
        try:
            target_engine = create_async_engine(TEST_DATABASE_URL)
            async with target_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await target_engine.dispose()
            return
        except Exception:
            pass
        raise RuntimeError(
            f"Failed to connect to or create test database '{target_db}' at {admin_url.render_as_string(hide_password=True)}.\n"
            f"Underlying error: {exc}\n"
            f"Please ensure PostgreSQL is running (e.g., 'docker compose up -d db') and TEST_DATABASE_URL is valid."
        ) from exc


def _run_alembic_migrations(db_url: str) -> None:
    """Executes Alembic migrations (alembic upgrade head) against test database."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(base_dir, "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


async def _discover_and_validate_tables() -> list[str]:
    """
    Dynamically queries PostgreSQL public schema for all base tables (excluding alembic_version),
    and validates that all Base.metadata model tables are covered.
    Fails loudly if any table in the migrated schema is missing from Base.metadata or vice-versa.
    """
    async with test_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_type = 'BASE TABLE' "
                "AND table_name != 'alembic_version' "
                "ORDER BY table_name;"
            )
        )
        db_tables = {row[0] for row in result.fetchall()}

    model_tables = set(Base.metadata.tables.keys())
    
    # Guard: Ensure all database tables in public schema are accounted for
    uncovered_tables = db_tables - model_tables
    if uncovered_tables:
        raise RuntimeError(
            f"Database contains public tables not registered in SQLAlchemy Base.metadata: {uncovered_tables}. "
            f"Ensure all models are imported in tests/conftest.py or registered on Base.metadata."
        )

    # Guard: Ensure all model tables exist in the migrated database
    unmigrated_tables = model_tables - db_tables
    if unmigrated_tables:
        raise RuntimeError(
            f"SQLAlchemy Base.metadata contains tables not found in migrated database: {unmigrated_tables}. "
            f"Check if all migrations have been applied."
        )

    return sorted(list(db_tables))


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Session-scoped Fixture:
    1. Validates test database safety guards (database name must contain 'test' and differ from dev/prod).
    2. Ensures the target PostgreSQL test database exists.
    3. Runs Alembic migrations ('alembic upgrade head') to build the schema from scratch.
    4. Dynamically discovers all base tables to truncate during test execution.
    """
    global _TABLES_TO_TRUNCATE
    import asyncio

    # Hard Safety Guard check before any DB interaction
    _validate_test_database_safety(TEST_DATABASE_URL)

    # Ensure database exists
    asyncio.run(_ensure_test_database_exists())

    # Run Alembic migrations against test database
    _run_alembic_migrations(TEST_DATABASE_URL)

    # Discover and validate migrated tables
    _TABLES_TO_TRUNCATE = asyncio.run(_discover_and_validate_tables())
    yield


@pytest.fixture(autouse=True)
def mock_send_welcome_email() -> AsyncGenerator[MagicMock, None]:
    """
    Autouse Fixture (Scope: Function):
    Automatically mocks SMTPEmailSender for ALL tests in the suite
    so no real SMTP network connections are ever attempted during pytest execution.
    """
    with patch(
        "app.core.email.SMTPEmailSender.send_welcome_email",
        return_value=True,
    ) as mock_smtp_welcome, patch(
        "app.core.email.SMTPEmailSender.send_verification_email",
        return_value=True,
    ):
        yield mock_smtp_welcome


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    Autouse Fixture (Scope: Function):
    Resets the in-memory rate limiter state before every test to ensure test isolation.
    """
    from app.core.rate_limit import _limiter_instance

    _limiter_instance.reset()
    yield
    _limiter_instance.reset()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async Database Session Fixture (Scope: Function)
    Provides fast, deterministic per-test data isolation via dynamic TRUNCATE and sequence reset.
    Enables multiple concurrent connections/commits without rollback isolation locks.
    """
    _validate_test_database_safety(TEST_DATABASE_URL)

    global _TABLES_TO_TRUNCATE
    if not _TABLES_TO_TRUNCATE:
        _TABLES_TO_TRUNCATE = await _discover_and_validate_tables()

    table_clause = ", ".join(f'"{t}"' for t in _TABLES_TO_TRUNCATE)
    async with test_engine.begin() as conn:
        if table_clause:
            await conn.execute(text(f"TRUNCATE TABLE {table_clause} RESTART IDENTITY CASCADE;"))

    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    FastAPI AsyncClient Fixture with Async Dependency Override
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def test_org(db_session: AsyncSession) -> Organization:
    """
    Fixture creating the default test organization in the test database.
    """
    org = Organization(
        name="Internal / free forever",
        status=OrgStatus.ACTIVE.value,
        is_internal=True,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def admin_user(db_session: AsyncSession, test_org: Organization) -> User:
    """
    Fixture creating a test ADMIN user asynchronously in the test database.
    """
    admin = User(
        full_name="Test System Admin",
        email="admin.test@example.com",
        hashed_password=hash_password("adminpassword123"),
        role=UserRole.ADMIN,
        access_level=1,
        employee_code="1000000001",
        is_email_verified=True,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def employee_user(db_session: AsyncSession, test_org: Organization) -> User:
    """
    Fixture creating a test EMPLOYEE user asynchronously in the test database.
    """
    employee = User(
        full_name="Test John Employee",
        email="employee.test@example.com",
        hashed_password=hash_password("employeepassword123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1000000002",
        is_email_verified=True,
        must_change_password=False,
        organization_id=test_org.id,
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


@pytest.fixture
async def test_org_b(db_session: AsyncSession) -> Organization:
    """
    Fixture creating a second isolated test organization (Org B).
    """
    org = Organization(
        name="Acme Corp Organization B",
        status=OrgStatus.ACTIVE.value,
        is_internal=False,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def admin_user_b(db_session: AsyncSession, test_org_b: Organization) -> User:
    """
    Fixture creating an ADMIN user for Org B.
    """
    admin = User(
        full_name="Org B Admin",
        email="admin.orgb@example.com",
        hashed_password=hash_password("adminorgb123"),
        role=UserRole.ADMIN,
        access_level=1,
        employee_code="1000000010",
        is_email_verified=True,
        must_change_password=False,
        organization_id=test_org_b.id,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def employee_user_b(db_session: AsyncSession, test_org_b: Organization) -> User:
    """
    Fixture creating an EMPLOYEE user for Org B.
    """
    emp = User(
        full_name="Org B Employee",
        email="employee.orgb@example.com",
        hashed_password=hash_password("emporgb123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1000000011",
        is_email_verified=True,
        must_change_password=False,
        organization_id=test_org_b.id,
    )
    db_session.add(emp)
    await db_session.commit()
    await db_session.refresh(emp)
    return emp


@pytest.fixture
async def admin_headers_b(admin_user_b: User) -> dict[str, str]:
    """
    Authorization headers for Org B Admin.
    """
    token = create_access_token(email=admin_user_b.email, role=admin_user_b.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def employee_headers_b(employee_user_b: User) -> dict[str, str]:
    """
    Authorization headers for Org B Employee.
    """
    token = create_access_token(email=employee_user_b.email, role=employee_user_b.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def task_b(
    db_session: AsyncSession,
    test_org_b: Organization,
    employee_user_b: User,
    admin_user_b: User,
) -> Task:
    """
    Fixture creating a Task belonging to Org B.
    """
    from datetime import UTC, datetime, timedelta
    from app.models.task import TaskPriority, TaskStatus

    task = Task(
        title="Org B Task",
        description="Task for org B",
        priority=TaskPriority.HIGH,
        status=TaskStatus.PENDING,
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        assigned_to=employee_user_b.id,
        created_by=admin_user_b.id,
        organization_id=test_org_b.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest.fixture
async def leave_b(
    db_session: AsyncSession,
    test_org_b: Organization,
    employee_user_b: User,
) -> LeaveRequest:
    """
    Fixture creating a LeaveRequest belonging to Org B.
    """
    from datetime import date, timedelta
    from app.models.leave import LeaveStatus

    leave = LeaveRequest(
        employee_id=employee_user_b.id,
        reason="Org B Vacation",
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=7),
        status=LeaveStatus.PENDING,
        organization_id=test_org_b.id,
    )
    db_session.add(leave)
    await db_session.commit()
    await db_session.refresh(leave)
    return leave

