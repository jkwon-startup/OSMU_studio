"""배포·설치 편의(D) 테스트 — 사전 점검, 브랜드 토큰 저장, 파이썬 경로, 플러그인 매니페스트."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import osmu  # noqa: E402
from run import daily  # noqa: E402
from video import frame_tokens  # noqa: E402


class PreflightTest(unittest.TestCase):
    def test_ok_on_this_machine_or_explains(self):
        problems = daily.preflight({})
        for p in problems:
            self.assertIn("→", p)  # 문제마다 해결 방법이 붙어 있다

    def test_missing_ffmpeg_reported(self):
        with mock.patch("shutil.which", return_value=None):
            problems = daily.preflight({})
        self.assertTrue(any("FFmpeg" in p for p in problems))


class ResolvePythonTest(unittest.TestCase):
    def test_missing_configured_path_falls_back(self):
        self.assertEqual(daily.resolve_python({"python_path": "/no/such/python"}), sys.executable)
        self.assertEqual(daily.resolve_python({}), sys.executable)
        self.assertEqual(daily.resolve_python({"python_path": sys.executable}), sys.executable)


class FrameWriteTest(unittest.TestCase):
    def _run(self, payload: dict, tmp: Path) -> int:
        (tmp / "frame.example.md").write_text((ROOT / "config" / "frame.example.md").read_text(encoding="utf-8"), encoding="utf-8")
        with mock.patch.object(frame_tokens, "CONFIG_DIR", tmp), mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                mock.patch("sys.stdout", io.StringIO()):
            return osmu.main(["frame-write"])

    def test_write_and_reload(self):
        tmp = Path(tempfile.mkdtemp())
        self.assertEqual(self._run({"colors": {"bg": "#042A24", "accent": "#A72524"}}, tmp), 0)
        with mock.patch.object(frame_tokens, "CONFIG_DIR", tmp):
            tok = frame_tokens.load_frame_tokens()
        self.assertEqual(tok["colors"]["bg"], "#042A24")
        self.assertEqual(tok["colors"]["text"], "#FFFFFF")  # 예시의 나머지 값 유지
        self.assertEqual(tok["caption"]["size"], 1.0)

    def test_rejects_bad_color(self):
        tmp = Path(tempfile.mkdtemp())
        self.assertEqual(self._run({"colors": {"accent": "빨강"}}, tmp), 1)
        self.assertFalse((tmp / "frame.local.md").exists())


class ConfigWriteTest(unittest.TestCase):
    def test_rejects_secret_and_bad_json(self):
        with mock.patch("sys.stdin", io.StringIO('{"GEMINI_API_KEY": "x"}')), mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(osmu.main(["config-write"]), 1)
        with mock.patch("sys.stdin", io.StringIO("{깨짐")), mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(osmu.main(["config-write"]), 1)


class PluginManifestTest(unittest.TestCase):
    def test_marketplace_points_to_plugin(self):
        mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        src = ROOT / mk["plugins"][0]["source"]
        pj = json.loads((src / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(pj["name"], mk["plugins"][0]["name"])
        self.assertTrue((src / "commands" / "install.md").exists())

    def test_versions_match(self):
        pj = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{pj["version"]}"', py)


if __name__ == "__main__":
    unittest.main()
