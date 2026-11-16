"""F06 공정 실적. 저장·삭제 후 BR-05(실적 반영) → BR-03(상태 재계산)."""
import sqlite3

from .. import config, db
from ..errors import not_found, validation
from ..util import blank_to_none, is_date
from . import plans as plans_svc
from . import rules
from .hulls import ensure_hull
from .shell import approved_user

TARGET_STATUSES = ("READY", "WORK", "DELAY")
TARGET_FIELDS = ("plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt", "actual_end_dt",
                 "progress_rate", "plan_status", "manager_emp_no", "manager_nm", "drawing_wait")


def progress_hulls(conn: sqlite3.Connection) -> dict:
    hulls = [{"hull_no": r[0], "hull_nm": r[1], "hull_status": r[2]} for r in conn.execute(
        "SELECT HullNo, HullNm, HullStatus FROM TB_MST_Hull h"
        " WHERE EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.HullNo = h.HullNo) ORDER BY HullNo")]
    default = next((h["hull_no"] for h in hulls if h["hull_status"] == "BUILD"), hulls[0]["hull_no"] if hulls else None)
    return {"hulls": hulls, "default_hull_no": default}


def targets(conn: sqlite3.Connection, hull_no: str, include_done: bool) -> dict:
    ensure_hull(conn, hull_no)
    rows = plans_svc.load_plans(conn, hull_no)
    if not include_done:
        rows = [p for p in rows if p["plan_status"] in TARGET_STATUSES]
    return {"hull_no": hull_no, "today": config.TODAY, "plans": [{k: p[k] for k in TARGET_FIELDS} for p in rows]}


def plan_progress(conn: sqlite3.Connection, plan_id: int) -> dict:
    plan = plans_svc.get_plan(conn, plan_id)
    history = [{
        "progress_id": r[0], "plan_id": r[1], "work_dt": r[2], "progress_rate": r[3], "man_hour": r[4],
        "worker_cnt": r[5], "worker_emp_no": r[6], "worker_nm": r[7], "remark": r[8], "create_dt": r[9],
    } for r in conn.execute(
        "SELECT g.ProgressId, g.PlanId, g.WorkDt, g.ProgressRate, g.ManHour, g.WorkerCnt, g.WorkerEmpNo,"
        " u.display_name, g.Remark, g.CreateDt FROM TB_PRC_Progress g LEFT JOIN users u ON u.emp_no = g.WorkerEmpNo"
        " WHERE g.PlanId = ? ORDER BY g.WorkDt DESC", (plan_id,))]
    return {"plan": plan, "history": history}


def save_progress(conn: sqlite3.Connection, plan_id: int, work_dt: str, data: dict) -> dict:
    plan = plans_svc.get_plan(conn, plan_id)
    if not is_date(work_dt):
        raise validation("work_dt", "작업일을 입력하세요.")
    if work_dt > config.TODAY:
        raise validation("work_dt", "미래 일자의 실적은 입력할 수 없습니다.")
    rate = data.get("progress_rate")
    if rate is None or not (0 <= rate <= 100):
        raise validation("progress_rate", "진척률은 0~100 사이로 입력하세요.")
    worker = blank_to_none(data.get("worker_emp_no"))
    if worker and not approved_user(conn, worker):
        raise validation("worker_emp_no", "승인된 회원만 작업자로 지정할 수 있습니다.")
    with db.tx(conn):
        conn.execute(
            "INSERT INTO TB_PRC_Progress(PlanId, WorkDt, ProgressRate, ManHour, WorkerCnt, WorkerEmpNo, Remark, CreateDt)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(PlanId, WorkDt) DO UPDATE SET"
            " ProgressRate = excluded.ProgressRate, ManHour = excluded.ManHour, WorkerCnt = excluded.WorkerCnt,"
            " WorkerEmpNo = excluded.WorkerEmpNo, Remark = excluded.Remark",
            (plan_id, work_dt, rate, data.get("man_hour"), data.get("worker_cnt"), worker,
             blank_to_none(data.get("remark")), config.TODAY),
        )
        rules.apply_progress(conn, plan_id)
        rules.recalc_hull(conn, plan["hull_no"])
    return plan_progress(conn, plan_id)


def delete_progress(conn: sqlite3.Connection, progress_id: int) -> dict:
    r = conn.execute("SELECT g.PlanId, p.HullNo FROM TB_PRC_Progress g JOIN TB_PRC_Plan p ON p.PlanId = g.PlanId"
                     " WHERE g.ProgressId = ?", (progress_id,)).fetchone()
    if not r:
        raise not_found("PROGRESS_NOT_FOUND", "실적을 찾을 수 없습니다.")
    with db.tx(conn):
        conn.execute("DELETE FROM TB_PRC_Progress WHERE ProgressId = ?", (progress_id,))
        rules.apply_progress(conn, r[0])
        rules.recalc_hull(conn, r[1])
    return plan_progress(conn, r[0])
