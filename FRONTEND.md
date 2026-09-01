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
| **oxlint** | `^1.75.0` | High-performance Rust-based JavaScript/JSX linter |

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
│   │   ├── employees/              # Employee administration components
│   │   │   └── EmployeeFormModal.jsx   # Modal for creating employees with code, designation & supervisor
│   │   ├── guards/
│   │   │   ├── AdminRoute.jsx          # Route guard restricting access to ADMIN users
│   │   │   ├── ManagerRoute.jsx        # Route guard restricting access to users with direct reports or ADMIN
│   │   │   ├── PasswordChangeRoute.jsx # Route guard permitting access to all authenticated users for forced or voluntary password updates
│   │   │   └── ProtectedRoute.jsx      # Route guard redirecting unauthenticated users to /login and pending password users to /change-password
│   │   ├── layout/
│   │   │   ├── Navbar.jsx          # Top application bar with logo, brand title, and navigation links
│   │   │   └── UserMenu.jsx        # Avatar initials button triggering dropdown menu with user info, designation, employee code/email, password change link, and logout button
│   │   ├── ui/                     # Deep Pine design primitives
│   │   │   ├── Alert.jsx           # Status alert box (info, success, warning, danger)
│   │   │   ├── Badge.jsx           # Status & priority badge (slate, amber, teal, emerald, coral, red, violet, blue)
│   │   │   ├── Button.jsx          # Styled button (primary, secondary, danger, ghost variants; sm, md, lg sizes)
│   │   │   ├── Card.jsx            # Surface card container (Card, CardHeader, CardTitle, CardDescription, CardContent)
│   │   │   ├── DueCountdown.jsx    # Relative deadline countdown indicator with live 1-minute ticker
│   │   │   ├── EmptyState.jsx      # Placeholder banner with icon, title, description, and action button
│   │   │   ├── Input.jsx           # Text/password input field with validation error state and password visibility toggle
│   │   │   ├── Modal.jsx           # Centered modal dialog wrapper with backdrop and escape/close triggers
│   │   │   ├── Select.jsx          # Styled native select dropdown component
│   │   │   ├── Spinner.jsx         # SVG loading spinner indicator (sm, md, lg sizes)
│   │   │   └── Textarea.jsx        # Multi-line text input field with error messaging
│   │   ├── LeaveForm.jsx           # Employee leave submission form card with date validation
│   │   ├── LeaveHistoryList.jsx    # Stacked timeline list of personal leave requests with filter/status badges
│   │   ├── LeaveRejectModal.jsx    # Modal dialog for capturing rejection rationale on leave review
│   │   ├── MilestoneTrail.jsx      # Chronological task state dots (on-time, late, pending, overdue) with tooltips
│   │   ├── PerformanceRing.jsx     # Static SVG circular on-time percentage ring with metric cards breakdown
│   │   ├── TaskCard.jsx            # Employee task card with priority badge, countdown, and inline status stepper
│   │   ├── TaskDeleteModal.jsx     # Confirmation dialog for deleting a task
│   │   ├── TaskFormModal.jsx       # Task create/edit dialog with date-time picker and assignee selector
│   │   └── TaskList.jsx            # Responsive employee task grid with filter controls and empty states
│   ├── lib/
│   │   ├── api.js                  # Axios client configuration with JWT injection and silent 401 refresh handler
│   │   └── dateUtils.js            # Date/datetime formatting helpers (ISO, local format, datetime-local input)
│   ├── pages/                      # Page view containers
│   │   ├── AdminEmployeesPage.jsx  # System-wide employee management directory for administrators (/admin/employees)
│   │   ├── AdminLeavesPage.jsx     # System-wide leave approval hub for administrators (/admin/leaves)
│   │   ├── AdminTasksPage.jsx      # System-wide task control panel for administrators (/admin/tasks)
│   │   ├── ChangePasswordPage.jsx  # Forced initial password update page (/change-password)
│   │   ├── DashboardPage.jsx       # Employee personal task management dashboard (/dashboard)
│   │   ├── LeavesPage.jsx          # Employee personal leave request portal (/leaves)
│   │   ├── LoginPage.jsx           # Sign-in page supporting employee code and password (/login)
│   │   ├── MyPerformancePage.jsx   # Employee personal performance analytics page (/my-performance)
│   │   ├── MyTeamPage.jsx          # Manager direct report roster, team tasks, leaves, and analytics (/my-team)
│   │   └── RegisterPage.jsx        # Legacy employee registration page (retained for reference; superseded by admin creation)
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

### 3.2 Typography & Spacing Conventions
- **Base Font Family**: System sans-serif stack (`system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif`).
- **Code & Identifiers**: Monospace font family (`font-mono`) used for employee codes (`EMP-1001`), user IDs (`#12`), and numerical percentages.
- **Hierarchy**:
  - `h1`: 20px (`text-xl font-semibold text-[var(--text-primary)]`)
  - `h2` / Card Titles: 16px (`text-base font-semibold text-[var(--text-primary)]`)
  - Section Headers: 12px uppercase (`text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]`)
  - Body Text: 14px (`text-sm`) and Secondary Labels: 12px (`text-xs`)
  - Metadata / Badges / Tooltips: 10px–11px (`text-[10px]` or `text-[11px]`)
- **Spacing**: Consistent 4px grid steps (`gap-2`, `gap-3`, `gap-4`, `gap-6`, `p-4`, `p-6`).

---

## 4. Page Routing & View Reference

| Route | Page Component | Guard / Access Level | Purpose & Rendered Content |
|---|---|---|---|
| `/login` | `LoginPage` | Public | Employee ID (`EMP-XXXX`) and password input form with validation alerts and automatic post-login role redirection. |
| `/change-password` | `ChangePasswordPage` | `ProtectedRoute` | Mandatory password update screen for newly provisioned employees; captures current temporary password, validates new password (min 6 chars), and submits to `/auth/change-password`. |
| `/dashboard` | `DashboardPage` | `ProtectedRoute` (Employee & Admin) | Main employee dashboard displaying session status banner, user profile hero card, and the `TaskList` task board. |
| `/leaves` | `LeavesPage` | `ProtectedRoute` (Employee & Admin) | Employee self-service leave portal rendering `LeaveForm` submission card and `LeaveHistoryList` timeline. |
| `/my-performance` | `MyPerformancePage` | `ProtectedRoute` (Employee & Admin) | Personal performance analytics dashboard rendering `PerformanceRing` on-time circular gauge, metric count cards, and `MilestoneTrail`. |
| `/my-team` | `MyTeamPage` | `ManagerRoute` (Managers & Admin) | Team management workspace rendering direct reports roster chips, tabbed team tasks table, tabbed team leave approvals table, and team/individual performance analytics. |
| `/admin/tasks` | `AdminTasksPage` | `AdminRoute` (Admin only) | Comprehensive system-wide task table with instant status, priority, and employee dropdown filters, `TaskFormModal` trigger, and `TaskDeleteModal`. |
| `/admin/leaves` | `AdminLeavesPage` | `AdminRoute` (Admin only) | System-wide leave approval table with status filter (defaulting to `PENDING`), inline one-click approve, and `LeaveRejectModal` for rejection. |
| `/admin/employees` | `AdminEmployeesPage` | `AdminRoute` (Admin only) | System-wide employee directory showing codes, designations, reporting relationships, search filter, and `EmployeeFormModal` for provisioning new employees. |
| `/` | `RootRedirect` | Dynamic Redirect | Routes unauthenticated users to `/login`, users with `must_change_password=True` to `/change-password`, Admin to `/admin/tasks`, and Employee to `/dashboard`. |

---

## 5. Reusable Component Catalog

### 5.1 UI Primitives (`frontend/src/components/ui/`)

| Component | Props | Purpose | Used In |
|---|---|---|---|
| `Alert` | `variant` (`info`, `success`, `warning`, `danger`), `className`, `children` | Status message banner with corresponding background and border tints | `LoginPage`, `RegisterPage`, `ChangePasswordPage`, `DashboardPage`, `MyPerformancePage`, `MyTeamPage`, `AdminTasksPage`, `AdminLeavesPage` |
| `Badge` | `variant` (`slate`, `amber`, `teal`, `emerald`, `coral`, `red`, `violet`, `blue`), `size` (`sm`, `md`), `className`, `children` | Visual status and priority pill with muted background tint | `Navbar`, `TaskCard`, `TaskList`, `LeaveHistoryList`, `AdminTasksPage`, `AdminLeavesPage`, `MyTeamPage` |
| `Button` | `variant` (`primary`, `secondary`, `danger`, `ghost`), `size` (`sm`, `md`, `lg`), `disabled`, `className`, `onClick`, `children` | Unified button component adhering to Deep Pine interactive tokens | Used across all pages, modals, and list components |
| `Card` | `className`, `children` (also exports `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`) | Standard surface container with `--surface-1` background and `--border` hairline | `LoginPage`, `RegisterPage`, `ChangePasswordPage`, `DashboardPage`, `LeaveForm`, `MyPerformancePage`, `MyTeamPage` |
| `DueCountdown` | `dueDatetime`, `status`, `className` | Real-time relative countdown timer ticking every 60s; displays "Overdue by Xd Yh" (red), "Xh Ym left" (coral/amber/secondary), or "Completed" (emerald) | `TaskCard`, `AdminTasksPage`, `MyTeamPage` |
| `EmptyState` | `icon`, `title`, `description`, `action` | Clean empty state placeholder with icon, message, and action CTA | `TaskList`, `LeaveHistoryList`, `AdminTasksPage`, `AdminLeavesPage`, `MyTeamPage` |
| `Input` | `label`, `error`, `helperText`, `type`, `id`, `className`, `...props` | Text input with validation styling, accessible label, and interactive show/hide password toggle button when `type="password"` | `LoginPage`, `RegisterPage`, `ChangePasswordPage`, `LeaveForm`, `TaskFormModal` |
| `Modal` | `isOpen`, `onClose`, `title`, `description`, `children`, `footer`, `size` (`sm`, `md`, `lg`, `xl`) | Accessible modal dialog with `--surface-2` backdrop overlay, ESC key listener, and click-outside dismissal | `LeaveRejectModal`, `TaskDeleteModal`, `TaskFormModal` |
| `Select` | `label`, `error`, `helperText`, `options` (`[{value, label}]`), `className`, `...props` | Styled select dropdown matching `--surface-1` styling | `TaskFormModal`, `TaskList`, `AdminTasksPage`, `AdminLeavesPage`, `MyTeamPage` |
| `Spinner` | `size` (`sm`, `md`, `lg`), `className` | Animated SVG loading indicator spinner | `App`, `Button`, `TaskList`, `LeaveHistoryList`, `AdminTasksPage`, `AdminLeavesPage`, `MyTeamPage`, `MyPerformancePage` |
| `Textarea` | `label`, `error`, `helperText`, `className`, `...props` | Multi-line text field with validation error messaging | `LeaveForm`, `TaskFormModal`, `LeaveRejectModal` |

### 5.2 Layout & Feature Components (`frontend/src/components/`)

| Component | Props | Purpose | Used In |
|---|---|---|---|
| `Navbar` | `rightSlot` | Top navigation header rendering logo, app title, navigation tabs (`Tasks`, `Leaves`, `My Team`, `Performance`), and user menu | `DashboardPage`, `LeavesPage`, `MyPerformancePage`, `MyTeamPage`, `AdminTasksPage`, `AdminLeavesPage` |
| `UserMenu` | None | User profile chip rendering initials avatar, role badge, quick link to `/change-password`, and one-click sign out button | Mounted in `Navbar` `rightSlot` across all authenticated pages |
| `TaskCard` | `task`, `onStatusChange` | Individual task card showing title, description, priority badge, `DueCountdown`, and interactive status stepper (`PENDING` → `IN_PROGRESS` → `COMPLETED`) | `TaskList` |
| `TaskList` | None | Employee dashboard task board featuring status filter pills, priority filter dropdown, task count metrics, and responsive grid of `TaskCard` items | `DashboardPage` |
| `LeaveForm` | `onLeaveSubmitted` | Card form allowing employees to submit leave requests with start/end date validation (`end_date >= start_date`) and reason field | `LeavesPage` |
| `LeaveHistoryList` | `ref` (exposes `refresh()`) | Stacked timeline list of personal leave requests with status badges, reviewer status, and duration calculations | `LeavesPage` |
| `LeaveRejectModal` | `isOpen`, `onClose`, `onSuccess`, `leave`, `employee` | Modal dialog allowing Admin or Manager to reject a leave request and record the rejection | `AdminLeavesPage`, `MyTeamPage` |
| `TaskFormModal` | `isOpen`, `onClose`, `onSuccess`, `editingTask`, `assignableEmployees` | Modal dialog for creating or updating tasks; dynamically supports assigning to all employees (Admin) or direct reports only (Manager) | `AdminTasksPage`, `MyTeamPage` |
| `TaskDeleteModal` | `isOpen`, `onClose`, `onSuccess`, `task` | Confirmation modal dialog for deleting a task with warning details | `AdminTasksPage`, `MyTeamPage` |
| `PerformanceRing` | `stats` | Static SVG circular progress ring rendering on-time completion percentage accompanied by a 4-metric count breakdown grid (On-Time, Late, Overdue, Pending) | `MyPerformancePage`, `MyTeamPage` |
| `MilestoneTrail` | `trail` (`list[TrailItem]`) | Horizontal trail of task status dots (On-Time [Teal], Late [Coral], Pending [Muted], Overdue [Red]) with hover tooltips and legend | `MyPerformancePage`, `MyTeamPage` |

### 5.3 Route Guards (`frontend/src/components/guards/`)

| Guard Component | Props | Validation Logic |
|---|---|---|
| `ProtectedRoute` | `children` | Checks `isAuthenticated` in `authStore`. If false, redirects to `/login`. If `user.must_change_password` is true and current path is not `/change-password`, redirects to `/change-password`. |
| `PasswordChangeRoute` | `children` | Verifies `isAuthenticated` in `authStore`. Permits access to any logged-in user to allow both forced initial password changes and voluntary self-service password updates from the profile dropdown. |
| `AdminRoute` | `children` | Wraps `ProtectedRoute` and verifies `user.role === 'ADMIN'`. If non-admin, redirects to `/dashboard`. |
| `ManagerRoute` | `children` | Wraps `ProtectedRoute` and verifies user is an `ADMIN` OR has `directReports.length > 0`. If plain employee without reports, redirects to `/dashboard`. |

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
        Backend-->>API: 200 OK User Profile JSON
        API-->>Store: set user, isAuthenticated=true, isLoading=false
        Store->>API: GET /users/me/reports
        API-->>Store: set directReports
        Store-->>React: Session restored; renders authenticated view
    else No Cookie / Expired
        Backend-->>API: 401 Unauthorized
        Store-->>React: clearAuth(); isAuthenticated=false, isLoading=false -> renders LoginPage
    end

    Note over User,Backend: User Login Flow
    User->>React: Submits Employee ID & Password
    React->>Store: login(employeeCode, password)
    Store->>Backend: POST /auth/login
    Backend-->>Store: 200 OK {access_token, must_change_password, user} + Set-Cookie refresh_token
    Store-->>React: User authenticated; redirects to target page
```

### 6.1 `authStore` State Properties & Actions

- **State Properties**:
  - `user`: Authenticated user profile object (`id`, `full_name`, `email`, `role`, `employee_code`, `must_change_password`, `reports_to_id`, `designation`).
  - `accessToken`: Short-lived JWT string stored purely in memory.
  - `isAuthenticated`: Boolean flag (`Boolean(user && accessToken)`).
  - `isLoading`: Boolean flag indicating initial bootstrap session check.
  - `directReports`: Array of direct report employee objects managed by the current user.
- **Store Actions**:
  - `login(employeeCode, password)`: Authenticates credentials, stores access token, sets user data, and triggers `fetchDirectReports()`.
  - `refreshSession()`: Executed once on `App` mount to seamlessly restore active sessions via silent cookie refresh.
  - `changePassword(currentPassword, newPassword)`: Posts new credentials, updates local user state, and re-fetches direct reports.
  - `fetchDirectReports()`: Queries `/users/me/reports` and caches direct report users.
  - `logout()`: Calls `POST /auth/logout` to clear the httpOnly cookie and invokes `clearAuth()`.
  - `clearAuth()`: Resets all store variables to default empty state.

### 6.2 Axios Interceptors & Silent Token Rotation (`frontend/src/lib/api.js`)
- **Request Interceptor**: Reads `accessToken` from `useAuthStore.getState()` and automatically injects header `Authorization: Bearer <token>` into outgoing requests.
- **Response Interceptor**: Intercepts HTTP `401 Unauthorized` responses on protected endpoints, attempts a single silent POST `/auth/refresh` request with credentials, updates the in-memory token, and transparently retries the failed original request. If the refresh request fails, it invokes `clearAuth()` to cleanly reset the UI.

---

## 7. Known Deferred Work & UI State Notes

> [!NOTE]
> **Static UI Architecture (v1 Release Specification)**:
> The v1 user interface is deliberately designed with static layout stability. Micro-animations, page transitions, and motion smoothing (e.g. Framer Motion, CSS keyframe sweeps) are explicitly deferred to a future polish milestone. All UI components currently render with instant state updates and zero decorative animation delays to ensure maximum responsiveness and predictable testability.
