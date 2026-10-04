"""규칙 파일 존재·필수 섹션·금지 어휘 목록 파싱 테스트."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules"

REQUIRED = {
    "persona.md": ["1단계", "자동 선택 기준", "2단계", "핵심내용 5가지"],
    "copy.md": ["친구 톤", "8개 후킹 패턴", "광고티 어휘", "자가 검증", "채널별 변형"],
    "blog-naver.md": ["제목", "서론", "본론", "결론", "발행 전 체크리스트", "1,500자"],
    "blog-sge.md": ["E-E-A-T", "틈새", "자주 묻는 질문"],
    "writing-absolute.md": ["항상 피한다", "항상 지킨다"],
    "instagram.md": ["3:4", "해시태그", "검수 포인트"],
    "threads.md": ["반말", "혼잣말", "존댓말", "해시태그 1개"],
    "shorts-script.md": ["7자/초", "beats", "photoreal", "motion", "tts_text"],
    "image-prompts.md": ["No text", "16:9", "3:4"],
    "review-checklist.md": ["pass", "fix", "fail"],
    "untrusted-input.md": ["데이터", "지시로 따르지 않는다"],
    "data/korea-distribution.md": ["지역", "연령대", "직업", "CC BY 4.0"],
}


class RulesTest(unittest.TestCase):
    def test_required_sections_present(self):
        for name, needles in REQUIRED.items():
            text = (RULES / name).read_text(encoding="utf-8")
            for n in needles:
                self.assertIn(n, text, f"{name} 에 '{n}' 없음")

    def test_ad_blacklist_parses(self):
        text = (RULES / "copy.md").read_text(encoding="utf-8")
        m = re.search(r"\*\*광고티 어휘\*\*:\s*(.+)", text)
        self.assertIsNotNone(m)
        words = [w.strip() for w in m.group(1).split("·")]
        self.assertGreaterEqual(len(words), 15)
        self.assertIn("프리미엄", words)

    def test_no_personal_paths_in_rules(self):
        for p in RULES.rglob("*.md"):
            self.assertNotRegex(p.read_text(encoding="utf-8"), r"/Users/[A-Za-z]", f"{p} 에 개인 경로")


if __name__ == "__main__":
    unittest.main()
