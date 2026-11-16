"""교차 업무 규칙(rules.md) — 각 규칙의 유일한 구현.
BR-01 가중 진척률, BR-02 도면 게이트, BR-03 공정 상태·호선 전이, BR-05 실적 반영, BR-07 개정 영향, 공정 정렬."""
import sqlite3
from typing import Iterable

from .. import config
from ..util import add_days, days_between

PLAN_STATUSES = ("PLAN", "READY", "WORK", "DONE", "DELAY")


# --- BR-01
def weighted_progress(items: Iterable[tuple[float, str, str]]) -> int | None:
    """items: (진척률, 시작, 종료). 공정이 없으면 None(대시보드는 호출 쪽에서 0으로)."""
    num = den = 0
    for rate, start, end in items:
        d = days_between(start, end) + 1
        num += (rate or 0) * d
        den += d
    if den == 0:
        return None
    return int(num / den + 0.5)


def progress_by(conn: sqlite3.Connection, key: str, where: str = "", params: tuple = ()) -> dict:
    """key 컬럼(HullNo/BlockId)별 BR-01 진척률."""
    groups: dict = {}
    for r in conn.execute(f"SELECT {key}, ProgressRate, PlanStartDt, PlanEndDt FROM TB_PRC_Plan {where}", params):
        groups.setdefault(r[0], []).append((r[1], r[2], r[3]))
    return {k: weighted_progress(v) for k, v in groups.items()}


# --- BR-02
_BLOCKER_SQL = (
    "SELECT l.PlanId, d.DrawingId, d.DrawingNo, d.DwgStatus FROM TB_DWG_PlanLink l"
    " JOIN TB_DWG_Drawing d ON d.DrawingId = l.DrawingId JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId"
    " WHERE l.RequiredYN = 1 AND d.DwgStatus <> 'OBSOLETE'"
    " AND NOT EXISTS (SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId AND r.RevStatus = 'ISSUED')"
)


def blockers_map(conn: sqlite3.Connection, *, hull_no: str | None = None, plan_id: int | None = None) -> dict[int, list]:
    sql, params = _BLOCKER_SQL, []
    if hull_no is not None:
        sql += " AND p.HullNo = ?"
        params.append(hull_no)
    if plan_id is not None:
        sql += " AND p.PlanId = ?"
        params.append(plan_id)
    out: dict[int, list] = {}
    for r in conn.execute(sql + " ORDER BY d.DrawingNo", params):
        out.setdefault(r[0], []).append({"drawing_id": r[1], "drawing_no": r[2], "dwg_status": r[3]})
    return out


def pred_map(conn: sqlite3.Connection, hull_no: str) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for pid, pred in conn.execute(
        "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId = d.PlanId"
        " WHERE p.HullNo = ? ORDER BY d.PlanId, d.PredPlanId",
        (hull_no,),
    ):
        out.setdefault(pid, []).append(pred)
    return out


# --- BR-03
def plan_status(rate: float, actual_start: str | None, end: str, preds_done: bool, blocked: bool, today: str) -> str:
    if rate >= 100:
        return "DONE"
    if rate > 0 or actual_start:
        return "DELAY" if end < today else "WORK"
    if end < today:
        return "DELAY"
    return "READY" if preds_done and not blocked else "PLAN"


def recalc_hull(conn: sqlite3.Connection, hull_no: str) -> None:
    """호선의 모든 공정 상태와 호선 자동 전이를 재계산한다(호출 쪽 트랜잭션 안에서)."""
    today = config.TODAY
    rows = conn.execute(
        "SELECT PlanId, ProcCd, PlanEndDt, ProgressRate, ActualStartDt, PlanStatus FROM TB_PRC_Plan WHERE HullNo = ?",
        (hull_no,),
    ).fetchall()
    rate = {r["PlanId"]: r["ProgressRate"] for r in rows}
    preds = pred_map(conn, hull_no)
    blocked = blockers_map(conn, hull_no=hull_no)
    new = {}
    for r in rows:
        pid = r["PlanId"]
        done = all(rate.get(p, 0) >= 100 for p in preds.get(pid, []))
        st = plan_status(r["ProgressRate"], r["ActualStartDt"], r["PlanEndDt"], done, pid in blocked, today)
        new[pid] = st
        if st != r["PlanStatus"]:
            conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = ? WHERE PlanId = ?", (st, pid))
    h = conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone()
    if not h:
        return
    status = h[0]
    if status == "DESIGN" and any(s == "WORK" for s in new.values()):
        status = "BUILD"
    if status == "BUILD" and any(r["ProcCd"] == "LAUNCH" and new[r["PlanId"]] == "DONE" for r in rows):
        status = "LAUNCH"
    if status != h[0]:
        conn.execute("UPDATE TB_MST_Hull SET HullStatus = ? WHERE HullNo = ?", (status, hull_no))


def recalc_plan_hull(conn: sqlite3.Connection, plan_id: int) -> None:
    r = conn.execute("SELECT HullNo FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,)).fetchone()
    if r:
        recalc_hull(conn, r[0])


# --- BR-05
def apply_progress(conn: sqlite3.Connection, plan_id: int) -> None:
    rows = conn.execute(
        "SELECT WorkDt, ProgressRate FROM TB_PRC_Progress WHERE PlanId = ? ORDER BY WorkDt", (plan_id,)
    ).fetchall()
    if not rows:
        rate, start, end = 0, None, None
    else:
        rate, start = rows[-1]["ProgressRate"], rows[0]["WorkDt"]
        end = rows[-1]["WorkDt"] if rate >= 100 else None
    conn.execute("UPDATE TB_PRC_Plan SET ProgressRate = ?, ActualStartDt = ?, ActualEndDt = ? WHERE PlanId = ?",
                 (rate, start, end, plan_id))


def plan_label(block_cd: str | None, hull_no: str, proc_nm: str) -> str:
    return f"[{block_cd}] {proc_nm}" if block_cd else f"[{hull_no}] {proc_nm}"


# --- 정렬: 블록코드 숫자순(비숫자 뒤), 블록 없는 공정 맨 뒤, 표준공정 Seq, PlanId
def code_sort_key(code: str | None) -> tuple:
    if code is None:
        return (2, 0, "")
    return (0, int(code), code) if code.isdigit() else (1, 0, code)


def plan_sort_key(block_cd: str | None, proc_seq: int, plan_id: int) -> tuple:
    return (code_sort_key(block_cd), proc_seq or 0, plan_id)


# --- BR-07
IMPACT_STATUSES = ("WORK", "DONE", "DELAY")


def revision_impacts(conn: sqlite3.Connection, *, drawing_id: int | None = None, hull_nos: list[str] | None = None) -> list[dict]:
    """도면별 Rev>=1, ISSUED, IssueDt가 [오늘-30일, 오늘]인 최대 Rev의 연계 공정 중 WORK/DONE/DELAY. 배포일 내림차순."""
    today = config.TODAY
    sql = (
        "SELECT d.DrawingId, d.DrawingNo, d.HullNo, r.RevNo, r.IssueDt, r.ChangeDesc, p.PlanId, p.PlanStatus,"
        " p.HullNo AS PHull, b.BlockCd, pr.ProcNm, pr.Seq FROM TB_DWG_Drawing d"
        " JOIN TB_DWG_Revision r ON r.DrawingId = d.DrawingId AND r.RevNo = ("
        "  SELECT MAX(r2.RevNo) FROM TB_DWG_Revision r2 WHERE r2.DrawingId = d.DrawingId AND r2.RevNo >= 1"
        "  AND r2.RevStatus = 'ISSUED' AND r2.IssueDt BETWEEN ? AND ?)"
        " JOIN TB_DWG_PlanLink l ON l.DrawingId = d.DrawingId JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId"
        " LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId JOIN TB_PRC_Proc pr ON pr.ProcCd = p.ProcCd"
        f" WHERE p.PlanStatus IN ({','.join('?' * len(IMPACT_STATUSES))})"
    )
    params: list = [add_days(today, -30), today, *IMPACT_STATUSES]
    if drawing_id is not None:
        sql += " AND d.DrawingId = ?"
        params.append(drawing_id)
    if hull_nos is not None:
        sql += f" AND d.HullNo IN ({','.join('?' * len(hull_nos)) or 'NULL'})"
        params += hull_nos
    rows = conn.execute(sql, params).fetchall()
    rows.sort(key=lambda r: plan_sort_key(r["BlockCd"], r["Seq"], r["PlanId"]))
    rows.sort(key=lambda r: r["DrawingNo"])
    rows.sort(key=lambda r: r["IssueDt"], reverse=True)
    return [{
        "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "rev_no": r["RevNo"], "issue_dt": r["IssueDt"],
        "plan_id": r["PlanId"], "plan_label": plan_label(r["BlockCd"], r["PHull"], r["ProcNm"]),
        "plan_status": r["PlanStatus"], "hull_no": r["HullNo"], "change_desc": r["ChangeDesc"],
        "link": {"screen": "drawing", "param": r["DrawingId"]},
    } for r in rows]
