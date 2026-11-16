"""F11 사용 로그: API 호출 기록(미들웨어가 호출)과 집계."""
import datetime as dt
import sqlite3

from .. import db
from ..errors import validation

KST = dt.timedelta(hours=9)
SKIP_PREFIXES = ("/api/usage/",)
SKIP_PATHS = ("/api/health", "/api/usage")
# 경로 접두어 → 기능(앞에서부터 첫 일치)
FEATURES = (
    (("/api/hulls/{hull_no}/plans", "/api/plans", "/api/plan-hulls", "/api/procs"), "공정 계획"),
    (("/api/progress",), "공정 실적"),
    (("/api/hulls", "/api/blocks"), "호선 관리"),
    (("/api/drawings",), "도면 관리"),
    (("/api/approvals",), "결재"),
    (("/api/dashboard",), "대시보드"),
    (("/api/users", "/api/auth-groups"), "회원관리"),
    (("/api/auth",), "로그인·인증"),
    (("/api/inquiries",), "건의·문의"),
    (("/api/chat",), "챗봇"),
    (("/api/me", "/api/codes"), "공통(메뉴·세션)"),
    (("/api/weather",), "날씨"),
)
DAYS = (7, 30, 90)


def feature_of(path: str) -> str:
    for prefixes, name in FEATURES:
        if any(path.startswith(p) for p in prefixes):
            return name
    return "기타"


def should_log(path: str) -> bool:
    return path.startswith("/api") and path not in SKIP_PATHS and not path.startswith(SKIP_PREFIXES)


def record(emp_no: str | None, method: str, path: str, status: int, duration_ms: int, call_dt: str) -> None:
    """미들웨어가 스레드풀에서 호출한다. 실패는 호출 쪽에서 삼킨다."""
    conn = db.connect()
    try:
        conn.execute("INSERT INTO TB_SYS_LogApi(EmpNo, Method, Path, Status, DurationMs, CallDt) VALUES (?, ?, ?, ?, ?, ?)",
                     (emp_no, method, path, status, duration_ms, call_dt))
    finally:
        conn.close()


def _kst_today() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) + KST).date()


def summary(conn: sqlite3.Connection, days, emp_no: str | None) -> dict:
    if days not in DAYS:
        raise validation("days", "조회 기간은 7, 30, 90일 중 하나입니다.")
    emp_no = (emp_no or "").strip() or None
    first = _kst_today() - dt.timedelta(days=days - 1)
    since = (dt.datetime.combine(first, dt.time()) - KST).strftime("%Y-%m-%d %H:%M:%S")
    where, params = "CallDt >= ?", [since]
    if emp_no:
        where += " AND EmpNo = ?"
        params.append(emp_no)
    rows = conn.execute(f"SELECT EmpNo, Method, Path, Status, DurationMs, CallDt, DemoYN FROM TB_SYS_LogApi WHERE {where}",
                        params).fetchall()
    names = {r[0]: r[1] for r in conn.execute("SELECT emp_no, display_name FROM users")}

    def kst(s: str) -> dt.datetime:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S") + KST

    calls = len(rows)
    errors = sum(r["Status"] >= 400 for r in rows)
    lp = [since] + ([emp_no] if emp_no else [])
    logins = conn.execute("SELECT COUNT(*) FROM TB_SYS_LogAccess WHERE LoginDt >= ?" + (" AND UserId = ?" if emp_no else ""),
                          lp).fetchone()[0]
    daily = {(first + dt.timedelta(days=i)).isoformat(): {"calls": 0, "errors": 0, "users": set()} for i in range(days)}
    hours = [0] * 24
    feats: dict = {}
    users: dict = {}
    eps: dict = {}
    for r in rows:
        t = kst(r["CallDt"])
        day = daily.get(t.date().isoformat())
        if day is not None:
            day["calls"] += 1
            day["errors"] += r["Status"] >= 400
            if r["EmpNo"]:
                day["users"].add(r["EmpNo"])
        hours[t.hour] += 1
        f = feature_of(r["Path"])
        fe = feats.setdefault(f, {"calls": 0, "paths": set()})
        fe["calls"] += 1
        fe["paths"].add(r["Path"])
        if r["EmpNo"]:
            u = users.setdefault(r["EmpNo"], {"calls": 0, "last": r["CallDt"], "feats": {}})
            u["calls"] += 1
            u["last"] = max(u["last"], r["CallDt"])
            u["feats"][f] = u["feats"].get(f, 0) + 1
        e = eps.setdefault((r["Method"], r["Path"]), {"calls": 0, "errors": 0, "sum": 0, "max": 0})
        e["calls"] += 1
        e["errors"] += r["Status"] >= 400
        e["sum"] += r["DurationMs"]
        e["max"] = max(e["max"], r["DurationMs"])

    mwhere, mparams = "m.InDt >= ?", [since]
    if emp_no:
        mwhere += " AND l.UserId = ?"
        mparams.append(emp_no)
    menus = [{"menu_id": r[0], "title": r[1], "opens": r[2], "users": r[3]} for r in conn.execute(
        "SELECT m.MenuId, mi.Title, COUNT(*), COUNT(DISTINCT l.UserId) FROM TB_SYS_LogMenuAccess m"
        " JOIN TB_SYS_LogAccess l ON l.LogId = m.LogId JOIN TB_SYS_MenuInfo mi ON mi.MenuId = m.MenuId"
        f" WHERE {mwhere} GROUP BY m.MenuId ORDER BY COUNT(*) DESC, mi.Seq", mparams)]
    recent = [{"call_dt": r[0], "method": r[1], "path": r[2], "status": r[3], "emp_no": r[4], "display_name": names.get(r[4])}
              for r in conn.execute(f"SELECT CallDt, Method, Path, Status, EmpNo FROM TB_SYS_LogApi WHERE {where} AND Status >= 400"
                                    " ORDER BY CallDt DESC, LogApiId DESC LIMIT 10", params)]
    top_users = sorted(users.items(), key=lambda kv: (-kv[1]["calls"], kv[0]))[:10]
    return {
        "days": days, "emp_no": emp_no, "since": since,
        "kpi": {"calls": calls, "users": len(users), "logins": logins, "errors": errors,
                "error_rate": round(errors * 100 / calls, 1) if calls else 0.0,
                "avg_ms": round(sum(r["DurationMs"] for r in rows) / calls) if calls else 0},
        "daily": [{"date": d, "calls": v["calls"], "errors": v["errors"], "users": len(v["users"])} for d, v in daily.items()],
        "hours": hours,
        "features": [{"feature": f, "calls": v["calls"], "paths": len(v["paths"])}
                     for f, v in sorted(feats.items(), key=lambda kv: (-kv[1]["calls"], kv[0]))],
        "top_users": [{"emp_no": k, "display_name": names.get(k, k), "calls": v["calls"], "last_dt": v["last"],
                       "top_feature": max(v["feats"].items(), key=lambda kv: (kv[1], kv[0]))[0]} for k, v in top_users],
        "endpoints": [{"method": m, "path": p, "calls": v["calls"], "errors": v["errors"], "avg_ms": round(v["sum"] / v["calls"]),
                       "max_ms": v["max"], "feature": feature_of(p)}
                      for (m, p), v in sorted(eps.items(), key=lambda kv: (-kv[1]["calls"], kv[0]))[:15]],
        "menus": menus,
        "recent_errors": recent,
        "demo_calls": sum(r["DemoYN"] == 1 for r in rows),
        "user_options": [{"emp_no": r[0], "display_name": r[1]}
                         for r in conn.execute("SELECT emp_no, display_name FROM users ORDER BY display_name, emp_no")],
    }
