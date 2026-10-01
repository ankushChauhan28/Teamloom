"""
Integration Tests for Role-Based Access Control (RBAC) Enforcements
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole



@pytest.mark.asyncio
async def test_employee_cannot_create_task(
    client: AsyncClient,
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee attempting to create a task returns HTTP 403 Forbidden.
    """
    payload = {
        "title": "Unauthorized Task",
        "description": "Employee trying to create task.",
        "priority": "HIGH",
        "due_datetime": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        "assigned_to": employee_user.id,
    }
    response = await client.post("/tasks/", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "permission" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_employee_cannot_delete_task(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee attempting to delete a task returns HTTP 403 Forbidden.
    """
    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Task for Deletion Test",
            "description": "Description",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    task_id = task_res.json()["id"]

    del_res = await client.delete(f"/tasks/{task_id}", headers=employee_headers)
    assert del_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_employee_cannot_list_all_employees(
    client: AsyncClient, employee_headers: dict[str, str]
) -> None:
    """
    Test Employee attempting to list all employees (`GET /users/`) returns HTTP 403 Forbidden.
    """
    response = await client.get("/users/", headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_employee_cannot_review_leave(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test Employee attempting to approve/reject a leave request returns HTTP 403 Forbidden.
    """
    sub_res = await client.post(
        "/leaves/",
        json={
            "reason": "Test Leave",
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
        },
        headers=employee_headers,
    )
    leave_id = sub_res.json()["id"]

    rev_res = await client.patch(
        f"/leaves/{leave_id}",
        json={"status": "APPROVED"},
        headers=employee_headers,
    )
    assert rev_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_employee_cannot_set_reports_to(
    client: AsyncClient,
    employee_headers: dict[str, str],
    employee_user: User,
    admin_user: User,
) -> None:
    """
    Test Employee attempting to set/change any user's reports_to_id (`PATCH /users/{user_id}/reports-to`)
    returns HTTP 403 Forbidden.
    """
    res = await client.patch(
        f"/users/{employee_user.id}/reports-to",
        json={"reports_to_id": admin_user.id},
        headers=employee_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_employee_cannot_bypass_reports_to_id_via_update_me(
    client: AsyncClient,
    employee_headers: dict[str, str],
    employee_user: User,
    admin_user: User,
) -> None:
    """
    Test an EMPLOYEE attempting to pass `reports_to_id` to `PATCH /users/me` fails to mutate `reports_to_id`.
    The `UserUpdate` schema excludes `reports_to_id`, ensuring it is ignored/not applied.
    """
    payload = {"full_name": "Updated Employee Name", "reports_to_id": admin_user.id}
    response = await client.patch("/users/me", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["full_name"] == "Updated Employee Name"
    # Ensure reports_to_id remained None and was not mutated via self-update
    assert data["reports_to_id"] is None


@pytest.mark.asyncio
async def test_tier3_user_can_assign_task_to_direct_report(

    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Verify that Tier 3 users CAN assign tasks to their direct reports,
    and CANNOT assign to non-direct reports or themselves.
    """
    tier3_lead = User(
        full_name="Tier 3 Team Lead",
        email="lead.tier3@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="EMP-3001",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(tier3_lead)
    await db_session.commit()
    await db_session.refresh(tier3_lead)

    tier4_subordinate = User(
        full_name="Tier 4 Associate",
        email="assoc.tier4@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-4001",
        reports_to_id=tier3_lead.id,
        must_change_password=False,
        organization_id=test_org.id,
    )
    non_report = User(
        full_name="Other Associate",
        email="other.tier4@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-4009",
        reports_to_id=None,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(tier4_subordinate)
    db_session.add(non_report)
    await db_session.commit()
    await db_session.refresh(tier4_subordinate)
    await db_session.refresh(non_report)

    lead_token = create_access_token(email=tier3_lead.email, role=tier3_lead.role.value)
    lead_headers = {"Authorization": f"Bearer {lead_token}"}

    # 1. Successful assignment to direct report
    payload = {
        "title": "Lead Task Assignment to Direct Report",
        "description": "Tier 3 assigning task to direct report",
        "priority": "HIGH",
        "due_datetime": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "assigned_to": tier4_subordinate.id,
    }
    response = await client.post("/tasks/", json=payload, headers=lead_headers)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["assigned_to"] == tier4_subordinate.id

    # 2. Denied assignment to non-direct report
    unauthorized_payload = {
        "title": "Lead Task to Non-Report",
        "description": "Tier 3 attempting to assign task to non-direct report",
        "priority": "LOW",
        "due_datetime": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "assigned_to": non_report.id,
    }
    unauthorized_res = await client.post("/tasks/", json=unauthorized_payload, headers=lead_headers)
    assert unauthorized_res.status_code == status.HTTP_403_FORBIDDEN
    assert "permission" in unauthorized_res.json()["detail"].lower()

    # 3. Denied self-assignment
    self_payload = {
        "title": "Self Assignment Attempt",
        "description": "Tier 3 attempting to assign task to self",
        "priority": "LOW",
        "due_datetime": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "assigned_to": tier3_lead.id,
    }
    self_res = await client.post("/tasks/", json=self_payload, headers=lead_headers)
    assert self_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_tier4_user_can_assign_task_to_direct_report(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Verify that Tier 4 users CAN assign tasks to their direct reports,
    and CANNOT assign to non-direct reports.
    """
    tier4_user = User(
        full_name="Tier 4 Worker",
        email="worker.tier4@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-4002",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(tier4_user)
    await db_session.commit()
    await db_session.refresh(tier4_user)

    tier4_report = User(
        full_name="Tier 4 Report",
        email="report.tier4@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-4003",
        reports_to_id=tier4_user.id,
        must_change_password=False,
        organization_id=test_org.id,
    )
    tier4_non_report = User(
        full_name="Tier 4 Peer",
        email="peer.tier4@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-4004",
        reports_to_id=None,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(tier4_report)
    db_session.add(tier4_non_report)
    await db_session.commit()
    await db_session.refresh(tier4_report)
    await db_session.refresh(tier4_non_report)

    token = create_access_token(email=tier4_user.email, role=tier4_user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Successful assignment to direct report
    payload = {
        "title": "Tier 4 Assignment to Direct Report",
        "description": "Tier 4 assigning task to direct report",
        "priority": "LOW",
        "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "assigned_to": tier4_report.id,
    }
    response = await client.post("/tasks/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["assigned_to"] == tier4_report.id

    # 2. Denied assignment to non-direct report
    unauthorized_res = await client.post(
        "/tasks/",
        json={
            "title": "Tier 4 Assignment to Non-Report",
            "description": "Tier 4 attempting to assign task to peer",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": tier4_non_report.id,
        },
        headers=headers,
    )
    assert unauthorized_res.status_code == status.HTTP_403_FORBIDDEN
    assert "permission" in unauthorized_res.json()["detail"].lower()



@pytest.mark.asyncio
async def test_tier2_manager_can_assign_task_to_direct_report_normally(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Verify that Tier 2 managers can normally assign tasks to their direct reports.
    """
    tier2_mgr = User(
        full_name="Tier 2 Manager Standard",
        email="mgr.tier2.standard@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=2,
        employee_code="EMP-2005",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(tier2_mgr)
    await db_session.commit()
    await db_session.refresh(tier2_mgr)

    subordinate = User(
        full_name="Tier 3 Subordinate",
        email="subordinate.tier3@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="EMP-3005",
        reports_to_id=tier2_mgr.id,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(subordinate)
    await db_session.commit()
    await db_session.refresh(subordinate)

    mgr_token = create_access_token(email=tier2_mgr.email, role=tier2_mgr.role.value)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    payload = {
        "title": "Manager Assigned Task",
        "description": "Valid task from Tier 2 manager to report",
        "priority": "MEDIUM",
        "due_datetime": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
        "assigned_to": subordinate.id,
    }
    response = await client.post("/tasks/", json=payload, headers=mgr_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["assigned_to"] == subordinate.id


@pytest.mark.asyncio
async def test_ankush_piyush_mortal_hierarchy_chain_task_assignment(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Regression test for the real-world chain:
    Ankush (Tier 2, no manager) -> Piyush (Tier 3 direct report) -> Mortal Gama (Tier 4 direct report).
    - Ankush assigning to Piyush must succeed.
    - Piyush assigning to Mortal Gama must succeed.
    - Piyush assigning to Ankush must be forbidden.
    - Mortal Gama assigning to Piyush must be forbidden.
    """
    ankush = User(
        full_name="Ankush Chauhan",
        email="ankush@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=2,
        employee_code="EMP-1002",
        reports_to_id=None,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(ankush)
    await db_session.commit()
    await db_session.refresh(ankush)

    piyush = User(
        full_name="Piyush Chauhan",
        email="piyush@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="EMP-1005",
        reports_to_id=ankush.id,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(piyush)
    await db_session.commit()
    await db_session.refresh(piyush)

    mortal = User(
        full_name="Mortal Gama",
        email="mortal@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-1006",
        reports_to_id=piyush.id,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(mortal)
    await db_session.commit()
    await db_session.refresh(mortal)


    ankush_token = create_access_token(email=ankush.email, role=ankush.role.value)
    ankush_headers = {"Authorization": f"Bearer {ankush_token}"}

    piyush_token = create_access_token(email=piyush.email, role=piyush.role.value)
    piyush_headers = {"Authorization": f"Bearer {piyush_token}"}

    mortal_token = create_access_token(email=mortal.email, role=mortal.role.value)
    mortal_headers = {"Authorization": f"Bearer {mortal_token}"}

    # 1. Ankush (Tier 2) assigns task to Piyush (Tier 3 direct report) -> MUST SUCCEED
    res1 = await client.post(
        "/tasks/",
        json={
            "title": "Ankush to Piyush Task",
            "description": "Task from manager to direct report",
            "priority": "HIGH",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": piyush.id,
        },
        headers=ankush_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    assert res1.json()["assigned_to"] == piyush.id

    # 2. Piyush (Tier 3) assigns task to Mortal Gama (Tier 4 direct report) -> MUST SUCCEED
    res2 = await client.post(
        "/tasks/",
        json={
            "title": "Piyush to Mortal Task",
            "description": "Task from lead to direct report",
            "priority": "MEDIUM",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": mortal.id,
        },
        headers=piyush_headers,
    )
    assert res2.status_code == status.HTTP_201_CREATED
    assert res2.json()["assigned_to"] == mortal.id

    # 3. Piyush (Tier 3) cannot assign to Ankush (Tier 2 manager - not a direct report)
    res3 = await client.post(
        "/tasks/",
        json={
            "title": "Piyush to Ankush Task",
            "description": "Reverse assignment",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": ankush.id,
        },
        headers=piyush_headers,
    )
    assert res3.status_code == status.HTTP_403_FORBIDDEN

    # 4. Mortal (Tier 4) cannot assign to Piyush (Tier 3 lead - not a direct report)
    res4 = await client.post(
        "/tasks/",
        json={
            "title": "Mortal to Piyush Task",
            "description": "Reverse assignment",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": mortal.id,
        },
        headers=mortal_headers,
    )
    assert res4.status_code == status.HTTP_403_FORBIDDEN


