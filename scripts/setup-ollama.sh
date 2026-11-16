#!/usr/bin/env bash
# 로컬 LLM(Ollama) 설치·실행·모델 준비·추론 검증. 반복 실행해도 안전하다.
#
#   scripts/setup-ollama.sh           # 필요한 것만 설치·실행·다운로드하고 검증
#   scripts/setup-ollama.sh --check   # 아무것도 설치·실행하지 않고 상태만 점검
#
# 설정(환경 변수 또는 backend/.env의 같은 이름 줄):
#   OLLAMA_BASE_URL  기본 http://127.0.0.1:11434
#   OLLAMA_MODEL     기본 qwen2.5:1.5b-instruct
#
# 하지 않는 것: Homebrew 자동 설치, 실행 중인 Ollama 서버 종료·재시작, 이미 있는 Ollama 재설치, 모델 삭제.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

ok()   { printf '  \033[32m[OK]\033[0m   %s\n' "$*"; }
info() { printf '  [INFO] %s\n' "$*"; }
skip() { printf '  [SKIP] %s\n' "$*"; }
warn() { printf '  \033[33m[WARN]\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m[FAIL]\033[0m %s\n' "$*"; exit 1; }
step() { printf '\n%s\n' "$*"; }

# backend/.env에 OLLAMA_* 값이 있으면 읽는다(환경 변수가 우선). 다른 줄은 실행하지 않는다.
if [ -f "$ROOT/backend/.env" ]; then
  while IFS='=' read -r k v; do
    case "$k" in
      OLLAMA_BASE_URL|OLLAMA_MODEL) [ -z "${!k:-}" ] && export "$k=${v%\"}" && export "$k=${!k#\"}" ;;
    esac
  done < <(grep -E '^(OLLAMA_BASE_URL|OLLAMA_MODEL)=' "$ROOT/backend/.env")
fi
BASE="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
BASE="${BASE%/}"
MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b-instruct}"
HOSTPORT="${BASE#http://}"; HOSTPORT="${HOSTPORT#https://}"; HOSTPORT="${HOSTPORT%%/*}"
LOCAL=0
case "$HOSTPORT" in 127.0.0.1:*|localhost:*) LOCAL=1 ;; esac

echo "Ollama 준비 — 서버 $BASE, 모델 $MODEL$([ $CHECK_ONLY = 1 ] && echo ' (점검만)')"

# 1. macOS ------------------------------------------------------------------
step "1. 운영체제"
[ "$(uname -s)" = "Darwin" ] || fail "macOS 전용 스크립트다. 다른 OS는 https://ollama.com/download 를 참고해 설치한다."
ARCH="$(uname -m)"
ok "macOS $(sw_vers -productVersion 2>/dev/null) ($ARCH)"
[ "$ARCH" = "arm64" ] || warn "Apple Silicon이 아니다. 동작은 하지만 추론이 느릴 수 있다."

# 2. Homebrew / Ollama ---------------------------------------------------------
step "2. Ollama 명령"
find_ollama() {
  command -v ollama 2>/dev/null && return
  for p in /opt/homebrew/bin/ollama /usr/local/bin/ollama /Applications/Ollama.app/Contents/Resources/ollama; do
    [ -x "$p" ] && { echo "$p"; return; }
  done
}
OLLAMA="$(find_ollama || true)"
BREW="$(command -v brew 2>/dev/null || { [ -x /opt/homebrew/bin/brew ] && echo /opt/homebrew/bin/brew; } || true)"
if [ -n "$OLLAMA" ]; then
  skip "이미 설치됨: $OLLAMA (재설치하지 않음)"
elif [ $CHECK_ONLY = 1 ]; then
  fail "ollama 명령이 없다. 설치: scripts/setup-ollama.sh (또는 brew install ollama)"
elif [ -z "$BREW" ]; then
  echo "  Homebrew가 없어 자동 설치하지 않는다. 아래 중 하나를 직접 실행한 뒤 다시 실행한다."
  echo "    · Homebrew 설치: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  echo "    · 또는 Ollama 앱 설치: https://ollama.com/download (Applications로 옮긴 뒤 한 번 실행)"
  fail "Homebrew 없음"
else
  ok "Homebrew: $($BREW --version | head -1)"
  info "brew install ollama 실행"
  "$BREW" install ollama || fail "brew install ollama 실패. 출력의 오류를 확인한다."
  OLLAMA="$(find_ollama || true)"
  [ -n "$OLLAMA" ] || fail "설치 후에도 ollama 명령을 찾지 못했다. 새 터미널에서 다시 실행한다."
  ok "설치 완료: $OLLAMA"
fi
ok "버전: $("$OLLAMA" --version 2>/dev/null | tail -1)"

# 3. 서버 ---------------------------------------------------------------------
step "3. 서버 ($BASE)"
alive() { curl -sf -m 3 "$BASE/api/tags" >/dev/null 2>&1; }
if alive; then
  OWNER=""
  if [ $LOCAL = 1 ] && command -v lsof >/dev/null; then
    PID="$(lsof -nP -iTCP:"${HOSTPORT##*:}" -sTCP:LISTEN -t 2>/dev/null | head -1)"
    [ -n "$PID" ] && OWNER=" (PID $PID: $(ps -o command= -p "$PID" 2>/dev/null | cut -c1-90))"
  fi
  skip "이미 실행 중인 서버를 그대로 쓴다$OWNER"
elif [ $CHECK_ONLY = 1 ]; then
  fail "서버가 응답하지 않는다. 시작: scripts/setup-ollama.sh 또는 ollama serve"
elif [ $LOCAL = 0 ]; then
  fail "원격 서버($BASE)가 응답하지 않는다. 원격 서버는 이 스크립트가 시작하지 않는다."
else
  mkdir -p "$ROOT/state/run"
  LOG="$ROOT/state/run/ollama-serve.log"
  info "ollama serve 시작 (로그 $LOG)"
  OLLAMA_HOST="$HOSTPORT" nohup "$OLLAMA" serve >>"$LOG" 2>&1 &
  echo $! > "$ROOT/state/run/ollama-serve.pid"
  for _ in $(seq 1 30); do alive && break; sleep 1; done
  alive || fail "30초 안에 서버가 응답하지 않았다. 로그 확인: tail -n 40 $LOG"
  ok "서버 시작됨 (PID $(cat "$ROOT/state/run/ollama-serve.pid"))"
fi
VER="$(curl -s -m 3 "$BASE/api/version" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version","?"))' 2>/dev/null)"
ok "API 응답: /api/tags, 서버 버전 ${VER:-?}"

# 4. 모델 ---------------------------------------------------------------------
step "4. 모델 ($MODEL)"
has_model() {
  curl -s -m 5 "$BASE/api/tags" | python3 -c '
import json, sys
want = sys.argv[1]; names = [m.get("name", "") for m in json.load(sys.stdin).get("models", [])]
sys.exit(0 if want in names or (":" not in want and want + ":latest" in names) else 1)' "$MODEL"
}
if has_model; then
  skip "이미 있음 (다운로드 생략)"
elif [ $CHECK_ONLY = 1 ]; then
  fail "모델이 없다. 다운로드: OLLAMA_HOST=$HOSTPORT ollama pull $MODEL"
else
  info "ollama pull $MODEL (처음 한 번, 약 1GB)"
  OLLAMA_HOST="$HOSTPORT" "$OLLAMA" pull "$MODEL" || fail "모델 다운로드 실패. 네트워크와 디스크 공간을 확인한다."
  has_model || fail "다운로드 후에도 서버 목록에 모델이 없다."
  ok "다운로드 완료"
fi
info "ollama list:"
OLLAMA_HOST="$HOSTPORT" "$OLLAMA" list 2>/dev/null | sed 's/^/         /'

# 5. 추론 검증 ------------------------------------------------------------------
step "5. 추론 검증 (POST /api/chat)"
REQ="$(python3 -c '
import json, sys
print(json.dumps({"model": sys.argv[1], "stream": False, "options": {"num_predict": 60},
  "messages": [{"role": "user", "content": "조선소의 블록 탑재가 무엇인지 한 문장으로 답해 주세요."}]}, ensure_ascii=False))' "$MODEL")"
T0=$(python3 -c 'import time; print(time.time())')
RES="$(curl -s -m 120 -H 'Content-Type: application/json' -d "$REQ" "$BASE/api/chat")"
T1=$(python3 -c 'import time; print(time.time())')
ANSWER="$(printf '%s' "$RES" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(2)
if d.get("error"): print("ERROR:" + d["error"]); sys.exit(1)
c = (d.get("message") or {}).get("content", "").strip()
print(c.replace("\n", " ")[:160]); sys.exit(0 if c else 1)')"
case $? in
  0) ok "응답 $(python3 -c "print(round($T1-$T0,1))")초: $ANSWER" ;;
  2) fail "응답이 JSON이 아니다: $(printf '%s' "$RES" | head -c 200)" ;;
  *) fail "추론 실패: ${ANSWER:-빈 응답}" ;;
esac

echo
echo "완료. 백엔드 설정: OLLAMA_BASE_URL=$BASE  OLLAMA_MODEL=$MODEL"
