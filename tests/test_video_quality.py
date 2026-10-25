"""영상 품질(B·C) 테스트 — 자막 정렬, 비율·전환 검증, 배경음악, HTML 템플릿, 브랜드 토큰."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from video import align, build, frame_tokens, html_render, plan_schema  # noqa: E402

FF = shutil.which("ffmpeg")


def _has_chromium() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


class AlignTest(unittest.TestCase):
    WORDS = [{"text": "세", "start": 0.0, "end": 0.2}, {"text": "가지만", "start": 0.2, "end": 0.6},
             {"text": "바꾸면", "start": 0.6, "end": 1.0}, {"text": "됩니다", "start": 1.0, "end": 1.5},
             {"text": "먼저", "start": 1.7, "end": 2.0}, {"text": "알림부터", "start": 2.0, "end": 2.5},
             {"text": "끄세요", "start": 2.5, "end": 3.0}]
    TEXT = "3가지만 바꾸면 됩니다. 먼저 알림부터 끄세요."

    def test_hangul_kept_and_digits_interpolated(self):
        times = align.display_char_times(self.TEXT, self.WORDS, 0.0, 3.0)
        self.assertEqual(len(times), len(self.TEXT) + 1)
        self.assertAlmostEqual(times[self.TEXT.index("먼저")], 1.7, places=2)  # 한글이 지워지지 않고 맞춰진다
        self.assertLessEqual(times[0], times[self.TEXT.index("바")])            # 숫자 '3' 은 앞쪽으로 보간
        self.assertEqual(times, sorted(times))

    def test_chunk_long_sentence(self):
        caps = align.chunk_captions(self.TEXT, self.WORDS, 0.0, 3.0, max_line=8)
        self.assertGreaterEqual(len(caps), 2)
        self.assertEqual(caps[0]["start"], 0.0)
        self.assertEqual(caps[-1]["end"], 3.0)
        for a, b in zip(caps, caps[1:]):
            self.assertLessEqual(a["end"], b["start"] + 1e-6)
        for c in caps:
            self.assertTrue(all(len(ln) <= 8 for ln in c["text"].split("\n")), c)

    def test_without_words_uses_char_ratio(self):
        caps = align.chunk_captions("가나다라마바사아 자차카타파하 가나다라마바사아 자차카타파하", [], 0.0, 4.0, max_line=8)
        self.assertGreaterEqual(len(caps), 2)
        self.assertTrue(0 < caps[1]["start"] < 4.0)


class PlanTest(unittest.TestCase):
    def test_aspect_transition_validation(self):
        plan = {"duration_s": 6, "aspect": "4:5", "transition": "spin",
                "shots": [{"id": "a", "start": 0, "end": 6, "transition": "warp", "source": {"type": "endcard", "props": {}}}]}
        errs = " ".join(plan_schema.validate(plan))
        self.assertIn("aspect", errs)
        self.assertIn("transition 'spin'", errs)
        self.assertIn("transition 'warp'", errs)

    def test_unknown_template_lists_available(self):
        plan = {"duration_s": 6, "shots": [{"id": "a", "start": 0, "end": 6, "source": {"type": "motion", "template": "nope"}}]}
        self.assertIn("kinetic_full", " ".join(plan_schema.validate(plan)))


class HtmlTemplateTest(unittest.TestCase):
    def test_all_templates_listed_with_params(self):
        names = html_render.list_templates()
        for t in ("kinetic_full", "bullet_card", "data_bars", "endcard"):
            self.assertIn(t, names)
        self.assertIn("sub", [p["name"] for p in html_render.template_params("endcard")])

    def test_fill_escapes_and_types(self):
        out = html_render.fill("<b>{{title:text=기본}}</b>{{n:number=1}}{{c:color=#000000}}",
                               {"title": "<b>x</b>", "n": "2.50", "c": "red"})
        self.assertIn("&lt;b&gt;x", out)
        self.assertIn("2.5", out)
        self.assertIn("#000000", out)  # 잘못된 색은 기본값
        self.assertEqual(html_render.fill("{{title:text=기본}}", {}), "기본")

    def test_page_injection(self):
        page = html_render.build_page("endcard", {"title": "끝</script>"}, build.PALETTE, 3.0, 1080, 1920, True)
        self.assertIn("--dur:3.000s", page)
        self.assertIn('class="fade-out"', page)
        data = page.split("window.OSMU=")[1].split(";</script>")[0]
        self.assertNotIn("</script>", data)

    @unittest.skipUnless(FF and _has_chromium(), "Playwright Chromium 필요")
    def test_render_video_length(self):
        out = Path(tempfile.mkdtemp()) / "k.mp4"
        with html_render.Renderer() as r:
            r.video("kinetic_full", {"text": "하루 30분"}, 1.0, out, build.PALETTE, 540, 960)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                 capture_output=True, text=True).stdout)
        self.assertAlmostEqual(d, 1.0, delta=0.1)


class BgmTest(unittest.TestCase):
    @unittest.skipUnless(FF, "ffmpeg 필요")
    def test_pick_bgm(self):
        tmp = Path(tempfile.mkdtemp())
        for n in ("a.mp3", "b.mp3"):
            subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=2", str(tmp / n)], check=True)
        (tmp / "notes.txt").write_text("x")
        with mock.patch.object(build, "BGM_DIR", tmp):
            p, _ = build.pick_bgm({}, Path("2026-10-25"))
            self.assertIn(p.name, ("a.mp3", "b.mp3"))
            self.assertEqual(build.pick_bgm({}, Path("2026-10-25"))[0], p)  # 같은 날은 같은 곡
            self.assertIsNone(build.pick_bgm({"bgm": {"enabled": False}}, Path("x"))[0])
            p2, note = build.pick_bgm({"bgm": {"file": "없는곡.mp3"}}, Path("x"))
            self.assertIsNone(p2)
            self.assertIn("없는곡", note)
        with mock.patch.object(build, "BGM_DIR", tmp / "nope"):
            self.assertIn("비어", build.pick_bgm({}, Path("x"))[1])


class FrameTokenTest(unittest.TestCase):
    def test_parse(self):
        text = '---\n# 주석\ncolors:\n  bg: "#111111"   # 배경\n  accent: #FF0000\n  text: nothex\ncaption:\n  size: 9\n---\n본문'
        raw = frame_tokens.parse_frontmatter(text)
        self.assertEqual(raw["colors"]["bg"], "#111111")
        self.assertEqual(raw["colors"]["accent"], "#FF0000")

    def test_load_filters_invalid(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "frame.local.md").write_text('---\ncolors:\n  bg: "#111111"\n  text: nothex\ncaption:\n  size: 9\n---\n', encoding="utf-8")
        with mock.patch.object(frame_tokens, "CONFIG_DIR", tmp):
            tok = frame_tokens.load_frame_tokens()
            self.assertEqual(tok["colors"], {"bg": "#111111"})
            self.assertEqual(tok["caption"]["size"], 1.6)
            colors = build.brand_colors({"brand": {"colors": {"accent": "#00FF00", "bg": "bad"}}})
        self.assertEqual(colors["bg"], "#111111")      # frame.md 가 우선
        self.assertEqual(colors["accent"], "#00FF00")  # config brand.colors
        self.assertEqual(colors["text"], "#FFFFFF")    # 기본값


if __name__ == "__main__":
    unittest.main()
