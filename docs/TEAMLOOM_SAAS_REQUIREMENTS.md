# Teamloom SaaS Requirements: Multi-Tenancy + Billing

Status: requirements locked, implementation not started.
Scope: turn Teamloom into a multi-company SaaS with pay-first access, packs, subscriptions and invoices. AI features come after this is proven with real-scenario tests.

Items marked **(default)** were not explicitly chosen by the product owner. They are sensible assumptions; change them before implementation if wrong.

---

## Progress / Status

### Implementation Tracker

| Slice | Scope | Status | Completed on | Notes |
|:---:|---|:---:|:---:|---|
| 1 | Test infrastructure on PostgreSQL (Docker for dev, CI) | Done | 2026-10-01 | Merged to main (PR #1), PostgreSQL test suite on Docker & GitHub Actions CI, safety guard against prod DB, 151 tests passing |
| 2 | Organization model, migration, backfill into the default organization | Done | 2026-10-02 | merged to main, CI green (run #6), dev DB migrated to revision l2m3n4o5p6q7, 158 tests passing |
| 3 | Org scoping on all queries + pagination | Done | 2026-10-02 | Tenant-scoped all queries/aggregates/ID lookups (404 on cross-tenant), single-query window pagination with X-Total-Count header, CORS expose_headers, fetchAllEmployees helper, 175 tests passing |
| 4 | Dual login (Admin email / User ID), signup, email verification | Pending | | |
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
- Dual login (Admin email / User ID), self-serve signup and email verification are deferred to Slice 4.

---

## 1. Locked Decisions

### Multi-tenancy and identity
| ID | Decision |
|----|----------|
| A1 | One database, shared tables, every row carries `organization_id`. |
| A2 | **One login page with two modes: "Login as Admin" and "Login as Employee".** Admin mode: official email + password. Employee mode: User ID + password (same as today). |
| A3 | An email address belongs to exactly one company across the whole system. |
| A4 | **(default)** User IDs are **numeric only** (1, 2, ... 1220): one global counter across all companies, never reused, always unique. Shown as "User ID" in the UI; the existing `employee_code` column can keep its name. Employee login therefore needs no company code. Existing users keep their current number (the `EMP-` prefix is dropped), so nobody's ID changes. |
| A5 | One user belongs to one company. |
| A6 | A company is created by self-serve signup (company name, admin name, official email, password). The signup email becomes the first admin's login. |
| A9 | No platform-admin UI for now; operator tasks are CLI scripts. |
| A10 | Company data isolation is mandatory and proven by tests on every endpoint. |

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

### Environment
| ID | Decision |
|----|----------|
| E1 | Development runs on PostgreSQL in Docker. Production moves to a managed Postgres host with only credentials and small environment config changing (see NFR-8). |

### Defaults assumed (change if wrong)
| ID | Default |
|----|---------|
| X1 | A company that signed up but never paid stays in `pending_payment`; the admin can log in but sees only the pack selection / billing page. Unpaid signups are deleted after 7 days. |
| X2 | Admin email must be verified via a link before checkout. Any email domain is accepted (no Gmail block). |
| X3 | Admin mode accepts only Tier-1 admin accounts; Employee mode accepts only non-Tier-1 accounts (manager, team lead, employee). A wrong-mode login fails with a generic error. The toggle is only UI; the server enforces it. |
| X4 | Requesting another company's record by ID returns 404 (not 403), so existence is not revealed. |
| X5 | Custom pack allows 1 to 500 seats; above that, the UI says "contact us". |
| X6 | Upgrading to a bigger pack takes effect immediately and starts a new billing period. No proration in v1. |
| X7 | Amounts are stored in paise (integers), never floats. |
| X8 | Additional Tier-1 admins (created later by the first admin) log in with their own email in Admin mode. |

---

## 2. Functional Requirements

### 2.1 Organizations and signup
- FR-1: `Organization` has a name, id, status, created date, optional GST number.
- FR-2: Signup creates the organization (status `pending_payment`), its first Tier-1 Admin, and sends an email verification link.
- FR-3: Checkout is only possible after the admin email is verified (X2). The app is only usable after the first successful payment.
- FR-4: Email is unique system-wide (A3). Signup with an existing email is rejected.
- FR-5: User ID generation stays race-safe: two admins creating users at the same time never get the same code.
- FR-6: Unpaid signups are removed after 7 days by a scheduled job, freeing the email (X1).

### 2.2 Login and users
- FR-7: Login page has an "Admin" mode (email + password) and an "Employee" mode (User ID + password). The existing lockout, rate limiting, token revocation and forced-password-change behavior apply to both.
- FR-8: Mode rules per X3 are enforced by the backend.
- FR-9: Admins create employees inside their own organization only (existing flow, now org-scoped). Employee email must be unique system-wide.
- FR-10: Hierarchy (reports_to), direct-report rules and cycle protection work **inside** an organization; a user can never report to someone in another organization.
- FR-11: Existing users, tasks and leaves are migrated into one default organization. Existing admins log in via Admin mode with their email; everyone else via Employee mode with their User ID, as before.

### 2.3 Data isolation
- FR-12: Every query on users, tasks, leave requests and analytics is filtered by the requester's organization.
- FR-13: Admin "list all" endpoints and org-wide analytics return only the admin's own organization, with pagination.
- FR-14: Cross-organization access by ID returns 404 (X4).
- FR-15: Any table added later carries `organization_id`.

### 2.4 Packs, payment-first access and seats
- FR-16: Each organization has exactly one subscription with a status (see 2.5).
- FR-17: Seat count = number of active users in the organization.
- FR-18: Creating or reactivating a user is blocked when active users would exceed the seat limit. This check is race-safe (two simultaneous adds at the limit: only one succeeds).
- FR-19: Deactivating a user frees a seat immediately.
- FR-20: Downgrade is rejected if active users exceed the new pack's limit (B8).
- FR-21: Custom pack: admin chooses a seat count (X5); price = seats x custom per-seat rate x months in the chosen duration, minus the duration discount.

### 2.5 Subscription lifecycle
Statuses: `pending_payment`, `active`, `past_due`, `read_only`, `cancel_at_period_end`, `deleted`.

- FR-22: `pending_payment` -> (first successful payment) -> `active`.
- FR-23: `active` renewal fails -> `past_due` (3-day grace, full access, warning banner) -> `read_only`.
- FR-24: `cancel_at_period_end`: full access until period end, then `read_only`.
- FR-25: `read_only` for 30 days, then the organization's data is deleted by a scheduled job (`deleted`). Payment during `read_only` restores `active`.
- FR-26: **Read-only mode** allows login and viewing data and billing. It blocks creating or editing tasks, leaves, users, and every other write except billing actions.
- FR-27: `pending_payment` mode allows only the billing/pack-selection pages.
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
- H2: Existing admins log in via Admin mode with their email; other existing users via Employee mode with their User ID.
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

---

## 7. Suggested Delivery Slices

Each slice ships working and tested before the next starts.

1. Test infrastructure on PostgreSQL (Docker for dev, CI)
2. Organization model, migration, backfill into the default organization
3. Org scoping on all queries + pagination
4. Dual login (Admin email / User ID), signup, email verification
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
