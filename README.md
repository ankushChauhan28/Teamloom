# Teamloom

A modern workforce task management platform featuring reporting hierarchy, performance analytics, and granular role-based access control.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19.0+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Vite](https://img.shields.io/badge/Vite-8.2+-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)

---

## 📸 Overview & Screenshots

![Teamloom Login Page](docs/screenshots/login.png)
*Teamloom Login Page*

![Task Control Panel](docs/screenshots/admin_tasks.png)
*Admin's System-Wide Task Control Panel*

![Manage Employees Directory](docs/screenshots/admin_employees.png)
*Admin's Manage Employees Directory (Provisioning, Designations & Hierarchy)*

![My Team Portal](docs/screenshots/my_team.png)
*Manager's "My Team" Page Showing Direct Reports*

![My Performance Analytics](docs/screenshots/my_performance.png)
*Personal Performance Analytics (Completion Ring & Milestone Trail)*

![Leave Approval Queue](docs/screenshots/leave_approval.png)
*Admin's Leave Request Approval Queue*

🔗 **Live Demo**: [Coming Soon]

---

## ✨ Key Features

- **Manager Hierarchy & Supervisory Scoping**: Self-referencing supervisor mapping (`reports_to_id`) with cycle detection, supporting hierarchy-scoped task assignment, leave approvals, and direct report rosters (`/my-team`).
- **Administrative Employee Provisioning**: Secure onboarding flow generating sequential employee codes (`EMP-1001`), job title designations, supervisor assignments, temporary passwords, and welcome emails (`/admin/employees`).
- **Forced & Voluntary Password Management**: Automated forced redirect to `/change-password` for new hires on initial login, alongside voluntary self-service password updates accessible via the profile dropdown.
- **Task & Leave Management Workflows**: End-to-end task lifecycle (`PENDING` → `IN_PROGRESS` → `COMPLETED`) and personal leave request submission portal (`/leaves`) with administrative review hub (`/admin/leaves`).
- **Live Deadline Countdown Ticker**: Dynamic `DueCountdown` component updating every minute with exact relative deadline status ("2d 4h left", "15m left", "Overdue by 1d 3h").
- **Server-Side Performance Analytics**: Fast server-side SQL aggregation providing completion rate gauges (`PerformanceRing`) and chronological milestone trails (`MilestoneTrail`) scoped by `self`, `team`, or `org`.
- **Dual-Token Authentication & Security**: Memory-stored access tokens with rotation via `httpOnly` refresh cookies, account lockout defense (5 failed login attempts → 15 min lock), and IP sliding-window rate limiting.
- **Deep Pine Dark Theme**: Bespoke enterprise design system featuring rich dark surfaces (`#0E1614`, `#131F1C`, `#17251F`), high-contrast typography, and smooth micro-interactions.

---

## 🛠 Tech Stack

### Backend
- **Framework**: FastAPI (Async Python 3.11+)
- **Database & ORM**: PostgreSQL 16, Async SQLAlchemy 2.0, `asyncpg`
- **Migrations**: Alembic
- **Authentication**: PyJWT (Dual-Token), Passlib / Bcrypt password hashing
- **Validation**: Pydantic v2 & Pydantic-Settings

### Frontend
- **Framework**: React 19 SPA (Vite)
- **State Management**: Zustand (In-memory token & session store)
- **Styling**: Vanilla CSS & Tailwind CSS v4 ("Deep Pine" design tokens)
- **Icons & HTTP**: Lucide React, Axios (with silent 401 token refresh interceptors)

---

## 📁 Project Structure

```text
Teamloom/
├── app/                  # FastAPI backend application
│   ├── core/             # Configuration, security, rate limiting & exception handlers
│   ├── db/               # Async database engine & session dependencies
│   ├── models/           # SQLAlchemy 2.0 ORM models (Organization, User, Task, LeaveRequest, RevokedToken)
│   ├── routes/           # REST API endpoints (auth, users, tasks, leaves, analytics)
│   ├── schemas/          # Pydantic request & response validation schemas
│   └── services/         # Domain business logic & server-side SQL queries
├── alembic/              # Database schema migration scripts
├── scripts/              # Administrative CLI scripts (seed_admin, unlock_user, run_qa_suite)
├── tests/                # Pytest async integration & unit test suite
├── frontend/             # React 19 + Vite frontend application
│   ├── src/
│   │   ├── components/   # UI primitives, layout headers, route guards & feature modals
│   │   ├── pages/        # Application view containers (Dashboard, Team, Performance, Admin)
│   │   ├── store/        # Zustand session & authentication store (authStore.js)
│   │   └── lib/          # Axios API client & date formatting helpers
│   ├── package.json      # Node dependencies & build scripts
│   └── vite.config.js    # Vite configuration
├── docker-compose.yml    # Multi-container Docker Compose configuration
└── requirements.txt      # Python dependencies
```

---

## 🚀 Getting Started

### Option A: Running with Docker Compose (Recommended)

Run both the FastAPI application backend and PostgreSQL database in containerized mode:

```bash
# 1. Clone repository
git clone https://github.com/ankushChauhan28/Teamloom.git
cd Teamloom

# 2. Configure environment
cp .env.example .env

# 3. Build and launch services
docker compose up --build -d
```

- **Interactive API Documentation**: Access Swagger UI at `http://localhost:8000/docs`.
- **Seed System Administrator**:
  ```bash
  docker compose exec -e ADMIN_EMAIL="admin@example.com" -e ADMIN_PASSWORD="adminpassword123" app python scripts/seed_admin.py
  ```

---

### Option B: Manual Local Setup

#### 1. Backend Setup
```bash
# Clone and enter root directory
cd Teamloom

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your local PostgreSQL connection details

# Apply database migrations to head
alembic upgrade head

# Seed canonical System Administrator
python scripts/seed_admin.py

# Start FastAPI dev server
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Testing & Quality Assurance

Backend tests run against a real, isolated PostgreSQL database (running via Docker or local PostgreSQL instance) with automatic Alembic migrations and per-test table isolation:

```bash
# 1. Start PostgreSQL with Docker Compose (creates dev and test databases)
docker compose up -d db

# 2. (Optional) Override test database URL if not using default localhost:5433
# Windows PowerShell:
# $env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/employee_task_test_db"
# Linux/macOS:
# export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/employee_task_test_db"

# 3. Run complete test suite
pytest

# 4. Run tests with coverage summary
pytest --cov=app --cov-report=term-missing
```

- **Pass Rate**: 100% (**158 passing tests**)
- **Database Engine**: PostgreSQL 16 (Docker) with Alembic migration parity
- **Statement Coverage**: **87% overall**
