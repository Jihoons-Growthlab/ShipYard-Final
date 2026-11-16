import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import VIEW, WRITE, require
from ..schemas import DecisionIn
from ..services import approvals as svc

router = APIRouter(prefix="/api/approvals", tags=["approvals"])
M = "M33"


@router.get("/inbox")
def inbox(user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.inbox(conn, user)


@router.post("/{approval_id}/decision")
def decision(approval_id: int, body: DecisionIn, user=Depends(require(M, WRITE)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.decide(conn, approval_id, body.result, body.comment, user)


@router.get("/history")
def history(user=Depends(require(M, VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.history(conn)
