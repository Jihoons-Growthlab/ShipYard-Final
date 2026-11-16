"""F14 보고서(PDF·XLSX). MCP build_report 도구가 build()를 호출한다. 섹션은 메뉴 View 권한(BR-10)별."""
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import config
from ..errors import AppError, not_found
from ..permissions import menu_levels
from . import drawings as dwg_svc
from . import hulls as hull_svc
from . import plans as plan_svc

FORMATS = {"pdf": "PDF", "xlsx": "Excel"}
MIME = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
ID_RE = re.compile(r"^[0-9a-f]{24}$")
SECTIONS = (("hulls", "M11", "호선"), ("plans", "M21", "공정"), ("drawings", "M31", "도면"))
MSG_NO_PERM = "보고서에 넣을 수 있는 메뉴 권한(호선·공정·도면 조회)이 없습니다."
MSG_NO_FONT = "보고서 PDF용 한글 글꼴을 찾을 수 없습니다. SHIPYARD_REPORT_FONT에 글꼴 경로를 설정해 주세요."
FONT_CANDIDATES = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/NanumGothic.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
)
PLAN_ORDER = ("PLAN", "READY", "WORK", "DONE", "DELAY")
STATUS_RGB = {"PLAN": (148, 163, 184), "READY": (14, 165, 233), "WORK": (37, 99, 235), "DONE": (22, 163, 74),
              "DELAY": (220, 38, 38)}
HEADS = {
    "hulls": ["호선번호", "호선명", "선종", "상태", "선주", "인도예정", "진척률", "지연"],
    "plans": ["호선", "블록", "공정", "계획 시작", "계획 종료", "진척", "상태", "담당자", "미배포 필수 도면"],
    "drawings": ["도면번호", "도면명", "호선", "블록", "분야", "Rev", "상태", "설계자"],
    "milestones": ["일정", "계획", "실적", "차이(일)"],
}
KPI = (("hulls", "호선 수"), ("plans", "공정 수"), ("delay", "지연 공정"), ("waiting", "도면 대기 공정"),
       ("drawings", "도면 수"), ("unissued", "미배포 도면"))


def pct(v) -> str:
    if v is None:
        return "-"
    v = float(v)
    return f"{int(v)}%" if v.is_integer() else f"{v:g}%"


def _d(v) -> str:
    return "-" if v is None or v == "" else str(v)


# --- 데이터 수집
def collect(conn: sqlite3.Connection, emp_no: str, hull_no: str | None) -> dict:
    levels = menu_levels(conn, emp_no)
    allowed = {key for key, mid, _ in SECTIONS if levels.get(mid, 0) >= 1}
    if not allowed:
        raise AppError(400, "REPORT_ERROR", MSG_NO_PERM)
    if hull_no:
        hull_svc.ensure_hull(conn, hull_no)
        hull_nos = [hull_no]
    else:
        hull_nos = [r[0] for r in conn.execute("SELECT HullNo FROM TB_MST_Hull WHERE UseYN = 1 ORDER BY HullNo")]
    codes: dict = {}
    for g, c, n in conn.execute("SELECT CodeGroup, Code, CodeName FROM TB_SYS_Code"):
        codes.setdefault(g, {})[c] = n
    name = lambda g, c: codes.get(g, {}).get(c, c) if c else "-"  # noqa: E731
    title = f"{hull_no} 호선 현황 보고서" if hull_no else "전체 호선 현황 보고서"
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    author = conn.execute("SELECT display_name FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    rep = {"title": title, "author": author[0] if author else emp_no, "created": now.strftime("%Y-%m-%d %H:%M"),
           "base_dt": config.TODAY, "stamp": now.strftime("%Y%m%d_%H%M"), "sections": allowed,
           "excluded": [label for key, _, label in SECTIONS if key not in allowed], "rows": {}, "milestones": None,
           "plan_status": {}, "dwg_status": {}}
    summary = {k: None for k, _ in KPI}
    if "hulls" in allowed:
        hulls = [h for h in hull_svc.list_hulls(conn) if h["hull_no"] in hull_nos]
        summary["hulls"] = len(hulls)
        rep["rows"]["hulls"] = [[h["hull_no"], h["hull_nm"], name("SHIPTYPE", h["ship_type"]),
                                 name("HULLSTAT", h["hull_status"]), _d(h["owner_nm"]), _d(h["delivery_dt"]),
                                 pct(h["progress"]), h["delay_count"] or 0] for h in hulls]
        if hull_no:
            rep["milestones"] = [[m["name"], _d(m["plan_dt"]), _d(m["actual_dt"]), _d(m["diff_days"])]
                                 for m in hull_svc.milestones(conn, hull_no)]
    if "plans" in allowed:
        plans = [p for h in hull_nos for p in plan_svc.load_plans(conn, h)]
        summary.update(plans=len(plans), delay=sum(p["plan_status"] == "DELAY" for p in plans),
                       waiting=sum(bool(p["drawing_wait"]) for p in plans))
        rep["plan_status"] = {s: sum(p["plan_status"] == s for p in plans) for s in PLAN_ORDER}
        rep["plan_status_names"] = {s: name("PLANSTAT", s) for s in PLAN_ORDER}
        rep["rows"]["plans"] = [[p["hull_no"], _d(p["block_cd"]), p["proc_nm"], _d(p["plan_start_dt"]),
                                 _d(p["plan_end_dt"]), pct(p["progress_rate"]), name("PLANSTAT", p["plan_status"]),
                                 _d(p["manager_nm"]), ", ".join(b["drawing_no"] for b in p["blockers"]) or "-",
                                 p["plan_status"] == "DELAY"] for p in plans]
    if "drawings" in allowed:
        dwgs = [d for h in hull_nos for d in dwg_svc.list_drawings(conn, hull_no=h)]
        summary.update(drawings=len(dwgs), unissued=sum(d["dwg_status"] not in ("ISSUED", "OBSOLETE") for d in dwgs))
        for d in dwgs:
            k = name("DWGSTAT", d["dwg_status"])
            rep["dwg_status"][k] = rep["dwg_status"].get(k, 0) + 1
        rep["rows"]["drawings"] = [[d["drawing_no"], d["drawing_nm"], d["hull_no"], _d(d["block_cd"]),
                                    name("DWGDISC", d["discipline"]),
                                    _d(d["current_rev_no"] if d["current_rev_no"] is not None else d["latest_rev_no"]),
                                    name("DWGSTAT", d["dwg_status"]), _d(d["designer_nm"])] for d in dwgs]
    rep["summary"] = summary
    return rep


# --- 파일 위치
def user_dir(emp_no: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", emp_no).strip(".") or "_"
    return config.report_dir() / safe


def report_path(emp_no: str, report_id: str, fmt: str) -> Path | None:
    if not ID_RE.match(report_id or "") or fmt not in FORMATS:
        return None
    base = user_dir(emp_no).resolve()
    p = (base / f"{report_id}.{fmt}").resolve()
    return p if p.parent == base and p.is_file() else None


def find(emp_no: str, report_id: str, fmt: str | None) -> tuple[Path, str, str]:
    for f in ([fmt] if fmt else list(FORMATS)):
        p = report_path(emp_no, report_id, f)
        if p:
            meta = p.with_suffix(".json")
            filename = json.loads(meta.read_text("utf-8")).get("filename") if meta.is_file() else p.name
            return p, filename, MIME[f]
    raise not_found("REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다.")


def build(conn: sqlite3.Connection, emp_no: str, fmt: str, hull_no: str | None) -> dict:
    rep = collect(conn, emp_no, hull_no)
    report_id = secrets.token_hex(12)
    d = user_dir(emp_no)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{report_id}.{fmt}"
    (write_pdf if fmt == "pdf" else write_xlsx)(rep, path)
    filename = f"{rep['title'].replace(' ', '_')}_{rep['stamp']}.{fmt}"
    path.with_suffix(".json").write_text(json.dumps({"filename": filename, "format": fmt}, ensure_ascii=False), "utf-8")
    return {"report_id": report_id, "format": fmt, "filename": filename, "title": rep["title"],
            "size": path.stat().st_size, "summary": rep["summary"],
            "download_url": f"/api/chat/reports/{report_id}?format={fmt}"}


# --- PDF (fpdf2, A4 가로)
NAVY, STRIPE, LINE, MUTED = (23, 61, 88), (244, 247, 251), (214, 222, 232), (100, 116, 139)
RED, ORANGE = (220, 38, 38), (234, 88, 12)
WIDTHS = {"hulls": [25, 60, 30, 25, 55, 30, 27, 25], "plans": [20, 22, 30, 27, 27, 20, 22, 28, 81],
          "drawings": [45, 80, 22, 22, 28, 15, 30, 35], "milestones": [60, 45, 45, 30]}


def font_path() -> tuple[str, int]:
    env = config.report_font()
    for p in ([env] if env else []) + list(FONT_CANDIDATES):
        if p and os.path.isfile(p):
            return p, 0
    raise AppError(400, "REPORT_ERROR", MSG_NO_FONT)


def write_pdf(rep: dict, path: Path) -> None:
    from fpdf import FPDF

    fpath, idx = font_path()

    class Pdf(FPDF):
        def footer(self):
            self.set_y(-10)
            self.set_font("ko", size=8)
            self.set_text_color(*MUTED)
            self.cell(0, 5, f"SWP 조선소 통합관리 · {rep['title']} · {self.page_no()}쪽", align="C")

    pdf = Pdf(orientation="L", unit="mm", format="A4")
    pdf.add_font("ko", fname=fpath, collection_font_number=idx)
    pdf.set_title(rep["title"])
    pdf.set_author(rep["author"])
    pdf.set_creator("SWP 조선소 통합관리")
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(False, margin=14)
    pdf.add_page()
    W = pdf.w - 20

    # 머리띠
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("ko", size=17)
    pdf.set_xy(10, 6)
    pdf.cell(W, 8, rep["title"])
    pdf.set_font("ko", size=9)
    pdf.set_xy(10, 16)
    pdf.cell(W, 5, f"작성 {rep['created']} · 작성자 {rep['author']} · 기준일 {rep['base_dt']}")

    # KPI 카드 6개
    s, gap, y = rep["summary"], 4, 32
    cw = (W - gap * 5) / 6
    for i, (key, label) in enumerate(KPI):
        x, v = 10 + i * (cw + gap), s[key]
        accent = RED if key == "delay" and v else ORANGE if key in ("waiting", "unissued") and v else NAVY
        pdf.set_draw_color(*LINE)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x, y, cw, 18, style="DF")
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, 1.4, 18, style="F")
        pdf.set_text_color(*MUTED)
        pdf.set_font("ko", size=8)
        pdf.set_xy(x + 4, y + 2.5)
        pdf.cell(cw - 6, 4, label)
        pdf.set_text_color(*(accent if accent != NAVY else (15, 23, 42)))
        pdf.set_font("ko", size=15)
        pdf.set_xy(x + 4, y + 8)
        pdf.cell(cw - 6, 7, "-" if v is None else f"{v:,}")
    pdf.set_y(y + 24)

    if rep["excluded"]:
        pdf.set_text_color(*ORANGE)
        pdf.set_font("ko", size=9)
        pdf.cell(W, 5, "조회 권한이 없어 제외: " + ", ".join(rep["excluded"]))
        pdf.ln(7)

    def heading(text: str, need: float = 20):
        if pdf.get_y() + need > pdf.page_break_trigger:
            pdf.add_page()
        pdf.set_text_color(15, 23, 42)
        pdf.set_font("ko", size=11)
        pdf.cell(W, 6, text)
        pdf.ln(8)

    total = sum(rep["plan_status"].values())
    if total:
        heading("공정 상태 분포")
        x, y = 10, pdf.get_y()
        for st in PLAN_ORDER:
            n = rep["plan_status"][st]
            if not n:
                continue
            w = W * n / total
            pdf.set_fill_color(*STATUS_RGB[st])
            pdf.rect(x, y, w, 8, style="F")
            if w > 22:
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("ko", size=8)
                pdf.set_xy(x, y + 1.5)
                pdf.cell(w, 5, f"{rep['plan_status_names'][st]} {n}", align="C")
            x += w
        pdf.set_y(y + 13)

    def fit(text: str, w: float) -> str:
        text = str(text)
        if pdf.get_string_width(text) <= w:
            return text
        while text and pdf.get_string_width(text + "…") > w:
            text = text[:-1]
        return text + "…"

    def table(title: str, key: str, rows: list, status_col: int | None = None):
        heads, widths = HEADS[key], WIDTHS[key]
        heading(title, 30)

        def head_row():
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("ko", size=8.5)
            for h, w in zip(heads, widths):
                pdf.cell(w, 7, h, fill=True, align="C")
            pdf.ln(7)

        head_row()
        pdf.set_font("ko", size=8)
        if not rows:
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(*MUTED)
            pdf.cell(sum(widths), 7, "자료가 없습니다.", fill=True, align="C")
            pdf.ln(9)
            return
        for i, row in enumerate(rows):
            if pdf.get_y() + 6.5 > pdf.page_break_trigger:
                pdf.add_page()
                head_row()
                pdf.set_font("ko", size=8)
            delay = bool(row[-1]) if key == "plans" else False
            cells = row[:-1] if key == "plans" else row
            # 줄무늬 채움색은 직전 도형 색이 이어지지 않게 행마다 명시한다
            pdf.set_fill_color(*(STRIPE if i % 2 else (255, 255, 255)))
            for j, (v, w) in enumerate(zip(cells, widths)):
                pdf.set_text_color(*(RED if delay and j == status_col else (30, 41, 59)))
                align = "R" if isinstance(v, int) else "L"
                pdf.cell(w, 6.5, " " + fit(v, w - 2.5) + " ", fill=True, align=align)
            pdf.ln(6.5)
        pdf.ln(4)

    if rep["milestones"] is not None:
        table("주요 일정", "milestones", rep["milestones"])
    if "hulls" in rep["rows"]:
        table("호선 현황", "hulls", rep["rows"]["hulls"])
    if "plans" in rep["rows"]:
        table("공정 현황", "plans", rep["rows"]["plans"], status_col=6)
    if "drawings" in rep["rows"]:
        table("도면 현황", "drawings", rep["rows"]["drawings"])
    pdf.output(str(path))


# --- Excel (openpyxl)
def write_xlsx(rep: dict, path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    navy = PatternFill("solid", fgColor="173D58")
    head_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    red = Font(color="DC2626", bold=True)

    def head(ws, row: int, values: list):
        for c, v in enumerate(values, 1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.fill, cell.font, cell.border = navy, head_font, border
            cell.alignment = Alignment(horizontal="center", vertical="center")

    wb = Workbook()
    ws = wb.active
    ws.title = "요약"
    ws["A1"] = rep["title"]
    ws["A1"].font = Font(size=16, bold=True)
    ws["A2"] = f"작성 {rep['created']} · 작성자 {rep['author']} · 기준일 {rep['base_dt']}"
    r = 4
    head(ws, r, [label for _, label in KPI])
    for c, (key, _) in enumerate(KPI, 1):
        cell = ws.cell(row=r + 1, column=c, value=rep["summary"][key] if rep["summary"][key] is not None else "-")
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
    r += 3
    if rep["plan_status"]:
        ws.cell(row=r, column=1, value="공정 상태별 건수").font = Font(bold=True)
        head(ws, r + 1, ["상태", "건수"])
        r += 2
        for st in PLAN_ORDER:
            for c, v in enumerate((rep["plan_status_names"][st], rep["plan_status"][st]), 1):
                ws.cell(row=r, column=c, value=v).border = border
            r += 1
        r += 1
    if rep["dwg_status"]:
        ws.cell(row=r, column=1, value="도면 상태별 건수").font = Font(bold=True)
        head(ws, r + 1, ["상태", "건수"])
        r += 2
        for k, n in rep["dwg_status"].items():
            for c, v in enumerate((k, n), 1):
                ws.cell(row=r, column=c, value=v).border = border
            r += 1
        r += 1
    if rep["milestones"] is not None:
        ws.cell(row=r, column=1, value="주요 일정").font = Font(bold=True)
        head(ws, r + 1, HEADS["milestones"])
        r += 2
        for m in rep["milestones"]:
            for c, v in enumerate(m, 1):
                ws.cell(row=r, column=c, value=v).border = border
            r += 1
        r += 1
    if rep["excluded"]:
        ws.cell(row=r, column=1, value="조회 권한이 없어 제외: " + ", ".join(rep["excluded"])).font = Font(color="EA580C")
    for col, w in zip("ABCDEF", (16, 16, 14, 16, 14, 14)):
        ws.column_dimensions[col].width = w

    for key, title in (("hulls", "호선"), ("plans", "공정"), ("drawings", "도면")):
        if key not in rep["rows"]:
            continue
        sh = wb.create_sheet(title)
        heads = HEADS[key]
        head(sh, 1, heads)
        for i, row in enumerate(rep["rows"][key], 2):
            delay = bool(row[-1]) if key == "plans" else False
            for c, v in enumerate(row[:-1] if key == "plans" else row, 1):
                cell = sh.cell(row=i, column=c, value=v)
                cell.border = border
                if delay and c == 7:
                    cell.font = red
        for c, h in enumerate(heads, 1):
            vals = [len(str(h))] + [len(str(rw[c - 1])) for rw in rep["rows"][key]]
            sh.column_dimensions[sh.cell(row=1, column=c).column_letter].width = min(max(vals) * 1.6 + 2, 50)
        sh.freeze_panes = "A2"
        sh.auto_filter.ref = sh.dimensions
    wb.save(path)
