import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import VIEW, require
from ..services import dashboard as svc

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(user=Depends(require("M00", VIEW)), conn: sqlite3.Connection = Depends(get_db)):
    return svc.summary(conn)
