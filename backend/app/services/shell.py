"""F02 메뉴·메뉴 접근 기록·공통 코드."""
import sqlite3

from .. import db
from ..errors import AppError, not_found
from ..permissions import NAMES, menu_levels
from ..util import utc_now


def visible_menus(conn: sqlite3.Connection, emp_no: str) -> list[dict]:
    levels = menu_levels(conn, emp_no)
    rows = conn.execute(
        "SELECT MenuId, ParentId, Title, TokenUrl, Seq FROM TB_SYS_MenuInfo WHERE UseYN = 1 ORDER BY Seq, MenuId"
    ).fetchall()
    by_id = {r["MenuId"]: r for r in rows}
    memo: dict[str, bool] = {}

    def visible(mid: str) -> bool:
        if mid not in memo:
            r = by_id.get(mid)
            memo[mid] = bool(r) and levels.get(mid, 0) >= 1 and (r["ParentId"] is None or visible(r["ParentId"]))
        return memo[mid]

    out = []
    for r in rows:
        if visible(r["MenuId"]):
            lv = levels[r["MenuId"]]
            out.append({
                "menu_id": r["MenuId"], "parent_id": r["ParentId"], "title": r["Title"], "token": r["TokenUrl"],
                "seq": r["Seq"], "level": lv, "auth_gbn": NAMES[lv], "can_write": lv >= 2,
            })
    return out


def record_menu_access(conn: sqlite3.Connection, user: dict, menu_id: str) -> None:
    if not conn.execute("SELECT 1 FROM TB_SYS_MenuInfo WHERE MenuId = ?", (menu_id,)).fetchone():
        raise not_found("MENU_NOT_FOUND", "메뉴를 찾을 수 없습니다.")
    if menu_levels(conn, user["emp_no"]).get(menu_id, 0) < 1:
        raise AppError(403, "FORBIDDEN", "해당 화면에 대한 권한이 없습니다.", {"menu_id": menu_id})
    with db.tx(conn):
        conn.execute("INSERT INTO TB_SYS_LogMenuAccess(MenuId, LogId, InDt) VALUES (?, ?, ?)",
                     (menu_id, user["lid"], utc_now()))


def codes(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in conn.execute(
        "SELECT c.CodeGroup, c.Code, c.CodeName FROM TB_SYS_Code c JOIN TB_SYS_CodeGroup g ON g.CodeGroup = c.CodeGroup"
        " WHERE c.UseYN = 1 AND g.UseYN = 1 ORDER BY g.Seq, c.Seq, c.Code"
    ):
        out.setdefault(r[0], []).append({"code": r[1], "name": r[2]})
    return out


def code_set(conn: sqlite3.Connection, group: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT Code FROM TB_SYS_Code WHERE CodeGroup = ? AND UseYN = 1", (group,))}


def approved_user(conn: sqlite3.Connection, emp_no: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM users WHERE emp_no = ? AND status = 'approved'", (emp_no,)).fetchone())


def user_options(conn: sqlite3.Connection) -> list[dict]:
    return [
        {"emp_no": r[0], "display_name": r[1]}
        for r in conn.execute("SELECT emp_no, display_name FROM users WHERE status = 'approved' ORDER BY display_name, emp_no")
    ]
