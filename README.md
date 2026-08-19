# Employee Task Management System

A full-stack Employee Task Management System built using FastAPI, PostgreSQL, SQLAlchemy 2.0, and React 19 with Vite, Tailwind CSS v4, and Zustand. This project showcases clean, modular architecture, `httpOnly` cookie-based JWT authentication, Role-Based Access Control (RBAC), administrative control panels, employee task & leave management portals, and an enterprise design system ("Deep Pine").

---

## Architecture & Project Structure

```text
Employee Task Management/
├── app/                                       # FastAPI Backend Application
│   ├── core/                                  # Core Security, JWT & Configuration
│   ├── db/                                    # Database Engine & Async Session Dependencies
│   ├── models/                                # SQLAlchemy 2.0 ORM Models (User, Task, Leave)
│   ├── routes/                                # HTTP API Controller Endpoints (Auth, Users, Tasks, Leaves)
│   ├── schemas/                               # Pydantic Input/Output Validation Schemas
│   └── services/                              # Async Database Query & Domain Business Logic Layer
├── frontend/                                  # React 19 + Vite SPA Frontend Application
│   ├── src/
│   │   ├── components/                        # UI Components & Layouts
│   │   │   ├── guards/                        # ProtectedRoute & AdminRoute Guards
│   │   │   ├── layout/                        # Navbar & UserMenu Layout Elements
│   │   │   ├── ui/                            # Deep Pine Design System Primitives (Button, Card, Badge, Modal, etc.)
│   │   │   ├── LeaveForm.jsx                  # Leave Submission Form
│   │   │   ├── LeaveHistoryList.jsx           # Personal Leave History List
│   │   │   ├── LeaveRejectModal.jsx           # Admin Leave Rejection Confirmation Dialog
│   │   │   ├── TaskCard.jsx                   # Employee Task Card Component
│   │   │   ├── TaskDeleteModal.jsx            # Admin Task Delete Dialog
│   │   │   ├── TaskFormModal.jsx              # Admin Task Creation & Edit Dialog
│   │   │   └── TaskList.jsx                   # Responsive Task Grid Container
│   │   ├── lib/                               # Axios Client & Date Helpers (api.js, dateUtils.js)
│   │   ├── pages/                             # Route Page Containers (Dashboard, AdminTasks, AdminLeaves, Leaves, Login, Register)
│   │   └── store/                             # Zustand In-Memory Auth Store (authStore.js)
│   ├── package.json                           # Frontend Dependencies & Scripts
│   └── vite.config.js                         # Vite Build Tool Configuration
├── alembic/                                   # Database Schema Migrations
├── docs/                                      # Verification Reports & System Documentation
├── scripts/                                   # Administrative Seeding & Integration Test Runner Scripts
└── tests/                                     # Pytest Backend Automated Test Suite
```

---

## Frontend Architecture & UI Features

The frontend is a modern single-page React application built with **React 19**, **Vite**, **Tailwind CSS v4**, **Zustand**, **React Router 7**, **Axios**, and **Lucide React**.

### Design System ("Deep Pine")
* **Restrained Palette**: Page background (`#0E1614`), primary surface (`#131F1C`), elevated surface (`#17251F`), and single teal accent (`#3FA88F`). No glassmorphism, no indigo, no glow effects.
* **Typography Discipline**: System sans-serif stack with 2 font weights (`400` regular, `500` medium). Sentence case used everywhere.
* **Component Library**: Primitive UI components (`Button`, `Input`, `Select`, `Textarea`, `Badge`, `Card`, `Modal`, `Alert`, `Spinner`, `EmptyState`) built with 1px hairline borders and subtle hover state micro-interactions.

### Key Frontend Features
1. **Auth & Session Security (Phase 2)**: In-memory access token storage, `httpOnly` refresh cookie automatic silent session restoration, and instant role-based post-login redirection.
2. **Employee Task Dashboard (Phase 3)**: Responsive 3-column task grid (`/dashboard`), relative due date countdowns ("Due today", "Overdue by N days"), and inline status transition selectors (`PENDING` → `IN_PROGRESS` → `COMPLETED`).
3. **Admin Task Control Panel (Phase 4)**: High-density data table at `/admin/tasks` (guarded by `AdminRoute`), client-side status/priority/employee filtering, reusable modal for task creation & editing, and deletion confirmation dialog.
4. **Employee Leave Portal (Phase 5)**: Personal leave request form at `/leaves` with client-side date validation (`end_date >= start_date`), and personal request timeline displaying status badges.
5. **Admin Leave Approval Hub (Phase 6)**: System-wide leave review table at `/admin/leaves` defaulting to `PENDING` review items, one-click inline Approve action, Reject confirmation dialog, and automatic reviewer tracking (`reviewed_by`).

### Running the Frontend
```bash
cd frontend
npm run dev
```
Access the application in your browser at:
👉 **`http://localhost:5173`**

To compile the production bundle:
```bash
cd frontend
npm run build
```

---

## Backend Asynchronous Architecture & Key Concepts

The backend is built with FastAPI and uses **100% Asynchronous Database Architecture** with SQLAlchemy 2.0, `asyncpg`, `AsyncSession`, and `async def` endpoints.

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

> *"In this project, we built a fully asynchronous backend using SQLAlchemy 2.0, `asyncpg`, and `AsyncSession`.*
> 
> *FastAPI is an ASGI asynchronous framework. In a synchronous setup, every database query blocks the thread waiting for network I/O. By converting route handlers and service logic to `async def` using `select()` constructs with `await db.execute()`, we made database I/O non-blocking.*
> 
> *When PostgreSQL processes a query, Python's event loop immediately switches context to process other concurrent incoming HTTP requests. We also configured Alembic to execute migrations via `async_engine.connect()` with `run_sync()`, and built an async Pytest test suite using `httpx.AsyncClient`, `aiosqlite` in-memory database, and `@pytest.mark.asyncio` fixtures to guarantee 100% test isolation."*

---

## Backend Setup Instructions

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
python scripts/seed_admin.py

# Non-interactive mode (environment variables):
# Windows (PowerShell):
$env:ADMIN_EMAIL="admin@example.com"; $env:ADMIN_PASSWORD="adminpassword123"; python scripts/seed_admin.py
# macOS/Linux:
ADMIN_EMAIL="admin@example.com" ADMIN_PASSWORD="adminpassword123" python scripts/seed_admin.py
```

---

## Running the Backend Server

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
docker compose exec -e ADMIN_EMAIL="admin@example.com" -e ADMIN_PASSWORD="adminpassword123" app python scripts/seed_admin.py

# Interactive mode:
docker compose exec app python scripts/seed_admin.py
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

---

## API Testing & Verification

### 1. Pytest Test Suite (Primary Test Suite)
The application includes a professional, industry-standard `pytest` test suite configured in `tests/`.

* **Isolated In-Memory Database**: Tests execute against an isolated in-memory SQLite database (`sqlite:///:memory:`) using FastAPI dependency overrides (`app.dependency_overrides[get_db]`). The development PostgreSQL database is never touched or modified during test runs.
* **Domain Integration & Service Unit Tests**: Includes HTTP integration test suites (`test_auth.py`, `test_leaves.py`, `test_rbac.py`, `test_tasks.py`) and direct service-layer unit tests (`test_services.py`).

**Run the Pytest suite**:
```bash
# Run all tests
pytest

# Run tests with detailed code coverage report
pytest --cov=app --cov-report=term-missing
```

### 2. Manual Verification Scripts & Postman
* **Integration Script**: `python scripts/test_endpoints.py`.
* **QA Suite Script**: `python scripts/run_qa_suite.py`.
* **Postman Collection**: Import [postman_collection.json](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/postman_collection.json) into Postman.
