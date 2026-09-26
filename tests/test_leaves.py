"""
Integration Tests for Leave Endpoints (/leaves/)
"""

from datetime import date, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_submit_leave_request_success(
    client: AsyncClient,
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test submitting a leave request succeeds with 201 Created and PENDING status.
    """
    payload = {
        "reason": "Annual Vacation",
        "start_date": str(date.today() + timedelta(days=10)),
        "end_date": str(date.today() + timedelta(days=15)),
    }
    response = await client.post("/leaves/", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["reason"] == payload["reason"]
    assert data["status"] == "PENDING"
    assert data["employee_id"] == employee_user.id
    assert data["reviewed_by"] is None


@pytest.mark.asyncio
async def test_submit_leave_invalid_dates_fails(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test submitting leave with end_date prior to start_date fails with 400 Bad Request.
    """
    payload = {
        "reason": "Time Travel Vacation",
        "start_date": str(date.today() + timedelta(days=10)),
        "end_date": str(date.today() + timedelta(days=5)),
    }
    response = await client.post("/leaves/", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot be prior to start date" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_leaves_pagination_and_sorting(
    client: AsyncClient,
    employee_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    """
    Test listing leaves with pagination (skip, limit), status filtering, and sorting.
    """
    await client.post(
        "/leaves/",
        json={
            "reason": "Medical Leave",
            "start_date": str(date.today() + timedelta(days=2)),
            "end_date": str(date.today() + timedelta(days=4)),
        },
        headers=employee_headers,
    )

    response = await client.get(
        "/leaves/?status=PENDING&sort_by=start_date&skip=0&limit=5",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for leave in data:
        assert leave["status"] == "PENDING"


@pytest.mark.asyncio
async def test_admin_approve_leave_success(
    client: AsyncClient,
    employee_headers: dict[str, str],
    admin_headers: dict[str, str],
    admin_user: User,
) -> None:
    """
    Test Admin approving a leave request updates status to APPROVED and records reviewed_by ID.
    """
    sub_res = await client.post(
        "/leaves/",
        json={
            "reason": "Conference",
            "start_date": str(date.today() + timedelta(days=20)),
            "end_date": str(date.today() + timedelta(days=22)),
        },
        headers=employee_headers,
    )
    leave_id = sub_res.json()["id"]

    app_res = await client.patch(
        f"/leaves/{leave_id}",
        json={"status": "APPROVED"},
        headers=admin_headers,
    )
    assert app_res.status_code == status.HTTP_200_OK

    data = app_res.json()
    assert data["status"] == "APPROVED"
    assert data["reviewed_by"] == admin_user.id


@pytest.mark.asyncio
async def test_double_review_leave_fails(
    client: AsyncClient,
    employee_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    """
    Test attempting to re-review an already processed leave request fails with 400 Bad Request.
    """
    sub_res = await client.post(
        "/leaves/",
        json={
            "reason": "Personal",
            "start_date": str(date.today() + timedelta(days=30)),
            "end_date": str(date.today() + timedelta(days=31)),
        },
        headers=employee_headers,
    )
    leave_id = sub_res.json()["id"]

    await client.patch(f"/leaves/{leave_id}", json={"status": "APPROVED"}, headers=admin_headers)

    re_res = await client.patch(
        f"/leaves/{leave_id}", json={"status": "REJECTED"}, headers=admin_headers
    )
    assert re_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already been reviewed" in re_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_leave_request_overlapping_dates_rejected(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test creating an initial leave request (Jan 10-15) and attempting
    a second overlapping request (Jan 12-20) fails with 400 Bad Request.
    """
    res1 = await client.post(
        "/leaves/",
        json={"reason": "Trip 1", "start_date": "2027-01-10", "end_date": "2027-01-15"},
        headers=employee_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    req1_id = res1.json()["id"]

    res2 = await client.post(
        "/leaves/",
        json={"reason": "Trip 2 Overlapping", "start_date": "2027-01-12", "end_date": "2027-01-20"},
        headers=employee_headers,
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    detail = res2.json()["detail"]
    assert f"overlap with existing request (ID: {req1_id})" in detail


@pytest.mark.asyncio
async def test_leave_request_non_overlapping_dates_allowed(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test creating non-overlapping leave requests (Jan 10-15 and Jan 20-25) both succeed.
    """
    res1 = await client.post(
        "/leaves/",
        json={"reason": "First Leave", "start_date": "2027-01-10", "end_date": "2027-01-15"},
        headers=employee_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = await client.post(
        "/leaves/",
        json={"reason": "Second Leave", "start_date": "2027-01-20", "end_date": "2027-01-25"},
        headers=employee_headers,
    )
    assert res2.status_code == status.HTTP_201_CREATED


@pytest.mark.asyncio
async def test_leave_request_edge_case_same_end_start(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test boundary condition: 1st leave ends Jan 15, 2nd starts Jan 16 (no overlap) succeeds.
    """
    res1 = await client.post(
        "/leaves/",
        json={"reason": "Block 1", "start_date": "2027-02-10", "end_date": "2027-02-15"},
        headers=employee_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = await client.post(
        "/leaves/",
        json={"reason": "Block 2 Adjacent", "start_date": "2027-02-16", "end_date": "2027-02-20"},
        headers=employee_headers,
    )
    assert res2.status_code == status.HTTP_201_CREATED


@pytest.mark.asyncio
async def test_tier2_manager_cannot_approve_leave(
    client: AsyncClient,
    db_session: AsyncSession,
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Verify that a Tier 2 Manager receives 403 Forbidden when attempting to approve a leave request.
    Only Tier 1 Administrators can approve or reject leaves.
    """
    from app.core.security import create_access_token, hash_password
    from app.models.user import UserRole

    manager = User(
        full_name="Tier 2 Manager",
        email="manager.tier2@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=2,
        employee_code="EMP-1020",
        must_change_password=False,
    )
    db_session.add(manager)
    await db_session.commit()
    await db_session.refresh(manager)

    employee_user.reports_to_id = manager.id
    await db_session.commit()

    sub_res = await client.post(
        "/leaves/",
        json={
            "reason": "Family Vacation",
            "start_date": str(date.today() + timedelta(days=10)),
            "end_date": str(date.today() + timedelta(days=12)),
        },
        headers=employee_headers,
    )
    assert sub_res.status_code == status.HTTP_201_CREATED
    leave_id = sub_res.json()["id"]

    mgr_token = create_access_token(email=manager.email, role=manager.role.value)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    rev_res = await client.patch(
        f"/leaves/{leave_id}",
        json={"status": "APPROVED"},
        headers=mgr_headers,
    )
    assert rev_res.status_code == status.HTTP_403_FORBIDDEN
    assert "Tier 1" in rev_res.json()["detail"]


