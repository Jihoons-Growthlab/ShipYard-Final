import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import ADMIN, require
from ..schemas import ApproveIn, UserIn, UserMenusIn
from ..services import users as svc

router = APIRouter(prefix="/api", tags=["users"])
ADM = require("M91", ADMIN)


@router.get("/users")
def list_users(status: str | None = None, q: str | None = None, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.list_users(conn, status, q)


@router.post("/users", status_code=201)
def create_user(body: UserIn, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_user(conn, body.model_dump())


@router.get("/auth-groups")
def auth_groups(user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.auth_groups(conn)


@router.get("/users/{emp_no}")
def get_user(emp_no: str, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.get_user(conn, emp_no)


@router.patch("/users/{emp_no}")
def update_user(emp_no: str, body: UserIn, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.update_user(conn, emp_no, body.model_dump(), body.model_fields_set)


@router.delete("/users/{emp_no}", status_code=204)
def delete_user(emp_no: str, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_user(conn, emp_no, user)
    return Response(status_code=204)


@router.post("/users/{emp_no}/approve")
def approve(emp_no: str, body: ApproveIn, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.approve(conn, emp_no, body.groups)


@router.post("/users/{emp_no}/reject")
def reject(emp_no: str, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.reject(conn, emp_no)


@router.get("/users/{emp_no}/menus")
def user_menus(emp_no: str, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.user_menus(conn, emp_no)


@router.put("/users/{emp_no}/menus")
def set_user_menus(emp_no: str, body: UserMenusIn, user=Depends(ADM), conn: sqlite3.Connection = Depends(get_db)):
    return svc.set_user_menus(conn, emp_no, [m.model_dump() for m in body.menus], user)
