"""요청 의존성: DB 연결, 현재 사용자, 메뉴 권한 검사."""
import sqlite3

from fastapi import Depends, Request

from .db import get_db
from .errors import AppError, unauthorized
from .permissions import menu_level
from .security import decode_token


def bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or ""
    if h[:7].lower() != "bearer ":
        return None
    return h[7:].strip() or None


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """stage=full, 열린 접근 로그, 일치하는 사용자, approved 상태를 확인한다."""
    tok = bearer(request)
    p = decode_token(tok) if tok else None
    if not p or p.get("stage") != "full" or not p.get("lid"):
        raise unauthorized()
    row = conn.execute(
        "SELECT u.* FROM TB_SYS_LogAccess l JOIN users u ON u.emp_no = l.UserId"
        " WHERE l.LogId = ? AND l.LogoutDt IS NULL AND u.emp_no = ?",
        (p["lid"], p["sub"]),
    ).fetchone()
    if not row or row["status"] != "approved":
        raise unauthorized()
    user = dict(row)
    user["lid"] = p["lid"]
    request.state.user = user
    request.state.emp_no = user["emp_no"]  # 사용 로그(F11)
    return user


VIEW, WRITE, ADMIN = 1, 2, 3
FORBIDDEN_MSG = "해당 화면에 대한 권한이 없습니다."


def forbidden(menu_id: str) -> AppError:
    return AppError(403, "FORBIDDEN", FORBIDDEN_MSG, {"menu_id": menu_id})


def require(menu_id: str, min_level: int = VIEW):
    """메뉴 ID와 최소 등급(View=1, Write=2, Admin=3). 미달이면 403. 등급은 BR-10 함수로 요청마다 DB에서 읽는다."""
    def dep(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        if menu_level(conn, user["emp_no"], menu_id) < min_level:
            raise forbidden(menu_id)
        return user
    return dep
