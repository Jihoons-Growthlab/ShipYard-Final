from tests.test_drawings import new_dwg


def request(client, h, did, rev=0):
    r = client.post(f"/api/drawings/{did}/revisions/{rev}/request-approval",
                    json={"reviewer_emp_no": "park.pm", "approver_emp_no": "lee.dwg"}, headers=h)
    assert r.status_code == 200, r.text
    return {a["step_no"]: a["approval_id"] for a in r.json()["approvals"] if a["rev_no"] == rev}


def test_step2_waits_for_step1_and_assignment(client, login):
    lee, pm = login("lee.dwg"), login("park.pm")
    did = new_dwg(client, lee)["drawing_id"]
    ids = request(client, lee, did)
    assert ids[2] not in [w["approval_id"] for w in client.get("/api/approvals/inbox", headers=lee).json()["waiting"]]
    r = client.post(f"/api/approvals/{ids[2]}/decision", json={"result": "APPROVE"}, headers=lee)
    assert r.status_code == 409 and r.json()["code"] == "NOT_CURRENT_STEP"
    r = client.post(f"/api/approvals/{ids[1]}/decision", json={"result": "APPROVE"}, headers=lee)
    assert r.status_code == 403 and r.json()["code"] == "NOT_ASSIGNED_APPROVER"
    # park.pm은 M33 권한 없음(PROC) → 메뉴 403 먼저
    assert client.post(f"/api/approvals/{ids[1]}/decision", json={"result": "APPROVE"}, headers=pm).status_code == 403


def test_decision_validation_order(client, login):
    lee = login("lee.dwg")
    assert client.post("/api/approvals/999/decision", json={"result": "X"}, headers=lee).json()["message"] == \
        "결재 결과는 APPROVE 또는 REJECT 이어야 합니다."
    assert client.post("/api/approvals/999/decision", json={"result": "REJECT", "comment": " "}, headers=lee).json()["message"] == \
        "반려 시 의견을 입력하세요."
    r = client.post("/api/approvals/999/decision", json={"result": "APPROVE"}, headers=lee)
    assert r.status_code == 404 and r.json()["code"] == "APPROVAL_NOT_FOUND"
    r = client.post("/api/approvals/1/decision", json={"result": "APPROVE"}, headers=lee)
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_DECIDED"


def test_reject_returns_draft_and_keeps_history(client, login, conn):
    lee, admin = login("lee.dwg"), login("admin")
    did = new_dwg(client, lee)["drawing_id"]
    r = client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                    json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=lee).json()
    a1 = next(a["approval_id"] for a in r["approvals"] if a["step_no"] == 1)
    r = client.post(f"/api/approvals/{a1}/decision", json={"result": "REJECT", "comment": "치수 오류"}, headers=lee)
    assert r.status_code == 200 and r.json()["result"] == "REJECT"
    d = client.get(f"/api/drawings/{did}", headers=lee).json()
    assert d["dwg_status"] == "DRAFT" and d["revisions"][0]["rev_status"] == "DRAFT"
    assert [(a["step_no"], a["result"]) for a in d["approvals"]] == [(1, "REJECT")]
    assert d["approvals"][0]["comment"] == "치수 오류" and d["approvals"][0]["act_dt"].startswith("2026-10-19 ")
    conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId <> ?", (did,))
    h = client.get("/api/approvals/history", headers=admin).json()
    assert [x["approval_id"] for x in h] == [a1]


def test_both_steps_approve_then_ready_and_issue(client, login):
    lee, admin = login("lee.dwg"), login("admin")
    did = new_dwg(client, lee)["drawing_id"]
    r = client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                    json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=lee).json()
    ids = {a["step_no"]: a["approval_id"] for a in r["approvals"]}
    r = client.post(f"/api/approvals/{ids[1]}/decision", json={"result": "APPROVE", "comment": ""}, headers=lee).json()
    assert client.get(f"/api/drawings/{did}", headers=lee).json()["dwg_status"] == "REVIEW"
    assert ids[2] in [w["approval_id"] for w in client.get("/api/approvals/inbox", headers=admin).json()["waiting"]]
    r = client.post(f"/api/approvals/{ids[2]}/decision", json={"result": "APPROVE"}, headers=admin).json()
    assert did in [x["drawing_id"] for x in r["ready"]]
    d = client.get(f"/api/drawings/{did}", headers=lee).json()
    assert d["dwg_status"] == "APPROVED" and {a["comment"] for a in d["approvals"]} == {"승인"}
    ib = client.get("/api/approvals/inbox", headers=lee).json()
    assert ib["can_issue"] is True and set(ib) == {"waiting", "ready", "can_issue"}
    assert client.get("/api/approvals/inbox", headers=login("choi.qa")).json()["can_issue"] is False
    client.post(f"/api/drawings/{did}/revisions/0/issue", headers=lee)
    assert did not in [x["drawing_id"] for x in client.get("/api/approvals/inbox", headers=lee).json()["ready"]]


def test_history_limit_and_order(client, login, conn):
    h = client.get("/api/approvals/history", headers=login("choi.qa")).json()
    assert len(h) == 10 and all(x["result"] != "WAIT" for x in h)
    assert [(x["act_dt"], x["approval_id"]) for x in h] == sorted([(x["act_dt"], x["approval_id"]) for x in h], reverse=True)
    conn.execute("DELETE FROM TB_DWG_Approval")
    assert client.get("/api/approvals/history", headers=login("choi.qa")).json() == []


def test_seed_inbox_shapes(client, login):
    ib = client.get("/api/approvals/inbox", headers=login("lee.dwg")).json()
    assert ib["waiting"] and set(ib["waiting"][0]) == {"approval_id", "drawing_id", "drawing_no", "drawing_nm", "rev_no",
                                                       "step_no", "change_desc"}
    assert {x["drawing_id"] for x in ib["ready"]} == {12, 28}
