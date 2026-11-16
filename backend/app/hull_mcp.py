"""F13 MCP 서버(stdio, 줄 단위 JSON-RPC 2.0). 실행: python -m app.hull_mcp <emp_no> (cwd=backend).

stdout에는 프로토콜만 쓴다. 조회 도구는 query_only 연결로 메뉴 View 권한(BR-10)을 확인한다.
"""
import json
import sqlite3
import sys
import uuid
from contextlib import contextmanager

from . import db
from .errors import AppError
from .permissions import menu_level

PROTOCOL = "2025-03-26"
SERVER_INFO = {"name": "shipyard-hulls", "version": "4.0"}
FORBIDDEN = {"forbidden": True}


class BadArgs(Exception):
    pass


@contextmanager
def _ro():
    conn = db.connect()
    conn.execute("PRAGMA query_only=ON")
    try:
        yield conn
    finally:
        conn.close()


def _allowed(conn: sqlite3.Connection, emp_no: str, menu_id: str, level: int = 1) -> bool:
    u = conn.execute("SELECT status FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    return bool(u) and u[0] == "approved" and menu_level(conn, emp_no, menu_id) >= level


def _keys(args: dict, allowed: set[str]) -> None:
    if not isinstance(args, dict) or set(args) - allowed:
        raise BadArgs("허용되지 않는 인자입니다.")


def _str(args: dict, key: str, max_len: int, required: bool = False, min_len: int = 0) -> str | None:
    v = args.get(key)
    if v is None and not required:
        return None
    if not isinstance(v, str) or not (min_len <= len(v) <= max_len):
        raise BadArgs(f"{key} 형식이 올바르지 않습니다.")
    return v


def search_hulls(emp_no: str, args: dict) -> dict:
    from .services.hulls import list_hulls
    _keys(args, {"query"})
    q = _str(args, "query", 100) or ""
    with _ro() as conn:
        if not _allowed(conn, emp_no, "M11"):
            return FORBIDDEN
        rows = list_hulls(conn, q=q)
    keys = ("hull_no", "hull_nm", "hull_status", "progress", "delay_count", "delivery_dt")
    return {"hulls": [{k: h[k] for k in keys} for h in rows[:20]], "total": len(rows)}


def list_drawings(emp_no: str, args: dict) -> dict:
    from .services import drawings
    _keys(args, set())
    with _ro() as conn:
        if not _allowed(conn, emp_no, "M31"):
            return FORBIDDEN
        rows = drawings.list_drawings(conn)
    keys = ("drawing_id", "drawing_no", "drawing_nm", "hull_no", "dwg_status")
    return {"items": [{k: d[k] for k in keys} for d in rows]}


def list_progress_hulls(emp_no: str, args: dict) -> dict:
    from .services.progress import progress_hulls
    _keys(args, set())
    with _ro() as conn:
        if not _allowed(conn, emp_no, "M22"):
            return FORBIDDEN
        hulls = progress_hulls(conn)["hulls"]
    return {"items": [{"hull_no": h["hull_no"], "hull_nm": h["hull_nm"]} for h in hulls]}


def submit_feedback(emp_no: str, args: dict) -> dict:
    from .services.chat import save_feedback
    _keys(args, {"kind", "content", "request_id"})
    kind = args.get("kind")
    if kind not in ("suggestion", "inquiry"):
        raise BadArgs("kind 형식이 올바르지 않습니다.")
    content = _str(args, "content", 2000, required=True, min_len=1)
    try:
        rid = str(uuid.UUID(_str(args, "request_id", 64, required=True)))
    except ValueError as e:
        raise BadArgs("request_id 형식이 올바르지 않습니다.") from e
    conn = db.connect()
    try:
        if not _allowed(conn, emp_no, "M95", 2):
            return FORBIDDEN
        return save_feedback(conn, emp_no, kind, content, rid)
    finally:
        conn.close()


def build_report(emp_no: str, args: dict) -> dict:
    from .services import reports
    _keys(args, {"format", "hull_no"})
    fmt = args.get("format")
    if fmt not in reports.FORMATS:
        raise BadArgs("format 형식이 올바르지 않습니다.")
    hull_no = _str(args, "hull_no", 20) or None
    with _ro() as conn:
        return reports.build(conn, emp_no, fmt, hull_no)


def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


TOOLS = {
    "search_hulls": (search_hulls, "호선 번호·이름으로 검색(최대 20척)",
                     _schema({"query": {"type": "string", "maxLength": 100}})),
    "list_drawings": (list_drawings, "도면 목록", _schema({})),
    "list_progress_hulls": (list_progress_hulls, "공정이 등록된 호선 목록", _schema({})),
    "submit_feedback": (submit_feedback, "건의·문의 접수", _schema({
        "kind": {"enum": ["suggestion", "inquiry"]}, "content": {"type": "string", "minLength": 1, "maxLength": 2000},
        "request_id": {"type": "string", "format": "uuid"}}, ["kind", "content", "request_id"])),
    "build_report": (build_report, "호선·공정·도면 현황 보고서 생성(PDF·XLSX)", _schema({
        "format": {"enum": ["pdf", "xlsx"]}, "hull_no": {"type": "string", "maxLength": 20}}, ["format"])),
}


def handle(emp_no: str, msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:  # 알림(notifications/initialized 등)은 응답하지 않는다
        return None
    ok = lambda result: {"jsonrpc": "2.0", "id": mid, "result": result}  # noqa: E731
    err = lambda code, text: {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": text}}  # noqa: E731
    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})
    if method == "tools/list":
        return ok({"tools": [{"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in TOOLS.items()]})
    if method == "tools/call":
        tool = TOOLS.get(params.get("name"))
        if not tool:
            return err(-32602, "알 수 없는 도구입니다.")
        try:
            out = tool[0](emp_no, params.get("arguments") or {})
        except BadArgs as e:
            return err(-32602, str(e))
        except AppError as e:
            out = {"error": e.message, "status": e.status, "code": e.code}
        text = json.dumps(out, ensure_ascii=False)
        return ok({"content": [{"type": "text", "text": text}], "structuredContent": out, "isError": False})
    return err(-32601, "지원하지 않는 메서드입니다.")


def main() -> None:
    emp_no = sys.argv[1] if len(sys.argv) > 1 else ""
    out = sys.stdout
    sys.stdout = sys.stderr  # 라이브러리 출력이 프로토콜에 섞이지 않게
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            try:
                resp = handle(emp_no, msg)
            except Exception as e:  # noqa: BLE001 — 프로세스는 응답을 남기고 계속한다
                resp = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": str(e)}}
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
