from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.user import User, UserRole


@pytest.fixture
async def manager_hierarchy(db_session: AsyncSession):
    """
    Creates a manager hierarchy fixture:
    - Manager: EMP-1010 (EMPLOYEE role, manages Report 1)
    - Report 1: EMP-1011 (EMPLOYEE role, reports_to_id = Manager.id)
    - Other Employee: EMP-1012 (EMPLOYEE role, reports_to_id = None)
    """
    manager = User(
        full_name="Manager Aisha",
        email="aisha.mgr@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        employee_code="EMP-1010",
        must_change_password=False,
    )
    db_session.add(manager)
    await db_session.commit()
    await db_session.refresh(manager)

    report1 = User(
        full_name="Report Karan",
        email="karan.rpt@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        employee_code="EMP-1011",
        reports_to_id=manager.id,
        must_change_password=False,
    )
    db_session.add(report1)

    other_emp = User(
        full_name="Other Rakesh",
        email="rakesh.other@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        employee_code="EMP-1012",
        reports_to_id=None,
        must_change_password=False,
    )
    db_session.add(other_emp)
    await db_session.commit()
    await db_session.refresh(report1)
    await db_session.refresh(other_emp)

    mgr_token = create_access_token(email=manager.email, role=manager.role.value)
    report_token = create_access_token(email=report1.email, role=report1.role.value)
    other_token = create_access_token(email=other_emp.email, role=other_emp.role.value)

    return {
        "manager": manager,
        "report1": report1,
        "other_emp": other_emp,
        "mgr_headers": {"Authorization": f"Bearer {mgr_token}"},
        "report_headers": {"Authorization": f"Bearer {report_token}"},
        "other_headers": {"Authorization": f"Bearer {other_token}"},
    }


async def test_get_my_direct_reports(client: AsyncClient, manager_hierarchy: dict):
    """
    GET /users/me/reports returns direct reports for a manager, empty list for non-manager.
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    report_headers = manager_hierarchy["report_headers"]
    report1 = manager_hierarchy["report1"]

    # Manager calls /users/me/reports -> gets report1
    res = await client.get("/users/me/reports", headers=mgr_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == report1.id
    assert data[0]["employee_code"] == "EMP-1011"

    # Report calls /users/me/reports -> gets empty list []
    res_empty = await client.get("/users/me/reports", headers=report_headers)
    assert res_empty.status_code == 200
    assert res_empty.json() == []


async def test_manager_create_task_for_direct_report_success(
    client: AsyncClient, manager_hierarchy: dict
):
    """
    A non-admin manager can create/assign a task to their direct report.
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    report1 = manager_hierarchy["report1"]
    manager = manager_hierarchy["manager"]

    payload = {
        "title": "Quarterly Performance Review",
        "description": "Prepare self-assessment document",
        "priority": "HIGH",
        "due_datetime": "2026-12-31T23:59:59Z",
        "assigned_to": report1.id,
    }

    res = await client.post("/tasks/", json=payload, headers=mgr_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["assigned_to"] == report1.id
    assert data["created_by"] == manager.id


async def test_manager_cannot_assign_task_to_non_report_fails(
    client: AsyncClient, manager_hierarchy: dict
):
    """
    A non-admin manager CANNOT assign a task to someone who is NOT their direct report (403 Forbidden).
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    other_emp = manager_hierarchy["other_emp"]

    payload = {
        "title": "Unauthorized Task",
        "description": "Should fail with 403",
        "priority": "MEDIUM",
        "due_datetime": "2026-12-31T23:59:59Z",
        "assigned_to": other_emp.id,
    }

    res = await client.post("/tasks/", json=payload, headers=mgr_headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "You do not have permission to assign tasks to this employee."


async def test_manager_cannot_assign_task_to_self_fails(
    client: AsyncClient, manager_hierarchy: dict
):
    """
    A non-admin manager CANNOT assign a task to themselves via manager path (403 Forbidden).
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    manager = manager_hierarchy["manager"]

    payload = {
        "title": "Self Assigned Task",
        "description": "Should fail with 403",
        "priority": "MEDIUM",
        "due_datetime": "2026-12-31T23:59:59Z",
        "assigned_to": manager.id,
    }

    res = await client.post("/tasks/", json=payload, headers=mgr_headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "You do not have permission to assign tasks to this employee."


async def test_get_team_tasks(client: AsyncClient, manager_hierarchy: dict):
    """
    GET /tasks/team returns tasks assigned to direct reports, empty for users with no reports.
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    other_headers = manager_hierarchy["other_headers"]
    report1 = manager_hierarchy["report1"]

    # Manager creates task for report1
    payload = {
        "title": "Team Task 1",
        "description": "Task for team view test",
        "priority": "LOW",
        "due_datetime": "2026-12-31T23:59:59Z",
        "assigned_to": report1.id,
    }
    await client.post("/tasks/", json=payload, headers=mgr_headers)

    # Manager calls GET /tasks/team -> returns task
    res_team = await client.get("/tasks/team", headers=mgr_headers)
    assert res_team.status_code == 200
    tasks = res_team.json()
    assert len(tasks) == 1
    assert tasks[0]["assigned_to"] == report1.id

    # Other employee calls GET /tasks/team -> returns empty list []
    res_other = await client.get("/tasks/team", headers=other_headers)
    assert res_other.status_code == 200
    assert res_other.json() == []


async def test_manager_approve_direct_report_leave_success(
    client: AsyncClient, manager_hierarchy: dict, db_session: AsyncSession
):
    """
    A non-admin manager can approve a direct report's leave request and reviewed_by is recorded.
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    report1 = manager_hierarchy["report1"]
    manager = manager_hierarchy["manager"]

    # Report1 creates leave request
    leave = LeaveRequest(
        employee_id=report1.id,
        reason="Medical leave",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 5),
        status=LeaveStatus.PENDING,
    )
    db_session.add(leave)
    await db_session.commit()
    await db_session.refresh(leave)

    # Manager approves leave
    res = await client.patch(
        f"/leaves/{leave.id}",
        json={"status": "APPROVED"},
        headers=mgr_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "APPROVED"
    assert data["reviewed_by"] == manager.id


async def test_manager_cannot_approve_non_report_leave_fails(
    client: AsyncClient, manager_hierarchy: dict, db_session: AsyncSession
):
    """
    A non-admin manager CANNOT approve/reject a leave request from a non-report (403 Forbidden).
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    other_emp = manager_hierarchy["other_emp"]

    # Other employee creates leave request
    leave = LeaveRequest(
        employee_id=other_emp.id,
        reason="Vacation",
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 15),
        status=LeaveStatus.PENDING,
    )
    db_session.add(leave)
    await db_session.commit()
    await db_session.refresh(leave)

    # Manager attempts to approve other employee's leave -> 403 Forbidden
    res = await client.patch(
        f"/leaves/{leave.id}",
        json={"status": "APPROVED"},
        headers=mgr_headers,
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "You do not have permission to review this leave request."


async def test_user_cannot_approve_own_leave_fails(
    client: AsyncClient, manager_hierarchy: dict, db_session: AsyncSession
):
    """
    A user cannot approve/reject their own leave request (403 Forbidden).
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    manager = manager_hierarchy["manager"]

    # Manager submits own leave request
    leave = LeaveRequest(
        employee_id=manager.id,
        reason="Personal day",
        start_date=date(2026, 9, 20),
        end_date=date(2026, 9, 21),
        status=LeaveStatus.PENDING,
    )
    db_session.add(leave)
    await db_session.commit()
    await db_session.refresh(leave)

    # Manager attempts to self-approve -> 403 Forbidden
    res = await client.patch(
        f"/leaves/{leave.id}",
        json={"status": "APPROVED"},
        headers=mgr_headers,
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "You cannot approve or reject your own leave request."


async def test_get_team_leave_requests(
    client: AsyncClient, manager_hierarchy: dict, db_session: AsyncSession
):
    """
    GET /leaves/team returns direct reports' leave requests, empty for users with no reports.
    """
    mgr_headers = manager_hierarchy["mgr_headers"]
    other_headers = manager_hierarchy["other_headers"]
    report1 = manager_hierarchy["report1"]

    leave = LeaveRequest(
        employee_id=report1.id,
        reason="Casual leave",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
        status=LeaveStatus.PENDING,
    )
    db_session.add(leave)
    await db_session.commit()

    # Manager calls GET /leaves/team -> returns leave
    res_team = await client.get("/leaves/team", headers=mgr_headers)
    assert res_team.status_code == 200
    leaves = res_team.json()
    assert len(leaves) == 1
    assert leaves[0]["employee_id"] == report1.id

    # Other employee calls GET /leaves/team -> empty list []
    res_other = await client.get("/leaves/team", headers=other_headers)
    assert res_other.status_code == 200
    assert res_other.json() == []


async def test_edge_case_plain_employee_task_creation_fails(
    client: AsyncClient, manager_hierarchy: dict
):
    """
    Edge Case 1: A plain EMPLOYEE with no reports and no admin role attempts POST /tasks/ -> confirm 403 Forbidden.
    """
    other_headers = manager_hierarchy["other_headers"]
    report1 = manager_hierarchy["report1"]

    payload = {
        "title": "Plain Employee Task Attempt",
        "description": "Should fail with 403",
        "priority": "LOW",
        "due_datetime": "2026-12-31T23:59:59Z",
        "assigned_to": report1.id,
    }
    res = await client.post("/tasks/", json=payload, headers=other_headers)
    assert res.status_code == 403
    assert "permission" in res.json()["detail"].lower()


async def test_edge_case_plain_employee_leave_review_fails(
    client: AsyncClient, manager_hierarchy: dict, db_session: AsyncSession
):
    """
    Edge Case 2: A plain EMPLOYEE with no reports attempts PATCH /leaves/{id} on someone else's leave -> confirm 403 Forbidden.
    """
    other_headers = manager_hierarchy["other_headers"]
    report1 = manager_hierarchy["report1"]

    leave = LeaveRequest(
        employee_id=report1.id,
        reason="Report leave",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 2),
        status=LeaveStatus.PENDING,
    )
    db_session.add(leave)
    await db_session.commit()

    res = await client.patch(
        f"/leaves/{leave.id}",
        json={"status": "APPROVED"},
        headers=other_headers,
    )
    assert res.status_code == 403
    assert "permission" in res.json()["detail"].lower()


async def test_edge_case_manager_assign_to_nonexistent_user_id_fails(
    client: AsyncClient, manager_hierarchy: dict
):
    """
    Edge Case 3: Manager attempts to assign a task to assigned_to ID that does not exist at all -> confirm clean 404.
    """
    mgr_headers = manager_hierarchy["mgr_headers"]

    payload = {
        "title": "Task for Non-Existent User",
        "description": "Invalid assignee ID 99999",
        "priority": "MEDIUM",
        "due_datetime": "2026-12-31T23:59:59Z",
        "assigned_to": 99999,
    }
    res = await client.post("/tasks/", json=payload, headers=mgr_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


async def test_edge_case_top_of_chain_user_leave_submission_and_review_flow(
    client: AsyncClient, manager_hierarchy: dict, admin_headers: dict
):
    """
    Edge Case 4: A user with reports_to_id = None (top of chain) submits own leave request and admin reviews it -> confirm 200 OK.
    """
    other_headers = manager_hierarchy["other_headers"]
    other_emp = manager_hierarchy["other_emp"]

    assert other_emp.reports_to_id is None

    # Submit leave request
    leave_payload = {
        "reason": "Top of chain annual leave",
        "start_date": "2026-12-01",
        "end_date": "2026-12-05",
    }
    res_submit = await client.post("/leaves/", json=leave_payload, headers=other_headers)
    assert res_submit.status_code == 201
    leave_id = res_submit.json()["id"]

    # Admin reviews leave request
    res_review = await client.patch(
        f"/leaves/{leave_id}",
        json={"status": "APPROVED"},
        headers=admin_headers,
    )
    assert res_review.status_code == 200
    assert res_review.json()["status"] == "APPROVED"
