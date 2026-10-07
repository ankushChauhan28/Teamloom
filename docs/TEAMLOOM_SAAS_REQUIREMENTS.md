# Teamloom SaaS Requirements: Multi-Tenancy + Billing

Status: requirements locked, Slices 1-3, 4a-4d done, Slice 4e next.
Scope: turn Teamloom into a multi-company SaaS with pay-first access, packs, subscriptions and invoices. AI features come after this is proven with real-scenario tests.

Items marked **(default)** were not explicitly chosen by the product owner. They are sensible assumptions; change them before implementation if wrong.

---

## Progress / Status

### Implementation Tracker

| Slice | Scope | Status | Completed on | Notes |
|:---:|---|:---:|:---:|---|
| 1 | Test infrastructure on PostgreSQL (Docker for dev, CI) | Done | 2026-10-01 | Merged to main (PR #1), PostgreSQL test suite on Docker & GitHub Actions CI, safety guard against prod DB, 151 tests passing |
| 2 | Organization model, migration, backfill into the default organization | Done | 2026-10-02 | merged to main, CI green (run #6), dev DB migrated to revision l2m3n4o5p6q7, 158 tests passing |
| 3 | Org scoping on all queries + pagination | Done | 2026-10-02 | Tenant-scoped all queries/aggregates/ID lookups (404 on cross-tenant), single-query window pagination with X-Total-Count header, CORS expose_headers, fetchAllEmployees helper, 175 tests passing, merged to main, CI green (run #10) |
| 4a | DB cleanup: 10-digit numeric User IDs (no `EMP-`), email verification fields, regenerate IDs of the 6 dummy users | Done | 2026-10-02 | PR #4 merged, hotfix PR #5 merged, CI green, 10-digit random IDs, email verification schema, 180 tests passing, 83% coverage |
| 4b | Login modes: Admin (email) and Employee (User ID), server-enforced (X3) | Done | 2026-10-03 | Merged to main (PR #6), dual login mode enforcement, 187 tests passing |
| 4c | Signup + email verification (backend) | Done | 2026-10-04 | Branch feat/slice-4c-signup-verification, POST /auth/signup, POST /auth/verify-email, POST /auth/resend-verification, NFR-3 EmailSender interface, unverified admin login enforcement, unverified signup 7d cleanup, backfill migration n4o5p6q7r8s9, 201 tests passing, 82% coverage |
| 4d | Frontend: login toggle, signup page, verify-email page, unverified login UX, auth UI polish | Done | 2026-10-07 | Branch feat/slice-4d-frontend-auth, AuthLayout, LoginPage dual-mode toggle with password clearing & Option 2 unverified admin resend helper on 401, SignupPage at /signup (201 check-email state + resend), VerifyEmailPage at /verify-email (single-use StrictMode guard + resend fallback), ChangePasswordPage flash fix, RegisterPage removed, oxlint (0 errors) & vite build green |
| 4e | Employee invite flow | Pending | | |
| 5 | Isolation test suite (section 5.A) fully green | Pending | | |
| 6 | Plans, subscription model, `pending_payment` gating, seat limits (race-safe) | Pending | | |
| 7 | Payment provider, checkout, webhooks (signature, idempotency) | Pending | | |
| 8 | Lifecycle: grace period, read-only mode, cancellation, retention and unpaid-signup cleanup jobs | Pending | | |
| 9 | Invoices and Billing UI | Pending | | |
| 10 | Operator CLI scripts | Pending | | |
| 11 | Go-live checklist (below) | Pending | | |

*Note on updating*: When completing a slice, change its status to `Done`, record the completion date (`YYYY-MM-DD`), and add verification notes (e.g. migration revision, test counts, CI status).

### Known Gaps / Deferred to Later Slices
- `AdminTasksPage` and `AdminLeavesPage` fetch at most 100 records (`limit=100`) and need server-side filtering / paging UI later.
- There is currently no UI to resend a temporary password or to see email delivery failures (the `POST /users/{user_id}/reset-temp-password` endpoint exists in the backend but has no UI button), to be solved by Slice 4e (Employee invite flow).
- Production needs a real transactional email provider with domain authentication (SPF/DKIM/DMARC) and `EMAIL_BACKEND` explicitly set to `smtp`.
- Until Slices 6 and 7 are done, a company created by signup is not payment-gated. Do not deploy Slice 4 publicly before then.
- Admin account recovery (admin loses access to the registered email) has no self-serve path. It will be handled by the operator CLI (Slice 10). A forgot-password flow is not specified yet and needs a decision.
- Email change is not supported, and additional Tier-1 admins (X8) are deferred.

### Items Needing Decision / Investigation
- **Login Rate Limit (Decision)**: The login rate limit (10 requests per 15 minutes per IP) may be too tight for organizations operating behind a single corporate / office NAT IP. Needs a decision on whether to relax the limit, key rate limiting by `{IP, identifier}`, or separate IP rate limiting from account lockout.
- **Production Email Logging (Decision)**: Production environments must never use the console email backend or log raw verification tokens/passwords to logs or monitoring systems.
- **Create Employee Request Latency (Resolved)**: Fixed in PR #10 (branch fix/create-employee-latency): bcrypt password hashing offloaded to threadpool via `asyncio.to_thread`, welcome/reset emails dispatched non-blocking in `BackgroundTasks`. `email_sent=True` means delivery was successfully queued (delivery failures logged to server logs). Request latency reduced from ~3-4s to ~150-200ms.

### Requirement Change Log
| Date | Change |
|---|---|
| 2026-10-02 | A4 changed: User IDs are 10-digit random numeric (was: sequential counter that keeps existing numbers). `EMP-` prefix dropped completely; the 6 existing users are dummy test accounts and get regenerated IDs. FR-5 and FR-11 updated to match. |
| 2026-10-02 | Added A11 (signup and login live in the app, website only links), A12 (admin credentials: normal email + password + verification link, no Google/Apple sign-in for now), B16 (plan selection and payment happen inside the app; plan activates only via verified webhook). |
| 2026-10-02 | X8 (additional Tier-1 admins) marked deferred. Out of Scope extended. Slice 4 split into 4a to 4d. |
| 2026-10-03 | Slice 4b login modes: payload is {identifier, password, mode}; wrong-mode login is treated as user-not-found and does not count toward lockout; generic error "Incorrect credentials." |
| 2026-10-04 | Slice 4c self-serve signup & email verification (backend): POST /auth/signup (no auto-login/tokens), POST /auth/verify-email (POST-only to prevent prefetch consumption), POST /auth/resend-verification with anti-enumeration, NFR-3 EmailSender interface with SMTP/Console providers, background email delivery, unverified admin login block, 7-day unverified signup cleanup job, backfill migration n4o5p6q7r8s9. |
| 2026-10-04 | Slice 4c manual smoke test complete on running dev app: verified real SMTP email delivery, signup, verification link, resend verification, anti-enumeration on duplicate signup/resend, and admin-created employee immediate login. |
| 2026-10-04 | Slice 4d scope refined: verify-email page (email links to `/verify-email?token=...`), signup page, "check your email + resend" UX for unverified login, clear password field on login mode switch, fix brief change-password form flash before redirect. Added create-employee latency investigation (3-4s welcome email sync vs background). |
| 2026-10-07 | Slice 4d completed (frontend auth UI: shared AuthLayout, LoginPage dual-mode toggle + password clearing + Option 2 unverified admin resend helper on 401, SignupPage with anti-enumeration check-email view, VerifyEmailPage with single-use StrictMode guard & fallback resend form, ChangePasswordPage mount flow capture preventing layout flash, RegisterPage removed). Latency fix resolved in PR #10 (BackgroundTasks + threadpool bcrypt). Added Slice 4e (Employee invite flow) to delivery plan. |

---

## 1. Locked Decisions

### Multi-tenancy and identity
| ID | Decision |
|----|----------|
| A1 | One database, shared tables, every row carries `organization_id`. |
| A2 | **One login page with two modes: "Login as Admin" and "Login as Employee".** Admin mode: official email + password. Employee mode: User ID + password (same as today). |
| A3 | An email address belongs to exactly one company across the whole system. |
| A4 | User IDs are **numeric only, 10 digits, random** (not sequential, so they cannot be guessed in order), unique across all companies and never reused. Stored as a string in the existing `employee_code` column (so leading zeros are never lost) and shown as "User ID" in the UI. Uniqueness is guaranteed by a database unique constraint, with a retry on collision. Employee login needs no company code and accepts the plain number only: the `EMP-` prefix is dropped completely and the old format is not accepted. The 6 existing users are dummy test accounts, so their IDs are regenerated in the new format. If the 10-digit space is ever exhausted, new IDs move to 15 digits (not built now). |
| A5 | One user belongs to one company. |
| A6 | A company is created by self-serve signup (company name, admin name, official email, password). The signup email becomes the first admin's login. |
| A9 | No platform-admin UI for now; operator tasks are CLI scripts. |
| A10 | Company data isolation is mandatory and proven by tests on every endpoint. |
| A11 | Signup, login, email verification and billing live in the app. The future marketing website only shows product info and pricing and links to the app's signup/login pages; it holds no accounts or customer data. |
| A12 | Admin mode uses a normal email (any provider) + password, verified by a link sent to that email. The person with access to that inbox is the admin. No "Sign in with Google/Apple" for now. |

### Billing
| ID | Decision |
|----|----------|
| B1 | Payment gateway: Razorpay, India focus, INR. |
| B2 | Billing is managed by the company's Tier-1 Admin (there is no separate Owner role). |
| B3 | A seat is one **active** user. Deactivated users do not count. |
| B4 | Three size packs plus a Custom option, with a duration toggle (see section 4). |
| B6 | **No free trial. Pay first, then use.** |
| B7 | When seats are full, adding a user or reactivating a user is blocked with an "upgrade" prompt. |
| B8 | Downgrade is allowed only when current active users fit inside the new pack. |
| B9 | Payment failure: 3-day grace period, then read-only. Users who paid but got no access send proof; operator activates manually within 24 hours. |
| B10 | Cancellation: access continues until the paid period ends, then read-only, then data is deleted after 30 days. No refund. |
| B12 | Invoices: each successful payment produces a downloadable invoice. Optional GST number stored on the company. Legal/tax correctness must be confirmed with a CA before going live. |
| B14 | Test mode only during development. Live payments only after the go-live checklist. |
| B15 | The existing (current) data becomes a default company marked "Internal / free forever". It also serves as the demo company. |
| B16 | Plan selection and payment happen inside the app (never on the marketing website). The website may link to signup with a plan pre-selected (e.g. `?plan=growth`), but that value is only a UI hint and is never trusted: a plan becomes active only after a verified payment webhook. The Billing page shows the plan name, expiry and a renew/pay option. |

### Environment
| ID | Decision |
|----|----------|
| E1 | Development runs on PostgreSQL in Docker. Production moves to a managed Postgres host with only credentials and small environment config changing (see NFR-8). |

### Defaults assumed (change if wrong)
| ID | Default |
|----|---------|
| X1 | A company that signed up but never paid stays in `pending_payment`; the admin can log in but sees only the pack selection / billing page. Unpaid signups are deleted after 7 days. |
| X2 | Admin email must be verified via a link before checkout. Any email domain is accepted (no Gmail block). |

---

## 2. Functional Requirements (delta from today)

### 2.1 Multi-tenancy
- FR-1: Every existing and new table has `organization_id` (except `revoked_tokens` and system tables).
- FR-2: `POST /auth/signup` creates a new organization (status: `pending_payment`) and its first Tier-1 Admin user (`is_email_verified: False`), and sends a verification email.
- FR-3: Every query and mutation is filtered by the authenticated user's `organization_id` (enforced at the service/ORM layer, proven by isolation tests).
- FR-4: Email addresses are unique system-wide.
- FR-5: User IDs are 10-digit random numbers, unique system-wide, generated on employee creation.
- FR-6: Direct-report hierarchy (`reports_to_id`) and task assignment cannot cross company boundaries.
- FR-7: Cross-company lookups return 404 (not 403) so existence of records in other companies is never revealed.
- FR-8: The default company ("Internal / free forever") is seeded on first migration and holds the existing data.

### 2.2 Dual login modes
- FR-9: The login page has two modes: "Login as Admin" (official email + password) and "Login as Employee" (User ID + password).
- FR-10: Admin mode accepts only users with `access_level == 1` and authenticates by email.
- FR-11: Employee mode accepts only users with `access_level > 1` and authenticates by 10-digit User ID.
- FR-12: An employee trying to log in with an admin's email or an admin trying to log in with an employee's User ID receives the generic error "Incorrect credentials." with no hint that the account exists.

### 2.3 Email verification
- FR-13: Signup sends a verification email with a single-use, expiring token link (`/verify-email?token=...`).
- FR-14: Unverified admins cannot log in; attempt returns generic error with an option to resend the verification email.
- FR-15: Token expires after 24 hours (default). Resend invalidates earlier tokens.
- FR-16: Once verified, `is_email_verified` is set to `True` and `email_verified_at` is stamped.

### 2.4 Plans and seat limits
- FR-17: Packs: Starter (up to 20), Growth (up to 50), Business (up to 100), Custom (1 to 500).
- FR-18: Durations: Monthly, Quarterly (10% off), Yearly (20% off).
- FR-19: A seat is one user where `is_active = True`. Deactivated users do not count against the limit.
- FR-20: Creating a user or reactivating a deactivated user when `active_count >= seat_limit` is rejected with an upgrade prompt.
- FR-21: The default "Internal" company has `status = 'active'`, no seat limit and no expiry.

### 2.5 Lifecycle and access states
- FR-22: `pending_payment`: admin can only view/complete checkout; all other app endpoints return 402/403.
- FR-23: `active`: full access within the paid seat limit.
- FR-24: `past_due` (payment failed): 3-day grace period with warning banner, full access remains.
- FR-25: `read_only` (grace period ended or cancelled period ended): login works, all mutations blocked, billing page accessible.
- FR-26: `cancelled`: access continues until the end of the paid duration, then transitions to `read_only`.
- FR-27: Data deletion: organizations in `read_only` for 30+ days have their data deleted by a scheduled job.
- FR-28: Status changes come from payment-provider webhooks and scheduled checks, never from the frontend.

### 2.6 Payments and webhooks
- FR-29: Payment code sits behind a `PaymentProvider` interface; Razorpay is the first implementation, chosen by config.
- FR-30: Checkout is created server-side for the admin's own organization only.
- FR-31: Webhooks verify the provider signature; invalid signatures are rejected and nothing changes.
- FR-32: Webhooks are idempotent: the same event delivered twice is applied once (event IDs stored).
- FR-33: Out-of-order or unknown events never corrupt state (ignored or logged safely).
- FR-34: All amounts stored in paise (X7).

### 2.7 Invoices
- FR-35: Each successful payment creates an invoice: invoice number, organization name, GST number if provided, pack, duration, seats, amount, date.
- FR-36: Admin can view and download invoices from the Billing page.
- FR-37: Invoice numbers are unique and sequential per system.

### 2.8 Billing UI (Admin only)
- FR-38: Billing page shows status, seats used / limit, next renewal, invoices.
- FR-39: Pack view: three cards (Starter up to 20, Growth up to 50, Business up to 100), a Monthly / Quarterly / Yearly toggle, and a small "Custom" link for seat-based customization.
- FR-40: Non-admin users never see or reach billing endpoints.
- FR-41: Banners for: payment pending, grace period, read-only, seat limit reached.

### 2.9 Operator tools (CLI scripts, no UI)
- FR-42: List organizations with status and seat usage.
- FR-43: Manually activate a subscription (the "I paid but no access" case) with an audit log entry.
- FR-44: Suspend / unsuspend an organization.

---

## 3. Non-Functional Requirements

- NFR-1: Tests run on real PostgreSQL, same major version as production.
- NFR-2: No cross-organization access on any route (proven by section 5.A).
- NFR-3: Payment and email providers are swappable through config, not code changes.
- NFR-4: App instances are stateless; anything shared (rate limit, jobs) works across multiple workers.
- NFR-5: All list endpoints are paginated.
- NFR-6: Secrets (gateway keys, webhook secret) only from environment variables.
- NFR-7: Existing behavior (optimistic locking, lockout, token revocation, hierarchy rules) continues to pass its tests.
- NFR-8: **Production parity.** Moving from Docker Postgres to a managed host must only need: `DATABASE_URL` credentials, SSL/pooler-related settings from environment variables, and the same Postgres major version. To make that true: the schema is created only through Alembic migrations, no host-specific SQL, extensions are enabled through migrations, and the docker-compose Postgres version is pinned and checked against the chosen host before go-live.

---

## 4. Packs and Pricing (dummy test prices, per month, in INR)

| Pack | Active users | Monthly | Quarterly (10% off) | Yearly (20% off) |
|------|--------------|---------|---------------------|------------------|
| Starter | up to 20 | 1,500 | 1,350 / month | 1,200 / month |
| Growth | up to 50 | 3,500 | 3,150 / month | 2,800 / month |
| Business | up to 100 | 6,000 | 5,400 / month | 4,800 / month |
| Custom | 1 to 500 seats | 100 per seat | 90 per seat | 80 per seat |

Test-mode numbers. Prices live in configuration/data, not hardcoded, so changing them needs no code change.

---

## 5. Acceptance Scenarios (real-world tests)

Each scenario must become an automated test unless marked manual.

### A. Isolation (highest priority)
- A1: Company A and Company B each have an admin, a manager and an employee. Every list endpoint (users, tasks, leaves, analytics) returns only own-company records for each role.
- A2: Company A admin requests a Company B user, task and leave by ID: 404 on each, for read, update, delete, approve and reject.
- A3: Employees in both companies log in with their own User IDs; a code only ever authenticates its own user.
- A4: Creating a user in Company B with an email already used in Company A is rejected.
- A5: Company A admin cannot assign a task to, or set as supervisor, a Company B user.
- A6: Manager performance/team views never include users from another company.
- A7: Org-wide analytics for Company A ignores Company B's tasks completely.
- A8: Deactivating a user in A changes nothing in B, including seat counts.
- A9: A Company A token cannot read Company B data, even with guessed IDs.
- A10: A payment webhook for Company A changes only Company A's subscription.

### B. Signup and login
- B1: Signup creates the organization (`pending_payment`), the admin, and sends a verification email.
- B2: Checkout is refused until the email is verified.
- B3: Signup with an already-registered email is rejected.
- B4: Admin logs in with email + password in Admin mode; wrong password locks out after the existing threshold.
- B5: Employee mode with an admin's credentials fails; Admin mode with an employee's credentials fails (generic error).
- B6: Employee logs in with User ID + password in Employee mode and is forced to change a temporary password.
- B7: A `pending_payment` company's admin can reach only billing/pack selection; every other endpoint is blocked and no employees can be created.
- B8: A signup that never pays is deleted after 7 days and its email can be reused.
- B9: Two admins create employees at the same moment; codes are unique.

### C. Payment-first access and seats
- C1: Before the first payment, there is no access to the app features.
- C2: After the first payment, the chosen pack's seat limit applies.
- C3: At the seat limit, adding a user is blocked with an upgrade message.
- C4: Deactivating a user then adding another succeeds.
- C5: Reactivating a deactivated user at the seat limit is blocked.
- C6: Two simultaneous "add user" requests with one seat left: exactly one succeeds.

### D. Payments
- D1: Admin picks Growth + Monthly, completes test-mode checkout, webhook arrives: status `active`, seat limit 50, invoice created.
- D2: The same webhook delivered twice: one invoice, one state change.
- D3: Webhook with an invalid signature: rejected, nothing changes.
- D4: Webhook for an unknown organization or unknown event type: safely ignored and logged.
- D5: Renewal payment fails: `past_due`, full access for 3 days with a banner; after 3 days `read_only`.
- D6: Payment succeeds during `read_only`: status returns to `active`.
- D7: Custom pack for 35 seats + Quarterly: price equals seats x per-seat rate x 3 months minus discount; seat limit 35.
- D8: Non-admin (manager, employee) calling any billing endpoint: forbidden.
- D9: Upgrade from Starter to Business: takes effect immediately (X6), new limit applies at once.
- D10: Downgrade Business to Starter with 30 active users: rejected; with 18 active users: allowed.
- D11: Operator activates a subscription manually via script: company becomes `active`, an audit entry exists.

### E. Cancellation and retention
- E1: Admin cancels: `cancel_at_period_end`, full access until period end, no refund.
- E2: At period end: `read_only`.
- E3: 30 days after `read_only` starts: a scheduled job deletes only that company's data; other companies untouched.
- E4: The job is safe if run twice, or from two workers at once.

### F. Read-only behavior
- F1: In `read_only`, login works and pages load; creating/editing tasks, leaves and users is rejected with a clear message.
- F2: In `read_only`, the admin can still open Billing and pay.

### G. Invoices
- G1: Each successful payment creates exactly one invoice with a unique sequential number.
- G2: Admin sees and downloads only own-company invoices.
- G3: A GST number entered on the company appears on invoices; an empty GST number is fine.

### H. Migration of existing data
- H1: After migration, one default organization exists ("Internal / free forever"), and every existing user, task and leave belongs to it.
- H2: Existing admins log in via Admin mode with their email; other existing users via Employee mode with their (regenerated, 10-digit) User ID. The old `EMP-` format no longer works.
- H3: The default organization has no billing restrictions (no seat limit, no expiry, no payment needed).
- H4: The existing test suite passes (after fixtures are updated) with no lowered assertions.

### I. Regression
- I1: Hierarchy rules (direct reports, cycle protection, deactivation unlinking reports) work inside an organization exactly as before.
- I2: Optimistic locking (409), lockout, token revocation, rate limiting behave as before.

### J. Production parity
- J1: A fresh database built only from Alembic migrations passes the full test suite.
- J2: Pointing `DATABASE_URL` at a different Postgres instance (same major version) requires no code change.

---

## 6. Out of Scope (this stage)
- AI features (Team Insights, Smart Leave Review, Task Assist)
- Free trial
- Users belonging to multiple companies
- Platform-admin UI
- Proration on mid-period changes
- Legally compliant GST invoicing (needs CA input)
- Row-level security in the database
- Real-money payments (until the go-live checklist)
- SSO, SCIM, custom domains
- "Sign in with Google/Apple" (OAuth) login
- Changing a user's or admin's email address
- Additional Tier-1 admins (X8, deferred)
- The marketing website (separate future project)

---

## 7. Suggested Delivery Slices

Each slice ships working and tested before the next starts.

1. Test infrastructure on PostgreSQL (Docker for dev, CI)
2. Organization model, migration, backfill into the default organization
3. Org scoping on all queries + pagination
4. Dual login (Admin email / User ID), signup, email verification. Delivered in four parts, each with its own branch and CI run:
   - 4a. DB cleanup: 10-digit numeric User IDs, email verification fields, regenerate IDs of the dummy users (Done)
   - 4b. Login modes (Admin email / Employee User ID), server-enforced (Done)
   - 4c. Signup and email verification backend (Done)
   - 4d. Frontend: login mode toggle, signup page, verify-email page, unverified login UX, auth UI polish (Done)
   - 4e. Employee invite flow: replace the "temporary password by email" onboarding with a one-time set-password invite link (hashed, single-use, expiring token, reusing the verification-token pattern); the admin sees invite status (Pending / Accepted / Expired) in the employee list with Resend and Revoke actions; a wrongly typed email is fixed by revoking and re-inviting; the admin never sees or handles a password; needs a migration; it must ship before Slice 5 so isolation tests cover the invite endpoints and before Slice 6 so seat checks apply once. (Pending)
5. Isolation test suite (section 5.A) fully green
6. Plans, subscription model, `pending_payment` gating, seat limits (race-safe)
7. Payment provider, checkout, webhooks (signature, idempotency)
8. Lifecycle: grace period, read-only mode, cancellation, retention and unpaid-signup cleanup jobs
9. Invoices and Billing UI
10. Operator CLI scripts
11. Go-live checklist (below)

## 8. Go-Live Checklist (before any real payment)
- [ ] Razorpay business verification (KYC) completed
- [ ] Live keys and live webhook secret set in the production environment only
- [ ] Production Postgres host uses the same major version as development
- [ ] One small real payment made and refunded end to end
- [ ] Invoice format and GST handling reviewed by a CA
- [ ] Backups and restore tested
- [ ] Terms of Service, Privacy Policy and refund/cancellation policy published
