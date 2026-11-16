from fastapi import FastAPI

from . import errors
from .usage_log import UsageLogMiddleware
from .routers import approvals, auth, chat, dashboard, drawings, hulls, inquiries, plans, progress, shell, usage, users

app = FastAPI(title="SWP Shipyard", version="4.0")
errors.install(app)

app.include_router(auth.router)
app.include_router(shell.router)
app.include_router(hulls.router)
app.include_router(plans.router)
app.include_router(progress.router)
app.include_router(drawings.router)
app.include_router(approvals.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(usage.router)
app.include_router(inquiries.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 사용 로그 미들웨어는 모든 라우터 등록 뒤에 둔다(F11).
app.add_middleware(UsageLogMiddleware)
