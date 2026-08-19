# Employee Task Management System — Frontend & UI Architecture Guide

This document provides a comprehensive end-to-end overview of the **Employee Task Management System** frontend architecture, design system, technology stack, styling rules, backend integration contracts, and feature-by-feature implementation progress from 0 to completion.

---

## 1. Technology Stack & Tooling

The frontend application is built as a single-page web application (SPA) housed inside the `frontend/` directory.

| Technology / Library | Version | Role in Frontend | Why Selected |
|---|---|---|---|
| **React** | `^19.2.8` | Core UI Framework | Declarative component model, ultra-fast Virtual DOM rendering, and modern React 19 hooks. |
| **Vite** | `^8.2.0` | Build Tool & Dev Server | Lightning-fast HMR (Hot Module Replacement) and optimized production Rollup bundling. |
| **Tailwind CSS** | `^4.3.3` | Utility-First Styling Framework | Zero-runtime CSS processing via `@tailwindcss/vite` plugin for rapid, responsive UI development. |
| **Lucide React** | `^1.31.0` | Icon Library | Clean, modern SVG icon set for task priority, status badges, actions, and navigation elements. |
| **Oxlint** | `^1.75.0` | Code Quality & Linting | High-performance Rust-backed linter for JavaScript/JSX code quality enforcement. |
| **Environment Config** | `.env` | Environment Variables | Manages base API URLs (`VITE_API_BASE_URL=http://localhost:8000`) without hardcoding secrets. |

---

## 2. Design System & Frontend Building Rules ("Deep Pine" Palette)

To ensure a calm, restrained, enterprise-grade aesthetic, all UI components adhere to the **Deep Pine** design standards:

### Color Tokens & Palette
```css
:root {
  /* Backgrounds / surfaces */
  --bg-page: #0E1614;        /* page background */
  --surface-1: #131F1C;      /* cards, panels */
  --surface-2: #17251F;      /* elevated: modals, dropdowns, popovers */

  /* Borders */
  --border: #223330;         /* default hairline */
  --border-strong: #2C4038;  /* hover / emphasized divider */

  /* Text */
  --text-primary: #DCEAE5;
  --text-secondary: #8FA79E;
  --text-muted: #5E7168;

  /* Accent (single accent color — teal) */
  --accent: #3FA88F;
  --accent-hover: #4FBE9F;
  --accent-active: #359078;
  --on-accent: #04231C;      /* text/icon color when placed ON the accent fill */

  /* Semantic status colors — muted tints */
  --amber: #D9A441;          /* pending */
  --amber-bg: rgba(217, 164, 65, 0.12);
  --teal: #3FA88F;           /* in progress — reuses accent */
  --teal-bg: rgba(63, 168, 143, 0.12);
  --green: #6FBE7A;          /* completed / approved / success */
  --green-bg: rgba(111, 190, 122, 0.12);
  --coral: #D98C6B;          /* high priority */
  --coral-bg: rgba(217, 140, 107, 0.12);
  --red: #D9695A;            /* rejected / destructive / danger */
  --red-bg: rgba(217, 105, 90, 0.12);
  --violet: #9C87C9;         /* admin role badge */
  --violet-bg: rgba(156, 135, 201, 0.12);
  --blue: #5FA0D9;           /* employee role badge */
  --blue-bg: rgba(95, 160, 217, 0.12);
  --slate: #8FA79E;          /* low priority — reuses text-secondary tone */
  --slate-bg: rgba(143, 167, 158, 0.10);
}
```

### Aesthetic & Theme Constraints
1. **Restrained Aesthetic**:
   * No glassmorphism, no indigo, no glow effects, no blur, no gradients on cards or buttons.
   * Hairline 1px borders (`var(--border)`).
   * Backgrounds use `--bg-page` (`#0E1614`), `--surface-1` (`#131F1C`), `--surface-2` (`#17251F`).
2. **Typography & Font Weight Discipline**:
   * System sans-serif stack with antialiased font smoothing (`-webkit-font-smoothing: antialiased`).
   * **Two Weights Only**: `400` (regular) and `500` (medium). 600/700 font weights are strictly prohibited.
   * **Sentence Case Everywhere**: All labels, headings, buttons, and badges use sentence case (no ALL CAPS, no Title Case). No terminal punctuation on buttons/headings/labels.
3. **Micro-Interactivity**:
   * Interactive elements feature `transition-all duration-150 ease-out`, `active:scale-[0.98]`, and cursor pointer.
   * Focus state uses a subtle 2px ring at 30% opacity (`focus:ring-2 focus:ring-[var(--accent)]/30`).
4. **No Unstyled Defaults**:
   * Every form input, select dropdown, button, badge, modal, alert, and card is built as a reusable component in `src/components/ui/`.

---

## 3. Backend Integration Contracts & Enum Enforcements

The frontend communicates with the FastAPI backend running at `http://localhost:8000`.

### Data Models & Enum Casing Table

| Entity / Field | Enum / Type | Exact Values & Casing | Frontend Badge Variant & Style |
|---|---|---|---|
| **User Role** | `UserRole` | `"ADMIN"`, `"EMPLOYEE"` | `ADMIN`: Violet (`#9C87C9`), `EMPLOYEE`: Blue (`#5FA0D9`). |
| **Task Status** | `TaskStatus` | `"PENDING"`, `"IN_PROGRESS"`, `"COMPLETED"` | `PENDING`: Amber (`#D9A441`), `IN_PROGRESS`: Teal (`#3FA88F`), `COMPLETED`: Green (`#6FBE7A`). |
| **Task Priority** | `TaskPriority` | `"LOW"`, `"MEDIUM"`, `"HIGH"` | `LOW`: Slate (`#8FA79E`), `MEDIUM`: Amber (`#D9A441`), `HIGH`: Coral (`#D98C6B`). |
| **Leave Status** | `LeaveStatus` | `"PENDING"`, `"APPROVED"`, `"REJECTED"` | `PENDING`: Amber (`#D9A441`), `APPROVED`: Green (`#6FBE7A`), `REJECTED`: Red (`#D9695A`). |

### Component Library Specification (`src/components/ui/`)
* **`Button`**: `primary` (teal filled), `secondary` (outlined), `ghost` (text only), `danger` (red filled). Sizes: `sm`, `md`. Supports spinner loading & disabled states.
* **`Input` / `Textarea` / `Select`**: Surface-1 background, label above, error ring + error helper text below.
* **`Badge`**: Pill shape (`rounded-full`), tinted background, decoupled generic visual variants (`amber`, `emerald`, `green`, `coral`, `red`, `violet`, `blue`, `slate`, `teal`).
* **`Card`**: Surface-1 background, rounded-xl (12px), optional hover border highlight for clickable cards.
* **`Modal`**: Centered panel on surface-2, rounded-xl, Lucide `X` close button, backdrop overlay `bg-black/50`.
* **`Spinner`**: Rotating ring using `border-t-[var(--accent)]`.
* **`EmptyState`**: Centered icon + headline + one-line description + optional CTA action.
* **`Alert`**: Inline banner using status bg/text pairs, dismissible with X.

### Layout & Guards Architecture (`src/components/layout/` & `src/components/guards/`)
* **`Navbar` (`src/components/layout/Navbar.jsx`)**: Top bar shell: surface-1, 1px bottom border, `h-14`, title on left, role-based navigation tabs in middle, right-side slot for profile bar.
* **`UserMenu` (`src/components/layout/UserMenu.jsx`)**: User profile bar displaying user avatar initials, full name, role badge, and logout action.
* **`ProtectedRoute` (`src/components/guards/ProtectedRoute.jsx`)**: Authenticated session guard.
* **`AdminRoute` (`src/components/guards/AdminRoute.jsx`)**: Admin role-based authorization guard.

---

## 4. End-to-End Feature Implementation Roadmap

[Phase 0: Environment & Infrastructure] ──▶ 100% COMPLETED
[Phase 1: Design System & Components]  ──▶ 100% COMPLETED
[Phase 2: Auth & User Session Management] ──▶ 100% COMPLETED
[Phase 3: Task Management Dashboard]    ──▶ 100% COMPLETED
[Phase 4: Admin Task Control Panel]     ──▶ 100% COMPLETED
[Phase 5: Employee Leave Portal]        ──▶ 100% COMPLETED
[Phase 6: Admin Leave Review Portal]    ──▶ 100% COMPLETED

---

## 5. Phase 2: Auth & Session Management Architecture

Phase 2 establishes end-to-end security, session persistence, and state management using the backend's `httpOnly` refresh token cookie mechanism.

### Key Architecture Components
1. **Axios Client (`src/lib/api.js`)**:
   - `withCredentials: true` enables browser transmission of `httpOnly` refresh cookies across origins.
   - **Request Interceptor**: Attaches `Authorization: Bearer <accessToken>` header from memory.
   - **Response Interceptor**: Catches 401 errors, performs one silent `POST /auth/refresh` call, updates in-memory access token, and retries original request once.

2. **In-Memory Auth Store (`src/store/authStore.js`)**:
   - `accessToken`: Maintained strictly in memory (never stored in `localStorage` or `sessionStorage`).
   - `user`: User object (`{ id, full_name, email, role }`).
   - `refreshSession()`: Executed on app mount (`App.jsx`). Silently restores session via `POST /auth/refresh` and fetches user profile from `/users/me`.

3. **Routing & Guards**:
   - `ProtectedRoute.jsx`: Displays centered loading `<Spinner size="lg" />` during initial session restoration, redirects unauthenticated users to `/login`.
   - `LoginPage.jsx` (`/login`): Form with Email & Password inputs, primary button with spinner, client-side inline validation, error alert banner.
   - `RegisterPage.jsx` (`/register`): Form with Full Name, Email, Password. Default role `EMPLOYEE`. Client-side inline validation, auto-login after submit.

4. **Navbar Profile Bar (`src/components/UserMenu.jsx`)**:
   - Displays user initials avatar circle, full name, role `Badge` (`ADMIN` -> violet, `EMPLOYEE` -> blue), and a logout button calling `logout()` (which invokes `POST /auth/logout` on the backend to clear the cookie).

---

## 6. Phase 3: Employee Task List (Card View) Architecture

Phase 3 renders the employee-facing task management dashboard at `/dashboard`.

### Key Features & Components
1. **Data Fetching (`src/components/TaskList.jsx`)**:
   - Fetches assigned tasks via `GET /tasks/?limit=50`.
   - Handles loading spinner, empty state (`CheckSquare` icon + description), and error alert states gracefully.

2. **Card Grid & Badge Mapping (`src/components/TaskCard.jsx`)**:
   - Layout: Responsive 3-column grid (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4`).
   - Priority Badges: `LOW` (slate), `MEDIUM` (amber), `HIGH` (coral).
   - Status Badges: `PENDING` (amber), `IN_PROGRESS` (teal), `COMPLETED` (emerald).
   - Description: Truncated to 2 lines (`line-clamp-2 text-xs text-[var(--text-muted)]`).

3. **Relative Due Date Countdown (`src/utils/dateUtils.js`)**:
   - Formats task due dates into relative countdowns ("Due today", "Due tomorrow", "Due in N days", "Overdue by N days" in `--red`).

4. **Inline Status Updater**:
   - Embedded `Select` control on each card allowing employees to transition task status (`PENDING` → `IN_PROGRESS` → `COMPLETED`).
   - Executes `PATCH /tasks/{id}` with `{ status: newStatus }`.
   - Displays a card-specific spinner during updates without blocking the page, and shows inline error messages if an update fails.

---

## 7. Phase 4: Admin Task Control Panel (Table View) Architecture

Phase 4 implements system-wide task administration for users with the `ADMIN` role at `/admin/tasks`.

### Key Features & Components
1. **Role Guard & Role Routing (`src/components/AdminRoute.jsx`)**:
   - `AdminRoute` verifies `user.role === 'ADMIN'`. Non-admin users attempting direct URL access are immediately redirected to `/dashboard`.
   - Post-login redirection routes `ADMIN` users to `/admin/tasks` and `EMPLOYEE` users to `/dashboard`.

2. **System-Wide Task Table (`src/pages/AdminTasksPage.jsx`)**:
   - Renders system-wide tasks in a clean table layout using `--surface-1` background, `--border` dividers, and `--surface-2` row hover states.
   - Displays Title, Assigned Employee, Priority Badge, Status Badge, Due Date, and Edit/Delete action icons.

3. **Filter Controls**:
   - Status, Priority, and Employee filter selects above the table for instant client-side filtering.

4. **Task Form Modal (`src/components/TaskFormModal.jsx`)**:
   - Single reusable modal for both Task Creation (`POST /tasks/`) and Task Editing (`PATCH /tasks/{id}`).
   - Dynamically populates employee dropdown from `GET /users/`.
   - Handles inline field validation and submit loading spinners.

5. **Task Delete Confirmation Modal (`src/components/TaskDeleteModal.jsx`)**:
   - Confirmation dialog displaying target task title with Cancel and danger Delete Task buttons in the footer.
   - Executes `DELETE /tasks/{id}` and updates table on success.

---

## 8. Phase 5: Employee Leave Portal Architecture

Phase 5 implements personal leave request submission and history tracking at `/leaves`.

### Key Features & Components
1. **Leave Submission Form (`src/components/LeaveForm.jsx`)**:
   - Form card accepting `Reason` (`Textarea`), `Start Date` (`Input type="date"`), and `End Date` (`Input type="date"`).
   - Client-side validation enforces `end_date >= start_date` with inline error helper text under End Date.
   - Executes `POST /leaves/` with payload `{ reason, start_date, end_date }`.

2. **Personal Leave History List (`src/components/LeaveHistoryList.jsx`)**:
   - Fetches personal leave requests via `GET /leaves/?limit=50`.
   - Displays stacked card list sorted newest-first (`created_at desc`).
   - Badges: `PENDING` (amber), `APPROVED` (green/emerald), `REJECTED` (red).
   - Shows date range, calculated duration in days, reason text, and submitted date timestamp.

---

## 9. Phase 6: Admin Leave Approval Hub Architecture

Phase 6 implements system-wide leave request review for users with the `ADMIN` role at `/admin/leaves`.

### Key Features & Components
1. **Role Guard & Admin Navigation (`src/components/AdminRoute.jsx` & `src/components/ui/Navbar.jsx`)**:
   - `/admin/leaves` guarded by `<AdminRoute>`.
   - Top `Navbar` renders role-specific tabs: **Task Control Panel** (`/admin/tasks`) and **Leave Approval** (`/admin/leaves`).

2. **System-Wide Leave Table (`src/pages/AdminLeavesPage.jsx`)**:
   - Renders system-wide leave requests in a high-density table view with Status filter defaulting to `PENDING` ("Pending Review").
   - Columns: Employee (name & email), Date Range (start → end + duration), Reason, Status Badge, Submitted On, Actions (Approve / Reject).

3. **Inline Approve Action**:
   - Executes `PATCH /leaves/{id}` with `{ status: "APPROVED" }`. Updates status badge in place to `Approved` (green) and removes action buttons.

4. **Reject Confirmation Modal (`src/components/LeaveRejectModal.jsx`)**:
   - Confirmation dialog asking admin to confirm leave rejection.
   - Executes `PATCH /leaves/{id}` with `{ status: "REJECTED" }`. Updates status badge in place to `Rejected` (red) and removes action buttons.

---

## 10. How to Run & Verify the Frontend

### Development Execution
To start the live Vite development server:
```bash
cd frontend
npm run dev
```
Access the application in your browser at:
👉 **`http://localhost:5173`**

### Production Build Verification
To compile and verify the production bundle:
```bash
cd frontend
npm run build
```
Output bundles are generated in `frontend/dist/`.
