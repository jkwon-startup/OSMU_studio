"""HTML 모션 템플릿 → 영상 (Playwright Chromium + FFmpeg). Remotion 없이, 라이선스 걱정 없이.

  python3 scripts/osmu.py motion-preview <템플릿> [--props JSON] [--seconds 3] [--aspect 9:16]

- 템플릿: templates/motion/<이름>.html — 자리표시자 {{이름:타입=기본값}} (Pixelle-Video 방식), 목록은 window.OSMU.props
- 결정적 렌더: 모든 CSS 애니메이션을 멈추고 프레임마다 currentTime 을 고정해 찍는다(HyperFrames 의 seek 방식).
- 움직임이 없는 구간은 직전 프레임을 재사용해 빠르게 끝낸다.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import subprocess
from pathlib import Path

from video.ff import FF, encoder_args

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "templates" / "motion"
FPS = 30
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*(?::\s*(text|number|color|bool))?\s*(?:=(.*?))?\s*\}\}", re.S)

SEEK_JS = """(t) => {
  const anims = document.getAnimations();
  anims.forEach(a => { a.currentTime = t; });
  return anims.map(a => { const p = a.effect.getComputedTiming().progress; return p == null ? -1 : Math.round(p * 1000); }).join(",");
}"""


def list_templates() -> list[str]:
    return sorted(p.stem for p in TEMPLATE_DIR.glob("*.html") if not p.stem.startswith("_"))


def template_params(name: str) -> list[dict]:
    """템플릿이 받는 자리표시자 목록 — 문서·검증용."""
    text = (TEMPLATE_DIR / f"{name}.html").read_text(encoding="utf-8")
    seen, out = set(), []
    for m in PLACEHOLDER.finditer(text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append({"name": m.group(1), "type": m.group(2) or "text", "default": (m.group(3) or "").strip()})
    for name in re.findall(r"OSMU\.props\.(\w+)", text):  # 스크립트에서 읽는 목록·복합 값
        if name not in seen:
            seen.add(name)
            out.append({"name": name, "type": "data", "default": ""})
    return out


def fill(text: str, props: dict) -> str:
    def rep(m: re.Match) -> str:
        name, typ, default = m.group(1), m.group(2) or "text", (m.group(3) or "").strip()
        val = props.get(name, default)
        if val is None or isinstance(val, (list, dict)):
            val = default
        if typ == "number":
            try:
                val = f"{float(val):g}"
            except (TypeError, ValueError):
                val = default or "0"
        elif typ == "bool":
            val = "true" if str(val).lower() in ("1", "true", "yes", "on") else "false"
        elif typ == "color":
            val = val if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", str(val)) else default
        return htmllib.escape(str(val), quote=True)
    return PLACEHOLDER.sub(rep, text)


def build_page(template: str, props: dict, colors: dict, seconds: float, w: int, h: int, fade_out: bool) -> str:
    src = TEMPLATE_DIR / f"{template}.html"
    if not src.exists():
        raise FileNotFoundError(f"모션 템플릿 없음: templates/motion/{template}.html (있는 것: {', '.join(list_templates())})")
    page = fill(src.read_text(encoding="utf-8"), props)
    u = min(w, h) / 100
    data = json.dumps({"props": props, "colors": colors, "duration": seconds, "width": w, "height": h}, ensure_ascii=False)
    data = data.replace("</", "<\\/")  # 글 속 </script> 로 스크립트가 끊기지 않게
    inject = (f'<base href="{TEMPLATE_DIR.as_uri()}/">'
              f"<style>:root{{--bg:{colors['bg']};--accent:{colors['accent']};--text:{colors['text']};--muted:{colors['muted']};"
              f"--dur:{seconds:.3f}s;--u:{u:.3f}px;}}</style>"
              f"<script>window.OSMU={data};</script>")
    page = re.sub(r"<head([^>]*)>", lambda m: f"<head{m.group(1)}>{inject}", page, count=1)
    if fade_out:
        page = re.sub(r"<body([^>]*)>", lambda m: f'<body{m.group(1)} class="fade-out">' if "class=" not in m.group(1)
                      else m.group(0), page, count=1)
    return page


def available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return False, "Playwright 미설치 (pip install -r requirements.txt)"
    return True, ""


class Renderer:
    """브라우저 하나를 여러 장면에 재사용한다. with 문으로 쓴다."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch()
        except Exception:
            self._pw.stop()
            raise RuntimeError("Chromium 을 열 수 없습니다 — `python -m playwright install chromium` 을 한 번 실행하세요")
        return self

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    def _open(self, template, props, colors, seconds, w, h, fade_out, work: Path):
        work.parent.mkdir(parents=True, exist_ok=True)
        work.write_text(build_page(template, props, colors, seconds, w, h, fade_out), encoding="utf-8")
        page = self._browser.new_page(viewport={"width": w, "height": h})
        page.goto(work.resolve().as_uri())
        page.evaluate("document.fonts.ready.then(() => true)")
        page.evaluate("() => document.getAnimations().forEach(a => a.pause())")
        return page

    def still(self, template: str, props: dict, out: Path, colors: dict, w: int, h: int, at: float | None = None) -> Path:
        """정지 화면 PNG (등장 애니메이션이 끝난 시점)."""
        page = self._open(template, props, colors, 10.0, w, h, False, out.with_suffix(".html"))
        try:
            page.evaluate(SEEK_JS, (at if at is not None else 3.0) * 1000)
            page.screenshot(path=str(out), type="png")
        finally:
            page.close()
        return out

    def video(self, template: str, props: dict, seconds: float, out: Path, colors: dict, w: int, h: int,
              fade_out: bool = True) -> Path:
        frames = max(int(round(seconds * FPS)), 2)
        page = self._open(template, props, colors, seconds, w, h, fade_out, out.with_suffix(".html"))
        cmd = [FF, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
               *encoder_args(), "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            prev_sig, prev = None, b""
            for i in range(frames):
                sig = page.evaluate(SEEK_JS, i * 1000 / FPS)
                if sig != prev_sig or not prev:
                    prev = page.screenshot(type="jpeg", quality=94)
                    prev_sig = sig
                proc.stdin.write(prev)
            proc.stdin.close()
            err = proc.stderr.read().decode("utf-8", "replace")
            if proc.wait(timeout=300) != 0:
                raise RuntimeError(f"모션 인코딩 실패: {err[-300:]}")
        finally:
            page.close()
            if proc.poll() is None:
                proc.kill()
            proc.stderr.close()
        return out
