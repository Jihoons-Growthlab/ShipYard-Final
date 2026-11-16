from tests.helpers import HULL, add_drawing, mk_plan


def dash(client, h):
    r = client.get("/api/dashboard/summary", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_shape_and_links(client, login, conn):
    d = dash(client, login("choi.qa"))
    assert d["today"] == "2026-10-19"
    assert set(d["kpi"]) == {"active_hulls", "delay_plans", "waiting_plans", "pending_drawings"}
    assert [d["kpi"][k]["link"]["screen"] for k in ("active_hulls", "delay_plans", "waiting_plans", "pending_drawings")] == \
        ["hull-list", "plan-gantt", "plan-gantt", "dwg-approval"]
    assert d["kpi"]["active_hulls"]["value"] == 4  # 8001·8002 BUILD, 8003 DESIGN, 8005 TRIAL
    assert d["kpi"]["pending_drawings"]["value"] == 6  # REVIEW 4 + APPROVED 2
    assert [s["status"] for s in d["plan_status"]] == ["PLAN", "READY", "WORK", "DONE", "DELAY"]
    assert sum(s["count"] for s in d["plan_status"]) == conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan").fetchone()[0]
    hp = {h["hull_no"]: h for h in d["hull_progress"]}
    assert hp["8004"]["progress"] == 0 and hp["8001"]["progress"] == 65 and hp["8001"]["link"] == {"screen": "plan-gantt", "param": "8001"}
    codes = [x["discipline"] for x in d["drawing_disciplines"]]
    order = ["HULL", "MACH", "ELEC", "PIPE", "OUTFIT"]
    assert codes == [c for c in order if c in codes]
    assert all(set(x["counts"]) == {"ISSUED", "APPROVED", "REVIEW", "DRAFT"} for x in d["drawing_disciplines"])
    assert sum(x["total"] for x in d["drawing_disciplines"]) == conn.execute("SELECT COUNT(*) FROM TB_DWG_Drawing").fetchone()[0]
    months = {x["month"]: x for x in d["deliveries"]}
    assert months["2026-12"] == {"month": "2026-12", "count": 1, "hull_nos": ["8005"]}
    assert [x["month"] for x in d["deliveries"]] == sorted(months)
    for sec in ("delay_list", "waiting_list", "impact_list"):
        assert len(d[sec]["items"]) <= 6 and d[sec]["count"] >= len(d[sec]["items"])
    assert all(i["plan_status"] in ("WORK", "DONE", "DELAY") and i["link"]["screen"] == "drawing" for i in d["impact_list"]["items"])
    assert all(i["link"] == {"screen": "plan-gantt", "param": i["hull_no"]} for i in d["delay_list"]["items"])


def test_progress_and_waiting_update(client, login, conn):
    pm = login("park.pm")
    pid = mk_plan(client, pm, "2026-10-20", "2026-10-29")
    did = add_drawing(conn, "8004-T-1", issued=False)
    before = dash(client, pm)
    client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": did, "required": True}, headers=pm)
    d = dash(client, pm)
    assert d["kpi"]["waiting_plans"]["value"] == before["kpi"]["waiting_plans"]["value"] + 1
    item = next(i for i in d["waiting_list"]["items"] + [None] if i is None or i["plan_id"] == pid) or {}
    if item:
        assert item["blockers"] == ["8004-T-1"]
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'ISSUED' WHERE DrawingId = ?", (did,))
    client.put(f"/api/plans/{pid}/progress/2026-10-19", json={"progress_rate": 100}, headers=pm)
    d = dash(client, pm)
    assert d["kpi"]["waiting_plans"]["value"] == before["kpi"]["waiting_plans"]["value"]
    assert next(h for h in d["hull_progress"] if h["hull_no"] == HULL)["progress"] == 100


def test_list_cap_six(client, login, conn):
    pm = login("park.pm")
    for i in range(8):
        mk_plan(client, pm, "2026-09-01", "2026-09-10", proc_cd="CUT")
    d = dash(client, pm)
    assert d["delay_list"]["count"] >= 8 and len(d["delay_list"]["items"]) == 6


def test_impacts_window(client, login, conn):
    pm = login("park.pm")
    pid = mk_plan(client, pm, "2026-10-01", "2026-12-10")
    did = add_drawing(conn, "8004-T-2", issued=True)
    conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, IssueDt) VALUES (?, 1, 'ISSUED', 'c', '2026-10-15')", (did,))
    conn.execute("INSERT INTO TB_DWG_PlanLink(DrawingId, PlanId, RequiredYN) VALUES (?, ?, 1)", (did, pid))
    ids = lambda: {(i["drawing_id"], i["plan_id"]) for i in rules_items(client, pm)}  # noqa: E731
    assert (did, pid) not in ids()  # PLAN 상태 → 영향 아님
    conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = 'WORK' WHERE PlanId = ?", (pid,))
    assert (did, pid) in ids()


def rules_items(client, h):
    from app.services import rules  # noqa: F401
    return client.get("/api/dashboard/summary", headers=h).json()["impact_list"]["items"]
