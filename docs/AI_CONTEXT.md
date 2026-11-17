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
  * **Slice 5 (Stabilization Batch Completed)**: Complete API-level tenant isolation test suite (`tests/test_tenant_isolation.py`, `tests/fixtures_tenant_isolation.py`), proving zero cross-tenant leakage across all routes.
  * **Rate Limiting (Level 1 Completed)**: Abstract `RateLimiter` interface, `InMemoryRateLimiter` sliding-window implementation, dual-key auth protection (compound `{client IP, normalized identifier}` 10/15m + per-IP ceiling 100/15m), stale-key cleanup, trusted proxy support, and anti-enumeration.
* **Pending Slices**: Frontend CI check integration, Slice 4e (employee invite flow), Slice 6 (plans & billing), Slices 7–10 (Razorpay billing, lifecycle, invoices, operator CLI), and Slice 11 (go-live checklist).
* **Alembic Head Revision**: `p6q7r8s9t0u1` (`add_soft_delete_to_tasks`).
* **Test Suite Health**: **316 collected tests** via `pytest --collect-only -q` (100% passing in CI).

---

## 4. Locked Architectural Decisions & Delivery Order
1. **Target Execution Order (Owner's Plan)**:
   * **Phase 1: Stabilization Batch (All 4 Items Completed)**:
     1. `fix/db-indexes` (add missing foreign key and search indexes — Completed).
     2. `fix/supervisor-deactivation` (require subordinate reassignment before deactivation; return HTTP 409 with affected list — Completed).
     3. `feat/soft-delete-tasks` (soft-delete columns and scoped filters for tasks — Completed; task restore and leave soft delete deferred as later items).
     4. `test/tenant-isolation-suite` (Slice 5 multi-tenant isolation tests for all existing routes — Completed).
   * **Phase 2: Rate Limiting & Next Planned Work**:
     * **Rate Limiting (Level 1 Completed on `fix/rate-limiting`)**: Dual-key sliding window (`{client IP, identifier}` 10/15m + IP ceiling 100/15m) behind swappable `RateLimiter` interface with stale-key cleanup and trusted-proxy defense.
     * **Next Planned Work**:
       1. Frontend CI check: Add `npm run lint` and `npm run build` to GitHub Actions workflow.
       2. Slice 4e (Employee Invite Flow): One-time set-password invite link (hashed, single-use, 24h expiring token), admin Resend/Revoke in roster, no temp passwords. Updates isolation suite to cover invite endpoints. Ships before Slice 6 so seat caps apply to invites cleanly.
       3. Slice 6 (Plans & Billing): Plan subscription model, `pending_payment` access gating, race-safe seat limit enforcement.
   *(Note: `docs/TEAMLOOM_SAAS_REQUIREMENTS.md` originally suggested Slice 4e -> Slice 5 -> Slice 6; the owner's plan prioritizes codebase stabilization and lands the Slice 5 isolation test suite first, followed by rate limiting stabilization, Slice 4e, and Slice 6).*
2. **Supervisor Deactivation Safety**: Deactivating a supervisor must **not** silently set direct reports' `reports_to_id = NULL`. The API must require the admin to reassign subordinates first, returning HTTP 409 Conflict with the subordinate list if reassignment is needed.
3. **Soft-Delete for Tasks & Leaves**: Soft-delete is implemented for tasks (`is_deleted`, `deleted_at`, `deleted_by`, version bump; stabilization item 3 done for tasks). Task restore and leave soft delete are deferred as later items (since no real leave delete flow exists today; approve, reject, and cancel are status changes). An independent `audit_logs` table is deferred to a later SaaS slice.
4. **Rate Limiting**: **Level 1 Implemented & Resolved (on `fix/rate-limiting`)**.
   * *Architecture*: Sliding window rate limiting behind abstract `RateLimiter` interface (`check_and_increment`, `check_auth_rate_limit`, `cleanup`, `reset`).
   * *Keying*: Dual-key check on auth endpoints (`/auth/login`, `/auth/swagger-login`, `/auth/signup`, `/auth/resend-verification`) requiring requests to pass compound `{client IP, normalized identifier}` (default 10 attempts / 15m) to prevent corporate NAT lockout, and a looser per-IP ceiling (default 100 attempts / 15m) to prevent password spraying.
   * *Anti-Enumeration*: Generic identical 429 response body and `Retry-After` header regardless of account existence; timing attack defense (dummy bcrypt comparison) intact.
   * *Proxy Handling*: Direct socket connection host used by default; `X-Forwarded-For` parsed only if direct client host is in `settings.TRUSTED_PROXY_IPS`.
   * *Persistence & Scalability*: `InMemoryRateLimiter` with automatic and manual stale-key cleanup; routes depend only on abstract interface via `get_rate_limiter()` so `RedisRateLimiter` can be swapped in without modifying endpoints.

---

## 5. Engineering Workflow Rules
* **Branch Naming**: One branch per task using `type/short-name` (e.g., `feat/slice-4e-invites`, `fix/db-indexes`, `docs/cleanup-handover`, `test/tenant-isolation`).
* **Branch Base**: Always branch from an up-to-date `main`. Never commit directly to `main`.
* **Commit Style**: Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
* **PR Process**: Push the branch to `origin`, but **do not open the Pull Request** (the repository owner opens and reviews PRs on GitHub).
* **CI Quality Gate**: GitHub Actions (`.github/workflows/ci.yml`) runs on push and PR, executing strictly:
  1. `alembic upgrade head` (database migration validation on PostgreSQL 16 service).
  2. `pytest --cov=app --cov-report=term-missing` (backend test suite on isolated test DB).
  *Note: Frontend linting (`npm run lint` using `oxlint`) and frontend build (`npm run build` using `vite build`) are **not** part of CI and must be validated locally before pushing. Python `ruff` is also not currently in CI.*
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
