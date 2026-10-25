"""채널 규격 결정적 검사 — LLM 없이 글자 수·해시태그·제목·키워드·이미지 비율·영상 길이를 확인한다.

사용: python3 scripts/osmu.py check <run_dir> [--only blog,instagram,threads,images,shorts]
출력: <run_dir>/checks.json, 콘솔 요약. 실패 항목이 있으면 종료 코드 1 (경고만 있으면 0).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT  # noqa: E402

EMOJI_RX = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF⭐✅❌]")
HASHTAG_RX = re.compile(r"(?<!\w)#[\w가-힣_]+")
SUPERLATIVES = ["최고의", "유일한", "1위", "100% 보장", "완벽한", "혁신적인", "프리미엄", "럭셔리"]


def _frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}, text
    fm: dict = {}
    for line in parts[0].splitlines()[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
            else:
                v = v.strip("'\"")
            fm[k.strip()] = v
    return fm, parts[1].lstrip("-\n")


def _no_ws_len(s: str) -> int:
    return len(re.sub(r"\s", "", s))


def _ad_blacklist() -> list[str]:
    text = (ROOT / "rules" / "copy.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*광고티 어휘\*\*:\s*(.+)", text)
    return [w.strip() for w in m.group(1).split("·")] if m else []


class Report:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, channel: str, name: str, ok: bool, detail: str = "", level: str = "fail"):
        self.items.append({"channel": channel, "check": name, "ok": bool(ok), "detail": detail, "level": level if not ok else "ok"})

    @property
    def failed(self) -> list[dict]:
        return [i for i in self.items if not i["ok"] and i["level"] == "fail"]

    @property
    def warned(self) -> list[dict]:
        return [i for i in self.items if not i["ok"] and i["level"] == "warn"]


def check_blog(run: Path, r: Report) -> None:
    p = run / "05_blog.md"
    if not p.exists():
        p = run / "05_blog.draft.md"
    if not p.exists():
        r.add("blog", "exists", False, "05_blog.md 없음")
        return
    fm, body = _frontmatter(p.read_text(encoding="utf-8"))
    title = str(fm.get("title", "")).strip()
    kw = str(fm.get("main_keyword", "")).strip()
    r.add("blog", "title_exists", bool(title), "frontmatter title 없음")
    r.add("blog", "title_length", 0 < len(title) <= 30, f"제목 {len(title)}자 (25자 내외, 최대 30)", "warn" if len(title) <= 34 else "fail")
    r.add("blog", "keyword_first", bool(kw) and title.startswith(kw), f"메인 키워드 '{kw}' 가 제목 맨 앞인가", "warn")
    r.add("blog", "title_in_body_once", title != "" and body.count(title) >= 1, "서론에 제목 문장 그대로 1회 삽입")
    n = _no_ws_len(body)
    r.add("blog", "length_1500", n >= 1500, f"공백 제외 {n}자")
    heads = re.findall(r"^#{2,3}\s+", body, re.M)
    r.add("blog", "headings_3plus", len(heads) >= 3, f"소제목 {len(heads)}개")
    kwc = body.count(kw) if kw else 0
    r.add("blog", "keyword_count", 2 <= kwc <= 25, f"메인 키워드 {kwc}회 (2~25)", "warn")
    imgs = re.findall(r"!\[[^\]]*\]\(images/blog_\d\.jpg\)", body)
    r.add("blog", "image_slots_5", len(imgs) == 5, f"이미지 자리 {len(imgs)}개", "warn")
    quotes = re.findall(r"^>\s", body, re.M)
    r.add("blog", "quote_1plus", len(quotes) >= 1, f"인용구 {len(quotes)}개", "warn")
    long_paras = [pp for pp in body.split("\n\n") if not pp.startswith(("#", ">", "|", "!", "-")) and len(pp) > 260]
    r.add("blog", "paragraph_length", len(long_paras) == 0, f"260자 넘는 문단 {len(long_paras)}개 (4줄 이내)", "warn")
    bad = [w for w in SUPERLATIVES + _ad_blacklist() if w and w in body]
    r.add("blog", "no_ad_words", len(bad) == 0, f"광고티·최상급: {', '.join(bad[:8])}", "warn")
    em = len(EMOJI_RX.findall(body))
    r.add("blog", "emoji_0", em == 0, f"이모지 {em}개", "warn")
    r.add("blog", "no_injected_instructions", not re.search(r"(이전|위의?) 지시(를|사항을) 무시", body), "외부 지시문 흔적")


def _hashtags(text: str) -> list[str]:
    return HASHTAG_RX.findall(text)


def check_instagram(run: Path, r: Report) -> None:
    p = run / "06_instagram.md"
    if not p.exists():
        p = run / "06_instagram.draft.md"
    if not p.exists():
        r.add("instagram", "exists", False, "06_instagram.md 없음")
        return
    fm, body = _frontmatter(p.read_text(encoding="utf-8"))
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    r.add("instagram", "first_line_30", len(first) <= 30, f"첫 문장 {len(first)}자")
    n = len(body.strip())
    r.add("instagram", "length_300_600", 250 <= n <= 700, f"본문 {n}자 (300~600)", "warn")
    tags = fm.get("hashtags") if isinstance(fm.get("hashtags"), list) else _hashtags(body)
    r.add("instagram", "hashtags_max2", len(tags) <= 2, f"해시태그 {len(tags)}개 (3개 미만)")
    em = len(EMOJI_RX.findall(body))
    r.add("instagram", "emoji_max2", em <= 2, f"이모지 {em}개")
    ic = str(fm.get("image_copy", ""))
    r.add("instagram", "image_copy_20", 0 < len(ic) <= 20, f"이미지 카피 {len(ic)}자 (20자 이내)")


def check_threads(run: Path, r: Report) -> None:
    p = run / "07_threads.md"
    if not p.exists():
        p = run / "07_threads.draft.md"
    if not p.exists():
        r.add("threads", "exists", False, "07_threads.md 없음")
        return
    fm, body = _frontmatter(p.read_text(encoding="utf-8"))
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    r.add("threads", "first_line_25", len(first) <= 25, f"첫 줄 {len(first)}자")
    n = len(body.strip())
    r.add("threads", "length_150_350", 120 <= n <= 400, f"본문 {n}자 (150~350)", "warn")
    tags = _hashtags(body) + ([fm["hashtag"]] if fm.get("hashtag") and fm["hashtag"] not in body else [])
    r.add("threads", "hashtag_exactly1", len(set(tags)) == 1, f"해시태그 {len(set(tags))}개 (정확히 1)")
    em = len(EMOJI_RX.findall(body))
    r.add("threads", "emoji_0", em == 0, f"이모지 {em}개")
    mixed = bool(re.search(r"(습니다|입니다)[.!?]", body)) and bool(re.search(r"(야|다|지|거든|네)[.!?]\s", body))
    r.add("threads", "register_consistent", not mixed, "격식체와 반말 혼재 의심", "warn")


def _img_size(p: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(p) as im:
            return im.size
    except Exception:
        return None


def check_images(run: Path, r: Report) -> None:
    d = run / "images"
    for i in range(1, 6):
        p = d / f"blog_{i}.jpg"
        if not p.exists():
            p = d / f"blog_{i}.png"
        if not p.exists():
            r.add("images", f"blog_{i}_exists", False, "없음 — images/image_results.json 의 오류를 확인하세요"
                  " (무료 스톡이면 .env 에 PEXELS_API_KEY 가 있는지)")
            continue
        s = _img_size(p)
        ok = s is not None and s[0] > s[1] and abs(s[0] / s[1] - 16 / 9) < 0.08
        r.add("images", f"blog_{i}_landscape_16_9", ok, f"{s}")
    p = d / "instagram.jpg"
    if not p.exists():
        p = d / "instagram.png"
    if p.exists():
        s = _img_size(p)
        r.add("images", "instagram_3_4", s is not None and abs(s[0] / s[1] - 0.75) < 0.02, f"{s}")
    else:
        r.add("images", "instagram_exists", False, "images/instagram.jpg 없음")


def _ffprobe_duration(p: Path) -> float | None:
    fp = shutil.which("ffprobe")
    if not fp:
        return None
    out = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return None


def check_shorts(run: Path, r: Report) -> None:
    mp4 = run / "08_shorts" / "shorts.mp4"
    if not mp4.exists():
        r.add("shorts", "exists", False, "08_shorts/shorts.mp4 없음")
        return
    script = run / "08_shorts" / "script.json"
    target = 30
    if script.exists():
        try:
            target = int(json.loads(script.read_text(encoding="utf-8")).get("duration_s", 30))
        except (json.JSONDecodeError, ValueError):
            pass
    dur = _ffprobe_duration(mp4)
    r.add("shorts", "duration", dur is not None and abs(dur - target) <= 1.5, f"{dur}s (목표 {target}s ±1.5)")
    rev = run / "08_shorts" / "review.json"
    if rev.exists():
        try:
            d = json.loads(rev.read_text(encoding="utf-8"))
            r.add("shorts", "loudness", d.get("loudness_ok", False), f"LUFS {d.get('lufs')}", "warn")
            r.add("shorts", "no_freeze", d.get("freeze_ok", True), f"freeze {d.get('freeze_s', 0)}s", "warn")
            r.add("shorts", "first_frame", d.get("first_frame_ok", True), f"첫 프레임 대비 {d.get('first_frame_contrast')}"
                  " (낮으면 썸네일이 빈 화면)", "warn")
            fast = d.get("captions_fast") or []
            r.add("shorts", "caption_reading_time", not fast,
                  "모든 자막 읽을 시간 충분" if not fast else f"{len(fast)}개 너무 빨리 지나감: " + ", ".join(c["text"].replace("\n", " ") for c in fast[:3]), "warn")
            r.add("shorts", "narration", not d.get("silent_narration"), "음성 있음" if not d.get("silent_narration")
                  else "음성 없음(자막만) — 08_shorts/timing.json 의 fallback 이유 확인", "warn")
        except json.JSONDecodeError:
            pass


CHECKS = {"blog": check_blog, "instagram": check_instagram, "threads": check_threads, "images": check_images, "shorts": check_shorts}


def run_checks(run_dir: Path, only: set[str] | None = None) -> Report:
    r = Report()
    for name, fn in CHECKS.items():
        if only and name not in only:
            continue
        fn(run_dir, r)
    (run_dir / "checks.json").write_text(json.dumps(r.items, ensure_ascii=False, indent=2), encoding="utf-8")
    return r


def print_report(r: Report) -> None:
    for i in r.items:
        mark = "OK " if i["ok"] else ("WARN" if i["level"] == "warn" else "FAIL")
        print(f"[{mark:4}] {i['channel']}.{i['check']}: {i['detail']}")
    print(f"\ncheck: 실패 {len(r.failed)} · 경고 {len(r.warned)}")
