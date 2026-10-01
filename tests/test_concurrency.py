"""
Infrastructure Concurrency Smoke Tests against Real PostgreSQL.

Validates that concurrent database sessions and PostgreSQL atomic sequences
prevent collisions and handle race conditions cleanly.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task import TaskUpdateStatus
from app.schemas.user import EmployeeCreate
from app.services import task_service, user_service
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_concurrent_employee_code_generation_is_strictly_unique(
    db_session,
) -> None:
    """
    Tests that 10 concurrent requests to create_employee against real PostgreSQL
    atomically acquire sequential, non-colliding employee codes (EMP-1001 to EMP-1010).
    """
    concurrent_count = 10

    async def create_single_employee(idx: int) -> str:
        async with TestingSessionLocal() as session:
            emp_in = EmployeeCreate(
                email=f"concurrent.emp{idx}@example.com",
                full_name=f"Concurrent Employee {idx}",
                designation="Software Engineer",
                access_level=3,
            )
            created_user, _ = await user_service.create_employee(db=session, employee_in=emp_in)
            return created_user.employee_code

    # Execute all 10 creation tasks concurrently
    tasks = [create_single_employee(i) for i in range(concurrent_count)]
    generated_codes = await asyncio.gather(*tasks)

    # 1. Assert exactly 10 codes returned
    assert len(generated_codes) == concurrent_count

    # 2. Assert all codes are unique
    unique_codes = set(generated_codes)
    assert len(unique_codes) == concurrent_count, f"Duplicate codes detected: {generated_codes}"

    # 3. Assert all codes match EMP-1001 through EMP-1010
    expected_codes = {f"EMP-{1001 + i}" for i in range(concurrent_count)}
    assert unique_codes == expected_codes

    # 4. Verify all 10 rows exist in the PostgreSQL users table
    async with TestingSessionLocal() as verify_session:
        result = await verify_session.execute(select(User))
        all_users = result.scalars().all()
        assert len(all_users) == concurrent_count


@pytest.mark.asyncio
async def test_concurrent_task_optimistic_locking_conflict(
    db_session, admin_user: User, employee_user: User
) -> None:
    """
    Tests that concurrent updates targeting the same Task version trigger
    optimistic concurrency conflicts (HTTP 409) in PostgreSQL without corrupting state.
    """
    now = datetime.now(UTC)
    # Seed a task with version = 1
    async with TestingSessionLocal() as session:
        initial_task = Task(
            title="Concurrency Task",
            description="Testing concurrent updates",
            priority=TaskPriority.HIGH,
            due_datetime=now + timedelta(days=2),
            status=TaskStatus.PENDING,
            assigned_to=employee_user.id,
            created_by=admin_user.id,
            organization_id=admin_user.organization_id,
            version=1,
        )

        session.add(initial_task)
        await session.commit()
        await session.refresh(initial_task)
        task_id = initial_task.id

    async def attempt_status_update(target_status: TaskStatus) -> str:
        async with TestingSessionLocal() as session:
            try:
                await task_service.update_task(
                    db=session,
                    task_id=task_id,
                    task_update=TaskUpdateStatus(version=1, status=target_status),
                    user=employee_user,
                )
                return "SUCCESS"
            except AppException as exc:
                if exc.status_code == 409:
                    return "CONFLICT_409"
                raise

    # Execute 2 concurrent update attempts with the same base version 1
    results = await asyncio.gather(
        attempt_status_update(TaskStatus.IN_PROGRESS),
        attempt_status_update(TaskStatus.IN_PROGRESS),
    )

    # Exactly one update should succeed and one must be rejected with 409 Conflict
    success_count = results.count("SUCCESS")
    conflict_count = results.count("CONFLICT_409")

    assert success_count == 1, f"Expected exactly 1 success, got: {results}"
    assert conflict_count == 1, f"Expected exactly 1 conflict, got: {results}"
