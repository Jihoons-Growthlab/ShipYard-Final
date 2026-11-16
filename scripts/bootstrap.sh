#!/usr/bin/env bash
# 새 Mac(Apple Silicon)에서 Ver4를 처음 준비한다. 이미 있는 것은 다시 설치하지 않고, 반복 실행해도 안전하다.
#
#   scripts/bootstrap.sh           # 필요한 것만 설치 → Ollama 준비 → 프로젝트 의존성 → 환경 점검(setup.sh)
#   scripts/bootstrap.sh --check   # 아무것도 설치하지 않고 상태만 보고(없는 항목이 있으면 exit 1)
#   scripts/bootstrap.sh --yes     # Homebrew가 없을 때 묻지 않고 공식 설치 스크립트 실행에 동의
#
# 하지 않는 것: Chrome·Unity 설치(수동 안내), 실행 중인 서버 종료, 다른 프로젝트 변경, git 작업.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CHECK=0; YES=0
for a in "$@"; do case "$a" in --check) CHECK=1 ;; --yes) YES=1 ;; esac; done
MISSING=()

ok()   { printf '  \033[32m[OK]\033[0m   %s\n' "$*"; }
skip() { printf '  [SKIP] %s\n' "$*"; }
warn() { printf '  \033[33m[WARN]\033[0m %s\n' "$*"; }
miss() { printf '  \033[31m[MISS]\033[0m %s\n' "$*"; MISSING+=("$1"); }
step() { printf '\n%s\n' "$*"; }

echo "Ver4 bootstrap$([ $CHECK = 1 ] && echo ' (점검만)') — $ROOT"

step "1. 운영체제"
if [ "$(uname -s)" != "Darwin" ]; then echo "  macOS 전용이다."; exit 1; fi
ok "macOS $(sw_vers -productVersion) ($(uname -m))"
[ "$(uname -m)" = "arm64" ] || warn "Apple Silicon이 아니다(동작은 하지만 Ollama·Unity가 느릴 수 있다)"

step "2. Homebrew"
BREW="$(command -v brew || { [ -x /opt/homebrew/bin/brew ] && echo /opt/homebrew/bin/brew; } || true)"
if [ -n "$BREW" ]; then
  ok "$($BREW --version | head -1)"
  eval "$($BREW shellenv)" 2>/dev/null || true
elif [ $CHECK = 1 ]; then
  miss Homebrew "없음. 설치: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
else
  echo "  Homebrew가 없다. 공식 설치 명령:"
  echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  ans=n
  if [ $YES = 1 ]; then ans=y
  elif [ -t 0 ]; then read -r -p "  지금 설치할까? 관리자 암호를 물을 수 있다 [y/N] " ans
  fi
  if [ "$ans" = y ] || [ "$ans" = Y ]; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || { echo "  Homebrew 설치 실패"; exit 1; }
    BREW=/opt/homebrew/bin/brew; eval "$($BREW shellenv)"; ok "Homebrew 설치됨"
  else
    echo "  동의하지 않아 멈춘다. 위 명령을 직접 실행한 뒤 다시 실행한다."; exit 1
  fi
fi

brew_install() {  # $1=명령 $2=formula
  if command -v "$1" >/dev/null 2>&1; then return 0; fi
  if [ $CHECK = 1 ] || [ -z "$BREW" ]; then return 1; fi
  echo "  brew install $2"; "$BREW" install "$2" >/dev/null || return 1
  command -v "$1" >/dev/null 2>&1
}

step "3. uv · Python"
if command -v uv >/dev/null 2>&1; then skip "uv 있음: $(uv --version)"
elif brew_install uv uv; then ok "uv 설치: $(uv --version)"
else miss uv "없음(brew install uv)"; fi
if command -v uv >/dev/null 2>&1; then
  if PY="$(uv python find '>=3.10' 2>/dev/null)"; then skip "Python ≥3.10: $PY"
  elif [ $CHECK = 1 ]; then miss python "uv가 찾은 Python ≥3.10 없음(uv python install 3.12)"
  else uv python install 3.12 >/dev/null && ok "Python 3.12 설치(uv)" || miss python "uv python install 3.12 실패"; fi
fi

step "4. Node.js · npm"
if command -v node >/dev/null 2>&1; then
  NV="$(node -v)"; MAJOR="${NV#v}"; MAJOR="${MAJOR%%.*}"
  if [ "$MAJOR" -ge 20 ]; then skip "node $NV, npm $(npm -v)"; else warn "node $NV < 20. brew upgrade node 권장(자동 변경하지 않음)"; fi
elif brew_install node node; then ok "node $(node -v) 설치"
else miss node "없음(brew install node)"; fi

step "5. Ollama · 모델"
if [ $CHECK = 1 ]; then
  scripts/setup-ollama.sh --check >/tmp/ver4-ollama-check.$$ 2>&1 && ok "Ollama 서버·모델·추론 준비됨" || { miss ollama "준비 안 됨: scripts/setup-ollama.sh"; tail -2 /tmp/ver4-ollama-check.$$ | sed 's/^/    /'; }
  rm -f /tmp/ver4-ollama-check.$$
else
  scripts/setup-ollama.sh | sed 's/^/  /' ; [ "${PIPESTATUS[0]}" = 0 ] || miss ollama "setup-ollama.sh 실패(위 메시지)"
fi

step "6. 프로젝트 의존성"
if [ -f backend/pyproject.toml ]; then
  if [ $CHECK = 1 ]; then [ -d backend/.venv ] && skip "backend/.venv 있음" || miss backend-deps "cd backend && uv sync"
  else (cd backend && uv sync -q) && ok "backend uv sync" || miss backend-deps "uv sync 실패"; fi
else skip "backend/ 아직 없음(P1에서 생성)"; fi
if [ -f frontend/package.json ]; then
  if [ -d frontend/node_modules ]; then skip "frontend/node_modules 있음"
  elif [ $CHECK = 1 ]; then miss frontend-deps "npm install --prefix frontend"
  else npm install --prefix frontend --no-audit --no-fund --silent && ok "frontend npm install" || miss frontend-deps "npm install 실패"; fi
else skip "frontend/ 아직 없음(P1에서 생성)"; fi

step "7. 화면 캡처(Playwright · Chrome)"
if [ -d scripts/node_modules/playwright-core ]; then skip "playwright-core 있음"
elif [ $CHECK = 1 ]; then miss playwright "npm install --prefix scripts"
else npm install --prefix scripts --no-audit --no-fund --silent && ok "playwright-core 설치" || miss playwright "npm install --prefix scripts 실패"; fi
if [ -d "/Applications/Google Chrome.app" ]; then ok "Google Chrome 있음(shots는 시스템 Chrome 사용)"
else miss chrome "Google Chrome 수동 설치: https://www.google.com/chrome/ (Applications)"; fi

step "8. 한국어 글꼴(보고서 PDF)"
if [ -n "${SHIPYARD_REPORT_FONT:-}" ] && [ -f "$SHIPYARD_REPORT_FONT" ]; then ok "SHIPYARD_REPORT_FONT=$SHIPYARD_REPORT_FONT"
elif [ -f /System/Library/Fonts/AppleSDGothicNeo.ttc ]; then ok "AppleSDGothicNeo.ttc"
else miss font "한글 TTF/TTC를 SHIPYARD_REPORT_FONT로 지정"; fi

step "9. Unity WebGL"
if U="$(python3 scripts/wf.py unity-path)"; then ok "$U"
else miss unity "Unity Hub(https://unity.com/download) → 로그인·Personal 라이선스 → Installs에서 6000.x + Web Build Support (specs/F10.md)"; fi

step "10. 포트"
python3 scripts/wf.py ports | sed 's/^/  /'
for n in backend frontend; do
  P="$(python3 scripts/wf.py ports --env | grep -i "${n}_PORT" | cut -d= -f2)"
  if lsof -nP -iTCP:"$P" -sTCP:LISTEN >/dev/null 2>&1; then
    OWNER="$(lsof -nP -iTCP:"$P" -sTCP:LISTEN -t | head -1 | xargs -I{} ps -o command= -p {} | cut -c1-80)"
    if [ -f "state/run/$n.pid" ] && [ "$(cat "state/run/$n.pid")" = "$(lsof -nP -iTCP:"$P" -sTCP:LISTEN -t | head -1)" ]; then
      skip "$n 포트 $P: Ver4 dev 서버 실행 중"
    else
      warn "$n 포트 $P 사용 중: $OWNER — 종료하지 않는다. 다른 포트: config/workflow.json ports 또는 SHIPYARD_$(echo "$n" | tr a-z A-Z)_PORT"
    fi
  else ok "$n 포트 $P 비어 있음"; fi
done

step "11. 환경 점검 기록(setup.sh)"
if [ $CHECK = 1 ]; then skip "--check: setup.sh 생략"
else scripts/setup.sh | sed 's/^/  /'; fi

echo
if [ ${#MISSING[@]} -eq 0 ]; then
  echo "준비 완료. 빌드 시작: scripts/start.sh --launch"
else
  echo "남은 항목(${#MISSING[@]}): ${MISSING[*]} — 위 안내대로 처리한 뒤 다시 실행한다."
  exit 1
fi
