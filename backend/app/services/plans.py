"""F05 공정 계획·선후행(BR-04)·도면 연계·간트 일정 연쇄. API↔DB 매핑은 이 파일 한 곳."""
import sqlite3

from .. import config, db
from ..errors import AppError, duplicate, not_found, validation
from ..util import add_days, blank_to_none, days_between, is_date
from . import rules
from .hulls import ensure_hull
from .shell import approved_user

PLAN_SQL = (
    "SELECT p.*, b.BlockCd, b.BlockNm, pr.ProcNm, pr.Seq AS ProcSeq, u.display_name AS ManagerNm"
    " FROM TB_PRC_Plan p LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId"
    " JOIN TB_PRC_Proc pr ON pr.ProcCd = p.ProcCd LEFT JOIN users u ON u.emp_no = p.ManagerEmpNo"
)
EDITABLE = {"block_id": "BlockId", "proc_cd": "ProcCd", "plan_start_dt": "PlanStartDt", "plan_end_dt": "PlanEndDt",
            "manager_emp_no": "ManagerEmpNo", "remark": "Remark"}
MSG_DATES = "계획 시작/종료일을 입력하세요."
MSG_LATE = "선행 공정 종료일이 이 공정의 시작일보다 늦습니다. 그대로 저장할까요?"


def plan_not_found() -> AppError:
    return not_found("PLAN_NOT_FOUND", "공정을 찾을 수 없습니다.")


plan_label = rules.plan_label


def _to_api(r, preds: dict, blockers: dict) -> dict:
    b = blockers.get(r["PlanId"], [])
    return {
        "plan_id": r["PlanId"], "hull_no": r["HullNo"], "block_id": r["BlockId"], "block_cd": r["BlockCd"],
        "block_nm": r["BlockNm"], "proc_cd": r["ProcCd"], "proc_nm": r["ProcNm"],
        "label": plan_label(r["BlockCd"], r["HullNo"], r["ProcNm"]),
        "plan_start_dt": r["PlanStartDt"], "plan_end_dt": r["PlanEndDt"],
        "actual_start_dt": r["ActualStartDt"], "actual_end_dt": r["ActualEndDt"],
        "progress_rate": r["ProgressRate"], "plan_status": r["PlanStatus"],
        "manager_emp_no": r["ManagerEmpNo"], "manager_nm": r["ManagerNm"], "remark": r["Remark"],
        "create_user_id": r["CreateUserId"], "create_dt": r["CreateDt"],
        "pred_plan_ids": preds.get(r["PlanId"], []), "gate_ok": not b, "blockers": b,
        "drawing_wait": r["PlanStatus"] == "PLAN" and bool(b),
    }


def load_plans(conn: sqlite3.Connection, hull_no: str, block_id: int | None = None) -> list[dict]:
    sql, params = PLAN_SQL + " WHERE p.HullNo = ?", [hull_no]
    if block_id is not None:
        sql += " AND p.BlockId = ?"
        params.append(block_id)
    rows = sorted(conn.execute(sql, params).fetchall(),
                  key=lambda r: rules.plan_sort_key(r["BlockCd"], r["ProcSeq"], r["PlanId"]))
    preds, blockers = rules.pred_map(conn, hull_no), rules.blockers_map(conn, hull_no=hull_no)
    return [_to_api(r, preds, blockers) for r in rows]


def _row(conn: sqlite3.Connection, plan_id: int):
    r = conn.execute(PLAN_SQL + " WHERE p.PlanId = ?", (plan_id,)).fetchone()
    if not r:
        raise plan_not_found()
    return r


def get_plan(conn: sqlite3.Connection, plan_id: int) -> dict:
    r = _row(conn, plan_id)
    return _to_api(r, rules.pred_map(conn, r["HullNo"]), rules.blockers_map(conn, plan_id=plan_id))


def hull_plans(conn: sqlite3.Connection, hull_no: str, block_id: int | None) -> dict:
    ensure_hull(conn, hull_no)
    plans = load_plans(conn, hull_no, block_id)
    ids = {p["plan_id"] for p in plans}
    deps = [{"plan_id": p["plan_id"], "pred_plan_id": pr} for p in plans for pr in p["pred_plan_ids"] if pr in ids]
    prog = rules.progress_by(conn, "HullNo", "WHERE HullNo = ?", (hull_no,)).get(hull_no)
    return {"hull_no": hull_no, "hull_progress": prog, "today": config.TODAY, "plans": plans, "deps": deps}


def procs(conn: sqlite3.Connection) -> list[dict]:
    return [{"proc_cd": r[0], "proc_nm": r[1], "proc_group": r[2], "std_days": r[3], "seq": r[4]}
            for r in conn.execute("SELECT ProcCd, ProcNm, ProcGroup, StdDays, Seq FROM TB_PRC_Proc WHERE UseYN = 1 ORDER BY Seq")]


def plan_hulls(conn: sqlite3.Connection) -> list[dict]:
    return [{"hull_no": r[0], "hull_nm": r[1], "plan_count": r[2]} for r in conn.execute(
        "SELECT h.HullNo, h.HullNm, (SELECT COUNT(*) FROM TB_PRC_Plan p WHERE p.HullNo = h.HullNo)"
        " FROM TB_MST_Hull h ORDER BY h.HullNo")]


# --- 검증
def _validate_dates(start, end) -> None:
    if not is_date(start):
        raise validation("plan_start_dt", MSG_DATES)
    if not is_date(end):
        raise validation("plan_end_dt", MSG_DATES)
    if end < start:
        raise validation("plan_end_dt", "계획 종료일이 시작일보다 빠릅니다.")


def _validate_fields(conn: sqlite3.Connection, hull_no: str, v: dict) -> None:
    _validate_dates(v.get("plan_start_dt"), v.get("plan_end_dt"))
    if v.get("block_id") is not None and not conn.execute(
            "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (v["block_id"], hull_no)).fetchone():
        raise validation("block_id", "해당 호선의 블록이 아닙니다.")
    if not v.get("proc_cd") or not conn.execute(
            "SELECT 1 FROM TB_PRC_Proc WHERE ProcCd = ? AND UseYN = 1", (v["proc_cd"],)).fetchone():
        raise validation("proc_cd", "허용되지 않는 공정 코드입니다.")
    if v.get("manager_emp_no") and not approved_user(conn, v["manager_emp_no"]):
        raise validation("manager_emp_no", "승인된 회원만 담당자로 지정할 수 있습니다.")


def check_preds(conn: sqlite3.Connection, hull_no: str, plan_id: int | None, pred_ids: list[int],
                start: str, confirm: bool) -> list[int]:
    """BR-04: 자기 참조 → 다른 호선 → 순환 → 늦은 선행(409, confirm으로 통과)."""
    ids = list(dict.fromkeys(pred_ids or []))
    if plan_id is not None and plan_id in ids:
        raise AppError(400, "PLAN_DEPENDENCY_SELF", "자기 자신을 선행 공정으로 지정할 수 없습니다.", {"field": "pred_plan_ids"})
    rows = {}
    if ids:
        rows = {r[0]: r for r in conn.execute(
            f"SELECT PlanId, HullNo, PlanEndDt FROM TB_PRC_Plan WHERE PlanId IN ({','.join('?' * len(ids))})", ids)}
    if any(i not in rows or rows[i][1] != hull_no for i in ids):
        raise validation("pred_plan_ids", "선행 공정은 같은 호선의 공정이어야 합니다.")
    if plan_id is not None and ids:
        graph = rules.pred_map(conn, hull_no)
        graph[plan_id] = ids
        stack, seen = list(ids), set()
        while stack:
            x = stack.pop()
            if x == plan_id:
                raise AppError(400, "PLAN_DEPENDENCY_CYCLE", "선행 공정이 순환 구조를 만듭니다.", {"field": "pred_plan_ids"})
            if x not in seen:
                seen.add(x)
                stack.extend(graph.get(x, []))
    late = sorted(i for i in ids if rows[i][2] > start)
    if late and not confirm:
        raise AppError(409, "PRED_LATE_CONFIRM_REQUIRED", MSG_LATE, {"late_pred_plan_ids": late})
    return ids


def _set_preds(conn: sqlite3.Connection, plan_id: int, ids: list[int]) -> None:
    conn.execute("DELETE FROM TB_PRC_PlanDep WHERE PlanId = ?", (plan_id,))
    conn.executemany("INSERT INTO TB_PRC_PlanDep(PlanId, PredPlanId, LagDays) VALUES (?, ?, 0)", [(plan_id, i) for i in ids])


# --- 쓰기
def create_plan(conn: sqlite3.Connection, hull_no: str, data: dict, user: dict) -> dict:
    ensure_hull(conn, hull_no)
    v = {k: blank_to_none(x) for k, x in data.items()}
    _validate_fields(conn, hull_no, v)
    ids = check_preds(conn, hull_no, None, v.get("pred_plan_ids") or [], v["plan_start_dt"], bool(v.get("confirm_late_preds")))
    with db.tx(conn):
        pid = conn.execute(
            "INSERT INTO TB_PRC_Plan(HullNo, BlockId, ProcCd, PlanStartDt, PlanEndDt, ProgressRate, PlanStatus,"
            " ManagerEmpNo, Remark, CreateUserId, CreateDt) VALUES (?, ?, ?, ?, ?, 0, 'PLAN', ?, ?, ?, ?)",
            (hull_no, v.get("block_id"), v["proc_cd"], v["plan_start_dt"], v["plan_end_dt"], v.get("manager_emp_no"),
             v.get("remark"), user["emp_no"], config.TODAY),
        ).lastrowid
        _set_preds(conn, pid, ids)
        rules.recalc_hull(conn, hull_no)
    return get_plan(conn, pid)


def update_plan(conn: sqlite3.Connection, plan_id: int, data: dict, fields: set[str]) -> dict:
    """보낸 필드만 수정. 진척·실제일 보존. 일정 자동 조정 없음."""
    cur = _row(conn, plan_id)
    hull_no = cur["HullNo"]
    changes = {k: blank_to_none(data[k]) for k in fields if k in EDITABLE}
    merged = {k: cur[c] for k, c in EDITABLE.items()} | changes
    _validate_fields(conn, hull_no, merged)
    preds_given = "pred_plan_ids" in fields and data.get("pred_plan_ids") is not None
    preds = data["pred_plan_ids"] if preds_given else rules.pred_map(conn, hull_no).get(plan_id, [])
    if preds_given or merged["plan_start_dt"] != cur["PlanStartDt"]:
        preds = check_preds(conn, hull_no, plan_id, preds, merged["plan_start_dt"], bool(data.get("confirm_late_preds")))
    with db.tx(conn):
        if changes:
            conn.execute(f"UPDATE TB_PRC_Plan SET {', '.join(f'{EDITABLE[k]} = ?' for k in changes)} WHERE PlanId = ?",
                         list(changes.values()) + [plan_id])
        if preds_given:
            _set_preds(conn, plan_id, preds)
        rules.recalc_hull(conn, hull_no)
    return get_plan(conn, plan_id)


def set_predecessors(conn: sqlite3.Connection, plan_id: int, pred_ids: list[int], confirm: bool) -> dict:
    cur = _row(conn, plan_id)
    ids = check_preds(conn, cur["HullNo"], plan_id, pred_ids, cur["PlanStartDt"], confirm)
    with db.tx(conn):
        _set_preds(conn, plan_id, ids)
        rules.recalc_hull(conn, cur["HullNo"])
    return get_plan(conn, plan_id)


def delete_plan(conn: sqlite3.Connection, plan_id: int) -> None:
    cur = _row(conn, plan_id)
    with db.tx(conn):
        conn.execute("DELETE FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,))  # 실적·선후행·연계 CASCADE
        rules.recalc_hull(conn, cur["HullNo"])


def schedule(conn: sqlite3.Connection, plan_id: int, start: str | None, end: str | None, confirm: bool) -> dict:
    """간트 드래그 저장. BR-04 후행 연쇄: 후행 시작 < max(선행 종료)+1이면 그 날로 옮기고 기간 유지. 당기는 조정 없음."""
    cur = _row(conn, plan_id)
    hull_no = cur["HullNo"]
    _validate_dates(start, end)
    preds = rules.pred_map(conn, hull_no)
    if start != cur["PlanStartDt"]:
        check_preds(conn, hull_no, plan_id, preds.get(plan_id, []), start, confirm)
    dates = {r[0]: [r[1], r[2]] for r in conn.execute(
        "SELECT PlanId, PlanStartDt, PlanEndDt FROM TB_PRC_Plan WHERE HullNo = ?", (hull_no,))}
    dates[plan_id] = [start, end]
    succs: dict[int, list[int]] = {}
    for s, ps in preds.items():
        for p in ps:
            succs.setdefault(p, []).append(s)
    shifted: set[int] = set()
    queue = [plan_id]
    while queue:
        x = queue.pop(0)
        for s in succs.get(x, []):
            need = add_days(max(dates[p][1] for p in preds[s]), 1)
            if dates[s][0] < need:
                dur = days_between(dates[s][0], dates[s][1])
                dates[s] = [need, add_days(need, dur)]
                shifted.add(s)
                queue.append(s)
    with db.tx(conn):
        for pid in [plan_id, *sorted(shifted)]:
            conn.execute("UPDATE TB_PRC_Plan SET PlanStartDt = ?, PlanEndDt = ? WHERE PlanId = ?", (*dates[pid], pid))
        rules.recalc_hull(conn, hull_no)
    return {"plan": get_plan(conn, plan_id), "shifted_plan_ids": sorted(shifted)}


# --- 도면 연계
def plan_drawings(conn: sqlite3.Connection, plan_id: int) -> dict:
    cur = _row(conn, plan_id)
    links = [{
        "drawing_id": r[0], "drawing_no": r[1], "drawing_nm": r[2], "dwg_status": r[3], "has_issued": bool(r[4]),
        "required": bool(r[5]), "need_dt": r[6],
    } for r in conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.DrawingNm, d.DwgStatus,"
        " EXISTS (SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId AND r.RevStatus = 'ISSUED'),"
        " l.RequiredYN, l.NeedDt FROM TB_DWG_PlanLink l JOIN TB_DWG_Drawing d ON d.DrawingId = l.DrawingId"
        " WHERE l.PlanId = ? ORDER BY d.DrawingNo", (plan_id,))]
    available = [{"drawing_id": r[0], "drawing_no": r[1], "drawing_nm": r[2], "dwg_status": r[3]} for r in conn.execute(
        "SELECT DrawingId, DrawingNo, DrawingNm, DwgStatus FROM TB_DWG_Drawing WHERE HullNo = ?"
        " AND DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_PlanLink WHERE PlanId = ?) ORDER BY DrawingNo",
        (cur["HullNo"], plan_id))]
    return {"plan_id": plan_id, "blockers": rules.blockers_map(conn, plan_id=plan_id).get(plan_id, []),
            "links": links, "available": available}


def link_drawing(conn: sqlite3.Connection, plan_id: int, drawing_id: int | None, required: bool) -> dict:
    cur = _row(conn, plan_id)
    d = conn.execute("SELECT HullNo FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,)).fetchone() if drawing_id else None
    if not d:
        raise not_found("DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")
    if d[0] != cur["HullNo"]:
        raise validation("drawing_id", "같은 호선의 도면만 연계할 수 있습니다.")
    if conn.execute("SELECT 1 FROM TB_DWG_PlanLink WHERE PlanId = ? AND DrawingId = ?", (plan_id, drawing_id)).fetchone():
        raise duplicate("이미 연계된 도면입니다.", "drawing_id")
    with db.tx(conn):
        conn.execute("INSERT INTO TB_DWG_PlanLink(DrawingId, PlanId, RequiredYN, NeedDt) VALUES (?, ?, ?, ?)",
                     (drawing_id, plan_id, 1 if required else 0, cur["PlanStartDt"]))
        rules.recalc_hull(conn, cur["HullNo"])
    return plan_drawings(conn, plan_id)


def unlink_drawing(conn: sqlite3.Connection, plan_id: int, drawing_id: int) -> None:
    cur = _row(conn, plan_id)
    with db.tx(conn):
        n = conn.execute("DELETE FROM TB_DWG_PlanLink WHERE PlanId = ? AND DrawingId = ?", (plan_id, drawing_id)).rowcount
        if not n:
            raise not_found("LINK_NOT_FOUND", "연계 정보를 찾을 수 없습니다.")
        rules.recalc_hull(conn, cur["HullNo"])
