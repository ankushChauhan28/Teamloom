# Teamloom — Project Overview & Architecture Reference

> **Auditor Notice**: This technical handover document has been prepared by a senior software engineer conducting a forensic code audit of the entire repository. Every statement, file path, version number, configuration setting, and architectural flow is derived strictly from direct inspection of the codebase. Items that cannot be determined conclusively from the code are explicitly marked as `Unknown / Needs confirmation`. No application code was modified during this audit.

---

## PART 1: Project Overview and Structure

### 1.1 Project Purpose, Target Personas & Solved Problems
**Teamloom** is an enterprise workforce task management, managerial oversight, and organizational operations platform designed to coordinate day-to-day work assignments, absence management, supervisory reporting chains, and delivery analytics. Originally built as an internal tool, it is undergoing an architectural transition toward a multi-tenant, subscription-gated SaaS (Slices 1 through 4d complete).

#### Target Personas & Roles (inferred from `app/models/user.py`, `app/core/permissions.py`, `docs/PROJECT_MASTERY.md`)
1. **Tier 1 — Executive / Administrator (`access_level = 1`, legacy role `ADMIN`)**:
   - The first administrator is provisioned during self-serve company signup (`POST /auth/signup`).
   - Powers: Provision employee accounts, assign designations, establish and rewire reporting chains (`reports_to_id`), deactivate/reactivate staff, create system-wide tasks, delete tasks, review and approve/reject all leave requests, view company-wide performance metrics, and manage future billing/subscriptions.
2. **Tier 2 — Department Manager (`access_level = 2`, role `EMPLOYEE`)**:
   - Supervises direct reports.
   - Powers: Assign tasks to direct reports, edit task metadata for direct reports, monitor direct reports' task completion, view team leave schedules (view-only), and review aggregated team performance analytics.
3. **Tier 3 — Team Lead (`access_level = 3`, role `EMPLOYEE`)**:
   - Senior individual contributors who also have direct reports.
   - Powers: Execute personal tasks, delegate tasks down their direct-reporting chain, view sub-team leaves (view-only), and view personal and team analytics.
4. **Tier 4 — Associate / Contributor (`access_level = 4`, role `EMPLOYEE`)**:
   - Base operational employees without subordinates.
   - Powers: View personal task dashboard, transition task status (`PENDING` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`), submit absence requests, view personal leave history, and monitor individual on-time delivery rates.

#### Problems Solved by the Application:
- **Opaque Reporting & Delegation**: Solves informal task assignment by enforcing a strict direct-reporting delegation model (`assignee.reports_to_id == actor.id` or Tier 1 override).
- **Leave Schedule Conflicts**: Solves absence tracking with date-overlap validation and centralized Tier-1 approval while granting supervisors visibility into active direct reports' leaves.
- **Deadline Blindness**: Solves missed deadlines via live countdown tickers (`DueCountdown.jsx`) and server-side on-time/late performance analytics.
- **Concurrent Overwrites**: Solves lost updates via optimistic concurrency locking on tasks (`version` field with HTTP 409 conflict detection).
- **Tenant Isolation**: Groups users, tasks, and leave requests under an `Organization` container, preventing cross-company data leakage.

---

### 1.2 Complete Folder & File Structure

```text
C:\Users\ankus\Desktop\Employee Task Management\
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions workflow for backend test automation on Ubuntu + PostgreSQL 16
├── alembic/
│   ├── versions/                       # 16 schema migration scripts (f2850ec5859c to n4o5p6q7r8s9)
│   ├── env.py                          # Alembic async migration execution script loading Base metadata
│   ├── README                          # Default Alembic auto-generated directory readme
│   └── script.py.mako                  # Template for generating new Alembic migration scripts
├── app/
│   ├── core/
│   │   ├── config.py                   # Pydantic BaseSettings loading .env, database URLs, JWT keys, SMTP, CORS
│   │   ├── email.py                    # EmailSender abstract interface with SMTPEmailSender & ConsoleEmailSender
│   │   ├── exceptions.py               # Custom domain exception hierarchy (AppException, Auth, NotFound, Conflict)
│   │   ├── permissions.py              # Permission documentation and operational tier specifications (Tiers 1-4)
│   │   ├── rate_limit.py               # RateLimiter interface, InMemory sliding window, and Redis ZSET implementation
│   │   ├── scheduler.py                # APScheduler setup running 24h background cleanups (tokens, unverified signups)
│   │   └── security.py                 # Bcrypt hashing, JWT creation/decoding, blacklist checks, FastAPI auth dependencies
│   ├── db/
│   │   ├── base.py                     # Async SQLAlchemy engine, AsyncSessionLocal sessionmaker, Base declarative class
│   │   └── session.py                  # get_db FastAPI dependency yielding AsyncSession per request
│   ├── models/
│   │   ├── __init__.py                 # Re-exports all models so SQLAlchemy metadata registers all mappers
│   │   ├── email_verification_token.py # EmailVerificationToken model (SHA-256 token hash, 24h expiry)
│   │   ├── leave.py                    # LeaveRequest model and LeaveStatus enum
│   │   ├── organization.py             # Organization model (status, is_internal, gst_number)
│   │   ├── revoked_token.py            # RevokedToken model for blacklisting invalidated JWT jtis
│   │   ├── task.py                     # Task model with optimistic locking version, TaskStatus, TaskPriority
│   │   └── user.py                     # User model with access_level (1-4), 10-digit random employee_code, org pointer
│   ├── routes/
│   │   ├── analytics.py                # Router for /analytics/performance (self, team, org, employee scoping)
│   │   ├── auth.py                     # Router for /auth (signup, verify-email, resend, login, refresh, logout, change-pwd)
│   │   ├── leaves.py                   # Router for /leaves (submit, list personal/org, list team, review approve/reject)
│   │   ├── tasks.py                    # Router for /tasks (CRUD, list team, status update, optimistic lock check)
│   │   └── users.py                    # Router for /users (me, direct reports, employee directory, provisioning, lockout)
│   ├── schemas/
│   │   ├── analytics.py                # Pydantic schemas: PerformanceStats, TrailItem
│   │   ├── leave.py                    # Pydantic schemas: LeaveCreate, LeaveRead, LeaveUpdateStatus
│   │   ├── task.py                     # Pydantic schemas: TaskCreate, TaskRead, TaskUpdate, TaskUpdateStatus
│   │   └── user.py                     # Pydantic schemas: UserRead, UserLogin, SignupRequest, EmployeeCreate, etc.
│   ├── services/
│   │   ├── analytics_service.py        # Server-side SQL conditional aggregations for performance metrics
│   │   ├── auth_service.py             # Authentication, dual-token revocation, lockout counting, unverified signup cleanup
│   │   ├── common.py                   # get_scoped_or_404 multi-tenant resource resolution utility
│   │   ├── leave_service.py            # Leave request business logic, date overlap checks, team leaves
│   │   ├── permission_service.py       # Direct report verification (can_manage_specific_user), tier checks, user caching
│   │   ├── task_service.py             # Task CRUD logic, assignment authority validation, version conflict raising
│   │   └── user_service.py             # 10-digit random user ID generation, temporary passwords, supervisor updates
│   └── main.py                         # FastAPI app instance, CORS middleware, lifespan scheduler, exception handlers
├── docs/
│   ├── BACKEND.md                      # Comprehensive backend architecture reference documentation
│   ├── FRONTEND.md                     # Comprehensive frontend architecture reference documentation
│   ├── screenshots/                    # Application UI screenshots (login, tasks, team, performance, leaves)
│   ├── INTERVIEW_PREP.md               # Technical interview notes and sync vs async trade-offs
│   ├── PROJECT_MASTERY.md              # Detailed architecture blueprint, feature map, and modification guide
│   ├── TEAMLOOM_SAAS_REQUIREMENTS.md   # SaaS specifications (Slices 1-11, multi-tenancy, Razorpay billing roadmap)
│   ├── archive/
│   │   └── test_report_2026_07_28.md   # Historical manual QA test run report from July 28, 2026 (54 tests)
│   └── test_results.json               # Raw JSON test run outputs from July 28, 2026
├── frontend/
│   ├── public/
│   │   ├── favicon.svg                 # Browser tab favicon
│   │   └── icons.svg                   # SVG icons sprite sheet
│   ├── src/
│   │   ├── assets/                     # Static assets (hero.png, react.svg, vite.svg)
│   │   ├── components/
│   │   │   ├── employees/
│   │   │   │   └── EmployeeFormModal.jsx # Admin employee provisioning modal (generates code, designation, tier)
│   │   │   ├── guards/
│   │   │   │   ├── AdminRoute.jsx      # Route guard restricting route to Tier 1 Admin
│   │   │   │   ├── DirectReportsRoute.jsx # Route guard restricting route to users managing direct reports
│   │   │   │   ├── PasswordChangeRoute.jsx # Route guard for /change-password
│   │   │   │   └── ProtectedRoute.jsx  # Route guard checking authentication and forced password change
│   │   │   ├── layout/
│   │   │   │   ├── AuthLayout.jsx      # Shared centered auth page wrapper with Deep Pine branding
│   │   │   │   ├── Navbar.jsx          # Top navigation bar with role-aware and report-aware links
│   │   │   │   └── UserMenu.jsx        # Profile avatar dropdown with designation, password change, and logout
│   │   │   ├── ui/                     # Deep Pine UI primitive components (Button, Input, Card, Modal, Spinner, etc.)
│   │   │   │   ├── Alert.jsx           # Dismissible status alert box
│   │   │   │   ├── Badge.jsx           # Color-coded pill badge for status and priority
│   │   │   │   ├── Button.jsx          # Configurable button with primary/secondary/danger variants
│   │   │   │   ├── Card.jsx            # Bordered dark card surface component
│   │   │   │   ├── DueCountdown.jsx    # Live 1-minute interval relative deadline ticker
│   │   │   │   ├── EmptyState.jsx      # Zero-state illustration and action container
│   │   │   │   ├── Input.jsx           # Form input with validation error states and password toggle
│   │   │   │   ├── Modal.jsx           # Backdrop modal wrapper with keyboard accessibility
│   │   │   │   ├── Select.jsx          # Custom styled HTML select dropdown
│   │   │   │   ├── Spinner.jsx         # Loading spinner SVG
│   │   │   │   └── Textarea.jsx        # Multi-line text field component
│   │   │   ├── LeaveForm.jsx           # Personal leave submission card with date pickers
│   │   │   ├── LeaveHistoryList.jsx    # Chronological personal leave request list
│   │   │   ├── LeaveRejectModal.jsx    # Admin modal for entering leave rejection rationale
│   │   │   ├── MilestoneTrail.jsx      # Colored circular dots representing recent task completion states
│   │   │   ├── PerformanceRing.jsx     # SVG circular on-time percentage gauge
│   │   │   ├── TaskCard.jsx            # Individual task card with priority, countdown, and status stepper
│   │   │   ├── TaskDeleteModal.jsx     # Admin task deletion confirmation modal
│   │   │   ├── TaskFormModal.jsx       # Task create/edit modal with HTTP 409 conflict reload handler
│   │   │   └── TaskList.jsx            # Filterable grid/list of tasks
│   │   ├── lib/
│   │   │   ├── api.js                  # Axios client with request bearer token injection & 401 refresh interceptor
│   │   │   └── dateUtils.js            # Date formatting utilities (ISO, local readable string, countdown)
│   │   ├── pages/
│   │   │   ├── AdminEmployeesPage.jsx  # Admin employee directory, supervisor assignment, deactivation (/admin/employees)
│   │   │   ├── AdminLeavesPage.jsx     # Admin leave review hub (/admin/leaves)
│   │   │   ├── AdminPerformancePage.jsx # Admin company-wide performance leaderboard (/admin/performance)
│   │   │   ├── AdminTasksPage.jsx      # Admin system-wide task management panel (/admin/tasks)
│   │   │   ├── ChangePasswordPage.jsx  # Forced or voluntary password change page (/change-password)
│   │   │   ├── DashboardPage.jsx       # Employee personal task dashboard (/dashboard)
│   │   │   ├── LeavesPage.jsx          # Employee personal leave request page (/leaves)
│   │   │   ├── LoginPage.jsx           # Dual-mode login page (Admin email / Employee User ID) (/login)
│   │   │   ├── MyPerformancePage.jsx   # Employee personal analytics page (/my-performance)
│   │   │   ├── MyTeamPage.jsx          # Supervisor direct reports, team tasks, team leaves view (/my-team)
│   │   │   ├── SignupPage.jsx          # Self-serve company & admin signup (/signup)
│   │   │   └── VerifyEmailPage.jsx     # Email verification confirmation page (/verify-email)
│   │   ├── store/
│   │   │   └── authStore.js            # Zustand store managing in-memory access token, user session, reports
│   │   ├── App.jsx                     # Top-level route switchboard and session bootstrap logic
│   │   ├── index.css                   # Tailwind v4 theme, Deep Pine color variables, global styles
│   │   └── main.jsx                    # React 19 client entrypoint mounting to #root
│   ├── .env                            # Frontend environment file (VITE_API_BASE_URL)
│   ├── Dockerfile                      # Container definition for frontend dev server (node:20-alpine)
│   ├── index.html                      # Single page application HTML shell
│   ├── package.json                    # Frontend npm dependencies and scripts
│   ├── README.md                       # Vite template README (unmodified)
│   └── vite.config.js                  # Vite configuration loading @tailwindcss/vite and @vitejs/plugin-react
├── scratch/                            # 34 diagnostic, recovery, and live-database test scripts used during development
├── scripts/
│   ├── diagnose_users.py               # Diagnostic script for checking seeded users and account lockouts
│   ├── init-test-db.sh                 # PostgreSQL container entrypoint script creating test database
│   ├── reset_passwords.py              # Administrative script for resetting employee passwords
│   ├── run_qa_suite.py                 # HTTP API test runner executing 54 legacy QA test cases
│   ├── seed_admin.py                   # Interactive or env-driven CLI to seed the first Administrator
│   ├── test_endpoints.py               # Lightweight smoke-test script (partially outdated: calls /auth/register)
│   └── unlock_user.py                  # CLI utility to clear failed login attempts and unlock a user
├── tests/                              # Pytest test suite (19 files, 205 test cases)
│   ├── conftest.py                     # Central test fixtures, safety guards, PostgreSQL Docker engine, test DB setup
│   ├── test_analytics.py               # Performance stats scoping tests (self, team, org, employee)
│   ├── test_auth.py                    # Auth tests (login modes, lockout, refresh, logout revocation, password change)
│   ├── test_concurrency.py             # Concurrency tests (optimistic locking conflicts, user code collision retries)
│   ├── test_direct_report_scoping.py   # Manager hierarchy and direct report scoping tests
│   ├── test_employee_creation.py       # 10-digit random User ID generation and validation tests
│   ├── test_leaves.py                  # Personal and team leave requests, approval/rejection workflows
│   ├── test_login_security.py          # Lockout thresholds, rate limiting, constant-time dummy verification
│   ├── test_model_registry.py          # Fresh-subprocess mapper initialization regression test
│   ├── test_rbac.py                    # Tier access level enforcement and direct reporting boundary tests
│   ├── test_services.py                # Direct domain service layer tests
│   ├── test_slice2_migration.py        # Migration reversibility and data backfill test for organizations
│   ├── test_slice2_organizations.py    # Organization model and multi-tenant scoping unit tests
│   ├── test_slice3_isolation.py        # Cross-tenant data isolation and anti-enumeration tests (A1-A10)
│   ├── test_slice4a_migration.py       # Migration test for 10-digit user IDs, lower(email) unique index
│   ├── test_slice4c_migration.py       # Migration test for email verification backfill
│   ├── test_slice4c_signup_verification.py # Signup, token generation, email verification endpoint tests
│   ├── test_tasks.py                   # Task CRUD, versioning, completed_at, and sorting tests
│   └── test_users.py                   # User profile, reports-to hierarchy updates, and deactivation tests
├── .coverage                           # SQLite coverage data file from test runs
├── .dockerignore                       # Excludes git, venv, caches, and test artifacts from Docker build
├── .env                                # Local environment file with active secrets and database credentials
├── .env.example                        # Template environment configuration with documentation
├── .gitattributes                      # Git line ending normalization configuration
├── .gitignore                          # Git exclusion list (excludes .env, private docs, caches, dumps)
├── .pre-commit-config.yaml             # Pre-commit hooks for black, ruff, mypy
├── alembic.ini                         # Alembic configuration pointing to alembic/ directory
├── backup_before_4c.sql                # SQL database dump captured prior to Slice 4c migration
├── docker-compose.yml                  # 4-service Docker Compose configuration (db, redis, app, frontend)
├── docker-entrypoint.sh                # Container startup script executing 'alembic upgrade head' before uvicorn
├── Dockerfile                          # Multi-stage production container build for FastAPI backend (python:3.12-slim)
├── postman_collection.json             # Postman API test collection
├── pyproject.toml                      # Tooling configuration for Black, Ruff, Mypy, and Pytest
├── README.md                           # Main repository README
├── requirements-dev.txt                # Development and test dependencies (black, ruff, mypy, pytest, httpx)
├── requirements.txt                    # Production backend Python dependencies
└── teamloom_backup_before_slice4a.dump # Binary PostgreSQL database dump captured prior to Slice 4a
```

---

### 1.3 Entry Points
1. **Backend ASGI Application Entry Point**:
   - **File**: `app/main.py`
   - **Bootstrap**: Defines `app = FastAPI(title="Teamloom API", lifespan=lifespan)`.
   - **Lifespan Routine**: Calls `start_scheduler()` on startup (which registers APScheduler jobs for 24h token revocation pruning and 7d unverified signup cleanup) and `shutdown_scheduler()` on shutdown.
   - **Middleware**: Registers `CORSMiddleware` reading `settings.CORS_ORIGINS` and exposing `X-Total-Count` headers.
   - **Routers**: Explicitly includes routers from `auth`, `users`, `tasks`, `leaves`, and `analytics`.
   - **Server Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
     ```
   - **Container Start Command**: Handled via `docker-entrypoint.sh`, which runs `alembic upgrade head` before executing `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

2. **Frontend SPA Entry Point**:
   - **HTML Entry**: `frontend/index.html` (mounts `<div id="root"></div>` and loads `/src/main.jsx`).
   - **JavaScript Entry**: `frontend/src/main.jsx` (creates React 19 root and renders `<App />`).
   - **Routing & State Bootstrap**: `frontend/src/App.jsx`. On initial render, executes `refreshSession()` from `useAuthStore` to restore authenticated sessions from the `httpOnly` refresh token cookie via `POST /auth/refresh`.

---

### 1.4 Monorepo / Multi-Package Layout
The codebase is a unified monorepo organized into two primary application packages and support tooling:
- **Backend Service (`/app`)**: Standalone Python FastAPI application. Uses standard Python packaging (`requirements.txt`, `pyproject.toml`).
- **Frontend SPA (`/frontend`)**: Standalone Vite + React 19 application. Uses Node.js package management (`frontend/package.json`).
- **Database Migrations (`/alembic`)**: Standalone Alembic migration environment sharing database models with `app/models`.
- **Infrastructure Orchestration (`docker-compose.yml`)**: Coordinates 4 local container services (`db`, `redis`, `app`, `frontend`).

---

## PART 2: Tech Stack and Tooling

### 2.1 Languages, Frameworks, and Libraries (Exact Versions)

#### Backend Runtime & Libraries (from `requirements.txt`, `requirements-dev.txt`, and active environment `pip list`):
| Category | Package Name | Specified in Manifest | Exact Installed Version in Environment | Purpose |
|---|---|---|---|---|
| **Language** | Python | `>=3.11` | `3.11.9` | Primary backend runtime |
| **Framework** | `fastapi` | `>=0.110.0` | `0.139.2` | High-performance ASGI REST API framework |
| **ASGI Server** | `uvicorn` | `>=0.28.0` | `0.51.0` | Asynchronous ASGI server |
| **ORM** | `sqlalchemy` | `>=2.0.28` | `2.0.43` | Declarative 2.0 async SQL ORM |
| **DB Driver** | `asyncpg` | `>=0.29.0` | `0.31.0` | High-throughput asynchronous PostgreSQL driver |
| **Migrations** | `alembic` | `>=1.13.1` | `1.18.5` | Database schema migrations |
| **Security** | `bcrypt` | `>=4.1.2` | `5.0.0` | Password hashing algorithm |
| **Tokens** | `pyjwt[crypto]` | `>=2.8.0` | `2.13.0` (with `cryptography 49.0.0`) | JWT signing and validation |
| **Validation** | `pydantic` | `>=2.6.4` | `2.11.10` | Request/response schema validation (v2) |
| **Settings** | `pydantic-settings`| `>=2.2.1` | `2.14.2` | Type-safe environment management |
| **Email Validation** | `email-validator` | `>=2.1.0` | `2.3.0` | RFC 5322 email string validation |
| **Environment** | `python-dotenv` | `>=1.0.1` | `1.2.2` | `.env` file loader |
| **Form Parsing** | `python-multipart` | `>=0.0.7` | `0.0.32` | Multipart form parsing (Swagger UI OAuth2) |
| **Caching/Limits** | `redis` | `>=5.0.0` | `8.1.0` | Redis client for distributed rate limiting |
| **Cache Testing** | `fakeredis` | `>=2.20.0` | `2.38.0` | In-memory Redis simulation for unit tests |
| **Scheduling** | `apscheduler` | `>=3.10.4` | `3.11.3` | In-process background job scheduler |
| **Async Coroutine** | `greenlet` | `>=3.0.3` | `3.2.4` | SQLAlchemy async greenlet execution engine |
| **Dev / Testing** | `pytest` | `>=8.0.0` | `9.1.1` | Test framework |
| **Dev / Testing** | `pytest-asyncio` | `>=0.23.5` | `1.4.0` | Asynchronous test execution plugin |
| **Dev / Testing** | `pytest-cov` | `>=4.1.0` | `7.1.0` | Code coverage reporting plugin |
| **Dev / Testing** | `httpx` | `>=0.27.0` | `0.28.1` | Async HTTP client for ASGI test transport |
| **Dev / Linting** | `black` | `>=24.2.0` | `26.5.1` | Code formatter |
| **Dev / Linting** | `ruff` | `>=0.3.0` | `0.16.0` | Fast Python linter and import sorter |
| **Dev / Typing** | `mypy` | `>=1.8.0` | `2.3.0` | Static type checker |

#### Frontend Runtime & Libraries (from `frontend/package.json`):
| Category | Package Name | Manifest Constraint | Exact Installed Version (`node_modules`) | Purpose |
|---|---|---|---|---|
| **Runtime** | Node.js | Unknown / Not in `package.json` | `v24.12.0` (Host), `20-alpine` (Docker) | JavaScript runtime |
| **Package Manager**| npm | Unknown / Not in `package.json` | `11.6.2` | Node package manager |
| **UI Library** | `react` | `^19.2.8` | `19.2.8` | Core UI component model |
| **DOM Renderer** | `react-dom` | `^19.2.8` | `19.2.8` | React DOM rendering engine |
| **Routing** | `react-router-dom` | `^7.18.2` | `7.18.2` | Client-side routing with layout guards |
| **State Store** | `zustand` | `^5.0.15` | `5.0.15` | Lightweight in-memory state management |
| **HTTP Client** | `axios` | `^1.19.0` | `1.19.0` | Promise HTTP client with interceptors |
| **Styling** | `tailwindcss` | `^4.3.3` | `4.3.3` | Utility-first CSS engine |
| **Vite Tailwind** | `@tailwindcss/vite` | `^4.3.3` | `4.3.3` | Native Tailwind CSS plugin for Vite |
| **Icons** | `lucide-react` | `^1.31.0` | `1.31.0` | Micro SVG icon library |
| **Linter** | `oxlint` | `^1.75.0` | `1.75.0` | High-performance JavaScript/JSX linter |
| **Build Tool** | `vite` | `^8.2.0` | `8.2.1` | Frontend build bundler and dev server |
| **React Plugin** | `@vitejs/plugin-react` | `^6.0.4` | `6.0.4` | Babel/Oxc fast refresh plugin for Vite |

---

### 2.2 Build Tools, Bundlers, Linters, Formatters
- **Backend Linter**: `ruff` (configured in `pyproject.toml` with `select = ["E", "W", "F", "I", "UP"]`, line length 100).
  - *Current Status*: Running `ruff check .` found 78 style/import ordering errors (58 auto-fixable with `--fix`). No functional bugs.
- **Backend Formatter**: `black` (configured in `pyproject.toml` with line-length 100, target Python 3.12).
- **Backend Type Checker**: `mypy` (configured in `pyproject.toml` with `python_version = "3.12"`, `ignore_missing_imports = true`).
- **Frontend Linter**: `oxlint` (configured via `npm run lint`).
  - *Current Status*: Running `oxlint` executed across 46 files in 128ms, finding **0 errors** and **1 warning** (unused import `api` in `frontend/src/pages/AdminPerformancePage.jsx:2:10`).
- **Frontend Bundler**: `vite v8.2.1`. Running `npm run build` completed cleanly in 2.84s producing production chunks (`dist/assets/index-Ci3O6Ekr.css` 31.76 kB, `dist/assets/index-1rK9fJ6U.js` 416.08 kB).

---

### 2.3 Runtime Requirements
- **Python**: `>=3.11` (Host: `3.11.9`, Dockerfile: `3.12-slim`, GitHub Actions: `3.12`).
- **Node.js**: `>=18.0.0` (Host: `v24.12.0`, Dockerfile: `20-alpine`).
- **PostgreSQL**: PostgreSQL 16 (specifically `postgres:16-alpine` in Docker).
- **Redis**: Optional in dev (`RATE_LIMITER_BACKEND=memory`), required for horizontally scaled multi-worker production (`RATE_LIMITER_BACKEND=redis`). Docker specifies `redis:7-alpine`.
- **OS Dependencies**: When building the backend outside Docker on Linux, requires `gcc` and `libpq-dev`. On Windows, pre-compiled wheels for `asyncpg` and `bcrypt` are installed without requiring a local C toolchain.

---

### 2.4 Dependency Vulnerability and Audit Status
- **npm audit**: Running `npm audit` inside the sandboxed environment was blocked due to external network restrictions (`403 Forbidden - Request to POST /-/npm/v1/security/advisories/bulk on registry.npmjs.org not allowed by policy`). *Status: Needs confirmation in an unsandboxed network environment.*
- **Unused Packages Identified**:
  - `passlib` is mentioned in `README.md` ("Passlib / Bcrypt password hashing") but is **not** present in `requirements.txt` or `app/core/security.py` (which directly uses the native `bcrypt` package).
  - In `frontend/src/pages/AdminPerformancePage.jsx`, `api` is imported but never referenced.
- **Deprecated Constructs in Code**:
  - `User.role` column (`SQLEnum(UserRole)`) is marked as `DEPRECATED` in `app/models/user.py` ("Use access_level instead") but is still referenced in legacy route handlers, token generation, and schemas for backward compatibility.

---

## PART 3: Application Flow and Functionality

### 3.1 End-to-End Request Traversal
A representative user action (e.g., an Administrator creating a new employee task) follows this path:
```text
[ Browser / React 19 UI ]
       │ 1. User fills TaskFormModal and clicks "Create Task"
       │ 2. Axios client (lib/api.js) intercepts request, injects Authorization: Bearer <accessToken>
       ▼
[ FastAPI Server (app/main.py) ]
       │ 3. CORSMiddleware validates origin and headers
       │ 4. Route handler matched: POST /tasks/ (app/routes/tasks.py)
       │ 5. Dependency require_password_change_cleared:
       │    a. Calls get_current_user (app/core/security.py)
       │    b. Decodes JWT access token using settings.JWT_SECRET_KEY
       │    c. Queries revoked_tokens table for token jti (blacklist check)
       │    d. Queries users table for actor user by lower(email)
       │    e. Validates user.is_active is True
       │    f. Validates user.must_change_password is False
       ▼
[ Business Logic Layer (app/services/task_service.py) ]
       │ 6. Validates assignee exists in creator's organization via get_scoped_or_404
       │ 7. Evaluates assignment authority via can_manage_specific_user(creator, assignee):
       │    - If creator.access_level == 1 (Admin) -> Granted
       │    - If assignee.reports_to_id == creator.id -> Granted
       │    - Otherwise -> Raises AuthorizationException (403)
       │ 8. Instantiates Task model with version=1, organization_id=creator.organization_id
       ▼
[ Async Database Layer (app/db/session.py -> PostgreSQL) ]
       │ 9. db.add(db_task) -> await db.commit() -> await db.refresh(db_task)
       ▼
[ Response Serialization & Client Update ]
       │ 10. Serialized into TaskRead Pydantic model (including integer version)
       │ 11. Returned as JSON with HTTP 201 Created
       │ 12. Frontend UI appends task to state without full page reload
```

---

### 3.2 Complete Feature Inventory & Implementation Status

| Feature Name | Primary Files | Status | Evidence / Notes |
|---|---|---|---|
| **Dual-Mode Authentication** | `app/routes/auth.py`<br>`frontend/src/pages/LoginPage.jsx` | **Complete and working** | Server enforces Admin (email + tier 1) and Employee (10-digit code + tier > 1). Anti-enumeration dummy bcrypt timing. |
| **Token Refresh & Rotation** | `app/routes/auth.py`<br>`app/services/auth_service.py` | **Complete and working** | `POST /auth/refresh` rotates refresh token in httpOnly cookie and invalidates old refresh token in `revoked_tokens`. |
| **Dual-Token Logout Revocation** | `app/routes/auth.py`<br>`app/models/revoked_token.py` | **Complete and working** | `POST /auth/logout` revokes both Bearer access token and cookie refresh token jti entries. Continuous check in `get_current_user`. |
| **Account Lockout Defense** | `app/services/auth_service.py`<br>`app/core/rate_limit.py` | **Complete and working** | Locks account for 15 minutes after 5 consecutive failed attempts. In-memory sliding window limits IP to 10 requests / 15 min. |
| **Self-Serve Company Signup** | `app/routes/auth.py`<br>`frontend/src/pages/SignupPage.jsx` | **Complete and working** | Creates Organization (`pending_payment`) and first Tier-1 Admin. Background dispatch of single-use email verification link. |
| **Email Verification** | `app/routes/auth.py`<br>`frontend/src/pages/VerifyEmailPage.jsx` | **Complete and working** | POST-only verification (`/auth/verify-email`) preventing email scanner prefetching. Anti-enumeration resend endpoint. |
| **Forced Initial Password Change** | `app/routes/auth.py`<br>`frontend/src/pages/ChangePasswordPage.jsx` | **Complete and working** | Intercepted via `require_password_change_cleared` returning 403 `password_change_required`. Frontend redirects without layout flash. |
| **Employee Provisioning** | `app/routes/users.py`<br>`frontend/src/pages/AdminEmployeesPage.jsx` | **Complete and working** | Generates random 10-digit numeric codes with collision retry loop. Hashes password in threadpool, sends welcome email in background. |
| **Manager-Direct Report Scoping** | `app/services/permission_service.py`<br>`frontend/src/pages/MyTeamPage.jsx` | **Complete and working** | Supervisor relationship (`reports_to_id`) enables `/my-team` roster, team tasks, team leaves view, and delegated task creation. |
| **Optimistic Task Locking** | `app/services/task_service.py`<br>`frontend/src/components/TaskFormModal.jsx` | **Complete and working** | `version` column checked on update. HTTP 409 Conflict triggers client reload dialog preventing silent overwrites. |
| **Leave Request & Review** | `app/routes/leaves.py`<br>`frontend/src/pages/AdminLeavesPage.jsx` | **Complete and working** | Employee submission with date overlap prevention. Tier 1 Admin only approval/rejection. Supervisors have view-only team access. |
| **Performance Analytics** | `app/services/analytics_service.py`<br>`frontend/src/pages/MyPerformancePage.jsx` | **Complete and working** | Server-side SQL conditional aggregations for on-time rate, classified counts, and milestone trails. Scoped by `self`, `team`, `org`, `employee`. |
| **Multi-Tenant Data Isolation** | `app/services/common.py`<br>`tests/test_slice3_isolation.py` | **Complete and working** | All queries filter by `organization_id`. Cross-tenant lookups by ID return 404 anti-enumeration (X4). |
| **Background Cleanup Jobs** | `app/core/scheduler.py` | **Complete and working** | APScheduler runs every 24h: deletes expired revoked tokens and deletes unverified signups older than 7 days. |
| **Employee Invite Flow (Slice 4e)** | Not yet created | **Stubbed / Pending** | Tracked in `TEAMLOOM_SAAS_REQUIREMENTS.md` as Slice 4e. Intended to replace temporary passwords with set-password invite links. |
| **Subscription & Billing (Slices 6-9)** | Not yet created | **Stubbed / Pending** | Tracked in `TEAMLOOM_SAAS_REQUIREMENTS.md`. Razorpay checkout, pack selection, seat limits, and webhook listeners not yet written. |
| **Server-Side Pagination Controls** | `frontend/src/pages/AdminTasksPage.jsx`<br>`AdminLeavesPage.jsx` | **Partially implemented** | Backend supports `skip` and `limit` with `X-Total-Count` header, but frontend pages hardcode `limit=100` without page pagination UI. |
| **Admin Reset Password UI** | `app/routes/users.py:178` | **Partially implemented** | `POST /users/{id}/reset-temp-password` exists and works on backend, but has no button in `AdminEmployeesPage.jsx`. |
| **Legacy QA CLI Scripts** | `scripts/test_endpoints.py` | **Broken** | Line 52 calls `POST /auth/register` which was removed in Slice 4a/4c (replaced by `/auth/signup`). Fails with 404/405. |

---

### 3.3 Complete Route / Endpoint / Page Inventory

#### Backend API Routes:
| HTTP Method | Path | Auth Required | Permissions / Tier | Purpose |
|---|---|---|---|---|
| `GET` | `/` | No | Public | Root welcome message and API metadata |
| `GET` | `/docs` | No | Public | Swagger UI interactive API documentation |
| `GET` | `/redoc` | No | Public | ReDoc API documentation |
| `GET` | `/openapi.json` | No | Public | OpenAPI 3.1 specification schema |
| `POST` | `/auth/signup` | No | Public (Rate limited) | Create new organization and Tier-1 admin account |
| `POST` | `/auth/verify-email` | No | Public | Verify admin email using single-use SHA-256 token |
| `POST` | `/auth/resend-verification` | No | Public (Rate limited) | Resend email verification link with anti-enumeration |
| `POST` | `/auth/login` | No | Public (Rate limited) | Dual-mode login (Admin email or Employee User ID) |
| `POST` | `/auth/swagger-login` | No | Public (Form data) | OAuth2 password request form for Swagger UI |
| `POST` | `/auth/refresh` | No | Public (Cookie required) | Silent token refresh exchanging refresh cookie for access token |
| `POST` | `/auth/logout` | Yes | Authenticated | Dual-token revocation and refresh cookie deletion |
| `POST` | `/auth/change-password` | Yes | Authenticated (must_change_password permitted) | Updates password and clears must_change_password flag |
| `GET` | `/users/me` | Yes | Password change cleared | Current user profile with direct report IDs |
| `PATCH` | `/users/me` | Yes | Password change cleared | Update profile details (full_name, designation) |
| `GET` | `/users/me/reports` | Yes | Password change cleared | List direct report employees managed by current user |
| `GET` | `/users/{user_id}/direct-reports`| Yes | Tier 1 Admin or supervisor user | List direct reports for a specific supervisor ID |
| `GET` | `/users/` | Yes | Tier 1 Admin only | List all employees in the admin's organization |
| `POST` | `/users/employees` | Yes | Tier 1 Admin only | Provision new employee account with 10-digit ID |
| `POST` | `/users/{user_id}/reset-temp-password`| Yes | Tier 1 Admin only | Reset employee temp password and email credentials |
| `PATCH` | `/users/{user_id}/reports-to` | Yes | Tier 1 Admin only | Set or change an employee's supervisor |
| `PATCH` | `/users/{user_id}/deactivate` | Yes | Tier 1 Admin only | Soft deactivation (`is_active=False`) |
| `PATCH` | `/users/{user_id}/reactivate` | Yes | Tier 1 Admin only | Reactivate employee account (`is_active=True`) |
| `POST` | `/tasks/` | Yes | Tier 1 Admin or direct supervisor | Create task assigned to employee |
| `GET` | `/tasks/` | Yes | Password change cleared | List tasks (Admin sees org-wide; Employee sees assigned) |
| `GET` | `/tasks/team` | Yes | Password change cleared | List tasks assigned to current user's direct reports |
| `GET` | `/tasks/{id}` | Yes | Admin or assigned employee | Get single task details |
| `PATCH` | `/tasks/{id}` | Yes | Admin, supervisor, or assigned | Update task (version checked for 409 conflict) |
| `DELETE` | `/tasks/{id}` | Yes | Tier 1 Admin only | Delete task |
| `POST` | `/leaves/` | Yes | Password change cleared | Submit personal leave request with date overlap checks |
| `GET` | `/leaves/` | Yes | Password change cleared | List leaves (Admin sees org-wide; Employee sees own) |
| `GET` | `/leaves/team` | Yes | Password change cleared | View-only list of direct reports' leave requests |
| `PATCH` | `/leaves/{id}` | Yes | Tier 1 Admin only | Approve or reject leave request |
| `GET` | `/analytics/performance` | Yes | Password change cleared | Retrieve performance analytics (self, team, org, employee) |

#### Frontend Routes / Pages:
| Route Path | Page Component | Guard / Access Level | Purpose |
|---|---|---|---|
| `/login` | `LoginPage.jsx` | Public | Dual-mode login with toggle, anti-enumeration resend helper |
| `/signup` | `SignupPage.jsx` | Public | Self-serve company registration |
| `/verify-email` | `VerifyEmailPage.jsx` | Public | Consumes single-use token from query param |
| `/change-password` | `ChangePasswordPage.jsx` | `PasswordChangeRoute` | Forced initial password change or voluntary profile change |
| `/dashboard` | `DashboardPage.jsx` | `ProtectedRoute` | Employee personal task management grid |
| `/leaves` | `LeavesPage.jsx` | `ProtectedRoute` | Personal leave request submission and timeline |
| `/my-performance` | `MyPerformancePage.jsx` | `ProtectedRoute` | Personal on-time rate gauge and milestone trail |
| `/my-team` | `MyTeamPage.jsx` | `DirectReportsRoute` | Supervisor portal (roster, team tasks, team leaves) |
| `/admin/tasks` | `AdminTasksPage.jsx` | `AdminRoute` (Tier 1) | System-wide task control panel with polling |
| `/admin/leaves` | `AdminLeavesPage.jsx` | `AdminRoute` (Tier 1) | System-wide leave approval/rejection queue |
| `/admin/employees` | `AdminEmployeesPage.jsx` | `AdminRoute` (Tier 1) | Employee provisioning, supervisor assignment, deactivation |
| `/admin/performance` | `AdminPerformancePage.jsx` | `AdminRoute` (Tier 1) | Company-wide performance leaderboard and metrics |
| `/` & `*` | `RootRedirect` | Dynamic redirect | Redirects based on auth status and role (`/dashboard` vs `/admin/tasks`) |

---

### 3.4 State Management, Background Jobs, Queues & Webhooks
- **Frontend State Management**: Managed via **Zustand** in `frontend/src/store/authStore.js`. Holds in-memory `accessToken`, authenticated `user` object, `directReports` array, `isAuthenticated`, and `isLoading`. Avoids storing tokens in `localStorage` to defend against XSS token exfiltration.
- **Background Jobs (In-Process)**:
  - **Framework**: `APScheduler` (`AsyncIOScheduler`) in `app/core/scheduler.py`.
  - **Job 1**: `run_cleanup_expired_tokens` — Runs every 24 hours to delete expired rows from `revoked_tokens`.
  - **Job 2**: `run_cleanup_unverified_signups` — Runs every 24 hours to delete unverified signups and empty organizations older than 7 days (`User.created_at < now - 7d` and `Organization.status == 'pending_payment'`).
- **Background Tasks (Request-Bound)**:
  - Uses FastAPI `BackgroundTasks` to send emails asynchronously outside the request-response cycle (`send_verification_email`, `send_employee_welcome_email`), preventing slow SMTP roundtrips from delaying HTTP responses.
- **Queues**: No external worker queue (like Celery, RQ, or BullMQ) is implemented. All background tasks run in-process via `asyncio` or `BackgroundTasks`.
- **Webhooks**: None currently implemented. (Payment webhooks for Razorpay are planned for Slice 7).
- **Real-Time Features**: No WebSockets or Server-Sent Events (SSE). Client updates rely on HTTP polling (e.g., `AdminTasksPage.jsx` polls every 10 seconds via `setInterval`).

---

### 3.5 Codebase Search for Debt & Artifacts
A recursive search across all source directories (`app/`, `frontend/src/`, `tests/`, `scripts/`, `alembic/`) revealed:
- **`TODO` / `FIXME` / `XXX`**: **0 occurrences** found in application code. The only occurrences of `"HACK"` were string literals in test cases simulating malicious payloads (`tests/test_tasks.py:179` and `scripts/run_qa_suite.py:908` with `json={"title": "Hacked Title"}`).
- **Commented-Out Code Blocks**:
  - `frontend/src/pages/AdminEmployeesPage.jsx`: Commented-out test notes around modal submission.
  - `scripts/diagnose_users.py`: Contains commented-out fallback logic.
- **Unused Files & Test Artifacts**:
  - `backup_before_4c.sql`: 56 KB raw SQL dump left in project root.
  - `teamloom_backup_before_slice4a.dump`: 24 KB binary PostgreSQL dump in project root.
  - `docs/test_results.json`: 56 KB test output from July 28, 2026.
  - `scratch/`: Contains 34 ad-hoc python scripts used during iterative feature development.
  - `frontend/README.md`: Unmodified Vite template boilerplate.

---

## PART 6: Configuration, Environments and Integrations

### 6.1 Environment Variables Inventory

| Variable Name | Purpose | Required / Optional | Consumed By |
|---|---|---|---|
| `DATABASE_URL` | Async connection string for PostgreSQL app database | **Required** | `app/core/config.py`, `app/db/base.py`, `alembic/env.py` |
| `TEST_DATABASE_URL` | Async connection string for isolated pytest test database | Optional (defaults to port 5433) | `tests/conftest.py` |
| `POSTGRES_USER` | PostgreSQL superuser username | Optional (Docker default: `postgres`) | `docker-compose.yml`, `scripts/init-test-db.sh` |
| `POSTGRES_PASSWORD` | PostgreSQL superuser password | Optional (Docker default: `postgres`) | `docker-compose.yml`, `scripts/init-test-db.sh` |
| `POSTGRES_DB` | PostgreSQL default database name | Optional (Docker default: `employee_task_db`) | `docker-compose.yml`, `scripts/init-test-db.sh` |
| `JWT_SECRET_KEY` | HMAC-SHA256 secret key for signing short-lived access tokens | **Required** | `app/core/config.py`, `app/core/security.py` |
| `JWT_REFRESH_SECRET_KEY`| HMAC-SHA256 secret key for signing long-lived refresh tokens | **Required** | `app/core/config.py`, `app/core/security.py` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Expiration lifetime of access tokens | Optional (default: `15`) | `app/core/config.py`, `app/core/security.py` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiration lifetime of refresh tokens | Optional (default: `7`) | `app/core/config.py`, `app/core/security.py` |
| `COOKIE_SECURE` | Whether refresh token cookie requires HTTPS (`Secure` flag) | Optional (default: `False` for dev) | `app/core/config.py`, `app/routes/auth.py` |
| `LOG_LEVEL` | Application logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | Optional (default: `INFO`) | `app/core/config.py`, `app/main.py` |
| `CORS_ORIGINS` | JSON list or comma-delimited allowed origins for CORS | Optional (default: `["http://localhost:3000"]`)| `app/core/config.py`, `app/main.py` |
| `TRUSTED_PROXY_IPS` | IP list of reverse proxies trusted for `X-Forwarded-For` header | Optional (default: `[]`) | `app/core/config.py`, `app/routes/auth.py` |
| `RATE_LIMITER_BACKEND` | Switch between `memory` and `redis` rate limit storage | Optional (default: `memory`) | `app/core/config.py`, `app/core/rate_limit.py` |
| `REDIS_URL` | Redis connection URL for distributed rate limiting | Optional (default: `redis://localhost:6379/0`) | `app/core/config.py`, `app/core/rate_limit.py` |
| `EMAIL_BACKEND` | Switch between `auto`, `smtp`, and `console` email senders | Optional (default: `auto`) | `app/core/config.py`, `app/core/email.py` |
| `EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS`| Expiration time for email verification tokens | Optional (default: `24`) | `app/core/config.py`, `app/services/auth_service.py` |
| `EMAIL_VERIFICATION_URL`| Base URL for verification link | Optional (falls back to `{FRONTEND_URL}/verify-email`) | `app/core/config.py`, `app/core/email.py` |
| `SMTP_HOST` | Outgoing SMTP mail server hostname | Optional (e.g. `smtp.gmail.com`) | `app/core/config.py`, `app/core/email.py` |
| `SMTP_PORT` | Outgoing SMTP server port | Optional (default: `587`) | `app/core/config.py`, `app/core/email.py` |
| `SMTP_USERNAME` | SMTP authentication username / sender email | Optional | `app/core/config.py`, `app/core/email.py` |
| `SMTP_APP_PASSWORD` | SMTP authentication app password | Optional | `app/core/config.py`, `app/core/email.py` |
| `SMTP_FROM_EMAIL` | Display sender email address in email headers | Optional (falls back to `SMTP_USERNAME`) | `app/core/config.py`, `app/core/email.py` |
| `FRONTEND_URL` | Base URL of frontend client for email links | Optional (default: `http://localhost:5173`) | `app/core/config.py`, `app/core/email.py` |
| `VITE_API_BASE_URL` | Base backend API endpoint for Axios client | Optional (default: `http://localhost:8000`) | `frontend/.env`, `frontend/src/lib/api.js` |

*Note: In local `.env`, sensitive values (`JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, `POSTGRES_PASSWORD`, `SMTP_APP_PASSWORD`) were confirmed present and are masked for security.*

---

### 6.2 Third-Party Services and Integrations
1. **Email Service (SMTP / Transactional Email)**:
   - **Integration Point**: `app/core/email.py`.
   - **Implementation**: Uses Python's standard `smtplib` and `email.mime` modules connecting over STARTTLS (port 587).
   - **Supported Modes**: Configurable via `EMAIL_BACKEND`:
     - `smtp`: Uses real SMTP credentials (`SMTP_HOST`, `SMTP_USERNAME`, `SMTP_APP_PASSWORD`).
     - `console`: Logs email details (subject, recipient, links) directly to standard output via Python logger (safe for dev/test).
     - `auto`: Uses SMTP if host/credentials are supplied; otherwise silently falls back to console logging.
2. **Payment Gateway**:
   - **Status**: Not yet integrated in code. Architecture requirements in `TEAMLOOM_SAAS_REQUIREMENTS.md` specify Razorpay (INR payments, webhook signatures, idempotency tables) for Slices 6-9.
3. **External File Storage**: None. The app does not currently collect or store binary file uploads (avatars, attachments, invoices). Invoices are planned as generated PDFs in Slice 9.
4. **Error Tracking & Monitoring**: None (no Sentry, Datadog, or OpenTelemetry configured).

---

### 6.3 Environment Differences (Dev vs Production)
- **Database**: Development uses Dockerized PostgreSQL 16 on `localhost:5433` (mapped from container port 5432). Production requires a managed PostgreSQL instance with SSL enabled.
- **Cookies**: `COOKIE_SECURE` is `False` in development (allowing HTTP cookies on `localhost`) and must be `True` in production (requiring HTTPS).
- **Rate Limiting**: Development defaults to `RATE_LIMITER_BACKEND=memory`. Multi-worker production requires `RATE_LIMITER_BACKEND=redis` to prevent rate limit bypass across container replicas.
- **Email**: Development can operate with `EMAIL_BACKEND=console`. Production requires a verified transactional SMTP host (e.g., SendGrid, AWS SES, Postmark) with SPF/DKIM/DMARC records configured.

---

### 6.4 Deployment Setup & Step-by-Step Local Setup Guide

#### Deployment Architecture:
- **`Dockerfile`**: Implements a clean 2-stage build:
  - Stage 1 (`builder`): `python:3.12-slim`, installs `gcc` and `libpq-dev`, compiles wheels into `/install`.
  - Stage 2 (`runtime`): `python:3.12-slim`, installs runtime `libpq5` and `netcat`, creates non-root user `appuser` (UID 1001), copies `/install` to `/usr/local`.
- **`docker-compose.yml`**: Defines 4 interconnected services:
  - `db`: `postgres:16-alpine`, exposed on host `5433:5432`, data persisted in named volume `postgres_data`. Runs `scripts/init-test-db.sh` on init.
  - `redis`: `redis:7-alpine`, exposed on host `6379:6379`.
  - `app`: Builds root `Dockerfile`, depends on healthy `db` and `redis`, exposed on `8000:8000`.
  - `frontend`: Builds `frontend/Dockerfile`, exposed on `5173:5173`.
- **CI/CD Pipeline (`.github/workflows/ci.yml`)**:
  - Triggers on push/PR to `main`, `master`, `dev`, `feat/**`, `fix/**`.
  - Spins up PostgreSQL 16 service container, installs dependencies, creates database `employee_task_db`, executes `alembic upgrade head`, and runs `pytest --cov=app`.

#### Step-by-Step Guide to Run Locally From Scratch:

##### Prerequisites:
- Python 3.11 or 3.12
- Node.js 18+ and npm
- Docker Desktop (or local PostgreSQL 16 and Redis instances)

##### Step 1: Clone and Configure Environment
```bash
git clone <repo-url>
cd "Employee Task Management"

# Create .env from template
cp .env.example .env
# Ensure JWT secrets are populated with random hex keys:
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('JWT_REFRESH_SECRET_KEY=' + secrets.token_hex(32))"
```

##### Step 2: Option A — Launch via Docker Compose (Recommended)
```bash
docker compose up --build -d
```
The services will be available at:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`

Seed initial System Administrator:
```bash
docker compose exec -e ADMIN_EMAIL="admin@example.com" -e ADMIN_PASSWORD="adminpassword123" app python scripts/seed_admin.py
```

##### Step 3: Option B — Run Manually (Local Host Processes)
```bash
# 1. Start PostgreSQL (e.g. via Docker for the DB only)
docker compose up -d db redis

# 2. Setup Python virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
# source venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Run database migrations to head
alembic upgrade head

# 5. Seed initial admin user
python scripts/seed_admin.py

# 6. Start FastAPI development server
uvicorn app.main:app --reload --port 8000

# 7. Start Frontend development server (in separate terminal)
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

