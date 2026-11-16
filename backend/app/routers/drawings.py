import sqlite3

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from .. import config
from ..db import get_db
from ..deps import VIEW, WRITE, require
from ..schemas import ApprovalRequestIn, DrawingIn, DrawingLinkIn, RevisionIn
from ..services import drawings as svc

router = APIRouter(prefix="/api/drawings", tags=["drawings"])
M = "M31"


@router.get("")
def list_drawings(hull_no: str | None = None, discipline: str | None = None, status: str | None = None,
                  q: str | None = None, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.list_drawings(conn, hull_no, discipline, status, q)


@router.post("", status_code=201)
def create_drawing(body: DrawingIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_drawing(conn, body.model_dump(), user)


@router.get("/{drawing_id}")
def get_drawing(drawing_id: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.get_drawing(conn, drawing_id)


@router.patch("/{drawing_id}")
def update_drawing(drawing_id: int, body: DrawingIn, user=Depends(require(M, WRITE)),
                   conn: sqlite3.Connection = Depends(get_db)):
    return svc.update_drawing(conn, drawing_id, body.model_dump(), body.model_fields_set, user)


@router.delete("/{drawing_id}", status_code=204)
def delete_drawing(drawing_id: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_drawing(conn, drawing_id)
    return Response(status_code=204)


@router.get("/{drawing_id}/revisions")
def revisions(drawing_id: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.revisions(conn, drawing_id)


@router.post("/{drawing_id}/revisions", status_code=201)
def create_revision(drawing_id: int, body: RevisionIn, user=Depends(require(M, WRITE)),
                    conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_revision(conn, drawing_id, body.change_desc, user)


@router.post("/{drawing_id}/revisions/{rev_no}/pdf")
async def upload_pdf(drawing_id: int, rev_no: int, request: Request, filename: str | None = None,
                     user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    """권한 검사(의존성) → 대상·형식 검사 → 본문 스트리밍(30MiB 초과 시 중단) → %PDF- 확인 → 저장."""
    name, file_id = svc.check_upload_target(conn, drawing_id, rev_no, filename, request.headers.get("content-type"),
                                            request.headers.get("content-length"))
    d = config.file_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{file_id}.part"
    size = 0
    try:
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > svc.MAX_PDF:
                    raise svc.too_large()
                f.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return svc.save_upload(conn, drawing_id, rev_no, name, file_id, tmp)


@router.get("/{drawing_id}/revisions/{rev_no}/pdf")
def get_pdf(drawing_id: int, rev_no: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    path, name = svc.pdf_file(conn, drawing_id, rev_no)
    return FileResponse(path, media_type="application/pdf", filename=name, content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.delete("/{drawing_id}/revisions/{rev_no}/pdf", status_code=204)
def delete_pdf(drawing_id: int, rev_no: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_pdf(conn, drawing_id, rev_no)
    return Response(status_code=204)


@router.post("/{drawing_id}/revisions/{rev_no}/request-approval")
def request_approval(drawing_id: int, rev_no: int, body: ApprovalRequestIn, user=Depends(require(M, WRITE)),
                     conn: sqlite3.Connection = Depends(get_db)):
    return svc.request_approval(conn, drawing_id, rev_no, body.reviewer_emp_no, body.approver_emp_no)


@router.post("/{drawing_id}/revisions/{rev_no}/issue")
def issue(drawing_id: int, rev_no: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.issue(conn, drawing_id, rev_no)


@router.get("/{drawing_id}/plans")
def linked_plans(drawing_id: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.linked_plans(conn, drawing_id)


@router.post("/{drawing_id}/plans", status_code=201)
def link_plan(drawing_id: int, body: DrawingLinkIn, user=Depends(require(M, WRITE)),
              conn: sqlite3.Connection = Depends(get_db)):
    return svc.link_plan(conn, drawing_id, body.plan_id, body.required)


@router.delete("/{drawing_id}/plans/{plan_id}", status_code=204)
def unlink_plan(drawing_id: int, plan_id: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    svc.unlink_plan(conn, drawing_id, plan_id)
    return Response(status_code=204)
