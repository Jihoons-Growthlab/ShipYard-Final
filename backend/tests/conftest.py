import shutil

import pytest
from fastapi.testclient import TestClient

from app import db, security
from app.seed import load_seed, seed_users

SEED_USERS = seed_users()


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    p = tmp_path_factory.mktemp("tpl") / "template.db"
    conn = db.connect(p)
    db.migrate(conn)
    load_seed(conn)
    conn.close()
    return p


@pytest.fixture
def db_path(template_db, tmp_path, monkeypatch):
    p = tmp_path / "test.db"
    shutil.copy(template_db, p)
    monkeypatch.setenv("SHIPYARD_DB_PATH", str(p))
    monkeypatch.setenv("SHIPYARD_FILE_DIR", str(tmp_path / "files"))
    monkeypatch.delenv("WEATHER_PROVIDER", raising=False)
    try:
        from app.services import auth
        auth.reset_otp_state()
    except ImportError:
        pass
    return p


@pytest.fixture
def conn(db_path):
    c = db.connect(db_path)
    yield c
    c.close()


@pytest.fixture
def client(db_path):
    from app.main import app
    with TestClient(app) as c:
        yield c


def totp_now(emp_no: str) -> str:
    return security.totp_at(SEED_USERS[emp_no]["totp_secret"], security.current_step())


@pytest.fixture
def login(client):
    """시드 계정으로 로그인해 Authorization 헤더를 돌려준다(OTP 계정은 현재 코드 자동 계산)."""
    def _login(emp_no: str) -> dict:
        r = client.post("/api/auth/login", json={"emp_no": emp_no, "password": SEED_USERS[emp_no]["demo_password"]})
        assert r.status_code == 200, r.text
        b = r.json()
        if b["otp_required"]:
            from app.services import auth
            auth.reset_otp_state()
            r = client.post("/api/auth/otp/verify", json={"code": totp_now(emp_no)},
                            headers={"Authorization": f"Bearer {b['otp_token']}"})
            assert r.status_code == 200, r.text
            b = r.json()
        return {"Authorization": f"Bearer {b['access_token']}"}
    return _login
