import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import VIEW, WRITE, require
from ..schemas import BlockIn, HullIn, MilestonesIn
from ..services import hulls as svc

router = APIRouter(prefix="/api", tags=["hulls"])
M = "M11"


@router.get("/hulls")
def list_hulls(status: str | None = None, ship_type: str | None = None, q: str | None = None,
               user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.list_hulls(conn, status, ship_type, q)


@router.post("/hulls", status_code=201)
def create_hull(body: HullIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_hull(conn, body.model_dump(), body.model_fields_set, user)


@router.get("/hulls/{hull_no}")
def get_hull(hull_no: str, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.get_hull(conn, hull_no)


@router.patch("/hulls/{hull_no}")
def update_hull(hull_no: str, body: HullIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.update_hull(conn, hull_no, body.model_dump(), body.model_fields_set, user)


@router.delete("/hulls/{hull_no}", status_code=204)
def delete_hull(hull_no: str, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_hull(conn, hull_no)
    return Response(status_code=204)


@router.get("/hulls/{hull_no}/milestones")
def milestones(hull_no: str, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.milestones(conn, hull_no)


@router.put("/hulls/{hull_no}/milestones")
def save_milestones(hull_no: str, body: MilestonesIn, user=Depends(require(M, WRITE)),
                    conn: sqlite3.Connection = Depends(get_db)):
    return svc.save_milestones(conn, hull_no, [i.model_dump() for i in body.items])


@router.get("/hulls/{hull_no}/blocks")
def blocks(hull_no: str, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.blocks(conn, hull_no)


@router.post("/hulls/{hull_no}/blocks", status_code=201)
def create_block(hull_no: str, body: BlockIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_block(conn, hull_no, body.model_dump())


@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(block_id: int, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_block(conn, block_id)
    return Response(status_code=204)


@router.get("/hulls/{hull_no}/summary")
def summary(hull_no: str, user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.summary(conn, hull_no)
