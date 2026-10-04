"""예약 실행기의 결정적 부분 테스트 — 시간 창, 잠금, claude argv 조립, 알림 문구. 네트워크·LLM 없음."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

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
            # stale: mtime 을 과거로 돌리면 회수된다
            old = time.time() - 120
            os.utime(Path(d) / ".lock", (old, old))
            self.assertTrue(daily.Lock(Path(d) / ".lock", stale_s=60).acquire())


class ArgvTest(unittest.TestCase):
    def test_argv_ascii_and_flags(self):
        call = ClaudeCall(prompt="한글 프롬프트는 stdin 으로", agent="osmu-researcher",
                          allowed_tools=["WebSearch", "WebFetch"], disallowed_tools=["Bash"], max_budget_usd=2)
        argv = call.argv("claude")
        self.assertTrue(all(x.isascii() for x in argv))
        self.assertIn("--agent", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "WebSearch,WebFetch")
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")

    def test_non_ascii_argv_rejected(self):
        with self.assertRaises(ValueError):
            ClaudeCall(prompt="", extra=["한글인자"]).argv("claude")


class SummaryTextTest(unittest.TestCase):
    def test_summary_text_without_summary_file(self):
        with tempfile.TemporaryDirectory() as d:
            text = daily.build_summary_text("2026-10-03", {"title": "주제 A"}, Path(d), 125 * 60, 7.123)
            self.assertTrue(text.startswith("[OSMU] 2026-10-03 실패"))
            self.assertIn("주제: 주제 A", text)
            self.assertIn("125분 · 추정 $7.12", text)

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
