import asyncio
import getpass
import os
import sys

from sqlalchemy import select

# Add parent directory to Python path to allow app imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import UTC, datetime

# Ensure all models are imported so SQLAlchemy mappers resolve relationships
import app.models.email_verification_token  # noqa: F401
import app.models.leave  # noqa: F401
import app.models.task  # noqa: F401
from app.core.security import hash_password
from app.db.base import AsyncSessionLocal
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.services.user_service import _generate_next_employee_code



async def seed_admin():
    print("========================================")
    print("        Teamloom - Seed Admin")
    print("========================================")

    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    full_name = os.getenv("ADMIN_NAME", "System Administrator")

    async with AsyncSessionLocal() as db:
        try:
            if not email:
                email = input("Enter Admin Email [admin@example.com]: ").strip()
                if not email:
                    email = "admin@example.com"

            norm_email = email.strip().lower()
            result = await db.execute(select(User).where(User.email == norm_email))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                print(
                    f"\n[-] User with email '{email}' already exists. Role: {existing_user.role.value}, User ID: {existing_user.employee_code}"
                )
                return

            if not password:
                password = getpass.getpass("Enter Admin Password: ").strip()
                if not password:
                    print("\n[-] Error: Password cannot be empty.")
                    return

                confirm_pwd = getpass.getpass("Confirm Admin Password: ").strip()
                if password != confirm_pwd:
                    print("\n[-] Error: Passwords do not match.")
                    return

            org_res = await db.execute(
                select(Organization.id).where(Organization.is_internal.is_(True)).limit(1)
            )
            org_id = org_res.scalar_one_or_none()
            if not org_id:
                fallback_res = await db.execute(select(Organization.id).limit(1))
                org_id = fallback_res.scalar_one_or_none()

            emp_code = _generate_next_employee_code()
            hashed_password = hash_password(password)
            admin = User(
                full_name=full_name,
                email=norm_email,
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                access_level=1,
                employee_code=emp_code,
                is_email_verified=True,
                email_verified_at=datetime.now(UTC),
                must_change_password=False,
                organization_id=org_id,
            )

            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            print(f"\n[+] Success: Admin user '{full_name}' ({norm_email}) created successfully!")
            print(f"    User ID: {admin.employee_code}")

        except Exception as e:
            print(f"\n[-] An unexpected error occurred: {e}")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(seed_admin())
