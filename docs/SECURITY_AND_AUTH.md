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
  - Non-existent user, wrong mode, unverified admin, pending or revoked invite status, deactivated user, locked account, and invalid password all execute `verify_password(password, DUMMY_HASH)` or `verify_password(password, user.hashed_password)` followed by `await db.commit()`.
  - Server response timing and database I/O profiles are indistinguishable.
  - Returns identical error: HTTP 401 `{"detail": "Incorrect credentials."}`.
- **Invitation Status Enforcement**:
  - Pending employees (`invitation_status == "PENDING"`) and revoked invitations (`invitation_status == "REVOKED"`) cannot log in under any circumstances.
  - Attempting to log in with an unaccepted employee code executes the `DUMMY_HASH` timing defense and returns 401 `"Incorrect credentials."` without leaking invite state.
- **Account Lockout Rules**:
  - Failed password attempts increment `failed_login_attempts`.
  - Reaching **5 failed attempts** sets `locked_until = now() + timedelta(minutes=15)`.
  - Successful authentication resets `failed_login_attempts = 0` and `locked_until = None`.

### 2.3 Employee Onboarding & Single-Use Invite Flow (Slice 4e)
- **New Hire Onboarding**: When an admin provisions an employee (`POST /users/employees`), the backend creates the user record in `invitation_status = 'PENDING'` with a bcrypt hash of a random discarded secret (never a plaintext or sentinel string).
- **Cryptographic Invite Tokens**: Generates a 48-hour single-use token via `secrets.token_urlsafe(32)`. The token's SHA-256 hex digest is stored in `user_tokens` (`token_type='INVITE'`). The raw token is only sent in the invitation email via `BackgroundTasks` (or printed to dev console).
- **Account Activation**: The new employee calls `POST /auth/accept-invite` with `{token, password}`. The endpoint atomically consumes the token via a single-statement `UPDATE ... WHERE used_at IS NULL AND expires_at > now() RETURNING`, validates password strength, updates `hashed_password`, sets `invitation_status = 'ACTIVE'`, `invitation_accepted_at = now()`, and `is_email_verified = True`.
- **Legacy Password Reset Backward Compatibility**: Existing legacy accounts with `must_change_password = True` retain their first-login change flow: protected routes return HTTP 403 `{"detail": "password_change_required"}` until `POST /auth/change-password` is executed.

### 2.4 Self-Serve Password Reset & Universal Session Invalidation
- **Self-Serve Forgot Password**: `POST /auth/forgot-password` accepts `{email}`. Implements strict anti-enumeration: executes dummy bcrypt timing for unknown or unverified/revoked accounts, returning identical HTTP 200 `{"message": "If an account exists with that email, a password reset link has been sent."}`. For active users, generates a 1-hour single-use `PASSWORD_RESET` token in `user_tokens`.
- **Reset Password**: `POST /auth/reset-password` accepts `{token, new_password}`. Atomically consumes the token, validates password complexity, updates password hash, and triggers immediate session invalidation.
- **Immediate Session Invalidation (`tokens_valid_after`)**:
  - `users.tokens_valid_after` (`TIMESTAMP WITH TIME ZONE`) stores the cutoff timestamp for valid tokens.
  - Set to `now()` on password reset (`/auth/reset-password`), invite acceptance (`/auth/accept-invite`), and password change (`/auth/change-password`).
  - Both `get_current_user` in `app/core/security.py` (access tokens) and `refresh_access_token` in `app/services/auth_service.py` (refresh tokens) check the token's issued-at claim: if `token.iat < user.tokens_valid_after`, the token is rejected immediately with HTTP 401 Unauthorized (`"Token has been revoked by a security event."`), terminating all concurrent sessions across devices without waiting for JWT expiration.

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

### 4.4 Rate Limiting & Brute-Force Defense (Level 1)
- **Architecture (`app/core/rate_limit.py`)**:
  - Implements an abstract `RateLimiter` interface (`check_and_increment`, `check_auth_rate_limit`, `cleanup`, `reset`) with `InMemoryRateLimiter` as the active implementation.
  - Endpoints depend strictly on the `RateLimiter` abstraction via FastAPI dependency injection (`get_rate_limiter`), allowing the implementation to be replaced (e.g. with `RedisRateLimiter`) without touching routes.
  - **Sliding-Window Algorithm**: Tracks exact millisecond timestamps per key, purges entries older than the window, and calculates precise integer `Retry-After` seconds using `math.ceil(oldest_ts + window - now)`.
  - **Memory Safety & Stale-Key Cleanup**: `InMemoryRateLimiter` includes automatic periodic eviction (triggered every 100 calls) and manual `cleanup()` to prune keys whose timestamps have completely expired, preventing unbounded memory growth.
- **Dual-Key Auth Rate Limiting**:
  All protected authentication endpoints (`POST /auth/login`, `POST /auth/swagger-login`, `POST /auth/signup`, `POST /auth/resend-verification`) must pass two independent sliding-window checks:
  1. **Compound Key `{client IP, normalized identifier}`** (Default: 10 attempts / 15 minutes, configurable via `RATE_LIMIT_AUTH_ATTEMPTS` and `RATE_LIMIT_AUTH_WINDOW_SECONDS`):
     - Prevents office NAT IP lockout across different users sharing an egress gateway. Each normalized (trimmed and lowercased) email or employee code receives its own rate bucket.
  2. **Per-IP Ceiling across all identifiers** (Default: 100 attempts / 15 minutes, configurable via `RATE_LIMIT_IP_CEILING_ATTEMPTS` and `RATE_LIMIT_IP_CEILING_WINDOW_SECONDS`):
     - Protects against distributed password spraying attacks where an attacker rotates through many user accounts from a single IP.
- **Anti-Enumeration Guard & Timing Defense**:
  - On rate limit exhaustion, the endpoint immediately returns HTTP 429 Too Many Requests with a `Retry-After` header.
  - The HTTP 429 response body and status code are completely identical regardless of whether the identifier corresponds to an existing user or non-existent account.
  - Dummy bcrypt comparison (`DUMMY_HASH`) remains active during authentication so timing analysis cannot distinguish valid from invalid users.
- **Client IP Resolution & Trusted Proxy Defense**:
  - `extract_client_ip(request)` safely resolves the client IP.
  - `X-Forwarded-For` is strictly ignored by default, binding to the direct socket connection host (`request.client.host`).
  - Only when the direct connection host is registered in `settings.TRUSTED_PROXY_IPS` is `X-Forwarded-For` parsed (traversing right-to-left to extract the rightmost untrusted client IP), preventing header spoofing bypasses.
- **Deployment Notice (Single-Worker vs Multi-Worker)**:
  - In single-worker / development environments, `InMemoryRateLimiter` operates safely with zero external dependencies.
  - In horizontally scaled multi-worker or multi-container production environments, in-memory state is isolated per process. The abstract `RateLimiter` interface is designed to support a Redis-backed sliding window (`RedisRateLimiter`) when distributed scaling is provisioned.

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
1. **By-ID Access & Anti-Enumeration**: Target resource IDs belonging to Org B across all single-resource endpoints (`GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `PATCH /leaves/{id}`, `GET /users/{id}/direct-reports`, `POST /users/{id}/resend-invite`, `POST /users/{id}/revoke-invite`, `POST /users/{id}/send-password-reset`, `PATCH /users/{id}/reports-to`, `PATCH /users/{id}/deactivate`, `PATCH /users/{id}/reactivate`). Every request returns HTTP 404 with identical error messages to non-existent IDs, preventing cross-tenant existence enumeration.
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

### 5.3 Role Matrix & Cross-Org Attack Parametrization
Every cross-tenant attack (by-id access, collection listing, foreign-key injection, and write attacks) is systematically parametrized across all three caller roles:
- **Org A Admin (Tier 1)**
- **Org A Supervisor (Tier 2)**
- **Org A Employee (Tier 3)**

For endpoints requiring elevated privileges (such as employee creation, user deactivation/reactivation, manager reassignment, leave reviews, and task deletion), roles lacking authority return their standard HTTP 403 Forbidden response identically for both cross-tenant resource IDs and non-existent IDs (`NONEXISTENT_ID = 9999999`). Where roles have permission (e.g., GET/PATCH tasks), cross-tenant IDs and non-existent IDs return HTTP 404 Not Found identically. This guarantees **zero existence leakage** across all roles and resources.

### 5.4 Password Reset & Account Recovery Anti-Enumeration (Slice 4e)
The application enforces strict anti-enumeration across authentication recovery channels:
1. **Public Verification Resend (`POST /auth/resend-verification`)**: Responds with HTTP 200 and an identical generic message (`"If an unverified account exists for this email, a verification link has been sent."`) regardless of whether the email belongs to Org A, Org B, or does not exist at all.
2. **Public Self-Serve Forgot Password (`POST /auth/forgot-password`)**: Responds with HTTP 200 and an identical generic message (`"If an account exists with that email, a password reset link has been sent."`) with constant dummy-hash timing regardless of whether the email exists, belongs to another organization, is deactivated, revoked, or pending.
3. **Public Reset Password (`POST /auth/reset-password`) and Accept Invite (`POST /auth/accept-invite`)**: Any invalid, expired, already-consumed, or revoked token returns an identical generic error (`"Invalid or expired token."`), preventing token-state probing.
4. **Tenant Isolation of Admin Endpoints**: `POST /users/{id}/resend-invite`, `POST /users/{id}/revoke-invite`, and `POST /users/{id}/send-password-reset` return HTTP 404 for cross-tenant IDs, identically to non-existent IDs.
5. **Password Change (`POST /auth/change-password`)**: Authenticated endpoint bound strictly to `current_user.id`; changing an Org A user's password leaves Org B user hashes completely intact.

### 5.5 How to Extend the Isolation Suite
When new endpoints are added (e.g., Slice 4e Employee Invites or Slice 6 Billing):
1. **Import the fixture**: Import `isolation_setup` and `TenantIsolationSetup` from `tests.fixtures_tenant_isolation`.
2. **Add cross-org tests**:
   - By-ID attack: Call the new endpoint targeting Org B resource ID from Org A caller -> assert HTTP 404.
   - Write/FK attack: Pass Org B ID inside request body or query parameter -> assert HTTP 404 or override.
   - Verification: Query `db_session` to verify Org B records are unmodified.

