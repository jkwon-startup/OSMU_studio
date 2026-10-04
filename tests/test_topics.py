"""주제 선택기 테스트 — 세 소스(folder / sheet / docs) 와 완료 표시. 네트워크·LLM 없음."""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from topics import select  # noqa: E402


class TopicsTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # done.json 을 임시 폴더로 돌린다
        self._orig_done = select.DONE_PATH
        select.DONE_PATH = self.dir / "state" / "done.json"

    def tearDown(self):
        select.DONE_PATH = self._orig_done
        self.tmp.cleanup()


class FolderSourceTest(TopicsTestBase):
    def _make_folder(self):
        folder = self.dir / "주제 폴더"
        folder.mkdir()
        (folder / "10. 두 번째 주제.md").write_text("# 두 번째\n영상: 모션그래픽\n본문", encoding="utf-8")
        (folder / "2. 첫 번째 주제.md").write_text(
            "---\ntitle: AI로 블로그 자동화하기\nvideo_style: 실사\n---\n기획 메모입니다.", encoding="utf-8")
        (folder / "3. 세 번째.md").write_text("내용만 있는 파일", encoding="utf-8")
        return folder

    def test_natural_order_and_frontmatter(self):
        folder = self._make_folder()
        cfg = {"topics": {"source": "folder", "path": str(folder)}}
        t = select.select_topic(cfg)
        self.assertEqual(t["title"], "AI로 블로그 자동화하기")  # "2." 가 "10." 보다 먼저
        self.assertEqual(t["video_style"], "photoreal")
        self.assertIn("기획 메모", t["memo"])
        self.assertTrue(t["source_ref"].startswith("folder:"))

    def test_done_advances_and_body_style(self):
        folder = self._make_folder()
        cfg = {"topics": {"source": "folder", "path": str(folder)}}
        t1 = select.select_topic(cfg)
        select.mark(t1["source_ref"], "done")
        t2 = select.select_topic(cfg)
        self.assertEqual(t2["title"], "세 번째")            # 3. 이 10. 보다 먼저
        self.assertEqual(t2["video_style"], "photoreal")   # 표기 없음 → 기본값
        select.mark(t2["source_ref"], "done")
        t3 = select.select_topic(cfg)
        self.assertEqual(t3["title"], "두 번째")            # H1 사용
        self.assertEqual(t3["video_style"], "motion")      # 본문 "영상:" 줄

    def test_retry_limit_skips_topic(self):
        folder = self._make_folder()
        cfg = {"topics": {"source": "folder", "path": str(folder)}}
        t1 = select.select_topic(cfg)
        select.mark(t1["source_ref"], "retry")
        self.assertEqual(select.select_topic(cfg)["source_ref"], t1["source_ref"])  # 1회 실패는 재시도
        select.mark(t1["source_ref"], "retry")
        self.assertNotEqual(select.select_topic(cfg)["source_ref"], t1["source_ref"])  # 2회 초과 → 건너뜀


class SheetSourceTest(TopicsTestBase):
    ROWS = [
        ["발행일", "주제", "영상스타일", "메모"],
        ["2026-10-02", "어제 주제", "실사", ""],
        ["2026.10.3", "오늘 주제", "모션그래픽", "오늘 메모"],
        ["10/4", "내일 주제", "", ""],
    ]

    def test_csv_cp949_today(self):
        p = self.dir / "topics.csv"
        with open(p, "w", encoding="cp949", newline="") as f:
            csv.writer(f).writerows(self.ROWS)
        cfg = {"topics": {"source": "sheet", "path": str(p)}}
        t = select.select_topic(cfg, today=date(2026, 10, 3))
        self.assertEqual(t["title"], "오늘 주제")
        self.assertEqual(t["video_style"], "motion")
        self.assertEqual(t["date"], "2026-10-03")

    def test_xlsx_missing_today_skip_vs_catch_up(self):
        import openpyxl
        p = self.dir / "topics.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        for r in self.ROWS:
            ws.append(r)
        wb.save(p)
        cfg = {"topics": {"source": "sheet", "path": str(p)}}
        self.assertIsNone(select.select_topic(cfg, today=date(2026, 10, 5)))  # skip 기본
        cfg["topics"]["on_missing"] = "catch_up"
        t = select.select_topic(cfg, today=date(2026, 10, 5))
        self.assertEqual(t["title"], "어제 주제")  # 가장 오래된 미완료


class DocsSourceTest(TopicsTestBase):
    def test_docs_csv_in_order(self):
        p = self.dir / "topics.local.csv"
        p.write_text("순서,주제,영상스타일,메모\n1,첫 기획,실사,메모1\n2,둘째 기획,모션,\n", encoding="utf-8-sig")
        cfg = {"topics": {"source": "docs", "path": str(p)}}
        t = select.select_topic(cfg)
        self.assertEqual(t["title"], "첫 기획")
        select.mark(t["source_ref"], "done")
        self.assertEqual(select.select_topic(cfg)["video_style"], "motion")


if __name__ == "__main__":
    unittest.main()
