"""F03 대시보드 요약(한 번의 응답). 규칙은 rules(BR-01·02·07)를 재사용한다."""
import sqlite3

from .. import config
from . import rules
from .plans import PLAN_SQL

ACTIVE = ("DESIGN", "BUILD", "LAUNCH", "TRIAL")
DWG_STATES = ("ISSUED", "APPROVED", "REVIEW", "DRAFT")
LIST_MAX = 6


def _plan_item(r, blockers: dict) -> dict:
    return {
        "plan_id": r["PlanId"], "hull_no": r["HullNo"], "label": rules.plan_label(r["BlockCd"], r["HullNo"], r["ProcNm"]),
        "plan_status": r["PlanStatus"], "progress_rate": r["ProgressRate"], "plan_start_dt": r["PlanStartDt"],
        "plan_end_dt": r["PlanEndDt"], "blockers": [b["drawing_no"] for b in blockers.get(r["PlanId"], [])],
        "link": {"screen": "plan-gantt", "param": r["HullNo"]},
    }


def _section(items: list) -> dict:
    return {"count": len(items), "items": items[:LIST_MAX]}


def summary(conn: sqlite3.Connection) -> dict:
    hulls = conn.execute("SELECT HullNo, HullNm, HullStatus, DeliveryDt FROM TB_MST_Hull WHERE UseYN = 1 ORDER BY HullNo").fetchall()
    hull_nos = [h["HullNo"] for h in hulls]
    marks = ",".join("?" * len(hull_nos)) or "NULL"
    plans = conn.execute(PLAN_SQL + f" WHERE p.HullNo IN ({marks})", hull_nos).fetchall()
    blockers: dict = {}
    for h in hull_nos:
        blockers |= rules.blockers_map(conn, hull_no=h)
    progress = rules.progress_by(conn, "HullNo", f"WHERE HullNo IN ({marks})", tuple(hull_nos))

    delay = sorted((p for p in plans if p["PlanStatus"] == "DELAY"), key=lambda p: (p["PlanEndDt"], p["PlanId"]))
    waiting = sorted((p for p in plans if p["PlanStatus"] == "PLAN" and p["PlanId"] in blockers),
                     key=lambda p: (p["PlanStartDt"], p["PlanId"]))
    status_counts = {s: 0 for s in rules.PLAN_STATUSES}
    for p in plans:
        status_counts[p["PlanStatus"]] = status_counts.get(p["PlanStatus"], 0) + 1

    disc_names = [(r[0], r[1]) for r in conn.execute(
        "SELECT Code, CodeName FROM TB_SYS_Code WHERE CodeGroup = 'DWGDISC' AND UseYN = 1 ORDER BY Seq, Code")]
    dcounts: dict = {}
    for disc, st, n in conn.execute(
            f"SELECT Discipline, DwgStatus, COUNT(*) FROM TB_DWG_Drawing WHERE HullNo IN ({marks}) GROUP BY 1, 2", hull_nos):
        dcounts.setdefault(disc, {})[st] = n
    disciplines = [{"discipline": c, "name": nm, "total": sum(dcounts[c].values()),
                    "counts": {s: dcounts[c].get(s, 0) for s in DWG_STATES}} for c, nm in disc_names if c in dcounts]

    months: dict = {}
    for h in hulls:
        if h["DeliveryDt"]:
            months.setdefault(h["DeliveryDt"][:7], []).append(h["HullNo"])
    pending = conn.execute(f"SELECT COUNT(*) FROM TB_DWG_Drawing WHERE DwgStatus IN ('REVIEW', 'APPROVED') AND HullNo IN ({marks})",
                           hull_nos).fetchone()[0]

    return {
        "today": config.TODAY,
        "kpi": {
            "active_hulls": {"value": sum(h["HullStatus"] in ACTIVE for h in hulls), "link": {"screen": "hull-list"}},
            "delay_plans": {"value": len(delay), "link": {"screen": "plan-gantt"}},
            "waiting_plans": {"value": len(waiting), "link": {"screen": "plan-gantt"}},
            "pending_drawings": {"value": pending, "link": {"screen": "dwg-approval"}},
        },
        "hull_progress": [{"hull_no": h["HullNo"], "hull_nm": h["HullNm"], "progress": progress.get(h["HullNo"]) or 0,
                           "link": {"screen": "plan-gantt", "param": h["HullNo"]}} for h in hulls],
        "plan_status": [{"status": s, "count": status_counts[s]} for s in rules.PLAN_STATUSES],
        "drawing_disciplines": disciplines,
        "deliveries": [{"month": m, "count": len(v), "hull_nos": v} for m, v in sorted(months.items())],
        "delay_list": _section([_plan_item(p, blockers) for p in delay]),
        "waiting_list": _section([_plan_item(p, blockers) for p in waiting]),
        "impact_list": _section(rules.revision_impacts(conn, hull_nos=hull_nos)),
    }
