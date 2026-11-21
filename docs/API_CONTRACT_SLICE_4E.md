# API Contract: Slice 4e (Employee Invite Flow & Self-Serve Password Reset)

> **Generated from Live Code & OpenAPI Spec**: Generated directly from FastAPI's `app.openapi()` schema and Pydantic model definitions (`app/schemas/user.py`, `app/models/user.py`, `app/routes/users.py`, `app/routes/auth.py`).

---

## 1. Schema Truth & Explicit Field Confirmations

### `EmployeeCreate` Request Schema
- **Exact Fields**:
  - `full_name`: `string` (Required)
  - `email`: `string` (`EmailStr`, Required, normalized to lowercase)
  - `reports_to_id`: `integer | null` (Optional, default: `null`)
  - `designation`: `string | null` (Optional, default: `null`)
  - `access_level`: `integer | null` (Optional, default: `3`)
- **Explicit Field Confirmations**:
  - `phone`: **DOES NOT EXIST** in `EmployeeCreate`.
  - `department`: **DOES NOT EXIST** in `EmployeeCreate`.
  - `role`: **DOES NOT EXIST** in `EmployeeCreate`.

### `UserRole` Enum Values
- **Real Values**: `["ADMIN", "EMPLOYEE"]`
- There is **no `SUPERVISOR` enum value**.

### How `access_level` Maps to Role & Tier
- When created via `POST /users/employees`, the database row is saved with `role = UserRole.EMPLOYEE` and `access_level = employee_in.access_level or 3`.
- `effective_tier` is dynamically computed by `permission_service.py`:
  - **Tier 1 (Admin)**: `user.role == UserRole.ADMIN` OR `user.access_level == 1`
  - **Tier 2 (Supervisor)**: `user.access_level == 2` OR user has active direct reports (`direct_reports_ids` not empty)
  - **Tier 3 (Employee)**: `user.access_level == 3` (default) without direct reports

### What is Returned for `employee_code`
- **Format**: Real, cryptographically random 10-digit numeric string (`"1000000000"` to `"9999999999"`).
- **Generation Logic** (`app/services/user_service.py`):
  ```python
  while True:
      emp_code = f"{secrets.randbelow(9000000000) + 1000000000:010d}"
      exists = await db.execute(select(User.id).where(User.employee_code == emp_code))
      if exists.scalar_one_or_none() is None:
          break
  ```
- Guaranteed unique with collision retry in the database; **never derived from the user ID**.

---

## 2. Endpoints Specification

### 1. `POST /users/employees`
- **Summary**: Invite a new employee account. Accessible by Tier 1 (Admin) only.
- **Security**: Bearer Token (`OAuth2PasswordBearer`, requires `access_level == 1`)
- **Rate Limit**: Per-admin limit: 30 invitations / hour (`INVITE_RATE_LIMIT_PER_ADMIN=30`, window `INVITE_RATE_LIMIT_WINDOW_SECONDS=3600`).
- **Request Body** (`application/json`):
  ```json
  {
    "full_name": "string",
    "email": "user@example.com",
    "reports_to_id": null,
    "designation": null,
    "access_level": 3
  }
  ```
- **Responses**:
  - **201 Created** (`EmployeeCreateResponse`):
    ```json
    {
      "id": 1,
      "full_name": "string",
      "email": "user@example.com",
      "employee_code": "1000000042",
      "role": "EMPLOYEE",
      "access_level": 3,
      "reports_to_id": null,
      "designation": null,
      "is_active": true,
      "is_email_verified": false,
      "email_verified_at": null,
      "created_at": "2026-11-21T18:00:00Z",
      "delivery_queued": true,
      "invitation_status": "PENDING"
    }
    ```
  - **400 Bad Request**: Invalid manager, cycle detected, or organization limit reached.
  - **401 Unauthorized**: Missing or invalid access token.
  - **403 Forbidden**: Insufficient privileges (not Tier 1 admin).
  - **409 Conflict**: Email already registered.
  - **429 Too Many Requests**: Admin invitation rate limit exceeded (`"Too many invitations sent."`).

---

### 2. `POST /users/{user_id}/resend-invite`
- **Summary**: Resends an invitation link to a pending employee.
- **Security**: Bearer Token (Tier 1 Admin only).
- **Rate Limits**:
  - Per target user: 3 resends / hour (`RESEND_INVITE_PER_USER_LIMIT=3`, key: `resend_invite:user:{user_id}`).
  - Per admin: 30 resends / hour (`RESEND_INVITE_PER_ADMIN_LIMIT=30`, key: `resend_invite:admin:{admin_id}`).
- **Path Parameters**:
  - `user_id`: `integer` (Target user ID).
- **Responses**:
  - **200 OK** (`ResendInviteResponse`):
    ```json
    {
      "message": "Invitation resent.",
      "delivery_queued": true
    }
    ```
  - **400 Bad Request**: User is not in `PENDING` state (e.g. already `ACTIVE` or `REVOKED`).
  - **404 Not Found**: User does not exist or belongs to another organization.
  - **429 Too Many Requests**: User or admin rate limit exceeded.

---

### 3. `POST /users/{user_id}/revoke-invite`
- **Summary**: Revokes a pending employee invitation.
- **Security**: Bearer Token (Tier 1 Admin only).
- **Path Parameters**:
  - `user_id`: `integer` (Target user ID).
- **Responses**:
  - **200 OK** (`RevokeInviteResponse`):
    ```json
    {
      "message": "Invitation revoked."
    }
    ```
  - **400 Bad Request**: User is not in `PENDING` state.
  - **404 Not Found**: User not found or cross-org.

---

### 4. `POST /users/{user_id}/send-password-reset`
- **Summary**: Admin triggers a password reset email for an active employee.
- **Security**: Bearer Token (Tier 1 Admin only).
- **Rate Limits**:
  - Per target user: 5 resets / hour (`SEND_RESET_PER_USER_LIMIT=5`, key: `send_reset:user:{user_id}`).
  - Per admin: 50 resets / hour (`SEND_RESET_PER_ADMIN_LIMIT=50`, key: `send_reset:admin:{admin_id}`).
- **Path Parameters**:
  - `user_id`: `integer` (Target user ID).
- **Responses**:
  - **200 OK** (`SendPasswordResetResponse`):
    ```json
    {
      "message": "Password reset link sent.",
      "delivery_queued": true
    }
    ```
  - **400 Bad Request**: User is not `ACTIVE` (e.g. `PENDING` or `REVOKED`) or is deactivated.
  - **404 Not Found**: User not found or cross-org.
  - **429 Too Many Requests**: Target user or admin rate limit exceeded.

---

### 5. `POST /auth/accept-invite`
- **Summary**: Public endpoint for invited employees to activate their account and choose a password.
- **Security**: None (Public).
- **Rate Limit**: Per-IP ceiling: 10 attempts / 15 min (`ACCEPT_INVITE_IP_LIMIT=10`, window `ACCEPT_INVITE_IP_WINDOW=900`).
- **Request Body** (`AcceptInviteRequest`):
  ```json
  {
    "token": "raw_urlsafe_invite_token",
    "password": "StrongPassword123!"
  }
  ```
- **Responses**:
  - **200 OK** (`AcceptInviteResponse`):
    ```json
    {
      "message": "Account activated. You may now log in."
    }
    ```
  - **400 Bad Request**:
    - Invalid, expired, reused, or revoked token.
    - Password does not meet security requirements (weak password leaves token unconsumed).
  - **429 Too Many Requests**: IP rate limit exceeded (`Retry-After` header included).

---

### 6. `POST /auth/forgot-password`
- **Summary**: Public self-serve forgot password request with strict anti-enumeration.
- **Security**: None (Public).
- **Rate Limits**:
  - Compound `{IP, email}`: 3 requests / 15 min (`FORGOT_PASSWORD_COMPOUND_LIMIT=3`, window `FORGOT_PASSWORD_COMPOUND_WINDOW=900`).
  - Per-IP ceiling: 20 requests / 15 min (`FORGOT_PASSWORD_IP_LIMIT=20`, window `FORGOT_PASSWORD_IP_WINDOW=900`).
- **Request Body** (`ForgotPasswordRequest`):
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Responses**:
  - **200 OK** (`ForgotPasswordResponse`):
    ```json
    {
      "message": "If an account with that email exists, a password reset link has been sent."
    }
    ```
    *Note: Returns identical 200 OK response and constant timing for existing, non-existent, pending, revoked, and deactivated emails.*
  - **429 Too Many Requests**: Rate limit exceeded.

---

### 7. `POST /auth/reset-password`
- **Summary**: Public endpoint to consume a password reset token and update password.
- **Security**: None (Public).
- **Rate Limit**: Per-IP ceiling: 10 attempts / 15 min (`RESET_PASSWORD_IP_LIMIT=10`, window `RESET_PASSWORD_IP_WINDOW=900`).
- **Request Body** (`ResetPasswordRequest`):
  ```json
  {
    "token": "raw_urlsafe_reset_token",
    "new_password": "NewStrongPassword123!"
  }
  ```
- **Responses**:
  - **200 OK** (`ResetPasswordResponse`):
    ```json
    {
      "message": "Password has been reset. Please log in."
    }
    ```
  - **400 Bad Request**:
    - Invalid, expired, or reused token.
    - Password does not meet strength requirements (weak password leaves token unconsumed).
  - **429 Too Many Requests**: IP rate limit exceeded.

---

### 8. `GET /users/` (List Employees) & `GET /users/me` (Current User Profile)
- **Summary**: Returns user profiles with all Slice 4e fields.
- **Security**: Bearer Token.
- **Responses**:
  - **200 OK** (`UserRead` or `array[UserRead]`):
    ```json
    {
      "id": 1,
      "email": "user@example.com",
      "full_name": "Jane Doe",
      "role": "EMPLOYEE",
      "access_level": 3,
      "effective_tier": 3,
      "direct_reports_ids": [],
      "reports_to_id": null,
      "designation": "Software Engineer",
      "employee_code": "1000000042",
      "is_email_verified": true,
      "email_verified_at": "2026-11-21T18:00:00Z",
      "must_change_password": false,
      "is_active": true,
      "created_at": "2026-11-21T17:00:00Z",
      "invitation_status": "ACTIVE"
    }
    ```
    - `invitation_status`: `"PENDING"` | `"ACTIVE"` | `"REVOKED"`
    - `effective_tier`: `1` (Admin) | `2` (Supervisor) | `3` (Employee)

---

## 3. Session Invalidation Lifecycle (`POST /auth/change-password`)

- **Endpoint**: `POST /auth/change-password`
- **Request Body**: `{"current_password": "...", "new_password": "..."}`
- **Response**: `UserRead` (HTTP 200 OK with `must_change_password: false`).
- **Session Effect**:
  - Does **NOT** return new tokens.
  - Updates `users.tokens_valid_after = datetime.now(UTC).replace(microsecond=0)`.
  - All existing access tokens and refresh tokens issued prior to or during that second are invalidated.
  - Subsequent requests with the old access token return `HTTP 401 Unauthorized: Token has been revoked.`.
  - **Frontend Requirement**: The frontend must clear stored tokens and redirect the user to log in again with the newly set password.
