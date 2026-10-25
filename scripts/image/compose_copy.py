"""인스타 3:4 이미지에 후킹 카피를 코드로 합성한다 (이미지 모델에 글자를 맡기지 않는다 — 한글 깨짐 방지).

  python3 scripts/osmu.py compose --run <run> --text "카피" [--bg images/instagram_bg.jpg] [--out images/instagram.jpg] [--position top|bottom]

- 폰트: assets/fonts/ 의 OFL 한글 폰트(굵은 것 우선). 없으면 PIL 기본 폰트로 떨어지지 않고 실패를 알린다(한글이 깨지므로).
- 카피는 최대 2줄(수동 줄바꿈 '\\n' 또는 자동 분할). 반투명 띠 위에 흰 글자 + 그림자.
- 자막 PNG(숏츠)도 같은 함수(render_text_png)를 쓴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT  # noqa: E402

FONT_DIR = ROOT / "assets" / "fonts"


def find_font(bold: bool = True) -> Path | None:
    if not FONT_DIR.exists():
        return None
    try:  # 브랜드 토큰(config/frame.local.md)에 지정한 글꼴이 있으면 우선
        from video.frame_tokens import load_frame_tokens
        name = load_frame_tokens().get("font", {}).get("bold" if bold else "regular")
        if name and (FONT_DIR / name).exists():
            return FONT_DIR / name
    except Exception:
        pass
    files = sorted(FONT_DIR.glob("*.[ot]tf"))
    if not files:
        return None
    pref = [f for f in files if ("bold" in f.name.lower() or "700" in f.name)] if bold else [f for f in files if "regular" in f.name.lower()]
    return (pref or files)[0]


def _wrap(text: str, max_chars: int) -> list[str]:
    if "\n" in text:
        return [t.strip() for t in text.split("\n") if t.strip()][:2]
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    # 공백 기준으로 두 줄 분할, 없으면 중간에서
    cut = text.rfind(" ", 0, max_chars + 1)
    if cut <= 0:
        cut = max_chars
    return [text[:cut].strip(), text[cut:].strip()]


def compose(bg: Path, text: str, out: Path, position: str = "top", size: tuple[int, int] = (1080, 1440)) -> dict:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    font_path = find_font(bold=True)
    if not font_path:
        raise RuntimeError("assets/fonts 에 한글 폰트가 없습니다 (OFL 폰트 동봉 필요)")
    im = Image.open(bg).convert("RGB")
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    W, H = im.size
    lines = _wrap(text, 11)
    font_size = int(W * (0.085 if len(lines) == 1 else 0.075))
    font = ImageFont.truetype(str(font_path), font_size)
    draw = ImageDraw.Draw(im, "RGBA")
    line_h = int(font_size * 1.35)
    block_h = line_h * len(lines) + int(font_size * 1.2)
    y0 = int(H * 0.08) if position == "top" else H - int(H * 0.08) - block_h
    # 반투명 띠
    band = Image.new("RGBA", (W, block_h), (0, 0, 0, 120))
    im.paste(band, (0, y0), band)
    draw = ImageDraw.Draw(im, "RGBA")
    y = y0 + int(font_size * 0.6)
    for ln in lines:
        w = draw.textlength(ln, font=font)
        x = (W - w) / 2
        draw.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 160))  # 그림자
        draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=92)
    return {"out": str(out), "lines": lines, "font": font_path.name, "font_size": font_size}


def render_text_png(text: str, width: int, out: Path, font_px: int = 64, highlight: str | None = None,
                    color=(255, 255, 255), stroke=(0, 0, 0), highlight_color=(255, 214, 10)) -> Path:
    """숏츠 자막용 투명 PNG (drawtext 필터 없이 FFmpeg overlay 로 얹는다)."""
    from PIL import Image, ImageDraw, ImageFont
    font_path = find_font(bold=True)
    if not font_path:
        raise RuntimeError("assets/fonts 에 한글 폰트가 없습니다")
    font = ImageFont.truetype(str(font_path), font_px)
    lines = _wrap(text, 12)
    line_h = int(font_px * 1.3)
    H = line_h * len(lines) + font_px // 2
    im = Image.new("RGBA", (width, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    y = font_px // 4
    for ln in lines:
        w = draw.textlength(ln, font=font)
        x = (width - w) / 2
        draw.text((x, y), ln, font=font, fill=color + (255,), stroke_width=max(2, font_px // 14), stroke_fill=stroke + (255,))
        if highlight and highlight in ln:
            pre = ln[:ln.index(highlight)]
            hx = x + draw.textlength(pre, font=font)
            draw.text((hx, y), highlight, font=font, fill=tuple(highlight_color) + (255,), stroke_width=max(2, font_px // 14), stroke_fill=stroke + (255,))
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG")
    return out
