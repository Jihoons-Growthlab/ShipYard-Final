"""API 호출 기록 ASGI 미들웨어(F11). 라우트 템플릿은 호출 뒤 scope["route"].path, 사용자는 current_user가 state에 넣는다."""
import time

from starlette.concurrency import run_in_threadpool

from .services import usage
from .util import utc_now


class UsageLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not usage.should_log(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        scope.setdefault("state", {})
        status = {"code": 500}
        started = time.perf_counter()
        call_dt = utc_now()

        async def _send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            route = scope.get("route")
            path = getattr(route, "path", None) or scope.get("path", "")
            if usage.should_log(path):
                try:
                    await run_in_threadpool(usage.record, scope["state"].get("emp_no"), scope.get("method", ""), path,
                                            status["code"], int((time.perf_counter() - started) * 1000), call_dt)
                except Exception:  # 기록 실패는 응답에 영향 없음
                    pass
