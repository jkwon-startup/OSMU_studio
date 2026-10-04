"""윤문 게이트 — 원문과 윤문본을 비교해 과윤문·의미 손실을 결정적으로 판정한다.

플러그인(humanize-korean) 자체 게이트는 무인 권한에서 명령치환이 거부돼 빠질 수 있으므로 여기서 직접 판정한다.

  python3 scripts/osmu.py humanize-gate ORIGINAL REWRITTEN [--keywords a,b] [--title "..."]

판정 (종료 코드):
  0 = 통과 (변경률 ≤30%, 앵커 보존)
  1 = 경고 (변경률 30~50%) — 채택하되 검수에 표시
  2 = 롤백 (변경률 >50%, 또는 수치·키워드·제목 문장 손실)
변경률은 어절이 아니라 **문자 바이그램** 기준 — 한국어는 조사 하나만 바꿔도 어절 전체가 바뀌어 어절 단위는 과대 측정된다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


def bigrams(text: str) -> Counter:
    s = re.sub(r"\s+", " ", text.strip())
    return Counter(s[i:i + 2] for i in range(len(s) - 1))


def change_rate(a: str, b: str) -> float:
    ba, bb = bigrams(a), bigrams(b)
    if not ba:
        return 0.0
    common = sum((ba & bb).values())
    total = max(sum(ba.values()), sum(bb.values()))
    return 1 - common / total if total else 0.0


NUM_RX = re.compile(r"\d[\d,.]*\s*(?:%|원|만|억|개|명|분|시간|일|주|개월|년|배|초|kg|g|km|m|cm)?")


def numbers(text: str) -> set[str]:
    return {re.sub(r"\s", "", m.group(0)).rstrip(".,") for m in NUM_RX.finditer(text)}


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            return parts[1].lstrip("-\n")
    return text


def gate(original: str, rewritten: str, keywords: list[str] | None = None, title: str | None = None) -> dict:
    o, w = strip_frontmatter(original), strip_frontmatter(rewritten)
    rate = change_rate(o, w)
    lost_numbers = sorted(numbers(o) - numbers(w))
    kw_report = {}
    for k in keywords or []:
        if k:
            kw_report[k] = {"before": o.count(k), "after": w.count(k)}
    kw_lost = [k for k, v in kw_report.items() if v["before"] > 0 and v["after"] == 0]
    title_lost = bool(title) and (title in o) and (title not in w)
    length_ratio = len(w) / max(len(o), 1)

    reasons = []
    code = 0
    if rate > 0.5:
        code, _ = 2, reasons.append(f"변경률 {rate:.0%} > 50%")
    elif rate > 0.3:
        code, _ = 1, reasons.append(f"변경률 {rate:.0%} (경고 구간)")
    if lost_numbers:
        code = 2
        reasons.append(f"수치 손실: {', '.join(lost_numbers[:6])}")
    if kw_lost:
        code = 2
        reasons.append(f"키워드 소실: {', '.join(kw_lost)}")
    if title_lost:
        code = 2
        reasons.append("제목 문장(서론 1회 삽입)이 사라짐")
    if not 0.7 <= length_ratio <= 1.3:
        code = max(code, 1)
        reasons.append(f"길이 비율 {length_ratio:.2f}")
    return {"code": code, "verdict": ["pass", "warn", "rollback"][code], "change_rate": round(rate, 3),
            "length_ratio": round(length_ratio, 3), "lost_numbers": lost_numbers, "keywords": kw_report,
            "title_lost": title_lost, "reasons": reasons}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("rewritten")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--out", help="결과 JSON 저장 경로")
    a = ap.parse_args(argv)
    res = gate(Path(a.original).read_text(encoding="utf-8"), Path(a.rewritten).read_text(encoding="utf-8"),
               [k.strip() for k in a.keywords.split(",") if k.strip()], a.title or None)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res["code"]


if __name__ == "__main__":
    sys.exit(main())
