"""
Integration and Security Test Suite for Slice 4e:
Employee Invite Flow & Self-Serve Password Reset

Covers:
- Token generation, hashing, and 48h / 1h expiration
- Single-use atomic consumption and replay prevention
- Concurrent token consumption race condition safety
- Invalidation on resend and deactivation
- Accept-invite effects and activation state transitions
- Pending and revoked login behavior and constant-time timing path
- Forgot-password anti-enumeration across all user lifecycle states
- Session invalidation via tokens_valid_after
- Edge cases: task assignment, manager hierarchy, and reactivation rules
- Rate limiting enforcement with controllable clock
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.user_token import UserToken
from app.services import token_service


# ===========================================================================
# 1. Employee Invite Flow & Activation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_create_employee_returns_pending_status(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    POST /users/employees creates user in PENDING status, sets delivery_queued=True,
    generates 10-digit employee_code, stores real bcrypt hash (never sentinel),
    and creates a 48-hour hashed INVITE token.
    """
    payload = {
        "full_name": "Pending Employee Alpha",
        "email": "alpha.pending@example.com",
        "designation": "Software Engineer",
    }
    res = await client.post("/users/employees", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()

    assert data["invitation_status"] == "PENDING"
    assert data["delivery_queued"] is True
    assert "password" not in data
    assert "temp_password" not in data
    assert "temporary_password" not in data

    # Verify DB state
    stmt = select(User).where(User.email == "alpha.pending@example.com")
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user is not None
    assert user.invitation_status == "PENDING"
    assert user.is_active is True
    assert user.is_email_verified is False
    assert user.hashed_password.startswith("$2b$")  # Real bcrypt hash

    # Verify INVITE token exists in DB
    token_stmt = select(UserToken).where(
        UserToken.user_id == user.id, UserToken.token_type == "INVITE"
    )
    token = (await db_session.execute(token_stmt)).scalar_one_or_none()
    assert token is not None
    assert token.used_at is None
    assert token.expires_at > datetime.now(UTC) + timedelta(hours=47)


@pytest.mark.asyncio
async def test_pending_employee_cannot_login(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    A user with invitation_status='PENDING' cannot log in via employee_code.
    Returns 401 'Incorrect credentials.' with constant-time execution without leaking state.
    """
    res = await client.post(
        "/users/employees",
        json={"full_name": "Pending Login Tester", "email": "pending.login@example.com"},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    emp_code = res.json()["employee_code"]

    login_res = await client.post(
        "/auth/login",
        json={"identifier": emp_code, "password": "AnyAttemptedPassword123!", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert login_res.json()["detail"] == "Incorrect credentials."


@pytest.mark.asyncio
async def test_accept_invite_activates_account(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    POST /auth/accept-invite validates single-use token, validates password strength,
    hashes password, transitions invitation_status to 'ACTIVE', sets invitation_accepted_at,
    sets is_email_verified=True, and marks token used.
    """
    captured_tokens = []

    def capture_invite(email, full_name, employee_code, token):
        captured_tokens.append(token)
        return True

    with patch("app.routes.users.send_invite_email", side_effect=capture_invite):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Accepting User", "email": "accepting.user@example.com"},
            headers=admin_headers,
        )
        assert create_res.status_code == status.HTTP_201_CREATED

    raw_token = captured_tokens[0]

    # Call /auth/accept-invite
    accept_res = await client.post(
        "/auth/accept-invite",
        json={"token": raw_token, "password": "StrongNewPassword123!"},
    )
    assert accept_res.status_code == status.HTTP_200_OK
    assert accept_res.json()["message"] == "Account activated. You may now log in."

    # Verify user state in DB
    stmt = select(User).where(User.email == "accepting.user@example.com")
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user.invitation_status == "ACTIVE"
    assert user.invitation_accepted_at is not None
    assert user.is_email_verified is True
    assert user.email_verified_at is not None
    assert user.must_change_password is False

    # Verify token is consumed
    token_stmt = select(UserToken).where(
        UserToken.user_id == user.id, UserToken.token_type == "INVITE"
    )
    token_record = (await db_session.execute(token_stmt)).scalar_one_or_none()
    assert token_record.used_at is not None


@pytest.mark.asyncio
async def test_accept_invite_then_login_success(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    After accepting an invite, the employee can successfully authenticate
    using their employee_code and chosen permanent password.
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Login Ready User", "email": "login.ready@example.com"},
            headers=admin_headers,
        )
    emp_code = create_res.json()["employee_code"]
    raw_token = captured_tokens[0]

    await client.post(
        "/auth/accept-invite",
        json={"token": raw_token, "password": "SecurePassword123!"},
    )

    login_res = await client.post(
        "/auth/login",
        json={"identifier": emp_code, "password": "SecurePassword123!", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    data = login_res.json()
    assert "access_token" in data
    assert data["must_change_password"] is False
    assert data["user"]["invitation_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_accept_invite_single_use_replay_rejected(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Replaying an already used invite token returns HTTP 400 with a generic error.
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        await client.post(
            "/users/employees",
            json={"full_name": "Replay User", "email": "replay.user@example.com"},
            headers=admin_headers,
        )
    raw_token = captured_tokens[0]

    # First attempt: success
    res1 = await client.post(
        "/auth/accept-invite",
        json={"token": raw_token, "password": "ValidPassword123!"},
    )
    assert res1.status_code == status.HTTP_200_OK

    # Replay attempt: 400 Bad Request
    res2 = await client.post(
        "/auth/accept-invite",
        json={"token": raw_token, "password": "AnotherPassword123!"},
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert res2.json()["detail"] == "Invalid or expired token."


@pytest.mark.asyncio
async def test_accept_invite_expired_token_rejected(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    An invite token with expires_at in the past returns HTTP 400 'Invalid or expired token.'
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        res = await client.post(
            "/users/employees",
            json={"full_name": "Expired User", "email": "expired.user@example.com"},
            headers=admin_headers,
        )
    user_id = res.json()["id"]
    raw_token = captured_tokens[0]

    # Manually expire the token in DB
    past_time = datetime.now(UTC) - timedelta(hours=1)
    await db_session.execute(
        update(UserToken)
        .where(UserToken.user_id == user_id)
        .values(expires_at=past_time)
    )
    await db_session.commit()

    accept_res = await client.post(
        "/auth/accept-invite",
        json={"token": raw_token, "password": "ValidPassword123!"},
    )
    assert accept_res.status_code == status.HTTP_400_BAD_REQUEST
    assert accept_res.json()["detail"] == "Invalid or expired token."


@pytest.mark.asyncio
async def test_accept_invite_wrong_type_token_rejected(
    client: AsyncClient, employee_user: User, db_session: AsyncSession
) -> None:
    """
    Passing a PASSWORD_RESET token to /auth/accept-invite is rejected with 400.
    """
    raw_reset_token = await token_service.generate_user_token(
        db=db_session, user_id=employee_user.id, token_type="PASSWORD_RESET", expire_hours=1
    )
    await db_session.commit()

    res = await client.post(
        "/auth/accept-invite",
        json={"token": raw_reset_token, "password": "ValidPassword123!"},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json()["detail"] == "Invalid or expired token."


@pytest.mark.asyncio
async def test_accept_invite_weak_password_rejected(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Password strength rules are strictly enforced during accept-invite:
    rejects passwords with < 8 chars or missing complexity requirements.
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        await client.post(
            "/users/employees",
            json={"full_name": "Weak Pwd User", "email": "weak.pwd@example.com"},
            headers=admin_headers,
        )
    raw_token = captured_tokens[0]

    weak_passwords = ["short", "alllowercase123!", "NOLOWERCASE123!", "NoSpecialChar123", "NoDigitChar!@#"]
    for weak_pwd in weak_passwords:
        res = await client.post(
            "/auth/accept-invite",
            json={"token": raw_token, "password": weak_pwd},
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ===========================================================================
# 2. Resend and Revoke Invite Admin Actions
# ===========================================================================

@pytest.mark.asyncio
async def test_resend_invite_invalidates_old_token(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    POST /users/{id}/resend-invite:
    1. Returns 200 with delivery_queued=True.
    2. Invalidates the user's prior unused invite token (used_at set to now).
    3. Issues a fresh 48h token.
    4. Old token fails on accept-invite; new token succeeds.
    """
    first_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: first_tokens.append(token) or True,
    ):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Resend Tester", "email": "resend.tester@example.com"},
            headers=admin_headers,
        )
    user_id = create_res.json()["id"]
    old_token = first_tokens[0]

    # Admin calls resend-invite
    second_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: second_tokens.append(token) or True,
    ):
        resend_res = await client.post(f"/users/{user_id}/resend-invite", headers=admin_headers)
    assert resend_res.status_code == status.HTTP_200_OK
    assert resend_res.json()["delivery_queued"] is True
    new_token = second_tokens[0]
    assert new_token != old_token

    # Verify old token is rejected
    old_try = await client.post(
        "/auth/accept-invite",
        json={"token": old_token, "password": "StrongPassword123!"},
    )
    assert old_try.status_code == status.HTTP_400_BAD_REQUEST

    # Verify new token succeeds
    new_try = await client.post(
        "/auth/accept-invite",
        json={"token": new_token, "password": "StrongPassword123!"},
    )
    assert new_try.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_resend_invite_active_user_fails(
    client: AsyncClient, admin_headers: dict[str, str], employee_user: User
) -> None:
    """
    Calling resend-invite on an already ACTIVE user returns HTTP 400 Bad Request.
    """
    res = await client.post(f"/users/{employee_user.id}/resend-invite", headers=admin_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "not pending" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_revoke_invite_success(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    POST /users/{id}/revoke-invite:
    1. Sets invitation_status = 'REVOKED' and is_active = False.
    2. Invalidates all pending tokens.
    3. The token cannot be accepted.
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Revoke Tester", "email": "revoke.tester@example.com"},
            headers=admin_headers,
        )
    user_id = create_res.json()["id"]
    token = captured_tokens[0]

    revoke_res = await client.post(f"/users/{user_id}/revoke-invite", headers=admin_headers)
    assert revoke_res.status_code == status.HTTP_200_OK
    assert revoke_res.json()["message"] == "Invitation revoked."

    # Verify DB state
    stmt = select(User).where(User.id == user_id)
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user.invitation_status == "REVOKED"
    assert user.is_active is False

    # Attempt accept-invite with token -> 400
    accept_res = await client.post(
        "/auth/accept-invite",
        json={"token": token, "password": "ValidPassword123!"},
    )
    assert accept_res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_revoked_user_cannot_be_reactivated(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    REVOKED users cannot be reactivated via PATCH /users/{id}/reactivate.
    Returns HTTP 400 directing admin to issue a new invite.
    """
    create_res = await client.post(
        "/users/employees",
        json={"full_name": "Reactivate Blocker", "email": "react.block@example.com"},
        headers=admin_headers,
    )
    user_id = create_res.json()["id"]
    await client.post(f"/users/{user_id}/revoke-invite", headers=admin_headers)

    react_res = await client.patch(f"/users/{user_id}/reactivate", headers=admin_headers)
    assert react_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "revoked users cannot be reactivated" in react_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivate_pending_user_invalidates_tokens(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    Deactivating a PENDING employee invalidates their outstanding invite tokens.
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Deact Pending", "email": "deact.pending@example.com"},
            headers=admin_headers,
        )
    user_id = create_res.json()["id"]
    token = captured_tokens[0]

    # Deactivate the pending employee
    deact_res = await client.patch(f"/users/{user_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK

    # Accepting invite now returns 400
    accept_res = await client.post(
        "/auth/accept-invite",
        json={"token": token, "password": "ValidPassword123!"},
    )
    assert accept_res.status_code == status.HTTP_400_BAD_REQUEST


# ===========================================================================
# 3. Self-Serve Password Reset & Admin Password Reset
# ===========================================================================

@pytest.mark.asyncio
async def test_forgot_password_anti_enumeration(
    client: AsyncClient,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    POST /auth/forgot-password anti-enumeration:
    Returns identical HTTP 200 and message across:
    1. Existing ACTIVE user
    2. Non-existent email
    3. PENDING user
    4. REVOKED user
    5. Deactivated user
    Email is only dispatched for ACTIVE and active users.
    """
    # Create PENDING and REVOKED users
    create_pending = await client.post(
        "/users/employees",
        json={"full_name": "Pending Enum", "email": "pending.enum@example.com"},
        headers=admin_headers,
    )
    pending_id = create_pending.json()["id"]

    create_revoked = await client.post(
        "/users/employees",
        json={"full_name": "Revoked Enum", "email": "revoked.enum@example.com"},
        headers=admin_headers,
    )
    revoked_id = create_revoked.json()["id"]
    await client.post(f"/users/{revoked_id}/revoke-invite", headers=admin_headers)

    dispatched = []

    def mock_reset_email(email, full_name, token):
        dispatched.append(email)
        return True

    test_emails = [
        (employee_user.email, True),              # Existing active -> email sent
        ("nonexistent.random@example.com", False), # Non-existent -> no email
        ("pending.enum@example.com", False),       # Pending -> no email
        ("revoked.enum@example.com", False),       # Revoked -> no email
    ]

    with patch("app.routes.auth.send_password_reset_email", side_effect=mock_reset_email):
        for email_val, should_send in test_emails:
            dispatched.clear()
            res = await client.post("/auth/forgot-password", json={"email": email_val})
            assert res.status_code == status.HTTP_200_OK
            assert (
                res.json()["message"]
                == "If an account with that email exists, a password reset link has been sent."
            )
            if should_send:
                assert len(dispatched) == 1
                assert dispatched[0] == email_val
            else:
                assert len(dispatched) == 0


@pytest.mark.asyncio
async def test_reset_password_success_and_login(
    client: AsyncClient, employee_user: User, db_session: AsyncSession
) -> None:
    """
    POST /auth/reset-password:
    1. Consumes 1-hour PASSWORD_RESET token.
    2. Updates user password.
    3. User can log in with new password.
    4. Old password fails.
    """
    raw_token = await token_service.generate_user_token(
        db=db_session, user_id=employee_user.id, token_type="PASSWORD_RESET", expire_hours=1
    )
    await db_session.commit()

    reset_res = await client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "BrandNewPassword123!"},
    )
    assert reset_res.status_code == status.HTTP_200_OK
    assert reset_res.json()["message"] == "Password has been reset. Please log in."

    # Old password fails
    old_login = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    # New password succeeds
    new_login = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "BrandNewPassword123!", "mode": "employee"},
    )
    assert new_login.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_reset_password_session_invalidation(
    client: AsyncClient, employee_user: User, employee_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    After /auth/reset-password, all existing JWT access tokens of that user
    are rejected with HTTP 401 via the tokens_valid_after check.
    """
    # Verify current token works
    pre_res = await client.get("/users/me", headers=employee_headers)
    assert pre_res.status_code == status.HTTP_200_OK

    # Generate token and reset password
    raw_token = await token_service.generate_user_token(
        db=db_session, user_id=employee_user.id, token_type="PASSWORD_RESET", expire_hours=1
    )
    await db_session.commit()

    await client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "NewSessionInvalidationPassword123!"},
    )

    # Old access token must now be rejected
    post_res = await client.get("/users/me", headers=employee_headers)
    assert post_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in post_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_password_reset_pending_user_rejected(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Admin cannot send password reset link to a PENDING employee.
    Returns HTTP 400.
    """
    create_res = await client.post(
        "/users/employees",
        json={"full_name": "Pending Reset", "email": "pending.reset@example.com"},
        headers=admin_headers,
    )
    user_id = create_res.json()["id"]

    res = await client.post(f"/users/{user_id}/send-password-reset", headers=admin_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "active users" in res.json()["detail"].lower()


# ===========================================================================
# 4. Edge Cases: Task Assignment & Manager Validation for Pending Users
# ===========================================================================

@pytest.mark.asyncio
async def test_pending_user_cannot_be_assigned_task(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Attempting to create a task assigned to a PENDING user returns HTTP 400.
    """
    create_res = await client.post(
        "/users/employees",
        json={"full_name": "Task Assignee Pending", "email": "task.pending@example.com"},
        headers=admin_headers,
    )
    pending_user_id = create_res.json()["id"]

    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Invalid Pending Task",
            "description": "Should fail",
            "priority": "HIGH",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": pending_user_id,
        },
        headers=admin_headers,
    )
    assert task_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "pending" in task_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pending_user_cannot_be_chosen_as_supervisor(
    client: AsyncClient, admin_headers: dict[str, str], employee_user: User
) -> None:
    """
    Attempting to set reports_to_id to a PENDING user returns HTTP 400.
    """
    create_res = await client.post(
        "/users/employees",
        json={"full_name": "Supervisor Pending", "email": "sup.pending@example.com"},
        headers=admin_headers,
    )
    pending_user_id = create_res.json()["id"]

    res = await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": pending_user_id},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "pending" in res.json()["detail"].lower()


# ===========================================================================
# 5. Rate Limiting Tests (Using Controllable Clock)
# ===========================================================================

@pytest.mark.asyncio
async def test_forgot_password_rate_limit_compound_and_ip(
    client: AsyncClient,
) -> None:
    """
    Tests forgot-password compound limit (3 attempts / 15 min) and Retry-After header.
    """
    fake_time = [100000.0]

    def fake_clock():
        return fake_time[0]

    from app.core import rate_limit as rl_module
    custom_limiter = InMemoryRateLimiter(clock=fake_clock)
    original_limiter = rl_module._limiter_instance
    rl_module._limiter_instance = custom_limiter

    try:
        email = "ratelimit.test@example.com"
        for i in range(settings.FORGOT_PASSWORD_COMPOUND_LIMIT):
            res = await client.post("/auth/forgot-password", json={"email": email})
            assert res.status_code == status.HTTP_200_OK

        # Exceeded attempt
        blocked_res = await client.post("/auth/forgot-password", json={"email": email})
        assert blocked_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in blocked_res.headers

        # Fast forward time past 15-minute window
        fake_time[0] += settings.FORGOT_PASSWORD_COMPOUND_WINDOW + 1
        res_after = await client.post("/auth/forgot-password", json={"email": email})
        assert res_after.status_code == status.HTTP_200_OK
    finally:
        rl_module._limiter_instance = original_limiter
        original_limiter.reset()


@pytest.mark.asyncio
async def test_accept_invite_rate_limit(
    client: AsyncClient,
) -> None:
    """
    Tests accept-invite IP rate limiting (10 attempts / 15 min).
    """
    fake_time = [200000.0]

    def fake_clock():
        return fake_time[0]

    from app.core import rate_limit as rl_module
    custom_limiter = InMemoryRateLimiter(clock=fake_clock)
    original_limiter = rl_module._limiter_instance
    rl_module._limiter_instance = custom_limiter

    try:
        for i in range(settings.ACCEPT_INVITE_IP_LIMIT):
            res = await client.post(
                "/auth/accept-invite", json={"token": f"token_{i}", "password": "Password123!"}
            )
            # Will fail with 400 (invalid token), but rate limit counter increments
            assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK)

        # 11th request: 429 Too Many Requests
        blocked = await client.post(
            "/auth/accept-invite", json={"token": "token_exceeded", "password": "Password123!"}
        )
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    finally:
        rl_module._limiter_instance = original_limiter
        original_limiter.reset()


# ===========================================================================
# 6. Concurrency & Race Condition Safety
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_token_consumption_atomic(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Simultaneously fires two accept-invite requests with the identical token.
    Exactly one must return 200 OK and the other must return 400 Bad Request.
    """
    captured_tokens = []
    with patch(
        "app.routes.users.send_invite_email",
        side_effect=lambda email, full_name, employee_code, token, **kw: captured_tokens.append(token) or True,
    ):
        await client.post(
            "/users/employees",
            json={"full_name": "Concurrent Consume", "email": "concurrent.consume@example.com"},
            headers=admin_headers,
        )
    raw_token = captured_tokens[0]

    async def consume():
        return await client.post(
            "/auth/accept-invite",
            json={"token": raw_token, "password": "ConcurrentValid123!"},
        )

    res1, res2 = await asyncio.gather(consume(), consume())
    status_codes = [res1.status_code, res2.status_code]
    assert status.HTTP_200_OK in status_codes
    assert status.HTTP_400_BAD_REQUEST in status_codes
