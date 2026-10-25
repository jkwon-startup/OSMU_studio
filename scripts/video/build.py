"""숏츠 합성 — plan.json 을 읽어 장면 자산 생성 → 샷별 세그먼트 → 자막 overlay → 음성·음량 정규화 → shorts.mp4 + 검수.

  python3 scripts/osmu.py video plan-check --run <run>
  python3 scripts/osmu.py video auto-plan  --run <run>      # script+timing → plan.json 초안
  python3 scripts/osmu.py video assets     --run <run>      # 실사: 장면 이미지(+클립) 생성
  python3 scripts/osmu.py video build      --run <run>      # 세그먼트 → 합성 → review.json, frame_sheet.jpg
  python3 scripts/osmu.py video all        --run <run>      # auto-plan → assets → build

FFmpeg 만으로 동작한다(drawtext 비의존 — 자막은 Pillow PNG overlay). 모션 샷은 Node+Remotion 이 있으면 렌더하고, 없으면 Pillow 카드로 대체한다.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, load_config, load_env  # noqa: E402
from image.compose_copy import find_font, render_text_png  # noqa: E402

W, H, FPS = 1080, 1920, 30
FF = shutil.which("ffmpeg")
FP = shutil.which("ffprobe")
PALETTE = {"bg": "#0F172A", "accent": "#F59E0B", "text": "#FFFFFF", "muted": "#94A3B8"}


def _run(cmd: list[str], timeout=600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def _dur(p: Path) -> float:
    return float(_run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip() or 0)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# ---------- 카드(Pillow) — 모션 폴백·엔드카드 ----------
def render_card(template: str, props: dict, out: Path, colors: dict) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    font_b, font_r = find_font(True), find_font(False) or find_font(True)
    im = Image.new("RGB", (W, H), _hex(colors["bg"]))
    d = ImageDraw.Draw(im)
    accent = _hex(colors["accent"])
    d.rectangle((0, 0, W, 18), fill=accent)
    if template in ("kinetic_full", "endcard"):
        text = props.get("text") or props.get("title") or ""
        size = 110 if len(text) <= 10 else 88
        f = ImageFont.truetype(str(font_b), size)
        lines = _wrap_lines(text, 9)
        y = H // 2 - (len(lines) * int(size * 1.3)) // 2 - 60
        for ln in lines:
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2, y), ln, font=f, fill=_hex(colors["text"]))
            y += int(size * 1.3)
        if template == "endcard" and props.get("sub"):
            f2 = ImageFont.truetype(str(font_r), 48)
            w = d.textlength(props["sub"], font=f2)
            d.text(((W - w) / 2, y + 40), props["sub"], font=f2, fill=_hex(colors["muted"]))
    elif template == "bullet_card":
        f_t = ImageFont.truetype(str(font_b), 84)
        f_i = ImageFont.truetype(str(font_r), 58)
        title = props.get("title", "")
        y = int(H * 0.22)
        for ln in _wrap_lines(title, 10):
            d.text((100, y), ln, font=f_t, fill=_hex(colors["text"]))
            y += 110
        y += 40
        for i, item in enumerate(props.get("items", [])[:3]):
            d.ellipse((100, y + 18, 130, y + 48), fill=accent)
            for ln in _wrap_lines(item, 16):
                d.text((160, y), ln, font=f_i, fill=_hex(colors["text"]))
                y += 76
            y += 30
    elif template == "data_bars":
        f_t = ImageFont.truetype(str(font_b), 80)
        f_l = ImageFont.truetype(str(font_r), 50)
        d.text((100, int(H * 0.2)), props.get("title", "")[:12], font=f_t, fill=_hex(colors["text"]))
        bars = props.get("bars", [])[:4]
        mx = max([b.get("value", 1) for b in bars] + [1])
        y = int(H * 0.38)
        for b in bars:
            d.text((100, y), f"{b.get('label','')}  {b.get('value','')}{b.get('unit','')}", font=f_l, fill=_hex(colors["muted"]))
            d.rectangle((100, y + 70, 100 + int((W - 200) * b.get("value", 0) / mx), y + 110), fill=accent)
            y += 170
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG")
    return out


def _wrap_lines(text: str, n: int) -> list[str]:
    text = text.replace("\n", " ").strip()
    out, cur = [], ""
    for word in text.split(" "):
        if len(cur) + len(word) + (1 if cur else 0) > n and cur:
            out.append(cur); cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out[:3]


# ---------- Remotion (있으면) ----------
def render_remotion(template: str, props: dict, seconds: float, out: Path, colors: dict) -> bool:
    npx = shutil.which("npx")
    mdir = ROOT / "motion"
    if not npx or not (mdir / "node_modules").exists():
        return False
    props_file = out.with_suffix(".props.json")
    props_file.write_text(json.dumps({"template": template, "props": props, "colors": colors,
                                      "durationInFrames": int(round(seconds * FPS))}, ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([npx, "remotion", "render", "Scene", str(out.resolve()), f"--props={props_file.resolve()}", "--log=error", "--codec=h264"],
                       cwd=str(mdir), capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        (out.with_suffix(".remotion.log")).write_text(p.stderr[-2000:], encoding="utf-8")
    return p.returncode == 0 and out.exists()


# ---------- 세그먼트 ----------
def _zoompan(motion: str, frames: int) -> str:
    # 1.0 → 1.08 사이의 느린 움직임. zoompan 은 입력을 프레임 단위로 재해석하므로 s= 로 출력 크기 고정.
    z_in = "min(zoom+0.0008,1.08)"
    z_out = "if(eq(on,1),1.08,max(zoom-0.0008,1.0))"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    m = {
        "push_in": f"zoompan=z='{z_in}':x='{cx}':y='{cy}':d={frames}:s={W}x{H}:fps={FPS}",
        "push_out": f"zoompan=z='{z_out}':x='{cx}':y='{cy}':d={frames}:s={W}x{H}:fps={FPS}",
        "pan_left": f"zoompan=z='1.08':x='(iw-iw/zoom)*(1-on/{frames})':y='{cy}':d={frames}:s={W}x{H}:fps={FPS}",
        "pan_right": f"zoompan=z='1.08':x='(iw-iw/zoom)*(on/{frames})':y='{cy}':d={frames}:s={W}x{H}:fps={FPS}",
        "static": f"zoompan=z='1.0':d={frames}:s={W}x{H}:fps={FPS}",
    }
    return m.get(motion, m["push_in"])


def segment_from_image(img: Path, seconds: float, motion: str, out: Path) -> None:
    frames = max(int(round(seconds * FPS)), 2)
    # 원본을 먼저 1080x1920 보다 크게(2x) 맞춰 두면 zoompan 계단 현상이 준다
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"{_zoompan(motion, frames)},format=yuv420p")
    p = _run([FF, "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-vf", vf, "-t", f"{seconds:.3f}",
              "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(out)])
    if p.returncode != 0:
        raise RuntimeError(f"image segment 실패: {p.stderr[-300:]}")


def segment_from_clip(clip: Path, seconds: float, out: Path) -> None:
    src_d = _dur(clip) or seconds
    loops = max(math.ceil(seconds / src_d) - 1, 0)
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p"
    p = _run([FF, "-y", "-loglevel", "error", "-stream_loop", str(loops), "-i", str(clip), "-vf", vf, "-t", f"{seconds:.3f}",
              "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(out)])
    if p.returncode != 0:
        raise RuntimeError(f"clip segment 실패: {p.stderr[-300:]}")


# ---------- 자산 ----------
def make_assets(run_dir: Path, plan: dict, cfg: dict) -> list[dict]:
    """실사 장면 이미지 + 클립(Pixverse 는 이미지→영상, stock 은 무료 스톡 영상) 생성. 실패해도 build 가 대체 화면을 쓴다."""
    from image import generate, stock
    sdir = run_dir / "08_shorts"
    provider = cfg.get("image_provider", "stock")
    ratio = plan.get("aspect", "9:16")
    results = []
    scenes = plan.get("scenes") or []
    items = [{"file": Path(s["file"]).name, "ratio": ratio, "prompt": s.get("prompt", ""), "query": s.get("query", "")}
             for s in scenes if not (sdir / s["file"]).exists()]
    if items:
        results += generate.generate_all(run_dir, items, provider, cfg, out_dir=sdir / "scenes")
    env = load_env()
    for s in scenes:
        if not s.get("clip"):
            continue
        out = sdir / "clips" / f"{s['id']}.mp4"
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if provider == "pixverse":
            ok, d = generate.pixverse_clip(sdir / s["file"], s.get("clip_prompt", "subtle camera push-in"), ratio, out, env, cfg, 5)
        elif stock.available(env):
            q = (s.get("query") or "").strip() or stock.query_from_prompt(s.get("prompt", ""))
            ok, d = stock.fetch("video", q, ratio, out, env, sdir / "clips" / "credits.json")
        else:
            continue
        results.append({"file": out.name, "ok": ok, "detail": d})
        print(f"[{'OK' if ok else 'FAIL'}] clip {s['id']} {d if not ok else ''}")
    return results


# ---------- 합성 ----------
def build(run_dir: Path, cfg: dict) -> dict:
    sdir = run_dir / "08_shorts"
    plan = json.loads((sdir / "plan.json").read_text(encoding="utf-8"))
    colors = {**PALETTE, **(cfg.get("brand", {}).get("colors") or {})}
    seg_dir = sdir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    seg_files: list[Path] = []
    notes: list[str] = []
    for i, s in enumerate(plan["shots"]):
        seconds = float(s["end"]) - float(s["start"])
        out = seg_dir / f"{i:02d}_{s['id']}.mp4"
        src = s["source"]
        ty = src["type"]
        if ty == "image":
            img = sdir / src["file"]
            if not img.exists():
                notes.append(f"{s['id']}: 이미지 없음 → 카드 대체")
                img = render_card("kinetic_full", {"text": _caption_at(plan, s["start"])}, seg_dir / f"{i:02d}_fallback.png", colors)
            segment_from_image(img, seconds, src.get("motion", "push_in"), out)
        elif ty == "clip":
            clip = sdir / src["file"]
            if clip.exists():
                segment_from_clip(clip, seconds, out)
            else:
                img = sdir / src["file"].replace("clips/", "scenes/").replace(".mp4", ".jpg")
                notes.append(f"{s['id']}: 클립 없음 → 정지 이미지 대체")
                if not img.exists():
                    img = render_card("kinetic_full", {"text": _caption_at(plan, s["start"])}, seg_dir / f"{i:02d}_fallback.png", colors)
                segment_from_image(img, seconds, "push_in", out)
        elif ty in ("motion", "endcard"):
            tpl = src.get("template", "endcard") if ty == "motion" else "endcard"
            if ty == "motion" and render_remotion(tpl, src.get("props", {}), seconds, out, colors):
                pass
            else:
                if ty == "motion":
                    notes.append(f"{s['id']}: Remotion 없음 → 정적 카드")
                card = render_card(tpl, src.get("props", {}), seg_dir / f"{i:02d}_card.png", colors)
                segment_from_image(card, seconds, "push_in", out)  # 엔드카드도 느린 줌 (정지 프레임 방지)
        seg_files.append(out)

    # concat
    listing = seg_dir / "concat.txt"
    listing.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in seg_files) + "\n", encoding="utf-8")
    video_noaudio = sdir / "video_nocap.mp4"
    p = _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(video_noaudio)])
    if p.returncode != 0:
        raise RuntimeError(f"concat 실패: {p.stderr[-300:]}")

    # 자막 PNG overlay (한 번의 filter_complex)
    cap_dir = sdir / "captions"
    cap_dir.mkdir(exist_ok=True)
    inputs = ["-i", str(video_noaudio)]
    filters, last = [], "[0:v]"
    caps = plan.get("captions") or []
    for j, c in enumerate(caps):
        png = render_text_png(c["text"], W - 120, cap_dir / f"{j:02d}.png", font_px=64, highlight=c.get("highlight"))
        inputs += ["-i", str(png)]
        nxt = f"[v{j}]"
        filters.append(f"{last}[{j+1}:v]overlay=x=60:y=H-h-{int(H*0.17)}:enable='between(t,{c['start']:.3f},{c['end']:.3f})'{nxt}")
        last = nxt
    # 썸네일 문구 (첫 1.2초, 상단)
    thumb = plan.get("thumbnail_text")
    if thumb:
        png = render_text_png(thumb, W - 120, cap_dir / "thumb.png", font_px=96, color=(255, 214, 10))
        inputs += ["-i", str(png)]
        idx = len(caps) + 1
        filters.append(f"{last}[{idx}:v]overlay=x=60:y={int(H*0.12)}:enable='between(t,0,1.2)'[vt]")
        last = "[vt]"
    video_cap = sdir / "video_cap.mp4"
    cmd = [FF, "-y", "-loglevel", "error"] + inputs
    if filters:
        cmd += ["-filter_complex", ";".join(filters), "-map", last]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(video_cap)]
    p = _run(cmd, timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"자막 overlay 실패: {p.stderr[-400:]}")

    # 오디오: 내레이션 + (전환 효과음 없음 기본) → loudnorm 2-pass
    narration = sdir / "narration.mp3"
    final = sdir / "shorts.mp4"
    total = float(plan["duration_s"])
    measure = _run([FF, "-hide_banner", "-i", str(narration), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measure.stderr, re.S)
    ln = "loudnorm=I=-16:TP=-1.5:LRA=11"
    if m:
        try:
            j = json.loads(m.group(0))
            vals = [float(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")]
            if all(math.isfinite(v) for v in vals) and -70 < vals[0] <= 0:  # 무음(-inf)이면 1-pass 로
                ln += f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    p = _run([FF, "-y", "-loglevel", "error", "-i", str(video_cap), "-i", str(narration),
              "-af", f"{ln},apad", "-t", f"{total:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(final)])
    if p.returncode != 0:
        raise RuntimeError(f"오디오 합성 실패: {p.stderr[-300:]}")
    for tmp in (video_noaudio, video_cap):
        tmp.unlink(missing_ok=True)
    review = review_video(final, sdir, total)
    review["notes"] = notes
    (sdir / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return review


def _caption_at(plan: dict, t: float) -> str:
    for c in plan.get("captions") or []:
        if c["start"] <= t < c["end"]:
            return c["text"]
    return plan.get("thumbnail_text", "")


# ---------- 검수 ----------
def review_video(mp4: Path, sdir: Path, target_s: float) -> dict:
    dur = _dur(mp4)
    ebur = _run([FF, "-hide_banner", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    ms = re.findall(r"I:\s*(-?[\d.]+) LUFS", ebur)  # 마지막 값이 Summary (앞의 값들은 프레임별 진행값)
    lufs = float(ms[-1]) if ms else None
    fz = _run([FF, "-hide_banner", "-i", str(mp4), "-vf", "freezedetect=n=0.001:d=3", "-f", "null", "-"]).stderr
    freeze_s = sum(float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", fz))  # 3초 이상 완전 정지만
    sheet = sdir / "frame_sheet.jpg"
    n = max(int(dur), 6)
    _run([FF, "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps=1/{max(dur/8,1):.2f},scale=270:-1,tile=4x2", "-frames:v", "1", str(sheet)])
    return {"duration_s": round(dur, 2), "target_s": target_s, "duration_ok": abs(dur - target_s) <= 1.5,
            "lufs": lufs, "loudness_ok": lufs is not None and -19 <= lufs <= -13,
            "freeze_s": round(freeze_s, 2), "freeze_ok": freeze_s < 2.0, "frame_sheet": str(sheet), "frames_sampled": n}
