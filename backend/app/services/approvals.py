"""F08 결재함: 대기·배포 대기·처리·이력(BR-06, BR-03)."""
import datetime as dt
import sqlite3

from .. import config, db
from ..errors import AppError, not_found, validation
from ..permissions import menu_level
from ..util import blank_to_none
from . import rules

KST = dt.timezone(dt.timedelta(hours=9))


def waiting(conn: sqlite3.Connection, emp_no: str) -> list[dict]:
    """본인 지정, WAIT, Rev가 REVIEW이자 최신, 앞 단계가 모두 APPROVE."""
    return [{
        "approval_id": r[0], "drawing_id": r[1], "drawing_no": r[2], "drawing_nm": r[3], "rev_no": r[4], "step_no": r[5],
        "change_desc": r[6],
    } for r in conn.execute(
        "SELECT a.ApprovalId, d.DrawingId, d.DrawingNo, d.DrawingNm, a.RevNo, a.StepNo, r.ChangeDesc"
        " FROM TB_DWG_Approval a JOIN TB_DWG_Revision r ON r.DrawingId = a.DrawingId AND r.RevNo = a.RevNo"
        " JOIN TB_DWG_Drawing d ON d.DrawingId = a.DrawingId"
        " WHERE a.ApproverEmpNo = ? AND a.Result = 'WAIT' AND r.RevStatus = 'REVIEW'"
        " AND r.RevNo = (SELECT MAX(RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = a.DrawingId)"
        " AND NOT EXISTS (SELECT 1 FROM TB_DWG_Approval p WHERE p.DrawingId = a.DrawingId AND p.RevNo = a.RevNo"
        "  AND p.StepNo < a.StepNo AND p.Result <> 'APPROVE')"
        " ORDER BY a.ApprovalId", (emp_no,))]


def ready(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.DrawingNm, r.RevNo FROM TB_DWG_Drawing d"
        " JOIN TB_DWG_Revision r ON r.DrawingId = d.DrawingId"
        " AND r.RevNo = (SELECT MAX(RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = d.DrawingId)"
        " WHERE r.RevStatus = 'APPROVED' ORDER BY d.DrawingNo").fetchall()
    out = []
    for r in rows:
        plans = conn.execute(
            "SELECT p.PlanId, p.HullNo, b.BlockCd, pr.ProcNm, pr.Seq FROM TB_DWG_PlanLink l JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId"
            " LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId JOIN TB_PRC_Proc pr ON pr.ProcCd = p.ProcCd"
            " WHERE l.DrawingId = ? AND p.PlanStatus = 'PLAN'", (r[0],)).fetchall()
        plans.sort(key=lambda p: rules.plan_sort_key(p["BlockCd"], p["Seq"], p["PlanId"]))
        out.append({"drawing_id": r[0], "drawing_no": r[1], "drawing_nm": r[2], "rev_no": r[3],
                    "effect_plans": [rules.plan_label(p["BlockCd"], p["HullNo"], p["ProcNm"]) for p in plans]})
    return out


def inbox(conn: sqlite3.Connection, user: dict) -> dict:
    return {"waiting": waiting(conn, user["emp_no"]), "ready": ready(conn),
            "can_issue": menu_level(conn, user["emp_no"], "M31") >= 2}


def decide(conn: sqlite3.Connection, approval_id: int, result: str | None, comment: str | None, user: dict) -> dict:
    if result not in ("APPROVE", "REJECT"):
        raise validation("result", "결재 결과는 APPROVE 또는 REJECT 이어야 합니다.")
    comment = blank_to_none(comment)
    if result == "REJECT" and not comment:
        raise validation("comment", "반려 시 의견을 입력하세요.")
    a = conn.execute("SELECT * FROM TB_DWG_Approval WHERE ApprovalId = ?", (approval_id,)).fetchone()
    if not a:
        raise not_found("APPROVAL_NOT_FOUND", "결재 건을 찾을 수 없습니다.")
    if a["ApproverEmpNo"] != user["emp_no"]:
        raise AppError(403, "NOT_ASSIGNED_APPROVER", "본인에게 지정된 결재 건이 아닙니다.")
    if a["Result"] != "WAIT":
        raise AppError(409, "ALREADY_DECIDED", "이미 처리된 결재 건입니다.")
    if approval_id not in {w["approval_id"] for w in waiting(conn, user["emp_no"])}:
        raise AppError(409, "NOT_CURRENT_STEP", "결재 순서가 아니거나 최신 검토중 리비전이 아닙니다.")
    did, rev = a["DrawingId"], a["RevNo"]
    act = f"{config.TODAY} {dt.datetime.now(KST).strftime('%H:%M')}"
    with db.tx(conn):
        conn.execute("UPDATE TB_DWG_Approval SET Result = ?, Comment = ?, ActDt = ? WHERE ApprovalId = ?",
                     (result, comment or "승인" if result == "APPROVE" else comment, act, approval_id))
        if result == "REJECT":
            conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ? AND Result = 'WAIT'", (did, rev))
            status = "DRAFT"
        else:
            left = conn.execute("SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ? AND Result <> 'APPROVE'",
                                (did, rev)).fetchone()[0]
            status = "APPROVED" if left == 0 else None
        if status:
            conn.execute("UPDATE TB_DWG_Revision SET RevStatus = ? WHERE DrawingId = ? AND RevNo = ?", (status, did, rev))
            conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = ? WHERE DrawingId = ?", (status, did))
        hull = conn.execute("SELECT HullNo FROM TB_DWG_Drawing WHERE DrawingId = ?", (did,)).fetchone()[0]
        rules.recalc_hull(conn, hull)
    return {"approval_id": approval_id, "result": result, "waiting": waiting(conn, user["emp_no"]), "ready": ready(conn)}


def history(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    return [{
        "approval_id": r[0], "act_dt": r[1], "drawing_id": r[2], "drawing_no": r[3], "rev_no": r[4], "step_no": r[5],
        "approver_emp_no": r[6], "approver_nm": r[7], "result": r[8], "comment": r[9],
    } for r in conn.execute(
        "SELECT a.ApprovalId, a.ActDt, a.DrawingId, d.DrawingNo, a.RevNo, a.StepNo, a.ApproverEmpNo, u.display_name,"
        " a.Result, a.Comment FROM TB_DWG_Approval a JOIN TB_DWG_Drawing d ON d.DrawingId = a.DrawingId"
        " LEFT JOIN users u ON u.emp_no = a.ApproverEmpNo WHERE a.Result <> 'WAIT'"
        " ORDER BY a.ActDt DESC, a.ApprovalId DESC LIMIT ?", (limit,))]
