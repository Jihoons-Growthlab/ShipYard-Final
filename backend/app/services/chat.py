"""F13 챗봇: MCP 클라이언트(call_tool), 질문 라우팅, 건의 접수(멱등), Ollama 연결."""
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from .. import config, db
from ..deps import forbidden
from ..errors import AppError, validation
from ..util import utc_now

BACKEND_DIR = Path(__file__).resolve().parents[2]
MCP_TIMEOUT = 10
TOOL_MENUS = {"search_hulls": "M11", "list_drawings": "M31", "list_progress_hulls": "M22",
              "submit_feedback": "M95", "build_report": "M11"}
FEEDBACK_KIND = {"suggestion": ("FEATURE", "건의"), "inquiry": ("QUESTION", "문의")}

MSG_MCP = "호선 조회 서버에 연결하지 못했습니다."
MSG_FEEDBACK = "접수할 내용을 입력하고 접수 버튼을 눌러 주세요."
MSG_PROGRESS = "어떤 공정의 실적을 볼까요? 먼저 호선을 선택해 주세요."
MSG_PROGRESS_NONE = "공정이 등록된 호선이 없습니다."
MSG_DRAWING = "상세 정보를 볼 도면을 선택해 주세요."
MSG_HULL = "상세 정보를 볼 호선을 선택해 주세요."
MSG_HULL_NONE = "일치하는 호선이 없습니다. 호선 번호나 이름을 확인해 주세요."
MSG_HULL_MORE = "처음 20척을 표시합니다. 호선 번호나 이름으로 범위를 좁힐 수 있습니다."
MSG_HULL_SN = "‘SN’으로 등록된 호선을 찾지 못했습니다. 등록된 호선 중에서 선택해 주세요."
SYSTEM_PROMPT = ("당신은 조선소 업무 용어와 작업을 설명하는 안내 챗봇입니다. 한국어로 간결하게 답하세요. "
                 "시스템의 실제 호선·공정 데이터에 접근할 수 없습니다. "
                 "실제 현황은 추측하지 말고 호선 목록이나 상세 화면에서 확인하도록 안내하세요.")

RE_FEEDBACK = re.compile(r"(건의|문의)(하기| 하고 싶어)?[.!?]?")
RE_PROGRESS = re.compile(r"공정 실적|실적 (정보|알려|조회)")
RE_DRAWING = re.compile(r"도면.*(정보|알려|목록|조회|선택|보여|검색)")
RE_HULL = re.compile(r"호선\s*의?\s*(상세|정보|목록|현황|상태|진척|조회|선택|검색)|호선.*알려|SN-\d+", re.I)
RE_SN = re.compile(r"SN-(\d+)", re.I)
RE_HULL_NO = re.compile(r"호선\s+(\d[\w.-]*)")
RE_HULL_PREFIX = re.compile(r"([^\s]+?)\s*호선")


# --- MCP 클라이언트
def call_tool(emp_no: str, name: str, arguments: dict) -> dict:
    """initialize(id 1) → notifications/initialized → tools/call(id 2)을 한 번에 보내고 stdout 두 줄을 읽는다."""
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "shipyard-api", "version": "4.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    ]
    payload = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in msgs)
    try:
        p = subprocess.run([sys.executable, "-m", "app.hull_mcp", emp_no], input=payload, capture_output=True,
                           text=True, encoding="utf-8", cwd=BACKEND_DIR, env=os.environ.copy(), timeout=MCP_TIMEOUT)
        lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
        init, res = json.loads(lines[0]), json.loads(lines[1])
        if init.get("id") != 1 or "result" not in init or res.get("id") != 2 or "result" not in res:
            raise ValueError("bad response")
        out = res["result"].get("structuredContent")
        if not isinstance(out, dict):
            out = json.loads(res["result"]["content"][0]["text"])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError, KeyError, TypeError) as e:
        raise AppError(502, "HULL_MCP_ERROR", MSG_MCP) from e
    if out.get("forbidden"):
        raise forbidden(TOOL_MENUS.get(name, ""))
    return out


# --- 질문 라우팅
def _hull_query(text: str) -> str:
    for rx in (RE_SN, RE_HULL_NO, RE_HULL_PREFIX):
        m = rx.search(text)
        if m:
            return m.group(1)
    return ""


def _hull_answer(emp_no: str, text: str) -> dict:
    q = _hull_query(text)
    r = call_tool(emp_no, "search_hulls", {"query": q[:100]})
    base = MSG_HULL
    if not r["hulls"] and q.lower() == "sn":
        r, base = call_tool(emp_no, "search_hulls", {"query": ""}), MSG_HULL_SN
    if not r["hulls"]:
        return {"answer": MSG_HULL_NONE, "hulls": []}
    answer = f"{base} {MSG_HULL_MORE}" if r["total"] > 20 else base
    return {"answer": answer, "hulls": r["hulls"]}


def answer(emp_no: str, messages: list[dict]) -> dict:
    if not messages or messages[-1]["role"] != "user" or not messages[-1]["content"].strip():
        raise AppError(400, "CHAT_INPUT", "질문을 입력해 주세요.")
    text = messages[-1]["content"].strip()
    m = RE_FEEDBACK.fullmatch(text)
    if m:
        return {"answer": MSG_FEEDBACK, "feedback_kind": "suggestion" if m.group(1) == "건의" else "inquiry"}
    if RE_PROGRESS.search(text):
        items = call_tool(emp_no, "list_progress_hulls", {})["items"]
        if not items:
            return {"answer": MSG_PROGRESS_NONE, "choice_type": "progress-hull", "choices": []}
        return {"answer": MSG_PROGRESS, "choice_type": "progress-hull", "choices": items}
    if RE_DRAWING.search(text):
        return {"answer": MSG_DRAWING, "choice_type": "drawing", "choices": call_tool(emp_no, "list_drawings", {})["items"]}
    if RE_HULL.search(text):
        return _hull_answer(emp_no, text)
    return {"answer": ollama_chat(messages)}


# --- 건의·문의 접수 (MCP submit_feedback이 호출)
def save_feedback(conn: sqlite3.Connection, emp_no: str, kind: str, content: str, request_id: str) -> dict:
    category, word = FEEDBACK_KIND[kind]
    content = content.strip()
    with db.tx(conn):
        prev = conn.execute("SELECT InquiryId, Category, Content FROM TB_SYS_ChatInquiry"
                            " WHERE CreateUserId = ? AND RequestId = ?", (emp_no, request_id)).fetchone()
        if prev:
            if (prev[1], prev[2]) != (category, content):
                raise AppError(409, "FEEDBACK_CONFLICT", "같은 요청 번호로 다른 내용이 이미 접수되었습니다.")
            iid = prev[0]
        else:
            first = content.splitlines()[0].strip()
            title = f"[챗봇 {word}] {first[:60]}{'…' if len(first) > 60 else ''}"
            iid = conn.execute("INSERT INTO TB_SYS_Inquiry(Category, Title, Content, Status, CreateUserId, CreateDt)"
                               " VALUES (?, ?, ?, 'OPEN', ?, ?)", (category, title, content, emp_no, utc_now())).lastrowid
            conn.execute("INSERT INTO TB_SYS_ChatInquiry(CreateUserId, RequestId, InquiryId, Category, Content)"
                         " VALUES (?, ?, ?, ?, ?)", (emp_no, request_id, iid, category, content))
    return {"receipt": f"FB-{iid:06d}", "inquiry_id": iid}


def submit_feedback(emp_no: str, kind: str, content: str, request_id: str) -> dict:
    if not (content or "").strip():
        raise validation("content", "접수할 내용을 입력해 주세요.", "FEEDBACK_INPUT")
    out = call_tool(emp_no, "submit_feedback", {"kind": kind, "content": content.strip(), "request_id": request_id})
    if "error" in out:
        raise AppError(out.get("status", 400), out.get("code", "FEEDBACK_ERROR"), out["error"])
    return out


# --- Ollama (데이터 질문이 아닌 일반 설명만)
_busy = threading.Semaphore(1)


def ollama_chat(messages: list[dict]) -> str:
    if not _busy.acquire(blocking=False):
        raise AppError(429, "CHAT_BUSY", "다른 답변을 작성 중입니다. 잠시 후 다시 보내 주세요.")
    try:
        body = {"model": config.ollama_model(), "stream": False, "options": {"num_ctx": 4096, "num_predict": 320},
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             *({"role": m["role"], "content": m["content"]} for m in messages)]}
        req = urllib.request.Request(config.ollama_base_url().rstrip("/") + "/api/chat",
                                     data=json.dumps(body, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=config.ollama_timeout()) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise AppError(503, "CHAT_MODEL_MISSING", "로컬 채팅 모델을 찾을 수 없습니다.") from e
            raise AppError(502, "CHAT_MODEL_ERROR", "로컬 모델이 답변 중 오류를 반환했습니다.") from e
        except TimeoutError as e:
            raise AppError(502, "CHAT_MODEL_ERROR", "로컬 모델의 답변 시간이 초과되었습니다.") from e
        except (urllib.error.URLError, OSError) as e:
            raise AppError(503, "CHAT_OFFLINE", "로컬 모델에 연결할 수 없습니다. Ollama 실행 상태를 확인해 주세요.") from e
        except ValueError as e:
            raise AppError(502, "CHAT_RESPONSE", "로컬 모델의 답변 형식을 읽을 수 없습니다.") from e
        text = ((data.get("message") or {}).get("content") or "").strip() if isinstance(data, dict) else ""
        if not text:
            raise AppError(502, "CHAT_RESPONSE", "로컬 모델의 답변 형식을 읽을 수 없습니다.")
        return text
    finally:
        _busy.release()
