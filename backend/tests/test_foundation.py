import json

from app import config, db
from app.cli import main as init_db_main
from app.seed import load_seed


def count(conn, sql, *a):
    return conn.execute(sql, a).fetchone()[0]


def test_migrations_match_files(conn):
    files = sorted(p.stem for p in config.migrations_dir().glob("*.sql"))
    applied = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert applied == files
    assert db.migrate(conn) == []  # 재적용 없음


def test_seed_counts(conn):
    expect = {
        "users": 6, "TB_MST_Hull": 5, "TB_MST_Block": 17, "TB_SYS_MenuInfo": 13,
        "TB_PRC_Plan": 83, "TB_PRC_PlanDep": 79, "TB_PRC_Progress": 60,
        "TB_DWG_Drawing": 47, "TB_DWG_Revision": 79, "TB_DWG_Approval": 72, "TB_DWG_PlanLink": 45,
    }
    for t, n in expect.items():
        assert count(conn, f"SELECT COUNT(*) FROM {t}") == n, t
    st = dict(conn.execute("SELECT PlanStatus, COUNT(*) FROM TB_PRC_Plan GROUP BY PlanStatus").fetchall())
    assert st == {"PLAN": 39, "WORK": 7, "DONE": 36, "DELAY": 1}
    assert {"M92", "M95"} <= {r[0] for r in conn.execute("SELECT MenuId FROM TB_SYS_MenuInfo")}


def test_seed_passwords_hashed_argon2(conn):
    h = conn.execute("SELECT password_hash FROM users WHERE emp_no='park.pm'").fetchone()[0]
    assert h.startswith("$argon2id$")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
    assert "demo_password" not in cols


def test_seed_idempotent(conn):
    load_seed(conn)
    assert count(conn, "SELECT COUNT(*) FROM TB_PRC_Plan") == 83
    assert count(conn, "SELECT COUNT(*) FROM users") == 6


def test_pragmas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_phone_digits_unique(conn):
    import sqlite3
    try:
        conn.execute(
            "INSERT INTO users(id,email,password_hash,display_name,emp_no,last_name,first_name,birth_date,phone,created_at)"
            " VALUES('u-x','x@x.com','h','x','xxxx','x','x','2000-01-01','01022220002','2026-10-19')")
        assert False, "duplicate phone digits accepted"
    except sqlite3.IntegrityError:
        pass


def test_init_db_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPYARD_DB_PATH", str(tmp_path / "cli.db"))
    assert init_db_main(["--seed", "--demo-pdfs", "--demo-usage"]) == 0
    assert init_db_main(["--seed"]) == 0  # 반복 실행 안전
    c = db.connect(tmp_path / "cli.db")
    assert count(c, "SELECT COUNT(*) FROM TB_MST_Hull") == 5
    c.close()


def test_health_and_error_shape(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    r = client.get("/api/nope")
    assert r.status_code == 404 and set(r.json()) == {"code", "message", "details"}


def test_seed_json_untouched():
    d = json.loads(config.seed_path().read_text(encoding="utf-8"))
    assert "demo_password" in d["users"]["columns"]
