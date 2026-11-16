def post(client, h, **kw):
    return client.post("/api/inquiries", json={"category": "FEATURE", "title": "제목", "content": "내용"} | kw, headers=h)


def test_create_validation_trim(client, login):
    h = login("choi.qa")  # 조회 전용 그룹도 작성 가능
    for body, msg in [({"category": None}, "분류를 선택하세요."), ({"category": "X"}, "분류를 선택하세요."),
                      ({"title": "  "}, "제목을 입력하세요."), ({"content": "\n "}, "내용을 입력하세요."),
                      ({"title": "가" * 201}, "제목은 200자 이하로 입력하세요.")]:
        r = post(client, h, **body)
        assert r.status_code == 400 and r.json()["message"] == msg, body
    r = post(client, h, title="  공백 제목 ", content=" 본문 ")
    assert r.status_code == 201
    b = r.json()
    assert b["title"] == "공백 제목" and b["content"] == "본문" and b["status"] == "OPEN" and b["mine"] is True
    assert b["create_user_nm"] == "최품질"


def test_others_forbidden_and_own_list(client, login):
    qa, pm = login("choi.qa"), login("park.pm")
    iid = post(client, qa).json()["inquiry_id"]
    r = client.get(f"/api/inquiries/{iid}", headers=pm)
    assert r.status_code == 403 and r.json()["message"] == "본인이 작성한 글만 볼 수 있습니다."
    assert client.get("/api/inquiries/99999", headers=pm).json()["code"] == "INQUIRY_NOT_FOUND"
    lst = client.get("/api/inquiries", headers=pm).json()
    assert lst["is_admin"] is False and all(i["mine"] for i in lst["items"])
    admin = login("admin")
    al = client.get("/api/inquiries", headers=admin).json()
    assert al["is_admin"] and iid in [i["inquiry_id"] for i in al["items"]]
    assert client.get("/api/inquiries", params={"mine": True}, headers=admin).json()["items"] == []
    assert set(al["categories"]) == {"BUG", "FEATURE", "QUESTION", "ETC"} and al["statuses"]["IN_PROGRESS"] == "처리중"


def test_author_edit_only_when_open(client, login):
    qa, admin = login("choi.qa"), login("admin")
    iid = post(client, qa).json()["inquiry_id"]
    r = client.patch(f"/api/inquiries/{iid}", json={"title": "새 제목"}, headers=qa)
    assert r.status_code == 200 and r.json()["title"] == "새 제목" and r.json()["modify_dt"]
    assert client.patch(f"/api/inquiries/{iid}", json={"title": "x"}, headers=admin).status_code == 403
    r = client.patch(f"/api/inquiries/{iid}", json={"status": "IN_PROGRESS"}, headers=qa)
    assert r.status_code == 403 and r.json()["message"] == "관리자만 처리할 수 있습니다."
    assert client.patch(f"/api/inquiries/{iid}", json={"status": "IN_PROGRESS"}, headers=admin).status_code == 200
    r = client.patch(f"/api/inquiries/{iid}", json={"title": "x"}, headers=qa)
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATUS"
    r = client.delete(f"/api/inquiries/{iid}", headers=qa)
    assert r.status_code == 409 and r.json()["message"] == "접수 상태인 글만 삭제할 수 있습니다."
    assert client.delete(f"/api/inquiries/{iid}", headers=admin).status_code == 204
    iid2 = post(client, qa).json()["inquiry_id"]
    assert client.delete(f"/api/inquiries/{iid2}", headers=qa).status_code == 204


def test_admin_done_requires_answer(client, login):
    qa, admin = login("choi.qa"), login("admin")
    iid = post(client, qa).json()["inquiry_id"]
    for st in ("DONE", "REJECTED"):
        r = client.patch(f"/api/inquiries/{iid}", json={"status": st, "answer": " "}, headers=admin)
        assert r.status_code == 400 and r.json()["message"] == "완료·반려 처리에는 답변을 입력하세요."
    r = client.patch(f"/api/inquiries/{iid}", json={"status": "DONE", "answer": "처리했습니다."}, headers=admin).json()
    assert r["status"] == "DONE" and r["answer_user_nm"] == "김관리" and r["answer_dt"]
    assert client.get(f"/api/inquiries/{iid}", headers=qa).json()["answer"] == "처리했습니다."


def test_counts_before_status_filter(client, login):
    qa, admin = login("choi.qa"), login("admin")
    ids = [post(client, qa, title=f"t{i}").json()["inquiry_id"] for i in range(3)]
    client.patch(f"/api/inquiries/{ids[0]}", json={"status": "IN_PROGRESS"}, headers=admin)
    client.patch(f"/api/inquiries/{ids[1]}", json={"status": "REJECTED", "answer": "불가"}, headers=admin)
    b = client.get("/api/inquiries", params={"status": "OPEN"}, headers=qa).json()
    assert b["counts"] == {"OPEN": 1, "IN_PROGRESS": 1, "DONE": 0, "REJECTED": 1}
    assert [i["inquiry_id"] for i in b["items"]] == [ids[2]] and b["total"] == 1
    allq = client.get("/api/inquiries", headers=qa).json()
    assert [i["inquiry_id"] for i in allq["items"]] == sorted(ids, reverse=True)
    assert client.get("/api/inquiries", params={"q": "최품"}, headers=admin).json()["total"] == 3
