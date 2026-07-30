# Employee Task Management System — Project Inventory Report

This document provides a comprehensive, evidence-based factual inventory of the current codebase of the Employee Task Management System. All statements below cite specific files, lines of code, or configuration details present in the repository.

---

## 1. Tech Stack & Dependencies

### Python Version
* **Documented Version**: Python 3.12+ (with 3.11 support noted in [README.md](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/README.md#L44)).
* **Language Features**: Codebase uses standard Python type annotations (`typing.List`, `typing.Optional`, `typing.Union`, `typing.Generator`), standard library `enum`, `datetime`, and object-oriented domain models.

### Third-Party Libraries & Packages ([requirements.txt](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/requirements.txt))

| Package | Version Requirement | Specific Project Usage | Cites / References |
|---|---|---|---|
| `fastapi` | `>=0.110.0` | Core Web Framework used for creating the REST API (`FastAPI`), registering routes (`APIRouter`), defining dependency injection (`Depends`), and auto-generating OpenAPI documentation. | [app/main.py:16](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L16) |
| `uvicorn` | `>=0.28.0` | ASGI Web Server implementation used to serve the FastAPI application locally. | [README.md:106](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/README.md#L106) |
| `sqlalchemy` | `>=2.0.28` | Relational Database ORM and SQL toolkit used for declarative model mapping (`declarative_base`), database engine creation (`create_engine`), session management (`sessionmaker`), and synchronous ORM querying. | [app/db/base.py:6-18](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/db/base.py#L6-L18) |
| `psycopg2-binary` | `>=2.9.9` | PostgreSQL DBAPI driver adapter enabling SQLAlchemy to communicate synchronously with the PostgreSQL database instance. | [.env.example:3](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/.env.example#L3), [app/db/base.py:6](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/db/base.py#L6) |
| `alembic` | `>=1.13.1` | Database migration framework used to manage database schema migrations, auto-generate revisions, and execute schema upgrades/downgrades against SQLAlchemy metadata. | [alembic/env.py:30](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/alembic/env.py#L30), [alembic/versions/f2850ec5859c_initial_migration.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/alembic/versions/f2850ec5859c_initial_migration.py) |
| `bcrypt` | `>=4.1.2` | Password hashing library used for salted password hashing (`hashpw`) and password verification (`checkpw`). | [app/core/security.py:7-24](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L7-L24) |
| `pyjwt[crypto]` | `>=2.8.0` | JWT library used to encode (`jwt.encode`) and decode/verify (`jwt.decode`) signed JSON Web Tokens using the HS256 algorithm. | [app/core/security.py:26-97](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L26-L97) |
| `pydantic[email]` | `>=2.6.4` | Data validation and parsing library (with email validation via `EmailStr`) used to define API request/response schemas. | [app/schemas/user.py:7](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/schemas/user.py#L7) |
| `pydantic-settings` | `>=2.2.1` | Configuration settings parser extending Pydantic (`BaseSettings`, `SettingsConfigDict`) to parse environment variables from `.env`. | [app/core/config.py:4-11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/config.py#L4-L11) |
| `python-dotenv` | `>=1.0.1` | Utility integrated into `pydantic-settings` to load environment variables from `.env` files into Python process environment. | [app/core/config.py:8](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/config.py#L8) |
| `python-multipart` | `>=0.0.7` | Form-data parsing package required by FastAPI to process form-encoded HTTP request payloads in `OAuth2PasswordRequestForm`. | [app/routes/auth.py:38](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L38) |

### Database & ORM Architecture
* **Database Engine**: PostgreSQL (`postgresql://...`). Connection string format defined in [.env.example:3](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/.env.example#L3).
* **ORM Style**: SQLAlchemy 2.0 Declarative ORM style (`declarative_base()`). Uses synchronous `Session` instances with `pool_pre_ping=True` in `create_engine`.
* **Execution Paradigm**: 100% synchronous database interaction using standard synchronous SQLAlchemy queries (`db.query(...)`). No async database drivers or `AsyncSession` instances are used.

---

## 2. FastAPI Concepts & Features Implemented

### 1. Routers & App Structure
* Main application entrypoint initialized in [app/main.py:16](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L16).
* Endpoints organized across 4 domain routers in `app/routes/`:
  1. `Authentication`: [app/routes/auth.py:8](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L8) (`prefix="/auth"`, `tags=["Authentication"]`)
  2. `Users`: [app/routes/users.py:9](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/users.py#L9) (`prefix="/users"`, `tags=["Users"]`)
  3. `Tasks`: [app/routes/tasks.py:11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L11) (`prefix="/tasks"`, `tags=["Tasks"]`)
  4. `Leaves`: [app/routes/leaves.py:11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L11) (`prefix="/leaves"`, `tags=["Leaves"]`)
* All 4 routers registered on main `FastAPI` instance via `app.include_router()` in [app/main.py:32-35](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L32-L35).

### 2. Dependency Injection (`Depends`)
The codebase implements 5 specific FastAPI dependency functions/factories:
1. `get_db`: Generator dependency yielding a database session and closing it post-request in [app/db/session.py:5-14](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/db/session.py#L5-L14). Used in route functions to inject `Session`.
2. `oauth2_scheme`: Instance of `OAuth2PasswordBearer(tokenUrl="/auth/swagger-login")` in [app/core/security.py:107](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L107) extracting HTTP Bearer tokens from the `Authorization` header.
3. `get_current_user`: Authentication dependency in [app/core/security.py:109-131](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L109-L131) dependent on `get_db` and `oauth2_scheme`. Decodes the access token, verifies user existence in DB, and injects the authenticated `User` ORM instance.
4. `require_role(required_role)`: RBAC dependency factory in [app/core/security.py:133-141](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L133-L141) dependent on `get_current_user`. Asserts user role equality and raises `AuthorizationException` if unauthorized.
5. `OAuth2PasswordRequestForm`: Built-in FastAPI form dependency used in [app/routes/auth.py:38](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L38) to parse form-encoded username/password credentials.

### 3. Pydantic Models & Validation Schemas
The application defines 16 Pydantic models across settings and 3 schema modules:

* **Settings Schema** ([app/core/config.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/config.py)):
  * `Settings` (`BaseSettings`): Loads environment variables (`DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, token expiration settings, `CORS_ORIGINS`). Uses `@field_validator("CORS_ORIGINS", mode="before")` to parse string or JSON array representations into `List[str]`.

* **User Schemas** ([app/schemas/user.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/schemas/user.py)):
  * `UserBase`: Validates `email: EmailStr` and `full_name: str`.
  * `UserCreate` (extends `UserBase`): Validates registration input (`password: str`).
  * `UserUpdate`: Validates profile updates (`full_name: Optional[str]`).
  * `UserLogin`: Validates authentication login input (`email: EmailStr`, `password: str`).
  * `Token`: Validates output token payload (`access_token`, `refresh_token`, `token_type="bearer"`).
  * `TokenRefresh`: Validates refresh token request (`refresh_token: str`).
  * `TokenData`: Internal validation schema for decoded token data (`email: Optional[str]`, `role: Optional[UserRole]`).
  * `UserRead` / `UserResponse` (extends `UserBase`): Response model with `model_config = ConfigDict(from_attributes=True)` (`id: int`, `role: UserRole`, `created_at: datetime`).

* **Task Schemas** ([app/schemas/task.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/schemas/task.py)):
  * `TaskBase`: Validates base attributes (`title: str`, `description: str`, `priority: TaskPriority`, `due_date: date`).
  * `TaskCreate` (extends `TaskBase`): Validates creation input (`assigned_to: int`).
  * `TaskUpdate`: Validates partial updates (`title`, `description`, `status`, `priority`, `due_date`, `assigned_to` as optional fields).
  * `TaskUpdateStatus`: Validates employee status updates (`status: TaskStatus`).
  * `TaskRead` (extends `TaskBase`): Response model with `model_config = ConfigDict(from_attributes=True)` (`id: int`, `status: TaskStatus`, `assigned_to: int`, `created_by: int`, `created_at: datetime`).

* **Leave Schemas** ([app/schemas/leave.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/schemas/leave.py)):
  * `LeaveBase`: Validates base leave fields (`reason: str`, `start_date: date`, `end_date: date`).
  * `LeaveCreate` (extends `LeaveBase`): Schema for submitting leave requests.
  * `LeaveUpdateStatus`: Validates Admin status review (`status: LeaveStatus`).
  * `LeaveRead` (extends `LeaveBase`): Response model with `model_config = ConfigDict(from_attributes=True)` (`id: int`, `employee_id: int`, `status: LeaveStatus`, `reviewed_by: Optional[int]`, `created_at: datetime`).

### 4. Path and Query Parameters
* **Path Parameters**:
  * `id: int` in [app/routes/tasks.py:50](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L50), [app/routes/tasks.py:61](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L61), [app/routes/tasks.py:74](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L74).
  * `id: int` in [app/routes/leaves.py:38](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L38).
* **Query Parameters**:
  * `status: Optional[TaskStatus] = None` in [app/routes/tasks.py:26](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L26).
  * `priority: Optional[TaskPriority] = None` in [app/routes/tasks.py:27](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L27).
  * `sort_by: Optional[str] = None` in [app/routes/tasks.py:28](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L28).
  * `skip: int = 0` in [app/routes/tasks.py:29](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L29).
  * `limit: int = 10` in [app/routes/tasks.py:30](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L30).
  * `status: Optional[LeaveStatus] = None` in [app/routes/leaves.py:26](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L26).

### 5. Status Codes Explicitly Used
* `status.HTTP_200_OK`: Implicit default response code for standard `GET`, `PATCH`, and login/refresh `POST` endpoints.
* `status.HTTP_201_CREATED`: Explicitly specified in `@router.post("/register")` ([app/routes/auth.py:10](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L10)), `@router.post("/")` ([app/routes/tasks.py:13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L13)), `@router.post("/")` ([app/routes/leaves.py:13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L13)).
* `status.HTTP_204_NO_CONTENT`: Explicitly specified in `@router.delete("/{id}")` and returned via `Response(status_code=status.HTTP_204_NO_CONTENT)` in [app/routes/tasks.py:72-82](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L72-L82).
* `status.HTTP_400_BAD_REQUEST`: Returned by exception handlers for `UserAlreadyExistsException` ([app/main.py:55](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L55)) and `BadRequestException` ([app/main.py:82](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L82)).
* `status.HTTP_401_UNAUTHORIZED`: Returned by exception handlers for `InvalidCredentialsException` ([app/main.py:62](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L62)) and `AuthenticationException` ([app/main.py:68](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L68)).
* `status.HTTP_403_FORBIDDEN`: Returned by exception handler for `AuthorizationException` ([app/main.py:76](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L76)).
* `status.HTTP_404_NOT_FOUND`: Returned by exception handler for `ResourceNotFoundException` ([app/main.py:48](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L48)).
* `status.HTTP_500_INTERNAL_SERVER_ERROR`: Returned by exception handler for fallback `AppException` ([app/main.py:90](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L90)).

### 6. Exception Handling Strategy
* Custom domain exception hierarchy in [app/core/exceptions.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/exceptions.py):
  * `AppException(Exception)` (Base application exception)
  * `ResourceNotFoundException` (HTTP 404 mapping)
  * `UserAlreadyExistsException` (HTTP 400 mapping)
  * `InvalidCredentialsException` (HTTP 401 mapping)
  * `AuthenticationException` (HTTP 401 mapping)
  * `AuthorizationException` (HTTP 403 mapping)
  * `BadRequestException` (HTTP 400 mapping)
* Centralized exception handlers registered on `app` using `@app.exception_handler(...)` in [app/main.py:45-92](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L45-L92), converting internal domain exceptions into consistent `JSONResponse` objects with `{"detail": exc.message}`.

### 7. Middleware
* `CORSMiddleware` registered in [app/main.py:23-29](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L23-L29), configured with `allow_origins=settings.CORS_ORIGINS`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.

### 8. Async/Await & Background Tasks
* **Async/Await**: None. All route functions, dependency callables, and service functions are synchronous `def` functions.
* **Background Tasks**: None. `BackgroundTasks` from `fastapi` is not imported or utilized anywhere in the project.

### 9. OpenAPI / Swagger Customizations
* Metadata configured on `FastAPI` instance: `title`, `description`, `version` in [app/main.py:16-20](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L16-L20).
* Endpoints categorized via `tags` on router instances ([app/routes/auth.py:8](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L8), [app/routes/users.py:9](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/users.py#L9), [app/routes/tasks.py:11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L11), [app/routes/leaves.py:11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L11)).
* Endpoint docstrings rendered directly into Swagger UI documentation.
* Schema visibility override: `include_in_schema=False` applied to `@router.post("/swagger-login")` in [app/routes/auth.py:37](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L37) to hide Swagger form authentication from public schema docs while enabling the UI 'Authorize' button.

---

## 3. Database Design

### 1. Database Tables & Fields

#### Table: `users` ([app/models/user.py:11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py#L11))

| Field | Type | Constraints | Default |
|---|---|---|---|
| `id` | `Integer` | Primary Key, Index | Auto-increment |
| `full_name` | `String` | `nullable=False` | None |
| `email` | `String` | Unique, Index, `nullable=False` | None |
| `hashed_password` | `String` | `nullable=False` | None |
| `role` | `SQLEnum(UserRole)` | `nullable=False` (`ADMIN`, `EMPLOYEE`) | `UserRole.EMPLOYEE` |
| `created_at` | `DateTime(timezone=True)` | `nullable=False` | `func.now()` |

#### Table: `tasks` ([app/models/task.py:17](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/task.py#L17))

| Field | Type | Constraints | Default |
|---|---|---|---|
| `id` | `Integer` | Primary Key, Index | Auto-increment |
| `title` | `String` | `nullable=False` | None |
| `description` | `Text` | `nullable=False` | None |
| `status` | `SQLEnum(TaskStatus)` | `nullable=False` (`PENDING`, `IN_PROGRESS`, `COMPLETED`) | `TaskStatus.PENDING` |
| `priority` | `SQLEnum(TaskPriority)` | `nullable=False` (`LOW`, `MEDIUM`, `HIGH`) | None |
| `due_date` | `Date` | `nullable=False` | None |
| `assigned_to` | `Integer` | Foreign Key (`users.id`, `ondelete="CASCADE"`), `nullable=False` | None |
| `created_by` | `Integer` | Foreign Key (`users.id`, `ondelete="CASCADE"`), `nullable=False` | None |
| `created_at` | `DateTime(timezone=True)` | `nullable=False` | `func.now()` |

#### Table: `leave_requests` ([app/models/leave.py:12](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/leave.py#L12))

| Field | Type | Constraints | Default |
|---|---|---|---|
| `id` | `Integer` | Primary Key, Index | Auto-increment |
| `employee_id` | `Integer` | Foreign Key (`users.id`, `ondelete="CASCADE"`), `nullable=False` | None |
| `reason` | `String` | `nullable=False` | None |
| `start_date` | `Date` | `nullable=False` | None |
| `end_date` | `Date` | `nullable=False` | None |
| `status` | `SQLEnum(LeaveStatus)` | `nullable=False` (`PENDING`, `APPROVED`, `REJECTED`) | `LeaveStatus.PENDING` |
| `reviewed_by` | `Integer` | Foreign Key (`users.id`, `ondelete="SET NULL"`), `nullable=True` | None |
| `created_at` | `DateTime(timezone=True)` | `nullable=False` | `func.now()` |

### 2. Entity Relationships & Foreign Keys
1. **User assigned tasks**: One-to-Many relationship between `User.id` and `Task.assigned_to`.
   * `User.assigned_tasks` back-populates `Task.assigned_employee` with `cascade="all, delete-orphan"` ([app/models/user.py:22-27](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py#L22-L27)).
   * FK `Task.assigned_to` -> `users.id` with `ondelete="CASCADE"` ([app/models/task.py:26](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/task.py#L26)).
2. **User created tasks**: One-to-Many relationship between `User.id` and `Task.created_by`.
   * `User.created_tasks` back-populates `Task.creator` with `cascade="all, delete-orphan"` ([app/models/user.py:28-33](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py#L28-L33)).
   * FK `Task.created_by` -> `users.id` with `ondelete="CASCADE"` ([app/models/task.py:27](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/task.py#L27)).
3. **User submitted leaves**: One-to-Many relationship between `User.id` and `LeaveRequest.employee_id`.
   * `User.leave_requests` back-populates `LeaveRequest.employee` with `cascade="all, delete-orphan"` ([app/models/user.py:34-39](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py#L34-L39)).
   * FK `LeaveRequest.employee_id` -> `users.id` with `ondelete="CASCADE"` ([app/models/leave.py:16](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/leave.py#L16)).
4. **Admin reviewed leaves**: One-to-Many relationship between `User.id` and `LeaveRequest.reviewed_by`.
   * `User.reviewed_leaves` back-populates `LeaveRequest.reviewer` ([app/models/user.py:40-44](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py#L40-L44)).
   * FK `LeaveRequest.reviewed_by` -> `users.id` with `ondelete="SET NULL"` ([app/models/leave.py:21](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/leave.py#L21)).

### 3. Alembic Migrations History
The repository contains 1 migration file in `alembic/versions/`:
* **Revision**: `f2850ec5859c`
* **File**: [alembic/versions/f2850ec5859c_initial_migration.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/alembic/versions/f2850ec5859c_initial_migration.py)
* **Description**: `initial migration`
* **Revises**: `None` (Base migration)
* **Date**: `2026-07-18 22:49:41`
* **Operations Executed**:
  * Creates table `users` and indexes `ix_users_email`, `ix_users_id`.
  * Creates table `leave_requests` and index `ix_leave_requests_id` with foreign keys to `users.id`.
  * Creates table `tasks` and index `ix_tasks_id` with foreign keys to `users.id`.

---

## 4. Authentication & Security Implementation

### 1. JWT Implementation Details
* **Algorithm**: `HS256` (HMAC with SHA-256) hardcoded in [app/core/security.py:45](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L45).
* **Token Dual-Token Strategy**:
  1. **Access Token**:
     * Secret Key: `settings.JWT_SECRET_KEY` ([app/core/security.py:59](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L59)).
     * Expiration: Default 15 minutes (`settings.ACCESS_TOKEN_EXPIRE_MINUTES`) ([app/core/security.py:54](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L54)).
     * Payload: `{"sub": email, "role": role, "type": "access", "iat": timestamp, "exp": timestamp}` ([app/core/security.py:38-44](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L38-L44)).
  2. **Refresh Token**:
     * Secret Key: `settings.JWT_REFRESH_SECRET_KEY` ([app/core/security.py:76](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L76)).
     * Expiration: Default 7 days (`settings.REFRESH_TOKEN_EXPIRE_DAYS`) ([app/core/security.py:71](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L71)).
     * Payload: `{"sub": email, "role": role, "type": "refresh", "iat": timestamp, "exp": timestamp}` ([app/core/security.py:38-44](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L38-L44)).
* **Validation & Token Type Checking**:
  * `decode_access_token` verifies signature with `JWT_SECRET_KEY` and asserts `payload.get("type") == "access"` ([app/core/security.py:86-87](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L86-L87)).
  * `decode_refresh_token` verifies signature with `JWT_REFRESH_SECRET_KEY` and asserts `payload.get("type") == "refresh"` ([app/core/security.py:95-96](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L95-L96)).
  * Token verification failures raise `jwt.ExpiredSignatureError` or `jwt.InvalidTokenError`, caught and re-raised as `AuthenticationException` ([app/core/security.py:118-121](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L118-L121)).

### 2. Password Hashing
* **Library**: `bcrypt` package.
* **Salt Generation**: `bcrypt.gensalt()` ([app/core/security.py:12](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L12)).
* **Hashing Function**: `bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")` in `hash_password()` ([app/core/security.py:7-13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L7-L13)).
* **Verification Function**: `bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))` in `verify_password()` ([app/core/security.py:15-24](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L15-L24)).

### 3. Role-Based Access Control (RBAC) Mechanism
* Roles defined via Python `Enum` in [app/models/user.py:7-9](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/models/user.py#L7-L9): `UserRole.ADMIN = "ADMIN"`, `UserRole.EMPLOYEE = "EMPLOYEE"`.
* **Route Level RBAC**: Enforced via `require_role(required_role: UserRole)` dependency factory ([app/core/security.py:133-141](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/core/security.py#L133-L141)). Inspects `current_user.role` and raises `AuthorizationException("Action requires {required_role.value} role.")` if mismatched.
* **Service Level Ownership Checks**:
  * `task_service.py`: Limits task querying ([task_service.py:54](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L54)) and individual task access ([task_service.py:86](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L86)) for `EMPLOYEE` role to tasks where `assigned_to == user.id`.
  * `leave_service.py`: Limits leave query results for `EMPLOYEE` role to `employee_id == user.id` ([leave_service.py:46](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L46)).

---

## 5. API Endpoints — Complete Inventory

| Method | Endpoint Path | Auth / Role Requirement | Request Body Schema | Response Schema / Status | Description | File / Function Evidence |
|---|---|---|---|---|---|---|
| `GET` | `/` | None (Public) | None | `dict` (200 OK) | Returns welcome message and link to `/docs`. | [app/main.py:37](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/main.py#L37) (`read_root`) |
| `POST` | `/auth/register` | None (Public) | `UserCreate` | `UserRead` (201 Created) | Registers a new user with default role `EMPLOYEE`. | [app/routes/auth.py:10](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L10) (`register`) |
| `POST` | `/auth/login` | None (Public) | `UserLogin` | `Token` (200 OK) | Authenticates credentials and returns access & refresh JWT tokens. | [app/routes/auth.py:19](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L19) (`login`) |
| `POST` | `/auth/swagger-login` | None (Public) | `OAuth2PasswordRequestForm` (Form data) | `Token` (200 OK) | Form-data authentication endpoint for Swagger UI Authorize button (hidden from schema). | [app/routes/auth.py:37](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L37) (`swagger_login`) |
| `POST` | `/auth/refresh` | None (Public) | `TokenRefresh` | `Token` (200 OK) | Exchanges a valid refresh token for a new access token. | [app/routes/auth.py:55](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/auth.py#L55) (`refresh`) |
| `GET` | `/users/me` | Bearer Token (`get_current_user`) | None | `UserRead` (200 OK) | Retrieves current logged-in user's profile. | [app/routes/users.py:11](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/users.py#L11) (`get_me`) |
| `PATCH` | `/users/me` | Bearer Token (`get_current_user`) | `UserUpdate` | `UserRead` (200 OK) | Updates current logged-in user's non-sensitive profile fields (`full_name`). | [app/routes/users.py:18](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/users.py#L18) (`update_me`) |
| `GET` | `/users/` | Bearer Token (`require_role(ADMIN)`) | None | `List[UserRead]` (200 OK) | Lists all employees in the system (Admin only). | [app/routes/users.py:34](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/users.py#L34) (`list_employees`) |
| `POST` | `/tasks/` | Bearer Token (`require_role(ADMIN)`) | `TaskCreate` | `TaskRead` (201 Created) | Creates a task and assigns it to an employee (Admin only). | [app/routes/tasks.py:13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L13) (`create_task`) |
| `GET` | `/tasks/` | Bearer Token (`get_current_user`) | None (Query: `status`, `priority`, `sort_by`, `skip`, `limit`) | `List[TaskRead]` (200 OK) | Lists tasks (Admin sees all; Employee sees assigned tasks). Supports filters, sorting, pagination. | [app/routes/tasks.py:24](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L24) (`list_tasks`) |
| `GET` | `/tasks/{id}` | Bearer Token (`get_current_user`) | None | `TaskRead` (200 OK) | Retrieves details of single task by ID (Employee limited to own task). | [app/routes/tasks.py:48](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L48) (`get_task`) |
| `PATCH` | `/tasks/{id}` | Bearer Token (`get_current_user`) | `TaskUpdate` | `TaskRead` (200 OK) | Updates task (Admin: all fields; Employee: `status` field only). | [app/routes/tasks.py:59](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L59) (`update_task`) |
| `DELETE` | `/tasks/{id}` | Bearer Token (`require_role(ADMIN)`) | None | None (204 No Content) | Deletes task by ID (Admin only). | [app/routes/tasks.py:72](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/tasks.py#L72) (`delete_task`) |
| `POST` | `/leaves/` | Bearer Token (`get_current_user`) | `LeaveCreate` | `LeaveRead` (201 Created) | Submits a leave request for current user. | [app/routes/leaves.py:13](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L13) (`create_leave`) |
| `GET` | `/leaves/` | Bearer Token (`get_current_user`) | None (Query: `status`) | `List[LeaveRead]` (200 OK) | Lists leave requests (Admin sees all; Employee sees own requests). | [app/routes/leaves.py:24](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L24) (`list_leaves`) |
| `PATCH` | `/leaves/{id}` | Bearer Token (`require_role(ADMIN)`) | `LeaveUpdateStatus` | `LeaveRead` (200 OK) | Approves or rejects a leave request and sets `reviewed_by` (Admin only). | [app/routes/leaves.py:36](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/routes/leaves.py#L36) (`review_leave`) |

---

## 6. Business Logic Rules Implemented

| Rule Description | Implementation Enforcement Location | Evidence / Logic Details |
|---|---|---|
| **Email Uniqueness on Registration** | [app/services/auth_service.py:21-23](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/auth_service.py#L21-L23) | Checks if `User.email` exists; raises `UserAlreadyExistsException` if match found. |
| **Default User Role Assignment** | [app/services/auth_service.py:30](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/auth_service.py#L30) | Public registration hardcodes `role=UserRole.EMPLOYEE`. |
| **Assignee Existence Validation** | [app/services/task_service.py:17-19](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L17-L19) | Checks if `User` with ID `task_in.assigned_to` exists; raises `ResourceNotFoundException` if missing. |
| **Task Assignment Employee Role Restriction** | [app/services/task_service.py:22-23](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L22-L23) | Validates `assignee.role == UserRole.EMPLOYEE`; raises `BadRequestException` if assignee is an Admin. |
| **Task List Role Scope Isolation** | [app/services/task_service.py:54-55](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L54-L55) | Filters query `Task.assigned_to == user.id` if `user.role == UserRole.EMPLOYEE`. Admins receive unfiltered list. |
| **Task Dynamic Column Sorting Validation** | [app/services/task_service.py:66-69](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L66-L69) | Validates `hasattr(Task, sort_by)` before applying `order_by`; raises `BadRequestException` if column invalid. Defaults to `created_at desc`. |
| **Task Single Object Ownership Restriction** | [app/services/task_service.py:86-87](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L86-L87) | If `user.role == UserRole.EMPLOYEE` and `db_task.assigned_to != user.id`, raises `AuthorizationException`. |
| **Task Employee Update Attribute Whitelisting** | [app/services/task_service.py:105-109](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L105-L109) | When `user.role == UserRole.EMPLOYEE`, checks provided keys in update payload; raises `AuthorizationException` if any key other than `"status"` is present. |
| **Task Deletion Service-Level Enforcement** | [app/services/task_service.py:123-124](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/task_service.py#L123-L124) | Asserts `user.role == UserRole.ADMIN`; raises `AuthorizationException` if non-admin attempts deletion. |
| **Leave Date Order Constraint** | [app/services/leave_service.py:21-22](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L21-L22) | Checks `leave_in.end_date < leave_in.start_date`; raises `BadRequestException` if end date precedes start date. |
| **Leave Submission Default Status** | [app/services/leave_service.py:29](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L29) | Sets `status=LeaveStatus.PENDING` on leave request creation. |
| **Leave List Role Scope Isolation** | [app/services/leave_service.py:46-47](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L46-L47) | Filters query `LeaveRequest.employee_id == user.id` if `user.role == UserRole.EMPLOYEE`. |
| **Leave Review Status Immutability** | [app/services/leave_service.py:68-69](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L68-L69) | Checks `db_leave.status != LeaveStatus.PENDING`; raises `BadRequestException` if leave has already been reviewed. |
| **Leave Review Transition Whitelisting** | [app/services/leave_service.py:72-73](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L72-L73) | Checks `review_in.status not in [LeaveStatus.APPROVED, LeaveStatus.REJECTED]`; raises `BadRequestException` if attempting to set status back to PENDING or invalid state. |
| **Leave Reviewer Audit Tracking** | [app/services/leave_service.py:77](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/app/services/leave_service.py#L77) | Sets `db_leave.reviewed_by = reviewer_id` (the active Admin's user ID) upon review completion. |

---

## 7. Testing, Verification & Tooling Present

### 1. Test Scripts & Verification Suites
* [test_endpoints.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/test_endpoints.py): 182-line standalone Python verification script using standard library `urllib.request`. Executes an 11-step end-to-end integration flow (Admin Login, Employee Registration, Employee Login, Token Refresh, Get Profile, Admin Task Creation, Employee Task Listing, Employee Status Update, Employee Leave Submission, Admin Leave Approval, RBAC enforcement check).
* [run_qa_suite.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/run_qa_suite.py): 457-line comprehensive automated QA test suite using `urllib.request`. Seeds 5 employee accounts, executes 18 detailed test scenarios across auth, RBAC, input edge cases, error handling, and writes structured outputs.
* [test_results.json](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/test_results.json): Structured JSON file containing the full execution results of the 18 QA test runs.
* [test_report.md](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/test_report.md): Markdown summary report documenting the execution metrics and pass/fail statuses of the QA test suite.

### 2. Developer Tooling & Utilities
* [seed_admin.py](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/seed_admin.py): Administrative seeding CLI utility. Uses SQLAlchemy `SessionLocal` and `hash_password` to insert an initial `ADMIN` user into the database. Supports both interactive prompts (`input`, `getpass`) and non-interactive execution via environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`).
* [postman_collection.json](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/postman_collection.json): Pre-configured Postman v2.1 collection covering all API endpoints. Includes environment collection variables (`{{access_token}}`, `{{refresh_token}}`) and automated post-response test scripts on `/auth/login` and `/auth/refresh` to auto-populate tokens into variables.

### 3. Version Control Configuration ([.gitignore](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/.gitignore))
Excludes:
* **Python artifacts**: `__pycache__/`, `*.py[cod]`, `*$py.class`, `.venv/`, `venv/`, `ENV/`, `env/`, `build/`, `dist/`, `*.egg-info/`
* **Environment files**: `.env`
* **IDE directories**: `.idea/`, `.vscode/`, `*.suo`, `*.ntvs*`, `*.njsproj`, `*.sln`, `*.swp`
* **OS artifacts**: `Thumbs.db`, `ehthumbs.db`, `Desktop.ini`

### 4. Documentation ([README.md](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/README.md))
Documents:
* High-level architectural overview & folder tree.
* System prerequisites (Python 3.12+/3.11+, PostgreSQL).
* Step-by-step setup (virtualenv creation, `requirements.txt` installation, `.env` copy/configuration).
* Alembic migration commands (`alembic upgrade head`, `alembic revision --autogenerate`).
* `seed_admin.py` execution instructions.
* Uvicorn server startup and links to `/docs` and `/redoc`.
* API verification instructions via `test_endpoints.py` and Postman collection import.

---

## 8. Absent Features & Components

This section factually records standard backend features and tools that are **not** present in this codebase:

* **No `pytest` / `unittest` Test Suite**: No standard Python testing framework configuration (`pytest.ini`, `conftest.py`) or `tests/` directory exists. API testing relies on custom HTTP client scripts (`test_endpoints.py`, `run_qa_suite.py`).
* **No Containerization Setup**: No `Dockerfile`, `.dockerignore`, or `docker-compose.yml` configuration files exist in the project.
* **No CI/CD Pipeline Configuration**: No continuous integration workflow files exist (e.g. no `.github/workflows/`, `.gitlab-ci.yml`, or `azure-pipelines.yml`).
* **No Logging Module Configuration**: No application logging configuration (e.g., standard `logging`, `loguru`, or structured JSON logging) is configured within `app/`. (Logging setup is present only inside `alembic/env.py` for migration output).
* **No Rate Limiting / Throttling**: No rate-limiting middleware or library (e.g., `slowapi` or Redis-backed rate limiting) is implemented on any endpoint.
* **No Asynchronous Database / Handling**: No async ORM engine, `AsyncSession`, `asyncpg` driver, or `async def` endpoint signatures are present.
* **No Token Revocation / Blacklisting**: No token blacklist or revocation store (e.g., Redis or database token invalidation table) exists; JWTs remain valid until their expiration timestamp.
* **No Password Reset or Email Verification**: No endpoints or email services exist for user password resets or email verification flows.
* **No Soft Delete Support**: Task deletion executes hard SQL `DELETE` queries (`db.delete(db_task)`).
* **No Leave Pagination**: The `/leaves/` endpoint does not take `skip` or `limit` query parameters (unlike `/tasks/`).
