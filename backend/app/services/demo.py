"""F16 시연 모드와 예시 데이터. 모두 명시적 옵션(init-db --demo-pdfs / --demo-usage, scripts/demo.sh)으로만 동작한다."""
import datetime as dt
import random
import secrets
import sqlite3
import sys

from .. import db, storage
from ..security import hash_password
from ..util import utc_now
from .auth import DEMO_ROLES
from .usage import KST

# --- 예시 도면 PDF (PDF 1.4 직접 작성, 기본 Type1 글꼴 → ASCII만)
W, H = 1191, 842
DISC_EN = {"HULL": "HULL STRUCTURE", "PIPE": "PIPING ARRANGEMENT", "ELEC": "ELECTRICAL WIRING",
           "MACH": "MACHINERY ARRANGEMENT", "OUTFIT": "OUTFITTING ARRANGEMENT"}
STAMPS = {"DRAFT": "DRAFT", "REVIEW": "FOR REVIEW", "APPROVED": "APPROVED - NOT ISSUED", "OBSOLETE": "SUPERSEDED"}


def _ascii(s) -> str:
    t = str(s if s is not None else "").encode("ascii", "ignore").decode()
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class _Canvas:
    def __init__(self):
        self.ops: list[str] = []

    def add(self, *ops: str):
        self.ops.extend(ops)

    def text(self, x, y, s, size=10, bold=False):
        self.add(f"BT /{'F2' if bold else 'F1'} {size} Tf {x:.1f} {y:.1f} Td ({_ascii(s)}) Tj ET")

    def rect(self, x, y, w, h, fill=False):
        self.add(f"{x:.1f} {y:.1f} {w:.1f} {h:.1f} re {'B' if fill else 'S'}")

    def line(self, *pts):
        self.add(f"{pts[0][0]:.1f} {pts[0][1]:.1f} m " + " ".join(f"{x:.1f} {y:.1f} l" for x, y in pts[1:]) + " S")

    def poly(self, pts, close=True):
        self.add(f"{pts[0][0]:.1f} {pts[0][1]:.1f} m " + " ".join(f"{x:.1f} {y:.1f} l" for x, y in pts[1:])
                 + (" h S" if close else " S"))

    def circle(self, cx, cy, r):
        k = 0.5523 * r
        self.add(f"{cx + r:.1f} {cy:.1f} m {cx + r:.1f} {cy + k:.1f} {cx + k:.1f} {cy + r:.1f} {cx:.1f} {cy + r:.1f} c"
                 f" {cx - k:.1f} {cy + r:.1f} {cx - r:.1f} {cy + k:.1f} {cx - r:.1f} {cy:.1f} c"
                 f" {cx - r:.1f} {cy - k:.1f} {cx - k:.1f} {cy - r:.1f} {cx:.1f} {cy - r:.1f} c"
                 f" {cx + k:.1f} {cy - r:.1f} {cx + r:.1f} {cy - k:.1f} {cx + r:.1f} {cy:.1f} c S")

    def stroke(self, r, g, b, width=1.0, dash: str = "[] 0"):
        self.add(f"{r} {g} {b} RG {r} {g} {b} rg {width} w {dash} d")


def _figure(c: _Canvas, disc: str, block_cd: str | None, seed: int) -> None:
    rnd = random.Random(seed)
    c.stroke(0, 0, 0, 1.2)
    if disc == "HULL":
        c.text(60, 770, "PROFILE", 11, True)
        c.poly([(60, 560), (600, 560), (660, 600), (690, 700), (60, 700), (50, 640)])
        c.line((60, 690), (690, 690))
        c.stroke(0.4, 0.4, 0.4, 0.5, "[4 3] 0")
        for x in range(80, 660, 30):
            c.line((x, 562), (x, 688))
        c.stroke(0.85, 0.1, 0.1, 2)
        idx = int(block_cd) % 15 if block_cd and block_cd.isdigit() else rnd.randrange(15)
        if block_cd:
            bx = 80 + idx * 36
            c.rect(bx, 580, 50, 90)
            c.text(bx - 4, 676, "THIS BLOCK", 9, True)
        c.stroke(0, 0, 0, 1.2)
        c.text(60, 500, "PLAN VIEW", 11, True)
        c.poly([(60, 300), (600, 300), (690, 380), (600, 460), (60, 460)])
        c.stroke(0.4, 0.4, 0.4, 0.5, "[8 3 2 3] 0")
        c.line((50, 380), (700, 380))
    elif disc == "PIPE":
        c.text(60, 770, "PIPING DIAGRAM", 11, True)
        for y in (650, 500, 350):
            c.line((80, y), (660, y))
            for x in (200, 380, 540):
                c.line((x, y), (x, y - 70))
                c.poly([(x - 10, y - 30), (x + 10, y - 50), (x + 10, y - 30), (x - 10, y - 50)])  # 나비 밸브
            c.circle(100, y - 40, 18)
            c.text(84, y - 72, "PUMP", 8)
    elif disc == "ELEC":
        c.text(60, 770, "WIRING DIAGRAM", 11, True)
        for i, x in enumerate((90, 300, 510)):
            c.rect(x, 640, 120, 90)
            c.text(x + 20, 690, f"PANEL {i + 1}", 10, True)
            for j in range(3):
                lx = x + 20 + j * 40
                c.line((lx, 640), (lx, 420 - j * 30))
                c.circle(lx, 405 - j * 30, 12)
        c.text(90, 300, "LOADS", 9)
    else:
        c.text(60, 770, "ARRANGEMENT", 11, True)
        for i in range(6):
            x, y = 80 + (i % 3) * 210, 560 - (i // 3) * 220
            c.rect(x, y, 170, 150)
            c.text(x + 10, y + 130, f"EQUIPMENT {i + 1}", 10, True)
    c.stroke(0, 0, 0, 1)


def render_pdf(d: dict, rev: dict, history: list[dict]) -> bytes:
    """d: 도면(DrawingNo, HullNo, Discipline, BlockCd, DesignerEmpNo), rev: 대상 리비전, history: RevNo 내림차순(≤5)."""
    c = _Canvas()
    c.stroke(0, 0, 0, 2)
    c.rect(20, 20, W - 40, H - 40)
    c.stroke(0, 0, 0, 0.8)
    c.rect(30, 30, W - 60, H - 60)
    # 표제란 400x160
    tx, ty, tw, th = W - 30 - 400, 30, 400, 160
    c.rect(tx, ty, tw, th)
    disc_en = DISC_EN.get(d["Discipline"] or "", "GENERAL ARRANGEMENT")
    rows = [("PROJECT", f"HULL {d['HullNo']}"), ("DRAWING TITLE", f"{disc_en} - BLOCK {d['BlockCd'] or 'GENERAL'}"),
            ("DRAWING NO", d["DrawingNo"]), ("REV", f"{rev['RevNo']}   STATUS {rev['RevStatus']}"),
            ("DESIGNED BY", d["DesignerEmpNo"] or "-"), ("DATE", rev["IssueDt"] or rev["CreateDt"] or "-")]
    rh = th / len(rows)
    for i, (k, v) in enumerate(rows):
        y = ty + th - (i + 1) * rh
        if i:
            c.line((tx, y + rh), (tx + tw, y + rh))
        c.text(tx + 8, y + 9, k, 8)
        c.text(tx + 110, y + 8, v, 11, True)
    c.line((tx + 100, ty), (tx + 100, ty + th))
    c.text(45, 40, "SWP SHIPYARD | SAMPLE DRAWING FOR DEMONSTRATION - NOT FOR CONSTRUCTION", 9, True)
    # 리비전 표(오른쪽 위)
    rx, top = tx, H - 30
    c.rect(rx, top - 18 * (len(history) + 1), 400, 18 * (len(history) + 1))
    for j, (label, off) in enumerate((("REV", 6), ("DATE", 46), ("STATUS", 136), ("DESCRIPTION", 216))):
        c.text(rx + off, top - 13, label, 8, True)
    for i, h in enumerate(history):
        y = top - 18 * (i + 2)
        c.line((rx, y + 18), (rx + 400, y + 18))
        desc = h["ChangeDesc"] if h["ChangeDesc"] and h["ChangeDesc"].isascii() else (
            "INITIAL ISSUE" if h["RevNo"] == 0 else f"REVISION {h['RevNo']}")
        for v, off in ((h["RevNo"], 6), (h["IssueDt"] or h["CreateDt"] or "-", 46), (h["RevStatus"], 136), (desc[:30], 216)):
            c.text(rx + off, y + 5, v, 8)
    _figure(c, d["Discipline"] or "", d["BlockCd"], hash((d["DrawingNo"], rev["RevNo"])) & 0xFFFF)
    if rev["RevStatus"] in STAMPS:
        c.stroke(0.85, 0.1, 0.1, 3)
        c.add("q 0.94 0.34 -0.34 0.94 330 560 cm", "0 0 330 60 re S",
              f"BT /F2 28 Tf 0.85 0.1 0.1 rg 14 18 Td ({_ascii(STAMPS[rev['RevStatus']])}) Tj ET", "Q")
    stream = "\n".join(c.ops).encode("ascii")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        f"<< /Title ({_ascii(d['DrawingNo'])} Rev{rev['RevNo']}) /Producer (SWP Shipyard demo) >>".encode(),
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {len(objs)} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def load_demo_pdfs(conn: sqlite3.Connection) -> int:
    """파일 없는 모든 리비전에 예시 PDF를 붙인다(이미 있으면 건너뜀). 파일은 커밋 전에 쓰고 실패하면 지운다."""
    targets = conn.execute(
        "SELECT r.*, d.DrawingNo, d.HullNo, d.Discipline, d.DesignerEmpNo, b.BlockCd FROM TB_DWG_Revision r"
        " JOIN TB_DWG_Drawing d ON d.DrawingId = r.DrawingId LEFT JOIN TB_MST_Block b ON b.BlockId = d.BlockId"
        " WHERE r.FileId IS NULL ORDER BY r.DrawingId, r.RevNo").fetchall()
    if not targets:
        return 0
    storage.file_path("x").parent.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        with db.tx(conn):
            for t in targets:
                hist = conn.execute("SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? AND RevNo <= ? ORDER BY RevNo DESC LIMIT 5",
                                    (t["DrawingId"], t["RevNo"])).fetchall()
                fid = f"{secrets.token_hex(16)}.pdf"
                p = storage.file_path(fid)
                p.write_bytes(render_pdf(dict(t), dict(t), [dict(h) for h in hist]))
                written.append(fid)
                conn.execute("UPDATE TB_DWG_Revision SET FileId = ?, FileNm = ? WHERE DrawingId = ? AND RevNo = ?",
                             (fid, f"{t['DrawingNo']}_Rev{t['RevNo']}.pdf", t["DrawingId"], t["RevNo"]))
    except BaseException:
        storage.remove_files(written)
        raise
    return len(written)


# --- 예시 사용 로그·건의 글
DAILY = {"park.pm": 60, "han.wk": 45, "lee.dwg": 50, "choi.qa": 18, "admin": 14}
COMMON = [("POST", "/api/auth/login", 3), ("GET", "/api/me/menu", 3), ("GET", "/api/codes", 3), ("GET", "/api/weather", 3)]
PATHS = {
    "park.pm": [("GET", "/api/hulls/{hull_no}/plans", 8), ("PATCH", "/api/plans/{plan_id}/schedule", 5),
                ("GET", "/api/plan-hulls", 3), ("PATCH", "/api/plans/{plan_id}", 3), ("GET", "/api/plans/{plan_id}", 3),
                ("PUT", "/api/plans/{plan_id}/predecessors", 2), ("GET", "/api/plans/{plan_id}/drawings", 2),
                ("GET", "/api/dashboard/summary", 2), ("GET", "/api/hulls", 2)],
    "han.wk": [("GET", "/api/progress-hulls", 4), ("GET", "/api/hulls/{hull_no}/progress-targets", 7),
               ("GET", "/api/plans/{plan_id}/progress", 5), ("PUT", "/api/plans/{plan_id}/progress/{work_dt}", 7),
               ("DELETE", "/api/progress/{progress_id}", 1), ("GET", "/api/dashboard/summary", 1)],
    "lee.dwg": [("GET", "/api/drawings", 6), ("GET", "/api/drawings/{drawing_id}", 5),
                ("GET", "/api/drawings/{drawing_id}/revisions/{rev_no}/pdf", 5),
                ("POST", "/api/drawings/{drawing_id}/revisions/{rev_no}/pdf", 2), ("POST", "/api/drawings/{drawing_id}/revisions", 1),
                ("POST", "/api/drawings/{drawing_id}/revisions/{rev_no}/request-approval", 1),
                ("GET", "/api/approvals/inbox", 3), ("POST", "/api/approvals/{approval_id}/decision", 2),
                ("POST", "/api/drawings/{drawing_id}/revisions/{rev_no}/issue", 1)],
    "choi.qa": [("GET", "/api/dashboard/summary", 7), ("GET", "/api/hulls", 4), ("GET", "/api/hulls/{hull_no}", 3),
                ("GET", "/api/hulls/{hull_no}/summary", 2), ("GET", "/api/hulls/{hull_no}/blocks", 1), ("GET", "/api/drawings", 1)],
    "admin": [("GET", "/api/users", 6), ("PATCH", "/api/users/{emp_no}", 2), ("GET", "/api/users/{emp_no}/menus", 2),
              ("PUT", "/api/users/{emp_no}/menus", 1), ("POST", "/api/users/{emp_no}/approve", 1), ("GET", "/api/inquiries", 4),
              ("PATCH", "/api/inquiries/{inquiry_id}", 2), ("GET", "/api/dashboard/summary", 2)],
}
ERROR_CODES = (400, 403, 404, 409, 500)
DEMO_INQUIRIES = [
    ("park.pm", "FEATURE", "공정 계획 엑셀 내보내기 요청",
     "간트 화면의 공정 목록을 엑셀로 내려받을 수 있으면 주간 회의 자료 만들기가 편할 것 같습니다.",
     "IN_PROGRESS", "검토 중입니다. 다음 배포에 포함할 예정입니다."),
    ("lee.dwg", "BUG", "도면 PDF 업로드 시 파일명이 깨집니다", "한글 파일명으로 업로드하면 목록에서 파일명이 ??? 로 보입니다.",
     "OPEN", None),
    ("han.wk", "QUESTION", "실적 입력 마감 시간이 있나요?", "전날 실적을 다음날 오전에 입력해도 되는지 궁금합니다.",
     "DONE", "마감 시간은 없습니다. 다만 주간 보고 전(금 17시)까지 입력해 주세요."),
    ("choi.qa", "ETC", "대시보드 글자 크기 조정", "회의실 화면에서 대시보드 숫자가 작게 보입니다.",
     "REJECTED", "브라우저 확대(Ctrl +)로 조정해 주세요. 별도 설정은 제공하지 않습니다."),
]
FMT = "%Y-%m-%d %H:%M:%S"


def _demo_logs(now: dt.datetime, users: set[str]) -> list[tuple]:
    rnd = random.Random(7)
    today = (now + KST).date()
    rows = []
    for back in range(29, -1, -1):
        day = today - dt.timedelta(days=back)
        for emp, mean in DAILY.items():
            if emp not in users:
                continue
            if day.weekday() >= 5 and rnd.random() < 0.85:
                continue
            m = mean * (1.1 if back < 7 else 1.0)
            n = max(0, round(rnd.gauss(m, m * 0.25)))
            choices = PATHS[emp] + COMMON
            weights = [w for _, _, w in choices]
            for _ in range(n):
                method, path, _w = rnd.choices(choices, weights)[0]
                hour = min(19, max(7, round(rnd.gauss(13, 3))))
                local = dt.datetime.combine(day, dt.time(hour, rnd.randrange(60), rnd.randrange(60)))
                utc = local - KST
                if utc > now:
                    continue
                status = rnd.choice(ERROR_CODES) if rnd.random() < 0.03 else 200
                ms = int(rnd.lognormvariate(3.2, 0.5) if method == "GET" else rnd.lognormvariate(3.7, 0.5))
                rows.append((emp, method, path, status, ms, utc.strftime(FMT)))
    rows.sort(key=lambda r: r[5])
    return rows


def load_demo_usage(conn: sqlite3.Connection, now: dt.datetime | None = None) -> int:
    """예시 로그(없을 때만, DemoYN=1)와 예시 건의 글 4개(제목이 없을 때만)를 넣는다. 넣은 로그 수를 돌려준다."""
    now = (now or dt.datetime.now(dt.timezone.utc)).replace(tzinfo=None, microsecond=0)
    users = {r[0] for r in conn.execute("SELECT emp_no FROM users")}
    n = 0
    with db.tx(conn):
        if not conn.execute("SELECT 1 FROM TB_SYS_LogApi WHERE DemoYN = 1 LIMIT 1").fetchone():
            rows = _demo_logs(now, users)
            conn.executemany("INSERT INTO TB_SYS_LogApi(EmpNo, Method, Path, Status, DurationMs, CallDt, DemoYN)"
                             " VALUES (?, ?, ?, ?, ?, ?, 1)", rows)
            n = len(rows)
        for i, (emp, cat, title, content, status, answer) in enumerate(DEMO_INQUIRIES):
            if conn.execute("SELECT 1 FROM TB_SYS_Inquiry WHERE Title = ?", (title,)).fetchone():
                continue
            created = now - dt.timedelta(days=6 - i)
            ans_dt = (created + dt.timedelta(hours=5)).strftime(FMT) if answer else None
            conn.execute("INSERT INTO TB_SYS_Inquiry(Category, Title, Content, Status, CreateUserId, CreateDt, Answer, AnswerDt,"
                         " AnswerUserId) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (cat, title, content, status, emp if emp in users else None, created.strftime(FMT), answer, ans_dt,
                          "admin" if answer and "admin" in users else None))
    return n


# --- 데모 역할 전환 (scripts/demo.sh)
DEMO_PASSWORD = "Shipyard-Demo-26!"


def prepare_demo_accounts(conn: sqlite3.Connection) -> None:
    """모든 회원 disabled, admin·han.wk만 approved·OTP 끔·데모 비밀번호."""
    pw = hash_password(DEMO_PASSWORD)
    with db.tx(conn):
        conn.execute("UPDATE users SET status = 'disabled'")
        conn.executemany("UPDATE users SET status = 'approved', totp_enabled = 0, password_hash = ? WHERE emp_no = ?",
                         [(pw, e) for e in DEMO_ROLES])


if __name__ == "__main__" and sys.argv[1:] == ["prepare"]:
    _c = db.connect()
    try:
        prepare_demo_accounts(_c)
        print(f"[demo] accounts prepared at {utc_now()}")
    finally:
        _c.close()
