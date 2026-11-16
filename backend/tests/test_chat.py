import io
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.services import chat as chat_svc


def ask(client, h, text):
    return client.post("/api/chat", json={"messages": [{"role": "user", "content": text}]}, headers=h)


def deny(conn, emp, menu):
    conn.execute("INSERT OR REPLACE INTO TB_SYS_UserMenu(EmpNo, MenuId, AuthGbn) VALUES (?, ?, 'None')", (emp, menu))


def test_mcp_real_process_and_forbidden(db_path, conn):
    out = chat_svc.call_tool("park.pm", "search_hulls", {"query": "8001"})
    assert out["total"] == 1 and out["hulls"][0]["hull_no"] == "8001"
    assert set(out["hulls"][0]) == {"hull_no", "hull_nm", "hull_status", "progress", "delay_count", "delivery_dt"}
    deny(conn, "park.pm", "M11")
    with pytest.raises(Exception) as e:
        chat_svc.call_tool("park.pm", "search_hulls", {"query": ""})
    assert e.value.status == 403


def test_mcp_protocol_errors(db_path):
    import subprocess, sys
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_hulls", "arguments": {"query": "x" * 101}}}]
    p = subprocess.run([sys.executable, "-m", "app.hull_mcp", "park.pm"], input="".join(json.dumps(m) + "\n" for m in msgs),
                       capture_output=True, text=True, cwd=chat_svc.BACKEND_DIR, timeout=10)
    lines = [json.loads(x) for x in p.stdout.splitlines()]
    assert lines[0]["result"]["protocolVersion"] == "2025-03-26"
    assert lines[0]["result"]["serverInfo"]["name"] == "shipyard-hulls"
    assert [x["error"]["code"] for x in lines[1:]] == [-32602, -32602]


def test_mcp_failure_502(db_path, monkeypatch):
    monkeypatch.setattr(chat_svc, "BACKEND_DIR", chat_svc.BACKEND_DIR / "nope")
    with pytest.raises(Exception) as e:
        chat_svc.call_tool("park.pm", "list_drawings", {})
    assert e.value.status == 502 and e.value.code == "HULL_MCP_ERROR" and e.value.message == "호선 조회 서버에 연결하지 못했습니다."


def test_routing(client, login, conn):
    h = login("park.pm")
    b = ask(client, h, "호선 정보 알려줘").json()
    assert b["answer"] == "상세 정보를 볼 호선을 선택해 주세요." and len(b["hulls"]) == 5
    assert [x["hull_no"] for x in ask(client, h, "SN-8002 상태").json()["hulls"]] == ["8002"]
    assert [x["hull_no"] for x in ask(client, h, "호선 8003 알려줘").json()["hulls"]] == ["8003"]
    assert ask(client, h, "zzz 호선 정보").json()["answer"] == "일치하는 호선이 없습니다. 호선 번호나 이름을 확인해 주세요."
    sn = ask(client, h, "sn 호선 목록").json()
    assert sn["answer"].startswith("‘SN’으로 등록된 호선을 찾지 못했습니다.") and len(sn["hulls"]) == 5
    d = ask(client, h, "도면 목록 보여줘").json()
    assert d["choice_type"] == "drawing" and d["answer"] == "상세 정보를 볼 도면을 선택해 주세요." and d["choices"][0]["drawing_no"]
    p = ask(client, h, "공정 실적 알려줘").json()
    assert p["choice_type"] == "progress-hull" and p["choices"][0]["hull_no"] == "8001"
    f = ask(client, h, "건의하기").json()
    assert f == {"answer": "접수할 내용을 입력하고 접수 버튼을 눌러 주세요.", "feedback_kind": "suggestion"}
    assert ask(client, h, "문의 하고 싶어.").json()["feedback_kind"] == "inquiry"
    r = client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "x"}]}, headers=h)
    assert r.status_code == 400 and r.json()["code"] == "CHAT_INPUT"
    deny(conn, "park.pm", "M31")
    assert ask(client, h, "도면 목록 보여줘").status_code == 403


def test_feedback_idempotent(client, login):
    h = login("choi.qa")
    rid = str(uuid.uuid4())
    body = {"kind": "suggestion", "content": "공정표 인쇄 기능", "request_id": rid}
    a = client.post("/api/chat/feedback", json=body, headers=h)
    assert a.status_code == 200 and a.json()["receipt"].startswith("FB-")
    b = client.post("/api/chat/feedback", json=body, headers=h).json()
    assert b == a.json()
    c = client.post("/api/chat/feedback", json=body | {"content": "다른 내용"}, headers=h)
    assert c.status_code == 409
    e = client.post("/api/chat/feedback", json=body | {"content": "  ", "request_id": str(uuid.uuid4())}, headers=h)
    assert e.status_code == 400 and e.json()["code"] == "FEEDBACK_INPUT" and e.json()["message"] == "접수할 내용을 입력해 주세요."
    items = client.get("/api/inquiries", headers=h).json()["items"]
    mine = [i for i in items if i["inquiry_id"] == a.json()["inquiry_id"]]
    assert len(mine) == 1 and mine[0]["category"] == "FEATURE" and mine[0]["content"] == "공정표 인쇄 기능"


class _Fake(BaseHTTPRequestHandler):
    status, reply = 200, {"message": {"role": "assistant", "content": "블록은 선체를 나눈 단위입니다."}}
    seen = []

    def do_POST(self):
        self.seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(json.dumps(self.reply).encode())

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_ollama(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    _Fake.status, _Fake.seen = 200, []
    yield _Fake
    srv.shutdown()


def test_ollama_answer_and_errors(client, login, fake_ollama, monkeypatch):
    h = login("park.pm")
    r = ask(client, h, "블록이 뭐야?")
    assert r.status_code == 200 and r.json()["answer"] == "블록은 선체를 나눈 단위입니다."
    sent = fake_ollama.seen[0]
    assert sent["stream"] is False and sent["options"] == {"num_ctx": 4096, "num_predict": 320}
    assert sent["messages"][0]["role"] == "system" and sent["messages"][-1]["content"] == "블록이 뭐야?"
    fake_ollama.status = 404
    r = ask(client, h, "블록이 뭐야?")
    assert r.status_code == 503 and r.json()["message"] == "로컬 채팅 모델을 찾을 수 없습니다."
    assert chat_svc._busy.acquire(blocking=False)
    try:
        r = ask(client, h, "블록이 뭐야?")
        assert r.status_code == 429 and r.json()["message"] == "다른 답변을 작성 중입니다. 잠시 후 다시 보내 주세요."
    finally:
        chat_svc._busy.release()
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    r = ask(client, h, "블록이 뭐야?")
    assert r.status_code == 503 and r.json()["code"] == "CHAT_OFFLINE"
    assert r.json()["message"] == "로컬 모델에 연결할 수 없습니다. Ollama 실행 상태를 확인해 주세요."


# --- F14 보고서
def make(client, h, fmt, hull=None, expect=201):
    r = client.post("/api/chat/report", json={"format": fmt} | ({"hull_no": hull} if hull else {}), headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def test_report_pdf_xlsx_download(client, login):
    from openpyxl import load_workbook
    h = login("park.pm")
    opts = client.get("/api/chat/report/options", headers=h).json()
    assert [x["hull_no"] for x in opts["hulls"]] == ["8001", "8002", "8003", "8004", "8005"]
    assert opts["formats"] == [{"code": "pdf", "name": "PDF"}, {"code": "xlsx", "name": "Excel"}]
    p = make(client, h, "pdf", "8001")
    assert p["title"] == "8001 호선 현황 보고서" and p["filename"].startswith("8001_호선_현황_보고서_") and len(p["report_id"]) == 24
    d = client.get(p["download_url"], headers=h)
    assert d.status_code == 200 and d.content[:4] == b"%PDF" and d.headers["content-type"] == "application/pdf"
    x = make(client, h, "xlsx")
    assert x["summary"]["hulls"] == 5 and x["title"] == "전체 호선 현황 보고서"
    wb = load_workbook(io.BytesIO(client.get(x["download_url"], headers=h).content))
    assert wb.sheetnames == ["요약", "호선", "공정", "도면"] and wb["호선"].max_row == 6
    assert [c.value for c in wb["호선"][1]] == ["호선번호", "호선명", "선종", "상태", "선주", "인도예정", "진척률", "지연"]


def test_report_access_and_validation(client, login):
    h, other = login("park.pm"), login("lee.dwg")
    x = make(client, h, "xlsx", "8001")
    assert client.get(x["download_url"], headers=other).status_code == 404
    r = client.get("/api/chat/reports/../../etc?format=pdf", headers=h)
    assert r.status_code == 404
    assert client.get("/api/chat/reports/zz?format=pdf", headers=h).json()["code"] == "REPORT_NOT_FOUND"
    assert make(client, h, "doc", expect=422)["code"] == "REPORT_FORMAT"
    nf = make(client, h, "pdf", "9999", expect=404)
    assert nf["code"] == "REPORT_ERROR" and nf["message"] == "호선을 찾을 수 없습니다."


def test_report_sections_by_permission(client, login, conn):
    from openpyxl import load_workbook
    h = login("park.pm")
    deny(conn, "park.pm", "M21")
    x = make(client, h, "xlsx")
    wb = load_workbook(io.BytesIO(client.get(x["download_url"], headers=h).content))
    assert wb.sheetnames == ["요약", "호선", "도면"] and x["summary"]["plans"] is None
    assert any("조회 권한이 없어 제외: 공정" == c.value for row in wb["요약"].iter_rows() for c in row)
    for m in ("M11", "M31"):
        deny(conn, "park.pm", m)
    r = make(client, h, "pdf", expect=400)
    assert r["message"] == "보고서에 넣을 수 있는 메뉴 권한(호선·공정·도면 조회)이 없습니다."
    assert client.get("/api/chat/report/options", headers=h).json()["hulls"] == []
