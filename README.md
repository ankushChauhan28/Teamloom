# Teamloom

An enterprise role-based internal task & leave management platform built with FastAPI, PostgreSQL, SQLAlchemy 2.0, and React 19 with Vite, Tailwind CSS v4, and Zustand. The application features fine-grained access control, `httpOnly` cookie-based JWT authentication, administrative control panels, employee self-service portals, and an enterprise dark design system ("Deep Pine").

---

## Key Features

* **Role-Based Access Control (RBAC)**: Enforces strict authorization boundaries between `ADMIN` and `EMPLOYEE` roles across all backend APIs and frontend routes.
* **JWT Authentication & Security**: Uses `httpOnly` refresh token cookie rotation with short-lived access tokens stored strictly in memory, featuring automatic silent session restoration on app mount.
* **Employee Task Dashboard**: Responsive task list grid (`/dashboard`) displaying assigned tasks with relative due date countdowns ("Due today", "Overdue by N days") and inline status transition controls (`PENDING` → `IN_PROGRESS` → `COMPLETED`).
* **Admin Task Control Panel**: High-density management table at `/admin/tasks` featuring instant status, priority, and employee filtering, interactive task creation & edit modals, and deletion confirmation dialogs.
* **Employee Leave Portal**: Personal leave request submission form at `/leaves` with client-side date range validation (`end_date >= start_date`) and personal request history timelines.
* **Admin Leave Approval Hub**: System-wide leave review hub at `/admin/leaves` defaulting to pending action items, featuring one-click inline approvals, rejection confirmation dialogs, and reviewer tracking (`reviewed_by`).
* **Clean Layered Architecture**: Backend follows a strict multi-layer separation (routes, domain services, ORM models, Pydantic schemas) powered by 100% asynchronous database I/O.
* **Enterprise Design System ("Deep Pine")**: Dark green-black surface palette (`#0E1614` page, `#131F1C` surface-1, `#17251F` surface-2) with hairline borders, subtle micro-interactions, and typography discipline.

---

## Tech Stack

| Layer | Technologies & Tools |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), `asyncpg`, PostgreSQL, Alembic, Pydantic v2, PyJWT, Passlib (Bcrypt) |
| **Frontend** | React 19, Vite, Tailwind CSS v4, Zustand, React Router 7, Axios, Lucide React |
| **Containerization & Tooling** | Docker, Docker Compose, Pytest, Ruff, Black, Mypy, Pre-commit |

---

## Architecture & Project Structure

```text
Teamloom/
├── app/                                       # FastAPI Backend Application
│   ├── core/                                  # Security, JWT, exception handlers & environment config
│   ├── db/                                    # Async SQLAlchemy engine & session dependency setup
│   ├── models/                                # SQLAlchemy 2.0 ORM models (User, Task, LeaveRequest)
│   ├── routes/                                # HTTP API controllers (auth, users, tasks, leaves)
│   ├── schemas/                               # Pydantic v2 request & response validation schemas
│   └── services/                              # Business logic layer executing database operations
├── frontend/                                  # React 19 + Vite Single Page Application
│   ├── src/
│   │   ├── components/                        # React UI Components
│   │   │   ├── guards/                        # ProtectedRoute & AdminRoute authorization guards
│   │   │   ├── layout/                        # Navbar & UserMenu header elements
│   │   │   ├── ui/                            # Deep Pine design primitives (Button, Card, Badge, Modal, etc.)
│   │   │   ├── LeaveForm.jsx                  # Employee leave request submission form card
│   │   │   ├── LeaveHistoryList.jsx           # Stacked list of employee's personal leave requests
│   │   │   ├── LeaveRejectModal.jsx           # Admin leave rejection confirmation dialog
│   │   │   ├── TaskCard.jsx                   # Employee dashboard task card component
│   │   │   ├── TaskDeleteModal.jsx            # Admin task deletion dialog
│   │   │   ├── TaskFormModal.jsx              # Admin task creation & edit dialog
│   │   │   └── TaskList.jsx                   # Responsive task grid container
│   │   ├── lib/                               # Axios client instance & date utility helpers
│   │   ├── pages/                             # Route page containers (Dashboard, AdminTasks, AdminLeaves, Leaves, Login, Register)
│   │   └── store/                             # Zustand in-memory auth store (authStore.js)
│   ├── package.json                           # Frontend npm dependencies & build scripts
│   └── vite.config.js                         # Vite build tool configuration
├── alembic/                                   # Alembic database migration scripts
├── docs/                                      # Verification reports & documentation
├── scripts/                                   # Database seeding & API verification scripts
└── tests/                                     # Pytest backend test suite (unit + integration)
```

---

## Getting Started

### 1. Running with Docker Compose (Recommended)

The project includes Docker configurations for both the FastAPI application server and PostgreSQL database.

```bash
# Build and launch both containers in detached mode:
docker compose up --build -d
```

* **Automated Migrations**: The container startup script ([docker-entrypoint.sh](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/docker-entrypoint.sh)) automatically executes `alembic upgrade head` before Uvicorn starts.
* **Interactive API Documentation**: Access Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs) and ReDoc at [http://localhost:8000/redoc](http://localhost:8000/redoc).

#### Seeding an Administrative User
To create an initial `ADMIN` user inside the running container:
```bash
docker compose exec -e ADMIN_EMAIL="admin@example.com" -e ADMIN_PASSWORD="adminpassword123" app python scripts/seed_admin.py
```

---

### 2. Local Development Setup (Without Docker)

#### Backend Setup
1. **Prerequisites**: Python 3.11+ and PostgreSQL database server running locally.
2. **Environment & Dependencies**:
   ```bash
   python -m venv venv
   # Activate virtual environment:
   # Windows: venv\Scripts\activate | macOS/Linux: source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Environment Configuration**:
   ```bash
   cp .env.example .env
   # Update DATABASE_URL in .env with your PostgreSQL credentials
   ```
4. **Database Migrations & Admin Seeding**:
   ```bash
   alembic upgrade head
   python scripts/seed_admin.py
   ```
5. **Start FastAPI Backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

#### Frontend Setup
1. **Install Dependencies & Start Dev Server**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. **Access Frontend**: Open [http://localhost:5173](http://localhost:5173) in your browser.
3. **Production Build**:
   ```bash
   cd frontend
   npm run build
   ```

---

## Testing & Quality Assurance

### Pytest Automated Test Suite
The backend includes a `pytest` test suite configured in `tests/` using an isolated in-memory SQLite database (`sqlite:///:memory:`).

```bash
# Run backend test suite
pytest

# Run tests with code coverage report
pytest --cov=app --cov-report=term-missing
```

### Static Analysis & Pre-commit
```bash
# Linting & Formatting
ruff check .
black --check .
mypy app

# Run pre-commit hooks
pre-commit run --all-files
```

### API Integration Verification
* **Postman Collection**: Import [postman_collection.json](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/postman_collection.json) into Postman for endpoint testing.
* **CLI Test Scripts**: Run `python scripts/test_endpoints.py` or `python scripts/run_qa_suite.py`.
