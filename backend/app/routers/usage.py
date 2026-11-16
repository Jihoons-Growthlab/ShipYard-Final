import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import ADMIN, require
from ..services import usage as svc

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
def summary(days: str = "7", emp_no: str | None = None, user=Depends(require("M92", ADMIN)),
            conn: sqlite3.Connection = Depends(get_db)):
    return svc.summary(conn, int(days) if days.isdigit() else None, emp_no)
