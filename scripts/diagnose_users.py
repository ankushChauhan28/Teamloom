import asyncio
import os
import sys
from datetime import datetime, timezone
from sqlalchemy import text, select

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.models.leave  # noqa: F401
import app.models.task   # noqa: F401
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole

async def setup_and_diagnose():
    async with AsyncSessionLocal() as db:
        # Seed users if they don't already exist (idempotent check)
        USERS_TO_SEED = [
            ("admin@example.com", "System Administrator", "EMP-1001", UserRole.ADMIN, 1, "Admin@123"),
            ("manager@example.com", "Sarah Manager", "EMP-1002", UserRole.EMPLOYEE, 2, "password123"),
            ("employee@example.com", "Alex Employee", "EMP-1003", UserRole.EMPLOYEE, 4, "password123"),
        ]

        print("=== CHECKING SEED USERS (IDEMPOTENT) ===")
        for email, full_name, emp_code, role, tier, pwd in USERS_TO_SEED:
            result = await db.execute(
                select(User).where((User.email == email) | (User.employee_code == emp_code))
            )
            existing_user = result.scalar_one_or_none()
            if existing_user is not None:
                print(f"✓ User {email} already exists. Skipping creation.")
                continue

            new_user = User(
                full_name=full_name,
                email=email,
                hashed_password=hash_password(pwd),
                role=role,
                access_level=tier,
                employee_code=emp_code,
                must_change_password=False,
                is_active=True,
            )
            db.add(new_user)
            await db.commit()
            print(f"+ Created new user: {email} ({emp_code})")
        print()

        # Check admin access_level integrity without modifying password
        admin_res = await db.execute(select(User).where(User.email == "admin@example.com"))
        admin = admin_res.scalar_one_or_none()
        if admin and (admin.access_level != 1 or admin.failed_login_attempts > 0 or admin.locked_until is not None):
            admin.access_level = 1
            admin.role = UserRole.ADMIN
            admin.is_active = True
            admin.failed_login_attempts = 0
            admin.locked_until = None
            await db.commit()

        # 1. Count
        res = await db.execute(text("SELECT COUNT(*) FROM users"))
        count = res.scalar()
        print(f"=== TOTAL USERS COUNT: {count} ===")

        # 2. All Users Detailed
        users_res = await db.execute(
            select(User).order_by(User.access_level, User.id)
        )
        users = users_res.scalars().all()

        print("\n=== USER LIST ===")
        print(f"{'ID':<4} | {'Code':<10} | {'Tier':<4} | {'Active':<6} | {'MustChange':<10} | {'LockedUntil':<20} | {'Email':<30} | {'Full Name':<20} | {'Hash (first 10)'}")
        print("-" * 130)

        now = datetime.now(timezone.utc)
        locked_users = []
        tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        active_count = 0
        inactive_count = 0

        for u in users:
            is_act = "YES" if u.is_active else "NO"
            if u.is_active:
                active_count += 1
            else:
                inactive_count += 1

            must_chg = "YES" if u.must_change_password else "NO"
            tier = u.access_level
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

            is_locked = False
            lock_str = "None"
            if u.locked_until:
                lock_dt = u.locked_until
                if lock_dt.tzinfo is None:
                    lock_dt = lock_dt.replace(tzinfo=timezone.utc)
                if lock_dt > now:
                    is_locked = True
                    lock_str = str(u.locked_until)
                    locked_users.append(u)
                else:
                    lock_str = f"Expired ({u.locked_until})"

            hash_preview = (u.hashed_password[:10] + "...") if u.hashed_password else "EMPTY"

            print(f"{u.id:<4} | {u.employee_code or 'N/A':<10} | {tier:<4} | {is_act:<6} | {must_chg:<10} | {lock_str:<20} | {u.email:<30} | {u.full_name:<20} | {hash_preview}")

        print("\n=== LOCKED USERS (ACTIVE LOCKOUT) ===")
        if locked_users:
            for lu in locked_users:
                print(f"ID: {lu.id}, Name: {lu.full_name}, Email: {lu.email}, Locked until: {lu.locked_until}, Failed attempts: {lu.failed_login_attempts}")
        else:
            print("No currently locked users found.")

        print("\n=== SUMMARY REPORT ===")
        print(f"Total users in database: {count}")
        print(f"Active users: {active_count}")
        print(f"Inactive users: {inactive_count}")
        print(f"Locked users: {len(locked_users)}")
        print(f"Tier 1 (Admin): {tier_counts.get(1, 0)}")
        print(f"Tier 2 (Manager): {tier_counts.get(2, 0)}")
        print(f"Tier 3 (Lead): {tier_counts.get(3, 0)}")
        print(f"Tier 4 (Employee): {tier_counts.get(4, 0)}")

if __name__ == "__main__":
    asyncio.run(setup_and_diagnose())
