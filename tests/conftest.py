"""
Pytest Central Configuration & Fixture Registry (conftest.py)

EDUCATIONAL EXPLANATION - WHY WE USE CONFTEST & FIXTURES:
---------------------------------------------------------
1. What is conftest.py?
   In Pytest, 'conftest.py' is automatically discovered by pytest. Fixtures defined here
   are available to all test files in the directory tree without needing explicit imports.

2. Why use Fixtures?
   Fixtures manage setup (arrange) and teardown (clean up) logic for tests. Instead of
   manually initializing database connections or API clients in every single test, pytest
   injects these dependencies as argument names into test functions.

3. Why an Isolated SQLite Test Database?
   Testing against a real development or production database is an anti-pattern:
   - Tests could delete, mutate, or pollute actual development data.
   - Tests would depend on external service availability (PostgreSQL server running).
   - Tests would run much slower due to network/disk I/O.
   Here, we use an in-memory SQLite database (`sqlite:///:memory:`) with SQLAlchemy's `StaticPool`.
   Each test run creates fresh tables in memory and tears them down, guaranteeing 100% test isolation.

4. Why FastAPI Dependency Overrides (`app.dependency_overrides`)?
   FastAPI's architecture allows overriding dependency callables at runtime. By swapping the production
   `get_db` dependency with our test database generator, every API endpoint invoked during testing
   automatically operates against our isolated in-memory test database.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole

# Create an in-memory SQLite engine for testing.
# StaticPool maintains a single connection in memory across threads during the test session.
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Database Session Fixture (Scope: Function)

    EXPLANATION:
    - Creates all database tables (`Base.metadata.create_all`) before each test starts.
    - Yields a fresh `Session` for the test to use.
    - Drops all tables (`Base.metadata.drop_all`) after the test completes.
    This guarantees that every test starts with a completely clean database state.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient Fixture with Dependency Override

    EXPLANATION:
    FastAPI provides `TestClient` (powered by `httpx`) to simulate HTTP requests against
    our API endpoints without starting an actual network server on a port.

    We override `get_db` so that all route handlers execute queries against the `db_session`
    fixture's isolated in-memory SQLite database.
    """

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """
    Fixture creating a test ADMIN user in the test database.
    """
    admin = User(
        full_name="Test System Admin",
        email="admin.test@example.com",
        hashed_password=hash_password("adminpassword123"),
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def employee_user(db_session: Session) -> User:
    """
    Fixture creating a test EMPLOYEE user in the test database.
    """
    employee = User(
        full_name="Test John Employee",
        email="employee.test@example.com",
        hashed_password=hash_password("employeepassword123"),
        role=UserRole.EMPLOYEE,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    """
    Fixture returning Authorization headers containing a valid Bearer access token for Admin.
    """
    token = create_access_token(email=admin_user.email, role=admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def employee_headers(employee_user: User) -> dict[str, str]:
    """
    Fixture returning Authorization headers containing a valid Bearer access token for Employee.
    """
    token = create_access_token(email=employee_user.email, role=employee_user.role.value)
    return {"Authorization": f"Bearer {token}"}
