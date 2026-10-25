"""업그레이드 사전 검증 — 외부 연결·형식·핵심 로직을 1개 예시로 확인한다 (unittest 대상 아님, 수동 실행).

  .venv/bin/python tests/smoke/run_smoke.py [edge|stock|html|bgm ...]

결과물: output/smoke/
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from common import ensure_utf8_stdout, load_env  # noqa: E402

OUT = ROOT / "output" / "smoke"
FF = shutil.which("ffmpeg")


def smoke_edge() -> str:
    import edge_tts
    text = "하루 삼십 분, 진짜 될까요? 세 가지만 바꾸면 됩니다."

    async def go():
        com = edge_tts.Communicate(text, "ko-KR-SunHiNeural", boundary="WordBoundary")
        words, audio = [], bytearray()
        async for ch in com.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                words.append({"text": ch["text"], "start": ch["offset"] / 1e7, "end": (ch["offset"] + ch["duration"]) / 1e7})
        return bytes(audio), words

    audio, words = asyncio.run(go())
    (OUT / "edge.mp3").write_bytes(audio)
    assert len(audio) > 5000, "오디오가 너무 작음"
    assert words, "단어 타이밍 없음"
    return f"{len(audio)//1024}KB, 단어 {len(words)}개, 첫 단어 {words[0]}, 마지막 {words[-1]}"


def smoke_stock() -> str:
    env = load_env()
    key = env.get("PEXELS_API_KEY")
    if not key:
        return "SKIP — .env 에 PEXELS_API_KEY 없음"
    q = urllib.parse.quote("laptop desk morning")
    req = urllib.request.Request(f"https://api.pexels.com/v1/search?query={q}&orientation=landscape&per_page=1",
                                 headers={"Authorization": key, "User-Agent": "osmu-smoke"})
    with urllib.request.urlopen(req, timeout=20) as r:
        photo = json.loads(r.read())["photos"][0]
    req = urllib.request.Request(f"https://api.pexels.com/videos/search?query={q}&orientation=portrait&per_page=1",
                                 headers={"Authorization": key, "User-Agent": "osmu-smoke"})
    with urllib.request.urlopen(req, timeout=20) as r:
        video = json.loads(r.read())["videos"][0]
    return f"사진 {photo['width']}x{photo['height']} by {photo['photographer']} / 영상 {video['width']}x{video['height']} {video['duration']}s, 파일 {len(video['video_files'])}종"


HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: P; src: url('{font}'); font-weight: 700; }
html,body { margin:0; width:1080px; height:1920px; background:#0F172A; }
.t { position:absolute; top:760px; left:90px; right:90px; color:#fff; font:700 110px/1.3 P; word-break:keep-all;
     animation: up 0.6s ease-out both; }
@keyframes up { from { opacity:0; transform: translateY(80px); } to { opacity:1; transform:none; } }
</style></head><body><div class="t">하루 30분, 진짜 될까요?</div></body></html>"""


def smoke_html() -> str:
    from playwright.sync_api import sync_playwright
    font = (ROOT / "assets" / "fonts" / "Pretendard-Bold.otf").as_uri()
    page_file = OUT / "card.html"
    page_file.write_text(HTML.replace("{font}", font), encoding="utf-8")
    frames = OUT / "frames"
    frames.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(page_file.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.evaluate("document.getAnimations().forEach(a => a.pause())")
        for i in range(30):
            pg.evaluate(f"document.getAnimations().forEach(a => a.currentTime = {i * 1000 / 30})")
            pg.screenshot(path=str(frames / f"{i:04d}.png"))
        b.close()
    shutil.copy(frames / "0029.png", OUT / "card.png")
    mp4 = OUT / "card.mp4"
    p = subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", "30", "-i", str(frames / "%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-300:]
    return f"PNG {OUT / 'card.png'} / mp4 {mp4.stat().st_size//1024}KB (30프레임)"


def smoke_bgm() -> str:
    voice = OUT / "edge.mp3"
    if not voice.exists():
        return "SKIP — edge 먼저 실행"
    bgm = OUT / "tone.mp3"  # 테스트용 합성음(저작권 없음)
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=2", str(bgm)], check=True)
    out = OUT / "mix.m4a"
    fc = ("[1:a]aloop=loop=-1:size=2e9,volume=0.15[b];[b][0:a]sidechaincompress=threshold=0.05:ratio=8[bd];"
          "[0:a][bd]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={st}:d=1[a]")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(voice)],
                               capture_output=True, text=True).stdout)
    p = subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(voice), "-i", str(bgm), "-filter_complex",
                        fc.format(st=max(dur - 1, 0)), "-map", "[a]", "-c:a", "aac", str(out)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-400:]
    return f"믹스 {out.stat().st_size//1024}KB, 길이 {dur:.2f}s"


CHECKS = {"edge": smoke_edge, "stock": smoke_stock, "html": smoke_html, "bgm": smoke_bgm}

if __name__ == "__main__":
    ensure_utf8_stdout()
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(CHECKS)
    bad = 0
    for n in names:
        try:
            print(f"[OK]   {n}: {CHECKS[n]()}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"[FAIL] {n}: {type(e).__name__}: {e}")
    sys.exit(1 if bad else 0)
