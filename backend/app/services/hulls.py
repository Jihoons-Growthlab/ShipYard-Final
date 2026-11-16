"""F04 호선·주요일정·블록·요약. API↔DB 매핑은 이 파일 한 곳."""
import re
import sqlite3

from .. import config, db, storage
from ..errors import AppError, duplicate, not_found, validation
from ..util import blank_to_none, days_between, is_date
from . import rules
from .shell import code_set

HULL_MAP = {
    "hull_no": "HullNo", "hull_nm": "HullNm", "ship_type": "ShipType", "hull_status": "HullStatus",
    "owner_nm": "OwnerNm", "class_society": "ClassSociety", "length_m": "LengthM", "breadth_m": "BreadthM",
    "depth_m": "DepthM", "dead_weight": "DeadWeight", "dock_no": "DockNo", "contract_dt": "ContractDt",
    "delivery_dt": "DeliveryDt", "remark": "Remark", "use_yn": "UseYN", "create_user_id": "CreateUserId",
    "create_dt": "CreateDt", "modify_user_id": "ModifyUserId", "modify_dt": "ModifyDt",
}
EDITABLE = [k for k in HULL_MAP if k not in ("hull_no", "create_user_id", "create_dt", "modify_user_id", "modify_dt")]
HULL_NO_RE = re.compile(r"^[A-Za-z0-9._-]{1,20}$")
MILESTONES = ("CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER")
NUMERIC = ("length_m", "breadth_m", "depth_m", "dead_weight")


def hull_not_found() -> AppError:
    return not_found("HULL_NOT_FOUND", "호선을 찾을 수 없습니다.")


def ensure_hull(conn: sqlite3.Connection, hull_no: str):
    r = conn.execute("SELECT * FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone()
    if not r:
        raise hull_not_found()
    return r


def _to_api(r, progress: dict, counts: dict) -> dict:
    d = {k: r[v] for k, v in HULL_MAP.items()}
    d["use_yn"] = bool(d["use_yn"])
    pc, dc = counts.get(r["HullNo"], (0, 0))
    d.update(plan_count=pc, progress=progress.get(r["HullNo"]), delay_count=dc)
    return d


def _counts(conn) -> dict:
    return {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT HullNo, COUNT(*), SUM(PlanStatus = 'DELAY') FROM TB_PRC_Plan GROUP BY HullNo")}


def list_hulls(conn: sqlite3.Connection, status: str | None = None, ship_type: str | None = None,
               q: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM TB_MST_Hull WHERE 1=1", []
    if status:
        sql += " AND HullStatus = ?"
        params.append(status)
    if ship_type:
        sql += " AND ShipType = ?"
        params.append(ship_type)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        sql += " AND (lower(HullNo) LIKE ? OR lower(HullNm) LIKE ? OR lower(COALESCE(OwnerNm,'')) LIKE ?)"
        params += [like, like, like]
    rows = conn.execute(sql + " ORDER BY HullNo", params).fetchall()
    prog, counts = rules.progress_by(conn, "HullNo"), _counts(conn)
    return [_to_api(r, prog, counts) for r in rows]


def get_hull(conn: sqlite3.Connection, hull_no: str) -> dict:
    r = ensure_hull(conn, hull_no)
    prog = rules.progress_by(conn, "HullNo", "WHERE HullNo = ?", (hull_no,))
    return _to_api(r, prog, _counts(conn))


def _validate(conn: sqlite3.Connection, v: dict, fields: set[str], creating: bool) -> None:
    """명세 표 순서: 번호 없음 → 형식 → 중복 → (수정 시 변경) → 코드 → 날짜 형식 → 인도<계약 → 음수 → 상태 비움."""
    if creating:
        if not v.get("hull_no"):
            raise validation("hull_no", "호선번호를 입력하세요.")
        if not HULL_NO_RE.match(v["hull_no"]):
            raise validation("hull_no", "호선번호는 영문/숫자/._- 1~20자입니다.")
        if conn.execute("SELECT 1 FROM TB_MST_Hull WHERE HullNo = ?", (v["hull_no"],)).fetchone():
            raise duplicate("이미 존재하는 호선번호입니다.", "hull_no")
    if v.get("ship_type") and v["ship_type"] not in code_set(conn, "SHIPTYPE"):
        raise validation("ship_type", "허용되지 않는 코드값입니다.")
    if v.get("hull_status") and v["hull_status"] not in code_set(conn, "HULLSTAT"):
        raise validation("hull_status", "허용되지 않는 코드값입니다.")
    for f in ("contract_dt", "delivery_dt"):
        if v.get(f) and not is_date(v[f]):
            raise validation(f, "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다.")
    if v.get("contract_dt") and v.get("delivery_dt") and v["delivery_dt"] < v["contract_dt"]:
        raise validation("delivery_dt", "인도 예정일이 계약일보다 빠릅니다.")
    for f in NUMERIC:
        if v.get(f) is not None and v[f] < 0:
            raise validation(f, "0 이상의 값을 입력하세요.")
    if not v.get("hull_status"):
        raise validation("hull_status", "상태를 선택하세요.")


def _clean(data: dict) -> dict:
    return {k: blank_to_none(v) for k, v in data.items()}


def create_hull(conn: sqlite3.Connection, data: dict, fields: set[str], user: dict) -> dict:
    v = _clean(data)
    if "hull_status" not in fields:
        v["hull_status"] = "PLAN"
    if v.get("use_yn") is None:
        v["use_yn"] = True
    v["hull_nm"] = v.get("hull_nm") or ""
    _validate(conn, v, fields, creating=True)
    cols = ["hull_no"] + EDITABLE
    vals = [v.get(c) for c in cols]
    vals[cols.index("use_yn")] = 1 if v["use_yn"] else 0
    with db.tx(conn):
        conn.execute(
            f"INSERT INTO TB_MST_Hull ({','.join(HULL_MAP[c] for c in cols)}, CreateUserId, CreateDt)"
            f" VALUES ({','.join('?' * len(cols))}, ?, ?)",
            vals + [user["emp_no"], config.TODAY],
        )
        conn.executemany(
            "INSERT INTO TB_MST_HullMilestone(HullNo, MilestoneCd, PlanDt) VALUES (?, ?, ?)",
            [(v["hull_no"], m, v.get("delivery_dt") if m == "DELIVER" else None) for m in MILESTONES],
        )
    return get_hull(conn, v["hull_no"])


def update_hull(conn: sqlite3.Connection, hull_no: str, data: dict, fields: set[str], user: dict) -> dict:
    cur = ensure_hull(conn, hull_no)
    if "hull_no" in fields and data.get("hull_no") not in (None, hull_no):
        raise validation("hull_no", "호선번호는 수정할 수 없습니다.")
    changes = {k: blank_to_none(data[k]) for k in fields if k in EDITABLE}
    if "hull_nm" in changes and changes["hull_nm"] is None:
        changes["hull_nm"] = ""
    if "use_yn" in changes:
        changes["use_yn"] = 1 if changes["use_yn"] or changes["use_yn"] is None else 0
    merged = {k: cur[HULL_MAP[k]] for k in EDITABLE} | changes
    _validate(conn, merged, fields, creating=False)
    with db.tx(conn):
        sets = [f"{HULL_MAP[k]} = ?" for k in changes] + ["ModifyUserId = ?", "ModifyDt = ?"]
        conn.execute(f"UPDATE TB_MST_Hull SET {', '.join(sets)} WHERE HullNo = ?",
                     list(changes.values()) + [user["emp_no"], config.TODAY, hull_no])
    return get_hull(conn, hull_no)


def delete_hull(conn: sqlite3.Connection, hull_no: str) -> None:
    ensure_hull(conn, hull_no)
    with db.tx(conn):
        files = storage.revision_file_ids(conn, "d.HullNo = ?", (hull_no,))
        conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,))
    storage.remove_files(files)


# --- 주요일정
def milestones(conn: sqlite3.Connection, hull_no: str) -> list[dict]:
    ensure_hull(conn, hull_no)
    out = []
    for r in conn.execute(
        "SELECT m.MilestoneCd, c.CodeName, m.PlanDt, m.ActualDt FROM TB_MST_HullMilestone m"
        " LEFT JOIN TB_SYS_Code c ON c.CodeGroup = 'MILESTONE' AND c.Code = m.MilestoneCd"
        " WHERE m.HullNo = ? ORDER BY COALESCE(c.Seq, 999), m.MilestoneCd",
        (hull_no,),
    ):
        diff = days_between(r[2], r[3]) if r[2] and r[3] else None
        out.append({"milestone_cd": r[0], "name": r[1] or r[0], "plan_dt": r[2], "actual_dt": r[3], "diff_days": diff})
    return out


def save_milestones(conn: sqlite3.Connection, hull_no: str, items: list[dict]) -> list[dict]:
    ensure_hull(conn, hull_no)
    allowed, seen, clean = code_set(conn, "MILESTONE"), set(), []
    for it in items:
        cd = blank_to_none(it.get("milestone_cd"))
        if not cd or cd not in allowed or cd in seen:
            raise validation("milestone_cd", "허용되지 않거나 중복된 일정 코드입니다.")
        seen.add(cd)
        pd, ad = blank_to_none(it.get("plan_dt")), blank_to_none(it.get("actual_dt"))
        for f, val in (("plan_dt", pd), ("actual_dt", ad)):
            if val and not is_date(val):
                raise validation(f, "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다.")
        clean.append((hull_no, cd, pd, ad))
    with db.tx(conn):
        conn.executemany(
            "INSERT INTO TB_MST_HullMilestone(HullNo, MilestoneCd, PlanDt, ActualDt) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(HullNo, MilestoneCd) DO UPDATE SET PlanDt = excluded.PlanDt, ActualDt = excluded.ActualDt",
            clean,
        )
    return milestones(conn, hull_no)


# --- 블록
def _block_api(r, prog: dict, pcount: dict, dcount: dict) -> dict:
    return {
        "block_id": r["BlockId"], "hull_no": r["HullNo"], "block_cd": r["BlockCd"], "block_nm": r["BlockNm"],
        "block_type": r["BlockType"], "parent_block_id": r["ParentBlockId"], "weight_ton": r["WeightTon"],
        "use_yn": bool(r["UseYN"]), "plan_count": pcount.get(r["BlockId"], 0), "progress": prog.get(r["BlockId"]),
        "drawing_count": dcount.get(r["BlockId"], 0),
    }


def blocks(conn: sqlite3.Connection, hull_no: str) -> list[dict]:
    ensure_hull(conn, hull_no)
    rows = conn.execute("SELECT * FROM TB_MST_Block WHERE HullNo = ?", (hull_no,)).fetchall()
    prog = rules.progress_by(conn, "BlockId", "WHERE HullNo = ? AND BlockId IS NOT NULL", (hull_no,))
    pcount = dict(conn.execute("SELECT BlockId, COUNT(*) FROM TB_PRC_Plan WHERE HullNo = ? GROUP BY BlockId", (hull_no,)).fetchall())
    dcount = dict(conn.execute("SELECT BlockId, COUNT(*) FROM TB_DWG_Drawing WHERE HullNo = ? GROUP BY BlockId", (hull_no,)).fetchall())
    rows = sorted(rows, key=lambda r: rules.code_sort_key(r["BlockCd"]))
    return [_block_api(r, prog, pcount, dcount) for r in rows]


def create_block(conn: sqlite3.Connection, hull_no: str, data: dict) -> dict:
    ensure_hull(conn, hull_no)
    v = _clean(data)
    if not v.get("block_cd"):
        raise validation("block_cd", "블록코드를 입력하세요.")
    if conn.execute("SELECT 1 FROM TB_MST_Block WHERE HullNo = ? AND BlockCd = ?", (hull_no, v["block_cd"])).fetchone():
        raise duplicate("이미 존재하는 블록코드입니다.", "block_cd")
    if v.get("block_type") and v["block_type"] not in code_set(conn, "BLOCKTYPE"):
        raise validation("block_type", "허용되지 않는 코드값입니다.")
    if v.get("weight_ton") is not None and v["weight_ton"] < 0:
        raise validation("weight_ton", "0 이상의 값을 입력하세요.")
    if v.get("parent_block_id") is not None and not conn.execute(
            "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (v["parent_block_id"], hull_no)).fetchone():
        raise validation("parent_block_id", "해당 호선의 블록이 아닙니다.")
    with db.tx(conn):
        bid = conn.execute(
            "INSERT INTO TB_MST_Block(HullNo, BlockCd, BlockNm, BlockType, ParentBlockId, WeightTon) VALUES (?,?,?,?,?,?)",
            (hull_no, v["block_cd"], v.get("block_nm"), v.get("block_type"), v.get("parent_block_id"), v.get("weight_ton")),
        ).lastrowid
    return next(b for b in blocks(conn, hull_no) if b["block_id"] == bid)


def delete_block(conn: sqlite3.Connection, block_id: int) -> None:
    r = conn.execute("SELECT HullNo FROM TB_MST_Block WHERE BlockId = ?", (block_id,)).fetchone()
    if not r:
        raise not_found("BLOCK_NOT_FOUND", "블록을 찾을 수 없습니다.")
    with db.tx(conn):
        conn.execute("DELETE FROM TB_MST_Block WHERE BlockId = ?", (block_id,))  # 공정·연계 CASCADE, 도면 BlockId NULL
        rules.recalc_hull(conn, r[0])


def summary(conn: sqlite3.Connection, hull_no: str) -> dict:
    ensure_hull(conn, hull_no)
    ps = {s: 0 for s in rules.PLAN_STATUSES}
    for st, n in conn.execute("SELECT PlanStatus, COUNT(*) FROM TB_PRC_Plan WHERE HullNo = ? GROUP BY PlanStatus", (hull_no,)):
        ps[st] = n
    ds = {s: 0 for s in ("ISSUED", "APPROVED", "REVIEW", "DRAFT")}
    dtotal = 0
    for st, n in conn.execute("SELECT DwgStatus, COUNT(*) FROM TB_DWG_Drawing WHERE HullNo = ? GROUP BY DwgStatus", (hull_no,)):
        dtotal += n
        if st in ds:
            ds[st] = n
    prog = rules.progress_by(conn, "HullNo", "WHERE HullNo = ?", (hull_no,))
    return {"hull_no": hull_no, "plan_count": sum(ps.values()), "progress": prog.get(hull_no),
            "plan_status": ps, "drawing_count": dtotal, "drawing_status": ds}
