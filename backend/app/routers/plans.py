import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import VIEW, WRITE, current_user, require
from ..schemas import PlanIn, PlanLinkIn, PredecessorsIn, ScheduleIn
from ..services import plans as svc

router = APIRouter(prefix="/api", tags=["plans"])
M = "M21"


@router.get("/procs")
def procs(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return svc.procs(conn)


@router.get("/plan-hulls")
def plan_hulls(user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.plan_hulls(conn)


@router.get("/hulls/{hull_no}/plans")
def hull_plans(hull_no: str, block_id: int | None = None, user=Depends(require(M, VIEW)),
               conn: sqlite3.Connection = Depends(get_db)):
    return svc.hull_plans(conn, hull_no, block_id)


@router.post("/hulls/{hull_no}/plans", status_code=201)
def create_plan(hull_no: str, body: PlanIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_plan(conn, hull_no, body.model_dump(), user)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.get_plan(conn, plan_id)


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: int, body: PlanIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.update_plan(conn, plan_id, body.model_dump(), body.model_fields_set)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_plan(conn, plan_id)
    return Response(status_code=204)


@router.put("/plans/{plan_id}/predecessors")
def set_predecessors(plan_id: int, body: PredecessorsIn, user=Depends(require(M, WRITE)),
                     conn: sqlite3.Connection = Depends(get_db)):
    return svc.set_predecessors(conn, plan_id, body.pred_plan_ids, body.confirm_late_preds)


@router.patch("/plans/{plan_id}/schedule")
def schedule(plan_id: int, body: ScheduleIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.schedule(conn, plan_id, body.plan_start_dt, body.plan_end_dt, body.confirm_late_preds)


@router.get("/plans/{plan_id}/drawings")
def plan_drawings(plan_id: int, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.plan_drawings(conn, plan_id)


@router.post("/plans/{plan_id}/drawings", status_code=201)
def link_drawing(plan_id: int, body: PlanLinkIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.link_drawing(conn, plan_id, body.drawing_id, body.required)


@router.delete("/plans/{plan_id}/drawings/{drawing_id}", status_code=204)
def unlink_drawing(plan_id: int, drawing_id: int, user=Depends(require(M, WRITE)),
                   conn: sqlite3.Connection = Depends(get_db)):
    svc.unlink_drawing(conn, plan_id, drawing_id)
    return Response(status_code=204)
