"""숏츠 합성 결정적 테스트 — 외부 서비스 없이 단색 장면 + 무음 내레이션으로 끝까지 만든다 (FFmpeg·Pillow·폰트 필요)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from video import build, plan_schema  # noqa: E402
from checks import humanize_gate  # noqa: E402

SCRIPT = {
    "duration_s": 6, "style": "photoreal", "thumbnail_text": "테스트 문구",
    "beats": [
        {"id": "hook", "narration": "하루 30분, 진짜 될까요?", "caption": "하루 30분", "scene_prompt": "x", "target_s": 2},
        {"id": "core_1", "narration": "세팅 시간은 뺀 숫자예요. 글 한 편만 센 거죠.", "caption": "세팅 시간", "scene_prompt": "x", "target_s": 3},
        {"id": "outro", "narration": "오늘 밤 타이머를 맞춰 보세요.", "caption": "타이머", "scene_prompt": "x", "target_s": 1},
    ],
    "full_narration": "", "tts_text": "",
}
TIMING = {"total_s": 6.0, "units": [
    {"beat": "hook", "text": "하루 30분, 진짜 될까요?", "start": 0.0, "end": 1.6},
    {"beat": "core_1", "text": "세팅 시간은 뺀 숫자예요.", "start": 1.8, "end": 3.2},
    {"beat": "core_1", "text": "글 한 편만 센 거죠.", "start": 3.4, "end": 4.4},
    {"beat": "outro", "text": "오늘 밤 타이머를 맞춰 보세요.", "start": 4.6, "end": 5.8},
]}


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg 필요")
class VideoBuildTest(unittest.TestCase):
    def _make_run(self, style: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        sdir = tmp / "08_shorts"
        (sdir / "scenes").mkdir(parents=True)
        (sdir / "script.json").write_text(json.dumps({**SCRIPT, "style": style}, ensure_ascii=False), encoding="utf-8")
        (sdir / "timing.json").write_text(json.dumps(TIMING), encoding="utf-8")
        subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "6",
                        "-codec:a", "libmp3lame", str(sdir / "narration.mp3")], check=True)
        from PIL import Image
        for i, bid in enumerate(["hook", "core_1", "outro"]):
            Image.new("RGB", (1080, 1920), (40 + i * 60, 80, 120)).save(sdir / "scenes" / f"{bid}.jpg", "JPEG")
        return tmp

    def test_auto_plan_validates(self):
        for style in ("photoreal", "motion"):
            plan = plan_schema.auto_plan(SCRIPT, TIMING, style, "gemini")
            self.assertEqual(plan_schema.validate(plan), [], f"{style}: {plan_schema.validate(plan)}")
            self.assertEqual(plan["shots"][-1]["source"]["type"], "endcard")

    def test_plan_gap_detected(self):
        plan = plan_schema.auto_plan(SCRIPT, TIMING, "photoreal", "gemini")
        plan["shots"][1]["start"] += 0.5
        self.assertTrue(any("빈틈" in e for e in plan_schema.validate(plan)))

    def test_build_photoreal_without_services(self):
        run = self._make_run("photoreal")
        plan = plan_schema.auto_plan(SCRIPT, TIMING, "photoreal", "gemini")
        (run / "08_shorts" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        review = build.build(run, {"brand": {}})
        self.assertTrue(review["duration_ok"], review)
        self.assertTrue((run / "08_shorts" / "shorts.mp4").exists())
        self.assertTrue((run / "08_shorts" / "frame_sheet.jpg").exists())

    def test_build_motion_fallback_cards(self):
        run = self._make_run("motion")
        plan = plan_schema.auto_plan(SCRIPT, TIMING, "motion", "gemini")
        (run / "08_shorts" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        from video import html_render
        orig, orig_av = build.render_remotion, html_render.available
        build.render_remotion = lambda *a, **k: False  # Node·Playwright 없는 환경 가정 → Pillow 카드
        html_render.available = lambda: (False, "Playwright 미설치")
        try:
            review = build.build(run, {"brand": {"colors": {"accent": "#E11D48"}}, "bgm": {"enabled": False}})
        finally:
            build.render_remotion, html_render.available = orig, orig_av
        self.assertTrue(review["duration_ok"], review)
        self.assertTrue(any("정적 카드" in n for n in review["notes"]), review["notes"])
        self.assertEqual(review["motion"].get("card"), 3)

    def test_build_square_with_transitions(self):
        run = self._make_run("photoreal")
        plan = plan_schema.auto_plan(SCRIPT, TIMING, "photoreal", "gemini", "1:1", "slide_left")
        plan["shots"][1]["transition"] = "cut"  # 컷과 전환 섞기
        (run / "08_shorts" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        review = build.build(run, {"brand": {}, "bgm": {"enabled": False}})
        self.assertTrue(review["duration_ok"], review)
        self.assertEqual(review["aspect"], "1:1")
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "csv=p=0", str(run / "08_shorts" / "shorts.mp4")], capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "1080,1080")
        self.assertTrue(review["seams_sheet"])


class HumanizeGateTest(unittest.TestCase):
    def test_pass_and_rollback(self):
        o = "하루 30분이면 됩니다. 세팅 시간은 뺀 숫자예요. AI 블로그 자동화는 반자동입니다."
        w_small = "하루 30분이면 됩니다. 세팅 시간은 뺀 숫자죠. AI 블로그 자동화는 반자동입니다."
        self.assertEqual(humanize_gate.gate(o, w_small, ["AI 블로그 자동화"])["verdict"], "pass")
        w_lost = "하루 삼십 분이면 됩니다. 세팅 시간은 뺀 숫자죠. 블로그는 반자동입니다."
        res = humanize_gate.gate(o, w_lost, ["AI 블로그 자동화"])
        self.assertEqual(res["verdict"], "rollback")
        self.assertIn("AI 블로그 자동화", res["keywords"])
        self.assertTrue(res["lost_numbers"])

    def test_change_rate_bigram(self):
        self.assertAlmostEqual(humanize_gate.change_rate("가나다라", "가나다라"), 0.0)
        self.assertGreater(humanize_gate.change_rate("가나다라마바사", "완전히 다른 문장입니다"), 0.8)


if __name__ == "__main__":
    unittest.main()
