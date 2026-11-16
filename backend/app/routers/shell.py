import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import current_user
from ..schemas import MenuAccessIn
from ..services import shell as svc
from ..services.weather import get_weather

router = APIRouter(prefix="/api", tags=["shell"])


@router.get("/me/menu")
def my_menu(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return svc.visible_menus(conn, user["emp_no"])


@router.post("/me/menu-access", status_code=204)
def menu_access(body: MenuAccessIn, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    svc.record_menu_access(conn, user, body.menu_id)
    return Response(status_code=204)


@router.get("/weather")
def weather(region: str | None = None, user: dict = Depends(current_user)):
    return get_weather(region)


@router.get("/codes")
def codes(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return svc.codes(conn)


@router.get("/users/options")
def user_options(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return svc.user_options(conn)
