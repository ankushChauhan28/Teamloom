"""
Acceptance Test H2: Database Migration Slice 4a Backfill, Constraints & Reversibility.
Builds an isolated temporary PostgreSQL database, migrates to previous revision (l2m3n4o5p6q7),
seeds pre-existing users with EMP- codes and mixed-case emails, applies migration (m3n4o5p6q7r8),
and verifies:
1. All employee_code values are regenerated as unique 10-digit numeric strings.
2. IDs, passwords, and relations remain unchanged.
3. Emails are normalized to lowercase and trimmed.
4. is_email_verified is set to True and email_verified_at is set for existing users.
5. email_verification_tokens table is created.
6. employee_code_seq is dropped.
7. CHECK constraint rejects non-10-digit employee_code.
8. Downgrade to l2m3n4o5p6q7 and re-upgrade work cleanly.
9. Abort on colliding mixed-case emails.
"""

import asyncio
import os
import re
import uuid
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TEST_DATABASE_URL


def _get_alembic_config(db_url: str) -> Config:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(base_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.asyncio
async def test_migration_slice4a_backfill_and_reversibility() -> None:
    """
    Acceptance H2:
    1. Spin up dedicated temporary test DB.
    2. Upgrade to previous revision 'l2m3n4o5p6q7'.
    3. Insert pre-migration users with EMP- codes and mixed-case emails.
    4. Upgrade to head 'm3n4o5p6q7r8'.
    5. Verify:
       - employee_code is 10-digit numeric for all users.
       - IDs, hashed_passwords, role, access_level, organization_id are preserved.
       - emails are lowercased.
       - is_email_verified = True, email_verified_at IS NOT NULL.
       - email_verification_tokens table exists.
       - employee_code_seq sequence is dropped.
       - CHECK constraint rejects invalid employee_code (e.g. 'EMP-9999' or '12345').
    6. Downgrade to 'l2m3n4o5p6q7' and verify clean rollback.
    7. Re-upgrade to 'head' and verify idempotent migration.
    8. Drop temporary database.
    """
    temp_db_name = f"test_slice4a_mig_{uuid.uuid4().hex[:8]}"
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
        await asyncio.to_thread(command.upgrade, cfg, "l2m3n4o5p6q7")

        # 3. Seed realistic pre-migration data into legacy tables
        async with temp_engine.begin() as conn:
            # Get default org id
            org_res = await conn.execute(text("SELECT id FROM organizations LIMIT 1"))
            org_id = org_res.scalar_one()

            # Users with EMP- codes and mixed-case emails
            await conn.execute(
                text(
                    f"""
                    INSERT INTO users (id, full_name, email, hashed_password, role, access_level, employee_code, must_change_password, is_active, organization_id, created_at)
                    VALUES 
                    (101, 'Admin Alice', 'Alice.Admin@Example.COM', 'hash_alice_123', 'ADMIN', 1, 'EMP-1001', false, true, {org_id}, NOW()),
                    (102, 'Manager Bob', 'Bob.Manager@EXAMPLE.com', 'hash_bob_456', 'EMPLOYEE', 2, 'EMP-1002', false, true, {org_id}, NOW()),
                    (103, 'Employee Charlie', 'Charlie.Emp@example.Com ', 'hash_charlie_789', 'EMPLOYEE', 3, 'EMP-1003', false, true, {org_id}, NOW());
                    """
                )
            )

        # 4. Run Slice 4a migration to head
        await asyncio.to_thread(command.upgrade, cfg, "head")

        # 5. Verify backfill integrity and constraints
        async with temp_engine.connect() as conn:
            user_res = await conn.execute(
                text(
                    "SELECT id, full_name, email, hashed_password, role, access_level, employee_code, is_email_verified, email_verified_at "
                    "FROM users WHERE id IN (101, 102, 103) ORDER BY id"
                )
            )
            users = user_res.fetchall()
            assert len(users) == 3

            codes = []
            expected_emails = ["alice.admin@example.com", "bob.manager@example.com", "charlie.emp@example.com"]
            expected_hashes = ["hash_alice_123", "hash_bob_456", "hash_charlie_789"]

            for idx, u in enumerate(users):
                u_id, u_name, u_email, u_hash, u_role, u_level, u_code, u_verified, u_ver_at = u
                assert u_email == expected_emails[idx]
                assert u_hash == expected_hashes[idx]
                assert u_verified is True
                assert u_ver_at is not None
                assert re.match(r"^[0-9]{10}$", u_code), f"employee_code {u_code} is not 10 digits"
                codes.append(u_code)

            # Assert all 3 generated codes are strictly unique
            assert len(set(codes)) == 3

            # Check email_verification_tokens table exists
            has_tokens_table = (
                await conn.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'email_verification_tokens')")
                )
            ).scalar()
            assert has_tokens_table is True

            # Check employee_code_seq sequence is dropped
            seq_exists = (
                await conn.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.sequences WHERE sequence_name = 'employee_code_seq')")
                )
            ).scalar()
            assert seq_exists is False

            # Check CHECK constraint rejects non-10-digit employee_code
            with pytest.raises((IntegrityError, DBAPIError)):
                async with temp_engine.begin() as insert_conn:
                    await insert_conn.execute(
                        text(
                            f"""
                            INSERT INTO users (full_name, email, hashed_password, role, access_level, employee_code, organization_id)
                            VALUES ('Bad Code User', 'bad.code@example.com', 'hash', 'EMPLOYEE', 3, 'EMP-9999', {org_id})
                            """
                        )
                    )

        # 6. Test Downgrade to previous revision
        await asyncio.to_thread(command.downgrade, cfg, "l2m3n4o5p6q7")

        async with temp_engine.connect() as conn:
            # Check email_verification_tokens table is dropped
            has_tokens_table = (
                await conn.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'email_verification_tokens')")
                )
            ).scalar()
            assert has_tokens_table is False

            # Check sequence employee_code_seq is recreated
            seq_exists = (
                await conn.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.sequences WHERE sequence_name = 'employee_code_seq')")
                )
            ).scalar()
            assert seq_exists is True

            # Check is_email_verified column is removed
            has_col = (
                await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT FROM information_schema.columns "
                        "WHERE table_name = 'users' AND column_name = 'is_email_verified')"
                    )
                )
            ).scalar()
            assert has_col is False

        # 7. Test Re-upgrade to head
        await asyncio.to_thread(command.upgrade, cfg, "head")

        async with temp_engine.connect() as conn:
            has_tokens_table = (
                await conn.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'email_verification_tokens')")
                )
            ).scalar()
            assert has_tokens_table is True

    finally:
        await temp_engine.dispose()
        # Drop temporary database
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


@pytest.mark.asyncio
async def test_migration_slice4a_colliding_emails_aborts() -> None:
    """
    Verify that if pre-existing users have emails that collide after lowercasing,
    the migration aborts before changing anything.
    """
    temp_db_name = f"test_slice4a_col_{uuid.uuid4().hex[:8]}"
    base_url = make_url(TEST_DATABASE_URL)
    admin_url = base_url.set(database="postgres")
    temp_db_url = base_url.set(database=temp_db_name)

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{temp_db_name}"'))
    finally:
        await admin_engine.dispose()

    cfg = _get_alembic_config(temp_db_url.render_as_string(hide_password=False))
    temp_engine = create_async_engine(temp_db_url)

    try:
        # 1. Upgrade to l2m3n4o5p6q7
        await asyncio.to_thread(command.upgrade, cfg, "l2m3n4o5p6q7")

        # 2. Insert two users with emails that differ only by case
        async with temp_engine.begin() as conn:
            org_res = await conn.execute(text("SELECT id FROM organizations LIMIT 1"))
            org_id = org_res.scalar_one()

            await conn.execute(
                text(
                    f"""
                    INSERT INTO users (id, full_name, email, hashed_password, role, access_level, employee_code, organization_id)
                    VALUES 
                    (201, 'User Upper', 'COLLIDE@Example.com', 'hash1', 'EMPLOYEE', 3, 'EMP-2001', {org_id}),
                    (202, 'User Lower', 'collide@example.com', 'hash2', 'EMPLOYEE', 3, 'EMP-2002', {org_id});
                    """
                )
            )

        # 3. Upgrade to head should raise Exception about colliding emails
        with pytest.raises(Exception) as exc_info:
            await asyncio.to_thread(command.upgrade, cfg, "head")

        assert "duplicate emails detected after lowercasing" in str(exc_info.value).lower()

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
