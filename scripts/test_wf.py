"""Self-test for wf.py on a temp fixture root. Run: python3 scripts/test_wf.py"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL = HERE.parent


class WF(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for d in ("config", "state", "reports"):
            (self.tmp / d).mkdir()
        for f in ("config/workflow.json", "config/token-policy.json", "state/tasks.json", "state/PROGRESS.md"):
            shutil.copy(REAL / f, self.tmp / f)
        conf = json.loads((self.tmp / "config/workflow.json").read_text())
        py = sys.executable
        conf["verify"]["backend"] = {"cwd": ".", "cmd": [py, "-c", "print('3 passed in 0.1s')"], "parser": "pytest"}
        conf["verify"]["frontend"] = {"cwd": ".", "cmd": [py, "-c",
            "import sys; print(' FAIL  src/a.test.js > x\\nAssertionError: expected 1\\n Tests  1 failed | 2 passed'); sys.exit(1)"], "parser": "vitest"}
        conf["env_checks"] = {"python": [py, "--version"]}
        conf["srcmap"]["openapi_cmd"]["cwd"] = "no-backend"
        (self.tmp / "config/workflow.json").write_text(json.dumps(conf))
        os.environ["WF_ROOT"] = str(self.tmp)
        os.environ["WF_CLAUDE_PROJECTS"] = str(self.tmp / "projects")
        sys.path.insert(0, str(HERE))
        import wf
        self.wf = __import__("importlib").reload(wf)

    def tearDown(self):
        os.chdir(REAL)  # 지울 임시 폴더 안에 머물면 다음 테스트의 하위 프로세스가 cwd를 잃는다
        shutil.rmtree(self.tmp)
        os.environ.pop("WF_ROOT", None)  # 다른 테스트(Shots)가 지운 임시 폴더를 보지 않게
        os.environ.pop("WF_CLAUDE_PROJECTS", None)

    def run_cmd(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.wf.COMMANDS[argv[0]](list(argv[1:]))
        return rc or 0, buf.getvalue()

    def finish_phase(self, sid, phase):
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == phase:
                self.assertEqual(self.run_cmd("done-task", tid)[0], 0)
        time.sleep(1.1)
        (self.tmp / "state/PROGRESS.md").write_text("# 인계\n- 완료: P1\n")
        return self.run_cmd("handoff-phase")

    def test_session_flow_and_duplicate_refusal(self):
        rc, out = self.run_cmd("next")
        self.assertEqual(rc, 0)
        self.assertIn("PHASE P1", out)
        rc, out = self.run_cmd("claim", "${CLAUDE_SESSION_ID}")
        self.assertEqual(rc, 2)  # unsubstituted id
        rc, out = self.run_cmd("claim", "s1")
        self.assertEqual(rc, 0)
        self.assertIn("[claim]", out)
        self.assertIn("env: python=", out)
        self.assertIn("--- state/PROGRESS.md", out)
        rc, out = self.run_cmd("claim", "s1")
        self.assertIn("[resume]", out)
        # task cannot be done before its verification passes after the claim
        rc, out = self.run_cmd("done-task", "T01")
        self.assertEqual(rc, 1)
        self.assertIn("NOT DONE", out)
        self.assertEqual(self.run_cmd("verify", "backend", "tests/test_x.py")[0], 0)
        rc, out = self.run_cmd("handoff-phase")
        self.assertEqual(rc, 1)
        self.assertIn("미완료 작업", out)
        # targeted run does not satisfy the full checkpoint
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == "P1":
                self.run_cmd("done-task", tid)
        (self.tmp / "state/PROGRESS.md").write_text("x\n")
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("전체 검증 backend", out)
        self.run_cmd("verify", "backend")
        rc, out = self.run_cmd("handoff-phase")
        self.assertEqual(rc, 0, out)
        self.assertIn("PHASE P1 DONE", out)
        # done task is not redone
        rc, out = self.run_cmd("done-task", "T01")
        self.assertIn("already done", out)
        # same session may not start the next phase (Ver2 S5/S6 reuse)
        rc, out = self.run_cmd("claim", "s1")
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED", out)
        rc, out = self.run_cmd("claim", "s2")
        self.assertEqual(rc, 0)
        self.assertIn("PHASE P2", out)
        self.assertIn("specs/F07.md", out)  # Ver4: P2는 백엔드 2(이미지 없음)
        self.assertIn("--- state/SOURCEMAP.md", out)

    def test_takeover_and_progress_limit(self):
        self.run_cmd("claim", "a")
        rc, out = self.run_cmd("claim", "b")
        self.assertIn("[takeover]", out)
        self.run_cmd("verify", "backend")
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == "P1":
                self.run_cmd("done-task", tid)
        (self.tmp / "state/PROGRESS.md").write_text("line\n" * 41)
        rc, out = self.run_cmd("handoff-phase")
        self.assertEqual(rc, 1)
        self.assertIn("41줄", out)

    def test_shots_gate_and_accept(self):
        # Ver4: 첫 화면 phase는 P3(P1·P2는 백엔드)
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] in ("P1", "P2"):
                st["status"][tid] = {"state": "done", "at": "2026-01-01T00:00:00+09:00"}
        (self.tmp / "state/tasks.json").write_text(json.dumps(st))
        self.wf.log_event("old", "phase-done", "P1")
        self.wf.log_event("old", "phase-done", "P2")
        self.run_cmd("claim", "u1")
        conf = json.loads((self.tmp / "config/workflow.json").read_text())
        conf["verify"]["frontend"]["cmd"] = [sys.executable, "-c", "print(' Tests  4 passed (4)')"]
        conf["verify"]["build"] = {"cwd": ".", "cmd": [sys.executable, "-c", "print('built')"], "parser": "generic"}
        (self.tmp / "config/workflow.json").write_text(json.dumps(conf))
        self.run_cmd("verify", "frontend")
        self.run_cmd("verify", "build")
        for tid, t in st["tasks"].items():
            if t["phase"] == "P3":
                self.assertEqual(self.run_cmd("done-task", tid)[0], 0)
        time.sleep(1.1)
        (self.tmp / "state/PROGRESS.md").write_text("ok\n")
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("shots 체크포인트 없음", out)
        res = {"ts": "2999-01-01T00:00:00.000+00:00", "ok": False, "phases": ["P3"],
               "results": [{"name": "hull-list", "status": "over"}]}
        (self.tmp / "state/shots-result.json").write_text(json.dumps(res))
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("hull-list", out)
        rc, out = self.run_cmd("handoff-phase", "--accept-shots", "시드 날짜 차이")
        self.assertEqual(rc, 0, out)
        self.assertIn("시드 날짜 차이", (self.tmp / "state/accepted-shots.log").read_text())

    def test_verify_summary_and_dry_run(self):
        self.run_cmd("claim", "v")
        rc, out = self.run_cmd("verify", "frontend")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)
        self.assertIn("AssertionError: expected 1", out)
        self.assertIn("Tests  1 failed", out)
        log = json.loads((self.tmp / "state/verify.json").read_text())["frontend"]["log"]
        self.assertTrue((self.tmp / log).exists())
        rc, out = self.run_cmd("verify", "all", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("DRY-RUN"), 3)

    def test_block_and_all_done(self):
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid in st["tasks"]:
            st["status"][tid] = {"state": "done", "at": "x"}
        st["status"]["T20"] = {"state": "blocked", "reason": "Unity 라이선스"}
        (self.tmp / "state/tasks.json").write_text(json.dumps(st))
        for ph in st["phases"]:
            self.wf.log_event("x", "phase-done", ph["id"])
        rc, out = self.run_cmd("next")
        self.assertEqual(rc, 3)
        self.assertIn("차단(미실행): T20", out)
        self.assertEqual(self.run_cmd("claim", "z")[0], 3)
        self.assertEqual(self.run_cmd("launch", "--dry-run")[0], 3)

    def test_launch_guard(self):
        self.run_cmd("claim", "live")
        proj = self.wf.claude_project_dir()
        proj.mkdir(parents=True)
        (proj / "live.jsonl").write_text("{}\n")
        rc, out = self.run_cmd("launch", "--dry-run")
        self.assertEqual(rc, 2)
        rc, out = self.run_cmd("launch", "--dry-run", "--force")
        self.assertEqual(rc, 0)
        self.assertIn("/build", out)

    def test_srcmap(self):
        vue = self.tmp / "frontend/src/components/Panel.vue"
        vue.parent.mkdir(parents=True)
        vue.write_text("<script setup>\nconst p = defineProps({ hull: { type: Object, required: true }, mode: String })\n"
                       "const e = defineEmits(['saved', 'update:open'])\n</script>\n<style scoped>\n.panel .row:hover { color: red }\n"
                       "@media (max-width: 900px) { .panel-wide { width: 1px } }\n</style>\n")
        (self.tmp / "frontend/src/api").mkdir()
        (self.tmp / "frontend/src/api/client.js").write_text("export async function api(path) {}\nexport class ApiError {}\n")
        (self.tmp / "frontend/src/styles.css").write_text(".btn, .btn-primary > .ic { a: b }\n/* .nope */\n")
        py = self.tmp / "backend/app/routers/hulls.py"
        py.parent.mkdir(parents=True)
        py.write_text("@router.get('/hulls')\ndef list_hulls():\n    pass\ndef _private():\n    pass\n")
        (self.tmp / "backend/tests").mkdir()
        (self.tmp / "backend/tests/test_h.py").write_text("def test_a():\n    pass\ndef test_b():\n    pass\n")
        rc, out = self.run_cmd("srcmap")
        text = (self.tmp / "state/SOURCEMAP.md").read_text()
        self.assertIn("props[hull,mode] emits[saved,update:open] css[panel panel-wide row]", text)
        self.assertIn("client.js: api, ApiError", text)
        self.assertIn("styles.css: btn btn-primary ic", text)
        self.assertIn("list_hulls routes: GET /hulls", text)
        self.assertNotIn("_private", text)
        self.assertIn("test_h.py (2)", text)
        rc, out = self.run_cmd("srcmap", "--if-stale")
        self.assertIn("fresh", out)

    def test_usage_dedup(self):
        self.wf.log_event("sid1", "claim", "P1")
        proj = self.wf.claude_project_dir()
        (proj / "sid1" / "subagents").mkdir(parents=True)
        u = lambda i, o: {"input_tokens": 1, "output_tokens": o, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 100}
        rows = [{"type": "assistant", "message": {"id": "m1", "model": "x", "usage": u(1, 5)}},
                {"type": "assistant", "message": {"id": "m1", "model": "x", "usage": u(1, 900)}},
                {"type": "assistant", "message": {"id": "m2", "model": "<synthetic>", "usage": u(1, 9)}}]
        (proj / "sid1.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
        (proj / "sid1/subagents/a.jsonl").write_text(json.dumps({"type": "assistant", "message": {"id": "m3", "model": "x", "usage": u(1, 100)}}))
        rc, out = self.run_cmd("usage")
        rep = json.loads((self.tmp / "reports/usage.json").read_text())
        t = rep["total"]
        self.assertEqual(t["api_calls"], 2)
        self.assertEqual(t["output_tokens"], 1000)
        self.assertEqual(t["total"], 2 * 111 + 1000)
        self.assertEqual(t["short_calls"], 1)
        self.assertIsNone(rep["cost_usd"])


    # ---- Ver4 추가: 포트·변경 파일·반복 실패 차단·측정·변경 흐름 handoff
    def test_ports_fill_and_env_override(self):
        rc, out = self.run_cmd("ports")
        self.assertIn("backend=8100", out)
        self.assertEqual(self.wf.fill(["--port", "{backend_port}", "http://127.0.0.1:{frontend_port}/"]),
                         ["--port", "8100", "http://127.0.0.1:5273/"])
        os.environ["SHIPYARD_BACKEND_PORT"] = "8111"
        try:
            self.assertEqual(self.wf.ports()["backend"], 8111)
            self.assertEqual(self.wf.port_env()["SHIPYARD_BACKEND_PORT"], "8111")
        finally:
            os.environ.pop("SHIPYARD_BACKEND_PORT")

    def test_changed_files_tracked_without_git(self):
        self.run_cmd("claim", "f1")  # 기준 스냅샷
        app = self.tmp / "backend/app"
        app.mkdir(parents=True)
        (app / "a.py").write_text("x = 1\n")
        self.run_cmd("verify", "backend")
        rc, out = self.run_cmd("done-task", "T01")
        self.assertEqual(rc, 0, out)
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        self.assertEqual(st["status"]["T01"]["files"], ["backend/app/a.py"])
        time.sleep(0.01)
        (app / "b.py").write_text("y = 2\n")
        (app / "a.py").unlink()
        self.run_cmd("done-task", "T02")
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        self.assertEqual(st["status"]["T02"]["files"], ["backend/app/b.py", "-backend/app/a.py"])
        # 재개(resume)하면 마지막 task-done 이후 바뀐 파일을 알려 준다
        (app / "c.py").write_text("z = 3\n")
        rc, out = self.run_cmd("claim", "f1")
        self.assertIn("[resume]", out)
        self.assertIn("backend/app/c.py", out)

    def test_repeat_failure_guard_and_history(self):
        self.run_cmd("claim", "g1")
        self.assertEqual(self.run_cmd("verify", "frontend")[0], 1)
        self.assertEqual(self.run_cmd("verify", "frontend")[0], 1)
        rc, out = self.run_cmd("verify", "frontend")
        self.assertEqual(rc, 1)
        self.assertIn("REFUSED", out)
        hist = self.wf.verify_history()
        self.assertEqual([h["ok"] for h in hist], [False, False])  # 거부된 실행은 기록하지 않는다
        self.assertEqual(hist[0]["phase"], "P1")
        (self.tmp / "frontend").mkdir(exist_ok=True)
        (self.tmp / "frontend/package.json").write_text("{}")  # 추적 파일 변경 → 다시 실행 허용
        rc, out = self.run_cmd("verify", "frontend")
        self.assertNotIn("REFUSED", out)
        self.assertEqual(len(self.wf.verify_history()), 3)
        self.assertNotIn("REFUSED", self.run_cmd("verify", "frontend", "--force")[1])

    def test_usage_phase_metrics_and_provenance(self):
        self.run_cmd("claim", "m1")
        self.run_cmd("verify", "frontend")
        self.run_cmd("verify", "backend")
        self.run_cmd("done-task", "T01")
        self.run_cmd("usage", "--quiet")
        rep = json.loads((self.tmp / "reports/usage.json").read_text())
        p1 = rep["phases"]["P1"]
        self.assertEqual((p1["verify_runs"], p1["verify_failures"], p1["tasks_done"]), (2, 1, 1))
        self.assertEqual(rep["tasks"]["done"], 1)
        self.assertIsNone(rep["cost_usd"])
        self.assertIn("not_measured", rep["provenance"])

    def test_handoff_requires_mutating_run_when_phase_has_mutating_flows(self):
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] in ("P1", "P2"):
                st["status"][tid] = {"state": "done", "at": "2026-01-01T00:00:00+09:00"}
        (self.tmp / "state/tasks.json").write_text(json.dumps(st))
        self.wf.log_event("old", "phase-done", "P1")
        self.wf.log_event("old", "phase-done", "P2")
        (self.tmp / "state/shots.json").write_text(json.dumps({"auth": {}, "flows": [
            {"name": "hull-save", "phase": "P3", "mutates": True, "steps": [{"goto": "/"}]}]}))
        self.run_cmd("claim", "h1")
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("변경 흐름 1개 미실행", out)
        res = {"ts": "2999-01-01T00:00:00+00:00", "ok": True, "phases": ["P3"], "isolation_ok": False, "restored": True, "results": []}
        (self.tmp / "state/shots-mutating-result.json").write_text(json.dumps(res))
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("격리·복원 검증 실패", out)


class Shots(unittest.TestCase):
    def test_totp_rfc6238_and_dry_run(self):
        # RFC 6238 SHA1 vector: secret "12345678901234567890", T=59 → 94287082 (8 digits)
        code = subprocess.run(["node", "--input-type=module", "-e",
            f"import {{totp}} from '{HERE / 'shots.mjs'}'; console.log(totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 59000, 30, 8))"],
            capture_output=True, text=True)
        self.assertEqual(code.stdout.strip(), "94287082", code.stderr)
        r = subprocess.run(["node", str(HERE / "shots.mjs"), "--dry-run"], capture_output=True, text=True,
                           env={**os.environ, "WF_ROOT": str(REAL)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("flows=0", r.stdout)


    def test_mutating_flows_skipped_by_default_and_need_fresh_db(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for d in ("config", "state", "reference/seed"):
                (tmp / d).mkdir(parents=True)
            shutil.copy(REAL / "config/workflow.json", tmp / "config/workflow.json")
            shutil.copy(REAL / "reference/seed/seed.json", tmp / "reference/seed/seed.json")
            (tmp / "state/shots.json").write_text(json.dumps({"auth": {"key": "k"}, "flows": [
                {"name": "view", "phase": "P3", "steps": [{"goto": "/"}]},
                {"name": "save", "phase": "P3", "mutates": True, "steps": [{"goto": "/"}]}]}))
            env = {**os.environ, "WF_ROOT": str(tmp)}
            run = lambda *a: subprocess.run(["node", str(HERE / "shots.mjs"), *a], capture_output=True, text=True, env=env, cwd=tmp)
            r = run("--dry-run")
            self.assertIn("flows=1 skipped=1", r.stdout)
            self.assertIn("SKIP save", r.stdout)
            self.assertIn("base_url=http://127.0.0.1:5273", r.stdout)
            r = run("--dry-run", "--mutating")
            self.assertIn("DRY save", r.stdout)
            r = run("--mutating")  # fresh 모드가 아니면 브라우저를 띄우기 전에 거부
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("격리된 테스트 DB가 아니다", r.stdout)
            r = subprocess.run(["node", str(HERE / "shots.mjs"), "--dry-run"], capture_output=True, text=True,
                               env={**env, "SHIPYARD_FRONTEND_PORT": "5999"}, cwd=tmp)
            self.assertIn("base_url=http://127.0.0.1:5999", r.stdout)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=1)
