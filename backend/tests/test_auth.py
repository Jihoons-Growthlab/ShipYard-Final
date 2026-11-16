from app import security
from app.services import auth
from tests.conftest import SEED_USERS, totp_now


def pw(emp):
    return SEED_USERS[emp]["demo_password"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_auth_t01_approved_login(client):
    r = client.post("/api/auth/login", json={"emp_no": "park.pm", "password": pw("park.pm")})
    assert r.status_code == 200
    b = r.json()
    assert b["otp_required"] is False and b["token_type"] == "bearer" and b["expires_in"] == 28800
    assert b["user"]["emp_no"] == "park.pm"
    me = client.get("/api/auth/me", headers=H(b["access_token"])).json()
    assert me["groups"] == [{"code": "PROC", "name": "공정관리자"}]
    assert me["today"] == "2026-10-19" and me["totp_enabled"] is False
    claims = security.decode_token(b["access_token"])
    assert {"sub", "stage", "iat", "exp", "jti", "lid"} <= set(claims) and claims["stage"] == "full"


def test_auth_wrong_password_and_unknown(client):
    for body in ({"emp_no": "park.pm", "password": "x"}, {"emp_no": "ghost", "password": "x"}):
        r = client.post("/api/auth/login", json=body)
        assert r.status_code == 401
        assert r.json()["code"] == "INVALID_CREDENTIALS"
        assert r.json()["message"] == "아이디 또는 비밀번호가 올바르지 않습니다."


def test_auth_t02_status_messages(client, conn):
    r = client.post("/api/auth/login", json={"emp_no": "jung.new", "password": pw("jung.new")})
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_PENDING"
    assert r.json()["message"] == "관리자 승인 대기 중인 계정입니다."
    for st, code in (("rejected", "ACCOUNT_REJECTED"), ("disabled", "ACCOUNT_DISABLED")):
        conn.execute("UPDATE users SET status=? WHERE emp_no='jung.new'", (st,))
        r = client.post("/api/auth/login", json={"emp_no": "jung.new", "password": pw("jung.new")})
        assert r.status_code == 403 and r.json()["code"] == code
    # 비밀번호가 틀리면 상태를 알리지 않는다
    r = client.post("/api/auth/login", json={"emp_no": "jung.new", "password": "wrongpass"})
    assert r.status_code == 401


def test_auth_t03_otp_flow(client):
    r = client.post("/api/auth/login", json={"emp_no": "admin", "password": pw("admin")})
    b = r.json()
    assert b["otp_required"] is True and "access_token" not in b
    otp_tok = b["otp_token"]
    # OTP 토큰으로 보호 API 불가
    assert client.get("/api/auth/me", headers=H(otp_tok)).status_code == 401
    bad = client.post("/api/auth/otp/verify", json={"code": "000000" if totp_now("admin") != "000000" else "111111"},
                      headers=H(otp_tok))
    assert bad.status_code == 400 and bad.json()["code"] == "OTP_INVALID"
    ok = client.post("/api/auth/otp/verify", json={"code": totp_now("admin")}, headers=H(otp_tok))
    assert ok.status_code == 200 and ok.json()["otp_required"] is False
    assert client.get("/api/auth/me", headers=H(ok.json()["access_token"])).status_code == 200
    # 같은 step 재사용 거절
    tok2 = client.post("/api/auth/login", json={"emp_no": "admin", "password": pw("admin")}).json()["otp_token"]
    again = client.post("/api/auth/otp/verify", json={"code": totp_now("admin")}, headers=H(tok2))
    assert again.status_code == 400 and again.json()["code"] == "OTP_INVALID"


def test_auth_otp_lock_after_5(client):
    tok = client.post("/api/auth/login", json={"emp_no": "lee.dwg", "password": pw("lee.dwg")}).json()["otp_token"]
    wrong = "123456" if totp_now("lee.dwg") != "123456" else "654321"
    for _ in range(5):
        assert client.post("/api/auth/otp/verify", json={"code": wrong}, headers=H(tok)).status_code == 400
    r = client.post("/api/auth/otp/verify", json={"code": totp_now("lee.dwg")}, headers=H(tok))
    assert r.status_code == 429 and r.json()["code"] == "OTP_LOCKED"
    assert r.json()["message"] == "인증 시도 횟수를 초과했습니다. 다시 로그인하세요."
    # 다시 로그인하면 새 토큰으로 가능
    tok2 = client.post("/api/auth/login", json={"emp_no": "lee.dwg", "password": pw("lee.dwg")}).json()["otp_token"]
    assert client.post("/api/auth/otp/verify", json={"code": totp_now("lee.dwg")}, headers=H(tok2)).status_code == 200


def test_totp_rfc6238_vector():
    # RFC 6238 SHA1 테스트 벡터(시드 "12345678901234567890", T=59 → 94287082의 마지막 6자리)
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert security.totp_at(secret, 59 // 30) == "287082"
    assert security.totp_at(secret, 1111111109 // 30) == "081804"


REG = {"last_name": "홍", "first_name": "길동", "birth_date": "1999-01-02", "phone": "01077778888",
       "email": "hong@swp.co.kr", "emp_no": "hong.gd", "password": "password1", "password_confirm": "password1"}


def test_auth_t04_register_validation(client):
    cases = [
        ({"first_name": ""}, "name", "성과 이름을 입력하세요."),
        ({"birth_date": "1999/01/02"}, "birth_date", "생년월일을 입력하세요."),
        ({"email": "bad@"}, "email", "이메일 형식이 올바르지 않습니다."),
        ({"phone": "0201234567"}, "phone", "전화번호 형식(010-0000-0000)이 올바르지 않습니다."),
        ({"emp_no": "ab"}, "emp_no", "아이디는 영문/숫자/._- 조합 4~20자입니다."),
        ({"password": "short", "password_confirm": "short"}, "password", "비밀번호는 8자 이상 입력하세요."),
        ({"password_confirm": "different1"}, "password_confirm", "비밀번호 확인이 일치하지 않습니다."),
    ]
    for patch, field, msg in cases:
        r = client.post("/api/auth/register", json={**REG, **patch})
        assert r.status_code == 400, patch
        assert r.json() == {"code": "VALIDATION_ERROR", "message": msg, "details": {"field": field}}
    dups = [
        ({"emp_no": "park.pm"}, "이미 사용 중인 아이디입니다."),
        ({"email": "PARK.PM@swp.co.kr"}, "이미 등록된 이메일입니다."),
        ({"phone": "010-2222-0002"}, "이미 등록된 전화번호입니다."),
    ]
    for patch, msg in dups:
        r = client.post("/api/auth/register", json={**REG, **patch})
        assert r.status_code == 409 and r.json()["code"] == "DUPLICATE" and r.json()["message"] == msg


def test_auth_t05_register_pending(client, conn):
    r = client.post("/api/auth/register", json=REG)
    assert r.status_code == 201
    assert r.json()["emp_no"] == "hong.gd" and r.json()["status"] == "pending"
    u = conn.execute("SELECT * FROM users WHERE emp_no='hong.gd'").fetchone()
    assert u["id"] == "u-hong.gd" and u["display_name"] == "홍길동" and u["phone"] == "010-7777-8888"
    assert u["created_at"] == "2026-10-19" and u["status"] == "pending"
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_AuthUser WHERE EmpNo='hong.gd'").fetchone()[0] == 0
    r = client.post("/api/auth/login", json={"emp_no": "hong.gd", "password": "password1"})
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_PENDING"


def test_auth_t06_logout_and_expiry(client, login, conn):
    h = login("park.pm")
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["message"] == "세션이 만료되었거나 유효하지 않습니다."
    h2 = login("park.pm")
    lid = security.decode_token(h2["Authorization"][7:])["lid"]
    expired = security.create_token("park.pm", "full", -10, lid=lid)
    assert client.get("/api/auth/me", headers=H(expired)).status_code == 401
    # 승인 해제된 사용자의 기존 토큰도 401
    conn.execute("UPDATE users SET status='disabled' WHERE emp_no='park.pm'")
    assert client.get("/api/auth/me", headers=h2).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_auth_t07_access_log_matches(client, login, conn):
    h = login("choi.qa")
    claims = security.decode_token(h["Authorization"][7:])
    row = conn.execute("SELECT * FROM TB_SYS_LogAccess WHERE LogId=?", (claims["lid"],)).fetchone()
    assert row["UserId"] == "choi.qa" and row["LoginDt"] and row["LogoutDt"] is None
    # 다른 사용자의 lid로 위조한 토큰은 거절
    forged = security.create_token("park.pm", "full", 100, lid=claims["lid"])
    assert client.get("/api/auth/me", headers=H(forged)).status_code == 401
    client.post("/api/auth/logout", headers=h)
    assert conn.execute("SELECT LogoutDt FROM TB_SYS_LogAccess WHERE LogId=?", (claims["lid"],)).fetchone()[0]


def test_pydantic_error_shape(client):
    r = client.post("/api/auth/login", json={"emp_no": 123, "password": ["x"]})
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR" and r.json()["message"] == "요청 형식이 올바르지 않습니다."
    auth.reset_otp_state()
