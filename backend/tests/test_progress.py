from tests.helpers import HULL, mk_plan


def test_prog_t01_targets(client, login):
    h = login("choi.qa")
    ph = client.get("/api/progress-hulls", headers=h).json()
    assert ph["default_hull_no"] == "8001"
    assert HULL not in [x["hull_no"] for x in ph["hulls"]]
    assert set(ph["hulls"][0]) == {"hull_no", "hull_nm", "hull_status"}
    t = client.get("/api/hulls/8001/progress-targets", headers=h).json()
    assert t["today"] == "2026-10-19" and t["plans"]
    assert all(p["plan_status"] in ("READY", "WORK", "DELAY") for p in t["plans"])
    assert set(t["plans"][0]) == {"plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt", "actual_end_dt",
                                  "progress_rate", "plan_status", "manager_emp_no", "manager_nm", "drawing_wait"}
    full = client.get("/api/hulls/8001/progress-targets", params={"include_done": "true"}, headers=h).json()
    plans = client.get("/api/hulls/8001/plans", headers=h).json()["plans"]
    assert [p["plan_id"] for p in full["plans"]] == [p["plan_id"] for p in plans]


def test_prog_t02_t03_same_day_and_last_rate(client, login):
    h = login("park.pm")
    pid = mk_plan(client, h, "2026-10-01", "2026-10-31")
    url = f"/api/plans/{pid}/progress"
    client.put(f"{url}/2026-10-15", json={"progress_rate": 40, "man_hour": 8, "worker_cnt": 2, "worker_emp_no": "han.wk"}, headers=h)
    r = client.put(f"{url}/2026-10-15", json={"progress_rate": 50, "man_hour": 10}, headers=h)
    b = r.json()
    assert len(b["history"]) == 1 and b["history"][0]["progress_rate"] == 50 and b["history"][0]["man_hour"] == 10
    client.put(f"{url}/2026-10-10", json={"progress_rate": 20}, headers=h)
    b = client.put(f"{url}/2026-10-18", json={"progress_rate": 30, "worker_emp_no": "han.wk", "man_hour": -1}, headers=h).json()
    assert [x["work_dt"] for x in b["history"]] == ["2026-10-18", "2026-10-15", "2026-10-10"]
    assert b["history"][0]["worker_nm"] == "한현장"
    assert b["plan"]["progress_rate"] == 30  # 마지막 작업일의 누적률(역행 허용, 합산 안 함)
    assert b["plan"]["actual_start_dt"] == "2026-10-10" and b["plan"]["actual_end_dt"] is None
    assert b["plan"]["plan_status"] == "WORK"
    g = client.get(url, headers=h).json()
    assert g["history"] == b["history"]


def test_prog_t04_rejections(client, login):
    h = login("park.pm")
    pid = mk_plan(client, h, "2026-10-01", "2026-10-31")
    cases = [
        ("2026-10-20", {"progress_rate": 10}, "work_dt", "미래 일자의 실적은 입력할 수 없습니다."),
        ("2026-13-01", {"progress_rate": 10}, "work_dt", "작업일을 입력하세요."),
        ("2026-10-10", {"progress_rate": 101}, "progress_rate", "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-10", {"progress_rate": -1}, "progress_rate", "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-10", {}, "progress_rate", "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-10", {"progress_rate": 10, "worker_emp_no": "jung.new"}, "worker_emp_no",
         "승인된 회원만 작업자로 지정할 수 있습니다."),
    ]
    for d, body, field, msg in cases:
        r = client.put(f"/api/plans/{pid}/progress/{d}", json=body, headers=h)
        assert r.status_code == 400 and r.json()["details"]["field"] == field and r.json()["message"] == msg, (d, body)
    assert client.put("/api/plans/999999/progress/2026-10-10", json={"progress_rate": 1}, headers=h).status_code == 404
    assert client.delete("/api/progress/999999", headers=h).json()["code"] == "PROGRESS_NOT_FOUND"


def test_prog_t05_done_and_revert(client, login):
    h = login("park.pm")
    pid = mk_plan(client, h, "2026-11-01", "2026-11-10")
    b = client.put(f"/api/plans/{pid}/progress/2026-10-19", json={"progress_rate": 100}, headers=h).json()
    p = b["plan"]
    assert p["plan_status"] == "DONE" and p["actual_end_dt"] == "2026-10-19" and p["actual_start_dt"] == "2026-10-19"
    b = client.delete(f"/api/progress/{b['history'][0]['progress_id']}", headers=h).json()
    p = b["plan"]
    assert b["history"] == [] and p["progress_rate"] == 0 and p["actual_start_dt"] is None and p["actual_end_dt"] is None
    assert p["plan_status"] == "READY"


def test_status_delay_and_hull_transitions(client, login, conn):
    h = login("park.pm")
    conn.execute("UPDATE TB_MST_Hull SET HullStatus='DESIGN' WHERE HullNo=?", (HULL,))
    late = mk_plan(client, h, "2026-10-01", "2026-10-10")
    assert client.get(f"/api/plans/{late}", headers=h).json()["plan_status"] == "DELAY"  # 미착수·종료 경과
    work = mk_plan(client, h, "2026-10-01", "2026-10-31")
    client.put(f"/api/plans/{work}/progress/2026-10-12", json={"progress_rate": 10}, headers=h)
    assert conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo=?", (HULL,)).fetchone()[0] == "BUILD"
    launch = mk_plan(client, h, "2026-10-15", "2026-10-25", proc_cd="LAUNCH")
    client.put(f"/api/plans/{launch}/progress/2026-10-18", json={"progress_rate": 100}, headers=h)
    assert conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo=?", (HULL,)).fetchone()[0] == "LAUNCH"
    late_work = mk_plan(client, h, "2026-10-01", "2026-10-05")
    client.put(f"/api/plans/{late_work}/progress/2026-10-03", json={"progress_rate": 50}, headers=h)
    assert client.get(f"/api/plans/{late_work}", headers=h).json()["plan_status"] == "DELAY"


def test_prog_t06_permissions(client, login):
    h = login("choi.qa")
    r = client.put("/api/plans/1/progress/2026-10-10", json={"progress_rate": 10}, headers=h)
    assert r.status_code == 403 and r.json()["details"] == {"menu_id": "M22"}
    assert client.delete("/api/progress/1", headers=h).status_code == 403
    assert client.get("/api/plans/1/progress", headers=h).status_code == 200
    assert client.get("/api/progress-hulls", headers=login("lee.dwg")).status_code == 403
