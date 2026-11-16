import re

from app import config
from app.services import demo
from tests.conftest import SEED_USERS


def check_pdf(data: bytes):
    assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
    start = int(re.search(rb"startxref\n(\d+)\n%%EOF", data).group(1))
    assert data[start:start + 4] == b"xref"
    offs = [int(x) for x in re.findall(rb"(\d{10}) 00000 n ", data)]
    assert len(offs) == 7
    for i, o in enumerate(offs, 1):
        assert data[o:].startswith(f"{i} 0 obj".encode())
    assert re.search(rb"/Length (\d+)", data)
    data.decode("latin-1").encode("latin-1")


def test_demo_pdfs_idempotent(conn, db_path):
    assert demo.load_demo_pdfs(conn) == 79
    assert demo.load_demo_pdfs(conn) == 0
    rows = conn.execute("SELECT r.FileId, r.FileNm, r.RevNo, r.RevStatus, d.DrawingNo FROM TB_DWG_Revision r"
                        " JOIN TB_DWG_Drawing d ON d.DrawingId = r.DrawingId").fetchall()
    assert all(r[1] == f"{r[4]}_Rev{r[2]}.pdf" for r in rows)
    files = {p.name for p in (db_path.parent / "files").iterdir()}
    assert files == {r[0] for r in rows}
    for r in rows[:10]:
        data = (db_path.parent / "files" / r[0]).read_bytes()
        check_pdf(data)
        assert f"/Title ({r[4]} Rev{r[2]})".encode() in data
        if r[3] == "OBSOLETE":
            assert b"SUPERSEDED" in data


def test_demo_pdf_served(client, login, conn):
    demo.load_demo_pdfs(conn)
    h = login("lee.dwg")
    assert client.get("/api/drawings/1", headers=h).json()["revisions"][0]["has_file"]
    r = client.get("/api/drawings/1/revisions/0/pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")


def test_demo_usage_idempotent_and_summary(client, login, conn):
    n = demo.load_demo_usage(conn)
    assert n > 1000
    assert demo.load_demo_usage(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_Inquiry").fetchone()[0] == 4
    st = dict(conn.execute("SELECT Title, Status FROM TB_SYS_Inquiry").fetchall())
    assert st["대시보드 글자 크기 조정"] == "REJECTED"
    r = conn.execute("SELECT CreateDt, AnswerDt, AnswerUserId FROM TB_SYS_Inquiry WHERE Status = 'DONE'").fetchone()
    assert r[2] == "admin" and r[1] > r[0]
    paths = {p for (p,) in conn.execute("SELECT DISTINCT Path FROM TB_SYS_LogApi WHERE DemoYN = 1")}
    assert "/api/plans/{plan_id}/schedule" in paths and not any(re.search(r"/\d", p) for p in paths)
    b = client.get("/api/usage/summary", params={"days": 30}, headers=login("admin")).json()
    assert b["demo_calls"] > 0 and b["kpi"]["calls"] >= b["demo_calls"] and b["kpi"]["errors"] > 0
    assert b["top_users"][0]["emp_no"] == "park.pm"
    hours = b["hours"]
    assert sum(hours[:7]) == 0 or max(hours) == max(hours[7:20])


def test_demo_role_disabled_by_default(client, login):
    h = login("han.wk")
    assert "demo_role" not in client.get("/api/auth/me", headers=h).json()
    r = client.post("/api/auth/demo-role", json={"role": "admin"}, headers=h)
    assert r.status_code == 403


def test_demo_role_switch(client, conn, monkeypatch):
    monkeypatch.setattr(config, "demo_enabled", lambda: True)
    demo.prepare_demo_accounts(conn)
    assert client.post("/api/auth/login", json={"emp_no": "park.pm", "password": SEED_USERS["park.pm"]["demo_password"]}).status_code == 403
    tok = client.post("/api/auth/login", json={"emp_no": "han.wk", "password": demo.DEMO_PASSWORD}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/auth/me", headers=h).json()["demo_role"] == "user"
    r = client.post("/api/auth/demo-role", json={"role": "admin"}, headers=h)
    assert r.status_code == 200, r.text
    new = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=h).status_code == 401
    me = client.get("/api/auth/me", headers=new).json()
    assert me["emp_no"] == "admin" and me["demo_role"] == "admin"
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_LogAccess WHERE UserId = 'han.wk' AND LogoutDt IS NOT NULL").fetchone()[0] == 1
    conn.execute("UPDATE users SET totp_enabled = 1 WHERE emp_no = 'han.wk'")
    assert client.post("/api/auth/demo-role", json={"role": "user"}, headers=new).status_code == 403
