# Project Build Prompt: Employee Task Management System (Backend-Only)

Use this prompt as the master specification when generating/building this project.

---

## 1. Project Purpose

Build a **backend-only Employee Task Management System** in Python, designed primarily as a **learning and portfolio project** — not a production-scale enterprise system. The code must be clean, modular, easy to read, and easy for the author to confidently explain in a technical .

**Priorities:**
- Readability and maintainability over cleverness
- Only implement what is explicitly listed below — no extra features
- Avoid over-engineering: no unnecessary design patterns, no excessive abstraction layers, no speculative "future-proofing" code
- Every class, function, and table must have an obvious, explainable purpose

---

## 2. Tech Stack (mandatory)

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Web Framework | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Auth | JWT (access + refresh tokens) |
| Password Hashing | `bcrypt` (use the library directly, not `passlib`) |
| Validation | Pydantic v2 |
| API Docs | FastAPI's built-in Swagger/OpenAPI |
| API Testing | Postman (manual collection, no automated test suite required for v1) |
| Config | `.env` file + `python-dotenv` / Pydantic `BaseSettings` |

---

## 3. Folder Structure (must follow exactly)

```
app/
├── main.py                # FastAPI app entrypoint
├── core/
│   ├── config.py          # loads env vars via Pydantic BaseSettings
│   └── security.py        # JWT creation/verification, bcrypt hash/verify
├── db/
│   ├── base.py             # SQLAlchemy Base + session setup
│   └── session.py          # get_db() dependency
├── models/
│   ├── user.py
│   ├── task.py
│   └── leave.py
├── schemas/
│   ├── user.py
│   ├── task.py
│   └── leave.py
├── routes/
│   ├── auth.py
│   ├── users.py
│   ├── tasks.py
│   └── leaves.py
├── services/               # business logic, kept thin and per-domain
│   ├── auth_service.py
│   ├── task_service.py
│   └── leave_service.py
alembic/
├── env.py
└── versions/
.env                        # NEVER committed
.env.example                # committed, no real values
.gitignore
requirements.txt
README.md
```

Do not add extra folders (no `utils/`, no `helpers/`, no generic `common/`) unless a genuine cross-cutting need arises.

---

## 4. Database Design

Three tables only. Keep relationships simple.

### `users`
| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| full_name | String | |
| email | String, unique | login identifier |
| hashed_password | String | bcrypt hash, never plaintext |
| role | Enum(`ADMIN`, `EMPLOYEE`) | |
| created_at | DateTime | default now |

### `tasks`
| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| title | String | |
| description | Text | |
| status | Enum(`PENDING`, `IN_PROGRESS`, `COMPLETED`) | default `PENDING` |
| priority | Enum(`LOW`, `MEDIUM`, `HIGH`) | |
| due_date | Date | |
| assigned_to | Integer, FK → `users.id` | employee the task is assigned to |
| created_by | Integer, FK → `users.id` | always an Admin (see rule below) |
| created_at | DateTime | default now |

**Business rule — Task ownership/assignment:**
Only **Admins** can create and assign tasks. `created_by` will therefore always resolve to a user with role `ADMIN`. Employees can only **view** and **update the status** of tasks assigned to them — they cannot create, reassign, or delete tasks.

### `leave_requests`
| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| employee_id | Integer, FK → `users.id` | who applied for leave |
| reason | String | |
| start_date | Date | |
| end_date | Date | |
| status | Enum(`PENDING`, `APPROVED`, `REJECTED`) | default `PENDING` |
| reviewed_by | Integer, FK → `users.id`, nullable | which Admin approved/rejected it |
| created_at | DateTime | default now |

**Business rule:** Employees create their own leave requests (`employee_id` = their own id). Only Admins can update `status` and set `reviewed_by`.

---

## 5. Feature Requirements

### 5.1 Authentication
- `POST /auth/register` — creates a user (role defaults to `EMPLOYEE`; only allow `ADMIN` creation via a seed script or a protected admin-only endpoint, not open registration)
- `POST /auth/login` — verifies email + password (bcrypt), returns **access token** (short-lived, ~15–30 min) and **refresh token** (long-lived, ~7 days)
- `POST /auth/refresh` — exchanges a valid refresh token for a new access token
- Passwords hashed with `bcrypt` directly (no `passlib`)

### 5.2 Role-Based Access Control (RBAC)
- Two roles: `ADMIN`, `EMPLOYEE`
- Use a FastAPI dependency (e.g. `require_role("ADMIN")`) to protect admin-only routes
- Employees can only access/modify their own resources (tasks assigned to them, their own leave requests)

### 5.3 Employee Profile Management
- `GET /users/me` — view own profile
- `PATCH /users/me` — update own basic profile fields (name, etc. — not role or email)
- `GET /users/` — Admin only, list all employees

### 5.4 Task Management
- `POST /tasks` — Admin only, create + assign a task to an employee
- `GET /tasks` — list tasks (Admin sees all, Employee sees only their own assigned tasks)
- `GET /tasks/{id}` — view a single task (with ownership check)
- `PATCH /tasks/{id}` — Admin can update any field; Employee can only update `status`
- `DELETE /tasks/{id}` — Admin only

**Task listing must support** (via query params, not new tables/endpoints):
- Filter by `status`, `priority`
- Sort by any valid column (e.g. `due_date`, `created_at`)
- Pagination via `skip` and `limit`

Example: `GET /tasks?status=PENDING&priority=HIGH&sort_by=due_date&skip=0&limit=10`

### 5.5 Leave Management
- `POST /leaves` — Employee submits a leave request
- `GET /leaves` — Admin sees all requests (filterable by `status`); Employee sees only their own
- `PATCH /leaves/{id}` — Admin only, approve/reject (sets `status` and `reviewed_by`)

### 5.6 Cross-cutting requirements
- Consistent, meaningful HTTP status codes (200/201/204, 400, 401, 403, 404, 422)
- Centralized exception handling (FastAPI exception handlers, not scattered try/except blocks)
- Pydantic schemas for every request/response body (separate `Create`, `Update`, `Read` schemas per resource)
- Auto-generated Swagger docs at `/docs`

---

## 6. Database Migrations (Alembic)

- Initialize with `alembic init alembic`
- Point `alembic/env.py` at the project's SQLAlchemy `Base.metadata`
- Load the database URL from the `.env` file, not hardcoded
- Every schema change must go through:
  ```
  alembic revision --autogenerate -m "description of change"
  alembic upgrade head
  ```
- Commit migration files to version control; document these two commands in the `README.md`

---

## 7. Security & Secrets Management (mandatory — do not skip)

- **All secrets** (JWT secret key, database URL/credentials, any API keys) must be loaded from environment variables via a `.env` file — **never hardcoded in source code**.
- Provide a `.env.example` file with placeholder values only (e.g. `JWT_SECRET_KEY=changeme`), and commit that instead of the real `.env`.
- Add `.env` to `.gitignore` from the very first commit.
- JWT secret key must be a long, random string (generate with `openssl rand -hex 32` or Python's `secrets.token_hex(32)`) — never a guessable string.
- Access tokens short-lived; refresh tokens longer-lived but still expiring — no non-expiring tokens.
- Passwords are **never** logged, returned in API responses, or stored in plaintext anywhere.
- Use Pydantic `BaseSettings` (in `core/config.py`) to load and validate all env vars at startup, so the app fails fast if a required secret is missing, rather than silently running with defaults.
- Database credentials must not be printed in logs or error messages returned to the client.
- CORS should be explicitly configured (not wildcard `*`) even in a learning project, as a demonstrated good habit.

---

## 8. Coding Style Guidelines

- Simple, direct code — a junior developer should be able to read any file and explain it in an 
- No unnecessary helper classes, no generic "manager"/"factory" abstractions
- One responsibility per file/function
- Type hints everywhere (function signatures, Pydantic models)
- Meaningful variable and function names — no single-letter names outside of trivial loops
- Comments only where logic isn't self-evident (don't over-comment obvious code)

---

## 9. Deliverables Expected From This Build

1. Fully working FastAPI backend matching the structure and features above
2. Alembic migration setup with initial migration for all three tables
3. `.env.example` and a working `.env`-driven config
4. `requirements.txt`
5. `README.md` with: setup steps, how to run migrations, how to run the server, and a short description of each module
6. A Postman collection (or documented example requests) covering auth, tasks, and leave endpoints
