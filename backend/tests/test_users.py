NEW = {"last_name": "홍", "first_name": "길동", "birth_date": "1990-01-01", "phone": "010-9999-0000",
       "email": "hong@example.com", "emp_no": "hong.gd", "password": "password1", "groups": ["PROC"]}


def levels(client, h, emp):
    return {m["menu_id"]: m for m in client.get(f"/api/users/{emp}/menus", headers=h).json()["menus"]}


def test_list_filter_and_no_secrets(client, login):
    h = login("admin")
    b = client.get("/api/users", headers=h).json()
    assert b["total"] == len(b["users"]) == 6 and b["pending"] == 1
    u = b["users"][0]
    assert set(u) == {"emp_no", "last_name", "first_name", "display_name", "email", "phone", "birth_date", "status",
                      "totp_enabled", "groups", "created_at"}
    assert "password_hash" not in str(b) and "totp_secret" not in str(b)
    p = client.get("/api/users", params={"status": "pending"}, headers=h).json()
    assert [x["emp_no"] for x in p["users"]] == ["jung.new"] and p["total"] == 1
    q = client.get("/api/users", params={"q": "박공"}, headers=h).json()
    assert [x["emp_no"] for x in q["users"]] == ["park.pm"]
    assert client.get("/api/auth-groups", headers=h).json()[0] == {"code": "ADMIN", "name": "시스템관리자"}


def test_non_admin_forbidden(client, login):
    h = login("park.pm")
    for m, u in [("get", "/api/users"), ("get", "/api/auth-groups"), ("get", "/api/users/admin/menus"),
                 ("put", "/api/users/admin/menus"), ("delete", "/api/users/choi.qa")]:
        r = getattr(client, m)(u, headers=h, **({"json": {"menus": []}} if m == "put" else {}))
        assert r.status_code == 403, u
    assert client.get("/api/users/options", headers=h).status_code == 200


def test_create_validation_and_login(client, login):
    h = login("admin")
    for patch, code in [({"phone": "abc"}, 400), ({"emp_no": "ab"}, 400),
                        ({"password": "short"}, 400), ({"status": "x"}, 400), ({"groups": ["NOPE"]}, 400),
                        ({"totp_enabled": True}, 409)]:
        r = client.post("/api/users", json=NEW | patch, headers=h)
        assert r.status_code == code, (patch, r.text)
    existing = client.get("/api/users/admin", headers=h).json()
    r = client.post("/api/users", json=NEW | {"email": existing["email"]}, headers=h)
    assert r.status_code == 409
    r = client.post("/api/users", json=NEW, headers=h)
    assert r.status_code == 201 and r.json()["status"] == "approved" and r.json()["groups"][0]["code"] == "PROC"
    assert client.post("/api/auth/login", json={"emp_no": "hong.gd", "password": "password1"}).status_code == 200


def test_update_rules(client, login, conn):
    h = login("admin")
    old_hash = conn.execute("SELECT password_hash FROM users WHERE emp_no = 'park.pm'").fetchone()[0]
    r = client.patch("/api/users/park.pm", json={"emp_no": "other"}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "아이디는 변경할 수 없습니다."
    r = client.patch("/api/users/park.pm", json={"last_name": "김", "password": "", "groups": ["DWG"]}, headers=h)
    assert r.status_code == 200 and r.json()["display_name"] == "김공정" and [g["code"] for g in r.json()["groups"]] == ["DWG"]
    assert conn.execute("SELECT password_hash FROM users WHERE emp_no = 'park.pm'").fetchone()[0] == old_hash
    # 그룹 변경 즉시 반영
    pm = login("park.pm")
    assert client.get("/api/drawings", headers=pm).status_code == 200
    assert client.post("/api/hulls/8004/plans", json={}, headers=pm).status_code == 403
    assert client.patch("/api/users/park.pm", json={"groups": []}, headers=h).json()["groups"] == []
    assert client.patch("/api/users/park.pm", json={"password": "1234"}, headers=h).status_code == 400
    r = client.patch("/api/users/park.pm", json={"totp_enabled": True}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "OTP_NOT_ENROLLED"
    r = client.patch("/api/users/lee.dwg", json={"totp_enabled": False}, headers=h)
    assert r.json()["totp_enabled"] is False
    assert conn.execute("SELECT totp_secret FROM users WHERE emp_no = 'lee.dwg'").fetchone()[0]
    admin_email = client.get("/api/users/admin", headers=h).json()["email"]
    assert client.patch("/api/users/lee.dwg", json={"email": admin_email}, headers=h).status_code == 409
    assert client.get("/api/users/nobody", headers=h).json()["code"] == "USER_NOT_FOUND"


def test_approve_reject_delete(client, login, conn):
    h = login("admin")
    r = client.post("/api/users/jung.new/approve", json={"groups": []}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "승인 시 권한 그룹을 1개 이상 지정하세요."
    r = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATUS"
    from tests.conftest import SEED_USERS
    assert client.post("/api/auth/login", json={"emp_no": "jung.new", "password": SEED_USERS["jung.new"]["demo_password"]}).status_code == 200
    r = client.delete("/api/users/admin", headers=h)
    assert r.status_code == 409 and r.json()["code"] == "SELF_DELETE"
    assert client.delete("/api/users/lee.dwg", headers=h).status_code == 204
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_AuthUser WHERE EmpNo = 'lee.dwg'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_DWG_Drawing WHERE DesignerEmpNo = 'lee.dwg' OR CreateUserId = 'lee.dwg'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_DWG_Approval WHERE ApproverEmpNo IS NULL").fetchone()[0] > 0


def test_user_menu_override(client, login, conn):
    h = login("admin")
    m = levels(client, h, "choi.qa")
    assert m["M11"]["group_level"] == 1 and m["M11"]["user_level"] is None and m["M22"]["level"] == 1
    menus = [{"menu_id": "M11", "level": 2}, {"menu_id": "M22", "level": 0}, {"menu_id": "M00", "level": 1},
             {"menu_id": "M91", "level": 2}, {"menu_id": "M90", "level": 1}]
    r = client.put("/api/users/choi.qa/menus", json={"menus": menus}, headers=h)
    assert r.status_code == 200
    stored = dict(conn.execute("SELECT MenuId, AuthGbn FROM TB_SYS_UserMenu WHERE EmpNo = 'choi.qa'").fetchall())
    assert stored == {"M11": "Write", "M22": "None", "M91": "Admin", "M90": "View"}  # M00 그룹과 같아 미저장
    qa = login("choi.qa")
    assert client.post("/api/hulls", json={}, headers=qa).status_code == 400  # 쓰기 권한 → 검증 단계
    assert client.get("/api/progress-hulls", headers=qa).status_code == 403
    assert client.get("/api/users", headers=qa).status_code == 200
    assert "M22" not in {x["menu_id"] for x in client.get("/api/me/menu", headers=qa).json()}
    assert client.put("/api/users/choi.qa/menus", json={"menus": []}, headers=h).status_code == 200
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_UserMenu WHERE EmpNo = 'choi.qa'").fetchone()[0] == 0
    for bad, msg in [({"menu_id": "M99", "level": 1}, "존재하지 않는 메뉴입니다."), ({"menu_id": "M11", "level": 3}, "허용되지 않는 권한입니다."),
                     ({"menu_id": "M11", "level": "x"}, "허용되지 않는 권한입니다.")]:
        r = client.put("/api/users/choi.qa/menus", json={"menus": [bad]}, headers=h)
        assert r.status_code == 400 and r.json()["message"] == msg
    r = client.put("/api/users/admin/menus", json={"menus": [{"menu_id": "M91", "level": 1}]}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "SELF_LOCKOUT"
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_UserMenu WHERE EmpNo = 'admin'").fetchone()[0] == 0
    r = client.put("/api/users/admin/menus", json={"menus": [{"menu_id": "M91", "level": 2}, {"menu_id": "M22", "level": 1}]}, headers=h)
    assert r.status_code == 200 and levels(client, h, "admin")["M22"]["user_level"] == 1
