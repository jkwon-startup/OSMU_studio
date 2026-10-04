"""오늘 주제 선택 — 결정적(LLM 없음). 세 가지 소스를 지원한다.

config["topics"] 예시:
  {"source": "folder", "path": "~/Obsidian/주제", "default_video_style": "실사"}
  {"source": "sheet",  "path": "~/주제.xlsx" 또는 ".../export?format=csv&gid=0", "on_missing": "skip"|"catch_up"}
  {"source": "docs",   "path": "config/topics.local.csv"}   # /osmu-setup 이 기획서를 정규화해 만든 csv

출력 topic.json: {id, title, memo, video_style: "photoreal"|"motion", source_ref, date}
완료 상태: output/state/done.json  { source_ref: {status, date, retries} }
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import sys
import unicodedata
import urllib.request
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import OUTPUT_DIR, ROOT, kst_now, read_json, write_json  # noqa: E402

DONE_PATH = OUTPUT_DIR / "state" / "done.json"
MAX_RETRIES = 2

COL_ALIASES = {
    "date": ["발행일", "발행 날짜", "날짜", "date", "publish_date", "일자"],
    "title": ["주제", "제목", "topic", "title"],
    "style": ["영상스타일", "영상 스타일", "스타일", "영상", "video_style", "style"],
    "memo": ["메모", "설명", "memo", "note", "notes", "비고"],
}


# ---------- 공통 ----------
def normalize_style(raw: str | None, default: str = "실사") -> str:
    s = (raw or default or "").strip().lower()
    return "motion" if ("모션" in s or "motion" in s or "그래픽" in s) else "photoreal"


def _natural_key(name: str):
    name = unicodedata.normalize("NFC", name)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _ref_id(source_ref: str) -> str:
    return hashlib.sha1(source_ref.encode("utf-8")).hexdigest()[:10]


def load_done() -> dict:
    return read_json(DONE_PATH, {}) or {}


def is_done(done: dict, source_ref: str) -> bool:
    entry = done.get(source_ref)
    if not entry:
        return False
    if entry.get("status") == "done":
        return True
    return int(entry.get("retries", 0)) >= MAX_RETRIES  # 재시도 초과 → 건너뜀


def mark(source_ref: str, status: str) -> None:
    """status: 'done' | 'retry'"""
    done = load_done()
    entry = done.get(source_ref, {"retries": 0})
    if status == "retry":
        entry["retries"] = int(entry.get("retries", 0)) + 1
    entry["status"] = status
    entry["date"] = kst_now().strftime("%Y-%m-%d")
    done[source_ref] = entry
    write_json(DONE_PATH, done)


# ---------- folder ----------
def _parse_md(path: Path) -> tuple[str, str, str | None]:
    """(title, body_memo, style_raw)"""
    text = path.read_text(encoding="utf-8-sig")
    fm: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            for line in parts[0].splitlines()[1:]:
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip().lower()] = v.strip().strip("'\"")
            body = parts[1].lstrip("-\n")
    title = fm.get("title") or fm.get("주제")
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        stem = re.sub(r"^\d+\s*[.\-_)]\s*", "", unicodedata.normalize("NFC", path.stem))  # "3. 제목" → "제목"
        title = m.group(1).strip() if m else stem
    style = fm.get("video_style") or fm.get("영상") or fm.get("영상스타일") or fm.get("style")
    if not style:
        m = re.search(r"^\s*(?:영상|영상\s*스타일|video_style)\s*[:：]\s*(.+)$", body, re.M)
        style = m.group(1).strip() if m else None
    return title, body.strip(), style


def select_from_folder(cfg: dict, done: dict) -> dict | None:
    folder = Path(cfg["path"]).expanduser()
    files = sorted((p for p in folder.glob("*.md") if not p.name.startswith(".")), key=lambda p: _natural_key(p.name))
    for p in files:
        ref = f"folder:{unicodedata.normalize('NFC', p.name)}"
        if is_done(done, ref):
            continue
        title, memo, style = _parse_md(p)
        return _topic(title, memo, normalize_style(style, cfg.get("default_video_style", "실사")), ref)
    return None


# ---------- sheet (xlsx / csv / 구글시트 공개 CSV) ----------
def _parse_date(v, today: date) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})", s)
    if m:
        return date(today.year, int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _read_rows(path_or_url: str) -> list[dict]:
    """헤더 기준 dict 행 목록. 열 이름은 별칭으로 정규화."""
    if path_or_url.startswith("http"):
        with urllib.request.urlopen(path_or_url, timeout=30) as resp:
            raw = resp.read()
        return _rows_from_csv_bytes(raw)
    p = Path(path_or_url).expanduser()
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl  # 선택 의존성
        ws = openpyxl.load_workbook(p, read_only=True, data_only=True).active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        return _rows_from_lists(rows)
    return _rows_from_csv_bytes(p.read_bytes())


def _rows_from_csv_bytes(raw: bytes) -> list[dict]:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    return _rows_from_lists(list(csv.reader(io.StringIO(text))))


def _rows_from_lists(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    header = [unicodedata.normalize("NFC", str(h or "")).strip().lower() for h in rows[0]]
    colmap: dict[str, int] = {}
    for key, aliases in COL_ALIASES.items():
        for i, h in enumerate(header):
            if h in [a.lower() for a in aliases]:
                colmap[key] = i
                break
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if not any(str(c or "").strip() for c in r):
            continue
        get = lambda k: (r[colmap[k]] if k in colmap and colmap[k] < len(r) else None)  # noqa: E731
        out.append({"row": n, "date": get("date"), "title": get("title"), "style": get("style"), "memo": get("memo")})
    return out


def select_from_sheet(cfg: dict, done: dict, today: date) -> dict | None:
    rows = _read_rows(cfg["path"])
    on_missing = cfg.get("on_missing", "skip")
    candidates = []
    for r in rows:
        if not str(r["title"] or "").strip():
            continue
        d = _parse_date(r["date"], today)
        ref = f"sheet:{r['row']}:{_ref_id(str(r['title']))}"
        if is_done(done, ref):
            continue
        candidates.append((d, r, ref))
    todays = [c for c in candidates if c[0] == today]
    pick = todays[0] if todays else None
    if not pick and on_missing == "catch_up":
        past = sorted((c for c in candidates if c[0] and c[0] < today), key=lambda c: c[0])
        pick = past[0] if past else None
    if not pick:
        return None
    d, r, ref = pick
    return _topic(str(r["title"]).strip(), str(r["memo"] or "").strip(),
                 normalize_style(str(r["style"] or ""), cfg.get("default_video_style", "실사")), ref, d)


# ---------- docs (정규화된 csv를 순서대로) ----------
def select_from_docs(cfg: dict, done: dict) -> dict | None:
    rows = _read_rows(cfg.get("path", "config/topics.local.csv"))
    for r in rows:
        if not str(r["title"] or "").strip():
            continue
        ref = f"docs:{r['row']}:{_ref_id(str(r['title']))}"
        if is_done(done, ref):
            continue
        return _topic(str(r["title"]).strip(), str(r["memo"] or "").strip(),
                      normalize_style(str(r["style"] or ""), cfg.get("default_video_style", "실사")), ref)
    return None


def _topic(title: str, memo: str, style: str, ref: str, d: date | None = None) -> dict:
    today = kst_now().date()
    return {
        "id": f"{today:%Y%m%d}-{_ref_id(ref)}",
        "title": title,
        "memo": memo[:4000],
        "video_style": style,
        "source_ref": ref,
        "date": (d or today).isoformat(),
    }


def select_topic(config: dict, today: date | None = None) -> dict | None:
    cfg = config.get("topics") or {}
    today = today or kst_now().date()
    done = load_done()
    src = cfg.get("source")
    if src == "folder":
        return select_from_folder(cfg, done)
    if src == "sheet":
        return select_from_sheet(cfg, done, today)
    if src == "docs":
        return select_from_docs(cfg, done)
    raise ValueError(f"topics.source 가 잘못됨: {src!r} (folder|sheet|docs)")
