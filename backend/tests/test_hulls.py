NEW = {"hull_no": "9001", "hull_nm": "Test Ship", "ship_type": "LNG", "owner_nm": "Acme Lines",
       "contract_dt": "2026-01-01", "delivery_dt": "2028-03-31", "length_m": 100.0}


def test_seed_progress_and_list(client, login):
    rows = client.get("/api/hulls", headers=login("choi.qa")).json()
    assert [r["hull_no"] for r in rows] == ["8001", "8002", "8003", "8004", "8005"]
    # 대시보드 기준(공정 없으면 0)은 65,17,0,0,94 — 목록은 공정 없는 8004가 null
    assert [r["progress"] for r in rows] == [65, 17, 0, None, 94]
    assert rows[3]["plan_count"] == 0
    assert sum(r["delay_count"] for r in rows) == 1
    assert {"plan_count", "use_yn", "create_dt", "modify_dt", "dock_no"} <= set(rows[0])


def test_hull_t01_filters(client, login):
    h = login("choi.qa")
    allr = client.get("/api/hulls", headers=h).json()
    build = client.get("/api/hulls", params={"status": "BUILD"}, headers=h).json()
    assert build and all(r["hull_status"] == "BUILD" for r in build)
    lng = client.get("/api/hulls", params={"ship_type": "LNG"}, headers=h).json()
    assert all(r["ship_type"] == "LNG" for r in lng)
    q = client.get("/api/hulls", params={"q": "NORDIC"}, headers=h).json()
    assert q and all("nordic" in (r["owner_nm"] + r["hull_nm"] + r["hull_no"]).lower() for r in q)
    q2 = client.get("/api/hulls", params={"q": "ocean titan"}, headers=h).json()
    assert [r["hull_no"] for r in q2] == ["8002"]
    assert len(client.get("/api/hulls", params={"q": ""}, headers=h).json()) == len(allr)


def test_hull_t02_validation(client, login):
    h = login("park.pm")
    cases = [
        ({"hull_no": ""}, 400, "호선번호를 입력하세요."),
        ({"hull_no": "bad no!"}, 400, "호선번호는 영문/숫자/._- 1~20자입니다."),
        ({"hull_no": "8001"}, 409, "이미 존재하는 호선번호입니다."),
        ({"ship_type": "XXX"}, 400, "허용되지 않는 코드값입니다."),
        ({"contract_dt": "2026/01/01"}, 400, "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다."),
        ({"delivery_dt": "2025-12-31"}, 400, "인도 예정일이 계약일보다 빠릅니다."),
        ({"length_m": -1}, 400, "0 이상의 값을 입력하세요."),
        ({"hull_status": ""}, 400, "상태를 선택하세요."),
    ]
    for patch, st, msg in cases:
        r = client.post("/api/hulls", json={**NEW, **patch}, headers=h)
        assert r.status_code == st and r.json()["message"] == msg, (patch, r.json())


def test_hull_t03_create_milestones(client, login):
    h = login("park.pm")
    r = client.post("/api/hulls", json=NEW, headers=h)
    assert r.status_code == 201
    b = r.json()
    assert b["hull_status"] == "PLAN" and b["use_yn"] is True and b["progress"] is None and b["plan_count"] == 0
    assert b["create_user_id"] == "park.pm" and b["create_dt"] == "2026-10-19"
    ms = client.get("/api/hulls/9001/milestones", headers=h).json()
    assert [m["milestone_cd"] for m in ms] == ["CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER"]
    assert ms[-1]["plan_dt"] == "2028-03-31" and all(m["plan_dt"] is None for m in ms[:-1])
    assert ms[0]["name"] == "강재절단"
    r = client.put("/api/hulls/9001/milestones", json={"items": [
        {"milestone_cd": "CUT", "plan_dt": "2027-01-10", "actual_dt": "2027-01-13"}]}, headers=h)
    cut = r.json()[0]
    assert cut["diff_days"] == 3
    for items in ([{"milestone_cd": "XX"}], [{"milestone_cd": "CUT"}, {"milestone_cd": "CUT"}]):
        r = client.put("/api/hulls/9001/milestones", json={"items": items}, headers=h)
        assert r.status_code == 400 and r.json()["message"] == "허용되지 않거나 중복된 일정 코드입니다."


def test_hull_t04_update(client, login):
    h = login("park.pm")
    r = client.patch("/api/hulls/8003", json={"owner_nm": "New Owner", "dock_no": ""}, headers=h)
    assert r.status_code == 200
    b = r.json()
    assert b["owner_nm"] == "New Owner" and b["dock_no"] is None
    assert b["modify_user_id"] == "park.pm" and b["modify_dt"] == "2026-10-19"
    lst = {x["hull_no"]: x for x in client.get("/api/hulls", headers=h).json()}
    assert lst["8003"]["owner_nm"] == "New Owner"
    r = client.patch("/api/hulls/8003", json={"hull_no": "X1"}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "호선번호는 수정할 수 없습니다."
    r = client.patch("/api/hulls/8003", json={"delivery_dt": "2000-01-01"}, headers=h)
    assert r.json()["message"] == "인도 예정일이 계약일보다 빠릅니다."
    assert client.patch("/api/hulls/NOPE", json={}, headers=h).json()["code"] == "HULL_NOT_FOUND"


def test_hull_t05_block_unique(client, login):
    h = login("park.pm")
    r = client.post("/api/hulls/8001/blocks", json={"block_cd": "101"}, headers=h)
    assert r.status_code == 409 and r.json()["message"] == "이미 존재하는 블록코드입니다."
    assert client.post("/api/hulls/8001/blocks", json={"block_cd": ""}, headers=h).json()["message"] == "블록코드를 입력하세요."
    assert client.post("/api/hulls/8001/blocks", json={"block_cd": "9", "block_type": "X"}, headers=h).status_code == 400
    assert client.post("/api/hulls/8001/blocks", json={"block_cd": "9", "weight_ton": -1}, headers=h).status_code == 400
    r = client.post("/api/hulls/8002/blocks", json={"block_cd": "901", "block_nm": "추가", "block_type": "FLAT",
                                                    "weight_ton": 10}, headers=h)
    assert r.status_code == 201 and r.json()["progress"] is None and r.json()["plan_count"] == 0
    # 다른 호선에는 같은 코드 허용
    assert client.post("/api/hulls/8003/blocks", json={"block_cd": "901"}, headers=h).status_code == 201
    bl = client.get("/api/hulls/8001/blocks", headers=h).json()
    assert [b["block_cd"] for b in bl] == sorted([b["block_cd"] for b in bl], key=int)
    assert bl[0]["drawing_count"] > 0 and bl[0]["progress"] is not None


def test_hull_t06_block_delete_keeps_drawings(client, login, conn):
    h = login("park.pm")
    plans = conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE BlockId=1").fetchone()[0]
    dwgs = [r[0] for r in conn.execute("SELECT DrawingId FROM TB_DWG_Drawing WHERE BlockId=1")]
    assert plans and dwgs
    assert client.delete("/api/blocks/1", headers=h).status_code == 204
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE BlockId=1").fetchone()[0] == 0
    for d in dwgs:
        assert conn.execute("SELECT BlockId FROM TB_DWG_Drawing WHERE DrawingId=?", (d,)).fetchone()[0] is None
    assert client.delete("/api/blocks/1", headers=h).json()["code"] == "BLOCK_NOT_FOUND"


def test_hull_t07_delete_no_orphans(client, login, conn, db_path):
    from app import storage
    h = login("park.pm")
    fdir = storage.file_path("x").parent
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "f8001.pdf").write_bytes(b"%PDF")
    conn.execute("UPDATE TB_DWG_Revision SET FileId='f8001.pdf' WHERE DrawingId=1 AND RevNo=0")
    assert client.delete("/api/hulls/8001", headers=h).status_code == 204
    assert not (fdir / "f8001.pdf").exists()
    checks = [
        "SELECT COUNT(*) FROM TB_MST_Block WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "SELECT COUNT(*) FROM TB_PRC_Plan WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "SELECT COUNT(*) FROM TB_PRC_PlanDep WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)"
        " OR PredPlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)",
        "SELECT COUNT(*) FROM TB_PRC_Progress WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)",
        "SELECT COUNT(*) FROM TB_DWG_Drawing WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "SELECT COUNT(*) FROM TB_DWG_Revision WHERE DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_Drawing)",
        "SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_Drawing)",
        "SELECT COUNT(*) FROM TB_DWG_PlanLink WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)",
        "SELECT COUNT(*) FROM TB_MST_HullMilestone WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
    ]
    for sql in checks:
        assert conn.execute(sql).fetchone()[0] == 0, sql
    assert client.get("/api/hulls/8001", headers=h).status_code == 404


def test_hull_t08_view_cannot_write(client, login):
    h = login("choi.qa")
    for method, url, body in [("post", "/api/hulls", NEW), ("patch", "/api/hulls/8001", {"remark": "x"}),
                              ("delete", "/api/hulls/8001", None), ("put", "/api/hulls/8001/milestones", {"items": []}),
                              ("post", "/api/hulls/8001/blocks", {"block_cd": "999"}), ("delete", "/api/blocks/1", None)]:
        r = client.request(method, url, json=body, headers=h)
        assert r.status_code == 403 and r.json()["details"] == {"menu_id": "M11"}, url
    assert client.get("/api/hulls/8001", headers=h).status_code == 200


def test_summary(client, login):
    s = client.get("/api/hulls/8001/summary", headers=login("choi.qa")).json()
    assert set(s["plan_status"]) == {"PLAN", "READY", "WORK", "DONE", "DELAY"}
    assert set(s["drawing_status"]) == {"ISSUED", "APPROVED", "REVIEW", "DRAFT"}
    assert s["progress"] == 65 and s["plan_count"] == sum(s["plan_status"].values())
