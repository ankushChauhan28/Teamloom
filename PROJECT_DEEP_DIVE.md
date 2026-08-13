# Employee Task Management System — Architectural Deep Dive & Developer Onboarding Guide

Welcome to the **Employee Task Management System** codebase! This document is designed as a deep-dive onboarding guide for developers joining the project or reviewing the system architecture. After reading this guide, you will understand the design philosophy, layer boundaries, security mechanisms, database interactions, testing patterns, containerization strategies, and how to safely extend the codebase.

---

## 1. Project Overview & Purpose

### What This Project Is
The **Employee Task Management System** is a production-grade, asynchronous backend REST API built in Python using **FastAPI**, **SQLAlchemy 2.0 (Async)**, **asyncpg**, **PostgreSQL**, **Alembic**, and **Docker**. It provides enterprise-style task assignment and employee leave request management with strict Role-Based Access Control (RBAC).

### Core Problem Solved
In modern organizations, operational workflows require structured delegation and auditing:
1. **Task Lifecycle Management**: Managers must assign tasks to employees with priorities and due dates, while employees need to update status (`PENDING` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`) without altering administrative task details.
2. **Leave Request Workflow**: Employees must submit leave requests with date validation, while administrators require a centralized mechanism to review, approve, or reject requests.
3. **Data Scope & Role Enforcement**: Confidentiality requires strict data isolation — employees must only access their own assigned tasks and leave submissions, whereas administrators hold system-wide oversight.

### The Three System Actors & Capabilities

| Actor / Role | Authentication Status | System Permissions & Capabilities |
|---|---|---|
| **Unauthenticated User** | None | Can register (`POST /auth/register`), log in (`POST /auth/login`), exchange refresh tokens (`POST /auth/refresh`), and view API documentation (`GET /docs`). |
| **EMPLOYEE** | Authenticated (JWT) | Can view own profile (`GET /users/me`), update own full name (`PATCH /users/me`), list own assigned tasks (`GET /tasks/`), update assigned task status (`PATCH /tasks/{id}`), submit leave requests (`POST /leaves/`), and view own submitted leaves (`GET /leaves/`). |
| **ADMIN** | Authenticated (JWT) | Inherits all system permissions: create & assign tasks (`POST /tasks/`), list all system tasks (`GET /tasks/`), update any task (`PATCH /tasks/{id}`), delete tasks (`DELETE /tasks/{id}`), list all employees (`GET /users/`), and approve/reject leave requests (`PATCH /leaves/{id}`). |

---

## 2. Complete Tech Stack — With "WHY", Not Just "WHAT"

Every technology in this project was selected deliberately to demonstrate modern Python backend standards.

| Technology | Version | Project Role | WHY Chosen Over Alternatives |
|---|---|---|---|
| **Python** | `3.11` / `3.12` | Runtime Language | Chosen for clean syntax, modern type hints (`str \| None`, `list[str]`), and robust `asyncio` event loop capabilities. |
| **FastAPI** | `>=0.110.0` | Core Web Framework | Chosen over Django/Flask because FastAPI is natively built on ASGI (Starlette), automatically generates OpenAPI/Swagger UI docs, and integrates seamlessly with Pydantic v2 validation. |
| **SQLAlchemy 2.0** | `>=2.0.28` | Relational ORM | Chosen over raw SQL or Django ORM. Version 2.0 provides explicit `select()` constructs, strict type safety, and first-class `AsyncSession` support. |
| **asyncpg** | `>=0.29.0` | PostgreSQL Async Driver | Chosen over `psycopg2-binary`. `asyncpg` is written in Cython/C natively for Python's `asyncio` event loop, delivering 3x–5x higher throughput under concurrent network I/O load compared to synchronous DBAPI drivers. |
| **PostgreSQL** | `16-alpine` | Relational Database | Chosen over MySQL or SQLite for production. Provides strict ACID compliance, native ENUM types, row-level locking, foreign key constraint enforcement, and reliable containerization. |
| **Alembic** | `>=1.13.1` | Database Migration Engine | Chosen for declarative database schema revision tracking. Integrates natively with SQLAlchemy metadata and supports async migration runs via `async_engine_from_config` and `run_sync()`. |
| **Pydantic v2** | `>=2.6.4` | Validation & DTO Schemas | Chosen over Marshmallow or Cerberus. Pydantic v2 is backed by Rust (`pydantic-core`), delivering ultra-fast request parsing, response serialization, and RFC-compliant email validation (`email-validator`). |
| **PyJWT** | `>=2.8.0` | JWT Authentication | Chosen over server-side session cookies (`redis`/`memcached`). Stateless JWTs scale horizontally across container instances without requiring shared session state stores. |
| **bcrypt** | `>=4.1.2` | Password Hashing | Chosen over MD5/SHA256/PBKDF2. `bcrypt` incorporates key-stretching (salting + configurable work factor rounds), rendering brute-force dictionary attacks computationally infeasible. |
| **Docker & Compose** | `3.12-slim` / `16-alpine` | Containerization | Chosen for guaranteed environment parity across local development and production. Uses multi-stage builds, non-root security (`appuser`), and container healthcheck dependencies (`pg_isready`). |
| **Pytest & plugins** | `pytest>=8.0.0`<br>`pytest-asyncio`<br>`httpx`<br>`pytest-cov`<br>`aiosqlite` | Test Automation Suite | Chosen for non-blocking test execution. Uses `httpx.AsyncClient` with `ASGITransport`, an isolated in-memory SQLite database (`sqlite+aiosqlite:///:memory:`), and reports code coverage (94%). |
| **Ruff / Black / Mypy** | `ruff>=0.3.0`<br>`black>=24.2.0`<br>`mypy>=1.8.0` | Code Quality & Tooling | Chosen for automated linting (Ruff), deterministic code formatting (Black, line length 100), and static type checking (Mypy). |

---

## 3. Architecture Deep Dive

### Full Request Lifecycle (ASCII Data Flow)

Below is the complete trace of an HTTP request from client transmission to database execution and response serialization:

```text
  ┌────────────────┐
  │   HTTP Client  │ (e.g. Swagger UI, Postman, Frontend React App)
  └───────┬────────┘
          │ 1. HTTP Request (POST /tasks/ + Bearer Token Header + JSON Body)
          ▼
  ┌────────────────┐
  │ Uvicorn / ASGI │ (Event Loop receives incoming socket connection)
  └───────┬────────┘
          │ 2. Hands request payload to FastAPI application
          ▼
  ┌────────────────┐
  │ CORSMiddleware │ (Validates Origin against settings.CORS_ORIGINS)
  └───────┬────────┘
          │ 3. Passes middleware check
          ▼
  ┌────────────────┐
  │   APIRouter    │ (Matches route path in app/routes/tasks.py)
  └───────┬────────┘
          │ 4. Resolves Dependency Injection Chain (app/core/security.py)
          ├─────────────────────────┬─────────────────────────┐
          ▼                         ▼                         ▼
  ┌──────────────┐          ┌────────────────┐       ┌────────────────┐
  │  get_db()    │          │get_current_user│       │  require_role  │
  │ Yields async │          │Decodes JWT and │       │Verifies role ==│
  │ AsyncSession │          │queries DB user │       │   UserRole.ADMIN│
  └───────┬──────┘          └───────┬────────┘       └───────┬────────┘
          └─────────────────────────┼─────────────────────────┘
                                    │ 5. Validates Request Body via Pydantic (TaskCreate Schema)
                                    ▼
                          ┌──────────────────┐
                          │  Service Layer   │ (app/services/task_service.py -> create_task())
                          └─────────┬────────┘
                                    │ 6. Executes Async Query: select(User) -> checks assignee
                                    │ 7. Adds Task object -> await db.commit() -> await db.refresh()
                                    ▼
                          ┌──────────────────┐
                          │ AsyncSession / DB│ (asyncpg driver -> PostgreSQL 16)
                          └─────────┬────────┘
                                    │ 8. Returns ORM Task Instance
                                    ▼
                          ┌──────────────────┐
                          │  Schema Response │ (Serializes Task ORM -> TaskRead JSON DTO)
                          └─────────┬────────┘
                                    │ 9. Returns HTTP 201 Created JSON Response
                                    ▼
                          ┌──────────────────┐
                          │   HTTP Client    │
                          └──────────────────┘
```

### The Layered Architecture Rationale

The project strictly segregates concerns into 5 decoupled domain layers:

```
app/
├── core/       # Global configuration, security algorithms, exception definitions
├── db/         # Engine initialization, session management, declarative Base
├── models/     # SQLAlchemy ORM entities (Table definitions, columns, DB constraints)
├── schemas/    # Pydantic DTO models (Input validation, field serialization)
├── routes/     # Presentation Layer (HTTP status codes, routes, query parameters)
└── services/   # Business Logic Layer (Domain rules, state transitions, DB queries)
```

#### Why Layer Separation Matters
* **`app/routes/`**: Handles HTTP semantics only. It extracts headers, status codes (`HTTP_201_CREATED`), path/query parameters, and delegates business rules to `services`.
* **`app/services/`**: Contains pure business logic. Functions take `AsyncSession` and domain data primitives/Pydantic schemas. They contain **zero** HTTP dependencies (`Request`, `Response`, `Header`).
* **`app/schemas/`**: Pydantic schemas decouple the internal database representation from the external API contract. For example, `UserRead` excludes `hashed_password` to prevent credential leakage.
* **`app/models/`**: SQLAlchemy declarative models define table schemas, column types, foreign key constraints, and cascade rules.

#### What Breaks If Layers Are Mixed?
If route functions directly execute `db.execute(select(...))`:
1. **Testing Fragility**: Unit testing business logic would require instantiating full HTTP requests rather than calling Python functions.
2. **Code Duplication**: Reusing task assignment validation across multiple endpoints (e.g. REST API, background tasks, seed scripts) would duplicate code.
3. **Security Vulnerabilities**: Returning ORM models directly in routes bypasses field filtering, leaking private hash attributes to clients.

---

### Dependency Injection Chain End-to-End Trace

FastAPI's dependency injection (`Depends`) resolves parameter dependencies hierarchically before entering the route handler.

#### Concrete Trace: `POST /tasks/` (Admin Task Creation)

1. **Route Signature** ([app/routes/tasks.py:15-19](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L15-L19)):
   ```python
   @router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
   async def create_task(
       task_in: TaskCreate,
       db: AsyncSession = Depends(get_db),
       current_admin: User = Depends(require_role(UserRole.ADMIN)),
   ):
   ```

2. **Step 1 — Session Generator Injection (`get_db`)**:
   FastAPI calls `get_db()` ([app/db/session.py:8](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/db/session.py#L8)). It initializes an `AsyncSession` via `AsyncSessionLocal()` and yields `db`.

3. **Step 2 — Security Chain (`require_role` $\rightarrow$ `get_current_user`)**:
   `require_role(UserRole.ADMIN)` returns a dependency callable that requests `current_user: User = Depends(get_current_user)` ([app/core/security.py:132-142](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L132-L142)).

4. **Step 3 — Bearer Token Extraction & User Retrieval (`get_current_user`)**:
   * Extracts the `Authorization: Bearer <token>` string via `oauth2_scheme`.
   * Decodes JWT via `decode_access_token(token)` ([app/core/security.py:78](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L78)).
   * Queries the user asynchronously:
     ```python
     result = await db.execute(select(User).where(User.email == email))
     user = result.scalar_one_or_none()
     ```
   * Returns `current_user`.

5. **Step 4 — Role Check Execution**:
   `require_role` checks `current_user.role == UserRole.ADMIN`. If true, `current_admin` is returned to the route.

6. **Step 5 — Route Execution**:
   The route receives fully validated `task_in`, `db`, and `current_admin`, and calls `await task_service.create_task(...)`.

---

## 4. Feature-by-Feature Design Flow

### 1. Authentication & User Management Flow

#### Narrative Trace: User Registration (`POST /auth/register`)
1. Client sends JSON payload `{"email": "john@example.com", "full_name": "John Doe", "password": "secretpassword"}` to `POST /auth/register`.
2. Pydantic validates `UserCreate` schema ([app/schemas/user.py:13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/schemas/user.py#L13)). `EmailStr` validates email formatting.
3. Route delegates to `auth_service.register_user(db, user_in)` ([app/services/auth_service.py:19](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/auth_service.py#L19)).
4. Service queries `select(User).where(User.email == user_in.email)`. If existing user found, raises `UserAlreadyExistsException` (returns HTTP 400).
5. Password is hashed via `hash_password(user_in.password)` ([app/core/security.py:9](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L9)).
6. New `User` instance created with role `UserRole.EMPLOYEE`.
7. `db.add(db_user)` $\rightarrow$ `await db.commit()` $\rightarrow$ `await db.refresh(db_user)`.
8. Route returns `db_user`, serialized by `UserRead` ([app/schemas/user.py:27](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/schemas/user.py#L27)) (excluding `hashed_password`).

#### Narrative Trace: User Login (`POST /auth/login`)
1. Client sends `{"email": "john@example.com", "password": "secretpassword"}` to `POST /auth/login`.
2. Service calls `auth_service.authenticate_user(db, login_in)` ([app/services/auth_service.py:40](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/auth_service.py#L40)).
3. Queries user by email. If not found or `verify_password(...)` returns `False`, raises `InvalidCredentialsException` (returns HTTP 401).
4. Generates short-lived access token (`create_access_token`, 15 min expiry) and long-lived refresh token (`create_refresh_token`, 7 day expiry).
5. Returns `Token` DTO: `{"access_token": "...", "refresh_token": "...", "token_type": "bearer"}`.

#### Narrative Trace: Token Refresh (`POST /auth/refresh`)
1. Client submits `{"refresh_token": "..."}` to `POST /auth/refresh`.
2. Service calls `decode_refresh_token(refresh_token)` ([app/core/security.py:88](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L88)). Validates token type is `"refresh"` and signature is valid.
3. Queries user by payload `sub` email.
4. Generates a fresh access token and returns it alongside the original refresh token.

---

### 2. Task Management Flow

#### Narrative Trace: Task Creation & Assignment (`POST /tasks/`)
1. Admin submits task payload to `POST /tasks/`.
2. Dependency `require_role(UserRole.ADMIN)` enforces Admin privilege.
3. Service `create_task(...)` ([app/services/task_service.py:13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L13)) verifies assignee user exists via `select(User).where(User.id == task_in.assigned_to)`.
4. **Business Rule**: Asserts `assignee.role == UserRole.EMPLOYEE`. If assignee is an Admin, raises `BadRequestException("Tasks can only be assigned to users with the EMPLOYEE role.")`.
5. Creates `Task` with `status=TaskStatus.PENDING`, `created_by=creator_id`.
6. Saves to database and returns `TaskRead` schema.

#### Narrative Trace: Task Listing & Scope Isolation (`GET /tasks/`)
1. User requests `GET /tasks/?status=PENDING&sort_by=due_date&skip=0&limit=10`.
2. Service `get_tasks(...)` ([app/services/task_service.py:40](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L40)) constructs `stmt = select(Task)`.
3. **Data Scope Rule**: If `user.role == UserRole.EMPLOYEE`, appends `stmt = stmt.where(Task.assigned_to == user.id)`. Admins bypass this filter and view all tasks.
4. Appends optional filters (`status`, `priority`), dynamic sorting (`order_by(getattr(Task, sort_by).asc())`), and pagination (`offset(skip).limit(limit)`).
5. Executes `await db.execute(stmt)` and returns `list[TaskRead]`.

#### Narrative Trace: Task Status Update with RBAC Restrictions (`PATCH /tasks/{id}`)
1. Client submits patch body `{"status": "IN_PROGRESS"}` to `PATCH /tasks/{id}`.
2. Service retrieves task via `get_task_by_id(...)` ([app/services/task_service.py:80](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L80)), which enforces ownership check: if `user.role == UserRole.EMPLOYEE` and `task.assigned_to != user.id`, raises `AuthorizationException` (HTTP 403).
3. **Field Constraint Rule**: If `user.role == UserRole.EMPLOYEE`, inspects `update_data.keys()`. If any key other than `"status"` is present (e.g. updating `title`), raises `AuthorizationException("Employees are only permitted to update the task status.")`.
4. Applies status update, commits, and returns updated task.

---

### 3. Leave Request Flow

#### Narrative Trace: Leave Submission (`POST /leaves/`)
1. Employee submits leave request `{"reason": "Vacation", "start_date": "2026-08-10", "end_date": "2026-08-15"}`.
2. Service `create_leave_request(...)` ([app/services/leave_service.py:12](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L12)) evaluates date logic.
3. **Date Constraint Rule**: If `leave_in.end_date < leave_in.start_date`, raises `BadRequestException("End date cannot be prior to start date.")`.
4. Persists `LeaveRequest` with `status=LeaveStatus.PENDING`, `employee_id=current_user.id`.

#### Narrative Trace: Admin Leave Review & Approval (`PATCH /leaves/{id}`)
1. Admin calls `PATCH /leaves/{id}` with body `{"status": "APPROVED"}`.
2. Dependency `require_role(UserRole.ADMIN)` restricts access to Admins.
3. Service `review_leave_request(...)` ([app/services/leave_service.py:67](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L67)) fetches leave request.
4. **State Transition Rule**: If `db_leave.status != LeaveStatus.PENDING`, raises `BadRequestException("This leave request has already been reviewed and cannot be modified.")`.
5. **Status Whitelist Rule**: Asserts `review_in.status in [LeaveStatus.APPROVED, LeaveStatus.REJECTED]`.
6. Sets `db_leave.status = review_in.status` and records reviewer `db_leave.reviewed_by = reviewer_id`. Commits and returns updated leave request.

---

### Comprehensive Business Rule & Code Location Registry

| Business Rule | Description | File Location | Function / Line |
|---|---|---|---|
| **Duplicate Email Check** | Prevents registering multiple users with the same email. | `app/services/auth_service.py` | `register_user()` ([L23-25](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/auth_service.py#L23-L25)) |
| **Assignee Existence & Role** | Tasks can only be assigned to existing users holding role `EMPLOYEE`. | `app/services/task_service.py` | `create_task()` ([L18-24](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L18-L24)) |
| **Task Listing Scope Isolation** | Employees see only their assigned tasks; Admins view all system tasks. | `app/services/task_service.py` | `get_tasks()` ([L56-57](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L56-L57)) |
| **Task Ownership Isolation** | Employees cannot view or modify tasks assigned to other employees. | `app/services/task_service.py` | `get_task_by_id()` ([L89-90](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L89-L90)) |
| **Employee Task Update Restriction** | Employees can only update task `status`; modifying `title` or `description` is forbidden. | `app/services/task_service.py` | `update_task()` ([L106-110](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L106-L110)) |
| **Task Deletion RBAC** | Only Admin users can delete tasks. | `app/services/task_service.py` | `delete_task()` ([L125-126](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L125-L126)) |
| **Leave Date Chronology** | Leave `end_date` cannot precede `start_date`. | `app/services/leave_service.py` | `create_leave_request()` ([L17-18](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L17-L18)) |
| **Leave Review State Lock** | Only `PENDING` leave requests can be reviewed. Re-reviewing processed leaves is blocked. | `app/services/leave_service.py` | `review_leave_request()` ([L78-81](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L78-L81)) |

---

## 5. Database Schema Deep Dive

### Entity-Relationship Diagram (ERD Description)

```text
    ┌───────────────────────────┐
    │           users           │
    ├───────────────────────────┤
    │ PK  id          Integer   │◀──────┐
    │     full_name   String    │       │
    │ UK  email       String    │       │ (created_by / assigned_to)
    │     hashed_pwd  String    │       │
    │     role        Enum      │       │
    │     created_at  DateTime  │       │
    └─────────────┬─────────────┘       │
                  │ (employee_id /      │
                  │  reviewed_by)       │
                  ▼                     │
    ┌───────────────────────────┐  ┌────┴──────────────────────┐
    │      leave_requests       │  │         tasks             │
    ├───────────────────────────┤  ├───────────────────────────┤
    │ PK  id          Integer   │  │ PK  id          Integer   │
    │ FK  employee_id Integer   │  │     title       String    │
    │     reason      Text      │  │     description Text      │
    │     start_date  Date      │  │     status      Enum      │
    │     end_date    Date      │  │     priority    Enum      │
    │     status      Enum      │  │     due_date    Date      │
    │ FK  reviewed_by Integer   │  │ FK  assigned_to Integer   │
    │     created_at  DateTime  │  │ FK  created_by  Integer   │
    └───────────────────────────┘  │     created_at  DateTime  │
                                   └───────────────────────────┘
```

### Table Definitions & Constraint Rationale

#### 1. `users` Table ([app/models/user.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py))
* `id`: Integer, Primary Key, Indexed.
* `email`: String, Unique, Indexed (`unique=True, index=True`), Nullable=False. Indexing speeds up user login queries (`select(User).where(User.email == email)`).
* `role`: SQLEnum (`UserRole.ADMIN`, `UserRole.EMPLOYEE`). Enforces database-level role constraints.
* **Relationships**:
  * `assigned_tasks`: Relationship to `Task` on `Task.assigned_to`, with `cascade="all, delete-orphan"`.
  * `created_tasks`: Relationship to `Task` on `Task.created_by`.
  * `leave_requests`: Relationship to `LeaveRequest` on `LeaveRequest.employee_id`.

#### 2. `tasks` Table ([app/models/task.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/task.py))
* `id`: Integer, Primary Key.
* `status`: SQLEnum (`PENDING`, `IN_PROGRESS`, `COMPLETED`), default `PENDING`.
* `priority`: SQLEnum (`LOW`, `MEDIUM`, `HIGH`).
* `assigned_to`: Integer, Foreign Key `users.id` with `ondelete="CASCADE"`.
* `created_by`: Integer, Foreign Key `users.id` with `ondelete="CASCADE"`.
* **Cascade Rationale**: `ondelete="CASCADE"` guarantees relational integrity. If a user record is removed, all associated tasks are cleaned up automatically without leaving orphaned foreign keys.

#### 3. `leave_requests` Table ([app/models/leave.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/leave.py))
* `id`: Integer, Primary Key.
* `status`: SQLEnum (`PENDING`, `APPROVED`, `REJECTED`), default `PENDING`.
* `employee_id`: Integer, Foreign Key `users.id` with `ondelete="CASCADE"`.
* `reviewed_by`: Integer, Foreign Key `users.id`, Nullable=True. Stays `NULL` until an Admin approves or rejects the request.

---

### Async Query Execution Mechanics (SQLAlchemy 2.0 vs 1.4 Sync)

In synchronous SQLAlchemy 1.4, queries used `db.query(Model).filter(...).first()`. In asynchronous SQLAlchemy 2.0 with `asyncpg` and `AsyncSession`, `db.query()` is deprecated because accessing unloaded relationships or executing queries synchronously causes thread blocking or `MissingGreenlet` errors.

#### SQLAlchemy 2.0 Async Query Patterns

```python
# 1. Fetch Single Record by Identifier / Condition
stmt = select(User).where(User.email == email)
result = await db.execute(stmt)
user = result.scalar_one_or_none()  # Returns User instance or None

# 2. Fetch Filtered List with Pagination & Sorting
stmt = (
    select(Task)
    .where(Task.assigned_to == user_id)
    .where(Task.status == TaskStatus.PENDING)
    .order_by(Task.due_date.asc())
    .offset(skip)
    .limit(limit)
)
result = await db.execute(stmt)
tasks = list(result.scalars().all())  # Unwraps scalar ORM objects from Row tuples

# 3. Mutations (Insert / Update / Delete)
db.add(new_task)
await db.commit()       # Flushes changes to PostgreSQL non-blockingly over asyncio loop
await db.refresh(new_task)  # Re-queries generated fields (id, created_at) asynchronously
```

---

## 6. Authentication & Security Deep Dive

### JWT Token Lifecycle & Payload Structure

The application uses symmetric JWTs signed with `HS256` and secret keys loaded from `settings.JWT_SECRET_KEY` and `settings.JWT_REFRESH_SECRET_KEY`.

#### Access Token vs Refresh Token Comparison

| Attribute | Access Token | Refresh Token |
|---|---|---|
| **Purpose** | Authorizes short-term HTTP requests to protected API endpoints. | Exchanges for a new Access Token without requiring re-entry of user password. |
| **Lifespan** | Short-lived: 15 minutes (`settings.ACCESS_TOKEN_EXPIRE_MINUTES`). | Long-lived: 7 days (`settings.REFRESH_TOKEN_EXPIRE_DAYS`). |
| **Secret Key** | Signed using `settings.JWT_SECRET_KEY`. | Signed using `settings.JWT_REFRESH_SECRET_KEY`. |
| **Header Transmission** | Client attaches to `Authorization: Bearer <token>` header. | Client submits in JSON body to `POST /auth/refresh`. |

#### Decoded JWT Payload Anatomy

```json
{
  "sub": "admin@example.com",
  "role": "ADMIN",
  "type": "access",
  "iat": 1723230000,
  "exp": 1723230900
}
```
* `sub` (Subject): User's unique email address.
* `role`: User role (`ADMIN` or `EMPLOYEE`).
* `type`: Token type classification (`"access"` or `"refresh"`). Enforces token isolation — submitting a refresh token in the `Authorization` header fails validation.
* `iat` (Issued At) & `exp` (Expiration): Unix timestamps evaluated automatically by `jwt.decode`. If `current_time > exp`, raises `jwt.ExpiredSignatureError` (HTTP 401).

---

### Dual-Layer Authorization (RBAC vs Service Ownership)

A critical architectural distinction in this project is the separation between **Route-Level Role Authorization** and **Service-Level Resource Ownership Checks**.

```text
Incoming Request
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 1: Route-Level RBAC (require_role)                │
│ Evaluates: "Does this user hold the required Role?"     │
│ Example: DELETE /tasks/{id} requires UserRole.ADMIN     │
└──────────────────────────┬──────────────────────────────┘
                           │ Passed
                           ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 2: Service-Level Ownership Check                  │
│ Evaluates: "Does this Employee own this specific Task?" │
│ Example: PATCH /tasks/5 checks task.assigned_to == user.id│
└──────────────────────────┴──────────────────────────────┘
```

#### Why Both Authorization Layers Exist
1. **Route-Level RBAC (`require_role`)**: Quick gatekeeping. Rejects unauthorized roles (e.g. an Employee trying to delete a task or approve leave) immediately at the HTTP boundary before querying the domain entity.
2. **Service-Level Ownership**: Resource-specific granularity. An Employee *is* authorized to view and update task status, but *only for tasks assigned to them*. The service layer inspects the specific model instance attributes against `current_user.id`.

---

## 7. Testing Architecture

### Test Infrastructure & In-Memory Async Database

The test suite is built on **Pytest**, **pytest-asyncio**, **httpx.AsyncClient**, and **aiosqlite**.

#### Why `sqlite+aiosqlite:///:memory:` is Used
Testing against a live development or production PostgreSQL database is an anti-pattern:
* **Isolation**: Tests could alter or wipe development data.
* **Speed**: In-memory SQLite executes schema creation and queries in memory without disk or network I/O.
* **Independence**: Tests run cleanly in CI/CD pipelines without launching external PostgreSQL services.

#### Fixture Lifecycle & Dependency Overrides ([tests/conftest.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/tests/conftest.py))

```python
# 1. Async Database Session Fixture (Scope: Function)
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Creates clean tables
    async with TestingSessionLocal() as session:
        yield session  # Provides session to test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)    # Tears down tables post-test

# 2. FastAPI AsyncClient Fixture with Dependency Override
@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db  # Swaps production get_db with test db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

---

### Unit Tests vs Integration Tests

* **Unit Tests** ([tests/test_services.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/tests/test_services.py)): Directly invoke service layer Python functions with `db_session`. They test pure business logic, exceptions, and database state without HTTP framing or FastAPI routing.
* **Integration Tests** ([tests/test_auth.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/tests/test_auth.py), [test_tasks.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/tests/test_tasks.py), etc.): Execute HTTP calls via `client.post()`, `client.get()` against route endpoints. They verify Pydantic request parsing, HTTP status codes, security headers, and end-to-end database operations.

#### How to Execute Tests & View Coverage
```bash
# Run all tests
python -m pytest

# Run tests with terminal coverage report
python -m pytest --cov=app --cov-report=term-missing
```

---

## 8. Docker & Deployment Architecture

### Multi-Stage Dockerfile Rationale ([Dockerfile](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/Dockerfile))

The project uses a two-stage `Dockerfile` to optimize image size and security:

```dockerfile
# STAGE 1: Builder (Compiles C extensions & Python wheels into /install)
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y gcc libpq-dev
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# STAGE 2: Production Runtime (Clean slim image & unprivileged user)
FROM python:3.12-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y libpq5 netcat-openbsd
# Copy compiled packages from builder stage
COPY --from=builder /install /usr/local
# Security: Create non-root system user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini docker-entrypoint.sh seed_admin.py /app/
USER appuser
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Why Multi-Stage & Non-Root Matter
1. **Size & Security**: Stage 1 contains compilers (`gcc`). Stage 2 copies *only* the compiled packages into a clean runtime image, eliminating build tools from production and reducing image size.
2. **Non-Root Execution (`USER appuser`)**: Containers by default run as `root`. Switching to `appuser` (UID 1001) enforces least privilege, preventing container escape vulnerabilities from gaining root access to the host kernel.

---

### Docker Compose & Container Startup Sequence ([docker-compose.yml](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/docker-compose.yml))

```text
1. docker compose up -d
        │
        ▼
2. Launches 'db' container (postgres:16-alpine)
        │
        ▼
3. PostgreSQL starts & executes Healthcheck:
   pg_isready -U postgres -d employee_task_db
        │
        ▼ (Retries until HEALTHY)
4. 'app' container starts (depends_on: db: condition: service_healthy)
        │
        ▼
5. Runs ENTRYPOINT script (docker-entrypoint.sh):
   a. Executes: alembic upgrade head (Applies schema migrations)
   b. Executes: exec uvicorn app.main:app --host 0.0.0.0 --port 8000
        │
        ▼
6. FastAPI API server is live at http://127.0.0.1:8000/docs
```

---

## 9. Code Quality Tooling

The codebase enforces linting, formatting, and static typing via `pyproject.toml`:

### 1. Ruff (Linter & Import Sorter)
Fast Rust-backed linter enforcing standard rules (`E`, `W`, `F`, `I`, `UP`).
```bash
# Check code style & import ordering
python -m ruff check .

# Auto-fix trivial lint issues
python -m ruff check --fix .
```

### 2. Black (Code Formatter)
Opinionated Python code formatter configured for line length **100**.
```bash
# Check formatting compliance
python -m black --check .

# Auto-format all Python files
python -m black .
```

### 3. Mypy (Static Type Checker)
Static type analyzer verifying Python type hints across `app/`.
```bash
# Execute static type analysis
python -m mypy app
```

---

## 10. "If I Had to Modify This Live" — Practical Extension Guide

### Worked Example: Adding Endpoint `GET /tasks/overdue`

To demonstrate how to extend the codebase cleanly, let's walk through adding a new endpoint: `GET /tasks/overdue` (returns all tasks where `due_date < today` and `status != COMPLETED`).

#### Step 1: Update Schema (if necessary)
No new request schema needed since `GET` returns existing `list[TaskRead]`.

#### Step 2: Implement Service Logic ([app/services/task_service.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py))
Add the async query logic:
```python
from datetime import date

async def get_overdue_tasks(db: AsyncSession, user: User) -> list[Task]:
    """
    Returns overdue tasks. Admin sees all overdue; Employee sees only their assigned.
    """
    stmt = select(Task).where(Task.due_date < date.today()).where(Task.status != TaskStatus.COMPLETED)
    if user.role == UserRole.EMPLOYEE:
        stmt = stmt.where(Task.assigned_to == user.id)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

#### Step 3: Implement Route Handler ([app/routes/tasks.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py))
Add the route handler:
```python
@router.get("/overdue", response_model=list[TaskRead])
async def list_overdue_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all overdue tasks past their due date.
    """
    return await task_service.get_overdue_tasks(db=db, user=current_user)
```

#### Step 4: Add Automated Integration Test ([tests/test_tasks.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/tests/test_tasks.py))
Add the test function:
```python
@pytest.mark.asyncio
async def test_get_overdue_tasks(
    client: AsyncClient, admin_headers: dict[str, str], employee_user: User
) -> None:
    # Seed an overdue task
    payload = {
        "title": "Overdue Task",
        "description": "Past due task",
        "priority": "HIGH",
        "due_date": str(date.today() - timedelta(days=2)),
        "assigned_to": employee_user.id,
    }
    await client.post("/tasks/", json=payload, headers=admin_headers)

    response = await client.get("/tasks/overdue", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Overdue Task"
```

#### Step 5: Verify Quality & Run Tests
```bash
python -m black .
python -m ruff check .
python -m pytest
```

---

## 11. Common Pitfalls & Gotchas

1. **Forgetting `await` on Async Operations**:
   * *Gotcha*: Calling `db.execute()`, `db.commit()`, `db.refresh()`, or service functions without `await`.
   * *Symptom*: Returns an un-awaited coroutine object `<coroutine object ...>` or fails Pydantic serialization.
2. **SQLAlchemy 2.0 Legacy `db.query()` Syntax**:
   * *Gotcha*: Using `db.query(User).filter(...)` with `AsyncSession`.
   * *Symptom*: Deprecation warnings or `MissingGreenlet` exception. Always use `select(Model).where(...)` + `await db.execute(...)`.
3. **Circular Import in Model Relationships**:
   * *Gotcha*: Direct imports between `User`, `Task`, and `LeaveRequest` models.
   * *Symptom*: Import cycle crashes. Always use string class references in relationships (e.g. `relationship("Task", foreign_keys="Task.assigned_to")`).
4. **Pytest-Asyncio Event Loop Scope**:
   * *Gotcha*: Declaring async fixtures without `asyncio_mode = "auto"` in `pyproject.toml`.
   * *Symptom*: `AssertionError` or `ScopeMismatch` during test setup.
5. **Docker Container Code Caching**:
   * *Gotcha*: Running `docker compose up -d` after editing Python files without rebuilding.
   * *Symptom*: Old code continues running inside container. Rebuild with `docker compose build app && docker compose up -d`.

---

## 12. Full Project File Map

```
Employee Task Management/
├── .dockerignore                  # Excludes venv, pycache, env, and test files from Docker context
├── .env                           # Local environment variables (DB URL, JWT keys) - GIT IGNORED
├── .env.example                   # Template environment configuration file for setup guidance
├── .gitignore                     # Prevents committing venv, bytecode, secrets, and test coverage
├── .pre-commit-config.yaml        # Pre-commit hook configuration for ruff, black, and trailing whitespace
├── Dockerfile                     # Multi-stage Docker build file (python:3.12-slim, non-root user)
├── Dockerfile.dev                 # Development Dockerfile variant
├── PROJECT_DEEP_DIVE.md           # Master architectural deep-dive & developer onboarding guide
├── README.md                      # General project overview, Docker instructions, and  concepts
├── alembic.ini                    # Alembic migration configuration file
├── docker-compose.yml             # Orchestrates app and postgres:16-alpine containers with healthchecks
├── docker-entrypoint.sh           # Container startup shell script running alembic migrations then uvicorn
├── postman_collection.json        # Postman collection for API endpoint testing with auth scripts
├── project_inventory.md           # Factual audit report of tech stack, schemas, and endpoint inventories
├── pyproject.toml                 # Tool configuration for Black, Ruff, Mypy, and Pytest
├── requirements-dev.txt           # Development & testing dependencies (pytest, black, ruff, mypy)
├── requirements.txt               # Core production dependencies (fastapi, asyncpg, sqlalchemy, alembic)
├── seed_admin.py                  # CLI script for seeding an initial Admin user into the database
├── run_qa_suite.py                # Standalone QA verification script
├── test_endpoints.py              # Manual integration test script
│
├── alembic/
│   ├── env.py                     # Alembic async migration environment script (run_sync wrapper)
│   ├── script.py.mako             # Template script for generating new Alembic migration revisions
│   └── versions/                  # Revision history folder containing SQL schema migration files
│       └── f2850ec5859c_initial_migration.py  # Migration creating users, tasks, and leave_requests
│
├── app/
│   ├── __init__.py                # App package marker
│   ├── main.py                    # FastAPI app initialization, CORS middleware, & exception handlers
│   │
│   ├── core/                      # Core cross-cutting infrastructure
│   │   ├── __init__.py            # Core package marker
│   │   ├── config.py              # Pydantic BaseSettings loading .env with async URL validator
│   │   ├── exceptions.py          # Custom domain exceptions (ResourceNotFound, Authorization, etc.)
│   │   └── security.py            # Password hashing, JWT signing/decoding, get_current_user, require_role
│   │
│   ├── db/                        # Database infrastructure
│   │   ├── __init__.py            # DB package marker
│   │   ├── base.py                # create_async_engine, AsyncSessionLocal, and declarative Base
│   │   └── session.py             # get_db() async dependency generator yielding AsyncSession
│   │
│   ├── models/                    # Declarative ORM Database Models
│   │   ├── __init__.py            # Models package marker
│   │   ├── leave.py               # LeaveRequest ORM model (status, employee_id, reviewed_by)
│   │   ├── task.py                # Task ORM model (title, status, priority, assigned_to, created_by)
│   │   └── user.py                # User ORM model (full_name, email, hashed_password, role)
│   │
│   ├── routes/                    # API Presentation Layer (Endpoint Handlers)
│   │   ├── __init__.py            # Routes package marker
│   │   ├── auth.py                # /auth/ endpoints (register, login, refresh, swagger-login)
│   │   ├── leaves.py              # /leaves/ endpoints (submit, list, review)
│   │   ├── tasks.py               # /tasks/ endpoints (create, list, get, update, delete)
│   │   └── users.py               # /users/ endpoints (me, update me, list employees)
│   │
│   ├── schemas/                   # Pydantic DTO Schemas (Request/Response Parsing)
│   │   ├── __init__.py            # Schemas package marker
│   │   ├── leave.py               # Pydantic schemas for Leave creation, status update, and read
│   │   ├── task.py                # Pydantic schemas for Task creation, status update, and read
│   │   └── user.py                # Pydantic schemas for User registration, login, token, and read
│   │
│   └── services/                  # Business Logic Layer (Async Query Processing)
│       ├── __init__.py            # Services package marker
│       ├── auth_service.py        # Business logic for user registration, auth, and token refresh
│       ├── leave_service.py       # Business logic for leave submission, filtering, and admin review
│       └── task_service.py        # Business logic for task creation, RBAC update restrictions, & deletion
│
└── tests/                         # Pytest Automated Test Suite
    ├── __init__.py                # Tests package marker
    ├── conftest.py                # Pytest async fixtures (in-memory SQLite, AsyncClient, test users)
    ├── test_auth.py               # Integration tests for /auth/ endpoints
    ├── test_leaves.py             # Integration tests for /leaves/ endpoints
    ├── test_rbac.py               # Integration tests for RBAC role enforcement (403 forbidden checks)
    ├── test_services.py           # Isolated unit tests for auth, task, and leave service functions
    ├── test_tasks.py              # Integration tests for /tasks/ endpoints
    └── test_users.py              # Integration tests for /users/ endpoints
```
