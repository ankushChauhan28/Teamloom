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
Start the development server using Uvicorn:
```bash
uvicorn app.main:app --reload
```
Once running, the interactive Swagger documentation is available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

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


