"""F01 인증: 로그인·OTP·가입·로그아웃·me. 가입 검증은 회원관리(F09)와 공유한다."""
import re
import sqlite3

from .. import config, db
from ..errors import AppError, duplicate, unauthorized, validation
from ..security import create_token, decode_token, hash_password, match_totp, verify_password
from ..util import is_date, utc_now

STATUS_ERRORS = {
    "pending": ("ACCOUNT_PENDING", "관리자 승인 대기 중인 계정입니다."),
    "rejected": ("ACCOUNT_REJECTED", "가입이 반려된 계정입니다."),
    "disabled": ("ACCOUNT_DISABLED", "사용이 중지된 계정입니다."),
}
INVALID_CREDENTIALS = "아이디 또는 비밀번호가 올바르지 않습니다."
OTP_MAX_FAIL = 5
DEMO_ROLES = {"admin": "admin", "han.wk": "user"}  # F16 데모 역할 전환 대상(emp_no → 역할)

# 프로세스 메모리: 토큰(jti)별 실패 횟수, 사용자별 마지막 사용 step
_otp_fail: dict[str, int] = {}
_otp_used: dict[str, int] = {}


def reset_otp_state() -> None:
    _otp_fail.clear()
    _otp_used.clear()


def groups_of(conn: sqlite3.Connection, emp_no: str) -> list[dict]:
    return [
        {"code": r[0], "name": r[1]}
        for r in conn.execute(
            "SELECT g.AuthCd, g.AuthNm FROM TB_SYS_AuthUser au JOIN TB_SYS_AuthGroup g ON g.AuthCd = au.AuthCd"
            " WHERE au.EmpNo = ? ORDER BY g.AuthCd",
            (emp_no,),
        )
    ]


def me(conn: sqlite3.Connection, user: dict) -> dict:
    out = {
        "emp_no": user["emp_no"],
        "display_name": user["display_name"],
        "email": user["email"],
        "status": user["status"],
        "totp_enabled": bool(user["totp_enabled"]),
        "groups": groups_of(conn, user["emp_no"]),
        "today": config.TODAY,
    }
    if config.demo_enabled() and user["emp_no"] in DEMO_ROLES:
        out["demo_role"] = DEMO_ROLES[user["emp_no"]]
    return out


def _check_status(user) -> None:
    if user["status"] in STATUS_ERRORS:
        code, msg = STATUS_ERRORS[user["status"]]
        raise AppError(403, code, msg)
    if user["status"] != "approved":
        raise AppError(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)


def start_session(conn: sqlite3.Connection, user, ip: str | None) -> dict:
    with db.tx(conn):
        cur = conn.execute(
            "INSERT INTO TB_SYS_LogAccess(UserId, LoginDt, IpAddress) VALUES (?, ?, ?)",
            (user["emp_no"], utc_now(), ip),
        )
        lid = cur.lastrowid
    ttl = config.token_ttl()
    return {
        "otp_required": False,
        "access_token": create_token(user["emp_no"], "full", ttl, lid=lid),
        "token_type": "bearer",
        "expires_in": ttl,
        "user": me(conn, dict(user)),
    }


def login(conn: sqlite3.Connection, emp_no: str, password: str, ip: str | None) -> dict:
    user = conn.execute("SELECT * FROM users WHERE emp_no = ?", (emp_no.strip(),)).fetchone()
    if not user or not verify_password(user["password_hash"], password):
        raise AppError(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)
    _check_status(user)
    if user["totp_enabled"] and user["totp_secret"]:
        ttl = config.otp_token_ttl()
        return {"otp_required": True, "otp_token": create_token(user["emp_no"], "otp", ttl), "expires_in": ttl}
    return start_session(conn, user, ip)


def verify_otp(conn: sqlite3.Connection, otp_token: str | None, code: str, ip: str | None) -> dict:
    p = decode_token(otp_token) if otp_token else None
    if not p or p.get("stage") != "otp":
        raise unauthorized()
    user = conn.execute("SELECT * FROM users WHERE emp_no = ?", (p["sub"],)).fetchone()
    if not user or not user["totp_enabled"] or not user["totp_secret"]:
        raise unauthorized()
    _check_status(user)
    jti = p["jti"]
    if _otp_fail.get(jti, 0) >= OTP_MAX_FAIL:
        raise AppError(429, "OTP_LOCKED", "인증 시도 횟수를 초과했습니다. 다시 로그인하세요.")
    step = match_totp(user["totp_secret"], (code or "").strip())
    if step is None or step <= _otp_used.get(user["emp_no"], -1):
        _otp_fail[jti] = _otp_fail.get(jti, 0) + 1
        raise AppError(400, "OTP_INVALID", "인증 코드가 올바르지 않습니다.", {"field": "code"})
    _otp_used[user["emp_no"]] = step
    _otp_fail.pop(jti, None)
    return start_session(conn, user, ip)


def logout(conn: sqlite3.Connection, lid: int) -> None:
    with db.tx(conn):
        conn.execute("UPDATE TB_SYS_LogAccess SET LogoutDt = ? WHERE LogId = ? AND LogoutDt IS NULL", (utc_now(), lid))


# --- 가입 검증 (회원관리와 공유)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^01\d-?\d{3,4}-?\d{4}$")
EMP_RE = re.compile(r"^[A-Za-z0-9._-]{4,20}$")


def normalize_phone(phone: str) -> str:
    d = re.sub(r"\D", "", phone)
    return f"{d[:3]}-{d[3:-4]}-{d[-4:]}"


def validate_user_fields(conn: sqlite3.Connection, data: dict, *, exclude_emp_no: str | None = None,
                         check_password: bool = True) -> dict:
    """가입/회원 입력을 순서대로 검사하고 정규화된 값을 돌려준다."""
    s = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}
    if not s.get("last_name") or not s.get("first_name"):
        raise validation("name", "성과 이름을 입력하세요.")
    if not is_date(s.get("birth_date")):
        raise validation("birth_date", "생년월일을 입력하세요.")
    if not EMAIL_RE.match(s.get("email") or ""):
        raise validation("email", "이메일 형식이 올바르지 않습니다.")
    if not PHONE_RE.match(s.get("phone") or ""):
        raise validation("phone", "전화번호 형식(010-0000-0000)이 올바르지 않습니다.")
    if exclude_emp_no is None and not EMP_RE.match(s.get("emp_no") or ""):
        raise validation("emp_no", "아이디는 영문/숫자/._- 조합 4~20자입니다.")
    if check_password:
        pw = data.get("password") or ""
        if len(pw) < 8:
            raise validation("password", "비밀번호는 8자 이상 입력하세요.")
        if pw != (data.get("password_confirm") or ""):
            raise validation("password_confirm", "비밀번호 확인이 일치하지 않습니다.")
    emp_no = exclude_emp_no or s["emp_no"]
    if exclude_emp_no is None and conn.execute("SELECT 1 FROM users WHERE emp_no = ?", (emp_no,)).fetchone():
        raise duplicate("이미 사용 중인 아이디입니다.", "emp_no")
    if conn.execute("SELECT 1 FROM users WHERE lower(email) = lower(?) AND emp_no <> ?", (s["email"], emp_no)).fetchone():
        raise duplicate("이미 등록된 이메일입니다.", "email")
    digits = re.sub(r"\D", "", s["phone"])
    if conn.execute("SELECT 1 FROM users WHERE replace(phone, '-', '') = ? AND emp_no <> ?", (digits, emp_no)).fetchone():
        raise duplicate("이미 등록된 전화번호입니다.", "phone")
    return {
        "last_name": s["last_name"], "first_name": s["first_name"], "birth_date": s["birth_date"],
        "email": s["email"], "phone": normalize_phone(s["phone"]), "emp_no": emp_no,
    }


def register(conn: sqlite3.Connection, data: dict) -> dict:
    v = validate_user_fields(conn, data)
    pw_hash = hash_password(data["password"])
    with db.tx(conn):
        conn.execute(
            "INSERT INTO users(id, email, password_hash, display_name, emp_no, status, auth_provider,"
            " last_name, first_name, birth_date, phone, totp_enabled, totp_secret, created_at)"
            " VALUES (?, ?, ?, ?, ?, 'pending', 'local', ?, ?, ?, ?, 0, NULL, ?)",
            ("u-" + v["emp_no"], v["email"], pw_hash, v["last_name"] + v["first_name"], v["emp_no"],
             v["last_name"], v["first_name"], v["birth_date"], v["phone"], config.TODAY),
        )
    return {"emp_no": v["emp_no"], "status": "pending", "message": "가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다."}


# --- F16 데모 역할 전환
def switch_demo_role(conn: sqlite3.Connection, user: dict, role: str | None, ip: str | None) -> dict:
    """조건(SHIPYARD_DEMO=1 + DB가 state/run/demo.db)과 대상(approved·OTP 끔)을 확인하고 현재 접속을 닫은 뒤 새 세션을 연다."""
    if not config.demo_enabled():
        raise AppError(403, "DEMO_DISABLED", "시연 모드에서만 역할을 전환할 수 있습니다.")
    emp = next((e for e, r in DEMO_ROLES.items() if r == role), None)
    target = conn.execute("SELECT * FROM users WHERE emp_no = ?", (emp,)).fetchone() if emp else None
    if not target or target["status"] != "approved" or target["totp_enabled"]:
        raise AppError(403, "DEMO_TARGET_UNAVAILABLE", "전환할 수 있는 시연 계정이 없습니다.")
    logout(conn, user["lid"])
    return start_session(conn, target, ip)
