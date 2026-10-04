"""이미지 생성 — 설치 때 고른 서비스(gemini | pixverse)로 prompts.json 의 항목을 만든다. 키는 .env 에서만 읽는다.

  python3 scripts/osmu.py image --run <run> [--prompts-stdin | --prompts images/prompts.json] [--provider gemini|pixverse]

prompts.json 항목: {"file": "blog_1.jpg", "ratio": "16:9", "prompt": "...", "ref": "(선택) 참조 이미지 경로"}
결과: <run>/images/<file> (실패 항목은 건너뛰고 image_results.json 에 기록)
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import load_env  # noqa: E402

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
NO_TEXT = " No text, no letters, no numbers, no logos, no watermark, no UI."
RATIO_SIZE = {"16:9": (1920, 1080), "3:4": (1080, 1440), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:3": (1440, 1080)}


def _ensure_no_text(prompt: str) -> str:
    return prompt if "no text" in prompt.lower() else prompt.rstrip() + NO_TEXT


# ---------- Gemini ----------
def gemini_image(prompt: str, ratio: str, out: Path, env: dict, cfg: dict) -> tuple[bool, str]:
    key = env.get("GEMINI_API_KEY")
    if not key:
        return False, "GEMINI_API_KEY 없음"
    model = cfg.get("gemini_image_model", "gemini-2.5-flash-image")
    body = {"contents": [{"parts": [{"text": _ensure_no_text(prompt)}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ratio}}}
    req = urllib.request.Request(f"{GEMINI_BASE}/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            img = next((p["inlineData"] for p in parts if "inlineData" in p), None)
            if not img:
                return False, "응답에 이미지 없음(안전 필터 또는 모델 ID)"
            raw = base64.b64decode(img["data"])
            _save_as_jpg(raw, out, ratio)
            return True, model
        except urllib.error.HTTPError as e:
            msg = e.read()[:200].decode("utf-8", "replace")
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(20 * (attempt + 1))  # 분당 한도(429)는 기다리면 풀린다
                continue
            return False, f"HTTP {e.code} {msg}"
        except (urllib.error.URLError, TimeoutError) as e:
            return False, f"연결 실패 {type(e).__name__}"
    return False, "재시도 실패"


# ---------- Pixverse ----------
def pixverse_cmd(env: dict) -> list[str] | None:
    if env.get("PIXVERSE_CLI"):
        p = Path(env["PIXVERSE_CLI"]).expanduser()
        if p.exists():
            return [shutil.which("node") or "node", str(p)] if p.suffix == ".js" else [str(p)]
    exe = shutil.which("pixverse") or shutil.which("pixverse.cmd")
    return [exe] if exe else None


def _url_from_json(text: str) -> str | None:
    m = re.findall(r"https://[^\"\s]+\.(?:png|jpg|jpeg|webp|mp4)[^\"\s]*", text)
    return m[0] if m else None


def _download(url: str, out: Path) -> None:
    # media.pixverse.ai 는 User-Agent 없는 요청을 403 으로 거부한다
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OSMU Studio)"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        out.write_bytes(resp.read())


def pixverse_image(prompt: str, ratio: str, out: Path, env: dict, cfg: dict, ref: Path | None = None) -> tuple[bool, str]:
    cli = pixverse_cmd(env)
    if not cli:
        return False, "Pixverse CLI 없음"
    model = cfg.get("pixverse_image_model", "gpt-image-2.0")
    cmd = cli + ["create", "image", "--prompt", _ensure_no_text(prompt), "-m", model, "--aspect-ratio", ratio, "--json"]
    if ref and ref.exists():
        cmd += ["--image", str(ref)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=400, encoding="utf-8", errors="replace")
    url = _url_from_json(p.stdout)
    if p.returncode != 0 or not url:
        return False, f"exit {p.returncode}: {(p.stderr or p.stdout)[-200:]}"
    try:
        tmp = out.with_suffix(".download")
        _download(url, tmp)
        _save_as_jpg(tmp.read_bytes(), out, ratio)
        tmp.unlink(missing_ok=True)
        return True, model
    except Exception as e:
        return False, f"다운로드 실패 {type(e).__name__}"


def pixverse_clip(image: Path, prompt: str, ratio: str, out: Path, env: dict, cfg: dict, seconds: int = 5) -> tuple[bool, str]:
    cli = pixverse_cmd(env)
    if not cli:
        return False, "Pixverse CLI 없음"
    model = cfg.get("pixverse_video_model", "v6")
    cmd = cli + ["create", "video", "--image", str(image), "--prompt", prompt + ". Stable composition, no new text, preserve subject.",
                 "-m", model, "--aspect-ratio", ratio, "-d", str(seconds), "--no-audio", "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
    url = _url_from_json(p.stdout)
    if p.returncode != 0 or not url:
        return False, f"exit {p.returncode}: {(p.stderr or p.stdout)[-200:]}"
    try:
        _download(url, out)
        return True, model
    except Exception as e:
        return False, f"다운로드 실패 {type(e).__name__}"


# ---------- 공통 ----------
def _save_as_jpg(raw: bytes, out: Path, ratio: str) -> None:
    """어떤 포맷으로 오든 목표 비율로 중앙 크롭·리사이즈해 JPG 로 저장."""
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    tw, th = RATIO_SIZE.get(ratio, im.size)
    target = tw / th
    w, h = im.size
    if abs(w / h - target) > 0.01:
        if w / h > target:
            nw = int(h * target); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / target); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((tw, th), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=92)


def generate_all(run_dir: Path, items: list[dict], provider: str, cfg: dict, out_dir: Path | None = None) -> list[dict]:
    env = load_env()
    img_dir = out_dir or (run_dir / "images")
    img_dir.mkdir(parents=True, exist_ok=True)
    (img_dir / "prompts.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    results = []
    for it in items:
        out = img_dir / it["file"]
        ratio = it.get("ratio", "16:9")
        ref = (run_dir / it["ref"]) if it.get("ref") else None
        t0 = time.time()
        if provider == "gemini":
            ok, detail = gemini_image(it["prompt"], ratio, out, env, cfg)
        elif provider == "pixverse":
            ok, detail = pixverse_image(it["prompt"], ratio, out, env, cfg, ref)
        else:
            ok, detail = False, f"알 수 없는 provider {provider}"
        results.append({"file": it["file"], "ok": ok, "detail": detail, "seconds": round(time.time() - t0, 1)})
        print(f"[{'OK' if ok else 'FAIL'}] {it['file']} ({results[-1]['seconds']}s) {detail if not ok else ''}")
    (img_dir / "image_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
