# Frontend Architecture & Technical Reference

This document provides the authoritative technical reference for the Employee Task Management Single Page Application (SPA).

---

## 1. Tech Stack & Dependencies

The frontend is built on React 19 and Vite with Tailwind CSS v4, Zustand, and React Router v7.

| Package | Version Constraint | Purpose |
|---|---|---|
| **react** | `^19.2.8` | Core UI Component & Virtual DOM Library |
| **react-dom** | `^19.2.8` | React DOM rendering engine |
| **react-router-dom** | `^7.18.2` | Client-side routing, navigation, and URL matching |
| **zustand** | `^5.0.15` | Minimalist in-memory state management store |
| **axios** | `^1.19.0` | Promise-based HTTP client with request/response interceptors |
| **tailwindcss** | `^4.3.3` | Utility-first CSS styling framework |
| **@tailwindcss/vite** | `^4.3.3` | Native Vite integration plugin for Tailwind v4 |
| **lucide-react** | `^1.31.0` | Lightweight, consistent SVG icon set |
| **vite** | `^8.2.0` | Modern frontend build tool and development server |
| **oxlint** | `^1.75.0` | High-performance JavaScript/JSX linter |

---

## 2. Directory Structure & File Map

```text
frontend/
├── public/
│   ├── favicon.svg             # Application SVG browser tab icon
│   └── icons.svg               # Application SVG icons asset
├── src/
│   ├── assets/                 # Static vector assets (react.svg, vite.svg, hero.png)
│   ├── components/             # Reusable UI & Feature components
│   │   ├── employees/          # Employee administration components
│   │   │   └── EmployeeFormModal.jsx   # Modal for creating employees with code, designation, supervisor, & access level
│   │   ├── guards/
│   │   │   ├── AdminRoute.jsx          # Route guard restricting access to Tier 1 Admin users
│   │   │   ├── DirectReportsRoute.jsx  # Route guard restricting access to users with direct reports or Tier 1 Admin
│   │   │   ├── PasswordChangeRoute.jsx # Route guard permitting authenticated users for forced or voluntary password updates
│   │   │   └── ProtectedRoute.jsx      # Route guard redirecting unauthenticated users to /login and pending password users to /change-password
│   │   ├── layout/
│   │   │   ├── AuthLayout.jsx      # Shared centered full-screen layout with Deep Pine branding for auth pages
│   │   │   ├── Navbar.jsx          # Top application bar with navigation links (My Performance hidden for Admin)
│   │   │   └── UserMenu.jsx        # Avatar chip triggering dropdown with user info, designation, password change, and logout
│   │   ├── ui/                     # Deep Pine design primitives
│   │   │   ├── Alert.jsx           # Status alert box (info, success, warning, danger)
│   │   │   ├── Badge.jsx           # Status & priority badge (slate, amber, teal, emerald, coral, red, violet, blue)
│   │   │   ├── Button.jsx          # Styled button (primary, secondary, danger, ghost variants; sm, md, lg sizes)
│   │   │   ├── Card.jsx            # Surface card container (Card, CardHeader, CardTitle, CardDescription, CardContent)
│   │   │   ├── DueCountdown.jsx    # Relative deadline countdown indicator with live 1-minute ticker
│   │   │   ├── EmptyState.jsx      # Placeholder banner with icon, title, description, and action button
│   │   │   ├── Input.jsx           # Text/password input field with validation error state and password visibility toggle
│   │   │   ├── Modal.jsx           # Centered modal dialog wrapper with backdrop and escape/close triggers
│   │   │   ├── PasswordChecklist.jsx # Live password complexity checklist (length, upper, lower, digit, special)
│   │   │   ├── Select.jsx          # Styled native select dropdown component
│   │   │   ├── Spinner.jsx         # SVG loading spinner indicator (sm, md, lg sizes)
│   │   │   └── Textarea.jsx        # Multi-line text input field with error messaging
│   │   ├── LeaveForm.jsx           # Employee leave submission form card with date validation
│   │   ├── LeaveHistoryList.jsx    # Stacked timeline list of personal leave requests with filter/status badges
│   │   ├── LeaveRejectModal.jsx    # Admin modal dialog for capturing rejection rationale on leave review
│   │   ├── MilestoneTrail.jsx      # Chronological task state dots (on-time, late, pending, overdue) with tooltips
│   │   ├── PerformanceRing.jsx     # Static SVG circular on-time percentage ring with metric cards breakdown
│   │   ├── TaskCard.jsx            # Employee task card with priority badge, countdown, status stepper, and completed locking
│   │   ├── TaskDeleteModal.jsx     # Confirmation dialog for deleting a task
│   │   ├── TaskFormModal.jsx       # Task create/edit dialog with optimistic locking conflict resolution (HTTP 409 handling)
│   │   └── TaskList.jsx            # Responsive employee task grid with filter controls and conflict reload handling
│   ├── lib/
│   │   ├── api.js                  # Axios client configuration with JWT injection and silent 401 refresh handler
│   │   ├── dateUtils.js            # Date/datetime formatting helpers (ISO, local format, datetime-local input)
│   │   └── passwordUtils.js        # Password complexity validation and special character regex rules
│   ├── pages/                      # Page view containers
│   │   ├── AcceptInvitePage.jsx    # Public set-password & invite activation page (/accept-invite?token=...)
│   │   ├── AdminEmployeesPage.jsx  # System-wide employee management directory for administrators (/admin/employees)
│   │   ├── AdminLeavesPage.jsx     # System-wide leave approval hub for administrators (/admin/leaves)
│   │   ├── AdminPerformancePage.jsx# System-wide employee performance analytics and metric leaderboard (/admin/performance)
│   │   ├── AdminTasksPage.jsx      # System-wide task control panel with 10s auto-polling (/admin/tasks)
│   │   ├── ChangePasswordPage.jsx  # Forced or voluntary password update page (/change-password)
│   │   ├── DashboardPage.jsx       # Employee personal task management dashboard (/dashboard)
│   │   ├── ForgotPasswordPage.jsx  # Public self-serve password reset request page (/forgot-password)
│   │   ├── LeavesPage.jsx          # Employee personal leave request portal (/leaves)
│   │   ├── LoginPage.jsx           # Dual-mode login page (Admin email / Employee User ID) (/login)
│   │   ├── MyPerformancePage.jsx   # Employee personal performance analytics page (/my-performance)
│   │   ├── MyTeamPage.jsx          # Manager direct report roster, team tasks, team leaves view, and analytics (/my-team)
│   │   ├── ResetPasswordPage.jsx   # Public single-use password reset completion page (/reset-password?token=...)
│   │   ├── SignupPage.jsx          # Self-serve organization & admin registration page (/signup)
│   │   └── VerifyEmailPage.jsx     # Single-use email verification token confirmation page (/verify-email)
│   ├── store/
│   │   └── authStore.js            # Zustand store managing user session, in-memory JWT, reports, and auth workflows
│   ├── App.jsx                     # Top-level application routing, layout guards, and bootstrap session refresh
│   ├── index.css                   # Global CSS design tokens, color variables, and base typography
│   └── main.jsx                    # Application entrypoint rendering <App /> to DOM
├── index.html                      # HTML5 page skeleton
├── package.json                    # npm dependencies and script commands
└── vite.config.js                  # Vite configuration with Tailwind CSS plugin
```

---

## 3. "Deep Pine" Design System

The application implements a bespoke dark theme named **"Deep Pine"**, defined via CSS custom properties in `frontend/src/index.css`.

### 3.1 Color Palette & Token Variables

```css
:root {
  /* Backgrounds & Surfaces */
  --bg-page: #0E1614;        /* Dark forest canvas background */
  --surface-1: #131F1C;      /* Card backgrounds, tables, toolbars */
  --surface-2: #17251F;      /* Elevated surfaces: modals, dropdowns, headers */

  /* Hairline Borders */
  --border: #223330;         /* Default hairline boundary */
  --border-strong: #2C4038;  /* Emphasized borders, hover states */

  /* Typography Colors */
  --text-primary: #DCEAE5;    /* High-contrast body & heading text */
  --text-secondary: #8FA79E;  /* Subtitles, labels, metadata */
  --text-muted: #5E7168;      /* Placeholders, disabled text, icons */

  /* Brand Accent */
  --accent: #3FA88F;         /* Teal accent */
  --accent-hover: #4FBE9F;   /* Bright teal hover state */
  --accent-active: #359078;  /* Pressed teal state */
  --on-accent: #04231C;      /* Dark text on accent fill */

  /* Semantic Status Tints */
  --amber: #D9A441;          /* Pending state */
  --amber-bg: rgba(217, 164, 65, 0.12);
  --teal: #3FA88F;           /* In Progress state */
  --teal-bg: rgba(63, 168, 143, 0.12);
  --green: #6FBE7A;          /* Completed / Approved / Success */
  --green-bg: rgba(111, 190, 122, 0.12);
  --coral: #D98C6B;          /* High priority / Imminent due */
  --coral-bg: rgba(217, 140, 107, 0.12);
  --red: #D9695A;            /* Rejected / Overdue / Destructive */
  --red-bg: rgba(217, 105, 90, 0.12);
  --violet: #9C87C9;         /* Admin role badge */
  --violet-bg: rgba(156, 135, 201, 0.12);
  --blue: #5FA0D9;           /* Employee role badge */
  --blue-bg: rgba(95, 160, 217, 0.12);
  --slate: #8FA79E;          /* Low priority */
  --slate-bg: rgba(143, 167, 158, 0.10);
}
```

---

## 4. Page Routing & View Reference

| Route | Page Component | Guard / Access Level | Purpose & Rendered Content |
|---|---|---|---|
| `/login` | `LoginPage` | Public | Dual-mode login interface (Admin mode: email; Employee mode: 10-digit User ID) with password field clearing on mode switch, "Forgot password?" links, flash messages (`location.state.message`), unverified admin resend helper on 401, signup link, and automatic post-login redirection. |
| `/signup` | `SignupPage` | Public | Self-serve organization and admin registration (company name, full name, email, password, confirm password) with client/server validation, 201 "Check your email" confirmation view, resend verification trigger, and anti-enumeration protection. |
| `/verify-email` | `VerifyEmailPage` | Public | Single-use email verification landing page that executes `POST /auth/verify-email` with token query parameter, featuring React StrictMode double-effect protection, loading spinner, success state, and invalid/expired fallback with resend verification form. |
| `/accept-invite` | `AcceptInvitePage` | Public | Single-use employee invite activation landing page executing `POST /auth/accept-invite` with `token` parameter, password + confirm inputs with live strength checklist, success state linking to login, and generic invalid/expired error handling. |
| `/forgot-password` | `ForgotPasswordPage` | Public | Self-serve password reset request page executing `POST /auth/forgot-password` with email, always displaying anti-enumeration generic confirmation guidance and rate-limit handling. |
| `/reset-password` | `ResetPasswordPage` | Public | Single-use password reset landing page executing `POST /auth/reset-password` with `token` parameter, live strength checklist, success state linking to login, and generic invalid/expired error handling. |
| `/change-password` | `ChangePasswordPage` | `PasswordChangeRoute` | Password update screen for both newly provisioned employees (`must_change_password=True`) and voluntary updates via UserMenu; enforces live password strength checklist and redirects to `/login` upon session invalidation. |
| `/dashboard` | `DashboardPage` | `ProtectedRoute` | Main employee dashboard displaying session status banner, user profile hero card, and the `TaskList` task board. |
| `/leaves` | `LeavesPage` | `ProtectedRoute` | Employee self-service leave portal rendering `LeaveForm` submission card and `LeaveHistoryList` timeline. |
| `/my-performance` | `MyPerformancePage` | `ProtectedRoute` (Hidden for Admin) | Personal performance analytics dashboard rendering `PerformanceRing` on-time circular gauge, metric count cards, and `MilestoneTrail`. |
| `/my-team` | `MyTeamPage` | `DirectReportsRoute` (Direct Managers & Admin) | Team management workspace rendering direct reports roster chips, tabbed team tasks table, tabbed team leaves view (all statuses), and team/individual performance analytics. |
| `/admin/tasks` | `AdminTasksPage` | `AdminRoute` (Tier 1 Admin) | System-wide task table with 10-second background auto-polling, status/priority/assignee filters, and task management modals. |
| `/admin/leaves` | `AdminLeavesPage` | `AdminRoute` (Tier 1 Admin) | System-wide leave approval table with status filter, inline one-click approve, and `LeaveRejectModal` for rejection. (Leave approval is strictly Admin-only). |
| `/admin/employees` | `AdminEmployeesPage` | `AdminRoute` (Tier 1 Admin) | System-wide employee directory showing codes, designations, reporting relationships, invitation status badges (`Active`, `Invite pending`, `Revoked`), invite actions (Resend invite, Revoke invite), password reset trigger, and `EmployeeFormModal`. |
| `/admin/performance` | `AdminPerformancePage` | `AdminRoute` (Tier 1 Admin) | System-wide performance analytics dashboard with company overview ring, distribution breakdown, and individual employee performance cards. |
| `/` | `RootRedirect` | Dynamic Redirect | Routes unauthenticated users to `/login`, users with `must_change_password=True` to `/change-password`, Admin to `/admin/tasks`, and Employee to `/dashboard`. |

---

## 5. Key Component Behaviors

### 5.1 `TaskFormModal` Optimistic Locking & Conflict Resolution
- When editing a task, `TaskFormModal` transmits the current integer `version` received from `TaskRead`.
- If another user or process modified the task concurrently, the backend returns **HTTP 409 Conflict**.
- Instead of crashing or silently overwriting, `TaskFormModal` detects status 409, sets `isConflict(true)`, and renders a warning banner:
  > *"Conflict: This task was modified by another user. Reload the latest version to review and apply your changes."*
- A dedicated **"Reload Latest Version"** action button calls `GET /tasks/{id}`, updates form fields with the fresh server data, synchronizes `editingTask.version`, and clears the conflict state so the user can re-apply changes safely.

### 5.2 `AuthLayout` Shared Authentication Frame
- Encapsulates the standard Deep Pine centered single-column layout, SVG brand header, Card surface container, title/subtitle block, and card footer across authentication screens (`LoginPage`, `SignupPage`, `VerifyEmailPage`).

### 5.3 `LoginPage` Dual Modes, Unverified Admin Helper & Error Handling
- **Two-Option Mode Toggle**: Provides a clean tabbed toggle between **"Login as Admin"** and **"Login as Employee"**.
  - **Admin Mode**: Displays an Email input field (`type="email"`, `placeholder="admin@example.com"`, `autoComplete="username"`).
  - **Employee Mode**: Displays a User ID input field (`type="text"`, `inputMode="numeric"`, `placeholder="1000000001"`, `autoComplete="username"`).
- **State Reset on Switch**: Toggling mode resets both the identifier and password fields, clearing active field validation errors, server error alerts, and unverified helper alerts.
- **Unverified Admin UX ("Option 2")**: In Admin mode, every HTTP 401 error displays the standard `"Incorrect credentials."` alert along with a contextual helper: *"Just signed up? You need to verify your email first."* and a **"Resend verification email"** button. This helper is shown on all Admin 401 failures to preserve anti-enumeration safety. If clicked, it calls `POST /auth/resend-verification` with the typed email (validating format first) and renders the generic server response or rate-limit message.
- **Registration Footer**: Includes a clear link: *"New to Teamloom? Create an account"* routing to `/signup`.
- **Robust Error Display**:
  - `401 Unauthorized`: Displays `"Incorrect credentials."`
  - `429 Too Many Requests`: Displays the server rate-limit message (e.g. `"Too many login attempts. Please try again later."`).
  - Network failures or `5xx` server errors: Displays `"Server error. Please try again."` (never masks server crashes as invalid credentials).

### 5.4 `SignupPage` Self-Serve Registration & Email Check State
- Provides inputs for Company Name, Full Name, Work Email, Password (min 6 chars), and Confirm Password (client-side match validation).
- Mirrors backend `SignupRequest` constraints and maps Pydantic 422 validation errors to individual fields.
- On HTTP 201 Created, replaces the input form with a **"Check your email"** state presenting confirmation guidance, a **"Resend verification email"** button, and a **"Go to login"** button.
- Anti-enumeration safe: duplicate registrations produce the identical success view. Does not automatically log in or issue tokens.

### 5.5 `VerifyEmailPage` Single-Use Token Verification & Fallback
- Reads `token` from `?token=...` query string on load.
- Uses a `useRef` execution guard (`hasRequestedRef`) to prevent React StrictMode double effect invocations from consuming single-use verification tokens twice in development.
- **Loading State**: Displays a centered spinner and status notice.
- **Success State**: Shows a green confirmation alert and **"Go to login"** button (no automatic login).
- **Failure State**: If the token is missing, invalid, or expired, displays `"Invalid or expired verification token."` alongside an inline email input and **"Resend verification email"** button to request a fresh link.

### 5.6 `MyTeamPage` Team Leave Visibility & View-Only Guard
- **Status Filter**: Defaults to `'ALL'` (`leaveStatusFilter = 'ALL'`) with `{ value: 'ALL', label: 'All Statuses' }` as the first dropdown option.
- **Backend Fetch**: Calls `GET /leaves/team` without query parameters, fetching leave requests across all statuses (`PENDING`, `APPROVED`, `REJECTED`) submitted by active direct reports. Deactivated direct reports are excluded by the backend.
- **View-Only Rationale**: In accordance with the system authority model, leave approvals are restricted exclusively to Tier 1 Administrators. The team leaves table on `MyTeamPage` provides direct managers with complete visibility into their direct reports' schedules, while explicitly noting: *"Approvals handled by Tier 1 Admin only"*.

### 5.7 `TaskList` Status Stepper & Completed Task Locking
- Employees can transition task status sequentially: `PENDING` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`.
- Each status update includes the task's current `version` (`PATCH /tasks/{id}`).
- If a conflict occurs during an inline stepper change, `TaskList` catches the 409 error and re-fetches the task list to align with server state.
- Once a task reaches `COMPLETED`, it is immutable: controls are disabled with a tooltip indicating completion.

### 5.8 `ChangePasswordPage` Session Invalidation & Feedback
- Supports both forced password change on first login and voluntary password updates initiated from `UserMenu`.
- **Live Strength Validation**: Integrates `PasswordChecklist` enforcing 8+ characters, uppercase, lowercase, digit, and special character requirements.
- **Session Revocation Handling**: Following `POST /auth/change-password`, the backend revokes the user's active session (`tokens_valid_after`). The frontend clears in-memory auth state via `authStore.clearAuth()` and redirects to `/login` with flash message `"Password changed, please log in again."`.

### 5.9 `AcceptInvitePage` & `ResetPasswordPage` Token Consumption & Strength Checklist
- Both `/accept-invite?token=...` and `/reset-password?token=...` read the token query parameter on mount.
- **Missing or Invalid Token Handling**: Missing, invalid, expired, or reused tokens display one generic friendly error alert:
  - Invites: *"This link is invalid or has expired. Ask your admin to resend the invite"*
  - Resets: *"This link is invalid or has expired. Please request a new reset link."* (with direct action link to `/forgot-password`).
- **Interactive Strength Checklist**: Renders dynamic check indicators confirming all 5 complexity criteria as the user types.
- **Success State**: Successful activation or reset presents a clear confirmation card with action button routing to `/login`.

### 5.10 `ForgotPasswordPage` Anti-Enumeration & Rate Limiting
- Public interface accepting an email address to dispatch a password recovery link (`POST /auth/forgot-password`).
- Anti-enumeration defense: always transitions to a generic confirmation view (*"If an account with that email exists, a password reset link has been sent."*), preventing account harvesting.
- Respects HTTP 429 rate limiting with parsed `Retry-After` display.

### 5.11 `AdminEmployeesPage` Roster Invitations & Status Badging
- Replaced temporary password provisioning with automated 48-hour expiring invite links (`POST /users/employees`).
- Status column renders real-time badges derived from `invitation_status`:
  - `PENDING` $\rightarrow$ Amber `Invite pending` badge with **Resend invite** and **Revoke invite** action buttons.
  - `ACTIVE` $\rightarrow$ Emerald `Active` badge with **Supervisor**, **Send password reset link**, and **Remove** action buttons.
  - `REVOKED` $\rightarrow$ Slate `Revoked` badge.
  - Deactivated $\rightarrow$ Slate `Removed` badge with **Restore** action.
- Excludes `PENDING` and `REVOKED` users from manager and assignee dropdowns across the application.

---

## 6. State Management & Session Lifecycle

Client-side authentication and session state is managed via Zustand in `frontend/src/store/authStore.js`.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant React as React App (App.jsx)
    participant Store as Zustand authStore
    participant API as Axios /api Client
    participant Backend as FastAPI Backend (/auth)

    Note over React,Backend: App Startup (Bootstrap Session Restoration)
    React->>Store: refreshSession() on mount
    Store->>API: POST /auth/refresh (with httpOnly cookie)
    alt Valid Refresh Token Cookie Present
        API->>Backend: POST /auth/refresh
        Backend-->>API: 200 OK {access_token, token_type}
        API-->>Store: sets accessToken in memory
        Store->>API: GET /users/me
        API->>Backend: GET /users/me (Bearer access_token)
        Backend-->>API: 200 OK User Profile JSON (with access_level, direct_reports_ids)
        API-->>Store: set user, isAuthenticated=true, isLoading=false
        Store->>API: GET /users/me/reports
        API-->>Store: set directReports
        Store-->>React: Session restored; renders authenticated view
    else No Cookie / Revoked / Expired
        Backend-->>API: 401 Unauthorized
        Store-->>React: clearAuth(); isAuthenticated=false, isLoading=false -> renders LoginPage
    end

    Note over User,Backend: Dual-Mode User Login Flow
    User->>React: Selects Mode (Admin/Employee), Enters Identifier & Password
    React->>Store: login(identifier, password, mode)
    Store->>API: POST /auth/login {identifier, password, mode}
    API->>Backend: POST /auth/login
    Backend-->>Store: 200 OK {access_token, must_change_password, user} + Set-Cookie refresh_token
    Store-->>React: User authenticated; redirects to target page (/admin/tasks, /dashboard, or /change-password)
```

### 6.1 Dual-Token Logout & Axios Interceptors
- **Logout Action**: Calls `POST /auth/logout` with `Authorization: Bearer <accessToken>`. The backend revokes both the access token and refresh token in `revoked_tokens`, and clears the cookie. The store resets all local state (`clearAuth()`).
- **Axios Request Interceptor**: Injects `Authorization: Bearer <token>` from in-memory state into every outgoing request.
- **Axios Response Interceptor**: Intercepts `401 Unauthorized` responses on protected endpoints, attempts a single silent `POST /auth/refresh`, updates the memory token, and retries the original request. If the refresh token was revoked or expired, it clears auth state and redirects to `/login`. Skips `/auth/` URLs to prevent loops.

---

## 7. Admin Tasks Dashboard Auto-Polling

- **Automatic Polling**: In `frontend/src/pages/AdminTasksPage.jsx`, a background interval triggers every 10 seconds (`setInterval(() => fetchData(true), 10000)`). It silently updates tasks and employee metadata without triggering loading skeletons.
- **Last Updated Indicator**: Displays a live `Last updated: <time>` timestamp indicator beside the "Task Control Panel" header.
- **Lifecycle Cleanup**: The interval timer is cleared cleanly on component unmount (`clearInterval`) to prevent background memory leaks.

---

## 8. Navigation Scoping: Tier 1 Performance Link

- In `frontend/src/components/layout/Navbar.jsx`, the `"My performance"` link (`/my-performance`) is hidden for Tier 1 Executive / System Admins (`{user?.access_level !== 1 && (...)}`).
- Tier 1 Administrators manage system-wide operations, employees, and org-wide analytics rather than personal individual tasks. Hiding the link streamlines the navigation bar for administrative workflows.

---

## 9. Employee Directory Pagination & `fetchAllEmployees` Helper

- **Helper Function**: `fetchAllEmployees()` in `frontend/src/lib/api.js` pages through `GET /users/` using `limit=100` in a while-loop until a page returns fewer than 100 records, returning the aggregated array.
- **Consumer Components**:
  - `AdminEmployeesPage.jsx`: Loads the full employee directory without truncation.
  - `AdminTasksPage.jsx`: Fetches all assignable employees for filtering and assignment labels.
  - `AdminLeavesPage.jsx`: Resolves applicant names across all leave requests.
  - `AdminPerformancePage.jsx`: Populates employee drill-down filter dropdown.
  - `TaskFormModal.jsx`: Populates task assignment selector dropdown.
- **Error & 404 Handling**: Retains existing per-page `<Alert>` error displays for API errors and 404 responses without adding full-page 404 route overrides.
