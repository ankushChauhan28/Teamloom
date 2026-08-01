"""
Integration Tests for Leave Endpoints (/leaves/)
"""

from datetime import date, timedelta
import pytest
from fastapi import status
from httpx import AsyncClient

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
