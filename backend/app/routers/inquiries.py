import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import WRITE, require
from ..schemas import InquiryIn
from ..services import inquiries as svc

router = APIRouter(prefix="/api/inquiries", tags=["inquiries"])
W = require(svc.MENU, WRITE)


@router.get("")
def list_inquiries(status: str | None = None, q: str | None = None, mine: bool = False, user=Depends(W),
                   conn: sqlite3.Connection = Depends(get_db)):
    return svc.list_inquiries(conn, user, status, q, mine)


@router.post("", status_code=201)
def create_inquiry(body: InquiryIn, user=Depends(W), conn: sqlite3.Connection = Depends(get_db)):
    return svc.create_inquiry(conn, user["emp_no"], body.category, body.title, body.content)


@router.get("/{inquiry_id}")
def get_inquiry(inquiry_id: int, user=Depends(W), conn: sqlite3.Connection = Depends(get_db)):
    return svc.get_inquiry(conn, inquiry_id, user)


@router.patch("/{inquiry_id}")
def update_inquiry(inquiry_id: int, body: InquiryIn, user=Depends(W), conn: sqlite3.Connection = Depends(get_db)):
    return svc.update_inquiry(conn, inquiry_id, body.model_dump(), body.model_fields_set, user)


@router.delete("/{inquiry_id}", status_code=204)
def delete_inquiry(inquiry_id: int, user=Depends(W), conn: sqlite3.Connection = Depends(get_db)):
    svc.delete_inquiry(conn, inquiry_id, user)
    return Response(status_code=204)
