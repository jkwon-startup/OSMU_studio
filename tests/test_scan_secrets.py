"""비밀값 검사 테스트 — 가짜 값으로만 검증한다 (실제 키 형태를 코드에 두지 않는다)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from publish import scan_secrets  # noqa: E402


class ScanSecretsTest(unittest.TestCase):
    def _scan_text(self, text: str):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.md"
            p.write_text(text, encoding="utf-8")
            return [name for _, _, name in scan_secrets.scan([p])]

    def test_personal_paths_flagged(self):
        self.assertIn("macOS 개인 경로", self._scan_text("경로: /Users/someone/Documents/x"))  # scan-secrets:ignore
        self.assertIn("Windows 개인 경로", self._scan_text(r"경로: C:\Users\someone\x"))  # scan-secrets:ignore

    def test_placeholders_allowed(self):
        self.assertEqual([], self._scan_text("/Users/<username>/x 와 C:\\Users\\<username>\\x 는 예시"))

    def test_fake_tokens_flagged(self):
        fake_tg = "1234567890:" + "A" * 35
        fake_google = "AIza" + "x" * 35
        slack = "https://hooks.slack.com/" + "services/x"  # scan-secrets:ignore
        names = self._scan_text(f"a={fake_tg}\nb={fake_google}\nc={slack}")
        self.assertIn("텔레그램 봇 토큰", names)
        self.assertIn("Google API 키", names)
        self.assertIn("Slack 웹훅", names)

    def test_clean_text(self):
        self.assertEqual([], self._scan_text("SLACK_WEBHOOK_URL=\nGEMINI_API_KEY=\n보통 문장입니다."))


if __name__ == "__main__":
    unittest.main()
