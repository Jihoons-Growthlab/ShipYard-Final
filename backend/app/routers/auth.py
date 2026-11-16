import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from ..db import get_db
from ..deps import bearer, current_user
from ..schemas import DemoRoleIn, LoginIn, OtpIn, RegisterIn
from ..services import auth as svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login")
def login(body: LoginIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return svc.login(conn, body.emp_no, body.password, _ip(request))


@router.post("/otp/verify")
def otp_verify(body: OtpIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return svc.verify_otp(conn, bearer(request), body.code, _ip(request))


@router.post("/register", status_code=201)
def register(body: RegisterIn, conn: sqlite3.Connection = Depends(get_db)):
    return svc.register(conn, body.model_dump())


@router.post("/logout", status_code=204)
def logout(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    svc.logout(conn, user["lid"])
    return Response(status_code=204)


@router.get("/me")
def me(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return svc.me(conn, user)


@router.post("/demo-role")
def demo_role(body: DemoRoleIn, request: Request, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return svc.switch_demo_role(conn, user, body.role, _ip(request))
