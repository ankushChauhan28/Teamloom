# Employee Task Management System (Backend-Only)

A backend-only Employee Task Management System built in Python using FastAPI, SQLAlchemy, Alembic, and PostgreSQL. This project showcases clean, modular architecture, JWT-based Authentication (Access + Refresh tokens), Role-Based Access Control (RBAC), and database migration workflows.

---

## Folder Structure & Module Descriptions

```
app/
├── main.py                # FastAPI app entrypoint, registers routes, configures CORS, and defines centralized exception handling
├── core/
│   ├── config.py          # Configuration management loading variables from .env via Pydantic BaseSettings
│   ├── security.py        # Token operations (signing, validation, dependencies for auth) and password hashing
│   └── exceptions.py      # Custom domain exceptions for cleaner business error propagation
├── db/
│   ├── base.py            # SQLAlchemy Base configuration, database engine, and SessionLocal setup
│   └── session.py         # get_db() FastAPI dependency yielding database sessions
├── models/
│   ├── user.py            # User DB Model (roles: ADMIN, EMPLOYEE)
│   ├── task.py            # Task DB Model (status, priority, assignment relationships)
│   └── leave.py           # LeaveRequest DB Model (approval status, reviewer relationship)
├── schemas/
│   ├── user.py            # Pydantic validation schemas for authentication, token payload, and user profiles
│   ├── task.py            # Pydantic validation schemas for task inputs, status updates, and responses
│   └── leave.py           # Pydantic validation schemas for leave request creations and status approvals
├── routes/
│   ├── auth.py            # Registration, login, and refresh token endpoints
│   ├── users.py           # User profiles (me, list employees)
│   ├── tasks.py           # Task CRUD operations with filters, pagination, and sorting
│   └── leaves.py          # Leave request submission and Admin approvals
└── services/              # Thin business logic layer executing database actions
    ├── auth_service.py    # Registers users, authenticates passwords, and refreshes tokens
    ├── task_service.py    # CRUD task business logic and ownership constraints
    └── leave_service.py   # Submits leaves and executes Admin approvals
alembic/                   # Database migrations configuration and history versions
```

---

## Asynchronous Architecture & Key Concepts

The Employee Task Management backend uses **100% Asynchronous Database Architecture** built with SQLAlchemy 2.0, `asyncpg`, `AsyncSession`, and `async def` endpoints.

### Why Async Matters for FastAPI
FastAPI is built on Starlette and ASGI (Asynchronous Server Gateway Interface), powered by Python's `asyncio` event loop.

1. **Non-Blocking I/O Execution**:
   In synchronous frameworks (or with synchronous database drivers like `psycopg2`), executing a database query blocks the worker thread until PostgreSQL responds over the network. Under heavy traffic, thread starvation occurs and request latencies spike.
2. **Event Loop Efficiency (`asyncpg` + `AsyncSession`)**:
   By using `async def` routes and `await db.execute(stmt)` with `asyncpg`, when a query executes, control yields back to the `asyncio` event loop. While PostgreSQL computes the result, the event loop serves dozens of other concurrent incoming HTTP requests on the same thread.
3. **Performance Gains**:
   - **Scalability**: Handles high concurrent request volume (RPS) with significantly lower CPU & memory footprint.
   - **Resilience**: Prevents worker thread exhaustion during DB latency spikes.

---

###  Guide: "Walk me through Sync vs Async in your project"

> *"In this project, we migrated from synchronous SQLAlchemy with `psycopg2` to fully asynchronous database handling using SQLAlchemy 2.0, `asyncpg`, and `AsyncSession`.*
> 
> *FastAPI is an ASGI asynchronous framework. In a synchronous setup, every database query blocks the thread waiting for network I/O. By converting route handlers and service logic to `async def` using `select()` constructs with `await db.execute()`, we made database I/O non-blocking.*
> 
> *When PostgreSQL processes a query, Python's event loop immediately switches context to process other concurrent incoming HTTP requests. We also configured Alembic to execute migrations via `async_engine.connect()` with `run_sync()`, and built an async Pytest test suite using `httpx.AsyncClient`, `aiosqlite` in-memory database, and `@pytest.mark.asyncio` fixtures to guarantee 100% test isolation."*

---


## Setup Instructions

### 1. Prerequisites
- Python 3.12+ (Python 3.11 is also supported)
- PostgreSQL database server running locally or accessible remotely.

### 2. Installation
1. Clone this repository to your local machine.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install the application dependencies:
   ```bash
   pip install -r requirements.txt
   # Optional: Install development & code quality tools
   pip install -r requirements-dev.txt
   ```
4. Copy the environment variables template and configure the variables:
   ```bash
   cp .env.example .env
   ```
   *Note: Open `.env` and fill in your PostgreSQL server password and other settings. The database `employee_task_db` will need to be created in your PostgreSQL server first.*

---

## Database Migrations
Database table creations and schema changes are handled via Alembic.

1. **Verify your `.env` connection string**: Ensure `DATABASE_URL` is correct.
2. **Apply migrations**: Run the following command to create the database schema:
   ```bash
   alembic upgrade head
   ```

To generate future migrations after updating models:
```bash
alembic revision --autogenerate -m "description of changes"
alembic upgrade head
```

---

## Administrative Seed Script
Because open registration only creates users with the `EMPLOYEE` role, an administrative user must be created using the seeding utility.

Run the following command to seed an initial `ADMIN` user. You can pass environment variables or enter values interactively when prompted:
```bash
# Interactive mode:
python seed_admin.py

# Non-interactive mode (environment variables):
# Windows (PowerShell):
$env:ADMIN_EMAIL="admin@example.com"; $env:ADMIN_PASSWORD="adminpassword123"; python seed_admin.py
# macOS/Linux:
ADMIN_EMAIL="admin@example.com" ADMIN_PASSWORD="adminpassword123" python seed_admin.py
```

---

## Running the Server

### Option A: Run with Docker (Recommended)
The project includes an enterprise-ready Docker setup powering both the FastAPI application server (`app`) and PostgreSQL database (`db`) using `docker-compose`.

```bash
docker compose up --build -d
```

### Option B: Running Locally (without Docker)
Start the local development server using Uvicorn:
```bash
uvicorn app.main:app --reload
```

Once running (via Docker or local Uvicorn), interactive Swagger documentation is available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Run with Docker Details


### 1. Starting the Containers
Build and launch both application and database containers in detached mode:
```bash
docker compose up --build -d
```
* **Automated Database Migrations**: The container startup script ([docker-entrypoint.sh](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/docker-entrypoint.sh)) automatically runs `alembic upgrade head` before Uvicorn starts.

### 2. Seeding the Admin User inside Container
Execute the admin seeding script inside the running `app` container:
```bash
# Non-interactive mode with environment variables:
docker compose exec -e ADMIN_EMAIL="admin@example.com" -e ADMIN_PASSWORD="adminpassword123" app python seed_admin.py

# Interactive mode:
docker compose exec app python seed_admin.py
```

### 3. Viewing Logs & Stopping Services
```bash
# View live application logs:
docker compose logs -f app

# Stop containers (database data persists in named volume):
docker compose down

# Stop containers and erase persistent database volume:
docker compose down -v
```

---

## Docker Architecture &  Concepts

### Key Design Choices Explained

1. **Multi-Stage Builds (`Dockerfile`)**:
   * **Why**: Stage 1 (`builder`) installs build tools (`gcc`, `libpq-dev`) and compiles python wheels into `/build/wheels`. Stage 2 (`runtime`) copies *only* the pre-built wheels into a clean `python:3.12-slim` image.
   * **Benefit**: Reduces final image size significantly and eliminates build compilers from production containers, shrinking the attack surface.

2. **Non-Root User Security (`appuser`)**:
   * **Why**: Containers by default run as `root`. We create an unprivileged system user (`appuser:appgroup`) and switch execution context via `USER appuser`.
   * **Benefit**: Prevents container breakout vulnerabilities from gaining root privileges on the host system.

3. **Layer Caching Optimization**:
   * **Why**: We `COPY requirements.txt .` and run `pip wheel` *before* copying application source code (`COPY app/`).
   * **Benefit**: Docker caches the dependency layer. Modifying source code avoids re-downloading and re-building unchanged Python packages.

4. **Container Healthchecks & Service Dependencies**:
   * **Why**: The `db` service runs `pg_isready -U postgres`, and `app` uses `depends_on: db: condition: service_healthy`.
   * **Benefit**: Guarantees that Alembic migrations run only after PostgreSQL is fully ready to accept database connections, avoiding connection refactoring crashes on cold start.

5. **Data Persistence via Named Volumes**:
   * **Why**: PostgreSQL data is mapped to `postgres_data:/var/lib/postgresql/data`.
   * **Benefit**: Database records persist reliably even when containers are stopped, recreated, or updated.

---


## Code Quality & Tooling
The project includes professional Python code quality, linting, formatting, and static typing tooling configured via `pyproject.toml`.

### 1. Running Linter & Formatter
* **Ruff (Linter)**:
  ```bash
  ruff check .
  # Auto-fix trivial lint issues:
  ruff check --fix .
  ```
* **Black (Code Formatter)**:
  ```bash
  black --check .
  # Auto-format all files:
  black .
  ```
* **Mypy (Static Type Checking)**:
  ```bash
  mypy app
  ```

### 2. Pre-commit Git Hooks
To automatically enforce code quality checks before every git commit:
```bash
# Install git hook scripts
pre-commit install

# Manually run all hooks on all files
pre-commit run --all-files
```

## API Testing & Verification

### 1. Pytest Test Suite (Primary Test Suite)
The application includes a professional, industry-standard `pytest` test suite configured in `tests/`.

* **Isolated In-Memory Database**: Tests execute against an isolated in-memory SQLite database (`sqlite:///:memory:`) using FastAPI dependency overrides (`app.dependency_overrides[get_db]`). The development PostgreSQL database is never touched or modified during test runs.
* **Domain Integration & Service Unit Tests**: Includes HTTP integration test suites (`test_auth.py`, `test_users.py`, `test_tasks.py`, `test_leaves.py`, `test_rbac.py`) and direct service-layer unit tests (`test_services.py`).

**Run the Pytest suite**:
```bash
# Run all tests
pytest

# Run tests with detailed code coverage report
pytest --cov=app --cov-report=term-missing
```

### 2. Manual Verification Scripts & Postman
* **Integration Script**: `python test_endpoints.py` (requires running server at `http://127.0.0.1:8000`).
* **QA Suite Script**: `python run_qa_suite.py`.
* **Postman Collection**: Import [postman_collection.json](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/postman_collection.json) into Postman.


