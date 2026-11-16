#!/usr/bin/env bash
# 최초 1회: 명세·참고 자료 확인(이 폴더 안의 실제 파일), 상위 CLAUDE.md 제외, 측정 조건 기록, playwright-core 설치, 환경 점검.
set -euo pipefail
cd "$(dirname "$0")/.."
for d in specs reference/ui reference/seed reference/manual; do
  [ -d "$d" ] && [ ! -L "${d%%/*}" ] || { echo "$d가 없거나 링크다. 이 폴더 안의 실제 파일이어야 한다." >&2; exit 1; }
done
# 상위 폴더의 CLAUDE.md를 로드하지 않도록 절대 경로로 제외한다(다른 버전 지침이 섞이지 않게).
python3 - <<'PY'
import json, os
root = os.getcwd(); ex = []; d = os.path.dirname(root)
while d != os.path.dirname(d):
    for n in ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md"):
        if os.path.exists(os.path.join(d, n)): ex.append(os.path.join(d, n))
    d = os.path.dirname(d)
p = ".claude/settings.local.json"
cur = json.load(open(p)) if os.path.exists(p) else {}
cur["claudeMdExcludes"] = ex
json.dump(cur, open(p, "w"), indent=2); print("claudeMdExcludes:", ex or "없음")
PY
{
  echo "prepared_at=$(date +%FT%T%z)"
  echo "path=$PWD"
  echo "specs_sha256=$(find specs -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
  echo "reference_sha256=$(find reference -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
  echo "claude_version=$(claude --version 2>/dev/null || echo unknown)"
  # 비교 조건(Ver3와 같은 항목): 모델·설정, 입력 자료 양, 작업 수, 포트
  python3 - <<'PY'
import json, pathlib
c = json.load(open("config/workflow.json")); t = json.load(open("state/tasks.json"))
cmd = c["launch"]["command"]
opt = lambda k: cmd[cmd.index(k) + 1] if k in cmd else None
specs = sorted(pathlib.Path("specs").glob("*.md"))
print(f"launch_model={opt('--model')} effort={opt('--effort')} permission={opt('--permission-mode')} strict_mcp={'--strict-mcp-config' in cmd} prompt={c['launch']['prompt']}")
print(f"inputs: specs={len(specs)} files {sum(p.stat().st_size for p in specs)} bytes, reference_png={len(list(pathlib.Path('reference/ui').glob('*.png')))}, "
      f"manual_jpg={len(list(pathlib.Path('reference/manual').glob('*.jpg')))}, html_mockups=0")
print(f"plan: phases={len(t['phases'])} tasks={len(t['tasks'])}")
print(f"ports: backend={c['ports']['backend']} frontend={c['ports']['frontend']}")
PY
} > state/conditions.txt
[ -d scripts/node_modules/playwright-core ] || npm install --prefix scripts --no-audit --no-fund --silent
rm -f state/env.json
python3 - <<'PY'
import json, subprocess
cfg = json.load(open("config/workflow.json"))
res = {}
for k, argv in cfg["env_checks"].items():
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        res[k] = (r.stdout.strip().splitlines() or ["ok"])[0] if r.returncode == 0 else "MISSING"
    except (OSError, subprocess.TimeoutExpired):
        res[k] = "MISSING"
json.dump(res, open("state/env.json", "w"), ensure_ascii=False)
for k, v in res.items():
    print(f"  {k:12} {v}")
if "MISSING" in (res.get("ollama"), res.get("ollama_model")):
    print("  -> Ollama: scripts/setup-ollama.sh 실행(설치·서버·모델·추론 검증)")
if "MISSING" in (res.get("unity"), res.get("unity_webgl")):
    print("  -> Unity Hub에서 6000.x Editor + Web Build Support 설치·로그인(specs/F10.md 환경 절)")
PY
cat state/conditions.txt
echo "준비 완료. 시작: scripts/start.sh --launch"
