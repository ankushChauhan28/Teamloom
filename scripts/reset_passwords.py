import asyncio
import os
import sys
import urllib.request
import urllib.error
import json
from sqlalchemy import select

# Ensure app imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.models.task  # noqa: F401
import app.models.leave  # noqa: F401
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User

users_to_update = [
    ("EMP-1001", "admin@example.com", "Admin@123"),
    ("EMP-1002", "ankushchauhan04.in@gmail.com", "Ankush@123"),
    ("EMP-1003", "kingchauhan2534@gmail.com", "Abhi@123"),
    ("EMP-1004", "chauhanaayush324@gmail.com", "Aayush@123"),
    ("EMP-1005", "piyushchauhan.in@gmail.com", "Piyush@123"),
    ("EMP-1006", "mortalgaming3152009@gmail.com", "Mortal@123"),
]

async def reset_passwords():
    print("====================================================")
    print("      Resetting User Passwords in Database")
    print("====================================================")
    async with AsyncSessionLocal() as db:
        for emp_code, email, password in users_to_update:
            res = await db.execute(select(User).where(User.email == email))
            user = res.scalar_one_or_none()
            if not user:
                # Try by employee_code
                res = await db.execute(select(User).where(User.employee_code == emp_code))
                user = res.scalar_one_or_none()

            if user:
                user.hashed_password = hash_password(password)
                user.failed_login_attempts = 0
                user.locked_until = None
                user.must_change_password = False
                user.is_active = True
                print(f"[+] Updated: {user.employee_code} ({user.email}) -> password updated to '{password}'")
            else:
                print(f"[-] Warning: User not found for {emp_code} / {email}")
        
        await db.commit()
    print("\nDatabase commit completed successfully.")

def verify_logins():
    print("\n====================================================")
    print("      Verifying Logins via API")
    print("====================================================")
    api_url = "http://localhost:8000/auth/login"
    all_succeeded = True

    for emp_code, email, password in users_to_update:
        payload = json.dumps({"employee_code": emp_code, "password": password}).encode("utf-8")
        req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    user_info = data.get("user", {})
                    print(f"✅ Password reset for {email} ({emp_code}) -> Login OK! [Role: {user_info.get('role')}, Tier: {user_info.get('access_level')}]")
                else:
                    print(f"❌ Login failed for {email} ({emp_code}): HTTP {resp.status}")
                    all_succeeded = False
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"❌ Login error for {email} ({emp_code}): HTTP {e.code} - {err_body}")
            all_succeeded = False
        except Exception as ex:
            print(f"❌ Connection error for {email} ({emp_code}): {ex}")
            all_succeeded = False

    if all_succeeded:
        print("\n🎉 ALL 6 USERS SUCCESSFULLY RESET AND VERIFIED!")

if __name__ == "__main__":
    asyncio.run(reset_passwords())
    verify_logins()
