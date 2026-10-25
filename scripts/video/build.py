"""숏츠 합성 — plan.json 을 읽어 장면 자산 생성 → 샷별 세그먼트 → 장면 전환 → 자막 overlay → 음성·배경음악·음량 정규화 → shorts.mp4 + 검수.

  python3 scripts/osmu.py video plan-check --run <run>
  python3 scripts/osmu.py video auto-plan  --run <run>      # script+timing → plan.json 초안
  python3 scripts/osmu.py video assets     --run <run>      # 실사: 장면 이미지(+클립) 생성
  python3 scripts/osmu.py video build      --run <run>      # 세그먼트 → 합성 → review.json, frame_sheet.jpg, seams.jpg
  python3 scripts/osmu.py video all        --run <run>      # auto-plan → assets → build

FFmpeg 만으로 동작한다(drawtext 비의존 — 자막은 Pillow PNG overlay).
모션 샷: HTML 템플릿(Playwright) → (설정 시) Remotion → Pillow 정적 카드 순으로 가능한 것을 쓴다.
배경음악: assets/bgm/ 에 설치자가 넣은 파일만 쓴다(저장소는 음악을 동봉하지 않는다).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, load_env  # noqa: E402
from image.compose_copy import find_font, render_text_png  # noqa: E402
from video.ff import FF, FP, encoder_args, has_filter  # noqa: E402

W, H, FPS = 1080, 1920, 30
ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
PALETTE = {"bg": "#0F172A", "accent": "#F59E0B", "text": "#FFFFFF", "muted": "#94A3B8"}
XFADE_S = 0.35
XFADE_NAMES = {"fade": "fade", "dissolve": "dissolve", "slide_left": "slideleft", "slide_up": "slideup", "zoom": "zoomin", "cut": "fade"}
BGM_DIR = ROOT / "assets" / "bgm"
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac")


def set_aspect(aspect: str | None) -> str:
    global W, H
    aspect = aspect if aspect in ASPECTS else "9:16"
    W, H = ASPECTS[aspect]
    return aspect


def _run(cmd: list[str], timeout=600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def _dur(p: Path) -> float:
    try:
        return float(_run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip() or 0)
    except ValueError:
        return 0.0


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def brand_colors(cfg: dict) -> dict:
    """기본 팔레트 ← config brand.colors ← config/frame.local.md(브랜드 토큰). 잘못된 색 값은 무시."""
    colors = dict(PALETTE)
    try:
        from video.frame_tokens import load_frame_tokens
        sources = [(cfg.get("brand") or {}).get("colors") or {}, load_frame_tokens().get("colors", {})]
    except Exception:
        sources = [(cfg.get("brand") or {}).get("colors") or {}]
    for src in sources:
        for k, v in src.items():
            if k in colors and isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?", v):
                colors[k] = v
    return colors


# ---------- 카드(Pillow) — HTML·Remotion 이 없을 때의 정적 대체 ----------
def render_card(template: str, props: dict, out: Path, colors: dict) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    font_b, font_r = find_font(True), find_font(False) or find_font(True)
    s = min(W, H) / 1080  # 1:1·16:9 에서도 같은 비율
    im = Image.new("RGB", (W, H), _hex(colors["bg"]))
    d = ImageDraw.Draw(im)
    accent = _hex(colors["accent"])
    d.rectangle((0, 0, W, int(18 * s)), fill=accent)
    x0 = int(100 * s)
    if template in ("bullet_card", "data_bars"):
        pass
    elif template not in ("kinetic_full", "endcard"):
        template = "kinetic_full"  # 설치자가 만든 HTML 템플릿의 정적 대체 — 큰 글자 카드
    if template in ("kinetic_full", "endcard"):
        text = props.get("text") or props.get("title") or ""
        size = int((110 if len(text) <= 10 else 88) * s)
        f = ImageFont.truetype(str(font_b), size)
        lines = _wrap_lines(text, 9 if W <= H else 16)
        y = H // 2 - (len(lines) * int(size * 1.3)) // 2 - int(60 * s)
        for ln in lines:
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2, y), ln, font=f, fill=_hex(colors["text"]))
            y += int(size * 1.3)
        if template == "endcard" and props.get("sub"):
            f2 = ImageFont.truetype(str(font_r), int(48 * s))
            w = d.textlength(props["sub"], font=f2)
            d.text(((W - w) / 2, y + int(40 * s)), props["sub"], font=f2, fill=_hex(colors["muted"]))
    elif template == "bullet_card":
        f_t = ImageFont.truetype(str(font_b), int(84 * s))
        f_i = ImageFont.truetype(str(font_r), int(58 * s))
        y = int(H * 0.22)
        for ln in _wrap_lines(props.get("title", ""), 10):
            d.text((x0, y), ln, font=f_t, fill=_hex(colors["text"]))
            y += int(110 * s)
        y += int(40 * s)
        for item in props.get("items", [])[:3]:
            d.ellipse((x0, y + int(18 * s), x0 + int(30 * s), y + int(48 * s)), fill=accent)
            for ln in _wrap_lines(str(item), 16):
                d.text((x0 + int(60 * s), y), ln, font=f_i, fill=_hex(colors["text"]))
                y += int(76 * s)
            y += int(30 * s)
    elif template == "data_bars":
        f_t = ImageFont.truetype(str(font_b), int(80 * s))
        f_l = ImageFont.truetype(str(font_r), int(50 * s))
        d.text((x0, int(H * 0.2)), props.get("title", "")[:12], font=f_t, fill=_hex(colors["text"]))
        bars = props.get("bars", [])[:4]
        mx = max([b.get("value", 1) for b in bars] + [1])
        y = int(H * 0.38)
        for b in bars:
            d.text((x0, y), f"{b.get('label','')}  {b.get('value','')}{b.get('unit','')}", font=f_l, fill=_hex(colors["muted"]))
            d.rectangle((x0, y + int(70 * s), x0 + int((W - 2 * x0) * b.get("value", 0) / mx), y + int(110 * s)), fill=accent)
            y += int(170 * s)
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


# ---------- Remotion (선택) ----------
def render_remotion(template: str, props: dict, seconds: float, out: Path, colors: dict) -> bool:
    npx = shutil.which("npx")
    mdir = ROOT / "motion"
    if not npx or not (mdir / "node_modules").exists() or (W, H) != (1080, 1920):
        return False
    props_file = out.with_suffix(".props.json")
    props_file.write_text(json.dumps({"template": template, "props": props, "colors": colors,
                                      "durationInFrames": int(round(seconds * FPS))}, ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([npx, "remotion", "render", "Scene", str(out.resolve()), f"--props={props_file.resolve()}", "--log=error", "--codec=h264"],
                       cwd=str(mdir), capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        (out.with_suffix(".remotion.log")).write_text(p.stderr[-2000:], encoding="utf-8")
    return p.returncode == 0 and out.exists()


class MotionRenderer:
    """모션 샷 렌더 순서: html → (motion_engine=remotion 이면 Remotion 먼저) → Pillow 카드. 실패 이유는 notes 로."""

    def __init__(self, cfg: dict, stack: ExitStack):
        self.engine = cfg.get("motion_engine", "html")
        self.stack = stack
        self._html = None
        self._html_error = ""

    def _html_renderer(self):
        if self._html is None and not self._html_error:
            from video import html_render
            ok, why = html_render.available()
            if not ok:
                self._html_error = why
            else:
                try:
                    self._html = self.stack.enter_context(html_render.Renderer())
                except Exception as e:
                    self._html_error = str(e)[:160]
        return self._html

    def render(self, template: str, props: dict, seconds: float, out: Path, colors: dict, fade_out: bool) -> str:
        """만든 방법을 돌려준다: 'html' | 'remotion' | 'card'."""
        order = ["remotion", "html"] if self.engine == "remotion" else (["html"] if self.engine == "html" else [])
        for eng in order:
            if eng == "remotion" and render_remotion(template, props, seconds, out, colors):
                return "remotion"
            if eng == "html":
                r = self._html_renderer()
                if r:
                    try:
                        r.video(template, props, seconds, out, colors, W, H, fade_out=fade_out)
                        return "html"
                    except Exception as e:
                        self._html_error = f"{template}: {str(e)[:160]}"
        card = render_card(template, props, out.with_name(out.stem + "_card.png"), colors)
        segment_from_image(card, seconds, "push_in", out)  # 정지 프레임 방지용 느린 줌
        return "card"


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
    # 원본을 먼저 목표보다 크게(2x) 맞춰 두면 zoompan 계단 현상이 준다
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"{_zoompan(motion, frames)},format=yuv420p")
    p = _run([FF, "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-vf", vf, "-t", f"{seconds:.3f}",
              "-r", str(FPS), *encoder_args(), "-an", str(out)])
    if p.returncode != 0:
        raise RuntimeError(f"image segment 실패: {p.stderr[-300:]}")


def segment_from_clip(clip: Path, seconds: float, out: Path) -> None:
    src_d = _dur(clip) or seconds
    loops = max(math.ceil(seconds / src_d) - 1, 0)
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p"
    p = _run([FF, "-y", "-loglevel", "error", "-stream_loop", str(loops), "-i", str(clip), "-vf", vf, "-t", f"{seconds:.3f}",
              *encoder_args(), "-an", str(out)])
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


# ---------- 배경음악 ----------
def pick_bgm(cfg: dict, run_dir: Path) -> tuple[Path | None, str]:
    """(파일, 설명). 설정 파일 → 없으면 assets/bgm 에서 실행 날짜로 하나 고른다(같은 날 재실행해도 같은 곡)."""
    bgm = cfg.get("bgm") if isinstance(cfg.get("bgm"), dict) else {}
    if not bgm.get("enabled", True):
        return None, "배경음악 꺼짐(bgm.enabled=false)"
    if bgm.get("file"):
        p = Path(bgm["file"]).expanduser()
        p = p if p.is_absolute() else BGM_DIR / p
        if p.exists() and _dur(p) > 1:
            return p, p.name
        return None, f"bgm.file '{bgm['file']}' 을 찾지 못함 — assets/bgm/ 에 있는지 확인"
    files = sorted(p for p in BGM_DIR.glob("*") if p.suffix.lower() in AUDIO_EXT) if BGM_DIR.exists() else []
    if not files:
        return None, "assets/bgm 비어 있음 — 배경음악 없이 제작"
    idx = int(hashlib.md5(run_dir.resolve().name.encode()).hexdigest(), 16) % len(files)
    for p in files[idx:] + files[:idx]:
        if _dur(p) > 1:
            return p, p.name
    return None, "assets/bgm 의 파일을 읽지 못함"


# ---------- 합성 ----------
def _concat_xfade(seg_files: list[Path], shots: list[dict], trans: list[str | None], out: Path) -> None:
    inputs, chains = [], []
    for i, f in enumerate(seg_files):
        inputs += ["-i", str(f)]
        chains.append(f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[s{i}]")
    last = "[s0]"
    for i in range(1, len(seg_files)):
        t = trans[i] or "cut"
        d = XFADE_S if t != "cut" else 1 / FPS
        nxt = f"[x{i}]"
        chains.append(f"{last}[s{i}]xfade=transition={XFADE_NAMES.get(t, 'fade')}:duration={d:.3f}:offset={float(shots[i]['start']):.3f}{nxt}")
        last = nxt
    p = _run([FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(chains), "-map", last,
              *encoder_args(), "-pix_fmt", "yuv420p", "-an", str(out)], timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"장면 전환 합성 실패: {p.stderr[-300:]}")


def build(run_dir: Path, cfg: dict) -> dict:
    sdir = run_dir / "08_shorts"
    plan = json.loads((sdir / "plan.json").read_text(encoding="utf-8"))
    aspect = set_aspect(plan.get("aspect") or cfg.get("shorts_aspect", "9:16"))
    colors = brand_colors(cfg)
    seg_dir = sdir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    shots = plan["shots"]

    # 앞 샷에서 넘어오는 전환 (첫 샷은 없음)
    default_tr = plan.get("transition", cfg.get("shorts_transition", "cut"))
    trans: list[str | None] = [None] + [s.get("transition", default_tr) for s in shots[1:]]
    use_xfade = any(t and t != "cut" for t in trans)
    if use_xfade and not has_filter("xfade"):
        notes.append("FFmpeg 에 xfade 필터가 없어 장면 전환 없이 컷으로 이어 붙임 (FFmpeg 4.3 이상 권장)")
        use_xfade = False

    seg_files: list[Path] = []
    engines: dict[str, int] = {}
    with ExitStack() as stack:
        motion = MotionRenderer(cfg, stack)
        for i, s in enumerate(shots):
            seconds = float(s["end"]) - float(s["start"])
            # 전환이 겹치는 만큼 앞 샷을 늘려 전체 길이·자막 타이밍을 그대로 유지한다
            if use_xfade and i + 1 < len(shots):
                seconds += XFADE_S if trans[i + 1] != "cut" else 1 / FPS
            fade_out = not (use_xfade and i + 1 < len(shots) and trans[i + 1] != "cut")
            out = seg_dir / f"{i:02d}_{s['id']}.mp4"
            src = s["source"]
            ty = src["type"]
            if ty == "image":
                img = sdir / src["file"]
                if not img.exists():
                    notes.append(f"{s['id']}: 이미지 없음 → 글자 카드 대체")
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
                how = motion.render(tpl, src.get("props", {}), seconds, out, colors, fade_out)
                engines[how] = engines.get(how, 0) + 1
            seg_files.append(out)
        if engines.get("card"):
            why = motion._html_error or ("motion_engine=pillow" if motion.engine == "pillow" else "")
            notes.append(f"모션 {engines['card']}개 정적 카드로 대체" + (f" — {why}" if why else ""))

    video_noaudio = sdir / "video_nocap.mp4"
    if use_xfade and len(seg_files) > 1:
        _concat_xfade(seg_files, shots, trans, video_noaudio)
    else:
        listing = seg_dir / "concat.txt"
        listing.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in seg_files) + "\n", encoding="utf-8")
        p = _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(video_noaudio)])
        if p.returncode != 0:
            raise RuntimeError(f"concat 실패: {p.stderr[-300:]}")

    # 자막 PNG overlay (한 번의 filter_complex)
    cap_dir = sdir / "captions"
    cap_dir.mkdir(exist_ok=True)
    from video.frame_tokens import hex_rgb, load_frame_tokens
    skin = load_frame_tokens().get("caption", {})
    cap_style = {"color": hex_rgb(skin.get("color", "#FFFFFF")), "stroke": hex_rgb(skin.get("stroke", "#000000")),
                 "highlight_color": hex_rgb(skin.get("highlight", "#FFD60A"))}
    unit = min(W, H) * float(skin.get("size", 1.0))
    inputs = ["-i", str(video_noaudio)]
    filters, last = [], "[0:v]"
    caps = plan.get("captions") or []
    for j, c in enumerate(caps):
        png = render_text_png(c["text"], W - 120, cap_dir / f"{j:02d}.png", font_px=int(unit * 0.059), highlight=c.get("highlight"),
                              **cap_style)
        inputs += ["-i", str(png)]
        nxt = f"[v{j}]"
        filters.append(f"{last}[{j+1}:v]overlay=x=60:y=H-h-{int(H*0.17)}:enable='between(t,{c['start']:.3f},{c['end']:.3f})'{nxt}")
        last = nxt
    # 썸네일 문구 (첫 1.2초, 상단)
    thumb = plan.get("thumbnail_text")
    if thumb:
        png = render_text_png(thumb, W - 120, cap_dir / "thumb.png", font_px=int(unit * 0.089), color=(255, 214, 10))
        inputs += ["-i", str(png)]
        idx = len(caps) + 1
        filters.append(f"{last}[{idx}:v]overlay=x=60:y={int(H*0.12)}:enable='between(t,0,1.2)'[vt]")
        last = "[vt]"
    video_cap = sdir / "video_cap.mp4"
    cmd = [FF, "-y", "-loglevel", "error"] + inputs
    if filters:
        cmd += ["-filter_complex", ";".join(filters), "-map", last]
    cmd += [*encoder_args(), "-pix_fmt", "yuv420p", "-an", str(video_cap)]
    p = _run(cmd, timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"자막 overlay 실패: {p.stderr[-400:]}")

    # 오디오: 내레이션 loudnorm 2-pass (+ 배경음악은 내레이션이 나올 때 자동으로 작아진다)
    narration = sdir / "narration.mp3"
    final = sdir / "shorts.mp4"
    total = float(plan["duration_s"])
    measure = _run([FF, "-hide_banner", "-i", str(narration), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measure.stderr, re.S)
    ln = "loudnorm=I=-16:TP=-1.5:LRA=11"
    silent = True
    if m:
        try:
            j = json.loads(m.group(0))
            vals = [float(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")]
            if all(math.isfinite(v) for v in vals) and -70 < vals[0] <= 0:  # 무음(-inf)이면 1-pass 로
                silent = False
                ln += f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    bgm_path, bgm_note = pick_bgm(cfg, run_dir)
    if bgm_path:
        vol = float((cfg.get("bgm") or {}).get("volume", 0.15) or 0.15)
        vol = min(max(vol, 0.02), 1.0) * (2.5 if silent else 1.0)  # 내레이션이 없으면 음악을 조금 키운다
        duck = has_filter("sidechaincompress") and not silent
        fc = (f"[1:a]{ln},apad,asplit=2[n1][n2];"
              f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vol:.3f},afade=t=in:d=0.6,"
              f"afade=t=out:st={max(total - 2, 0):.3f}:d=2[bg];")
        fc += ("[bg][n1]sidechaincompress=threshold=0.04:ratio=6:attack=15:release=350[bgd];[n2][bgd]" if duck else "[n2][bg]")
        fc += "amix=inputs=2:duration=first:normalize=0[a]"
        acmd = [FF, "-y", "-loglevel", "error", "-i", str(video_cap), "-i", str(narration), "-stream_loop", "-1", "-i", str(bgm_path),
                "-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        acmd = [FF, "-y", "-loglevel", "error", "-i", str(video_cap), "-i", str(narration), "-af", f"{ln},apad"]
    acmd += ["-t", f"{total:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(final)]
    p = _run(acmd)
    if p.returncode != 0 and bgm_path:
        notes.append(f"배경음악 합성 실패 → 음악 없이 제작 ({p.stderr.strip()[-120:]})")
        bgm_path, bgm_note = None, "합성 실패"
        p = _run([FF, "-y", "-loglevel", "error", "-i", str(video_cap), "-i", str(narration), "-af", f"{ln},apad",
                  "-t", f"{total:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(final)])
    if p.returncode != 0:
        raise RuntimeError(f"오디오 합성 실패: {p.stderr[-300:]}")
    for tmp in (video_noaudio, video_cap):
        tmp.unlink(missing_ok=True)
    review = review_video(final, sdir, total, plan, silent=silent)
    review.update({"aspect": aspect, "transition": default_tr if use_xfade else "cut", "motion": engines,
                   "bgm": bgm_path.name if bgm_path else None, "bgm_note": bgm_note if not bgm_path else "", "notes": notes})
    (sdir / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return review


def _caption_at(plan: dict, t: float) -> str:
    for c in plan.get("captions") or []:
        if c["start"] <= t < c["end"]:
            return c["text"]
    return plan.get("thumbnail_text", "")


# ---------- 검수 ----------
def _frame_png(mp4: Path, t: float, out: Path, width: int | None = None) -> Path | None:
    vf = ["-vf", f"scale={width}:-1"] if width else []
    p = _run([FF, "-y", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(mp4), "-frames:v", "1", *vf, str(out)])
    return out if p.returncode == 0 and out.exists() else None


def review_video(mp4: Path, sdir: Path, target_s: float, plan: dict | None = None, silent: bool = False) -> dict:
    """결정적 검사 — 길이·음량·정지 구간·첫 프레임·자막 읽기 시간 + 검수용 시트(frame_sheet, seams)."""
    plan = plan or {}
    dur = _dur(mp4)
    ebur = _run([FF, "-hide_banner", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    ms = re.findall(r"I:\s*(-?[\d.]+) LUFS", ebur)  # 마지막 값이 Summary (앞의 값들은 프레임별 진행값)
    lufs = float(ms[-1]) if ms else None
    fz = _run([FF, "-hide_banner", "-i", str(mp4), "-vf", "freezedetect=n=0.001:d=3", "-f", "null", "-"]).stderr
    freeze_s = sum(float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", fz))  # 3초 이상 완전 정지만

    # 폰 화면 크기(가로 360px)로 8칸 — 작은 화면에서 자막이 읽히는지 보는 용도
    sheet = sdir / "frame_sheet.jpg"
    _run([FF, "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps=1/{max(dur/8,1):.2f},scale=360:-1,tile=4x2", "-frames:v", "1", str(sheet)])

    # 첫 프레임이 빈 화면(단색)이 아닌지 — 썸네일로 쓰인다
    first_ok, first_std = True, None
    tmp = sdir / "_first.png"
    if _frame_png(mp4, 0.05, tmp, 270):
        from PIL import Image, ImageStat
        with Image.open(tmp) as im:
            first_std = round(sum(ImageStat.Stat(im.convert("L")).stddev), 1)
        first_ok = first_std > 6
        tmp.unlink(missing_ok=True)

    # 장면 경계 ±0.2초 스트립 — 끊김·흰 화면 번쩍임 확인
    seams = None
    cuts = [float(s["start"]) for s in (plan.get("shots") or [])[1:]]
    if cuts:
        frames = []
        for k, t in enumerate(cuts[:8]):
            for dt, tag in ((-0.2, "a"), (0.2, "b")):
                f = _frame_png(mp4, t + dt, sdir / f"_seam{k}{tag}.png", 180)
                if f:
                    frames.append(f)
        if frames:
            # 한 줄에 경계 4개(앞·뒤 2칸씩 = 8칸)
            seams = sdir / "seams.jpg"
            ins = sum((["-i", str(f)] for f in frames), [])
            cols, cell_h = 8, int(180 * H / W)
            layout = "|".join(f"{(i % cols) * 180}_{(i // cols) * cell_h}" for i in range(len(frames)))
            fc = "".join(f"[{i}:v]" for i in range(len(frames))) + f"xstack=inputs={len(frames)}:layout={layout}:fill=black"
            if len(frames) == 1:
                shutil.copy(frames[0], seams)
            elif _run([FF, "-y", "-loglevel", "error", *ins, "-filter_complex", fc, "-frames:v", "1", str(seams)]).returncode != 0:
                seams = None
            for f in frames:
                f.unlink(missing_ok=True)

    # 자막이 읽을 시간 없이 지나가는지 (초당 15자 초과)
    fast = []
    for c in plan.get("captions") or []:
        n = len(re.sub(r"\s", "", c.get("text", "")))
        shown = float(c["end"]) - float(c["start"])
        if n and shown < max(0.6, n / 15):
            fast.append({"text": c["text"], "start": c["start"], "shown_s": round(shown, 2), "need_s": round(max(0.6, n / 15), 2)})

    return {"duration_s": round(dur, 2), "target_s": target_s, "duration_ok": abs(dur - target_s) <= 1.5,
            "lufs": lufs, "loudness_ok": (lufs is not None and -19 <= lufs <= -13) or silent, "silent_narration": silent,
            "freeze_s": round(freeze_s, 2), "freeze_ok": freeze_s < 2.0,
            "first_frame_ok": first_ok, "first_frame_contrast": first_std,
            "captions_fast": fast, "captions_ok": not fast,
            "frame_sheet": str(sheet), "seams_sheet": str(seams) if seams else None}
