#!/usr/bin/env bash
# F16 시연 모드: 별도 DB·파일 폴더로 예시 데이터를 만들고 백엔드를 띄운다(admin / han.wk, 비밀번호 Shipyard-Demo-26!).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SHIPYARD_DB_PATH=state/run/demo.db
export SHIPYARD_FILE_DIR=state/run/demo-files
export SHIPYARD_DEMO=1
PORT="${SHIPYARD_BACKEND_PORT:-8100}"
cd "$ROOT/backend"
if [ ! -f "$ROOT/state/run/demo.db" ]; then
  uv run init-db --seed --demo-pdfs --demo-usage
  uv run python -m app.services.demo prepare
fi
exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
