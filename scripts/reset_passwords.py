import asyncio
import os
import sys
import urllib.request
import urllib.error
import json
from sqlalchemy import select

# Ensure app imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import models as _models  # noqa: F401
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User

users_to_update = [
    ("admin@example.com", "Admin@123"),
    ("ankushchauhan04.in@gmail.com", "Ankush@123"),
    ("kingchauhan2534@gmail.com", "Abhi@123"),
    ("chauhanaayush324@gmail.com", "Aayush@123"),
    ("piyushchauhan.in@gmail.com", "Piyush@123"),
    ("mortalgaming3152009@gmail.com", "Mortal@123"),
]

resolved_users = []

async def reset_passwords():
    print("====================================================")
    print("      Resetting User Passwords in Database")
    print("====================================================")
    async with AsyncSessionLocal() as db:
        for email, password in users_to_update:
            norm_email = email.strip().lower()
            res = await db.execute(select(User).where(User.email == norm_email))
            user = res.scalar_one_or_none()

            if user:
                user.hashed_password = hash_password(password)
                user.failed_login_attempts = 0
                user.locked_until = None
                user.must_change_password = False
                user.is_active = True
                resolved_users.append((user.employee_code, norm_email, password, user.access_level))
                print(f"[+] Updated: {user.employee_code} ({user.email}) -> password updated to '{password}'")
            else:
                print(f"[-] Warning: User not found for {email}")
        
        await db.commit()
    print("\nDatabase commit completed successfully.")

def verify_logins():
    print("\n====================================================")
    print("      Verifying Logins via API")
    print("====================================================")
    api_url = "http://localhost:8000/auth/login"
    all_succeeded = True

    for emp_code, email, password, access_level in resolved_users:
        if access_level == 1:
            identifier = email
            mode = "admin"
        else:
            identifier = emp_code
            mode = "employee"

        payload = json.dumps({"identifier": identifier, "password": password, "mode": mode}).encode("utf-8")
        req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    user_info = data.get("user", {})
                    print(f"✅ Password reset for {email} ({emp_code}) [mode={mode}] -> Login OK! [Role: {user_info.get('role')}, Tier: {user_info.get('access_level')}]")
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

    if all_succeeded and resolved_users:
        print("\n🎉 ALL USERS SUCCESSFULLY RESET AND VERIFIED!")

if __name__ == "__main__":
    asyncio.run(reset_passwords())
    verify_logins()
