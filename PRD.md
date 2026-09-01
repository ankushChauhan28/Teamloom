# Product Requirements Document & System Architecture (PRD)

This document serves as the holistic product, system architecture, and operational reference for the Employee Task Management System, tying backend and frontend components into a unified specification.

---

## 1. Product Summary

The **Employee Task Management System** is an enterprise-grade internal operations platform designed to streamline task assignment, absence workflows, managerial oversight, and individual/team performance analytics.

### Target User Personas
1. **Employee**: Team members who execute assigned tasks, update work statuses, request leaves of absence, and monitor their individual on-time delivery rate.
2. **Manager (Team Lead)**: Supervisors who oversee direct reports, assign tasks within their team, review and approve/reject leave requests, and monitor aggregated team performance.
3. **Administrator**: System operations managers who provision employee accounts, manage organizational reporting lines, assign system-wide tasks, review organization leaves, and monitor company-wide delivery metrics.

---

## 2. End-to-End Feature Map by Milestone

```mermaid
timeline
    title Release Progression & Feature Milestones
    section v1.0.0 Core
      JWT Dual-Token Auth : Task CRUD & Status Stepper : Leave Submissions & Approvals : Deep Pine Design System
    section v2.0.0 Manager Hierarchy
      Admin-Provisioned Onboarding : Self-Referencing Manager Hierarchy : My Team Portal : Manager Scoped Delegation
    section Enhancements
      Exact Due Datetimes : Live Due Countdown Ticker : completed_at Timestamps
    section Security Hardening
      Account Lockout 5/15m : IP Rate Limiter 10/15m : Constant-Time Bcrypt : Password Visibility Toggle : Unlock User CLI
    section Performance Analytics
      SQL Conditional Aggregations : Scoped Analytics (Self/Team/Org) : PerformanceRing Gauge : MilestoneTrail Dots
```

### 2.1 Milestone v1.0.0 — Core Task & Leave Platform
- **Dual-Token JWT Security**:
  - *Backend*: Signs short-lived access tokens (15 min) and long-lived refresh tokens (7 days) in `httpOnly`, `SameSite=Lax` cookies.
  - *Frontend*: Stores access token in memory (`authStore.js`), transparently refreshes sessions via Axios response interceptors on 401, and performs silent session restoration on app boot.
- **Task Management Lifecycle**:
  - *Backend*: CRUD endpoints (`/tasks/`) supporting role isolation, pagination, status (`PENDING`, `IN_PROGRESS`, `COMPLETED`), and priority (`LOW`, `MEDIUM`, `HIGH`).
  - *Frontend*: `/dashboard` task grid with status stepper controls for employees, and `/admin/tasks` management panel for admins.
- **Leave Request Management**:
  - *Backend*: Leave submission and review endpoints (`/leaves/`) with start/end date validation.
  - *Frontend*: `/leaves` portal for personal submissions, and `/admin/leaves` hub for administrative approval/rejection.

### 2.2 Milestone v2.0.0 — Manager Hierarchy & Enterprise Delegation
- **Admin-Provisioned Onboarding & Directory (`/admin/employees`)**:
  - *Backend*: Replaced open self-registration with `POST /users/employees`. Generates sequential employee codes (`EMP-1001`), job titles (`designation`), supervisor mapping (`reports_to_id`), cryptographically random temporary passwords, and triggers welcome emails via SMTP. Includes `POST /users/{id}/reset-temp-password` and `PATCH /users/{id}/reports-to`.
  - *Frontend*: `/admin/employees` directory for administrators to provision employees, assign supervisors, and reset passwords. On first login with temporary credentials, `ProtectedRoute` forces redirect to `/change-password` before granting dashboard access.
- **Manager-Direct Report Scoping**:
  - *Backend*: Added self-referencing foreign key `users.reports_to_id` and optional job title string `designation`. Implemented cycle detection for supervisor assignments. Created `/tasks/team`, `/leaves/team`, and `/users/me/reports`.
  - *Frontend*: Dedicated `/my-team` workspace guarded by `ManagerRoute`, rendering direct reports roster, team tasks table, and team leave review hub.

### 2.3 Due Date-Time Precision & Live Countdown
- **Exact Timestamps & Completion Auditing**:
  - *Backend*: Converted `due_date` (`Date`) to `due_datetime` (`DateTime(timezone=True)`). Added `completed_at` timestamp automatically stamped when tasks transition to `COMPLETED`.
  - *Frontend*: `DueCountdown` component ticking every 60 seconds. Renders dynamic remaining time ("2d 4h left", "15m left") or overdue warnings ("Overdue by 1d 3h" in red).

### 2.4 Login Security Hardening & Administrative Unlock
- **Account Lockout & Rate Limiting**:
  - *Backend*: Tracks `failed_login_attempts` with a 5-failure threshold triggering a 15-minute lock (`locked_until`). IP rate limiting restricts login attempts to 10 requests per 15 minutes per IP with `429 Too Many Requests` and `Retry-After` headers.
  - *Frontend*: Generic error alerts ("Incorrect employee ID or password.") preventing username/lockout enumeration; password input fields feature interactive show/hide toggles.
  - *Operations*: CLI tool `scripts/unlock_user.py` for immediate account restoration.

### 2.5 Performance Analytics & Milestone Tracking
- **Server-Side SQL Aggregation & Visual Dashboards**:
  - *Backend*: `/analytics/performance` computes completion rates, categorized counts (on-time, late, overdue, pending), and milestone trails using server-side SQL `CASE` aggregations with role-based scoping (self, team, org, employee).
  - *Frontend*: `PerformanceRing` SVG progress gauge and `MilestoneTrail` chronological status dots rendered across `/my-performance` (employees) and `/my-team` (managers/admins).

### 2.6 Interactive Profile Dropdown & Self-Service Password Management
- **Avatar Dropdown & Self-Service Password Updates**:
  - *Backend*: Reuses existing `POST /auth/change-password` endpoint. Validates current password via `bcrypt`, updates password hash, and clears `must_change_password`.
  - *Frontend*: `UserMenu` renders an interactive avatar initials trigger opening a dropdown panel with user details (full name, role badge, designation, employee code, email), a "Change Password" action, and "Logout". `PasswordChangeRoute` permits voluntary access to `/change-password` for active users, displaying a "Back" button to return to the application.

---

## 3. Role-Permission & Scoping Matrix

The system enforces strict multi-tenant role boundaries across every endpoint and view:

| Action / Capability | Plain Employee | Manager (Has Reports) | System Administrator | Scoping & Authorization Rules |
|---|---|---|---|---|
| **View Personal Tasks** | Yes (`/dashboard`) | Yes (`/dashboard`) | Yes (`/dashboard`) | Scoped to tasks where `assigned_to == current_user.id`. |
| **Update Task Status** | Yes | Yes | Yes | Employees/Managers can only transition status (`PENDING` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`). |
| **Create / Assign Tasks** | No (403) | Yes (Direct Reports only) | Yes (Any Employee) | Managers can assign only to employees where `assignee.reports_to_id == manager.id`. Self-assignment blocked. |
| **Edit Full Task Metadata** | No (403) | Yes (Direct Reports only) | Yes (System-wide) | Title, description, due datetime, priority, assignee. |
| **Delete Tasks** | No (403) | No (403) | Yes (`/admin/tasks`) | Destructive action restricted exclusively to Admin role. |
| **View Team Tasks** | No (Empty / N/A) | Yes (`/my-team`) | Yes (`/admin/tasks`) | Scoped to tasks assigned to direct reports. |
| **Submit Leave Request** | Yes (`/leaves`) | Yes (`/leaves`) | Yes (`/leaves`) | Submits personal request with start/end date validation. |
| **Review Leave Requests** | No (403) | Yes (Direct Reports only) | Yes (System-wide) | Approve or reject pending requests. Cannot review own leave. |
| **View Team Leaves** | No (Empty / N/A) | Yes (`/my-team`) | Yes (`/admin/leaves`) | Scoped to leave requests submitted by direct reports. |
| **Provision Employees** | No (403) | No (403) | Yes (`/admin/employees` / `POST /users/employees`) | Generates `EMP-XXXX`, temporary password, sets `reports_to_id` & `designation`, sends email. |
| **Assign User Supervisors** | No (403) | No (403) | Yes (`PATCH /users/{id}/reports-to`) | Cycle-validated reporting chain assignment. |
| **Reset Temp Password** | No (403) | No (403) | Yes (`POST /users/{id}/reset-temp-password`) | Regenerates temp credentials and resends welcome email. |
| **Personal Analytics** | Yes (`/my-performance`) | Yes (`/my-performance`) | Yes (`/my-performance`) | `scope="self"`: Aggregated metrics across own assigned tasks. |
| **Team Analytics** | No (403) | Yes (`/my-team`) | Yes (Via employee selector) | `scope="team"`: Aggregated across direct reports. Individual report drilldown (`scope="employee"`). |
| **Org-Wide Analytics** | No (403) | No (403) | Yes (`/my-team` or `/analytics`) | `scope="org"`: Aggregated across all tasks in system. |

---

## 4. Key Architectural Decisions & Rationale

```mermaid
graph TD
    subgraph "Architectural Decisions"
        D1["Server-Side SQL Analytics<br><i>(vs Client-Side Compute)</i>"]
        D2["Generic Auth Error Messages<br><i>(vs Specific Error Reasons)</i>"]
        D3["Interface-Based Rate Limiting<br><i>(vs Hardcoded Redis/Memory)</i>"]
        D4["Sequential Employee Codes<br><i>(vs Obfuscated UUIDs)</i>"]
        D5["Dual-Token JWT + httpOnly Cookie<br><i>(vs LocalStorage Token)</i>"]
    end
```

### 4.1 Why Performance Analytics is Computed Server-Side via SQL
- **Decision**: Perform conditional count aggregations (`func.coalesce(func.sum(case(...)), 0)`) in PostgreSQL rather than sending raw task arrays to the frontend.
- **Rationale**:
  - **Bandwidth & Latency**: For organizations or large teams with thousands of historical tasks, transmitting full task models over HTTP introduces substantial latency and memory overhead.
  - **Single Source of Truth**: Eliminates discrepancies between client clock differences and server timezones when classifying `on_time` vs `late` vs `overdue`.
  - **Data Privacy**: Prevents leaking unredacted task descriptions or metadata to the client when only numerical summary metrics are requested.

### 4.2 Why Account Lockout & Login Failures Use Generic Error Messaging
- **Decision**: Return identical `401 Unauthorized` responses with `"Incorrect employee ID or password."` for non-existent users, incorrect passwords, and locked accounts.
- **Rationale**:
  - **Anti-User Enumeration**: Differentiating between "Account does not exist" and "Incorrect password" allows attackers to harvest valid corporate employee IDs.
  - **Anti-Lockout Probing**: Revealing that an account is locked confirms to an attacker that their brute-force attempt succeeded in causing a Denial of Service (DoS) for that specific user.
  - **Timing Defense**: Running dummy bcrypt verification on non-existent user lookups ensures indistinguishable server response latencies.

### 4.3 Why the Rate Limiter is Interface-Based (`RateLimiter` ABC)
- **Decision**: Define an abstract base class `RateLimiter` with an in-memory sliding-window default implementation injected via FastAPI dependency.
- **Rationale**:
  - **Zero-Dependency Local Dev**: In-memory rate limiting works immediately in local development and testing environments without requiring external Redis or Memcached containers.
  - **Horizontal Scalability**: In clustered production environments with multiple Uvicorn worker processes or Docker replicas, a `RedisRateLimiter` can be swapped in at the dependency injection level without modifying routes or business services.

### 4.4 Why Sequential Employee Codes (`EMP-1001`) are Used
- **Decision**: Use predictable, sequential identifiers for employee logins rather than opaque UUIDs or arbitrary usernames.
- **Rationale**:
  - **Enterprise UX Realism**: Mirrors real-world internal ERP/HRMS systems where employees are issued standardized badge IDs.
  - **Simplicity & Error Reduction**: Easy for employees to type accurately, especially when logging in for the first time on mobile or restricted corporate devices.

### 4.5 Why httpOnly Cookies are Used for Refresh Tokens
- **Decision**: Store long-lived refresh tokens in `httpOnly`, `SameSite=Lax` cookies and keep access tokens strictly in JavaScript memory.
- **Rationale**:
  - **XSS Immunity**: JavaScript running in the browser (including malicious injected scripts or compromised third-party dependencies) cannot access `httpOnly` cookies, preventing persistent session hijacking.
  - **CSRF Protection**: Access tokens must still be explicitly sent in `Authorization: Bearer` headers for API calls; the refresh cookie is restricted to `SameSite=Lax` and scoped to `/auth`.

---

## 5. Local Development Setup & Operational Guide

### 5.1 Environment Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL 14+ (or Docker)

### 5.2 Local Execution (Recommended for Active Development)

> [!WARNING]
> **Port 8000 Conflict Gotcha**:
> Do NOT run both the Docker backend container and local `uvicorn` simultaneously on port `8000`. Running both causes port binding conflicts or routing requests to stale container code.
> - **During active coding**: Run local `uvicorn --reload` and PostgreSQL locally or via Docker db service.
> - **During staging verification**: Stop local Uvicorn and run `docker compose up --build`.

#### Step 1: Database Setup
Start a local PostgreSQL database or run a containerized database:
```bash
# If using Docker for PostgreSQL only:
docker run --name emp-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=employee_tasks -p 5432:5432 -d postgres:15-alpine
```

#### Step 2: Backend Setup & Migrations
```bash
# In repository root:
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure environment variables:
cp .env.example .env
# Ensure DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/employee_tasks

# Execute database migrations to head:
alembic upgrade head

# Seed initial system administrator:
python scripts/seed_admin.py
# (Or non-interactively: ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=adminpassword123 python scripts/seed_admin.py)

# Start FastAPI development server:
uvicorn app.main:app --reload --port 8000
```

#### Step 3: Frontend Setup
```bash
# In a separate terminal:
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 6. Testing, Quality Assurance & Data Management

### 6.1 Running Automated Tests
The repository includes a comprehensive Pytest suite (109+ tests) covering unit services, API routes, RBAC, scoping, and security mechanics with in-memory SQLite isolation:

```bash
# Run complete test suite:
pytest

# Run tests with terminal coverage report:
pytest --cov=app --cov-report=term-missing

# Run specific test module:
pytest tests/test_analytics.py
pytest tests/test_login_security.py
pytest tests/test_manager_scoping.py
```

### 6.2 Administrative CLI Tools
- **Seed Administrator**:
  ```bash
  python scripts/seed_admin.py
  ```
- **Unlock User Account**:
  ```bash
  # Unlock by employee code:
  python scripts/unlock_user.py EMP-1001
  ```
- **Run End-to-End API QA Verification**:
  ```bash
  python scripts/run_qa_suite.py
  ```

---

## 7. Current Status & Known Deferred Items

| Feature / Area | Status | Notes |
|---|---|---|
| **Core Authentication & RBAC** | Complete | Dual-token JWT, httpOnly cookies, role boundaries (`ADMIN`, `EMPLOYEE`). |
| **Admin Onboarding & Welcome Email** | Complete | Sequential `EMP-XXXX`, temp passwords, SMTP welcome email dispatch. |
| **Manager Hierarchy & Scoping** | Complete | Cycle-checked reporting lines, manager-assigned tasks, manager-reviewed leaves. |
| **Due Datetime & Countdown Ticker** | Complete | Timezone-aware exact datetimes, `completed_at` timestamps, live client timer. |
| **Login Security Hardening** | Complete | 5-failure account lockout, 10-req/15m IP rate limiter, timing attack mitigation. |
| **Performance Analytics v1** | Complete | Server-side SQL calculations, scoped access (`self`, `team`, `org`), `PerformanceRing` + `MilestoneTrail`. |
| **UI Motion & Polish Pass** | **Explicitly Deferred** | The v1 UI is deliberately static with zero animation delay to prioritize stability and testability. Animated transitions are planned for v2 polish milestone. |
| **Distributed Rate Limiting (Redis)** | Prepared / Deferred | `InMemoryRateLimiter` active; `RateLimiter` ABC is ready for a drop-in `RedisRateLimiter` when scaling horizontally. |
