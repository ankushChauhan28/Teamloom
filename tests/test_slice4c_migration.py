"""
Acceptance Test for Database Migration Slice 4c: Backfill is_email_verified & Reversibility.
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
async def test_migration_slice4c_backfill_and_reversibility() -> None:
    """
    1. Spin up dedicated temporary test DB.
    2. Upgrade to previous revision 'm3n4o5p6q7r8'.
    3. Insert a user with is_email_verified = False.
    4. Upgrade to head 'n4o5p6q7r8s9'.
    5. Verify:
       - user.is_email_verified is True.
       - user.email_verified_at is NOT NULL.
    6. Downgrade to 'm3n4o5p6q7r8' (safe no-op).
    7. Re-upgrade to head (idempotent).
    8. Drop temporary DB.
    """
    temp_db_name = f"test_slice4c_mig_{uuid.uuid4().hex[:8]}"
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
        # 2. Upgrade to previous revision
        await asyncio.to_thread(command.upgrade, cfg, "m3n4o5p6q7r8")

        # 3. Seed an unverified user
        async with temp_engine.begin() as conn:
            org_res = await conn.execute(text("SELECT id FROM organizations LIMIT 1"))
            org_id = org_res.scalar_one()

            await conn.execute(
                text(
                    f"""
                    INSERT INTO users (id, full_name, email, hashed_password, role, access_level, employee_code, is_email_verified, email_verified_at, organization_id)
                    VALUES (301, 'Legacy User', 'legacy.user@example.com', 'hash123', 'EMPLOYEE', 3, '1234567890', false, NULL, {org_id});
                    """
                )
            )

        # 4. Upgrade to head (n4o5p6q7r8s9)
        await asyncio.to_thread(command.upgrade, cfg, "head")

        # 5. Verify backfill
        async with temp_engine.connect() as conn:
            user_res = await conn.execute(
                text("SELECT is_email_verified, email_verified_at FROM users WHERE id = 301")
            )
            is_verified, verified_at = user_res.fetchone()
            assert is_verified is True
            assert verified_at is not None

        # 6. Downgrade to m3n4o5p6q7r8
        await asyncio.to_thread(command.downgrade, cfg, "m3n4o5p6q7r8")

        # 7. Re-upgrade to head
        await asyncio.to_thread(command.upgrade, cfg, "head")

    finally:
        await temp_engine.dispose()
        cleanup_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with cleanup_engine.connect() as conn:
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
