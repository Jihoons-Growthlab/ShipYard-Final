"""F13 챗봇·F14 보고서 API. 데이터 조회·접수·보고서 생성은 모두 MCP 도구(services.chat.call_tool)를 거친다."""
import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..db import get_db
from ..deps import current_user
from ..errors import AppError
from ..permissions import menu_level
from ..schemas import ChatIn, FeedbackIn, ReportIn
from ..services import chat as svc
from ..services import reports

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
def chat(body: ChatIn, user=Depends(current_user)):
    return svc.answer(user["emp_no"], [m.model_dump() for m in body.messages])


@router.post("/feedback")
def feedback(body: FeedbackIn, user=Depends(current_user)):
    return svc.submit_feedback(user["emp_no"], body.kind, body.content, body.request_id)


@router.get("/report/options")
def report_options(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    hulls = []
    if menu_level(conn, user["emp_no"], "M11") >= 1:
        hulls = [{"hull_no": r[0], "hull_nm": r[1]} for r in conn.execute(
            "SELECT HullNo, HullNm FROM TB_MST_Hull WHERE UseYN = 1 ORDER BY HullNo")]
    return {"hulls": hulls, "formats": [{"code": c, "name": n} for c, n in reports.FORMATS.items()]}


@router.post("/report", status_code=201)
def create_report(body: ReportIn, user=Depends(current_user)):
    if body.format not in reports.FORMATS:
        raise AppError(422, "REPORT_FORMAT", "보고서 형식은 PDF 또는 Excel만 선택할 수 있습니다.", {"field": "format"})
    args = {"format": body.format} | ({"hull_no": body.hull_no.strip()} if body.hull_no and body.hull_no.strip() else {})
    out = svc.call_tool(user["emp_no"], "build_report", args)
    if "error" in out:
        raise AppError(int(out.get("status") or 400), "REPORT_ERROR", out["error"])
    return out


@router.get("/reports/{report_id}")
def download_report(report_id: str, format: str | None = None, user=Depends(current_user)):
    path, filename, mime = reports.find(user["emp_no"], report_id, format)
    return FileResponse(path, media_type=mime, filename=filename)
