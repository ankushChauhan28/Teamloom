# Teamloom — AI & Developer Onboarding Context (`AI_CONTEXT.md`)

> **Entry-Point Guide**: Read this file first. It summarizes current system state, locked decisions, workflow rules, and points to authoritative tracked documentation for deep dives.

---

## 1. Project Overview
**Teamloom** is an enterprise workforce task management, managerial hierarchy, and operations platform transitioning from an internal tool into a multi-tenant, subscription-gated B2B SaaS.
* **Backend**: FastAPI (Python 3.11+), PostgreSQL 16 via Async SQLAlchemy 2.0 & `asyncpg`, Alembic migrations, PyJWT dual-token auth (in-memory access + httpOnly refresh), and bcrypt hashing.
* **Frontend**: React 19 SPA bootstrapped with Vite 8.2, Tailwind CSS v4, Lucide React icons, and Zustand for auth session state.

---

## 2. Source-of-Truth Documentation Map
*Always refer to these git-tracked documents for specific implementation details. Do not guess.*

| Domain / Topic | Authoritative Tracked Document | Key Contents |
| :--- | :--- | :--- |
| **SaaS Roadmap & Slices** | [TEAMLOOM_SAAS_REQUIREMENTS.md](TEAMLOOM_SAAS_REQUIREMENTS.md) | Locked decisions (A1-X8), Slices 1–11, pricing packs, acceptance criteria |
| **Database & Migrations** | [database.md](database.md) | PostgreSQL schema, ER diagram, indexes, migration drift notes, RLS plan |
| **Backend Architecture** | [BACKEND.md](BACKEND.md) | FastAPI app factory, services, dependency injection, async patterns |
| **Frontend Architecture** | [FRONTEND.md](FRONTEND.md) | Component tree, Zustand authStore, Axios interceptors, route guards |
| **Auth, RBAC & Security** | [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) | Dual-mode login, 10-digit IDs, token blacklist, lockout, rate limiting |
| **System Overview & Routes** | [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Full route inventory, file directory structure, environment variables |
| **Tech Debt & SaaS Gaps** | [SAAS_GAP_AND_ROADMAP.md](SAAS_GAP_AND_ROADMAP.md) | Quality review, known bugs, technical debt, and prioritized action plan |
| **Setup & Local Execution** | [README.md](../README.md) | Docker Compose setup, local virtualenv run commands, test suite invocation |

---

## 3. Current Implementation Status
* **Completed Delivery Slices**:
  * **Slice 1**: Docker PostgreSQL 16 test harness and GitHub Actions CI.
  * **Slice 2**: Multi-tenant `Organization` model and default org backfill.
  * **Slice 3**: Strict `organization_id` query scoping, `get_scoped_or_404`, and pagination.
  * **Slice 4a**: 10-digit random numeric User IDs and email verification database schema.
  * **Slice 4b**: Dual-mode login (`ADMIN` via email, `EMPLOYEE` via User ID) enforced on server.
  * **Slice 4c**: Self-serve signup (`pending_payment`) and background email verification.
  * **Slice 4d**: Frontend auth UI (mode toggle, signup form, verification page, unverified notice).
* **Pending Slices**: Slice 4e (employee invite flow), Slice 5 (isolation test suite), Slices 6–10 (Razorpay billing, lifecycle, invoices, operator CLI), and Slice 11 (go-live checklist).
* **Alembic Head Revision**: `n4o5p6q7r8s9` (`slice4c_backfill_email_verification`).
* **Test Suite Health**: **205 collected tests** via `pytest --collect-only -q` (100% passing in CI).

---

## 4. Locked Architectural Decisions & Stabilization Order
1. **Slice 4e Precedes Slice 6**: Employee invite flow (one-time set-password token, admin Resend/Revoke, no temp passwords) must ship before Slice 5 isolation tests and Slice 6 billing seat caps.
2. **Supervisor Deactivation Safety**: Deactivating a supervisor must **not** silently set direct reports' `reports_to_id = NULL`. The API must require the admin to reassign subordinates first, returning HTTP 409 Conflict with the subordinate list if reassignment is needed.
3. **Soft-Delete for Tasks & Leaves**: Tasks and leave requests will transition to soft-deletion (`is_deleted`, `deleted_at`, `deleted_by`). An independent `audit_logs` table is deferred to a later SaaS slice.
4. **Rate Limiting**: **Open decision / Under discussion** (evaluating Redis sliding-window vs distributed token bucket).
5. **Stabilization Branch Order**:
   1. `fix/db-indexes` (add missing foreign key and search indexes).
   2. `fix/supervisor-deactivation` (prevent silent subordinate orphan on supervisor deactivation).
   3. `feat/soft-delete-tasks-leaves` (implement soft delete columns and scoped filter).
   4. `test/tenant-isolation-suite` (Slice 5 multi-tenant leak tests).
   5. Rate limiting implementation once decided.

---

## 5. Engineering Workflow Rules
* **Branch Naming**: One branch per task using `type/short-name` (e.g., `feat/slice-4e-invites`, `fix/db-indexes`, `docs/cleanup-handover`, `test/tenant-isolation`).
* **Branch Base**: Always branch from an up-to-date `main`. Never commit directly to `main`.
* **Commit Style**: Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
* **PR Process**: Push the branch to `origin`, but **do not open the Pull Request** (the repository owner opens and reviews PRs on GitHub).
* **CI Quality Gate**: All GitHub Actions CI checks (Pytest, Ruff, ESLint, Vite build) must pass green before merge.
* **Migration Discipline**: **Never edit or rename existing Alembic migration files**. Always generate a new forward migration (`alembic revision --autogenerate -m "..."`).
* **Code Verification**: Always inspect actual code and configuration files before modifying them; do not assume or invent facts.
* **Context Maintenance**: Update Section 3 of this document (`docs/AI_CONTEXT.md`) at the conclusion of every PR.

---

## 6. Known Risks & Technical Debt Pointers
* **Known Bugs**: See [docs/SAAS_GAP_AND_ROADMAP.md Section 10.1](SAAS_GAP_AND_ROADMAP.md#101-known-bugs-and-risky-code-areas) (silent supervisor orphan unlinking, missing composite database indexes, misnamed migration file `104551d9fda5_*`).
* **Technical Debt**: See [docs/SAAS_GAP_AND_ROADMAP.md Section 10.2](SAAS_GAP_AND_ROADMAP.md#102-technical-debt-inventory) (stale `scripts/test_endpoints.py` calling removed `/auth/register`, in-memory rate limiter worker isolation, deprecated `role` column in `users`).

---

## 7. How to Start a New Session
1. Read this file ([docs/AI_CONTEXT.md](AI_CONTEXT.md)) to understand current project state, locked decisions, and workflow constraints.
2. Identify the active task's domain and read **only** the relevant tracked documents from the Source-of-Truth map in Section 2.
3. Check out a clean task branch from latest `main` following the branch naming convention before writing any code.
