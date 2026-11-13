"""예약 실행기의 결정적 부분 테스트 — 시간 창, 잠금, claude argv 조립, 알림 문구. 네트워크·LLM 없음."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import KST, load_env  # noqa: E402
from run import daily  # noqa: E402
from run.claude_cmd import ClaudeCall  # noqa: E402


class WindowTest(unittest.TestCase):
    def test_window(self):
        mk = lambda h, m: datetime(2026, 10, 3, h, m, tzinfo=KST)  # noqa: E731
        self.assertFalse(daily.in_window(mk(6, 59)))
        self.assertTrue(daily.in_window(mk(7, 0)))
        self.assertTrue(daily.in_window(mk(11, 59)))
        self.assertFalse(daily.in_window(mk(12, 0)))
        self.assertTrue(daily.in_window(mk(22, 30), "22:00", "23:00"))


class LockTest(unittest.TestCase):
    def test_lock_exclusive_and_stale(self):
        with tempfile.TemporaryDirectory() as d:
            lock = daily.Lock(Path(d) / ".lock", stale_s=60)
            self.assertTrue(lock.acquire())
            self.assertFalse(daily.Lock(Path(d) / ".lock", stale_s=60).acquire())  # 두 번째는 실패
            lock.release()
            self.assertTrue(lock.acquire())

    def test_live_holder_kept_even_when_old(self):
        """살아 있는 실행의 잠금은 stale 시간이 지나도 뺏지 않는다 — 긴 실행 도중 다음 정각 호출이 끼어들지 않게."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".lock"
            self.assertTrue(daily.Lock(path, stale_s=60, max_alive_s=600).acquire())  # 이 테스트 프로세스가 잡는다
            old = time.time() - 120
            os.utime(path, (old, old))
            self.assertFalse(daily.Lock(path, stale_s=60, max_alive_s=600).acquire())
            # 어떤 실행도 살아 있을 수 없는 시간이 지났다면 번호가 다른 프로그램에 재사용된 것 — 회수한다
            older = time.time() - 700
            os.utime(path, (older, older))
            self.assertTrue(daily.Lock(path, stale_s=60, max_alive_s=600).acquire())

    def test_max_run_covers_longest_possible_run(self):
        self.assertGreater(daily.MAX_RUN_S, daily.RESEARCH_TIMEOUT_S + 2 * daily.PRODUCE_TIMEOUT_S)
        self.assertGreater(daily.MAX_RUN_S, daily.STALE_LOCK_S)

    def test_pid_alive(self):
        self.assertTrue(daily.pid_alive(os.getpid()))
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.assertFalse(daily.pid_alive(p.pid))
        self.assertFalse(daily.pid_alive(0))

    def test_dead_holder_reclaimed_immediately(self):
        """터미널을 닫아 잠금만 남은 경우 — 3시간을 기다리지 않고 바로 회수한다."""
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".lock"
            path.mkdir()
            (path / "pid").write_text(str(p.pid), encoding="utf-8")
            lock = daily.Lock(path, stale_s=3 * 3600)
            self.assertTrue(lock.acquire())
            self.assertEqual(lock.holder_pid(), os.getpid())

    def test_live_holder_kept(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".lock"
            path.mkdir()
            (path / "pid").write_text(str(os.getpid()), encoding="utf-8")
            self.assertFalse(daily.Lock(path, stale_s=3 * 3600).acquire())

    def test_lock_without_pid_falls_back_to_age(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".lock"
            path.mkdir()
            self.assertFalse(daily.Lock(path, stale_s=60).acquire())  # 방금 만든 잠금 — 번호를 쓰는 중일 수 있다
            old = time.time() - 120
            os.utime(path, (old, old))
            self.assertTrue(daily.Lock(path, stale_s=60).acquire())


class RunStateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(daily, "RUNS_STATE", Path(self._tmp.name) / "runs.json")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_running_does_not_block_retry(self):
        """강제 종료로 running 이 남아도 그날 예약 호출을 막지 않는다(실행 중 여부는 잠금이 판단)."""
        daily.set_run_state("2026-11-13", "running", attempts=1)
        self.assertFalse(daily.already_ran("2026-11-13"))

    def test_finished_states_block(self):
        for status in ("done", "partial", "interrupted"):
            daily.set_run_state("2026-11-13", status)
            self.assertTrue(daily.already_ran("2026-11-13"), status)
        daily.set_run_state("2026-11-13", "failed")
        self.assertFalse(daily.already_ran("2026-11-13"))

    def test_attempts_survive_state_changes(self):
        daily.set_run_state("2026-11-13", "running", attempts=2)
        daily.set_run_state("2026-11-13", "error", stage="제작")
        self.assertEqual(daily.run_entry("2026-11-13")["attempts"], 2)
        self.assertEqual(daily.run_entry("2026-11-14"), {})

    def test_exit_codes(self):
        self.assertEqual(daily.exit_code_for("완료", True), 0)
        self.assertEqual(daily.exit_code_for("부분 완료", True), 3)
        self.assertEqual(daily.exit_code_for("실패", False), 1)
        self.assertEqual(daily.exit_code_for("완료", False), 1)  # 블로그가 없으면 요약이 뭐라 하든 실패


class MainRecoveryTest(unittest.TestCase):
    """main() 의 중단 복구·종료 코드 — 외부 호출(claude·알림·주제)은 모두 가짜로 바꾼다."""
    DATE = "2026-11-13"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "output"
        self.run_dir = self.out / "runs" / self.DATE
        self.lock_path = self.out / ".lock"
        self.notes: list[str] = []
        self.produced = 0
        self.summary = {"status": "완료", "completed": ["블로그 1,800자", "인스타", "쓰레드"], "failed": []}
        real_lock = daily.Lock
        from topics import select

        def fake_produce(run_dir, cfg, claude_path, attempt):
            self.produced += 1
            daily.write_json(run_dir / "summary.json", self.summary)
            return {"total_cost_usd": 5.0}, 5.0

        def fake_research(topic, run_dir, cfg, claude_path, costs=None):
            if costs is not None:
                costs.update({"market": 0.5, "youtube": 0.25, "blog": 0.25})
            return {"market": True, "youtube": True, "blog": True}

        patches = [
            mock.patch.object(daily, "OUTPUT_DIR", self.out),
            mock.patch.object(daily, "RUNS_STATE", self.out / "state" / "runs.json"),
            mock.patch.object(daily, "Lock", lambda: real_lock(self.lock_path)),
            mock.patch.object(daily, "load_config", lambda: {"schedule": {"max_attempts_per_day": 2}}),
            mock.patch.object(daily, "kst_now", lambda: datetime(2026, 11, 13, 8, 0, tzinfo=KST)),
            mock.patch.object(daily, "find_claude", lambda _=None: "claude"),
            mock.patch.object(daily, "preflight", lambda cfg: []),
            mock.patch.object(daily, "send_notification", lambda cfg, text: (self.notes.append(text), (True, "ok"))[1]),
            mock.patch.object(daily, "run_research", fake_research),
            mock.patch.object(daily, "run_produce", fake_produce),
            mock.patch.object(select, "select_topic", lambda cfg: {"title": "주제 A", "video_style": "실사", "source_ref": "a.md"}),
            mock.patch.object(select, "mark", lambda ref, status: None),
            mock.patch("builtins.print"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def _dead_pid(self) -> int:
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        return p.pid

    def test_complete_run_exits_zero_and_sums_cost(self):
        self.assertEqual(daily.main([]), daily.EXIT_OK)
        entry = daily.run_entry(self.DATE)
        self.assertEqual((entry["status"], entry["attempts"], entry["cost"]), ("done", 1, 6.0))
        self.assertIn("Claude 비용 $6.00", self.notes[-1])
        self.assertNotIn("누적", self.notes[-1])  # 오늘 첫 실행이면 누적 표시는 없다
        self.assertFalse(self.lock_path.exists())
        self.assertEqual(daily.main([]), daily.EXIT_OK)  # 같은 날 다음 정각 — 다시 돌지 않는다
        self.assertEqual(self.produced, 1)

    def test_partial_run_exits_three(self):
        self.summary = {"status": "부분 완료", "completed": ["블로그 1,800자"], "failed": ["숏츠(TTS 401)"]}
        self.assertEqual(daily.main([]), daily.EXIT_PARTIAL)
        self.assertEqual(daily.run_entry(self.DATE)["status"], "partial")

    def test_failed_run_exits_one(self):
        self.summary = {"status": "실패", "completed": [], "failed": ["블로그"]}
        self.assertEqual(daily.main([]), daily.EXIT_FAILED)
        self.assertEqual(daily.run_entry(self.DATE)["status"], "failed")

    def test_interrupted_run_is_retried_by_next_scheduled_call(self):
        """터미널을 닫아 running 상태와 잠금이 남은 뒤 — 다음 정각 호출이 이어서 실행한다."""
        daily.set_run_state(self.DATE, "running", topic="주제 A", attempts=1)
        self.lock_path.mkdir(parents=True)
        (self.lock_path / "pid").write_text(str(self._dead_pid()), encoding="utf-8")
        self.assertEqual(daily.main([]), daily.EXIT_OK)
        self.assertEqual(self.produced, 1)
        self.assertEqual(daily.run_entry(self.DATE)["attempts"], 2)

    def test_attempt_cap_stops_auto_retry_and_notifies_once(self):
        daily.set_run_state(self.DATE, "running", topic="주제 A", attempts=2)
        self.assertEqual(daily.main([]), daily.EXIT_FAILED)
        self.assertEqual(daily.run_entry(self.DATE)["status"], "interrupted")
        self.assertEqual(len(self.notes), 1)
        self.assertIn("--now", self.notes[0])
        self.assertEqual(daily.main([]), daily.EXIT_OK)  # 그날은 조용히 건너뛴다
        self.assertEqual((self.produced, len(self.notes)), (0, 1))
        self.assertEqual(daily.main(["--now"]), daily.EXIT_OK)  # 수동 실행은 상한과 무관
        self.assertEqual(self.produced, 1)

    def test_cost_accumulates_across_runs_of_the_day(self):
        self.summary = {"status": "실패", "completed": [], "failed": ["블로그"]}
        self.assertEqual(daily.main([]), daily.EXIT_FAILED)
        self.summary = {"status": "완료", "completed": ["블로그 1,800자", "인스타", "쓰레드"], "failed": []}
        self.assertEqual(daily.main([]), daily.EXIT_OK)
        entry = daily.run_entry(self.DATE)
        self.assertEqual((entry["cost"], entry["cost_day"], entry["attempts"]), (6.0, 12.0, 2))
        self.assertIn("오늘 확인된 누적 $12.00", self.notes[-1])

    def test_unknown_cost_is_not_shown_as_zero(self):
        with mock.patch.object(daily, "run_research", lambda *a, **k: {}), \
             mock.patch.object(daily, "run_produce", lambda run_dir, *a: (daily.write_json(run_dir / "summary.json", self.summary), ({}, 0.0))[1]):
            self.assertEqual(daily.main([]), daily.EXIT_OK)
        self.assertNotIn("$", self.notes[-1])
        self.assertIsNone(daily.run_entry(self.DATE)["cost"])

    def test_failed_runs_also_respect_cap(self):
        daily.set_run_state(self.DATE, "failed", attempts=2)
        self.assertEqual(daily.main([]), daily.EXIT_FAILED)
        self.assertEqual((self.produced, self.notes), (0, []))

    def test_now_while_another_run_is_alive(self):
        self.lock_path.mkdir(parents=True)
        (self.lock_path / "pid").write_text(str(os.getpid()), encoding="utf-8")
        self.assertEqual(daily.main(["--now"]), daily.EXIT_BUSY)
        self.assertEqual(daily.main([]), daily.EXIT_OK)
        self.assertEqual(self.produced, 0)
        self.assertTrue(self.lock_path.exists())  # 남의 잠금은 건드리지 않는다

    def test_no_topic_notifies_once_per_day(self):
        from topics import select
        with mock.patch.object(select, "select_topic", lambda cfg: None):
            self.assertEqual(daily.main([]), daily.EXIT_NO_TOPIC)
            self.assertEqual(daily.main([]), daily.EXIT_NO_TOPIC)
        self.assertEqual(len(self.notes), 1)


class ResearchReuseTest(unittest.TestCase):
    def test_reusable_only_with_success_record(self):
        with tempfile.TemporaryDirectory() as d:
            ok, no_meta, bad, empty = (Path(d) / n for n in ("market.md", "legacy.md", "blog.md", "youtube.md"))
            ok.write_text("# 시장 조사\n- 근거 …\n", encoding="utf-8")
            daily.write_json(daily.research_meta_path(ok), {"ok": True})
            no_meta.write_text("# 내용은 있지만 성공 기록이 없다\n", encoding="utf-8")
            bad.write_text("사용량 한도에 도달했습니다. 잠시 후 다시 시도하세요.\n", encoding="utf-8")
            daily.write_json(daily.research_meta_path(bad), {"ok": False})
            empty.write_text("", encoding="utf-8")
            daily.write_json(daily.research_meta_path(empty), {"ok": True})
            self.assertTrue(daily.research_reusable(ok))
            self.assertFalse(daily.research_reusable(no_meta))
            self.assertFalse(daily.research_reusable(bad))
            self.assertFalse(daily.research_reusable(empty))
            self.assertFalse(daily.research_reusable(Path(d) / "none.md"))

    def _run(self, run_dir: Path, responses: dict, calls: list) -> dict:
        from run.claude_cmd import ClaudeResult

        def fake_run_claude(call, claude_path, timeout_s, log_path):
            persp = log_path.stem
            calls.append(persp)
            code, payload = responses[persp]
            return ClaudeResult(code, json.dumps(payload, ensure_ascii=False), "", 1.0)

        costs: dict = {}
        with mock.patch.object(daily, "run_claude", fake_run_claude):
            res = daily.run_research({"title": "주제 A"}, run_dir, {}, "claude", costs)
        return {"res": res, "costs": costs}

    def test_failed_call_with_error_text_is_not_reused(self):
        """한도 초과처럼 실패한 호출이 오류 문장을 돌려줘도 조사 노트로 쓰지 않고, 다음 실행에서 다시 조사한다."""
        limit = {"is_error": True, "result": "사용량 한도에 도달했습니다.", "total_cost_usd": 0}
        good = {"is_error": False, "result": "# 조사 노트\n- 근거 …", "total_cost_usd": 0.5}
        with tempfile.TemporaryDirectory() as d:
            run_dir, calls = Path(d), []
            first = self._run(run_dir, {"market": (0, good), "youtube": (1, limit), "blog": (0, limit)}, calls)
            self.assertEqual(first["res"], {"market": True, "youtube": False, "blog": False})
            for persp in ("youtube", "blog"):  # 종료 코드가 0 이어도 is_error 면 실패
                note = (run_dir / "01_research" / f"{persp}.md").read_text(encoding="utf-8")
                self.assertTrue(note.startswith(daily.RESEARCH_FAIL_MARK))
                self.assertNotIn("한도", note)
            calls.clear()
            second = self._run(run_dir, {p: (0, good) for p in daily.RESEARCH_PERSPECTIVES}, calls)
            self.assertEqual(sorted(calls), ["blog", "youtube"])  # 성공했던 market 만 재사용
            self.assertEqual(second["res"], {"market": True, "youtube": True, "blog": True})
            self.assertEqual(second["costs"], {"youtube": 0.5, "blog": 0.5})


class ArgvTest(unittest.TestCase):
    def test_argv_ascii_and_flags(self):
        call = ClaudeCall(prompt="한글 프롬프트는 stdin 으로", agent="osmu-researcher",
                          allowed_tools=["WebSearch", "WebFetch"], disallowed_tools=["Bash"], max_budget_usd=2)
        argv = call.argv("claude")
        self.assertTrue(all(x.isascii() for x in argv))  # 프롬프트는 argv 에 들어가지 않는다
        self.assertIn("--agent", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "WebSearch,WebFetch")
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")

    def test_non_ascii_argv_rejected(self):
        with self.assertRaises(ValueError):
            ClaudeCall(prompt="", extra=["한글인자"]).argv("claude")

    def test_korean_paths_allowed(self):
        """사용자명·설치 폴더가 한글이어도 호출이 조립된다 — 경로는 검사 대상이 아니다."""
        claude = "C:\\Users\\홍길동\\.local\\bin\\claude.exe"  # scan-secrets:ignore
        settings = Path("/home/홍길동/OSMU_studio/config/unattended.local.json")
        argv = ClaudeCall(prompt="한글 프롬프트", agent="osmu-researcher", settings=settings).argv(claude)
        self.assertEqual(argv[0], claude)
        self.assertEqual(argv[argv.index("--settings") + 1], str(settings))
        with self.assertRaises(ValueError):  # 경로가 한글이어도 다른 인자의 한글은 여전히 거부
            ClaudeCall(prompt="", settings=settings, extra=["한글인자"]).argv(claude)


class SummaryTextTest(unittest.TestCase):
    def test_summary_text_without_summary_file(self):
        with tempfile.TemporaryDirectory() as d:
            text = daily.build_summary_text("2026-10-03", {"title": "주제 A"}, Path(d), 125 * 60, 7.123)
            self.assertTrue(text.startswith("[OSMU] 2026-10-03 실패"))
            self.assertIn("주제: 주제 A", text)
            self.assertIn("125분 · Claude 비용 $7.12", text)
            self.assertIn("이번 실행에서 확인된", text)
            self.assertIn("외부 서비스 별도", text)

    def test_summary_text_partial(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "summary.json").write_text(
                '{"status":"부분 완료","completed":["블로그 1,820자","이미지 6"],"failed":["숏츠(TTS 401)"],"skipped":["윤문(플러그인 없음)"],"decision":"페르소나 3번"}',
                encoding="utf-8")
            text = daily.build_summary_text("2026-10-03", None, Path(d), 60, None)
            self.assertIn("부분 완료 (2/3)", text)
            self.assertIn("실패: 숏츠(TTS 401)", text)
            self.assertIn("선택: 페르소나 3번", text)


class EnvLoaderTest(unittest.TestCase):
    def test_env_parse(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("# 주석\nA=1\nB='two words'\nC=\"quoted\"\nEMPTY=\n잘못된줄\n", encoding="utf-8-sig")
            env = load_env(p)
            self.assertEqual(env, {"A": "1", "B": "two words", "C": "quoted", "EMPTY": ""})


if __name__ == "__main__":
    unittest.main()
