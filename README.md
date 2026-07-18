# Employee Task Management System (Backend-Only)

A backend-only Employee Task Management System built in Python using FastAPI, SQLAlchemy, Alembic, and PostgreSQL. This project showcases clean, modular architecture, JWT-based Authentication (Access + Refresh tokens), Role-Based Access Control (RBAC), and database migration workflows.

---

## Folder Structure & Module Descriptions

```
app/
├── main.py                # FastAPI app entrypoint, registers routes, configures CORS, and defines centralized exception handling
├── core/
│   ├── config.py          # Configuration management loading variables from .env via Pydantic BaseSettings
│   ├── security.py        # Token operations (signing, validation, dependencies for auth) and password hashing
│   └── exceptions.py      # Custom domain exceptions for cleaner business error propagation
├── db/
│   ├── base.py            # SQLAlchemy Base configuration, database engine, and SessionLocal setup
│   └── session.py         # get_db() FastAPI dependency yielding database sessions
├── models/
│   ├── user.py            # User DB Model (roles: ADMIN, EMPLOYEE)
│   ├── task.py            # Task DB Model (status, priority, assignment relationships)
│   └── leave.py           # LeaveRequest DB Model (approval status, reviewer relationship)
├── schemas/
│   ├── user.py            # Pydantic validation schemas for authentication, token payload, and user profiles
│   ├── task.py            # Pydantic validation schemas for task inputs, status updates, and responses
│   └── leave.py           # Pydantic validation schemas for leave request creations and status approvals
├── routes/
│   ├── auth.py            # Registration, login, and refresh token endpoints
│   ├── users.py           # User profiles (me, list employees)
│   ├── tasks.py           # Task CRUD operations with filters, pagination, and sorting
│   └── leaves.py          # Leave request submission and Admin approvals
└── services/              # Thin business logic layer executing database actions
    ├── auth_service.py    # Registers users, authenticates passwords, and refreshes tokens
    ├── task_service.py    # CRUD task business logic and ownership constraints
    └── leave_service.py   # Submits leaves and executes Admin approvals
alembic/                   # Database migrations configuration and history versions
```

---

## Setup Instructions

### 1. Prerequisites
- Python 3.12+ (Python 3.11 is also supported)
- PostgreSQL database server running locally or accessible remotely.

### 2. Installation
1. Clone this repository to your local machine.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install the application dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment variables template and configure the variables:
   ```bash
   cp .env.example .env
   ```
   *Note: Open `.env` and fill in your PostgreSQL server password and other settings. The database `employee_task_db` will need to be created in your PostgreSQL server first.*

---

## Database Migrations
Database table creations and schema changes are handled via Alembic.

1. **Verify your `.env` connection string**: Ensure `DATABASE_URL` is correct.
2. **Apply migrations**: Run the following command to create the database schema:
   ```bash
   alembic upgrade head
   ```

To generate future migrations after updating models:
```bash
alembic revision --autogenerate -m "description of changes"
alembic upgrade head
```

---

## Administrative Seed Script
Because open registration only creates users with the `EMPLOYEE` role, an administrative user must be created using the seeding utility.

Run the following command to seed an initial `ADMIN` user. You can pass environment variables or enter values interactively when prompted:
```bash
# Interactive mode:
python seed_admin.py

# Non-interactive mode (environment variables):
# Windows (PowerShell):
$env:ADMIN_EMAIL="admin@example.com"; $env:ADMIN_PASSWORD="adminpassword123"; python seed_admin.py
# macOS/Linux:
ADMIN_EMAIL="admin@example.com" ADMIN_PASSWORD="adminpassword123" python seed_admin.py
```

---

## Running the Server
Start the development server using Uvicorn:
```bash
uvicorn app.main:app --reload
```
Once running, the interactive Swagger documentation is available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Testing & Verification

### 1. Integration Test Script
A pre-configured verification script is available in the root folder. With the server running at `http://127.0.0.1:8000`, execute the following to test all endpoints, RBAC checks, and status flows end-to-end:
```bash
python test_endpoints.py
```

### 2. Postman Collection
Import the pre-configured [postman_collection.json](file:///c:/Users/ankus/Desktop/Employee%20Task%20Management/postman_collection.json) in Postman.
- **Environment variables**: The collection includes environment-level variables `{{access_token}}` and `{{refresh_token}}`.
- **Automatic Token Saving**: A post-response test script on the `/auth/login` and `/auth/refresh` endpoints automatically saves active tokens into variables so subsequent requests execute seamlessly.
