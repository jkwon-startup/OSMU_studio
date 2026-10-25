"""브랜드 토큰(frame.md) — 숏츠 모션 카드·자막·인스타 카피가 같은 색·글꼴을 쓰게 하는 한 파일.

config/frame.local.md (설치자, git 제외) → 없으면 config/frame.example.md.
맨 위 --- 사이의 간단한 YAML(2단계까지, "키: 값")만 읽는다. 아래 본문은 자유 메모.
HyperFrames 의 frame.md(디자인 토큰을 영상용으로) 아이디어를 OSMU 규모로 줄였다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
HEX = re.compile(r"#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?")


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"﻿?---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    data: dict = {}
    section: dict | None = None
    for raw in m.group(1).splitlines():
        # 주석은 "# 뒤에 공백" 만 — 색 값(#0F172A)은 지우지 않는다
        line = re.split(r"\s+#\s", raw, maxsplit=1)[0].rstrip() if not raw.strip().startswith("# ") else ""
        if not line.strip() or ":" not in line:
            continue
        key, _, val = line.strip().partition(":")
        val = val.strip().strip("'\"")
        if not raw.startswith((" ", "\t")):
            if val:
                data[key] = val
                section = None
            else:
                section = data.setdefault(key, {})
        elif section is not None:
            section[key] = val
    return data


def load_frame_tokens() -> dict:
    """{"colors": {...}, "caption": {...}, "font": {...}} — 잘못된 값은 버린다."""
    for name in ("frame.local.md", "frame.example.md"):
        p = CONFIG_DIR / name
        if p.exists():
            try:
                raw = parse_frontmatter(p.read_text(encoding="utf-8"))
            except OSError:
                continue
            break
    else:
        return {}
    out: dict = {"colors": {}, "caption": {}, "font": {}}
    for k, v in (raw.get("colors") or {}).items():
        if HEX.fullmatch(v):
            out["colors"][k] = v
    cap = raw.get("caption") or {}
    for k in ("color", "highlight", "stroke"):
        if HEX.fullmatch(cap.get(k, "")):
            out["caption"][k] = cap[k]
    try:
        out["caption"]["size"] = min(max(float(cap.get("size", 1.0)), 0.6), 1.6)
    except ValueError:
        print("[브랜드 토큰] caption.size 는 숫자여야 합니다 — 1.0 으로 씁니다", file=sys.stderr)
        out["caption"]["size"] = 1.0
    fonts = ROOT / "assets" / "fonts"
    for k in ("bold", "regular"):
        f = (raw.get("font") or {}).get(k)
        if f and (fonts / f).exists():
            out["font"][k] = f
    return out


def hex_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
