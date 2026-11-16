"""F07 도면·리비전·PDF·결재 요청·배포·공정 연계(BR-02, 06~08). API↔DB 매핑은 이 파일 한 곳."""
import re
import secrets
import sqlite3
from pathlib import Path

from .. import config, db, storage
from ..errors import AppError, duplicate, not_found, validation
from ..util import blank_to_none
from . import plans as plan_svc
from . import rules
from .shell import approved_user, code_set

MAX_PDF = 30 * 1024 * 1024
EDITABLE = {"drawing_nm": "DrawingNm", "discipline": "Discipline", "block_id": "BlockId", "designer_emp_no": "DesignerEmpNo"}
MSG_NEW_REV = "최신 리비전이 배포/폐기 상태일 때만 신규 리비전을 작성할 수 있습니다."
MSG_REQ = "최신 작성중(DRAFT) 리비전만 결재 요청할 수 있습니다."
MSG_ISSUE = "승인(APPROVED)된 리비전만 배포할 수 있습니다."
MSG_UPLOAD = "작성중(DRAFT) 리비전만 업로드할 수 있습니다."
MSG_FILE_DEL = "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다."

LIST_SQL = (
    "SELECT d.*, b.BlockCd, b.BlockNm, u.display_name AS DesignerNm,"
    " (SELECT MAX(RevNo) FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId) AS LatestRevNo,"
    " (SELECT COUNT(*) FROM TB_DWG_PlanLink l WHERE l.DrawingId = d.DrawingId) AS LinkCount"
    " FROM TB_DWG_Drawing d LEFT JOIN TB_MST_Block b ON b.BlockId = d.BlockId"
    " LEFT JOIN users u ON u.emp_no = d.DesignerEmpNo"
)


def drawing_not_found() -> AppError:
    return not_found("DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")


def rev_state(message: str) -> AppError:
    return AppError(409, "INVALID_REV_STATE", message)


def _item(r) -> dict:
    return {
        "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "drawing_nm": r["DrawingNm"], "hull_no": r["HullNo"],
        "block_id": r["BlockId"], "block_cd": r["BlockCd"], "discipline": r["Discipline"], "dwg_status": r["DwgStatus"],
        "current_rev_no": r["CurrentRevNo"], "latest_rev_no": r["LatestRevNo"], "designer_emp_no": r["DesignerEmpNo"],
        "designer_nm": r["DesignerNm"], "link_count": r["LinkCount"],
    }


def list_drawings(conn: sqlite3.Connection, hull_no=None, discipline=None, status=None, q=None) -> list[dict]:
    sql, params = LIST_SQL + " WHERE 1 = 1", []
    for col, v in (("d.HullNo", hull_no), ("d.Discipline", discipline), ("d.DwgStatus", status)):
        if v:
            sql += f" AND {col} = ?"
            params.append(v)
    if q and q.strip():
        sql += " AND (instr(lower(d.DrawingNo), lower(?)) > 0 OR instr(lower(d.DrawingNm), lower(?)) > 0)"
        params += [q.strip(), q.strip()]
    return [_item(r) for r in conn.execute(sql + " ORDER BY d.DrawingId", params)]


def _row(conn: sqlite3.Connection, drawing_id: int):
    r = conn.execute(LIST_SQL + " WHERE d.DrawingId = ?", (drawing_id,)).fetchone()
    if not r:
        raise drawing_not_found()
    return r


def _rev(conn: sqlite3.Connection, drawing_id: int, rev_no: int):
    r = conn.execute("SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no)).fetchone()
    if not r:
        raise not_found("REVISION_NOT_FOUND", "리비전을 찾을 수 없습니다.")
    return r


def _latest(conn: sqlite3.Connection, drawing_id: int):
    return conn.execute("SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? ORDER BY RevNo DESC LIMIT 1",
                        (drawing_id,)).fetchone()


def revisions(conn: sqlite3.Connection, drawing_id: int) -> list[dict]:
    _row(conn, drawing_id)
    return [{
        "rev_no": r["RevNo"], "rev_status": r["RevStatus"], "change_desc": r["ChangeDesc"], "has_file": bool(r["FileId"]),
        "file_nm": r["FileNm"], "author_emp_no": r["AuthorEmpNo"], "author_nm": r["AuthorNm"], "issue_dt": r["IssueDt"],
        "create_dt": r["CreateDt"],
    } for r in conn.execute(
        "SELECT r.*, u.display_name AS AuthorNm FROM TB_DWG_Revision r LEFT JOIN users u ON u.emp_no = r.AuthorEmpNo"
        " WHERE r.DrawingId = ? ORDER BY r.RevNo DESC", (drawing_id,))]


def _approvals(conn: sqlite3.Connection, drawing_id: int) -> list[dict]:
    return [{
        "approval_id": r["ApprovalId"], "rev_no": r["RevNo"], "step_no": r["StepNo"], "approver_emp_no": r["ApproverEmpNo"],
        "approver_nm": r["ApproverNm"], "result": r["Result"], "comment": r["Comment"], "act_dt": r["ActDt"],
    } for r in conn.execute(
        "SELECT a.*, u.display_name AS ApproverNm FROM TB_DWG_Approval a LEFT JOIN users u ON u.emp_no = a.ApproverEmpNo"
        " WHERE a.DrawingId = ? ORDER BY a.RevNo DESC, a.StepNo", (drawing_id,))]


def _plan_rows(conn: sqlite3.Connection, where: str, params: tuple):
    rows = conn.execute(plan_svc.PLAN_SQL + " " + where, params).fetchall()
    return sorted(rows, key=lambda r: rules.plan_sort_key(r["BlockCd"], r["ProcSeq"], r["PlanId"]))


def linked_plans(conn: sqlite3.Connection, drawing_id: int) -> dict:
    d = _row(conn, drawing_id)
    links = {r[0]: r for r in conn.execute(
        "SELECT PlanId, RequiredYN, NeedDt FROM TB_DWG_PlanLink WHERE DrawingId = ?", (drawing_id,))}
    linked = [{
        "plan_id": r["PlanId"], "label": rules.plan_label(r["BlockCd"], r["HullNo"], r["ProcNm"]),
        "plan_status": r["PlanStatus"], "required": bool(links[r["PlanId"]]["RequiredYN"]),
        "need_dt": links[r["PlanId"]]["NeedDt"], "plan_start_dt": r["PlanStartDt"], "plan_end_dt": r["PlanEndDt"],
    } for r in _plan_rows(conn, "WHERE p.PlanId IN (SELECT PlanId FROM TB_DWG_PlanLink WHERE DrawingId = ?)", (drawing_id,))]
    available = [{
        "plan_id": r["PlanId"], "label": rules.plan_label(r["BlockCd"], r["HullNo"], r["ProcNm"]),
        "plan_status": r["PlanStatus"], "plan_start_dt": r["PlanStartDt"], "plan_end_dt": r["PlanEndDt"],
    } for r in _plan_rows(conn, "WHERE p.HullNo = ? AND p.PlanId NOT IN (SELECT PlanId FROM TB_DWG_PlanLink WHERE DrawingId = ?)",
                          (d["HullNo"], drawing_id))]
    return {"plans": linked, "available_plans": available}


def get_drawing(conn: sqlite3.Connection, drawing_id: int) -> dict:
    r = _row(conn, drawing_id)
    return _item(r) | {
        "block_nm": r["BlockNm"], "create_user_id": r["CreateUserId"], "create_dt": r["CreateDt"],
        "modify_user_id": r["ModifyUserId"], "modify_dt": r["ModifyDt"], "today": config.TODAY,
        "revisions": revisions(conn, drawing_id), "approvals": _approvals(conn, drawing_id),
        **linked_plans(conn, drawing_id), "impacts": rules.revision_impacts(conn, drawing_id=drawing_id),
    }


# --- 도면 CRUD
def _validate(conn: sqlite3.Connection, hull_no: str, v: dict) -> None:
    if not v.get("drawing_nm"):
        raise validation("drawing_nm", "도면명을 입력하세요.")
    if v.get("discipline") and v["discipline"] not in code_set(conn, "DWGDISC"):
        raise validation("discipline", "허용되지 않는 분야입니다.")
    if v.get("block_id") is not None and not conn.execute(
            "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (v["block_id"], hull_no)).fetchone():
        raise validation("block_id", "해당 호선의 블록이 아닙니다.")
    if v.get("designer_emp_no") and not approved_user(conn, v["designer_emp_no"]):
        raise validation("designer_emp_no", "승인된 회원만 지정할 수 있습니다.")


def create_drawing(conn: sqlite3.Connection, data: dict, user: dict) -> dict:
    v = {k: blank_to_none(x) for k, x in data.items()}
    if not v.get("drawing_no"):
        raise validation("drawing_no", "도면번호를 입력하세요.")
    if not v.get("hull_no") or not conn.execute("SELECT 1 FROM TB_MST_Hull WHERE HullNo = ?", (v["hull_no"],)).fetchone():
        raise validation("hull_no", "호선을 선택하세요.")
    _validate(conn, v["hull_no"], v)
    if conn.execute("SELECT 1 FROM TB_DWG_Drawing WHERE DrawingNo = ?", (v["drawing_no"],)).fetchone():
        raise duplicate("이미 존재하는 도면번호입니다.", "drawing_no")
    with db.tx(conn):
        did = conn.execute(
            "INSERT INTO TB_DWG_Drawing(DrawingNo, DrawingNm, HullNo, BlockId, Discipline, DwgStatus, CurrentRevNo,"
            " DesignerEmpNo, CreateUserId, CreateDt) VALUES (?, ?, ?, ?, ?, 'DRAFT', 0, ?, ?, ?)",
            (v["drawing_no"], v["drawing_nm"], v["hull_no"], v.get("block_id"), v.get("discipline"),
             v.get("designer_emp_no"), user["emp_no"], config.TODAY),
        ).lastrowid
        conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt)"
                     " VALUES (?, 0, 'DRAFT', '최초 작성', ?, ?)", (did, user["emp_no"], config.TODAY))
    return get_drawing(conn, did)


def update_drawing(conn: sqlite3.Connection, drawing_id: int, data: dict, fields: set[str], user: dict) -> dict:
    cur = _row(conn, drawing_id)
    if "hull_no" in fields and blank_to_none(data.get("hull_no")) not in (None, cur["HullNo"]):
        raise validation("hull_no", "호선은 변경할 수 없습니다.")
    if "drawing_no" in fields and blank_to_none(data.get("drawing_no")) not in (None, cur["DrawingNo"]):
        raise validation("drawing_no", "도면번호는 변경할 수 없습니다.")
    changes = {k: blank_to_none(data[k]) for k in fields if k in EDITABLE}
    merged = {k: cur[c] for k, c in EDITABLE.items()} | changes
    _validate(conn, cur["HullNo"], merged)
    with db.tx(conn):
        sets = [f"{EDITABLE[k]} = ?" for k in changes] + ["ModifyUserId = ?", "ModifyDt = ?"]
        conn.execute(f"UPDATE TB_DWG_Drawing SET {', '.join(sets)} WHERE DrawingId = ?",
                     [*changes.values(), user["emp_no"], config.TODAY, drawing_id])
    return get_drawing(conn, drawing_id)


def delete_drawing(conn: sqlite3.Connection, drawing_id: int) -> None:
    cur = _row(conn, drawing_id)
    with db.tx(conn):
        files = storage.revision_file_ids(conn, "d.DrawingId = ?", (drawing_id,))
        conn.execute("DELETE FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,))  # 리비전·결재·연계 CASCADE
        rules.recalc_hull(conn, cur["HullNo"])
    storage.remove_files(files)


def _set_status(conn: sqlite3.Connection, drawing_id: int, rev_no: int, status: str) -> None:
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = ? WHERE DrawingId = ? AND RevNo = ?", (status, drawing_id, rev_no))
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = ? WHERE DrawingId = ?", (status, drawing_id))


# --- 리비전 (BR-06)
def create_revision(conn: sqlite3.Connection, drawing_id: int, change_desc: str | None, user: dict) -> dict:
    cur = _row(conn, drawing_id)
    desc = blank_to_none(change_desc)
    if not desc:
        raise validation("change_desc", "개정 사유를 입력하세요.")
    latest = _latest(conn, drawing_id)
    if latest is not None and latest["RevStatus"] not in ("ISSUED", "OBSOLETE"):
        raise rev_state(MSG_NEW_REV)
    n = (latest["RevNo"] + 1) if latest is not None else 0
    with db.tx(conn):
        conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt)"
                     " VALUES (?, ?, 'DRAFT', ?, ?, ?)", (drawing_id, n, desc, user["emp_no"], config.TODAY))
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = 'DRAFT' WHERE DrawingId = ?", (drawing_id,))
        rules.recalc_hull(conn, cur["HullNo"])
    return get_drawing(conn, drawing_id)


def request_approval(conn: sqlite3.Connection, drawing_id: int, rev_no: int, reviewer: str | None, approver: str | None) -> dict:
    cur = _row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    reviewer, approver = blank_to_none(reviewer), blank_to_none(approver)
    if not reviewer or not approver:
        raise validation("reviewer_emp_no", "검토자와 승인자를 선택하세요.")
    if reviewer == approver:
        raise validation("approver_emp_no", "검토자와 승인자는 서로 다른 사람이어야 합니다.")
    for f, e in (("reviewer_emp_no", reviewer), ("approver_emp_no", approver)):
        if not approved_user(conn, e):
            raise validation(f, "승인된 회원만 지정할 수 있습니다.")
    if rev["RevStatus"] != "DRAFT" or _latest(conn, drawing_id)["RevNo"] != rev_no:
        raise rev_state(MSG_REQ)
    with db.tx(conn):
        conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no))
        conn.executemany("INSERT INTO TB_DWG_Approval(DrawingId, RevNo, StepNo, ApproverEmpNo, Result) VALUES (?, ?, ?, ?, 'WAIT')",
                         [(drawing_id, rev_no, 1, reviewer), (drawing_id, rev_no, 2, approver)])
        _set_status(conn, drawing_id, rev_no, "REVIEW")
        rules.recalc_hull(conn, cur["HullNo"])
    return get_drawing(conn, drawing_id)


def issue(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> dict:
    cur = _row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    if rev["RevStatus"] != "APPROVED":
        raise rev_state(MSG_ISSUE)
    results = [r[0] for r in conn.execute("SELECT Result FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ?",
                                          (drawing_id, rev_no))]
    if not results or any(x != "APPROVE" for x in results):
        raise AppError(409, "APPROVAL_INCOMPLETE", "결재가 완료된 리비전만 배포할 수 있습니다.")
    with db.tx(conn):
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'OBSOLETE' WHERE DrawingId = ? AND RevStatus = 'ISSUED'",
                     (drawing_id,))
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'ISSUED', IssueDt = ? WHERE DrawingId = ? AND RevNo = ?",
                     (config.TODAY, drawing_id, rev_no))
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = 'ISSUED', CurrentRevNo = ? WHERE DrawingId = ?",
                     (rev_no, drawing_id))
        rules.recalc_hull(conn, cur["HullNo"])
    return get_drawing(conn, drawing_id)


# --- PDF
def clean_filename(name: str | None) -> str | None:
    if not name:
        return None
    base = re.split(r"[\\/]", name)[-1].strip().replace("\x00", "")
    return base[:200] or None


def check_upload_target(conn: sqlite3.Connection, drawing_id: int, rev_no: int, filename: str | None,
                        content_type: str | None, content_length: str | None) -> tuple[str, str]:
    """본문을 읽기 전 검사. (정리된 파일명, 새 FileId)를 돌려준다."""
    d = _row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    name = clean_filename(filename)
    mime = (content_type or "").split(";")[0].strip().lower()
    if not ((name and name.lower().endswith(".pdf")) or mime == "application/pdf"):
        raise AppError(400, "INVALID_FILE_TYPE", "PDF 파일만 업로드할 수 있습니다.")
    if rev["RevStatus"] != "DRAFT":
        raise rev_state(MSG_UPLOAD)
    if content_length and content_length.isdigit() and int(content_length) > MAX_PDF:
        raise too_large()
    return name or f"{d['DrawingNo']}_Rev{rev_no}.pdf", secrets.token_hex(16)


def too_large() -> AppError:
    return AppError(413, "FILE_TOO_LARGE", "파일 크기는 30MB 이하여야 합니다.")


def save_upload(conn: sqlite3.Connection, drawing_id: int, rev_no: int, name: str, file_id: str, tmp: Path) -> dict:
    """스트리밍으로 받은 임시 파일을 검사하고 저장한다. 새 파일은 커밋 전에 두고 실패하면 지운다."""
    try:
        with tmp.open("rb") as f:
            if f.read(5) != b"%PDF-":
                raise AppError(400, "INVALID_FILE_TYPE", "PDF 파일만 업로드할 수 있습니다.")
        dest = storage.file_path(f"{file_id}.pdf")
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:
        with db.tx(conn):
            rev = _rev(conn, drawing_id, rev_no)
            if rev["RevStatus"] != "DRAFT":
                raise rev_state(MSG_UPLOAD)
            old = rev["FileId"]
            conn.execute("UPDATE TB_DWG_Revision SET FileId = ?, FileNm = ? WHERE DrawingId = ? AND RevNo = ?",
                         (f"{file_id}.pdf", name, drawing_id, rev_no))
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    storage.remove_files([old])
    return get_drawing(conn, drawing_id)


def pdf_file(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> tuple[Path, str]:
    _row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    if not rev["FileId"]:
        raise not_found("NO_FILE", "첨부된 PDF가 없습니다.")
    p = storage.file_path(rev["FileId"])
    if not p.is_file():
        raise not_found("FILE_NOT_FOUND", "파일을 찾을 수 없습니다.")
    return p, rev["FileNm"] or p.name


def delete_pdf(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> None:
    _row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    if rev["RevStatus"] != "DRAFT":
        raise rev_state(MSG_FILE_DEL)
    if not rev["FileId"]:
        raise not_found("NO_FILE", "첨부된 PDF가 없습니다.")
    with db.tx(conn):
        conn.execute("UPDATE TB_DWG_Revision SET FileId = NULL, FileNm = NULL WHERE DrawingId = ? AND RevNo = ?",
                     (drawing_id, rev_no))
    storage.remove_files([rev["FileId"]])


# --- 공정 연계 (공정 쪽 서비스와 같은 구현을 쓴다)
def link_plan(conn: sqlite3.Connection, drawing_id: int, plan_id: int | None, required: bool) -> dict:
    _row(conn, drawing_id)
    if plan_id is None:
        raise validation("plan_id", "공정을 선택하세요.")
    plan_svc.link_drawing(conn, plan_id, drawing_id, required)
    return linked_plans(conn, drawing_id)


def unlink_plan(conn: sqlite3.Connection, drawing_id: int, plan_id: int) -> None:
    _row(conn, drawing_id)
    plan_svc.unlink_drawing(conn, plan_id, drawing_id)
