"""F12 건의·문의(BR-11). 챗봇 접수(F13)도 create_inquiry를 그대로 쓴다."""
import sqlite3

from .. import db
from ..errors import AppError, not_found, validation
from ..permissions import menu_level
from ..util import utc_now

MENU = "M95"
CATEGORIES = {"BUG": "오류 신고", "FEATURE": "기능 건의", "QUESTION": "사용 문의", "ETC": "기타"}
STATUSES = {"OPEN": "접수", "IN_PROGRESS": "처리중", "DONE": "완료", "REJECTED": "반려"}
SQL = ("SELECT i.*, cu.display_name AS CreateUserNm, au.display_name AS AnswerUserNm FROM TB_SYS_Inquiry i"
       " LEFT JOIN users cu ON cu.emp_no = i.CreateUserId LEFT JOIN users au ON au.emp_no = i.AnswerUserId")


def is_admin(conn: sqlite3.Connection, emp_no: str) -> bool:
    return menu_level(conn, emp_no, MENU) >= 3


def _api(r, emp_no: str) -> dict:
    return {
        "inquiry_id": r["InquiryId"], "category": r["Category"], "title": r["Title"], "content": r["Content"],
        "status": r["Status"], "create_user_id": r["CreateUserId"], "create_user_nm": r["CreateUserNm"],
        "create_dt": r["CreateDt"], "modify_dt": r["ModifyDt"], "answer": r["Answer"], "answer_user_nm": r["AnswerUserNm"],
        "answer_dt": r["AnswerDt"], "mine": r["CreateUserId"] == emp_no,
    }


def list_inquiries(conn: sqlite3.Connection, user: dict, status: str | None, q: str | None, mine: bool) -> dict:
    admin = is_admin(conn, user["emp_no"])
    sql, params = SQL + " WHERE 1 = 1", []
    if not admin or mine:
        sql += " AND i.CreateUserId = ?"
        params.append(user["emp_no"])
    if q and q.strip():
        sql += " AND (instr(i.Title, ?) > 0 OR instr(i.Content, ?) > 0 OR instr(ifnull(cu.display_name, ''), ?) > 0)"
        params += [q.strip()] * 3
    rows = conn.execute(sql + " ORDER BY i.InquiryId DESC", params).fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["Status"]] += 1
    items = [_api(r, user["emp_no"]) for r in rows if not status or r["Status"] == status]
    return {"items": items, "total": len(items), "counts": counts, "is_admin": admin,
            "categories": CATEGORIES, "statuses": STATUSES}


def _clean(category, title, content) -> tuple[str, str, str]:
    if category not in CATEGORIES:
        raise validation("category", "분류를 선택하세요.")
    title, content = (title or "").strip(), (content or "").strip()
    if not title:
        raise validation("title", "제목을 입력하세요.")
    if len(title) > 200:
        raise validation("title", "제목은 200자 이하로 입력하세요.")
    if not content:
        raise validation("content", "내용을 입력하세요.")
    if len(content) > 5000:
        raise validation("content", "내용은 5000자 이하로 입력하세요.")
    return category, title, content


def create_inquiry(conn: sqlite3.Connection, emp_no: str, category, title, content) -> dict:
    c, t, b = _clean(category, title, content)
    with db.tx(conn):
        iid = conn.execute("INSERT INTO TB_SYS_Inquiry(Category, Title, Content, Status, CreateUserId, CreateDt)"
                           " VALUES (?, ?, ?, 'OPEN', ?, ?)", (c, t, b, emp_no, utc_now())).lastrowid
    return _api(_row(conn, iid), emp_no)


def _row(conn: sqlite3.Connection, inquiry_id: int):
    r = conn.execute(SQL + " WHERE i.InquiryId = ?", (inquiry_id,)).fetchone()
    if not r:
        raise not_found("INQUIRY_NOT_FOUND", "글을 찾을 수 없습니다.")
    return r


def _visible(conn: sqlite3.Connection, inquiry_id: int, user: dict):
    r = _row(conn, inquiry_id)
    admin = is_admin(conn, user["emp_no"])
    if not admin and r["CreateUserId"] != user["emp_no"]:
        raise AppError(403, "FORBIDDEN", "본인이 작성한 글만 볼 수 있습니다.")
    return r, admin


def get_inquiry(conn: sqlite3.Connection, inquiry_id: int, user: dict) -> dict:
    return _api(_visible(conn, inquiry_id, user)[0], user["emp_no"])


def update_inquiry(conn: sqlite3.Connection, inquiry_id: int, data: dict, fields: set[str], user: dict) -> dict:
    r, admin = _visible(conn, inquiry_id, user)
    sets: dict = {}
    if fields & {"category", "title", "content"}:
        if r["CreateUserId"] != user["emp_no"]:
            raise AppError(403, "FORBIDDEN", "작성자만 수정할 수 있습니다.")
        if r["Status"] != "OPEN":
            raise AppError(409, "INVALID_STATUS", "접수 상태인 글만 수정할 수 있습니다.")
        c, t, b = _clean(data.get("category") if "category" in fields else r["Category"],
                         data.get("title") if "title" in fields else r["Title"],
                         data.get("content") if "content" in fields else r["Content"])
        sets |= {"Category": c, "Title": t, "Content": b, "ModifyDt": utc_now()}
    if fields & {"status", "answer"}:
        if not admin:
            raise AppError(403, "FORBIDDEN", "관리자만 처리할 수 있습니다.")
        status = data.get("status") if "status" in fields and data.get("status") is not None else r["Status"]
        if status not in STATUSES:
            raise validation("status", "허용되지 않는 상태입니다.")
        answer = (data.get("answer") or "").strip() or None if "answer" in fields else r["Answer"]
        if status in ("DONE", "REJECTED") and not answer:
            raise validation("answer", "완료·반려 처리에는 답변을 입력하세요.")
        if status != r["Status"] or answer != r["Answer"]:
            sets |= {"Status": status, "Answer": answer, "AnswerUserId": user["emp_no"], "AnswerDt": utc_now()}
    if sets:
        with db.tx(conn):
            conn.execute(f"UPDATE TB_SYS_Inquiry SET {', '.join(f'{k} = ?' for k in sets)} WHERE InquiryId = ?",
                         [*sets.values(), inquiry_id])
    return _api(_row(conn, inquiry_id), user["emp_no"])


def delete_inquiry(conn: sqlite3.Connection, inquiry_id: int, user: dict) -> None:
    r, admin = _visible(conn, inquiry_id, user)
    if not admin:
        if r["CreateUserId"] != user["emp_no"]:
            raise AppError(403, "FORBIDDEN", "작성자만 삭제할 수 있습니다.")
        if r["Status"] != "OPEN":
            raise AppError(409, "INVALID_STATUS", "접수 상태인 글만 삭제할 수 있습니다.")
    with db.tx(conn):
        conn.execute("DELETE FROM TB_SYS_Inquiry WHERE InquiryId = ?", (inquiry_id,))
