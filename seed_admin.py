import getpass
import os
import sys

# Add current directory to Python path to allow app imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.models.user import User, UserRole


def seed_admin():
    print("========================================")
    print("   Employee Task Management - Seed Admin")
    print("========================================")

    # Allow loading from environment variables or prompting interactively
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    full_name = os.getenv("ADMIN_NAME", "System Administrator")

    db = SessionLocal()
    try:
        if not email:
            email = input("Enter Admin Email [admin@example.com]: ").strip()
            if not email:
                email = "admin@example.com"

        # Check if email is already taken
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"\n[-] Error: A user with email '{email}' already exists.")
            print(f"    Role: {existing_user.role.value}")
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

        # Hash the password and save
        hashed_password = hash_password(password)
        admin = User(
            full_name=full_name, email=email, hashed_password=hashed_password, role=UserRole.ADMIN
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"\n[+] Success: Admin user '{full_name}' ({email}) created successfully!")

    except Exception as e:
        print(f"\n[-] An unexpected error occurred: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
