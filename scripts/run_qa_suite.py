import json
import os
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

test_results = []


def make_api_request(endpoint, method="GET", data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            res_body = res.read().decode("utf-8")
            try:
                body_json = json.loads(res_body) if res_body else {}
            except Exception:
                body_json = res_body
            return res.status, body_json
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        try:
            err_body = json.loads(res_body) if res_body else {}
        except Exception:
            err_body = res_body
        return e.code, err_body
    except Exception as exc:
        return 0, str(exc)


def record_test(
    test_id, category, name, endpoint, method, role, payload, expected_status, actual_status, body
):
    passed = expected_status == actual_status
    # Special check for status match
    result = {
        "test_id": test_id,
        "category": category,
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "role": role,
        "payload": payload,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "passed": passed,
        "response_body": body,
    }
    test_results.append(result)
    status_str = "PASS" if passed else "FAIL"
    print(f"[{status_str}] {test_id}: {name} (Expected {expected_status}, Got {actual_status})")
    return result


def run_all_qa_tests():
    print("==========================================================")
    print("           TEAMLOOM SYSTEM - QA TEST SUITE               ")
    print("==========================================================")

    # ----------------------------------------------------
    # SETUP & DATASET SEEDING (PHASE 2)
    # ----------------------------------------------------
    print("\n--- PHASE 2: SEEDING REALISTIC DATASET ---")

    # 1. Admin Login or Seed
    admin_email = "admin@example.com"
    admin_password = "adminpassword123"

    status, body = make_api_request(
        "/auth/login", "POST", {"email": admin_email, "password": admin_password}
    )
    if status != 200:
        print("Admin user does not exist or credentials invalid. Attempting to seed admin...")
        # Execute seed logic via python direct DB insertion or script
        os.system("python seed_admin.py")
        status, body = make_api_request(
            "/auth/login", "POST", {"email": admin_email, "password": admin_password}
        )

    admin_token = body.get("access_token")
    admin_refresh = body.get("refresh_token")
    print(f"[+] Admin Login: Status {status}")

    # 2. Register 5 Employees with realistic emails
    employees_data = [
        {
            "full_name": "Priya Sharma",
            "email": "priya.sharma@company.com",
            "password": "password123",
        },
        {"full_name": "Rohan Verma", "email": "rohan.verma@company.com", "password": "password123"},
        {"full_name": "Sneha Iyer", "email": "sneha.iyer@company.com", "password": "password123"},
        {"full_name": "Arjun Mehta", "email": "arjun.mehta@company.com", "password": "password123"},
        {"full_name": "Kavya Nair", "email": "kavya.nair@company.com", "password": "password123"},
    ]

    emp_tokens = {}
    emp_ids = {}

    for emp in employees_data:
        reg_status, reg_body = make_api_request("/auth/register", "POST", emp)
        if reg_status == 201:
            emp_ids[emp["email"]] = reg_body["id"]
        elif reg_status == 400 and "already exists" in str(reg_body):
            pass

        # Login to get token and ID
        l_status, l_body = make_api_request(
            "/auth/login", "POST", {"email": emp["email"], "password": emp["password"]}
        )
        if l_status == 200:
            emp_tokens[emp["email"]] = l_body["access_token"]

            # Fetch user ID via /users/me
            me_status, me_body = make_api_request("/users/me", "GET", token=l_body["access_token"])
            if me_status == 200:
                emp_ids[emp["email"]] = me_body["id"]

    print(f"[+] 5 Employees Processed. IDs: {emp_ids}")

    # Fetch Admin user ID
    me_status, me_body = make_api_request("/users/me", "GET", token=admin_token)
    admin_user_id = me_body["id"]
    print(f"[+] Admin User ID: {admin_user_id}")

    # 3. Seed 9 Tasks across 4 employees (Kavya Nair gets 0 tasks)
    tasks_to_seed = [
        # Priya Sharma (Emp 1)
        {
            "title": "Client Presentation Deck",
            "description": "Prepare Q3 slides",
            "priority": "HIGH",
            "due_date": "2026-08-01",
            "assigned_to": emp_ids["priya.sharma@company.com"],
            "emp_email": "priya.sharma@company.com",
            "target_status": "IN_PROGRESS",
        },
        {
            "title": "Quarterly Audit Report",
            "description": "Review financial statements",
            "priority": "LOW",
            "due_date": "2026-08-15",
            "assigned_to": emp_ids["priya.sharma@company.com"],
            "emp_email": "priya.sharma@company.com",
            "target_status": "COMPLETED",
        },
        {
            "title": "Update Onboarding Docs",
            "description": "Add security guidelines",
            "priority": "MEDIUM",
            "due_date": "2026-08-20",
            "assigned_to": emp_ids["priya.sharma@company.com"],
            "emp_email": "priya.sharma@company.com",
            "target_status": "PENDING",
        },
        # Rohan Verma (Emp 2)
        {
            "title": "Database Migration Script",
            "description": "Migrate legacy tables",
            "priority": "HIGH",
            "due_date": "2026-08-05",
            "assigned_to": emp_ids["rohan.verma@company.com"],
            "emp_email": "rohan.verma@company.com",
            "target_status": "COMPLETED",
        },
        {
            "title": "Refactor Auth Middleware",
            "description": "Clean up JWT validation",
            "priority": "LOW",
            "due_date": "2026-08-25",
            "assigned_to": emp_ids["rohan.verma@company.com"],
            "emp_email": "rohan.verma@company.com",
            "target_status": "PENDING",
        },
        # Sneha Iyer (Emp 3)
        {
            "title": "API Performance Tuning",
            "description": "Optimize database queries",
            "priority": "MEDIUM",
            "due_date": "2026-08-10",
            "assigned_to": emp_ids["sneha.iyer@company.com"],
            "emp_email": "sneha.iyer@company.com",
            "target_status": "IN_PROGRESS",
        },
        {
            "title": "Security Patch Update",
            "description": "Update vulnerable packages",
            "priority": "HIGH",
            "due_date": "2026-08-30",
            "assigned_to": emp_ids["sneha.iyer@company.com"],
            "emp_email": "sneha.iyer@company.com",
            "target_status": "PENDING",
        },
        # Arjun Mehta (Emp 4)
        {
            "title": "UI Component Library",
            "description": "Build reusable UI buttons",
            "priority": "LOW",
            "due_date": "2026-08-12",
            "assigned_to": emp_ids["arjun.mehta@company.com"],
            "emp_email": "arjun.mehta@company.com",
            "target_status": "IN_PROGRESS",
        },
        {
            "title": "Integration Testing",
            "description": "Write end-to-end test cases",
            "priority": "MEDIUM",
            "due_date": "2026-08-28",
            "assigned_to": emp_ids["arjun.mehta@company.com"],
            "emp_email": "arjun.mehta@company.com",
            "target_status": "PENDING",
        },
    ]

    seeded_task_ids = []

    for tspec in tasks_to_seed:
        payload = {
            "title": tspec["title"],
            "description": tspec["description"],
            "priority": tspec["priority"],
            "due_date": tspec["due_date"],
            "assigned_to": tspec["assigned_to"],
        }
        st, res = make_api_request("/tasks/", "POST", payload, token=admin_token)
        if st == 201:
            t_id = res["id"]
            seeded_task_ids.append(t_id)
            # Transition status if needed
            if tspec["target_status"] != "PENDING":
                make_api_request(
                    f"/tasks/{t_id}",
                    "PATCH",
                    {"status": tspec["target_status"]},
                    token=emp_tokens[tspec["emp_email"]],
                )

    print(f"[+] {len(seeded_task_ids)} Tasks Created & Transitioned.")

    # 4. Seed Leave Requests
    leaves_to_seed = [
        {
            "emp_email": "priya.sharma@company.com",
            "reason": "Annual Vacation",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
            "action": "APPROVED",
        },
        {
            "emp_email": "rohan.verma@company.com",
            "reason": "Personal Leave",
            "start_date": "2026-08-10",
            "end_date": "2026-08-12",
            "action": "REJECTED",
        },
        {
            "emp_email": "sneha.iyer@company.com",
            "reason": "Medical Leave",
            "start_date": "2026-08-15",
            "end_date": "2026-08-18",
            "action": "PENDING",
        },
    ]

    seeded_leave_ids = []
    for lspec in leaves_to_seed:
        payload = {
            "reason": lspec["reason"],
            "start_date": lspec["start_date"],
            "end_date": lspec["end_date"],
        }
        st, res = make_api_request(
            "/leaves/", "POST", payload, token=emp_tokens[lspec["emp_email"]]
        )
        if st == 201:
            l_id = res["id"]
            seeded_leave_ids.append(l_id)
            if lspec["action"] != "PENDING":
                make_api_request(
                    f"/leaves/{l_id}", "PATCH", {"status": lspec["action"]}, token=admin_token
                )

    print(f"[+] {len(seeded_leave_ids)} Leave Requests Created & Processed.")

    print("\n--- PHASE 3: RUNNING FULL FUNCTIONAL & NEGATIVE TEST SUITE ---")

    # ====================================================
    # 1. AUTHENTICATION TESTS
    # ====================================================
    # TC-AUTH-01: Register valid employee
    import time

    new_email = f"temp.qa.user.{int(time.time())}@company.com"
    st, res = make_api_request(
        "/auth/register",
        "POST",
        {"full_name": "QA Tester", "email": new_email, "password": "password123"},
    )
    record_test(
        "TC-AUTH-01",
        "Authentication",
        "Register valid employee",
        "/auth/register",
        "POST",
        "Public",
        {"full_name": "QA Tester", "email": new_email, "password": "***"},
        201,
        st,
        res,
    )

    # TC-AUTH-02: Register duplicate email
    st, res = make_api_request(
        "/auth/register",
        "POST",
        {
            "full_name": "Priya Duplicate",
            "email": "priya.sharma@company.com",
            "password": "password123",
        },
    )
    record_test(
        "TC-AUTH-02",
        "Authentication",
        "Register duplicate email",
        "/auth/register",
        "POST",
        "Public",
        {"email": "priya.sharma@company.com"},
        400,
        st,
        res,
    )

    # TC-AUTH-03: Register invalid email format
    st, res = make_api_request(
        "/auth/register",
        "POST",
        {"full_name": "Invalid Email", "email": "invalid-email-format", "password": "password123"},
    )
    record_test(
        "TC-AUTH-03",
        "Authentication",
        "Register invalid email format",
        "/auth/register",
        "POST",
        "Public",
        {"email": "invalid-email-format"},
        422,
        st,
        res,
    )

    # TC-AUTH-04: Register missing password
    st, res = make_api_request(
        "/auth/register", "POST", {"full_name": "Missing Pass", "email": "missing.pass@company.com"}
    )
    record_test(
        "TC-AUTH-04",
        "Authentication",
        "Register missing password",
        "/auth/register",
        "POST",
        "Public",
        {"email": "missing.pass@company.com"},
        422,
        st,
        res,
    )

    # TC-AUTH-05: Login correct credentials
    st, res = make_api_request(
        "/auth/login", "POST", {"email": "priya.sharma@company.com", "password": "password123"}
    )
    record_test(
        "TC-AUTH-05",
        "Authentication",
        "Login correct credentials",
        "/auth/login",
        "POST",
        "Public",
        {"email": "priya.sharma@company.com", "password": "***"},
        200,
        st,
        res,
    )

    # TC-AUTH-06: Login wrong password
    st, res = make_api_request(
        "/auth/login", "POST", {"email": "priya.sharma@company.com", "password": "wrongpassword"}
    )
    record_test(
        "TC-AUTH-06",
        "Authentication",
        "Login wrong password",
        "/auth/login",
        "POST",
        "Public",
        {"email": "priya.sharma@company.com", "password": "***"},
        401,
        st,
        res,
    )

    # TC-AUTH-07: Login non-existent email
    st, res = make_api_request(
        "/auth/login", "POST", {"email": "nonexistent.email@company.com", "password": "password123"}
    )
    record_test(
        "TC-AUTH-07",
        "Authentication",
        "Login non-existent email",
        "/auth/login",
        "POST",
        "Public",
        {"email": "nonexistent.email@company.com"},
        401,
        st,
        res,
    )

    # TC-AUTH-08: Token refresh valid
    st, res = make_api_request("/auth/refresh", "POST", {"refresh_token": admin_refresh})
    record_test(
        "TC-AUTH-08",
        "Authentication",
        "Token refresh valid",
        "/auth/refresh",
        "POST",
        "Public",
        {"refresh_token": "valid_refresh_token..."},
        200,
        st,
        res,
    )

    # TC-AUTH-09: Token refresh invalid/garbage token
    st, res = make_api_request("/auth/refresh", "POST", {"refresh_token": "garbage.invalid.token"})
    record_test(
        "TC-AUTH-09",
        "Authentication",
        "Token refresh invalid token",
        "/auth/refresh",
        "POST",
        "Public",
        {"refresh_token": "garbage.invalid.token"},
        401,
        st,
        res,
    )

    # TC-AUTH-10: Access protected route with no token
    st, res = make_api_request("/users/me", "GET")
    record_test(
        "TC-AUTH-10",
        "Authentication",
        "Protected route with missing token",
        "/users/me",
        "GET",
        "None",
        None,
        401,
        st,
        res,
    )

    # TC-AUTH-11: Access protected route with malformed token
    st, res = make_api_request("/users/me", "GET", token="malformed_bearer_token")
    record_test(
        "TC-AUTH-11",
        "Authentication",
        "Protected route with malformed token",
        "/users/me",
        "GET",
        "None",
        None,
        401,
        st,
        res,
    )

    # ====================================================
    # 2. RBAC TESTS
    # ====================================================
    emp1_token = emp_tokens["priya.sharma@company.com"]

    # TC-RBAC-01: Employee attempting to create task
    st, res = make_api_request(
        "/tasks/",
        "POST",
        {
            "title": "Illegal Task",
            "description": "Desc",
            "priority": "LOW",
            "due_date": "2026-09-01",
            "assigned_to": emp_ids["priya.sharma@company.com"],
        },
        token=emp1_token,
    )
    record_test(
        "TC-RBAC-01",
        "RBAC",
        "Employee creating task",
        "/tasks/",
        "POST",
        "Employee",
        {"title": "Illegal Task"},
        403,
        st,
        res,
    )

    # TC-RBAC-02: Employee attempting to delete task
    first_task_id = seeded_task_ids[0]
    st, res = make_api_request(f"/tasks/{first_task_id}", "DELETE", token=emp1_token)
    record_test(
        "TC-RBAC-02",
        "RBAC",
        "Employee deleting task",
        f"/tasks/{first_task_id}",
        "DELETE",
        "Employee",
        None,
        403,
        st,
        res,
    )

    # TC-RBAC-03: Employee attempting to list all employees
    st, res = make_api_request("/users/", "GET", token=emp1_token)
    record_test(
        "TC-RBAC-03",
        "RBAC",
        "Employee listing all employees",
        "/users/",
        "GET",
        "Employee",
        None,
        403,
        st,
        res,
    )

    # TC-RBAC-04: Employee attempting to review leave
    first_leave_id = seeded_leave_ids[0]
    st, res = make_api_request(
        f"/leaves/{first_leave_id}", "PATCH", {"status": "APPROVED"}, token=emp1_token
    )
    record_test(
        "TC-RBAC-04",
        "RBAC",
        "Employee reviewing leave",
        f"/leaves/{first_leave_id}",
        "PATCH",
        "Employee",
        {"status": "APPROVED"},
        403,
        st,
        res,
    )

    # TC-RBAC-05: Admin performing create task
    st, res = make_api_request(
        "/tasks/",
        "POST",
        {
            "title": "Admin Valid Task",
            "description": "Desc",
            "priority": "MEDIUM",
            "due_date": "2026-09-01",
            "assigned_to": emp_ids["priya.sharma@company.com"],
        },
        token=admin_token,
    )
    record_test(
        "TC-RBAC-05",
        "RBAC",
        "Admin creating task",
        "/tasks/",
        "POST",
        "Admin",
        {"title": "Admin Valid Task"},
        201,
        st,
        res,
    )

    # TC-RBAC-06: Admin performing list all employees
    st, res = make_api_request("/users/", "GET", token=admin_token)
    record_test(
        "TC-RBAC-06",
        "RBAC",
        "Admin listing all employees",
        "/users/",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # ====================================================
    # 3. USER PROFILE TESTS
    # ====================================================
    # TC-PROF-01: GET /users/me as Admin
    st, res = make_api_request("/users/me", "GET", token=admin_token)
    record_test(
        "TC-PROF-01",
        "User Profile",
        "GET /users/me as Admin",
        "/users/me",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-PROF-02: GET /users/me as Employee
    st, res = make_api_request("/users/me", "GET", token=emp1_token)
    record_test(
        "TC-PROF-02",
        "User Profile",
        "GET /users/me as Employee",
        "/users/me",
        "GET",
        "Employee",
        None,
        200,
        st,
        res,
    )

    # TC-PROF-03: PATCH /users/me as Employee
    st, res = make_api_request(
        "/users/me", "PATCH", {"full_name": "Priya S. Sharma"}, token=emp1_token
    )
    record_test(
        "TC-PROF-03",
        "User Profile",
        "PATCH /users/me as Employee",
        "/users/me",
        "PATCH",
        "Employee",
        {"full_name": "Priya S. Sharma"},
        200,
        st,
        res,
    )

    # TC-PROF-04: GET /users/ as Admin
    st, res = make_api_request("/users/", "GET", token=admin_token)
    record_test(
        "TC-PROF-04",
        "User Profile",
        "GET /users/ as Admin",
        "/users/",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-PROF-05: GET /users/ as Employee
    st, res = make_api_request("/users/", "GET", token=emp1_token)
    record_test(
        "TC-PROF-05",
        "User Profile",
        "GET /users/ as Employee",
        "/users/",
        "GET",
        "Employee",
        None,
        403,
        st,
        res,
    )

    # ====================================================
    # 4. TASK MANAGEMENT TESTS
    # ====================================================
    # TC-TASK-01: Create task assigned to Admin ID (should fail)
    st, res = make_api_request(
        "/tasks/",
        "POST",
        {
            "title": "Task For Admin",
            "description": "Fail expected",
            "priority": "HIGH",
            "due_date": "2026-09-01",
            "assigned_to": admin_user_id,
        },
        token=admin_token,
    )
    record_test(
        "TC-TASK-01",
        "Task Management",
        "Create task assigned to ADMIN ID",
        "/tasks/",
        "POST",
        "Admin",
        {"assigned_to": admin_user_id},
        400,
        st,
        res,
    )

    # TC-TASK-02: Create task assigned to non-existent user ID
    st, res = make_api_request(
        "/tasks/",
        "POST",
        {
            "title": "Task For Nonexistent User",
            "description": "Fail expected",
            "priority": "HIGH",
            "due_date": "2026-09-01",
            "assigned_to": 99999,
        },
        token=admin_token,
    )
    record_test(
        "TC-TASK-02",
        "Task Management",
        "Create task assigned to non-existent ID",
        "/tasks/",
        "POST",
        "Admin",
        {"assigned_to": 99999},
        404,
        st,
        res,
    )

    # TC-TASK-03: Create task with missing required fields
    st, res = make_api_request(
        "/tasks/", "POST", {"description": "Incomplete task"}, token=admin_token
    )
    record_test(
        "TC-TASK-03",
        "Task Management",
        "Create task missing required fields",
        "/tasks/",
        "POST",
        "Admin",
        {"description": "Incomplete task"},
        422,
        st,
        res,
    )

    # TC-TASK-04: Create task with invalid priority enum
    st, res = make_api_request(
        "/tasks/",
        "POST",
        {
            "title": "Task Invalid Enum",
            "description": "Desc",
            "priority": "CRITICAL",
            "due_date": "2026-09-01",
            "assigned_to": emp_ids["priya.sharma@company.com"],
        },
        token=admin_token,
    )
    record_test(
        "TC-TASK-04",
        "Task Management",
        "Create task invalid priority enum",
        "/tasks/",
        "POST",
        "Admin",
        {"priority": "CRITICAL"},
        422,
        st,
        res,
    )

    # TC-TASK-05: List tasks as Admin (all tasks)
    st, res = make_api_request("/tasks/", "GET", token=admin_token)
    record_test(
        "TC-TASK-05",
        "Task Management",
        "List tasks as Admin",
        "/tasks/",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-06: List tasks as Employee (Priya - own tasks)
    st, res = make_api_request("/tasks/", "GET", token=emp1_token)
    record_test(
        "TC-TASK-06",
        "Task Management",
        "List tasks as Employee with tasks",
        "/tasks/",
        "GET",
        "Employee (Priya)",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-07: List tasks as Employee with zero tasks (Kavya)
    kavya_token = emp_tokens["kavya.nair@company.com"]
    st, res = make_api_request("/tasks/", "GET", token=kavya_token)
    record_test(
        "TC-TASK-07",
        "Task Management",
        "List tasks as Employee with zero tasks",
        "/tasks/",
        "GET",
        "Employee (Kavya)",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-08: Get single task (own task - Priya reading T1)
    st, res = make_api_request(f"/tasks/{seeded_task_ids[0]}", "GET", token=emp1_token)
    record_test(
        "TC-TASK-08",
        "Task Management",
        "Get single task (own task)",
        f"/tasks/{seeded_task_ids[0]}",
        "GET",
        "Employee (Priya)",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-09: Get single task (another employee's task - Priya reading Rohan's task)
    rohan_task_id = seeded_task_ids[3]
    st, res = make_api_request(f"/tasks/{rohan_task_id}", "GET", token=emp1_token)
    record_test(
        "TC-TASK-09",
        "Task Management",
        "Get single task (another employee's task)",
        f"/tasks/{rohan_task_id}",
        "GET",
        "Employee (Priya)",
        None,
        403,
        st,
        res,
    )

    # TC-TASK-10: Get single task (non-existent ID)
    st, res = make_api_request("/tasks/99999", "GET", token=admin_token)
    record_test(
        "TC-TASK-10",
        "Task Management",
        "Get single task non-existent ID",
        "/tasks/99999",
        "GET",
        "Admin",
        None,
        404,
        st,
        res,
    )

    # TC-TASK-11: Update task status as assigned employee
    st, res = make_api_request(
        f"/tasks/{seeded_task_ids[2]}", "PATCH", {"status": "IN_PROGRESS"}, token=emp1_token
    )
    record_test(
        "TC-TASK-11",
        "Task Management",
        "Update status as assigned employee",
        f"/tasks/{seeded_task_ids[2]}",
        "PATCH",
        "Employee (Priya)",
        {"status": "IN_PROGRESS"},
        200,
        st,
        res,
    )

    # TC-TASK-12: Employee attempting to edit title/priority/assigned_to
    st, res = make_api_request(
        f"/tasks/{seeded_task_ids[2]}",
        "PATCH",
        {"title": "Hacked Title", "priority": "HIGH"},
        token=emp1_token,
    )
    record_test(
        "TC-TASK-12",
        "Task Management",
        "Employee editing title/priority",
        f"/tasks/{seeded_task_ids[2]}",
        "PATCH",
        "Employee (Priya)",
        {"title": "Hacked Title"},
        403,
        st,
        res,
    )

    # TC-TASK-13: Delete task as Admin
    task_to_del = seeded_task_ids[-1]
    st, res = make_api_request(f"/tasks/{task_to_del}", "DELETE", token=admin_token)
    record_test(
        "TC-TASK-13",
        "Task Management",
        "Delete task as Admin",
        f"/tasks/{task_to_del}",
        "DELETE",
        "Admin",
        None,
        204,
        st,
        res,
    )

    # TC-TASK-14: Delete task as Employee
    st, res = make_api_request(f"/tasks/{seeded_task_ids[0]}", "DELETE", token=emp1_token)
    record_test(
        "TC-TASK-14",
        "Task Management",
        "Delete task as Employee",
        f"/tasks/{seeded_task_ids[0]}",
        "DELETE",
        "Employee",
        None,
        403,
        st,
        res,
    )

    # TC-TASK-15: Filtering ?status=PENDING
    st, res = make_api_request("/tasks/?status=PENDING", "GET", token=admin_token)
    record_test(
        "TC-TASK-15",
        "Task Management",
        "Filter tasks by status=PENDING",
        "/tasks/?status=PENDING",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-16: Filtering ?status=COMPLETED
    st, res = make_api_request("/tasks/?status=COMPLETED", "GET", token=admin_token)
    record_test(
        "TC-TASK-16",
        "Task Management",
        "Filter tasks by status=COMPLETED",
        "/tasks/?status=COMPLETED",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-17: Filtering ?priority=HIGH
    st, res = make_api_request("/tasks/?priority=HIGH", "GET", token=admin_token)
    record_test(
        "TC-TASK-17",
        "Task Management",
        "Filter tasks by priority=HIGH",
        "/tasks/?priority=HIGH",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-18: Sorting ?sort_by=due_date
    st, res = make_api_request("/tasks/?sort_by=due_date", "GET", token=admin_token)
    record_test(
        "TC-TASK-18",
        "Task Management",
        "Sort tasks by due_date",
        "/tasks/?sort_by=due_date",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-TASK-19: Sorting ?sort_by=invalid_column
    st, res = make_api_request("/tasks/?sort_by=invalid_column", "GET", token=admin_token)
    record_test(
        "TC-TASK-19",
        "Task Management",
        "Sort tasks by invalid column",
        "/tasks/?sort_by=invalid_column",
        "GET",
        "Admin",
        None,
        400,
        st,
        res,
    )

    # TC-TASK-20: Pagination ?skip=0&limit=3 and ?skip=3&limit=3
    st1, res1 = make_api_request("/tasks/?skip=0&limit=3", "GET", token=admin_token)
    st2, res2 = make_api_request("/tasks/?skip=3&limit=3", "GET", token=admin_token)
    pag_passed = st1 == 200 and st2 == 200
    if pag_passed and isinstance(res1, list) and isinstance(res2, list):
        ids1 = {t["id"] for t in res1}
        ids2 = {t["id"] for t in res2}
        if ids1.intersection(ids2):
            pag_passed = False
    record_test(
        "TC-TASK-20",
        "Task Management",
        "Pagination skip/limit no overlap",
        "/tasks/?skip=0&limit=3",
        "GET",
        "Admin",
        None,
        200,
        200 if pag_passed else 500,
        res1,
    )

    # ====================================================
    # 5. LEAVE MANAGEMENT TESTS
    # ====================================================
    # TC-LEAV-01: Submit leave request: valid
    st, res = make_api_request(
        "/leaves/",
        "POST",
        {"reason": "Conference Attendance", "start_date": "2026-10-01", "end_date": "2026-10-03"},
        token=emp1_token,
    )
    submitted_leave_id = res.get("id") if st == 201 else None
    record_test(
        "TC-LEAV-01",
        "Leave Management",
        "Submit valid leave request",
        "/leaves/",
        "POST",
        "Employee (Priya)",
        {"reason": "Conference Attendance"},
        201,
        st,
        res,
    )

    # TC-LEAV-02: Submit leave request: end_date before start_date
    st, res = make_api_request(
        "/leaves/",
        "POST",
        {"reason": "Time travel", "start_date": "2026-10-10", "end_date": "2026-10-05"},
        token=emp1_token,
    )
    record_test(
        "TC-LEAV-02",
        "Leave Management",
        "Submit leave with end_date < start_date",
        "/leaves/",
        "POST",
        "Employee (Priya)",
        {"start_date": "2026-10-10", "end_date": "2026-10-05"},
        400,
        st,
        res,
    )

    # TC-LEAV-03: Submit leave request: missing reason
    st, res = make_api_request(
        "/leaves/", "POST", {"start_date": "2026-10-01", "end_date": "2026-10-03"}, token=emp1_token
    )
    record_test(
        "TC-LEAV-03",
        "Leave Management",
        "Submit leave missing reason",
        "/leaves/",
        "POST",
        "Employee (Priya)",
        {"start_date": "2026-10-01"},
        422,
        st,
        res,
    )

    # TC-LEAV-04: List leaves as Admin
    st, res = make_api_request("/leaves/", "GET", token=admin_token)
    record_test(
        "TC-LEAV-04",
        "Leave Management",
        "List leaves as Admin",
        "/leaves/",
        "GET",
        "Admin",
        None,
        200,
        st,
        res,
    )

    # TC-LEAV-05: List leaves as Employee
    st, res = make_api_request("/leaves/", "GET", token=emp1_token)
    record_test(
        "TC-LEAV-05",
        "Leave Management",
        "List leaves as Employee",
        "/leaves/",
        "GET",
        "Employee (Priya)",
        None,
        200,
        st,
        res,
    )

    # TC-LEAV-06: Approve leave as Admin
    new_leave_id = seeded_leave_ids[2]  # Sneha's PENDING leave
    st, res = make_api_request(
        f"/leaves/{new_leave_id}", "PATCH", {"status": "APPROVED"}, token=admin_token
    )
    record_test(
        "TC-LEAV-06",
        "Leave Management",
        "Approve leave as Admin",
        f"/leaves/{new_leave_id}",
        "PATCH",
        "Admin",
        {"status": "APPROVED"},
        200,
        st,
        res,
    )

    # TC-LEAV-07: Reject leave as Admin
    target_reject_id = submitted_leave_id if submitted_leave_id else seeded_leave_ids[2]
    st, res = make_api_request(
        f"/leaves/{target_reject_id}", "PATCH", {"status": "REJECTED"}, token=admin_token
    )
    record_test(
        "TC-LEAV-07",
        "Leave Management",
        "Reject leave as Admin",
        f"/leaves/{target_reject_id}",
        "PATCH",
        "Admin",
        {"status": "REJECTED"},
        200,
        st,
        res,
    )

    # TC-LEAV-08: Employee attempting to approve/reject leave
    st, res = make_api_request(
        f"/leaves/{new_leave_id}", "PATCH", {"status": "APPROVED"}, token=emp1_token
    )
    record_test(
        "TC-LEAV-08",
        "Leave Management",
        "Employee reviewing leave",
        f"/leaves/{new_leave_id}",
        "PATCH",
        "Employee",
        {"status": "APPROVED"},
        403,
        st,
        res,
    )

    # TC-LEAV-09: Review non-existent leave ID
    st, res = make_api_request("/leaves/99999", "PATCH", {"status": "APPROVED"}, token=admin_token)
    record_test(
        "TC-LEAV-09",
        "Leave Management",
        "Review non-existent leave ID",
        "/leaves/99999",
        "PATCH",
        "Admin",
        {"status": "APPROVED"},
        404,
        st,
        res,
    )

    # TC-LEAV-10: Double-review (re-reviewing an already approved leave)
    st, res = make_api_request(
        f"/leaves/{new_leave_id}", "PATCH", {"status": "APPROVED"}, token=admin_token
    )
    record_test(
        "TC-LEAV-10",
        "Leave Management",
        "Double-review an already reviewed leave",
        f"/leaves/{new_leave_id}",
        "PATCH",
        "Admin",
        {"status": "APPROVED"},
        400,
        st,
        res,
    )

    # ====================================================
    # 6. CROSS-CUTTING TESTS
    # ====================================================
    # TC-CROSS-01: Root endpoint GET /
    st, res = make_api_request("/", "GET")
    record_test(
        "TC-CROSS-01",
        "Cross-cutting",
        "Root endpoint GET /",
        "/",
        "GET",
        "Public",
        None,
        200,
        st,
        res,
    )

    # TC-CROSS-02: Invalid route GET /invalid-route
    st, res = make_api_request("/invalid-route-xyz", "GET")
    record_test(
        "TC-CROSS-02",
        "Cross-cutting",
        "Invalid route GET /invalid-route-xyz",
        "/invalid-route-xyz",
        "GET",
        "Public",
        None,
        404,
        st,
        res,
    )

    # Write JSON results dump
    with open("test_results.json", "w") as f:
        json.dump(test_results, f, indent=2)

    total = len(test_results)
    passed_count = sum(1 for t in test_results if t["passed"])
    failed_count = total - passed_count
    print("\n==========================================================")
    print(f"   SUMMARY: Total: {total} | Passed: {passed_count} | Failed: {failed_count}")
    print("==========================================================")


if __name__ == "__main__":
    run_all_qa_tests()
