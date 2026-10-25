"""plan.json 스키마 검증 — 샷이 0초부터 빈틈없이 이어지고 합계가 길이와 같은지, 소스 종류와 자막 규격을 확인한다.

plan.json
{
  "duration_s": 30,
  "style": "photoreal" | "motion",
  "aspect": "9:16" | "1:1" | "16:9",               (선택, 기본 9:16)
  "transition": "fade",                             (선택. 샷마다 shots[].transition 으로 덮어쓰기 = 앞 샷에서 넘어오는 방식)
  "thumbnail_text": "…",
  "shots": [
    {"id": "s1", "start": 0.0, "end": 3.0, "source": {"type": "image", "file": "scenes/hook.jpg", "motion": "push_in"}},
    {"id": "s2", "start": 3.0, "end": 8.0, "source": {"type": "clip", "file": "clips/problem.mp4"}},
    {"id": "s3", "start": 8.0, "end": 14.0, "source": {"type": "motion", "template": "bullet_card", "props": {"title": "…", "items": ["…"]}}},
    {"id": "s7", "start": 27.0, "end": 30.0, "source": {"type": "endcard", "props": {"title": "…", "sub": "…"}}}
  ],
  "captions": [{"text": "하루 30분,\n진짜 될까요?", "start": 0.0, "end": 2.1, "highlight": "30분"}],
  "scenes": [{"id": "hook", "file": "scenes/hook.jpg", "prompt": "…", "clip": true, "clip_prompt": "…"}]
}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SOURCE_TYPES = {"image", "clip", "motion", "endcard"}
MOTIONS = {"push_in", "push_out", "pan_left", "pan_right", "static"}
ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
TRANSITIONS = {"cut", "fade", "dissolve", "slide_left", "slide_up", "zoom"}
TOLERANCE = 0.05


def templates() -> set[str]:
    """templates/motion/*.html 에 있는 모션 템플릿 이름 (설치자가 추가한 것 포함)."""
    from video.html_render import list_templates
    return set(list_templates()) | {"kinetic_full", "bullet_card", "data_bars", "endcard"}


def validate(plan: dict) -> list[str]:
    errs: list[str] = []
    dur = float(plan.get("duration_s", 0))
    if not 5 <= dur <= 90:
        errs.append(f"duration_s {dur} 범위 밖(5~90)")
    if plan.get("aspect", "9:16") not in ASPECTS:
        errs.append(f"aspect {plan.get('aspect')!r} ({' | '.join(ASPECTS)})")
    if plan.get("transition", "cut") not in TRANSITIONS:
        errs.append(f"transition {plan.get('transition')!r} ({' | '.join(sorted(TRANSITIONS))})")
    tpls = templates()
    shots = plan.get("shots") or []
    if not shots:
        errs.append("shots 비어 있음")
    t = 0.0
    for i, s in enumerate(shots):
        st, en = float(s.get("start", -1)), float(s.get("end", -1))
        if abs(st - t) > TOLERANCE:
            errs.append(f"shot {i}({s.get('id')}): start {st} ≠ 이전 end {t:.2f} — 빈틈/겹침")
        if en <= st:
            errs.append(f"shot {i}: end {en} ≤ start {st}")
        if en - st < 0.8:
            errs.append(f"shot {i}: {en-st:.2f}s — 너무 짧음(0.8s 이상)")
        src = s.get("source") or {}
        ty = src.get("type")
        if ty not in SOURCE_TYPES:
            errs.append(f"shot {i}: source.type {ty!r} (image|clip|motion|endcard)")
        if ty in ("image", "clip") and not src.get("file"):
            errs.append(f"shot {i}: source.file 없음")
        if ty == "image" and src.get("motion", "push_in") not in MOTIONS:
            errs.append(f"shot {i}: motion {src.get('motion')!r}")
        if ty == "motion" and src.get("template") not in tpls:
            errs.append(f"shot {i}: template {src.get('template')!r} (있는 것: {', '.join(sorted(tpls))})")
        if s.get("transition", "cut") not in TRANSITIONS:
            errs.append(f"shot {i}: transition {s.get('transition')!r}")
        t = en
    if shots and abs(t - dur) > TOLERANCE:
        errs.append(f"마지막 end {t:.2f} ≠ duration_s {dur}")
    for j, c in enumerate(plan.get("captions") or []):
        lines = str(c.get("text", "")).split("\n")
        if len(lines) > 2:
            errs.append(f"caption {j}: 3줄 이상")
        if any(len(ln) > 14 for ln in lines):
            errs.append(f"caption {j}: 한 줄 14자 초과 — {lines}")
        if float(c.get("end", 0)) <= float(c.get("start", 0)):
            errs.append(f"caption {j}: 시간 역전")
    return errs


def validate_file(path: Path) -> list[str]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"plan.json 읽기 실패: {e}"]
    return validate(plan)


def captions_from_timing(timing: dict, max_chars: int = 12) -> list[dict]:
    """timing.json 의 문장을 자막으로 — 한 줄 max_chars 자, 2줄씩. 더 긴 문장은 여러 장으로 나누고
    단어 타이밍(edge-tts)이 있으면 발화 시점에, 없으면 글자 수 비율로 맞춘다. 수치가 들어간 토큰을 강조."""
    from video.align import chunk_captions
    caps = []
    for u in timing["units"]:
        for c in chunk_captions(u["text"].strip(), u.get("words") or [], float(u["start"]), float(u["end"]), max_chars):
            m = re.search(r"\d[\d,.]*\s*[가-힣%]{0,2}", c["text"])
            caps.append({**c, "highlight": m.group(0).strip() if m else None, "beat": u["beat"]})
    return caps


def _clip(text: str, n: int) -> str:
    """카드 글자 수 제한 — 어절 중간에서 자르지 않는다."""
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text.rfind(" ", 0, n + 1)
    return text[:cut if cut > n // 2 else n].rstrip(" ,")


def auto_plan(script: dict, timing: dict, style: str, provider: str, aspect: str = "9:16", transition: str = "fade") -> dict:
    """대본 beats 와 타이밍으로 기본 plan 을 자동 생성한다 (PD 가 다듬기 전 초안, 또는 무인 폴백)."""
    beats = {b["id"]: b for b in script["beats"]}
    order = [b["id"] for b in script["beats"]]
    # beat 별 시작·끝 = 그 beat 의 첫 문장 start ~ 마지막 문장 end(+gap 은 다음 beat 시작까지)
    spans: dict[str, list[float]] = {}
    for u in timing["units"]:
        spans.setdefault(u["beat"], [u["start"], u["end"]])
        spans[u["beat"]][1] = u["end"]
    total = round(timing["total_s"], 2)
    shots, scenes = [], []
    clip_quota = 3 if provider in ("pixverse", "stock") else 0  # stock: 키가 없으면 make_assets 가 건너뛰고 정지 이미지로
    motions = ["push_in", "pan_left", "push_out", "pan_right"]
    for i, bid in enumerate(order):
        if bid not in spans:
            continue
        start = spans[bid][0] if i > 0 else 0.0
        end = spans[order[i + 1]][0] if i + 1 < len(order) and order[i + 1] in spans else total
        b = beats[bid]
        if i == len(order) - 1:
            shots.append({"id": bid, "start": round(start, 2), "end": round(end, 2),
                          "source": {"type": "endcard", "props": {"title": script.get("thumbnail_text", ""), "sub": "전체 글은 블로그에서"}}})
            continue
        if style == "motion":
            sents = [s.strip() for s in re.split(r"(?<=[.?!…])\s+", b["narration"].strip()) if s.strip()]
            tpl = "kinetic_full" if (i == 0 or len(sents) < 2) else "bullet_card"
            props = {"text": _clip(sents[0], 26)} if tpl == "kinetic_full" else \
                {"title": _clip(sents[0], 26), "items": [_clip(s.rstrip("."), 20) for s in sents[1:4]]}
            shots.append({"id": bid, "start": round(start, 2), "end": round(end, 2), "source": {"type": "motion", "template": tpl, "props": props}})
        else:
            use_clip = clip_quota > 0 and (end - start) >= 4 and i > 0
            if use_clip:
                clip_quota -= 1
            scenes.append({"id": bid, "file": f"scenes/{bid}.jpg", "prompt": b.get("scene_prompt", ""), "query": b.get("scene_query", ""), "clip": use_clip,
                           "clip_prompt": "subtle camera push-in, stable composition, no new text, preserve subject"})
            src = {"type": "clip", "file": f"clips/{bid}.mp4"} if use_clip else {"type": "image", "file": f"scenes/{bid}.jpg", "motion": motions[i % 4]}
            shots.append({"id": bid, "start": round(start, 2), "end": round(end, 2), "source": src})
    if shots:
        shots[-1]["end"] = total
    captions = captions_from_timing(timing)
    if style == "motion":
        # 화면에 이미 같은 문장이 크게 나오는 샷(큰 글자·핵심 카드·엔드카드)에는 자막을 겹쳐 쓰지 않는다
        text_shots = [(s["start"], s["end"]) for s in shots
                      if s["source"]["type"] == "endcard" or s["source"].get("template") in ("kinetic_full", "bullet_card")]
        captions = [c for c in captions if not any(st - 0.05 <= c["start"] < en - 0.05 for st, en in text_shots)]
    return {"duration_s": total, "style": style, "aspect": aspect if aspect in ASPECTS else "9:16",
            "transition": transition if transition in TRANSITIONS else "fade",
            "thumbnail_text": script.get("thumbnail_text", ""), "shots": shots, "captions": captions, "scenes": scenes}
