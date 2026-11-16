import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import VIEW, WRITE, require
from ..schemas import ProgressIn
from ..services import progress as svc

router = APIRouter(prefix="/api", tags=["progress"])
M = "M22"


@router.get("/progress-hulls")
def progress_hulls(user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.progress_hulls(conn)


@router.get("/hulls/{hull_no}/progress-targets")
def targets(hull_no: str, include_done: bool = False, user=Depends(require(M, VIEW)),
            conn: sqlite3.Connection = Depends(get_db)):
    return svc.targets(conn, hull_no, include_done)


@router.get("/plans/{plan_id}/progress")
def plan_progress(plan_id: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.plan_progress(conn, plan_id)


@router.put("/plans/{plan_id}/progress/{work_dt}")
def save_progress(plan_id: int, work_dt: str, body: ProgressIn, user=Depends(require(M, WRITE)),
                  conn: sqlite3.Connection = Depends(get_db)):
    return svc.save_progress(conn, plan_id, work_dt, body.model_dump())


@router.delete("/progress/{progress_id}")
def delete_progress(progress_id: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.delete_progress(conn, progress_id)
