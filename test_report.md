# Comprehensive QA Test Report: Employee Task Management System API

**Date of Execution**: July 28, 2026  
**Environment**: Local Backend Server (`http://127.0.0.1:8000`)  
**Test Suite**: `run_qa_suite.py`  
**Execution Results**: 54 Executed | 54 Passed | 0 Failed  

---

## 1. Seeded Dataset Overview (Phase 2)

Before running the full test suite, a realistic corporate environment dataset was seeded into the PostgreSQL database:

### Users (1 Admin + 5 Employees)
- **System Administrator** (`admin@example.com` | Role: `ADMIN` | ID: `1`)
- **Priya Sharma** (`priya.sharma@company.com` | Role: `EMPLOYEE` | ID: `5`)
- **Rohan Verma** (`rohan.verma@company.com` | Role: `EMPLOYEE` | ID: `6`)
- **Sneha Iyer** (`sneha.iyer@company.com` | Role: `EMPLOYEE` | ID: `7`)
- **Arjun Mehta** (`arjun.mehta@company.com` | Role: `EMPLOYEE` | ID: `8`)
- **Kavya Nair** (`kavya.nair@company.com` | Role: `EMPLOYEE` | ID: `9` — *0 tasks assigned for empty-state verification*)

### Tasks Seeded (9 Tasks across 4 Employees)
- **Priya Sharma**:
  - `Task 6`: "Client Presentation Deck" (`HIGH` priority, due `2026-08-01`) → Status: `IN_PROGRESS`
  - `Task 7`: "Quarterly Audit Report" (`LOW` priority, due `2026-08-15`) → Status: `COMPLETED`
  - `Task 8`: "Update Onboarding Docs" (`MEDIUM` priority, due `2026-08-20`) → Status: `PENDING`
- **Rohan Verma**:
  - `Task 9`: "Database Migration Script" (`HIGH` priority, due `2026-08-05`) → Status: `COMPLETED`
  - `Task 10`: "Refactor Auth Middleware" (`LOW` priority, due `2026-08-25`) → Status: `PENDING`
- **Sneha Iyer**:
  - `Task 11`: "API Performance Tuning" (`MEDIUM` priority, due `2026-08-10`) → Status: `IN_PROGRESS`
  - `Task 12`: "Security Patch Update" (`HIGH` priority, due `2026-08-30`) → Status: `PENDING`
- **Arjun Mehta**:
  - `Task 13`: "UI Component Library" (`LOW` priority, due `2026-08-12`) → Status: `IN_PROGRESS`
  - `Task 14`: "Integration Testing" (`MEDIUM` priority, due `2026-08-28`) → Status: `PENDING`
- **Kavya Nair**: `0` tasks assigned.

### Leave Requests Seeded (3 Requests)
- **Priya Sharma**: `Leave 5` — "Annual Vacation" (`2026-09-01` to `2026-09-05`) → Admin Status: `APPROVED` (`reviewed_by`: `1`)
- **Rohan Verma**: `Leave 6` — "Personal Leave" (`2026-08-10` to `2026-08-12`) → Admin Status: `REJECTED` (`reviewed_by`: `1`)
- **Sneha Iyer**: `Leave 7` — "Medical Leave" (`2026-08-15` to `2026-08-18`) → Status: `PENDING`

---

## 2. Test Execution Summary

| Test Category | Total Tests | Passed | Failed | Pass Rate |
| :--- | :---: | :---: | :---: | :---: |
| **Authentication** | 11 | 11 | 0 | 100% |
| **RBAC (Role-Based Access Control)** | 6 | 6 | 0 | 100% |
| **User Profile Management** | 5 | 5 | 0 | 100% |
| **Task Management** | 20 | 20 | 0 | 100% |
| **Leave Management** | 10 | 10 | 0 | 100% |
| **Cross-Cutting & System** | 2 | 2 | 0 | 100% |
| **TOTAL** | **54** | **54** | **0** | **100%** |

---

## 3. Per-Test Execution Detail

### Category 1: Authentication

| Test ID | Endpoint | Method | Role / User | Request Payload | Exp. Status | Act. Status | Result / Response Snippet |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `TC-AUTH-01` | `/auth/register` | `POST` | Public | `{"full_name":"QA Tester","email":"temp.qa.user...","password":"***"}` | 201 | 201 | **PASS**: Created User ID with role `EMPLOYEE`. |
| `TC-AUTH-02` | `/auth/register` | `POST` | Public | `{"email":"priya.sharma@company.com"}` | 400 | 400 | **PASS**: `{"detail":"A user with this email already exists."}` |
| `TC-AUTH-03` | `/auth/register` | `POST` | Public | `{"email":"invalid-email-format"}` | 422 | 422 | **PASS**: FastAPI Validation Error (`value is not a valid email address`). |
| `TC-AUTH-04` | `/auth/register` | `POST` | Public | `{"email":"missing.pass@company.com"}` | 422 | 422 | **PASS**: FastAPI Validation Error (`Field required: password`). |
| `TC-AUTH-05` | `/auth/login` | `POST` | Public | `{"email":"priya.sharma@company.com","password":"***"}` | 200 | 200 | **PASS**: Returned `access_token` and `refresh_token`. |
| `TC-AUTH-06` | `/auth/login` | `POST` | Public | `{"email":"priya.sharma@company.com","password":"wrong"}` | 401 | 401 | **PASS**: `{"detail":"Incorrect email or password."}` |
| `TC-AUTH-07` | `/auth/login` | `POST` | Public | `{"email":"nonexistent@company.com"}` | 401 | 401 | **PASS**: `{"detail":"Incorrect email or password."}` |
| `TC-AUTH-08` | `/auth/refresh` | `POST` | Public | `{"refresh_token":"valid_jwt..."}` | 200 | 200 | **PASS**: Returned new `access_token`. |
| `TC-AUTH-09` | `/auth/refresh` | `POST` | Public | `{"refresh_token":"garbage.token"}` | 401 | 401 | **PASS**: `{"detail":"Invalid refresh token."}` |
| `TC-AUTH-10` | `/users/me` | `GET` | Missing | `None` | 401 | 401 | **PASS**: `{"detail":"Not authenticated"}` |
| `TC-AUTH-11` | `/users/me` | `GET` | Malformed | `Bearer malformed_token` | 401 | 401 | **PASS**: `{"detail":"Invalid access token."}` |

### Category 2: Role-Based Access Control (RBAC)

| Test ID | Endpoint | Method | Role / User | Request Payload | Exp. Status | Act. Status | Result / Response Snippet |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `TC-RBAC-01` | `/tasks/` | `POST` | Employee | `{"title":"Illegal Task", ...}` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |
| `TC-RBAC-02` | `/tasks/6` | `DELETE` | Employee | `None` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |
| `TC-RBAC-03` | `/users/` | `GET` | Employee | `None` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |
| `TC-RBAC-04` | `/leaves/5` | `PATCH` | Employee | `{"status":"APPROVED"}` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |
| `TC-RBAC-05` | `/tasks/` | `POST` | Admin | `{"title":"Admin Valid Task", ...}` | 201 | 201 | **PASS**: Created Task ID. |
| `TC-RBAC-06` | `/users/` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned list of employees. |

### Category 3: User Profile Management

| Test ID | Endpoint | Method | Role / User | Request Payload | Exp. Status | Act. Status | Result / Response Snippet |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `TC-PROF-01` | `/users/me` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned Admin profile (`admin@example.com`). |
| `TC-PROF-02` | `/users/me` | `GET` | Employee | `None` | 200 | 200 | **PASS**: Returned Priya's profile (`priya.sharma@company.com`). |
| `TC-PROF-03` | `/users/me` | `PATCH` | Employee | `{"full_name":"Priya S. Sharma"}` | 200 | 200 | **PASS**: Updated `full_name` to `"Priya S. Sharma"`. |
| `TC-PROF-04` | `/users/` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned array of all employee accounts. |
| `TC-PROF-05` | `/users/` | `GET` | Employee | `None` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |

### Category 4: Task Management

| Test ID | Endpoint | Method | Role / User | Request Payload | Exp. Status | Act. Status | Result / Response Snippet |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `TC-TASK-01` | `/tasks/` | `POST` | Admin | `{"assigned_to":1}` (Admin ID) | 400 | 400 | **PASS**: `{"detail":"Tasks can only be assigned to users with the EMPLOYEE role."}` |
| `TC-TASK-02` | `/tasks/` | `POST` | Admin | `{"assigned_to":99999}` | 404 | 404 | **PASS**: `{"detail":"Assigned user with ID 99999 not found."}` |
| `TC-TASK-03` | `/tasks/` | `POST` | Admin | `{"description":"Incomplete"}` | 422 | 422 | **PASS**: Missing required `title`, `priority`, `due_date`, `assigned_to`. |
| `TC-TASK-04` | `/tasks/` | `POST` | Admin | `{"priority":"CRITICAL"}` | 422 | 422 | **PASS**: `{"msg":"Input should be 'LOW', 'MEDIUM' or 'HIGH'"}` |
| `TC-TASK-05` | `/tasks/` | `POST`/`GET`| Admin | `None` | 200 | 200 | **PASS**: Returned all tasks in backend. |
| `TC-TASK-06` | `/tasks/` | `GET` | Priya | `None` | 200 | 200 | **PASS**: Returned tasks assigned specifically to Priya. |
| `TC-TASK-07` | `/tasks/` | `GET` | Kavya | `None` | 200 | 200 | **PASS**: Returned `[]` empty list (Kavya has zero tasks). |
| `TC-TASK-08` | `/tasks/6` | `GET` | Priya | `None` | 200 | 200 | **PASS**: Returned Task 6 details. |
| `TC-TASK-09` | `/tasks/9` | `GET` | Priya | `None` (Rohan's task) | 403 | 403 | **PASS**: `{"detail":"You are not authorized to view this task."}` |
| `TC-TASK-10` | `/tasks/99999`| `GET` | Admin | `None` | 404 | 404 | **PASS**: `{"detail":"Task with ID 99999 not found."}` |
| `TC-TASK-11` | `/tasks/8` | `PATCH` | Priya | `{"status":"IN_PROGRESS"}` | 200 | 200 | **PASS**: Status successfully updated to `IN_PROGRESS`. |
| `TC-TASK-12` | `/tasks/8` | `PATCH` | Priya | `{"title":"Hacked Title"}` | 403 | 403 | **PASS**: `{"detail":"Employees are only permitted to update the task status."}` |
| `TC-TASK-13` | `/tasks/14` | `DELETE` | Admin | `None` | 204 | 204 | **PASS**: Task deleted (`204 No Content`). |
| `TC-TASK-14` | `/tasks/6` | `DELETE` | Employee | `None` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |
| `TC-TASK-15` | `/tasks/?status=PENDING` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned matching `PENDING` tasks. |
| `TC-TASK-16` | `/tasks/?status=COMPLETED` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned matching `COMPLETED` tasks. |
| `TC-TASK-17` | `/tasks/?priority=HIGH` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned matching `HIGH` priority tasks. |
| `TC-TASK-18` | `/tasks/?sort_by=due_date` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Tasks sorted in ascending `due_date` order. |
| `TC-TASK-19` | `/tasks/?sort_by=invalid_column` | `GET` | Admin | `None` | 400 | 400 | **PASS**: `{"detail":"Invalid sort column: invalid_column"}` |
| `TC-TASK-20` | `/tasks/?skip=0&limit=3` vs `skip=3&limit=3` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Zero overlapping task IDs across paginated subsets. |

### Category 5: Leave Management

| Test ID | Endpoint | Method | Role / User | Request Payload | Exp. Status | Act. Status | Result / Response Snippet |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `TC-LEAV-01` | `/leaves/` | `POST` | Priya | `{"reason":"Conf","start_date":"2026-10-01","end_date":"2026-10-03"}` | 201 | 201 | **PASS**: Leave request created. |
| `TC-LEAV-02` | `/leaves/` | `POST` | Priya | `{"start_date":"2026-10-10","end_date":"2026-10-05"}` | 400 | 400 | **PASS**: `{"detail":"End date cannot be prior to start date."}` |
| `TC-LEAV-03` | `/leaves/` | `POST` | Priya | Missing `reason` | 422 | 422 | **PASS**: Missing required field `reason`. |
| `TC-LEAV-04` | `/leaves/` | `GET` | Admin | `None` | 200 | 200 | **PASS**: Returned all leave requests across all employees. |
| `TC-LEAV-05` | `/leaves/` | `GET` | Priya | `None` | 200 | 200 | **PASS**: Returned only Priya's leave requests. |
| `TC-LEAV-06` | `/leaves/{id}` | `PATCH` | Admin | `{"status":"APPROVED"}` | 200 | 200 | **PASS**: Status set to `APPROVED`, `reviewed_by` set to `1`. |
| `TC-LEAV-07` | `/leaves/{id}` | `PATCH` | Admin | `{"status":"REJECTED"}` | 200 | 200 | **PASS**: Status set to `REJECTED`, `reviewed_by` set to `1`. |
| `TC-LEAV-08` | `/leaves/{id}` | `PATCH` | Employee | `{"status":"APPROVED"}` | 403 | 403 | **PASS**: `{"detail":"Action requires ADMIN role."}` |
| `TC-LEAV-09` | `/leaves/99999`| `PATCH` | Admin | `{"status":"APPROVED"}` | 404 | 404 | **PASS**: `{"detail":"Leave request with ID 99999 not found."}` |
| `TC-LEAV-10` | `/leaves/{id}` | `PATCH` | Admin | `{"status":"APPROVED"}` | 400 | 400 | **PASS (FIXED)**: `{"detail":"This leave request has already been reviewed and cannot be modified."}` |

### Category 6: Cross-Cutting & System

| Test ID | Endpoint | Method | Role / User | Request Payload | Exp. Status | Act. Status | Result / Response Snippet |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `TC-CROSS-01` | `/` | `GET` | Public | `None` | 200 | 200 | **PASS**: `{"message":"Welcome...","docs_url":"/docs"}` |
| `TC-CROSS-02` | `/invalid-route-xyz` | `GET` | Public | `None` | 404 | 404 | **PASS**: `{"detail":"Not Found"}` |

---

## 4. Business Logic & Quality Findings

> [!NOTE]
> ### RESOLVED: Double-Review / Re-review Protected on Processed Leave Requests (`TC-LEAV-10`)
> **Resolution Status**: FIXED & VERIFIED  
> **Location**: `app/services/leave_service.py` (`review_leave_request`)  
> **Fix Implemented**:
> ```python
> # Validation: leave request must be in PENDING status
> if db_leave.status != LeaveStatus.PENDING:
>     raise BadRequestException("This leave request has already been reviewed and cannot be modified.")
> ```
> **Verification Result**: Attempting to re-review an already reviewed leave request now properly returns HTTP `400 Bad Request` with detail `"This leave request has already been reviewed and cannot be modified."`
