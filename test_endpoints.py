import json
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def make_request(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req_data = None
    if data:
        req_data = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = e.reason
        return e.code, err_body


def run_tests():
    print("--- Starting Backend API Verification ---")

    # 1. Admin Login
    print("\n[1] Testing Admin Login...")
    login_payload = {"email": "admin@example.com", "password": "adminpassword123"}
    status, body = make_request("/auth/login", "POST", login_payload)
    if status == 200 and "access_token" in body:
        admin_token = body["access_token"]
        admin_refresh = body["refresh_token"]
        print("    -> Admin logged in successfully.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 2. Register Employee
    print("\n[2] Testing Employee Registration...")
    register_payload = {
        "email": "employee@example.com",
        "full_name": "John Employee",
        "password": "securepassword123",
    }
    status, body = make_request("/auth/register", "POST", register_payload)
    if status == 201:
        employee_id = body["id"]
        print(f"    -> Employee registered. ID: {employee_id}")
    elif status == 400 and "already exists" in str(body):
        print("    -> Employee already registered. Fetching user info...")
        # Get employees list as admin to find the ID
        status, users = make_request("/users/", "GET", token=admin_token)
        employee_id = next(u["id"] for u in users if u["email"] == "employee@example.com")
        print(f"    -> Found Employee ID: {employee_id}")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 3. Employee Login
    print("\n[3] Testing Employee Login...")
    emp_login_payload = {"email": "employee@example.com", "password": "securepassword123"}
    status, body = make_request("/auth/login", "POST", emp_login_payload)
    if status == 200 and "access_token" in body:
        emp_token = body["access_token"]
        print("    -> Employee logged in successfully.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 4. Token Refresh
    print("\n[4] Testing Token Refresh...")
    refresh_payload = {"refresh_token": admin_refresh}
    status, body = make_request("/auth/refresh", "POST", refresh_payload)
    if status == 200 and "access_token" in body:
        print("    -> Admin token refreshed successfully.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 5. Get Own Profile
    print("\n[5] Testing Get Own Profile...")
    status, body = make_request("/users/me", "GET", token=emp_token)
    if status == 200 and body["email"] == "employee@example.com":
        print("    -> Get Profile (Me) successful.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 6. Admin Create Task
    print("\n[6] Testing Admin Task Creation...")
    task_payload = {
        "title": "Build Core Features",
        "description": "Write all routes and services.",
        "priority": "HIGH",
        "due_date": "2026-08-30",
        "assigned_to": employee_id,
    }
    status, body = make_request("/tasks/", "POST", task_payload, token=admin_token)
    if status == 201:
        task_id = body["id"]
        print(f"    -> Task created successfully. ID: {task_id}")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 7. Employee List Tasks
    print("\n[7] Testing Employee Task Listing...")
    status, body = make_request("/tasks/", "GET", token=emp_token)
    if status == 200 and len(body) > 0:
        print(f"    -> Employee listed {len(body)} tasks successfully.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 8. Employee Update Task Status
    print("\n[8] Testing Employee Status Update...")
    status_payload = {"status": "IN_PROGRESS"}
    status, body = make_request(f"/tasks/{task_id}", "PATCH", status_payload, token=emp_token)
    if status == 200 and body["status"] == "IN_PROGRESS":
        print("    -> Task status updated to IN_PROGRESS successfully.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 9. Employee Submit Leave
    print("\n[9] Testing Employee Leave Submission...")
    leave_payload = {
        "reason": "Personal work",
        "start_date": "2026-09-10",
        "end_date": "2026-09-12",
    }
    status, body = make_request("/leaves/", "POST", leave_payload, token=emp_token)
    if status == 201:
        leave_id = body["id"]
        print(f"    -> Leave request submitted successfully. ID: {leave_id}")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 10. Admin Approve Leave
    print("\n[10] Testing Admin Leave Approval...")
    review_payload = {"status": "APPROVED"}
    status, body = make_request(f"/leaves/{leave_id}", "PATCH", review_payload, token=admin_token)
    if status == 200 and body["status"] == "APPROVED" and body["reviewed_by"] is not None:
        print("    -> Leave request approved by Admin successfully.")
    else:
        print(f"    -> FAILED: Status {status}, Body: {body}")
        return

    # 11. RBAC Check (Employee cannot create task)
    print("\n[11] Testing RBAC (Employee creating task - should fail)...")
    status, body = make_request("/tasks/", "POST", task_payload, token=emp_token)
    if status == 403:
        print("    -> RBAC test passed. Employee creation blocked with 403 Forbidden.")
    else:
        print(f"    -> FAILED: Expected 403, got {status}, Body: {body}")
        return

    print("\n========================================")
    print("   ALL TESTS PASSED SUCCESSFULLY!       ")
    print("========================================")


if __name__ == "__main__":
    run_tests()
