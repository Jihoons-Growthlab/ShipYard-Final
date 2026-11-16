"""F09 회원관리 + 회원별 메뉴 권한(BR-10 판정은 permissions 한 곳)."""
import sqlite3

from .. import config, db
from ..errors import AppError, not_found, validation
from ..permissions import LEVELS, group_levels, menu_level
from ..security import hash_password
from .auth import groups_of, validate_user_fields

STATUSES = ("pending", "approved", "rejected", "disabled")
USER_MENU = "M91"  # 회원관리: 쓰기는 Admin으로 저장


def user_not_found() -> AppError:
    return not_found("USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")


def _api(conn: sqlite3.Connection, r) -> dict:
    return {
        "emp_no": r["emp_no"], "last_name": r["last_name"], "first_name": r["first_name"],
        "display_name": r["display_name"], "email": r["email"], "phone": r["phone"], "birth_date": r["birth_date"],
        "status": r["status"], "totp_enabled": bool(r["totp_enabled"]), "groups": groups_of(conn, r["emp_no"]),
        "created_at": r["created_at"],
    }


def _row(conn: sqlite3.Connection, emp_no: str):
    r = conn.execute("SELECT * FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    if not r:
        raise user_not_found()
    return r


def list_users(conn: sqlite3.Connection, status: str | None, q: str | None) -> dict:
    sql, params = "SELECT * FROM users WHERE 1 = 1", []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q and q.strip():
        sql += " AND (" + " OR ".join(f"instr(lower({c}), lower(?)) > 0" for c in ("emp_no", "display_name", "email", "phone")) + ")"
        params += [q.strip()] * 4
    users = [_api(conn, r) for r in conn.execute(sql + " ORDER BY created_at, emp_no", params)]
    pending = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    return {"users": users, "total": len(users), "pending": pending}


def get_user(conn: sqlite3.Connection, emp_no: str) -> dict:
    return _api(conn, _row(conn, emp_no))


def auth_groups(conn: sqlite3.Connection) -> list[dict]:
    return [{"code": r[0], "name": r[1]} for r in conn.execute("SELECT AuthCd, AuthNm FROM TB_SYS_AuthGroup ORDER BY rowid")]


def _check_groups(conn: sqlite3.Connection, groups: list[str]) -> list[str]:
    valid = {g["code"] for g in auth_groups(conn)}
    if any(g not in valid for g in groups):
        raise validation("groups", "존재하지 않는 권한 그룹입니다.")
    return list(dict.fromkeys(groups))


def _check_common(conn: sqlite3.Connection, data: dict, has_secret: bool) -> None:
    if data.get("status") is not None and data["status"] not in STATUSES:
        raise validation("status", "허용되지 않는 상태입니다.")
    if data.get("groups") is not None:
        _check_groups(conn, data["groups"])
    if data.get("totp_enabled") and not has_secret:
        raise AppError(409, "OTP_NOT_ENROLLED", "OTP가 등록되지 않은 사용자는 2차인증을 켤 수 없습니다.")


def _check_password(pw: str) -> None:
    if len(pw) < 8:
        raise validation("password", "비밀번호는 8자 이상 입력하세요.")


def _set_groups(conn: sqlite3.Connection, emp_no: str, groups: list[str]) -> None:
    conn.execute("DELETE FROM TB_SYS_AuthUser WHERE EmpNo = ?", (emp_no,))
    conn.executemany("INSERT INTO TB_SYS_AuthUser(AuthCd, EmpNo) VALUES (?, ?)", [(g, emp_no) for g in dict.fromkeys(groups)])


def create_user(conn: sqlite3.Connection, data: dict) -> dict:
    v = validate_user_fields(conn, data, check_password=False)
    _check_password(data.get("password") or "")
    _check_common(conn, data, has_secret=False)
    with db.tx(conn):
        conn.execute(
            "INSERT INTO users(id, email, password_hash, display_name, emp_no, status, auth_provider,"
            " last_name, first_name, birth_date, phone, totp_enabled, totp_secret, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'local', ?, ?, ?, ?, 0, NULL, ?)",
            ("u-" + v["emp_no"], v["email"], hash_password(data["password"]), v["last_name"] + v["first_name"],
             v["emp_no"], data.get("status") or "approved", v["last_name"], v["first_name"], v["birth_date"], v["phone"],
             config.TODAY),
        )
        _set_groups(conn, v["emp_no"], data.get("groups") or [])
    return get_user(conn, v["emp_no"])


def update_user(conn: sqlite3.Connection, emp_no: str, data: dict, fields: set[str]) -> dict:
    cur = _row(conn, emp_no)
    if "emp_no" in fields and (data.get("emp_no") or "").strip() not in ("", emp_no):
        raise validation("emp_no", "아이디는 변경할 수 없습니다.")
    base = {k: cur[k] for k in ("last_name", "first_name", "birth_date", "phone", "email")}
    merged = base | {k: data[k] for k in base if k in fields and data.get(k) is not None}
    v = validate_user_fields(conn, merged, exclude_emp_no=emp_no, check_password=False)
    pw = data.get("password") or ""
    if pw:
        _check_password(pw)
    _check_common(conn, {k: data.get(k) for k in ("status", "groups", "totp_enabled") if k in fields},
                  has_secret=bool(cur["totp_secret"]))
    sets = {"last_name": v["last_name"], "first_name": v["first_name"], "birth_date": v["birth_date"],
            "phone": v["phone"], "email": v["email"], "display_name": v["last_name"] + v["first_name"]}
    if pw:
        sets["password_hash"] = hash_password(pw)
    if "status" in fields and data.get("status") is not None:
        sets["status"] = data["status"]
    if "totp_enabled" in fields and data.get("totp_enabled") is not None:
        sets["totp_enabled"] = 1 if data["totp_enabled"] else 0  # 끌 때 secret 유지
    with db.tx(conn):
        conn.execute(f"UPDATE users SET {', '.join(f'{k} = ?' for k in sets)} WHERE emp_no = ?", [*sets.values(), emp_no])
        if "groups" in fields and data.get("groups") is not None:
            _set_groups(conn, emp_no, data["groups"])
    return get_user(conn, emp_no)


def approve(conn: sqlite3.Connection, emp_no: str, groups: list[str]) -> dict:
    cur = _row(conn, emp_no)
    if cur["status"] != "pending":
        raise AppError(409, "INVALID_STATUS", "승인 대기 상태가 아닙니다.")
    if not groups:
        raise validation("groups", "승인 시 권한 그룹을 1개 이상 지정하세요.")
    groups = _check_groups(conn, groups)
    with db.tx(conn):
        conn.execute("UPDATE users SET status = 'approved' WHERE emp_no = ?", (emp_no,))
        _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def reject(conn: sqlite3.Connection, emp_no: str) -> dict:
    cur = _row(conn, emp_no)
    if cur["status"] != "pending":
        raise AppError(409, "INVALID_STATUS", "승인 대기 상태가 아닙니다.")
    with db.tx(conn):
        conn.execute("UPDATE users SET status = 'rejected' WHERE emp_no = ?", (emp_no,))
    return get_user(conn, emp_no)


# FK가 없는 작성자·수정자 컬럼(FK 있는 담당자·결재자·로그는 ON DELETE SET NULL)
_LOOSE_REFS = (("TB_MST_Hull", "CreateUserId"), ("TB_MST_Hull", "ModifyUserId"), ("TB_PRC_Plan", "CreateUserId"),
               ("TB_DWG_Drawing", "CreateUserId"), ("TB_DWG_Drawing", "ModifyUserId"))


def delete_user(conn: sqlite3.Connection, emp_no: str, me: dict) -> None:
    _row(conn, emp_no)
    if emp_no == me["emp_no"]:
        raise AppError(409, "SELF_DELETE", "로그인 중인 본인 계정은 삭제할 수 없습니다.")
    with db.tx(conn):
        for t, c in _LOOSE_REFS:
            conn.execute(f"UPDATE {t} SET {c} = NULL WHERE {c} = ?", (emp_no,))
        conn.execute("DELETE FROM users WHERE emp_no = ?", (emp_no,))


# --- 회원별 메뉴 권한 (화면 단위 0 없음 / 1 읽기 / 2 쓰기)
def _screen(level: int) -> int:
    return min(level, 2)


def _stored_name(menu_id: str, level: int) -> str:
    return {0: "None", 1: "View"}.get(level) or ("Admin" if menu_id == USER_MENU else "Write")


def user_menus(conn: sqlite3.Connection, emp_no: str) -> dict:
    _row(conn, emp_no)
    groups = group_levels(conn, emp_no)
    own = {r[0]: _screen(LEVELS.get(r[1], 0)) for r in conn.execute(
        "SELECT MenuId, AuthGbn FROM TB_SYS_UserMenu WHERE EmpNo = ?", (emp_no,))}
    menus = []
    for r in conn.execute("SELECT MenuId, ParentId, Title, Seq FROM TB_SYS_MenuInfo WHERE UseYN = 1 ORDER BY Seq, MenuId"):
        g = _screen(groups.get(r[0], 0))
        u = own.get(r[0])
        menus.append({"menu_id": r[0], "parent_id": r[1], "title": r[2], "seq": r[3], "group_level": g,
                      "user_level": u, "level": g if u is None else u})
    return {"emp_no": emp_no, "menus": menus}


def set_user_menus(conn: sqlite3.Connection, emp_no: str, items: list[dict], me: dict) -> dict:
    """전체 교체. 그룹과 같은 값은 저장하지 않는다. 본인의 M91 결과가 Admin 미만이면 409."""
    _row(conn, emp_no)
    valid = {r[0] for r in conn.execute("SELECT MenuId FROM TB_SYS_MenuInfo")}
    groups = group_levels(conn, emp_no)
    rows = {}
    for it in items:
        mid, lv = it.get("menu_id"), it.get("level")
        if mid not in valid:
            raise validation("menus", "존재하지 않는 메뉴입니다.")
        if lv is not None and (isinstance(lv, bool) or lv not in (0, 1, 2)):
            raise validation("menus", "허용되지 않는 권한입니다.")
        if lv is None or lv == _screen(groups.get(mid, 0)):
            rows.pop(mid, None)
        else:
            rows[mid] = _stored_name(mid, int(lv))
    with db.tx(conn):
        conn.execute("DELETE FROM TB_SYS_UserMenu WHERE EmpNo = ?", (emp_no,))
        conn.executemany("INSERT INTO TB_SYS_UserMenu(EmpNo, MenuId, AuthGbn) VALUES (?, ?, ?)",
                         [(emp_no, m, g) for m, g in rows.items()])
        if emp_no == me["emp_no"] and menu_level(conn, emp_no, USER_MENU) < LEVELS["Admin"]:
            raise AppError(409, "SELF_LOCKOUT", "본인의 회원관리 쓰기 권한은 낮출 수 없습니다.")
    return user_menus(conn, emp_no)
