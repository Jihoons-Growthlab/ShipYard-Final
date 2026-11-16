from app.services.usage import feature_of


def logs(conn):
    return [dict(r) for r in conn.execute("SELECT EmpNo, Method, Path, Status FROM TB_SYS_LogApi ORDER BY LogApiId")]


def test_records_template_path_and_user(client, login, conn):
    h = login("park.pm")
    conn.execute("DELETE FROM TB_SYS_LogApi")
    client.get("/api/health")
    client.get("/api/plans/1", headers=h)
    client.get("/api/hulls/8001/plans", headers=h)
    client.get("/api/usage/summary", headers=h)
    client.get("/api/users", headers=h)
    client.get("/api/hulls")
    rows = logs(conn)
    assert rows == [
        {"EmpNo": "park.pm", "Method": "GET", "Path": "/api/plans/{plan_id}", "Status": 200},
        {"EmpNo": "park.pm", "Method": "GET", "Path": "/api/hulls/{hull_no}/plans", "Status": 200},
        {"EmpNo": "park.pm", "Method": "GET", "Path": "/api/users", "Status": 403},
        {"EmpNo": None, "Method": "GET", "Path": "/api/hulls", "Status": 401},
    ]
    assert conn.execute("SELECT MIN(DurationMs) >= 0, MIN(length(CallDt)) FROM TB_SYS_LogApi").fetchone()[:] == (1, 19)


def test_feature_map():
    assert feature_of("/api/hulls/{hull_no}/plans") == "공정 계획"
    assert feature_of("/api/hulls/{hull_no}/progress-targets") == "호선 관리"
    assert feature_of("/api/progress-hulls") == "공정 실적"
    assert feature_of("/api/auth-groups") == "회원관리"
    assert feature_of("/api/auth/login") == "로그인·인증"
    assert feature_of("/api/me/menu") == "공통(메뉴·세션)"
    assert feature_of("/api/weather") == "날씨"
    assert feature_of("/api/x") == "기타"


def test_admin_only_and_days(client, login):
    assert client.get("/api/usage/summary", headers=login("lee.dwg")).status_code == 403
    assert "M92" not in {m["menu_id"] for m in client.get("/api/me/menu", headers=login("park.pm")).json()}
    h = login("admin")
    for d in ("5", "abc", "365"):
        r = client.get("/api/usage/summary", params={"days": d}, headers=h)
        assert r.status_code == 400 and r.json()["message"] == "조회 기간은 7, 30, 90일 중 하나입니다."
    b = client.get("/api/usage/summary", params={"days": 30}, headers=h).json()
    assert len(b["daily"]) == 30 and len(b["hours"]) == 24
    assert [x["date"] for x in b["daily"]] == sorted(x["date"] for x in b["daily"])


def test_summary_and_emp_filter(client, login):
    pm = login("park.pm")
    qa = login("choi.qa")
    client.get("/api/hulls", headers=pm)
    client.get("/api/drawings/99999", headers=qa)
    client.post("/api/me/menu-access", json={"menu_id": "M11"}, headers=pm)
    h = login("admin")
    b = client.get("/api/usage/summary", headers=h).json()
    assert b["kpi"]["calls"] >= 3 and b["kpi"]["logins"] >= 3 and b["kpi"]["errors"] >= 1
    assert b["demo_calls"] == 0
    assert any(e["status"] == 404 and e["emp_no"] == "choi.qa" for e in b["recent_errors"])
    assert {"M11"} <= {m["menu_id"] for m in b["menus"]}
    assert b["top_users"] and set(b["top_users"][0]) == {"emp_no", "display_name", "calls", "last_dt", "top_feature"}
    f = client.get("/api/usage/summary", params={"emp_no": "park.pm"}, headers=h).json()
    assert [u["emp_no"] for u in f["top_users"]] == ["park.pm"] and f["emp_no"] == "park.pm"
    assert all(m["users"] == 1 for m in f["menus"])
    assert sum(d["calls"] for d in f["daily"]) == f["kpi"]["calls"] == sum(f["hours"])
