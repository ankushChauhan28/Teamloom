import asyncio
import os
import sys

from sqlalchemy import select

# Add parent directory to Python path to allow app imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure all models are imported for relationship resolution
import app.models.email_verification_token  # noqa: F401
import app.models.leave  # noqa: F401
import app.models.task  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def unlock_user(employee_code: str):
    print("========================================")
    print("        Teamloom - Unlock User")
    print("========================================")

    emp_code = employee_code.strip()
    if not emp_code:
        print("\n[-] Error: User ID cannot be empty.")
        return

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(User).where(User.employee_code == emp_code))
            user = result.scalar_one_or_none()

            if not user:
                print(f"\n[-] Error: User with User ID '{emp_code}' not found in database.")
                return

            # Reset lockout state
            was_locked = user.locked_until is not None or user.failed_login_attempts > 0
            user.failed_login_attempts = 0
            user.locked_until = None
            await db.commit()

            status_note = (
                "Account unlocked & failed attempts reset to 0."
                if was_locked
                else "Account was not locked; counters reset to 0."
            )
            print(f"\n[+] Success: {user.full_name} ({user.employee_code}) -> {status_note}")

        except Exception as e:
            print(f"\n[-] An unexpected error occurred: {e}")
            await db.rollback()


def main():
    if len(sys.argv) > 1:
        emp_code = sys.argv[1]
    else:
        emp_code = input("Enter User ID to unlock (e.g. 1000000001): ").strip()

    asyncio.run(unlock_user(emp_code))


if __name__ == "__main__":
    main()
