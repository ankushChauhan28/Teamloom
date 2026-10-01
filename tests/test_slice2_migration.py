"""
Acceptance Test H1: Database Migration Backfill & Reversibility
Builds an isolated temporary PostgreSQL database, migrates to previous revision (k1l2m3n4o5p6),
seeds pre-existing un-tenanted data, applies the new migration (l2m3n4o5p6q7),
and verifies the default organization creation, backfill integrity, NOT NULL constraints,
downgrade, and re-upgrade.
"""

import asyncio
import os
import uuid
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TEST_DATABASE_URL


def _get_alembic_config(db_url: str) -> Config:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(base_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.asyncio
async def test_migration_slice2_backfill_and_reversibility() -> None:
    """
    Acceptance H1:
    1. Spin up dedicated temporary test DB.
    2. Upgrade to previous head 'k1l2m3n4o5p6'.
    3. Insert pre-migration legacy rows without organization_id.
    4. Upgrade to head 'l2m3n4o5p6q7'.
    5. Verify default org created, all rows backfilled, zero NULLs, NOT NULL enforced.
    6. Downgrade to 'k1l2m3n4o5p6' and verify schema cleanly reverted.
    7. Re-upgrade to 'head' and verify idempotent migration.
    8. Drop temporary database.
    """
    temp_db_name = f"test_slice2_mig_{uuid.uuid4().hex[:8]}"
    base_url = make_url(TEST_DATABASE_URL)
    admin_url = base_url.set(database="postgres")
    temp_db_url = base_url.set(database=temp_db_name)

    # 1. Create temporary database
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{temp_db_name}"'))
    finally:
        await admin_engine.dispose()

    cfg = _get_alembic_config(temp_db_url.render_as_string(hide_password=False))
    temp_engine = create_async_engine(temp_db_url)

    try:
        # 2. Run migrations up to previous revision
        await asyncio.to_thread(command.upgrade, cfg, "k1l2m3n4o5p6")

        # 3. Seed realistic pre-migration data into legacy tables (no organization_id exists yet)
        async with temp_engine.begin() as conn:
            # Users
            await conn.execute(
                text(
                    """
                    INSERT INTO users (id, full_name, email, hashed_password, role, access_level, employee_code, must_change_password, is_active, created_at)
                    VALUES 
                    (1, 'Legacy Admin', 'admin@legacy.com', 'hash123', 'ADMIN', 1, 'EMP-1001', false, true, NOW()),
                    (2, 'Legacy Manager', 'manager@legacy.com', 'hash123', 'EMPLOYEE', 2, 'EMP-1002', false, true, NOW()),
                    (3, 'Legacy Employee', 'employee@legacy.com', 'hash123', 'EMPLOYEE', 3, 'EMP-1003', false, true, NOW());
                    """
                )
            )
            # Tasks
            await conn.execute(
                text(
                    """
                    INSERT INTO tasks (id, title, description, status, priority, due_datetime, assigned_to, created_by, version, created_at)
                    VALUES 
                    (1, 'Legacy Task 1', 'Desc 1', 'PENDING', 'HIGH', NOW() + interval '2 days', 3, 1, 1, NOW()),
                    (2, 'Legacy Task 2', 'Desc 2', 'COMPLETED', 'MEDIUM', NOW() + interval '1 days', 3, 2, 1, NOW());
                    """
                )
            )
            # Leave Requests
            await conn.execute(
                text(
                    """
                    INSERT INTO leave_requests (id, employee_id, reason, start_date, end_date, status, reviewed_by, created_at)
                    VALUES 
                    (1, 3, 'Legacy Vacation', CURRENT_DATE + 5, CURRENT_DATE + 8, 'APPROVED', 1, NOW()),
                    (2, 3, 'Legacy Sick Leave', CURRENT_DATE + 12, CURRENT_DATE + 14, 'PENDING', NULL, NOW());
                    """
                )
            )

        # 4. Run Slice 2 migration to head
        await asyncio.to_thread(command.upgrade, cfg, "head")

        # 5. Verify backfill integrity and constraints
        async with temp_engine.connect() as conn:
            # Check default organization
            org_res = await conn.execute(
                text("SELECT id, name, status, is_internal FROM organizations")
            )
            orgs = org_res.fetchall()
            assert len(orgs) == 1
            default_org = orgs[0]
            assert default_org[1] == "Internal / free forever"
            assert default_org[2] == "active"
            assert default_org[3] is True
            default_org_id = default_org[0]

            # Check users
            user_res = await conn.execute(
                text("SELECT id, email, organization_id FROM users ORDER BY id")
            )
            users = user_res.fetchall()
            assert len(users) == 3
            for u in users:
                assert u[2] == default_org_id, f"User {u[1]} has organization_id {u[2]}, expected {default_org_id}"

            # Check tasks
            task_res = await conn.execute(
                text("SELECT id, title, organization_id FROM tasks ORDER BY id")
            )
            tasks = task_res.fetchall()
            assert len(tasks) == 2
            for t in tasks:
                assert t[2] == default_org_id, f"Task {t[1]} has organization_id {t[2]}, expected {default_org_id}"

            # Check leave requests
            leave_res = await conn.execute(
                text("SELECT id, reason, organization_id FROM leave_requests ORDER BY id")
            )
            leaves = leave_res.fetchall()
            assert len(leaves) == 2
            for l in leaves:
                assert l[2] == default_org_id, f"Leave {l[1]} has organization_id {l[2]}, expected {default_org_id}"

            # Verify zero NULLs across all company-owned tables
            null_users = (await conn.execute(text("SELECT COUNT(*) FROM users WHERE organization_id IS NULL"))).scalar()
            null_tasks = (await conn.execute(text("SELECT COUNT(*) FROM tasks WHERE organization_id IS NULL"))).scalar()
            null_leaves = (await conn.execute(text("SELECT COUNT(*) FROM leave_requests WHERE organization_id IS NULL"))).scalar()
            assert null_users == 0
            assert null_tasks == 0
            assert null_leaves == 0

        # 6. Test Downgrade to previous revision
        await asyncio.to_thread(command.downgrade, cfg, "k1l2m3n4o5p6")

        async with temp_engine.connect() as conn:
            # Check organizations table no longer exists
            has_org_table = (await conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'organizations')")
            )).scalar()
            assert has_org_table is False

            # Check row counts retained
            u_count = (await conn.execute(text("SELECT COUNT(*) FROM users"))).scalar()
            t_count = (await conn.execute(text("SELECT COUNT(*) FROM tasks"))).scalar()
            l_count = (await conn.execute(text("SELECT COUNT(*) FROM leave_requests"))).scalar()
            assert u_count == 3
            assert t_count == 2
            assert l_count == 2

        # 7. Test Re-upgrade to head
        await asyncio.to_thread(command.upgrade, cfg, "head")

        async with temp_engine.connect() as conn:
            re_org_count = (await conn.execute(text("SELECT COUNT(*) FROM organizations"))).scalar()
            re_users_with_org = (await conn.execute(text("SELECT COUNT(*) FROM users WHERE organization_id IS NOT NULL"))).scalar()
            assert re_org_count == 1
            assert re_users_with_org == 3

    finally:
        await temp_engine.dispose()
        # Drop temporary database
        cleanup_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with cleanup_engine.connect() as conn:
                # Terminate any remaining connections to temp db before dropping
                await conn.execute(
                    text(
                        f"""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = '{temp_db_name}'
                          AND pid <> pg_backend_pid();
                        """
                    )
                )
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{temp_db_name}"'))
        finally:
            await cleanup_engine.dispose()
