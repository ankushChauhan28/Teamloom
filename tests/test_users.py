"""
Integration Tests for User Endpoints (/users/)
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_get_me_success(
    client: AsyncClient, employee_user: User, employee_headers: dict[str, str]
) -> None:
    """
    Test retrieving own user profile (`GET /users/me`) returns 200 and matches user payload.
    """
    response = await client.get("/users/me", headers=employee_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == employee_user.id
    assert data["email"] == employee_user.email
    assert data["full_name"] == employee_user.full_name
    assert data["role"] == "EMPLOYEE"


@pytest.mark.asyncio
async def test_get_me_unauthenticated_fails(client: AsyncClient) -> None:
    """
    Test accessing `/users/me` without Authorization header returns 401 Unauthorized.
    """
    response = await client.get("/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_update_me_success(
    client: AsyncClient, employee_user: User, employee_headers: dict[str, str]
) -> None:
    """
    Test updating own full name (`PATCH /users/me`) returns updated user model.
    """
    payload = {"full_name": "Updated John Employee"}
    response = await client.patch("/users/me", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["full_name"] == payload["full_name"]
    assert data["email"] == employee_user.email


@pytest.mark.asyncio
async def test_list_employees_by_admin(
    client: AsyncClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test listing employees (`GET /users/`) as Admin returns a list of EMPLOYEE role users
    and strictly excludes ADMIN role users (e.g. admin_user).
    """
    response = await client.get("/users/", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    returned_ids = [item["id"] for item in data]
    assert admin_user.id not in returned_ids, "ADMIN role user must be excluded from GET /users/"

    for item in data:
        assert (
            item["role"] == "EMPLOYEE"
        ), f"User #{item['id']} had role {item['role']}, expected EMPLOYEE"


@pytest.mark.asyncio
async def test_admin_set_user_reports_to_success(
    client: AsyncClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test Admin can set a valid reports_to_id on a user via `PATCH /users/{user_id}/reports-to`.
    """
    # Verify initial reports_to_id is None
    me_res = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {admin_headers['Authorization'].split(' ')[1]}"},
    )
    assert me_res.json()["reports_to_id"] is None

    # Admin sets employee's supervisor to admin_user
    response = await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": admin_user.id},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == employee_user.id
    assert data["reports_to_id"] == admin_user.id


@pytest.mark.asyncio
async def test_admin_set_user_reports_to_self_rejected(
    client: AsyncClient,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test setting reports_to_id to user's own ID via API returns HTTP 400 Bad Request.
    """
    response = await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": employee_user.id},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot report to themselves" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_set_user_reports_to_nonexistent_supervisor_rejected(
    client: AsyncClient,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test setting reports_to_id to a non-existent user ID via API returns HTTP 404 Not Found.
    """
    response = await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": 99999},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "supervisor user not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_set_user_reports_to_cycle_rejected(
    client: AsyncClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test creating a circular chain (A -> B, B -> A) via API returns HTTP 400 Bad Request.
    """
    # Employee reports to Admin
    await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": admin_user.id},
        headers=admin_headers,
    )

    # Attempt to set Admin's supervisor to Employee (cycle)
    response = await client.patch(
        f"/users/{admin_user.id}/reports-to",
        json={"reports_to_id": employee_user.id},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "circular reporting hierarchy" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivate_and_reactivate_user_flow(
    client: AsyncClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test admin can deactivate and reactivate an employee.
    Verifies deactivated employee cannot log in, admin cannot deactivate self,
    and reactivation restores login access.
    """
    # 1. Admin attempts self-deactivation -> 400 Bad Request
    self_deact_res = await client.patch(f"/users/{admin_user.id}/deactivate", headers=admin_headers)
    assert self_deact_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot deactivate their own account" in self_deact_res.json()["detail"].lower()

    # 2. Deactivate employee_user -> 200 OK, is_active=False
    deact_res = await client.patch(f"/users/{employee_user.id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK
    assert deact_res.json()["is_active"] is False

    # 3. Attempt login with deactivated employee credentials -> 401 Unauthorized with generic error
    login_res = await client.post(
        "/auth/login",
        json={
            "identifier": employee_user.employee_code,
            "password": "employeepassword123",
            "mode": "employee",
        },
    )
    assert login_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert login_res.json()["detail"] == "Incorrect credentials."

    # 4. Reactivate employee_user -> 200 OK, is_active=True
    react_res = await client.patch(f"/users/{employee_user.id}/reactivate", headers=admin_headers)
    assert react_res.status_code == status.HTTP_200_OK
    assert react_res.json()["is_active"] is True

    # 5. Login after reactivation -> 200 OK
    login_res_2 = await client.post(
        "/auth/login",
        json={
            "identifier": employee_user.employee_code,
            "password": "employeepassword123",
            "mode": "employee",
        },
    )
    assert login_res_2.status_code == status.HTTP_200_OK
    assert "access_token" in login_res_2.json()


@pytest.mark.asyncio
async def test_deactivate_manager_clears_direct_reports_supervisor(
    client: AsyncClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test deactivating a manager automatically sets their direct reports' reports_to_id to None.
    """
    # Create employee_user reporting to admin_user
    await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": admin_user.id},
        headers=admin_headers,
    )

    # Deactivate employee_user (who will be a manager for a sub-employee if assigned)
    # Provision a sub-employee reporting to employee_user
    sub_emp_res = await client.post(
        "/users/employees",
        json={
            "full_name": "Sub Employee",
            "email": "sub.emp@example.com",
            "reports_to_id": employee_user.id,
            "designation": "Junior Engineer",
        },
        headers=admin_headers,
    )
    assert sub_emp_res.status_code == status.HTTP_201_CREATED
    sub_emp_id = sub_emp_res.json()["id"]

    # Deactivate manager (employee_user)
    deact_res = await client.patch(f"/users/{employee_user.id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK

    # Verify sub_employee's reports_to_id is now None
    sub_emp_check = await client.get("/users/", headers=admin_headers)
    sub_emp_obj = next((u for u in sub_emp_check.json() if u["id"] == sub_emp_id), None)
    assert sub_emp_obj is not None
    assert sub_emp_obj["reports_to_id"] is None, "Deactivating a manager must set direct reports' reports_to_id to None"


@pytest.mark.asyncio
async def test_deactivate_supervisor_clears_direct_reports(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Test that deactivating a supervisor who has 2 active direct reports
    clears reports_to_id to NULL for both reports.
    """
    # 1. Create a supervisor
    sup_res = await client.post(
        "/users/employees",
        json={
            "full_name": "Team Supervisor",
            "email": "supervisor.team@example.com",
            "designation": "Engineering Manager",
        },
        headers=admin_headers,
    )
    assert sup_res.status_code == status.HTTP_201_CREATED
    sup_id = sup_res.json()["id"]

    # 2. Create two active direct reports
    rep1_res = await client.post(
        "/users/employees",
        json={
            "full_name": "Report One",
            "email": "report.one@example.com",
            "reports_to_id": sup_id,
            "designation": "Software Engineer",
        },
        headers=admin_headers,
    )
    assert rep1_res.status_code == status.HTTP_201_CREATED
    rep1_id = rep1_res.json()["id"]

    rep2_res = await client.post(
        "/users/employees",
        json={
            "full_name": "Report Two",
            "email": "report.two@example.com",
            "reports_to_id": sup_id,
            "designation": "QA Engineer",
        },
        headers=admin_headers,
    )
    assert rep2_res.status_code == status.HTTP_201_CREATED
    rep2_id = rep2_res.json()["id"]

    # 3. Deactivate the supervisor
    deact_res = await client.patch(f"/users/{sup_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK
    assert deact_res.json()["is_active"] is False

    # 4. Verify both reports now have reports_to_id = NULL
    users_res = await client.get("/users/", headers=admin_headers)
    assert users_res.status_code == status.HTTP_200_OK
    users_by_id = {u["id"]: u for u in users_res.json()}

    assert users_by_id[rep1_id]["reports_to_id"] is None
    assert users_by_id[rep2_id]["reports_to_id"] is None


@pytest.mark.asyncio
async def test_deactivate_already_orphaned_reports_safe(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Test deactivating a supervisor with no active direct reports executes cleanly without error (idempotent).
    """
    sup_res = await client.post(
        "/users/employees",
        json={
            "full_name": "Solo Supervisor",
            "email": "solo.supervisor@example.com",
            "designation": "Team Lead",
        },
        headers=admin_headers,
    )
    assert sup_res.status_code == status.HTTP_201_CREATED
    sup_id = sup_res.json()["id"]

    # Deactivate supervisor with 0 direct reports
    deact_res = await client.patch(f"/users/{sup_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK
    assert deact_res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_deactivated_employee_excluded_from_direct_reports(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Regression test for FIX A:
    A soft-removed (deactivated) employee must NOT appear in direct reports
    (neither /users/{manager_id}/direct-reports nor /users/me/reports),
    and DOES reappear after being reactivated.
    """
    # 1. Create a manager directly in test DB with must_change_password=False
    manager = User(
        full_name="Manager Bob",
        email="manager.bob@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=2,
        employee_code="1000001020",
        must_change_password=False,
        organization_id=admin_user.organization_id,
    )

    db_session.add(manager)
    await db_session.commit()
    await db_session.refresh(manager)
    mgr_id = manager.id

    # Manager auth headers
    mgr_token = create_access_token(email="manager.bob@example.com", role=UserRole.EMPLOYEE.value)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # 2. Create a report under manager
    rep_res = await client.post(
        "/users/employees",
        json={
            "full_name": "Report Alice",
            "email": "report.alice@example.com",
            "reports_to_id": mgr_id,
            "designation": "Software Engineer",
        },
        headers=admin_headers,
    )
    assert rep_res.status_code == status.HTTP_201_CREATED
    rep_id = rep_res.json()["id"]

    # 3. Initially, direct reports includes Alice (checked via both endpoints)
    direct_res = await client.get(f"/users/{mgr_id}/direct-reports", headers=admin_headers)
    assert direct_res.status_code == status.HTTP_200_OK
    assert rep_id in [u["id"] for u in direct_res.json()]

    me_reports_res = await client.get("/users/me/reports", headers=mgr_headers)
    assert me_reports_res.status_code == status.HTTP_200_OK
    assert rep_id in [u["id"] for u in me_reports_res.json()]

    mgr_direct_res = await client.get(f"/users/{mgr_id}/direct-reports", headers=mgr_headers)
    assert mgr_direct_res.status_code == status.HTTP_200_OK
    assert rep_id in [u["id"] for u in mgr_direct_res.json()]

    # 4. Deactivate Alice
    deact_res = await client.patch(f"/users/{rep_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK
    assert deact_res.json()["is_active"] is False

    # 5. Verify Alice does NOT appear in direct reports (both endpoints)
    direct_res_after = await client.get(f"/users/{mgr_id}/direct-reports", headers=admin_headers)
    assert direct_res_after.status_code == status.HTTP_200_OK
    assert rep_id not in [u["id"] for u in direct_res_after.json()]

    me_reports_after = await client.get("/users/me/reports", headers=mgr_headers)
    assert me_reports_after.status_code == status.HTTP_200_OK
    assert rep_id not in [u["id"] for u in me_reports_after.json()]

    mgr_direct_res_after = await client.get(f"/users/{mgr_id}/direct-reports", headers=mgr_headers)
    assert mgr_direct_res_after.status_code == status.HTTP_200_OK
    assert rep_id not in [u["id"] for u in mgr_direct_res_after.json()]

    # 6. Reactivate Alice
    react_res = await client.patch(f"/users/{rep_id}/reactivate", headers=admin_headers)
    assert react_res.status_code == status.HTTP_200_OK
    assert react_res.json()["is_active"] is True

    # 7. Verify Alice DOES reappear in direct reports (both endpoints)
    direct_res_restored = await client.get(f"/users/{mgr_id}/direct-reports", headers=admin_headers)
    assert direct_res_restored.status_code == status.HTTP_200_OK
    assert rep_id in [u["id"] for u in direct_res_restored.json()]

    me_reports_restored = await client.get("/users/me/reports", headers=mgr_headers)
    assert me_reports_restored.status_code == status.HTTP_200_OK
    assert rep_id in [u["id"] for u in me_reports_restored.json()]

    mgr_direct_res_restored = await client.get(f"/users/{mgr_id}/direct-reports", headers=mgr_headers)
    assert mgr_direct_res_restored.status_code == status.HTTP_200_OK
    assert rep_id in [u["id"] for u in mgr_direct_res_restored.json()]



