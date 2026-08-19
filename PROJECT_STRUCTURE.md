# Project Structure Guide

A tree view of the **Employee Task Management System** codebase with one-line descriptions for every source file.

```text
Employee Task Management/
├── app/                                       # FastAPI Backend Application
│   ├── core/                                  # Core Configuration & Security Modules
│   │   ├── config.py                          # Environment settings & secret key configurations
│   │   ├── exceptions.py                      # Custom HTTP exception handlers (400, 401, 403, 404)
│   │   └── security.py                        # Password hashing & JWT access/refresh token logic
│   ├── db/                                    # Database Engine & Session Setup
│   │   ├── base.py                            # SQLAlchemy Base model class declaration
│   │   └── session.py                         # Async SQLAlchemy engine & session dependency
│   ├── models/                                # SQLAlchemy ORM Database Models
│   │   ├── leave.py                           # LeaveRequest database table model & LeaveStatus enum
│   │   ├── task.py                            # Task database table model, TaskStatus & TaskPriority enums
│   │   └── user.py                            # User database table model & UserRole enum
│   ├── routes/                                # HTTP API Controller Route Handlers
│   │   ├── auth.py                            # Login, registration, token refresh & logout endpoints
│   │   ├── leaves.py                          # Employee leave request submission & admin review endpoints
│   │   ├── tasks.py                           # Employee task view & admin task CRUD endpoints
│   │   └── users.py                           # User profile & employee directory listing endpoints
│   ├── schemas/                               # Pydantic Request & Response Validation Schemas
│   │   ├── leave.py                           # Pydantic validation schemas for leave creation & review
│   │   ├── task.py                            # Pydantic validation schemas for task creation & status updates
│   │   └── user.py                            # Pydantic validation schemas for auth tokens & user profiles
│   ├── services/                              # Database Query & Domain Business Logic Layer
│   │   ├── auth_service.py                    # User authentication, registration & token generation logic
│   │   ├── leave_service.py                   # Leave request submission, filtering & approval business logic
│   │   ├── task_service.py                    # Task creation, scoping, filtering & status update business logic
│   │   └── user_service.py                    # Employee listing & user profile update business logic
│   └── main.py                                # FastAPI app initialization, CORS middleware & route registration
│
├── frontend/                                  # React 19 + Vite + Tailwind CSS Frontend Application
│   ├── src/
│   │   ├── components/                        # Feature-Specific UI Components & Sub-panels
│   │   │   ├── guards/                        # Route Security & Authorization Guards
│   │   │   │   ├── AdminRoute.jsx             # Role guard restricting routes to ADMIN role users
│   │   │   │   └── ProtectedRoute.jsx         # Auth guard restricting routes to authenticated users
│   │   │   ├── layout/                        # Global Layout Components
│   │   │   │   ├── Navbar.jsx                 # Top header navigation bar with role-based tab links
│   │   │   │   └── UserMenu.jsx               # Header session bar with user avatar, role badge & logout
│   │   │   ├── ui/                            # Domain-Agnostic Reusable Design System Primitives
│   │   │   │   ├── Alert.jsx                  # Dismissible status/error alert banner
│   │   │   │   ├── Badge.jsx                  # Generic colored pill badge label component
│   │   │   │   ├── Button.jsx                 # Primary, secondary, ghost & danger button variants
│   │   │   │   ├── Card.jsx                   # Dark surface container card component
│   │   │   │   ├── EmptyState.jsx             # Centered empty state graphic & description
│   │   │   │   ├── Input.jsx                  # Form text & date input with label & error text
│   │   │   │   ├── Modal.jsx                  # Centered dialog panel overlay component
│   │   │   │   ├── Select.jsx                 # Dropdown select control component
│   │   │   │   ├── Spinner.jsx                # Animated loading spinner ring component
│   │   │   │   └── Textarea.jsx               # Multi-line text area form control component
│   │   │   ├── LeaveForm.jsx                  # Employee leave request submission form card
│   │   │   ├── LeaveHistoryList.jsx           # Stacked list of employee's personal leave requests
│   │   │   ├── LeaveRejectModal.jsx           # Admin leave rejection confirmation modal dialog
│   │   │   ├── TaskCard.jsx                   # Employee dashboard task card with inline status selector
│   │   │   ├── TaskDeleteModal.jsx            # Admin task deletion confirmation modal dialog
│   │   │   ├── TaskFormModal.jsx              # Admin task creation & editing modal dialog
│   │   │   └── TaskList.jsx                   # Responsive 3-column task grid container
│   │   ├── lib/                               # Client Libraries & Pure Helper Utilities
│   │   │   ├── api.js                         # Axios client instance with cookie credentials & 401 interceptor
│   │   │   └── dateUtils.js                   # Date calculation & relative due date countdown helper
│   │   ├── pages/                             # Route-Level Page Containers
│   │   │   ├── AdminLeavesPage.jsx            # Admin Leave Approval Hub page (/admin/leaves)
│   │   │   ├── AdminTasksPage.jsx             # Admin Task Control Panel table page (/admin/tasks)
│   │   │   ├── DashboardPage.jsx              # Employee task card dashboard page (/dashboard)
│   │   │   ├── LeavesPage.jsx                 # Employee leave portal submission page (/leaves)
│   │   │   ├── LoginPage.jsx                  # User authentication login page (/login)
│   │   │   └── RegisterPage.jsx               # User account registration page (/register)
│   │   ├── store/                             # Global State Management
│   │   │   └── authStore.js                   # Zustand store managing user session, tokens & login/logout
│   │   ├── App.jsx                            # Root application component with React Router route setup
│   │   ├── index.css                          # Global Tailwind CSS design system tokens & base styles
│   │   └── main.jsx                           # Vite DOM entry point mounting React root
│   ├── index.html                             # Single page HTML document entry point
│   ├── package.json                           # Frontend npm dependencies & build scripts
│   └── vite.config.js                         # Vite build tool configuration & dev server setup
│
├── alembic/                                   # Alembic Database Migration Scripts
│   ├── versions/                              # Database schema migration revision files
│   ├── env.py                                 # Alembic environment configuration script
│   └── script.py.mako                         # Migration revision template file
│
├── docs/                                      # Project Documentation & Verification Reports
│   └── test_report.md                         # Automated QA & test suite execution report
│
├── scripts/                                   # Database Seeding & Testing CLI Scripts
│   ├── run_qa_suite.py                        # Automated backend API integration test runner script
│   ├── seed_admin.py                          # CLI script to seed an admin user into the database
│   └── test_endpoints.py                      # Interactive API endpoint test verification script
│
├── tests/                                     # Pytest Backend Automated Test Suite
│   ├── conftest.py                            # Pytest fixtures for async DB sessions & HTTP test clients
│   ├── test_auth.py                           # Tests for registration, login, token refresh & cookies
│   ├── test_leaves.py                         # Tests for leave request submission & admin approvals
│   ├── test_rbac.py                           # Tests for role-based access control enforcement
│   ├── test_services.py                       # Unit tests for backend service layer functions
│   └── test_tasks.py                          # Tests for task CRUD operations & status updates
│
├── .env.example                               # Example environment variables template
├── .gitignore                                 # Git ignore patterns for dependencies & build artifacts
├── alembic.ini                                # Alembic migration configuration settings
├── completed_UI.md                            # Comprehensive frontend & UI architecture documentation
├── Dockerfile                                 # Multi-stage Docker container build definition
├── docker-compose.yml                         # Docker Compose service orchestration file
├── docker-entrypoint.sh                       # Container startup script running migrations & uvicorn
├── postman_collection.json                    # Postman collection for manual API testing
├── PROJECT_DEEP_DIVE.md                       # Full system architecture & backend reference guide
├── PROJECT_STRUCTURE.md                       # Navigation tree & file description guide
├── pyproject.toml                             # Python tool configurations (pytest, ruff, mypy)
├── README.md                                  # Project overview, setup & running instructions
└── requirements.txt                           # Production Python dependencies list
```

---

## Possibly unused or duplicate files

None found.
