"""오류 본문 {"code","message","details"}와 예외 처리기."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def validation(field: str, message: str, code: str = "VALIDATION_ERROR") -> AppError:
    return AppError(400, code, message, {"field": field})


def not_found(code: str, message: str) -> AppError:
    return AppError(404, code, message)


def duplicate(message: str, field: str | None = None) -> AppError:
    return AppError(409, "DUPLICATE", message, {"field": field} if field else {})


UNAUTHORIZED_MSG = "세션이 만료되었거나 유효하지 않습니다."


def unauthorized() -> AppError:
    return AppError(401, "UNAUTHORIZED", UNAUTHORIZED_MSG)


def body(code: str, message: str, details: dict | None = None) -> dict:
    return {"code": code, "message": message, "details": details or {}}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        return JSONResponse(body(e.code, e.message, e.details), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        errs = e.errors()
        loc = [str(x) for x in (errs[0].get("loc", ()) if errs else ()) if x not in ("body", "query", "path")]
        return JSONResponse(
            body("VALIDATION_ERROR", "요청 형식이 올바르지 않습니다.", {"field": ".".join(loc) or None}),
            status_code=400,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        if e.status_code == 404:
            return JSONResponse(body("NOT_FOUND", "요청한 경로를 찾을 수 없습니다."), status_code=404)
        if e.status_code == 405:
            return JSONResponse(body("METHOD_NOT_ALLOWED", "허용되지 않는 요청 방식입니다."), status_code=405)
        return JSONResponse(body("HTTP_ERROR", str(e.detail)), status_code=e.status_code)
