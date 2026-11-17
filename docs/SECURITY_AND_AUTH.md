# Security, Authentication & Authorization Audit (`SECURITY_AND_AUTH.md`)

> **Auditor Notice**: This technical assessment covers the complete security posture of Teamloom. Every finding is backed by source code references in `app/core/`, `app/routes/`, `app/services/`, and `frontend/src/`. All secret values are masked in compliance with audit safety standards.

---

## 1. Authentication Architecture & Token Lifecycle

### 1.1 Authentication Mechanism
Teamloom utilizes a custom **Dual-Token JSON Web Token (JWT)** architecture signing tokens with HMAC-SHA256 (`HS256`) via `pyjwt[crypto]`.

```text
 ┌────────────────┐                                       ┌────────────────┐
 │ React 19 SPA   │                                       │ FastAPI Server │
 └───────┬────────┘                                       └───────┬────────┘
         │                                                        │
         │ 1. POST /auth/login {identifier, password, mode}       │
         ├───────────────────────────────────────────────────────►│
         │                                                        │ 2. Authenticate & issue tokens
         │ 3. HTTP 200: {access_token: "..."}                     │
         │    Set-Cookie: refresh_token="..."; HttpOnly; SameSite │
         │◄───────────────────────────────────────────────────────┤
         │                                                        │
         │ 4. Request with Bearer Access Token (in-memory)        │
         ├───────────────────────────────────────────────────────►│ 5. Validate & check revoked_tokens
         │                                                        │
         │ 6. Access Token Expires (15m) -> HTTP 401              │
         │◄───────────────────────────────────────────────────────┤
         │                                                        │
         │ 7. Axios Interceptor triggers POST /auth/refresh       │
         │    (Browser automatically sends HttpOnly cookie)       │
         ├───────────────────────────────────────────────────────►│ 8. Rotate tokens:
         │                                                        │    - Invalidate old refresh_token
         │ 9. HTTP 200: {access_token: "new..."}                  │    - Issue new refresh_token
         │    Set-Cookie: refresh_token="new..."; HttpOnly        │
         │◄───────────────────────────────────────────────────────┤
```

### 1.2 Token Storage, Expiry & Rotation
1. **Access Token**:
   - **Lifetime**: `15 minutes` (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
   - **Storage**: Stored **strictly in-memory** within the Zustand state store (`frontend/src/store/authStore.js`).
   - **Defense**: Never written to `localStorage` or `sessionStorage`, mitigating access token exfiltration via Cross-Site Scripting (XSS).
   - **Transmission**: Sent via HTTP header: `Authorization: Bearer <access_token>`.
2. **Refresh Token**:
   - **Lifetime**: `7 days` (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`).
   - **Storage**: Stored in a browser cookie:
     - `httpOnly = True`: Inaccessible to JavaScript `document.cookie`.
     - `sameSite = "lax"`: Protects against Cross-Site Request Forgery (CSRF).
     - `secure = settings.COOKIE_SECURE`: `False` in local development; must be `True` in production.
     - `path = "/auth"`: Scoped strictly to authentication routes, preventing transmission on standard API calls.
3. **Continuous Token Invalidation Blacklist (`revoked_tokens`)**:
   - Every JWT payload embeds a unique `jti` (UUIDv4) and expiration timestamp (`exp`).
   - On **every authenticated request**, `get_current_user` in `app/core/security.py` queries the `revoked_tokens` table for the token's `jti`.
   - If the `jti` exists in `revoked_tokens`, the request is immediately rejected with HTTP 401 `Token has been revoked.`
4. **Token Rotation with Immediate Revocation**:
   - `POST /auth/refresh` extracts the refresh token cookie, checks `revoked_tokens`, issues a fresh token pair, and immediately inserts the old refresh token's `jti` into `revoked_tokens`.
   - Prevents refresh token replay attacks.
5. **Dual-Token Logout**:
   - `POST /auth/logout` extracts the Bearer access token and the refresh token cookie, inserts both `jti` entries into `revoked_tokens`, and instructs the browser to delete the cookie via `response.delete_cookie(key="refresh_token", path="/auth")`.

---

## 2. Authentication Flows

### 2.1 Self-Serve Signup & Verification Flow
- **Endpoint**: `POST /auth/signup` (`SignupRequest`: `company_name`, `full_name`, `email`, `password`).
- **Organization State**: Creates new `Organization` with status `pending_payment` and `is_internal = false`.
- **Admin Setup**: Creates first Tier-1 Administrator (`access_level = 1`, `is_email_verified = false`).
- **Token Generation**: Generates 32-byte cryptographically secure URL-safe token via `secrets.token_urlsafe(32)`.
- **Token Storage**: Inserts SHA-256 hash (`token_hash`) with 24-hour expiry into `email_verification_tokens`. The plaintext token is never stored in the database.
- **Asynchronous Delivery**: Dispatches verification link (`{FRONTEND_URL}/verify-email?token={raw_token}`) via FastAPI `BackgroundTasks`.
- **Anti-Enumeration Guarantee**: If an email is already registered, the backend executes a dummy bcrypt hash computation (`DUMMY_HASH`) to match execution time and returns HTTP 201 with an identical generic message.
- **Verification Endpoint**: `POST /auth/verify-email` (`EmailVerificationRequest`: `token`). Marks `token_record.used_at = now()`, activates `user.is_email_verified = true`, and sets `email_verified_at = now()`.

### 2.2 Dual-Mode Login Flow
- **Endpoint**: `POST /auth/login` (`UserLogin`: `identifier`, `password`, `mode`).
- **Mode Enforcement (Backend Controlled)**:
  - `mode == "admin"`: Query matches `LOWER(email) == LOWER(identifier)` AND `access_level == 1`.
  - `mode == "employee"`: Query matches `employee_code == identifier` AND `access_level > 1`.
  - Logging in with an admin's email in employee mode, or an employee's code in admin mode, is treated as user-not-found.
- **Anti-Enumeration Timing Protection**:
  - Non-existent user, wrong mode, unverified admin, deactivated user, locked account, and invalid password all execute `verify_password(password, DUMMY_HASH)` or `verify_password(password, user.hashed_password)` followed by `await db.commit()`.
  - Server response timing and database I/O profiles are indistinguishable.
  - Returns identical error: HTTP 401 `{"detail": "Incorrect credentials."}`.
- **Account Lockout Rules**:
  - Failed password attempts increment `failed_login_attempts`.
  - Reaching **5 failed attempts** sets `locked_until = now() + timedelta(minutes=15)`.
  - Successful authentication resets `failed_login_attempts = 0` and `locked_until = None`.

### 2.3 Password Management & Forced First-Time Reset
- **New Hire Onboarding**: When an admin provisions an employee (`POST /users/employees`), the backend sets `must_change_password = true`.
- **Route Guarding**: All protected routes depend on `require_password_change_cleared` (`app/core/security.py`). If `must_change_password == True`, raises HTTP 403 `{"detail": "password_change_required"}`.
- **Frontend Interception**: `ProtectedRoute.jsx` intercepts this detail and redirects to `/change-password` without rendering application dashboards.
- **Password Update**: `POST /auth/change-password` validates `current_password`, hashes `new_password`, sets `must_change_password = false`, and restores full system access.

---

## 3. Authorization, Roles & Permissions

### 3.1 4-Tier Operational Access Model

Authority is governed by integer `access_level` on `users` (`app/core/permissions.py`), where lower numbers indicate higher organizational privilege:

| Tier | Role Title | Scope & Authority | Enforcement Mechanism |
|:---:|---|---|---|
| **Tier 1** | Executive / Administrator | Organization-wide administration: provisions staff, reassigns supervisors, deactivates users, deletes tasks, approves/rejects leaves, views all analytics. | `check_access_level_dependency(1)` |
| **Tier 2** | Department Manager | Manages direct reports: delegates tasks, edits direct report tasks, views team leaves (view-only), views team analytics. | Direct reporting pointer (`assignee.reports_to_id == actor.id`) |
| **Tier 3** | Team Lead | Senior technical/operational lead with direct reports: delegates tasks to direct reports, views team leaves (view-only), views personal and team analytics. | Direct reporting pointer (`assignee.reports_to_id == actor.id`) |
| **Tier 4** | Associate / Contributor | Individual contributor: views assigned tasks, updates task status, submits leaves, views personal analytics. | Ownership checks (`Task.assigned_to == actor.id`) |

### 3.2 Direct-Report Delegation Rule
- In v3.0, arbitrary tier gaps between non-admin staff were eliminated.
- Non-admin task assignment authority is governed **strictly by the reporting pointer**:
  ```python
  # app/services/permission_service.py: can_manage_specific_user
  if actor_user.access_level == 1:
      return True
  return target_user.reports_to_id == actor_user.id
  ```
- **Self-Assignment Blocked**: Non-admin supervisors cannot assign tasks to themselves via the direct-report path.
- **Leave Approvals Admin-Only**: Direct managers have **view-only** visibility into team leaves (`GET /leaves/team`). Approving or rejecting leave requests (`PATCH /leaves/{id}`) is restricted exclusively to Tier-1 Administrators. Self-approval is blocked for all users, including Administrators.

### 3.3 Full-Stack Enforcement Architecture
1. **Frontend Enforcement**:
   - `ProtectedRoute.jsx`: Verifies session authentication and checks `must_change_password`.
   - `AdminRoute.jsx`: Checks `user.role === 'ADMIN' || user.access_level === 1`.
   - `DirectReportsRoute.jsx`: Checks `directReports.length > 0 || user.access_level === 1`.
   - `Navbar.jsx`: Conditionally hides or mounts navigation links based on user tier and direct reports count.
2. **Backend Enforcement (True Security Boundary)**:
   - Route dependencies: `current_user: User = Depends(require_password_change_cleared)`.
   - Tier dependencies: `current_admin: User = Depends(check_access_level_dependency(1))`.
   - Service-level assertions: `can_manage_specific_user` raises `AuthorizationException` (HTTP 403).
   - Resource isolation: `get_scoped_or_404` ensures tenant boundary enforcement (HTTP 404).

---

## 4. Comprehensive Security Review

### 4.1 Secrets & Environment Exposure
- **Hardcoded Secrets**: None found in application code (`app/`).
- **`.env` File**: Present in root workspace directory. It is properly listed in `.gitignore` (line 15).
- **Git Tracking Check**: `git status` confirms `.env` is untracked and ignored.
- **Docker Compose**: References environment variables with fallback defaults (`${POSTGRES_USER:-postgres}`).
- **Key Generation Recommendation**: Production secrets should be generated via cryptographically secure randomness:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

### 4.2 Injection & Input Validation (SQLi, XSS)
- **SQL Injection (SQLi)**: **Zero SQL injection vulnerabilities identified**.
  - All database queries use SQLAlchemy 2.0 type-safe `select()`, `insert()`, `update()`, and `delete()` constructs.
  - Where raw SQL is used (e.g. Alembic migrations `m3n4o5p6q7r8`), queries utilize parameterized expressions (`:code`, `:user_id`).
- **Cross-Site Scripting (XSS)**:
  - React 19 JSX auto-escapes all rendered strings by default.
  - No occurrences of `dangerouslySetInnerHTML` exist in the frontend codebase.
  - Sensitive tokens are stored in-memory, avoiding `localStorage` exfiltration.
- **Cross-Site Request Forgery (CSRF)**:
  - Refresh token cookie is configured with `samesite="lax"`.
  - Access tokens are transmitted in `Authorization: Bearer` headers, which cannot be initiated automatically by cross-origin form submissions.

### 4.3 CORS Configuration
- Configured in `app/main.py:49` via FastAPI `CORSMiddleware`:
  - `allow_origins = settings.CORS_ORIGINS`: Loaded from `.env` (defaults to `["http://localhost:3000"]`).
  - `allow_credentials = True`: Required for transmitting refresh cookies.
  - `allow_methods = ["*"]`
  - `allow_headers = ["*"]`
  - `expose_headers = ["X-Total-Count"]`: Permits frontend Axios client to read pagination counts.
- **Production Vulnerability Note**: Ensure `CORS_ORIGINS` in production is set strictly to the production frontend domain (e.g., `https://app.teamloom.com`) and never set to wildcard `["*"]` when `allow_credentials = True`.

### 4.4 Rate Limiting & Brute-Force Defense
- **Architecture (`app/core/rate_limit.py`)**:
  - Implements sliding-window rate limiting.
  - Keyed by client IP (`extract_client_ip` in `app/routes/auth.py`).
  - Supports `X-Forwarded-For` extraction **only** if the immediate connection IP matches `settings.TRUSTED_PROXY_IPS`, preventing IP spoofing attacks.
- **Protected Endpoints**:
  - `POST /auth/login`: 10 requests per 15 minutes per IP (`login:{ip}`).
  - `POST /auth/signup`: 10 requests per 15 minutes per IP (`signup:{ip}`).
  - `POST /auth/resend-verification`: 10 requests per 15 minutes per IP (`resend_verification:{ip}`).
- **Horizontal Scaling Vulnerability**:
  - When `RATE_LIMITER_BACKEND=memory` (default), rate limit counters are stored in Python process memory.
  - If deployed across multiple Uvicorn workers or container replicas, an attacker can bypass rate limits by distributing requests across workers.
  - `RATE_LIMITER_BACKEND=redis` is fully implemented using Redis sorted sets (ZSET) and must be enabled in production.

### 4.5 Password Hashing & Cryptography
- **Algorithm**: **Bcrypt** (`bcrypt` package, version `5.0.0`).
- **Implementation**:
  - `hash_password(pwd)`: Generates individual salt via `bcrypt.gensalt()` and hashes password bytes.
  - `verify_password(pwd, hash)`: Validates via `bcrypt.checkpw()`.
  - Threadpool offloading: Password hashing for employee creation is executed via `asyncio.to_thread` (`app/services/user_service.py:171`), preventing CPU-intensive bcrypt calculations from blocking the async event loop.
- **Timing Attack Mitigation**:
  - `DUMMY_HASH` is precomputed on server startup.
  - Non-existent user lookups and unverified accounts still execute `verify_password(password, DUMMY_HASH)` to normalize response times against valid user lookups.

### 4.6 File Upload Safety
- The application currently has **no file upload endpoints**.
- Avatar icons are rendered as colored SVG initials; attachments are not supported.
- Consequently, there are currently no risks regarding malicious file uploads, unvalidated MIME types, or directory traversal via filenames.

---

## 5. Multi-Tenant Isolation & Attack Surface Verification Suite (Slice 5, Depth A)

### 5.1 Architecture & Objectives
Teamloom implements strict multi-tenancy at the application and database layers. To provide mathematical certainty that an authenticated user of Organization A cannot read, modify, delete, or discover data belonging to Organization B, an API-level tenant isolation test suite is implemented in `tests/test_tenant_isolation.py` backed by dedicated fixtures in `tests/fixtures_tenant_isolation.py`.

The suite executes **pure black-box HTTP tests** through FastAPI's `AsyncClient`, validating external security contracts without internal mocking:
1. **By-ID Access & Anti-Enumeration**: Target resource IDs belonging to Org B across all single-resource endpoints (`GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `PATCH /leaves/{id}`, `GET /users/{id}/direct-reports`, `POST /users/{id}/reset-temp-password`, `PATCH /users/{id}/reports-to`, `PATCH /users/{id}/deactivate`, `PATCH /users/{id}/reactivate`). Every request returns HTTP 404 with identical error messages to non-existent IDs, preventing cross-tenant existence enumeration.
2. **List Endpoints & Pagination Scoping**: Endpoints returning collections (`/tasks/`, `/tasks/team`, `/leaves/`, `/leaves/team`, `/users/`, `/users/me/reports`) and their `X-Total-Count` headers strictly count and return only Org A entities, completely excluding Org B rows even when Org B has a larger volume of records.
3. **Cross-Tenant Write & Foreign-Key Injection Attacks**:
   - Assigning a task to an Org B user returns HTTP 404 (`Assigned user with ID ... not found.`).
   - Provisioning an employee with `reports_to_id` set to an Org B supervisor returns HTTP 404 (`Reports-to supervisor user not found.`).
   - Reassigning an employee's supervisor to an Org B supervisor via `PATCH /users/{id}/reports-to` returns HTTP 404.
   - Deactivating a supervisor with `default_new_manager_id` or `reassignments` mapped to an Org B manager returns HTTP 404.
   - Reviewing or modifying an Org B leave request returns HTTP 404.
4. **Soft-Deleted Invisibility**: Soft-deleted tasks of Org B are completely inaccessible to Org A across fetch (404), list (omitted), update (404), and delete (404).
5. **Analytics & Aggregation Scoping**: `/analytics/performance` across `org`, `team`, and `self` scopes strictly aggregates Org A tasks. Cross-org lookups via `?employee_id={org_b_user_id}` return HTTP 404/403.
6. **Query Parameter & Request Body Spoofing**: Injecting `?organization_id={org_b.id}` or request body `{"organization_id": org_b.id}` is completely overridden by the authenticated user's session context (`current_user.organization_id`).
7. **Database State Verification**: After every attempted write attack, direct database queries confirm that Org B records remain unchanged.

### 5.2 Test Fixture Harness (`tests/fixtures_tenant_isolation.py`)
The isolation test suite utilizes `TenantIsolationSetup`, an isolated two-tenant harness provisioning:
- **Org Alpha (Org A)** & **Org Bravo (Org B)**.
- Each tenant contains a full 3-tier hierarchy:
  - Tier 1: Organization Admin (`access_level = 1`, `role = ADMIN`)
  - Tier 2: Supervisor (`access_level = 2`, `role = EMPLOYEE`, reporting to Admin)
  - Tier 3: Direct Report Employee (`access_level = 3`, `role = EMPLOYEE`, reporting to Supervisor)
- Each tenant contains active tasks, soft-deleted tasks (`is_deleted = True`), and pending leave requests.
- Precomputed JWT Bearer headers for all 6 users, with shared password hashing to ensure deterministic, fast test runs.

### 5.3 How to Extend the Isolation Suite
When new endpoints are added (e.g., Slice 4e Employee Invites or Slice 6 Billing):
1. **Import the fixture**: Import `isolation_setup` and `TenantIsolationSetup` from `tests.fixtures_tenant_isolation`.
2. **Add cross-org tests**:
   - By-ID attack: Call the new endpoint targeting Org B resource ID from Org A caller -> assert HTTP 404.
   - Write/FK attack: Pass Org B ID inside request body or query parameter -> assert HTTP 404 or override.
   - Verification: Query `db_session` to verify Org B records are unmodified.

