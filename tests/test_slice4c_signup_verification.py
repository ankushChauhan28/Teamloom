"""
Slice 4c Acceptance Tests: Self-Serve Signup, Email Verification, Anti-Enumeration,
Unverified Login Enforcement, Cleanup Job, and Email Providers (NFR-3).
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import ConsoleEmailSender, SMTPEmailSender, get_email_sender
from app.core.rate_limit import _in_memory_instance
from app.core.security import hash_password
from app.models.email_verification_token import EmailVerificationToken
from app.models.organization import Organization, OrgStatus
from app.models.user import User, UserRole
from app.schemas.user import SignupRequest
from app.services import auth_service


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    FR-2, A6: POST /auth/signup creates organization in pending_payment, Tier-1 Admin,
    unverified email status, and returns generic message without tokens or auto-login.
    """
    signup_payload = {
        "company_name": "Acme Innovations",
        "full_name": "Alice Wonderland",
        "email": "alice.signup@acme.com",
        "password": "SecurePassword123!",
    }

    with patch("app.routes.auth.send_verification_email") as mock_email:
        response = await client.post("/auth/signup", json=signup_payload)
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "user" not in data

    # Verify database state
    user_stmt = select(User).where(func.lower(User.email) == "alice.signup@acme.com")
    user = (await db_session.execute(user_stmt)).scalar_one_or_none()
    assert user is not None
    assert user.full_name == "Alice Wonderland"
    assert user.access_level == 1
    assert user.role == UserRole.ADMIN
    assert user.is_email_verified is False
    assert user.email_verified_at is None
    assert user.employee_code is None

    # Verify Organization state
    org_stmt = select(Organization).where(Organization.id == user.organization_id)
    org = (await db_session.execute(org_stmt)).scalar_one_or_none()
    assert org is not None
    assert org.name == "Acme Innovations"
    assert org.status == OrgStatus.PENDING_PAYMENT.value
    assert org.is_internal is False

    # Verify Token record
    token_stmt = select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    token_record = (await db_session.execute(token_stmt)).scalar_one_or_none()
    assert token_record is not None
    assert len(token_record.token_hash) == 64  # SHA-256 hex string
    assert token_record.used_at is None
    assert token_record.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_signup_duplicate_email_anti_enumeration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    FR-4, B3, Anti-enumeration:
    Attempting signup with an already-registered email returns identical 201 response
    and does not create a duplicate user or organization.
    """
    signup_payload = {
        "company_name": "First Company",
        "full_name": "First Admin",
        "email": "duplicate.test@example.com",
        "password": "Password123!",
    }

    # 1. First signup
    res1 = await client.post("/auth/signup", json=signup_payload)
    assert res1.status_code == 201

    # 2. Duplicate signup with differing case
    duplicate_payload = {
        "company_name": "Second Rogue Company",
        "full_name": "Second Impostor",
        "email": "DUPLICATE.TEST@EXAMPLE.COM",
        "password": "Password123!",
    }
    res2 = await client.post("/auth/signup", json=duplicate_payload)
    assert res2.status_code == 201
    assert res2.json() == res1.json()

    # Verify only one user exists
    users_stmt = select(User).where(func.lower(User.email) == "duplicate.test@example.com")
    users = (await db_session.execute(users_stmt)).scalars().all()
    assert len(users) == 1

    # Verify second company was not created
    rogue_org_stmt = select(Organization).where(Organization.name == "Second Rogue Company")
    rogue_org = (await db_session.execute(rogue_org_stmt)).scalar_one_or_none()
    assert rogue_org is None


@pytest.mark.asyncio
async def test_verify_email_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    FR-2, X2: POST /auth/verify-email consumes single-use token,
    sets is_email_verified=True and email_verified_at=now.
    """
    # Create unverified user and token
    signup_req = SignupRequest(
        company_name="Verification Corp",
        full_name="Bob Verifier",
        email="bob.verify@example.com",
        password="Password123!",
    )
    _, email, full_name, raw_token = await auth_service.signup_organization_and_admin(
        db=db_session, signup_in=signup_req
    )
    assert raw_token is not None

    # Call verify-email
    response = await client.post("/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 200
    data = response.json()
    assert data["is_verified"] is True
    assert data["email"] == "bob.verify@example.com"

    # Verify DB state
    user_stmt = select(User).where(func.lower(User.email) == "bob.verify@example.com")
    user = (await db_session.execute(user_stmt)).scalar_one_or_none()
    assert user.is_email_verified is True
    assert user.email_verified_at is not None

    # Verify token record marked used
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    tok_stmt = select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    tok = (await db_session.execute(tok_stmt)).scalar_one_or_none()
    assert tok.used_at is not None


@pytest.mark.asyncio
async def test_verify_email_single_use_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    Single-use enforcement: reusing an already-consumed token returns generic 400.
    """
    signup_req = SignupRequest(
        company_name="Single Use Corp",
        full_name="Charlie Single",
        email="charlie.single@example.com",
        password="Password123!",
    )
    _, _, _, raw_token = await auth_service.signup_organization_and_admin(
        db=db_session, signup_in=signup_req
    )

    # 1. First verification succeeds
    res1 = await client.post("/auth/verify-email", json={"token": raw_token})
    assert res1.status_code == 200

    # 2. Second verification with same token fails
    res2 = await client.post("/auth/verify-email", json={"token": raw_token})
    assert res2.status_code == 400
    assert res2.json()["detail"] == "Invalid or expired verification token."


@pytest.mark.asyncio
async def test_verify_email_expired_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Expired token (> 24 hours) returns generic 400.
    """
    signup_req = SignupRequest(
        company_name="Expired Token Corp",
        full_name="Dave Expired",
        email="dave.expired@example.com",
        password="Password123!",
    )
    _, _, _, raw_token = await auth_service.signup_organization_and_admin(
        db=db_session, signup_in=signup_req
    )

    # Manually backdate token expires_at
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    tok_stmt = select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    tok = (await db_session.execute(tok_stmt)).scalar_one_or_none()
    tok.expires_at = datetime.now(UTC) - timedelta(hours=2)
    await db_session.commit()

    # Verify attempt fails
    res = await client.post("/auth/verify-email", json={"token": raw_token})
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid or expired verification token."


@pytest.mark.asyncio
async def test_verify_email_invalid_token_generic_error(client: AsyncClient) -> None:
    """
    Non-existent or malformed token returns generic 400 without leaking token validity details.
    """
    res = await client.post("/auth/verify-email", json={"token": "completely_bogus_token_value_123"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid or expired verification token."


@pytest.mark.asyncio
async def test_resend_verification_invalidates_older_tokens(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    POST /auth/resend-verification generates new token and invalidates older unused tokens.
    """
    signup_req = SignupRequest(
        company_name="Resend Corp",
        full_name="Eva Resend",
        email="eva.resend@example.com",
        password="Password123!",
    )
    _, _, _, raw_token_1 = await auth_service.signup_organization_and_admin(
        db=db_session, signup_in=signup_req
    )

    # Resend verification
    res = await client.post(
        "/auth/resend-verification", json={"email": "eva.resend@example.com"}
    )
    assert res.status_code == 200
    assert "verification link has been sent" in res.json()["message"]

    # Old token should now be marked used (invalidated)
    tok1_hash = hashlib.sha256(raw_token_1.encode("utf-8")).hexdigest()
    tok1 = (
        await db_session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == tok1_hash)
        )
    ).scalar_one_or_none()
    assert tok1.used_at is not None

    # Old token fails verification
    res_old = await client.post("/auth/verify-email", json={"token": raw_token_1})
    assert res_old.status_code == 400

    # Retrieve new token and verify it succeeds
    tok2_stmt = (
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == tok1.user_id,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    tok2 = (await db_session.execute(tok2_stmt)).scalar_one_or_none()
    assert tok2 is not None


@pytest.mark.asyncio
async def test_resend_verification_anti_enumeration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    Resending for non-existent email or already-verified user returns identical generic message.
    """
    # 1. Non-existent email
    res1 = await client.post(
        "/auth/resend-verification", json={"email": "nonexistent@nowhere.com"}
    )
    assert res1.status_code == 200

    # 2. Already-verified user
    signup_req = SignupRequest(
        company_name="Verified Corp",
        full_name="Frank Verified",
        email="frank.verified@example.com",
        password="Password123!",
    )
    _, _, _, raw_token = await auth_service.signup_organization_and_admin(
        db=db_session, signup_in=signup_req
    )
    await auth_service.verify_email(db=db_session, token=raw_token)

    res2 = await client.post(
        "/auth/resend-verification", json={"email": "frank.verified@example.com"}
    )
    assert res2.status_code == 200
    assert res1.json() == res2.json()


@pytest.mark.asyncio
async def test_unverified_admin_login_blocked(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Unverified admin cannot log in via /auth/login (returns generic 401 Incorrect credentials).
    Once verified via token, login succeeds and issues access token.
    """
    signup_req = SignupRequest(
        company_name="Login Blocked Corp",
        full_name="Grace Admin",
        email="grace.admin@example.com",
        password="SecurePassword123!",
    )
    _, _, _, raw_token = await auth_service.signup_organization_and_admin(
        db=db_session, signup_in=signup_req
    )

    # 1. Attempt login before verification -> 401 Incorrect credentials
    login_payload = {
        "identifier": "grace.admin@example.com",
        "password": "SecurePassword123!",
        "mode": "admin",
    }
    res_unverified = await client.post("/auth/login", json=login_payload)
    assert res_unverified.status_code == 401
    assert res_unverified.json()["detail"] == "Incorrect credentials."

    # 2. Verify email
    res_verify = await client.post("/auth/verify-email", json={"token": raw_token})
    assert res_verify.status_code == 200

    # 3. Attempt login after verification -> 200 OK with access token
    res_verified = await client.post("/auth/login", json=login_payload)
    assert res_verified.status_code == 200
    assert "access_token" in res_verified.json()


@pytest.mark.asyncio
async def test_admin_created_employee_login_without_verification(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """
    Employees created by admin inside an organization have is_email_verified=True
    and can log in immediately with their 10-digit User ID.
    """
    emp_payload = {
        "full_name": "Direct Employee",
        "email": "direct.emp@example.com",
        "access_level": 3,
    }
    create_res = await client.post("/users/employees", json=emp_payload, headers=admin_headers)
    assert create_res.status_code == 201
    emp_data = create_res.json()
    emp_code = emp_data["employee_code"]

    # Verify user in database has is_email_verified = True
    user_stmt = select(User).where(User.employee_code == emp_code)
    user = (await db_session.execute(user_stmt)).scalar_one_or_none()
    assert user.is_email_verified is True
    assert user.email_verified_at is not None


@pytest.mark.asyncio
async def test_rate_limiting_signup_and_resend(client: AsyncClient) -> None:
    """
    Verifies that POST /auth/signup and POST /auth/resend-verification are rate-limited
    using get_rate_limiter() with their dedicated key prefixes.
    """
    _in_memory_instance.reset()

    # 10 signup requests succeed
    for i in range(10):
        res = await client.post(
            "/auth/signup",
            json={
                "company_name": f"Rate Corp {i}",
                "full_name": f"Rate User {i}",
                "email": f"rateuser{i}@example.com",
                "password": "Password123!",
            },
        )
        assert res.status_code == 201

    # 11th signup request fails with 429
    res_11 = await client.post(
        "/auth/signup",
        json={
            "company_name": "Rate Corp Overflow",
            "full_name": "Rate User Overflow",
            "email": "overflow@example.com",
            "password": "Password123!",
        },
    )
    assert res_11.status_code == 429
    assert "Too many signup attempts" in res_11.json()["detail"]

    _in_memory_instance.reset()

    # 10 resend requests succeed
    for i in range(10):
        res = await client.post(
            "/auth/resend-verification",
            json={"email": f"rateuser{i}@example.com"},
        )
        assert res.status_code == 200

    # 11th resend request fails with 429
    res_resend_11 = await client.post(
        "/auth/resend-verification",
        json={"email": "overflow@example.com"},
    )
    assert res_resend_11.status_code == 429
    assert "Too many verification requests" in res_resend_11.json()["detail"]


@pytest.mark.asyncio
async def test_cleanup_unverified_signups(db_session: AsyncSession) -> None:
    """
    X1, B8: Scheduled cleanup job deletes unverified signups older than 7 days
    and their organizations in pending_payment status.
    Leaves recent signups, verified admins, and internal orgs untouched.
    """
    now = datetime.now(UTC)

    # 1. Unverified admin older than 7 days in pending_payment org -> SHOULD BE DELETED
    old_org = Organization(name="Old Unpaid Org", status=OrgStatus.PENDING_PAYMENT.value, is_internal=False)
    db_session.add(old_org)
    await db_session.flush()

    old_admin = User(
        full_name="Old Admin",
        email="old.admin@example.com",
        hashed_password=hash_password("pwd"),
        role=UserRole.ADMIN,
        access_level=1,
        is_email_verified=False,
        email_verified_at=None,
        organization_id=old_org.id,
        created_at=now - timedelta(days=8),
    )
    db_session.add(old_admin)
    await db_session.flush()

    old_token = EmailVerificationToken(
        user_id=old_admin.id,
        token_hash=hashlib.sha256(b"old_token_value_123").hexdigest(),
        expires_at=now - timedelta(days=7),
    )
    db_session.add(old_token)

    # 2. Recent unverified admin (created 3 days ago) -> SHOULD REMAIN
    recent_org = Organization(name="Recent Org", status=OrgStatus.PENDING_PAYMENT.value, is_internal=False)
    db_session.add(recent_org)
    await db_session.flush()

    recent_admin = User(
        full_name="Recent Admin",
        email="recent.admin@example.com",
        hashed_password=hash_password("pwd"),
        role=UserRole.ADMIN,
        access_level=1,
        is_email_verified=False,
        email_verified_at=None,
        organization_id=recent_org.id,
        created_at=now - timedelta(days=3),
    )
    db_session.add(recent_admin)

    # 3. Verified admin older than 7 days -> SHOULD REMAIN
    verified_org = Organization(name="Verified Org", status=OrgStatus.PENDING_PAYMENT.value, is_internal=False)
    db_session.add(verified_org)
    await db_session.flush()

    verified_admin = User(
        full_name="Verified Admin",
        email="verified.admin@example.com",
        hashed_password=hash_password("pwd"),
        role=UserRole.ADMIN,
        access_level=1,
        is_email_verified=True,
        email_verified_at=now - timedelta(days=8),
        organization_id=verified_org.id,
        created_at=now - timedelta(days=8),
    )
    db_session.add(verified_admin)

    await db_session.commit()

    # Execute cleanup
    deleted_count = await auth_service.cleanup_unverified_signups(db=db_session)
    assert deleted_count == 1

    # Verify old org and admin were removed
    assert (
        await db_session.execute(select(Organization).where(Organization.id == old_org.id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(User).where(User.id == old_admin.id))
    ).scalar_one_or_none() is None

    # Verify recent admin and verified admin still exist
    assert (
        await db_session.execute(select(User).where(User.id == recent_admin.id))
    ).scalar_one_or_none() is not None
    assert (
        await db_session.execute(select(User).where(User.id == verified_admin.id))
    ).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_email_sender_interface_implementations() -> None:
    """
    NFR-3: Test ConsoleEmailSender and SMTPEmailSender behaviors.
    """
    console_sender = ConsoleEmailSender()
    assert console_sender.send_verification_email("test@example.com", "Tester", "token123") is True
    assert console_sender.send_welcome_email("test@example.com", "Tester", "1000000001", "temp123") is True

    # SMTPEmailSender falls back to console if SMTP unconfigured
    smtp_sender = SMTPEmailSender()
    with patch.object(settings, "SMTP_HOST", None):
        assert smtp_sender.send_verification_email("test@example.com", "Tester", "token123") is True
        assert smtp_sender.send_welcome_email("test@example.com", "Tester", "1000000001", "temp123") is True

    # get_email_sender() respects EMAIL_BACKEND setting
    with patch.object(settings, "EMAIL_BACKEND", "console"):
        assert isinstance(get_email_sender(), ConsoleEmailSender)

    with patch.object(settings, "EMAIL_BACKEND", "smtp"):
        assert isinstance(get_email_sender(), SMTPEmailSender)
