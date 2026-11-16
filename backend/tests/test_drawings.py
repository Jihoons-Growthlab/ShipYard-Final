from tests.helpers import HULL, mk_plan

PDF = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def new_dwg(client, h, no="8004-HULL-901", **kw):
    r = client.post("/api/drawings", json={"drawing_no": no, "drawing_nm": "테스트 도면", "hull_no": HULL,
                                           "discipline": "HULL", **kw}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, h, did, rev, data=PDF, name="a.pdf", ctype="application/pdf"):
    return client.post(f"/api/drawings/{did}/revisions/{rev}/pdf", params={"filename": name}, content=data,
                       headers={**h, "Content-Type": ctype})


def approve_all(client, login, did, rev):
    d = client.get(f"/api/drawings/{did}", headers=login("lee.dwg")).json()
    for a in sorted([a for a in d["approvals"] if a["rev_no"] == rev], key=lambda a: a["step_no"]):
        r = client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "APPROVE"},
                        headers=login(a["approver_emp_no"]))
        assert r.status_code == 200, r.text


def test_list_filter_and_rev_display(client, login):
    h = login("choi.qa")
    items = client.get("/api/drawings", headers=h).json()
    assert [x["drawing_id"] for x in items] == sorted(x["drawing_id"] for x in items)
    keys = {"drawing_id", "drawing_no", "drawing_nm", "hull_no", "block_id", "block_cd", "discipline", "dwg_status",
            "current_rev_no", "latest_rev_no", "designer_emp_no", "designer_nm", "link_count"}
    assert set(items[0]) == keys
    f = client.get("/api/drawings", params={"hull_no": "8001", "discipline": "PIPE"}, headers=h).json()
    assert f and all(x["hull_no"] == "8001" and x["discipline"] == "PIPE" for x in f)
    q = client.get("/api/drawings", params={"q": "배관"}, headers=h).json()
    assert q and all("배관" in x["drawing_nm"] or "배관" in x["drawing_no"] for x in q)
    d12 = next(x for x in items if x["drawing_id"] == 12)
    assert d12["current_rev_no"] == 0 and d12["latest_rev_no"] == 1


def test_create_validation_and_rev0(client, login):
    h = login("lee.dwg")
    for body, msg in [({}, "도면번호를 입력하세요."), ({"drawing_no": "X"}, "호선을 선택하세요."),
                      ({"drawing_no": "X", "hull_no": HULL}, "도면명을 입력하세요."),
                      ({"drawing_no": "X", "hull_no": HULL, "drawing_nm": "n", "discipline": "ZZ"}, "허용되지 않는 분야입니다."),
                      ({"drawing_no": "X", "hull_no": HULL, "drawing_nm": "n", "block_id": 1}, "해당 호선의 블록이 아닙니다."),
                      ({"drawing_no": "X", "hull_no": HULL, "drawing_nm": "n", "designer_emp_no": "jung.new"},
                       "승인된 회원만 지정할 수 있습니다.")]:
        r = client.post("/api/drawings", json=body, headers=h)
        assert r.status_code == 400 and r.json()["message"] == msg, (body, r.text)
    r = client.post("/api/drawings", json={"drawing_no": "8001-HULL-101", "drawing_nm": "n", "hull_no": HULL}, headers=h)
    assert r.status_code == 409 and r.json()["message"] == "이미 존재하는 도면번호입니다."
    d = new_dwg(client, h)
    assert d["dwg_status"] == "DRAFT" and d["current_rev_no"] == 0
    assert [(x["rev_no"], x["rev_status"], x["change_desc"], x["has_file"]) for x in d["revisions"]] == [(0, "DRAFT", "최초 작성", False)]
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"hull_no": "8001"}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "호선은 변경할 수 없습니다."
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"drawing_no": "Y"}, headers=h)
    assert r.json()["message"] == "도면번호는 변경할 수 없습니다."
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"drawing_nm": "새 이름", "discipline": "PIPE"}, headers=h)
    assert r.status_code == 200 and r.json()["drawing_nm"] == "새 이름" and r.json()["modify_user_id"] == "lee.dwg"


def test_seed_file_name_without_file(client, login):
    h = login("lee.dwg")
    d = client.get("/api/drawings/1", headers=h).json()
    assert d["revisions"][0]["file_nm"] and not d["revisions"][0]["has_file"]
    r = client.get("/api/drawings/1/revisions/0/pdf", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "NO_FILE"


def test_pdf_upload_rules(client, login, db_path):
    h = login("lee.dwg")
    d = new_dwg(client, h)
    did = d["drawing_id"]
    r = upload(client, h, did, 0, b"hello", name="a.txt", ctype="text/plain")
    assert r.status_code == 400 and r.json()["code"] == "INVALID_FILE_TYPE"
    r = upload(client, h, did, 0, b"not a pdf", name="a.pdf")
    assert r.status_code == 400 and r.json()["code"] == "INVALID_FILE_TYPE"
    r = upload(client, h, did, 0, PDF + b"0" * (30 * 1024 * 1024), name="big.pdf")
    assert r.status_code == 413 and r.json()["code"] == "FILE_TOO_LARGE"
    r = upload(client, h, did, 0, name="../../x/도면 원본.pdf")
    assert r.status_code == 200, r.text
    rev = r.json()["revisions"][0]
    assert rev["has_file"] and rev["file_nm"] == "도면 원본.pdf"
    files = [p for p in (db_path.parent / "files").iterdir()]
    assert len(files) == 1 and len(files[0].stem) == 32 and files[0].suffix == ".pdf"
    g = client.get(f"/api/drawings/{did}/revisions/0/pdf", headers=h)
    assert g.status_code == 200 and g.content == PDF and g.headers["x-content-type-options"] == "nosniff"
    assert g.headers["content-disposition"].startswith("inline")
    # 교체 시 이전 파일 삭제
    upload(client, h, did, 0)
    assert len(list((db_path.parent / "files").iterdir())) == 1
    files = list((db_path.parent / "files").iterdir())
    files[0].unlink()
    assert client.get(f"/api/drawings/{did}/revisions/0/pdf", headers=h).json()["code"] == "FILE_NOT_FOUND"
    assert client.delete(f"/api/drawings/{did}/revisions/0/pdf", headers=h).status_code == 204
    # DRAFT 아닌 리비전
    r = upload(client, h, 1, 0)
    assert r.status_code == 409 and r.json()["message"] == "작성중(DRAFT) 리비전만 업로드할 수 있습니다."
    r = client.delete("/api/drawings/1/revisions/0/pdf", headers=h)
    assert r.status_code == 409 and r.json()["message"] == "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다."


def test_view_forbidden_before_body(client, login):
    h = login("choi.qa")
    assert upload(client, h, 1, 0, b"x" * 10).status_code == 403
    assert client.post("/api/drawings/1/revisions/0/issue", headers=h).status_code == 403
    assert client.delete("/api/drawings/1", headers=h).status_code == 403
    assert client.post("/api/drawings", json={}, headers=h).status_code == 403


def test_revision_approval_issue_flow_and_gate(client, login, conn):
    h = login("lee.dwg")
    pm = login("park.pm")
    d = new_dwg(client, h)
    did = d["drawing_id"]
    pid = mk_plan(client, pm, "2026-11-01", "2026-11-10")
    r = client.post(f"/api/drawings/{did}/plans", json={"plan_id": pid, "required": True}, headers=h)
    assert r.status_code == 201 and r.json()["plans"][0]["plan_id"] == pid
    assert client.get(f"/api/plans/{pid}", headers=pm).json()["plan_status"] == "PLAN"
    r = client.post(f"/api/drawings/{did}/revisions", json={"change_desc": "x"}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "INVALID_REV_STATE"
    r = client.post(f"/api/drawings/{did}/revisions/0/issue", headers=h)
    assert r.status_code == 409 and r.json()["message"] == "승인(APPROVED)된 리비전만 배포할 수 있습니다."
    for body, msg in [({}, "검토자와 승인자를 선택하세요."), ({"reviewer_emp_no": "admin", "approver_emp_no": "admin"},
                                                       "검토자와 승인자는 서로 다른 사람이어야 합니다.")]:
        r = client.post(f"/api/drawings/{did}/revisions/0/request-approval", json=body, headers=h)
        assert r.status_code == 400 and r.json()["message"] == msg
    r = client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                    json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=h)
    assert r.status_code == 200 and r.json()["dwg_status"] == "REVIEW"
    assert [(a["step_no"], a["result"]) for a in r.json()["approvals"]] == [(1, "WAIT"), (2, "WAIT")]
    approve_all(client, login, did, 0)
    assert client.get(f"/api/drawings/{did}", headers=h).json()["dwg_status"] == "APPROVED"
    assert client.get(f"/api/plans/{pid}", headers=pm).json()["plan_status"] == "PLAN"  # APPROVED만으로 통과 못 함
    r = client.post(f"/api/drawings/{did}/revisions/0/issue", headers=h)
    assert r.status_code == 200 and r.json()["dwg_status"] == "ISSUED" and r.json()["revisions"][0]["issue_dt"] == "2026-10-19"
    assert client.get(f"/api/plans/{pid}", headers=pm).json()["plan_status"] == "READY"
    # 신규 Rev1 → 배포 → Rev0 OBSOLETE, CurrentRevNo 1
    r = client.post(f"/api/drawings/{did}/revisions", json={"change_desc": "  "}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "개정 사유를 입력하세요."
    r = client.post(f"/api/drawings/{did}/revisions", json={"change_desc": "치수 변경"}, headers=h)
    assert r.status_code == 201 and r.json()["dwg_status"] == "DRAFT" and r.json()["current_rev_no"] == 0
    assert client.get(f"/api/plans/{pid}", headers=pm).json()["plan_status"] == "READY"  # 과거 ISSUED로 게이트 유지
    client.post(f"/api/drawings/{did}/revisions/1/request-approval",
                json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=h)
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'APPROVED' WHERE DrawingId = ? AND RevNo = 1", (did,))
    r = client.post(f"/api/drawings/{did}/revisions/1/issue", headers=h)
    assert r.status_code == 409 and r.json()["code"] == "APPROVAL_INCOMPLETE"
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'REVIEW' WHERE DrawingId = ? AND RevNo = 1", (did,))
    approve_all(client, login, did, 1)
    r = client.post(f"/api/drawings/{did}/revisions/1/issue", headers=h).json()
    assert r["current_rev_no"] == 1 and [x["rev_status"] for x in r["revisions"]] == ["ISSUED", "OBSOLETE"]


def test_link_rules_and_impacts(client, login, conn):
    h = login("lee.dwg")
    d = new_dwg(client, h)
    did = d["drawing_id"]
    other = client.get("/api/hulls/8001/plans", headers=h).json()["plans"][0]["plan_id"]
    assert client.post(f"/api/drawings/{did}/plans", json={"plan_id": other}, headers=h).status_code == 400
    assert client.post(f"/api/drawings/{did}/plans", json={}, headers=h).json()["message"] == "공정을 선택하세요."
    pid = mk_plan(client, login("park.pm"), "2026-10-01", "2026-12-10")
    assert client.post(f"/api/drawings/{did}/plans", json={"plan_id": pid}, headers=h).status_code == 201
    assert client.post(f"/api/drawings/{did}/plans", json={"plan_id": pid}, headers=h).status_code == 409
    body = client.get(f"/api/drawings/{did}/plans", headers=h).json()
    assert [p["plan_id"] for p in body["plans"]] == [pid] and pid not in [p["plan_id"] for p in body["available_plans"]]
    # 영향: 최근 30일 Rev>=1 ISSUED + WORK 공정
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'OBSOLETE' WHERE DrawingId = ?", (did,))
    conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, IssueDt) VALUES (?, 1, 'ISSUED', '변경', '2026-10-10')", (did,))
    conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = 'WORK' WHERE PlanId = ?", (pid,))
    imp = client.get(f"/api/drawings/{did}", headers=h).json()["impacts"]
    assert [(i["rev_no"], i["plan_id"], i["plan_status"]) for i in imp] == [(1, pid, "WORK")]
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt = '2026-09-01' WHERE DrawingId = ? AND RevNo = 1", (did,))
    assert client.get(f"/api/drawings/{did}", headers=h).json()["impacts"] == []
    assert client.delete(f"/api/drawings/{did}/plans/{pid}", headers=h).status_code == 204
    assert client.delete(f"/api/drawings/{did}/plans/{pid}", headers=h).status_code == 404


def test_delete_leaves_no_orphans(client, login, conn, db_path):
    h = login("lee.dwg")
    d = new_dwg(client, h)
    did = d["drawing_id"]
    pid = mk_plan(client, login("park.pm"), "2026-11-01", "2026-11-10")
    client.post(f"/api/drawings/{did}/plans", json={"plan_id": pid}, headers=h)
    upload(client, h, did, 0)
    client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=h)
    assert client.delete(f"/api/drawings/{did}", headers=h).status_code == 204
    for t in ("TB_DWG_Revision", "TB_DWG_Approval", "TB_DWG_PlanLink"):
        assert conn.execute(f"SELECT COUNT(*) FROM {t} WHERE DrawingId = ?", (did,)).fetchone()[0] == 0
    assert list((db_path.parent / "files").iterdir()) == []
    assert client.get(f"/api/drawings/{did}", headers=h).status_code == 404
    assert client.get(f"/api/plans/{pid}", headers=h).status_code in (200, 403)
