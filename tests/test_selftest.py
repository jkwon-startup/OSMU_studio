"""연결 검사(selftest)의 Pixverse 판정 — 고른 서비스는 실제로 만들어 봐야 통과. 네트워크·CLI 없음(모두 가짜)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from setup import selftest  # noqa: E402
from image import generate  # noqa: E402


def _cli_ok(cmd, **kw):
    out = '{"credits": 300}' if "account" in cmd else "{}"
    return subprocess.CompletedProcess(cmd, 0, out, "")


class PixverseCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.object(selftest, "OUT", Path(self._tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def test_not_selected_and_missing_is_skipped(self):
        with mock.patch.object(selftest, "_pixverse_cmd", lambda env: None):
            ok, detail = selftest.check_pixverse({}, {"image_provider": "stock"})
        self.assertIsNone(ok)
        self.assertIn("건너뜀", detail)

    def test_selected_but_missing_fails_with_next_step(self):
        with mock.patch.object(selftest, "_pixverse_cmd", lambda env: None):
            ok, detail = selftest.check_pixverse({}, {"image_provider": "pixverse"})
        self.assertIs(ok, False)
        self.assertIn("npm install -g pixverse", detail)

    def test_not_selected_checks_login_only(self):
        with mock.patch.object(selftest, "_pixverse_cmd", lambda env: ["pixverse"]), \
             mock.patch.object(selftest.subprocess, "run", _cli_ok), \
             mock.patch.object(generate, "pixverse_image", side_effect=AssertionError("크레딧을 쓰면 안 된다")):
            ok, detail = selftest.check_pixverse({}, {"image_provider": "stock"})
        self.assertIs(ok, True)
        self.assertIn("로그인됨", detail)

    def test_selected_must_generate_an_image(self):
        def fake_image(prompt, ratio, out, env, cfg, ref=None):
            from PIL import Image
            Image.new("RGB", (30, 40)).save(out)
            return True, "model"

        with mock.patch.object(selftest, "_pixverse_cmd", lambda env: ["pixverse"]), \
             mock.patch.object(selftest.subprocess, "run", _cli_ok):
            with mock.patch.object(generate, "pixverse_image", fake_image):
                ok, detail = selftest.check_pixverse({}, {"image_provider": "pixverse"})
            self.assertIs(ok, True)
            self.assertIn("이미지 1장 생성", detail)
            with mock.patch.object(generate, "pixverse_image", lambda *a, **k: (False, "exit 1: insufficient credits")):
                ok, detail = selftest.check_pixverse({}, {"image_provider": "pixverse"})
            self.assertIs(ok, False)
            self.assertIn("이미지 생성 실패", detail)

    def test_login_failure_fails(self):
        fail = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "not logged in")  # noqa: E731
        with mock.patch.object(selftest, "_pixverse_cmd", lambda env: ["pixverse"]), \
             mock.patch.object(selftest.subprocess, "run", fail):
            ok, detail = selftest.check_pixverse({}, {"image_provider": "pixverse"})
        self.assertIs(ok, False)
        self.assertIn("pixverse auth login", detail)


if __name__ == "__main__":
    unittest.main()
