from app.services import rules
from tests.helpers import HULL, add_drawing, mk_plan


def plan(client, h, pid):
    return client.get(f"/api/plans/{pid}", headers=h).json()


def test_plan_list_shape_and_order(client, login):
    h = login("choi.qa")
    b = client.get("/api/hulls/8001/plans", headers=h).json()
    assert b["hull_no"] == "8001" and b["hull_progress"] == 65 and b["today"] == "2026-10-19"
    p = b["plans"][0]
    assert p["label"] == f"[{p['block_cd']}] {p['proc_nm']}" and p["block_cd"] == "101" and p["proc_cd"] == "CUT"
    keys = {"plan_id", "hull_no", "block_id", "block_cd", "block_nm", "proc_cd", "proc_nm", "label", "plan_start_dt",
            "plan_end_dt", "actual_start_dt", "actual_end_dt", "progress_rate", "plan_status", "manager_emp_no",
            "manager_nm", "remark", "create_user_id", "create_dt", "pred_plan_ids", "gate_ok", "blockers", "drawing_wait"}
    assert keys == set(p)
    cds = [x["block_cd"] for x in b["plans"]]
    nums = [int(c) for c in cds if c and c.isdigit()]
    assert nums == sorted(nums)
    if None in cds:
        assert all(c is None for c in cds[cds.index(None):])
        nb = next(x for x in b["plans"] if x["block_cd"] is None)
        assert nb["label"] == f"[8001] {nb['proc_nm']}"
    assert all({"plan_id", "pred_plan_id"} == set(d) for d in b["deps"]) and b["deps"]
    f = client.get("/api/hulls/8001/plans", params={"block_id": 1}, headers=h).json()
    assert f["hull_progress"] == 65 and all(x["block_id"] == 1 for x in f["plans"])
    ids = {x["plan_id"] for x in f["plans"]}
    assert all(d["plan_id"] in ids and d["pred_plan_id"] in ids for d in f["deps"])
    empty = client.get(f"/api/hulls/{HULL}/plans", headers=h).json()
    assert empty["plans"] == [] and empty["hull_progress"] is None


def test_procs_and_plan_hulls(client, login):
    h = login("choi.qa")
    pr = client.get("/api/procs", headers=h).json()
    assert pr[0] == {"proc_cd": "CUT", "proc_nm": "강재절단", "proc_group": "HULL", "std_days": 14, "seq": 1}
    ph = client.get("/api/plan-hulls", headers=h).json()
    assert {x["hull_no"]: x["plan_count"] for x in ph}[HULL] == 0
    assert sum(x["plan_count"] for x in ph) == 83


def test_plan_t02_validation(client, login):
    h = login("park.pm")
    cases = [
        ({"plan_start_dt": None}, "plan_start_dt", "계획 시작/종료일을 입력하세요."),
        ({"plan_end_dt": ""}, "plan_end_dt", "계획 시작/종료일을 입력하세요."),
        ({"plan_end_dt": "2026-10-31"}, "plan_end_dt", "계획 종료일이 시작일보다 빠릅니다."),
        ({"block_id": 1}, "block_id", "해당 호선의 블록이 아닙니다."),
        ({"proc_cd": "XXX"}, "proc_cd", "허용되지 않는 공정 코드입니다."),
        ({"manager_emp_no": "jung.new"}, "manager_emp_no", "승인된 회원만 담당자로 지정할 수 있습니다."),
    ]
    base = {"proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-10"}
    for patch, field, msg in cases:
        r = client.post(f"/api/hulls/{HULL}/plans", json={**base, **patch}, headers=h)
        assert r.status_code == 400 and r.json()["details"]["field"] == field and r.json()["message"] == msg, patch
    pid = mk_plan(client, h, "2026-11-01", "2026-11-10", manager_emp_no="park.pm", remark="메모")
    p = plan(client, h, pid)
    assert p["plan_status"] == "READY" and p["progress_rate"] == 0 and p["manager_nm"] == "박공정"
    assert p["create_user_id"] == "park.pm" and p["create_dt"] == "2026-10-19"
    assert client.get("/api/plans/999999", headers=h).json()["code"] == "PLAN_NOT_FOUND"


def test_plan_t03_self_cycle_other_hull(client, login):
    h = login("park.pm")
    a = mk_plan(client, h, "2026-11-01", "2026-11-05")
    b = mk_plan(client, h, "2026-11-06", "2026-11-10", [a])
    c = mk_plan(client, h, "2026-11-11", "2026-11-15", [b])
    r = client.put(f"/api/plans/{a}/predecessors", json={"pred_plan_ids": [a]}, headers=h)
    assert r.status_code == 400 and r.json()["code"] == "PLAN_DEPENDENCY_SELF"
    assert r.json()["message"] == "자기 자신을 선행 공정으로 지정할 수 없습니다."
    r = client.put(f"/api/plans/{a}/predecessors", json={"pred_plan_ids": [c], "confirm_late_preds": True}, headers=h)
    assert r.status_code == 400 and r.json()["code"] == "PLAN_DEPENDENCY_CYCLE"
    assert r.json()["message"] == "선행 공정이 순환 구조를 만듭니다."
    r = client.put(f"/api/plans/{a}/predecessors", json={"pred_plan_ids": [1]}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "선행 공정은 같은 호선의 공정이어야 합니다."
    r = client.patch(f"/api/plans/{a}", json={"pred_plan_ids": [c], "confirm_late_preds": True}, headers=h)
    assert r.json()["code"] == "PLAN_DEPENDENCY_CYCLE"


def test_plan_t04_late_pred_confirm(client, login, conn):
    h = login("park.pm")
    a = mk_plan(client, h, "2026-11-01", "2026-11-14")
    r = mk_plan(client, h, "2026-11-10", "2026-11-20", [a], expect=409)
    assert r["code"] == "PRED_LATE_CONFIRM_REQUIRED" and r["details"]["late_pred_plan_ids"] == [a]
    assert r["message"] == "선행 공정 종료일이 이 공정의 시작일보다 늦습니다. 그대로 저장할까요?"
    n = conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE HullNo=?", (HULL,)).fetchone()[0]
    assert n == 1  # 취소(재전송 안 함) → 변경 없음
    b = mk_plan(client, h, "2026-11-10", "2026-11-20", [a], confirm_late_preds=True)
    assert plan(client, h, b)["pred_plan_ids"] == [a]
    assert conn.execute("SELECT LagDays FROM TB_PRC_PlanDep WHERE PlanId=?", (b,)).fetchone()[0] == 0
    # 일반 PATCH는 일정 자동 조정 없음
    client.patch(f"/api/plans/{a}", json={"plan_end_dt": "2026-11-30"}, headers=h)
    assert plan(client, h, b)["plan_start_dt"] == "2026-11-10"


def test_plan_t05_t06_t08_gate(client, login, conn):
    h = login("park.pm")
    a = mk_plan(client, h, "2026-10-20", "2026-10-31")
    b = mk_plan(client, h, "2026-11-01", "2026-11-10", [a])
    assert plan(client, h, b)["plan_status"] == "PLAN"  # 선행 미완료
    assert client.put(f"/api/plans/{a}/progress/2026-10-19", json={"progress_rate": 100}, headers=h).status_code == 200
    assert plan(client, h, a)["plan_status"] == "DONE"
    assert plan(client, h, b)["plan_status"] == "READY"
    issued = add_drawing(conn, "T-ISSUED", True)
    draft = add_drawing(conn, "T-DRAFT", False)
    r = client.post(f"/api/plans/{b}/drawings", json={"drawing_id": issued, "required": True}, headers=h)
    assert r.status_code == 201 and r.json()["links"][0]["has_issued"] is True
    assert r.json()["links"][0]["need_dt"] == "2026-11-01"
    assert plan(client, h, b)["plan_status"] == "READY"  # T05
    r = client.post(f"/api/plans/{b}/drawings", json={"drawing_id": draft}, headers=h)
    assert r.json()["blockers"] == [{"drawing_id": draft, "drawing_no": "T-DRAFT", "dwg_status": "DRAFT"}]
    p = plan(client, h, b)
    assert p["plan_status"] == "PLAN" and p["drawing_wait"] is True and p["gate_ok"] is False  # T06
    # APPROVED만으로는 통과 못함
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus='APPROVED' WHERE DrawingId=?", (draft,))
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='APPROVED' WHERE DrawingId=?", (draft,))
    rules.recalc_hull(conn, HULL)
    assert plan(client, h, b)["plan_status"] == "PLAN"
    # 배포 후 갱신
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus='ISSUED' WHERE DrawingId=?", (draft,))
    rules.recalc_hull(conn, HULL)
    assert plan(client, h, b)["plan_status"] == "READY"
    # T08: 참고 연계는 게이트 아님, 해제 시 재계산
    draft2 = add_drawing(conn, "T-DRAFT2", False)
    client.post(f"/api/plans/{b}/drawings", json={"drawing_id": draft2, "required": False}, headers=h)
    assert plan(client, h, b)["plan_status"] == "READY"
    client.delete(f"/api/plans/{b}/drawings/{draft2}", headers=h)
    draft3 = add_drawing(conn, "T-DRAFT3", False)
    client.post(f"/api/plans/{b}/drawings", json={"drawing_id": draft3}, headers=h)
    assert plan(client, h, b)["plan_status"] == "PLAN"
    assert client.delete(f"/api/plans/{b}/drawings/{draft3}", headers=h).status_code == 204
    assert plan(client, h, b)["plan_status"] == "READY"
    # OBSOLETE 도면은 blocker 아님
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='OBSOLETE' WHERE DrawingId=?", (draft3,))
    client.post(f"/api/plans/{b}/drawings", json={"drawing_id": draft3}, headers=h)
    assert plan(client, h, b)["plan_status"] == "READY"


def test_plan_link_errors(client, login):
    h = login("park.pm")
    pid = mk_plan(client, h, "2026-11-01", "2026-11-10")
    r = client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": 1}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "같은 호선의 도면만 연계할 수 있습니다."
    assert client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": 99999}, headers=h).json()["code"] == "DRAWING_NOT_FOUND"
    assert client.delete(f"/api/plans/{pid}/drawings/1", headers=h).json()["code"] == "LINK_NOT_FOUND"
    d = client.get("/api/plans/1/drawings", headers=h).json()
    assert d["links"] and all(x["drawing_id"] not in {l["drawing_id"] for l in d["links"]} for x in d["available"])
    linked = d["links"][0]["drawing_id"]
    r = client.post("/api/plans/1/drawings", json={"drawing_id": linked}, headers=h)
    assert r.status_code == 409 and r.json()["message"] == "이미 연계된 도면입니다."


def test_plan_t07_delete_no_orphans(client, login, conn):
    h = login("park.pm")
    a = mk_plan(client, h, "2026-10-01", "2026-10-31")
    b = mk_plan(client, h, "2026-11-01", "2026-11-10", [a])
    client.put(f"/api/plans/{a}/progress/2026-10-10", json={"progress_rate": 30}, headers=h)
    client.post(f"/api/plans/{a}/drawings", json={"drawing_id": add_drawing(conn, "T-X", False)}, headers=h)
    assert client.delete(f"/api/plans/{a}", headers=h).status_code == 204
    for t in ("TB_PRC_Progress", "TB_DWG_PlanLink"):
        assert conn.execute(f"SELECT COUNT(*) FROM {t} WHERE PlanId=?", (a,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_PlanDep WHERE PredPlanId=? OR PlanId=?", (a, a)).fetchone()[0] == 0
    assert plan(client, h, b)["pred_plan_ids"] == [] and plan(client, h, b)["plan_status"] == "READY"


def test_plan_t10_schedule_cascade(client, login):
    h = login("park.pm")
    a = mk_plan(client, h, "2026-11-01", "2026-11-14")
    b = mk_plan(client, h, "2026-11-15", "2026-11-20", [a])
    c = mk_plan(client, h, "2026-11-25", "2026-11-30", [b])
    d = mk_plan(client, h, "2026-11-02", "2026-11-05")

    def dates(pid):
        p = plan(client, h, pid)
        return p["plan_start_dt"], p["plan_end_dt"]

    r = client.patch(f"/api/plans/{a}/schedule", json={"plan_start_dt": "2026-11-07", "plan_end_dt": "2026-11-20"}, headers=h)
    assert r.status_code == 200 and r.json()["shifted_plan_ids"] == sorted([b, c])
    assert r.json()["plan"]["plan_start_dt"] == "2026-11-07"
    assert dates(b) == ("2026-11-21", "2026-11-26")
    assert dates(c) == ("2026-11-27", "2026-12-02")
    assert dates(d) == ("2026-11-02", "2026-11-05")
    # 다시 앞당겨도 후행 유지(당기는 조정 없음)
    r = client.patch(f"/api/plans/{a}/schedule", json={"plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-14"}, headers=h)
    assert r.json()["shifted_plan_ids"] == []
    assert dates(b) == ("2026-11-21", "2026-11-26") and dates(c) == ("2026-11-27", "2026-12-02")
    # B를 선행보다 앞으로 → 409, 확인 시 통과
    r = client.patch(f"/api/plans/{b}/schedule", json={"plan_start_dt": "2026-11-10", "plan_end_dt": "2026-11-15"}, headers=h)
    assert r.status_code == 409 and r.json()["details"]["late_pred_plan_ids"] == [a]
    assert dates(b) == ("2026-11-21", "2026-11-26")
    r = client.patch(f"/api/plans/{b}/schedule", json={"plan_start_dt": "2026-11-10", "plan_end_dt": "2026-11-15",
                                                        "confirm_late_preds": True}, headers=h)
    assert r.status_code == 200 and dates(b) == ("2026-11-10", "2026-11-15")
    # 종료일만 바꾸면 선행 검사 없음, 기간 검증은 동일
    r = client.patch(f"/api/plans/{b}/schedule", json={"plan_start_dt": "2026-11-10", "plan_end_dt": "2026-11-09"}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "계획 종료일이 시작일보다 빠릅니다."


def test_plan_t09_view_cannot_write(client, login):
    h = login("choi.qa")
    for method, url, body in [
        ("post", f"/api/hulls/{HULL}/plans", {"proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-02"}),
        ("patch", "/api/plans/1", {"remark": "x"}), ("delete", "/api/plans/1", None),
        ("put", "/api/plans/1/predecessors", {"pred_plan_ids": []}),
        ("patch", "/api/plans/1/schedule", {"plan_start_dt": "2026-06-15", "plan_end_dt": "2026-06-28"}),
        ("post", "/api/plans/1/drawings", {"drawing_id": 1}), ("delete", "/api/plans/1/drawings/1", None),
    ]:
        r = client.request(method, url, json=body, headers=h)
        assert r.status_code == 403 and r.json()["details"] == {"menu_id": "M21"}, url
    assert client.get("/api/plans/1/drawings", headers=h).status_code == 200
