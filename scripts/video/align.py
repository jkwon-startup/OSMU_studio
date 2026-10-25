"""자막 타이밍 정밀화 — 화면 자막(숫자 그대로 "3가지")과 발화(숫자 한글 "세 가지")를 글자 단위로 맞춘다.

edge-tts 의 단어 타이밍(timing.json units[].words)이 있을 때만 쓴다. 없으면 문장 단위 타이밍 그대로.
HyperFrames 의 align-captions 아이디어(표시 토큰 ↔ 발화 토큰 퍼지 매칭)를 한글이 지워지지 않게 파이썬으로 다시 썼다.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_KEEP = re.compile(r"[0-9A-Za-z가-힣]")


def _norm_chars(text: str) -> tuple[str, list[int]]:
    """비교용 글자열(한글·영문·숫자만, 소문자)과 원문 위치 목록."""
    chars, idx = [], []
    for i, ch in enumerate(text):
        if _KEEP.match(ch):
            chars.append(ch.lower())
            idx.append(i)
    return "".join(chars), idx


def spoken_char_times(words: list[dict]) -> tuple[str, list[float]]:
    """발화 단어 → 글자마다 시작 시각(단어 안에서는 균등 분배)."""
    s, times = [], []
    for w in words:
        norm, _ = _norm_chars(w.get("text", ""))
        n = len(norm)
        if not n:
            continue
        st, en = float(w["start"]), float(w["end"])
        for k, ch in enumerate(norm):
            s.append(ch)
            times.append(st + (en - st) * k / n)
    return "".join(s), times


def display_char_times(display: str, words: list[dict], unit_start: float, unit_end: float) -> list[float]:
    """화면 글자(원문 위치)마다 시작 시각. 맞는 글자가 없는 구간(숫자 등)은 앞뒤 사이를 보간한다."""
    d_norm, d_idx = _norm_chars(display)
    s_norm, s_times = spoken_char_times(words)
    times: list[float | None] = [None] * len(d_norm)
    if d_norm and s_norm:
        sm = SequenceMatcher(None, d_norm, s_norm, autojunk=False)
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                times[a + k] = s_times[b + k]
    # 보간: 앞 값과 뒤 값 사이를 글자 수 비율로
    known = [(i, t) for i, t in enumerate(times) if t is not None]
    if not known:
        n = max(len(d_norm), 1)
        times = [unit_start + (unit_end - unit_start) * i / n for i in range(len(d_norm))]
    else:
        anchors = [(-1, unit_start)] + known + [(len(d_norm), unit_end)]
        for (i0, t0), (i1, t1) in zip(anchors, anchors[1:]):
            for i in range(i0 + 1, i1):
                times[i] = t0 + (t1 - t0) * (i - i0) / (i1 - i0)
    # 단조 증가 보정
    out, last = [], unit_start
    for t in times:
        last = max(last, float(t))
        out.append(last)
    # 원문 위치 기준 배열로 펼친다(공백·문장부호는 다음 글자 시각)
    full = [unit_end] * (len(display) + 1)
    for k, pos in zip(range(len(out) - 1, -1, -1), reversed(d_idx)):
        full[pos] = out[k]
    kept = set(d_idx)
    for i in range(len(display) - 1, -1, -1):
        if i not in kept:
            full[i] = full[i + 1]
    return full


def pack_lines(text: str, max_line: int = 12, max_lines: int = 2) -> list[tuple[int, int, str]]:
    """어절 단위로 한 줄 max_line 자 이내, 자막 한 장 max_lines 줄 → [(시작 위치, 끝 위치, 자막 문자열)]."""
    tokens = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    lines: list[tuple[int, int]] = []
    cur: list[tuple[int, int]] = []
    for tok in tokens:
        cand = cur + [tok]
        if cur and len(text[cand[0][0]:cand[-1][1]]) > max_line:
            lines.append((cur[0][0], cur[-1][1]))
            cur = [tok]
        else:
            cur = cand
    if cur:
        lines.append((cur[0][0], cur[-1][1]))
    cards = []
    for i in range(0, len(lines), max_lines):
        grp = lines[i:i + max_lines]
        cards.append((grp[0][0], grp[-1][1], "\n".join(text[a:b] for a, b in grp)))
    return cards


def chunk_captions(text: str, words: list[dict], start: float, end: float, max_line: int = 12) -> list[dict]:
    """긴 문장을 자막 여러 장으로 나누고, 장마다 발화 시점에 맞춘 시작·끝을 준다."""
    cards = pack_lines(text, max_line)
    if len(cards) <= 1:
        return [{"text": c[2], "start": start, "end": end} for c in cards] or [{"text": text, "start": start, "end": end}]
    times = display_char_times(text, words, start, end)
    out = []
    for k, (a, _b, s) in enumerate(cards):  # 단어 타이밍이 없으면 글자 수 비율로 나눈다
        st = start if k == 0 else times[a]
        en = end if k == len(cards) - 1 else times[cards[k + 1][0]]
        out.append({"text": s, "start": round(st, 3), "end": round(max(en, st + 0.3), 3)})
    # 겹침 정리
    for k in range(len(out) - 1):
        out[k]["end"] = min(out[k]["end"], out[k + 1]["start"])
    return out
