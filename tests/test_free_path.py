"""무료 경로·폴백·설정 호환 테스트 — 네트워크 없이 (외부 호출은 가짜로 바꾼다)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import common  # noqa: E402
from image import generate, stock  # noqa: E402
from video import tts  # noqa: E402

FF = shutil.which("ffmpeg")


def _tone(out: Path, seconds: float = 0.5) -> None:
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-codec:a", "libmp3lame", str(out)], check=True)


class TtsChainTest(unittest.TestCase):
    def test_chain_order_and_unknown(self):
        self.assertEqual(tts.provider_chain("elevenlabs", {}), ["elevenlabs", "edge", "silent"])
        self.assertEqual(tts.provider_chain("edge", {"tts_fallback": ["silent"]}), ["edge", "silent"])
        self.assertEqual(tts.provider_chain("오타", {"tts_fallback": "bad"}), ["edge", "silent"])
        self.assertEqual(tts.provider_chain("gemini", {"tts_fallback": []}), ["gemini"])

    def test_precheck_missing_keys(self):
        self.assertIn("ELEVENLABS_API_KEY", tts._precheck("elevenlabs", {}, {}))
        self.assertIn("GEMINI_API_KEY", tts._precheck("gemini", {}, {}))
        self.assertIsNone(tts._precheck("edge", {}, {}))

    @unittest.skipUnless(FF, "ffmpeg 필요")
    def test_fallback_to_edge_then_silent(self):
        run = Path(tempfile.mkdtemp())
        sdir = run / "08_shorts"
        sdir.mkdir(parents=True)
        script = {"duration_s": 3, "beats": [{"id": "hook", "narration": "하루 30분, 진짜 될까요?", "tts": "하루 삼십 분, 진짜 될까요?"}]}
        (sdir / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

        def fake_edge(text, out, cfg):
            _tone(out)
            return True, "ok", [{"text": "하루", "start": 0.0, "end": 0.2}]

        with mock.patch.object(tts, "load_env", return_value={}), mock.patch.object(tts, "synth_edge", fake_edge):
            t = tts.run(run, {}, "elevenlabs")  # 키 없음 → edge
        self.assertEqual(t["provider"], "edge")
        self.assertEqual(t["fallback"][0]["provider"], "elevenlabs")
        self.assertEqual(t["units"][0]["words"][0]["text"], "하루")
        self.assertTrue((sdir / "narration.mp3").exists())

        with mock.patch.object(tts, "load_env", return_value={}), \
                mock.patch.object(tts, "synth_edge", lambda *a: (False, "네트워크 차단", [])):
            t = tts.run(run, {}, "edge")  # edge 실패 → 무음
        self.assertEqual(t["provider"], "silent")
        self.assertNotIn("words", t["units"][0])
        self.assertGreaterEqual(t["total_s"], 0.8)


class StockTest(unittest.TestCase):
    def test_query_from_prompt(self):
        q = stock.query_from_prompt("Photorealistic photo of a laptop on a wooden desk in a cafe, soft morning light. No text, no logos.")
        self.assertEqual(q, "laptop wooden desk cafe")
        self.assertEqual(stock.query_from_prompt(""), "workspace")

    def test_orientation(self):
        self.assertEqual(stock.orientation("16:9"), "landscape")
        self.assertEqual(stock.orientation("9:16"), "portrait")
        self.assertEqual(stock.orientation("1:1"), "square")

    def test_no_keys_message(self):
        found, err = stock.search("photo", "desk", "16:9", {})
        self.assertEqual(found, [])
        self.assertIn("pexels.com/api", err)

    def test_fetch_skips_used_and_records_credit(self):
        tmp = Path(tempfile.mkdtemp())
        cands = [{"id": "pexels:1", "url": "u1", "author": "A", "page": "p1", "source": "Pexels"},
                 {"id": "pexels:2", "url": "u2", "author": "B", "page": "p2", "source": "Pexels"}]
        got = []
        with mock.patch.object(stock, "search", return_value=(cands, "")), \
                mock.patch.object(stock, "_download", lambda url, out: (got.append(url), out.write_bytes(b"x"))):
            stock.fetch("photo", "desk", "16:9", tmp / "a.jpg", {}, tmp / "credits.json")
            stock.fetch("photo", "desk", "16:9", tmp / "b.jpg", {}, tmp / "credits.json")
        self.assertEqual(got, ["u1", "u2"])  # 같은 사진 반복 안 함
        credits = json.loads((tmp / "credits.json").read_text(encoding="utf-8"))
        self.assertEqual([c["file"] for c in credits], ["a.jpg", "b.jpg"])
        self.assertEqual(credits[1]["author"], "B")

    def test_generate_falls_back_to_stock(self):
        run = Path(tempfile.mkdtemp())
        items = [{"file": "blog_1.jpg", "ratio": "16:9", "prompt": "laptop on desk", "query": "laptop desk"}]
        with mock.patch.object(generate, "load_env", return_value={"PEXELS_API_KEY": "k"}), \
                mock.patch.object(generate, "gemini_image", return_value=(False, "HTTP 429 quota")), \
                mock.patch.object(generate, "stock_image", return_value=(True, "Pexels · A")) as st:
            res = generate.generate_all(run, items, "gemini", {})
        self.assertTrue(res[0]["ok"])
        self.assertIn("스톡", res[0]["detail"])
        st.assert_called_once()

    def test_generate_no_fallback_without_key(self):
        run = Path(tempfile.mkdtemp())
        items = [{"file": "blog_1.jpg", "ratio": "16:9", "prompt": "x"}]
        with mock.patch.object(generate, "load_env", return_value={}), \
                mock.patch.object(generate, "gemini_image", return_value=(False, "HTTP 429")):
            res = generate.generate_all(run, items, "gemini", {})
        self.assertFalse(res[0]["ok"])


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "config.example.json").write_text(json.dumps(
            {"image_provider": "stock", "tts_provider": "edge", "bgm": {"enabled": True, "volume": 0.15}, "brand": {"name": "예시"}},
            ensure_ascii=False), encoding="utf-8")
        self.patch = mock.patch.object(common, "CONFIG_DIR", self.tmp)
        self.patch.start()
        common._warned.clear()

    def tearDown(self):
        self.patch.stop()

    def test_defaults_fill_old_config(self):
        (self.tmp / "config.local.json").write_text(json.dumps({"brand": {"name": "내 브랜드"}, "bgm": {"volume": 0.3}},
                                                                 ensure_ascii=False), encoding="utf-8")
        cfg = common.load_config()
        self.assertEqual(cfg["brand"]["name"], "내 브랜드")
        self.assertEqual(cfg["tts_provider"], "edge")
        self.assertEqual(cfg["bgm"], {"enabled": True, "volume": 0.3})

    def test_invalid_choice_falls_back(self):
        (self.tmp / "config.local.json").write_text(json.dumps({"image_provider": "midjourney"}), encoding="utf-8")
        self.assertEqual(common.load_config()["image_provider"], "stock")

    def test_broken_local_json(self):
        (self.tmp / "config.local.json").write_text("{ 깨진 json", encoding="utf-8")
        self.assertEqual(common.load_config()["tts_provider"], "edge")


class RedactTest(unittest.TestCase):
    def test_env_values_and_patterns(self):
        env = {"GEMINI_API_KEY": "my-secret-value-123"}
        fake_sk = "sk" + "-" + "abcdefghijklmnopqrstu"  # 커밋 비밀값 검사에 걸리지 않게 실행 중에 조립
        fake_hook = "https://hooks.slack" + ".com/services/" + "T0/B0/xyz"
        s = f"error my-secret-value-123 and {fake_sk} and {fake_hook} ok"
        out = common.redact(s, env)
        self.assertNotIn("my-secret-value-123", out)
        self.assertNotIn(fake_sk, out)
        self.assertNotIn(fake_hook, out)
        self.assertTrue(out.endswith("ok"))

    def test_short_values_kept(self):
        self.assertEqual(common.redact("on slack", {"NOTIFY": "slack"}), "on slack")


if __name__ == "__main__":
    unittest.main()
