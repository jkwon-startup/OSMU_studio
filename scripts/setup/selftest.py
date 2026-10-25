"""외부 연결 검사 (selftest) — 설정된 서비스에 실제로 1건씩 호출해 PASS/FAIL 을 보고한다.

유료 서비스를 설정했다면 비용이 드는 호출(이미지 1장, TTS 1문장)이 포함되므로 설치 때와 문제 진단 때만 실행한다.
무료 경로(edge-tts, 스톡)는 비용이 없다.
결과 파일은 output/selftest/ 에 저장. 키 값은 절대 출력하지 않는다.

사용: python3 scripts/osmu.py selftest [--only slack,gemini_image,...]
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import OUTPUT_DIR, kst_now, load_config, load_env  # noqa: E402
import notify  # noqa: E402

OUT = OUTPUT_DIR / "selftest"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_ELEVEN_MODEL = "eleven_multilingual_v2"
TEST_SENTENCE = "오늘 아침 일곱 시, 콘텐츠 스튜디오가 첫 번째 주제를 준비했습니다."
TEST_IMAGE_PROMPT = ("Photorealistic photo of a sunlit wooden desk by a window with a cup of coffee and a notebook, "
                     "soft morning light, shallow depth of field. No text, no letters, no logos, no watermark.")


def _post_json(url: str, body: dict, headers: dict, timeout: int = 120) -> tuple[int, dict | bytes]:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(raw) if "json" in ctype else raw)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def _get_json(url: str, headers: dict, timeout: int = 60) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


# ---------- 개별 검사: 각각 (ok, detail) 반환 ----------
def check_slack(env, cfg):
    if not env.get("SLACK_WEBHOOK_URL"):
        return None, "SLACK_WEBHOOK_URL 없음 — 건너뜀"
    ok, d = notify.send("slack", env, f"[OSMU Studio] 연결 테스트 {kst_now():%Y-%m-%d %H:%M} KST — 이 메시지가 보이면 Slack 알림이 동작합니다.")
    return ok, d


def check_telegram(env, cfg):
    if not env.get("TELEGRAM_BOT_TOKEN"):
        return None, "TELEGRAM_BOT_TOKEN 없음 — 건너뜀"
    ok, d = notify.send("telegram", env, f"[OSMU Studio] 연결 테스트 {kst_now():%Y-%m-%d %H:%M} KST")
    return ok, d


def check_gemini_image(env, cfg):
    key = env.get("GEMINI_API_KEY")
    if not key:
        return None, "GEMINI_API_KEY 없음 — 건너뜀"
    model = cfg.get("gemini_image_model", DEFAULT_GEMINI_IMAGE_MODEL)
    body = {"contents": [{"parts": [{"text": TEST_IMAGE_PROMPT}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "3:4"}}}
    status, data = _post_json(f"{GEMINI_BASE}/models/{model}:generateContent", body, {"x-goog-api-key": key}, timeout=180)
    if status != 200 or not isinstance(data, dict):
        msg = data.get("error", {}).get("message", "") if isinstance(data, dict) else ""
        return False, f"HTTP {status} {msg[:160]}"
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    img = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not img:
        return False, "응답에 이미지 없음 (모델 ID 또는 비율 미지원 가능성)"
    ext = "png" if "png" in img.get("mimeType", "") else "jpg"
    out = OUT / f"gemini_image_3x4.{ext}"
    out.write_bytes(base64.b64decode(img["data"]))
    size = _image_size(out)
    return True, f"{model} → {out.name} {size}"


def _image_size(path: Path) -> str:
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        return f"{w}x{h} (비율 {w/h:.3f}, 3:4={0.75})"
    except Exception:
        return f"{path.stat().st_size} bytes"


def check_pixverse(env, cfg):
    cli = _pixverse_cmd(env)
    if not cli:
        return None, "Pixverse CLI 없음 — 건너뜀 (npm install -g pixverse 또는 .env PIXVERSE_CLI=index.js 경로)"
    p = subprocess.run(cli + ["auth", "status", "--json"], capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return False, f"auth status 실패 (exit {p.returncode}) — pixverse auth login 필요"
    p2 = subprocess.run(cli + ["account", "info", "--json"], capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    try:
        info = json.loads(p2.stdout)
        credit = info.get("credit") or info.get("credits") or info.get("balance") or info
        return True, f"로그인됨, 계정 정보 수신 (크레딧 필드: {str(credit)[:80]})"
    except json.JSONDecodeError:
        return p2.returncode == 0, (p2.stdout or p2.stderr)[:120]


def _pixverse_cmd(env) -> list[str] | None:
    if env.get("PIXVERSE_CLI"):
        p = Path(env["PIXVERSE_CLI"]).expanduser()
        if p.exists():
            return [shutil.which("node") or "node", str(p)] if p.suffix == ".js" else [str(p)]
    exe = shutil.which("pixverse") or shutil.which("pixverse.cmd")
    return [exe] if exe else None


def check_elevenlabs(env, cfg):
    key = env.get("ELEVENLABS_API_KEY")
    if not key:
        return None, "ELEVENLABS_API_KEY 없음 — 건너뜀"
    voice = cfg.get("elevenlabs_voice_id")
    if not voice:
        status, data = _get_json("https://api.elevenlabs.io/v1/voices", {"xi-api-key": key})
        if status != 200:
            return False, f"voices HTTP {status}"
        voices = data.get("voices", [])
        if not voices:
            return False, "사용 가능한 음성 없음"
        voice = voices[0]["voice_id"]
        note = f"voice_id 미설정 → 첫 음성 '{voices[0].get('name')}' 사용"
    else:
        note = f"voice_id 설정값 사용"
    model = cfg.get("elevenlabs_model", DEFAULT_ELEVEN_MODEL)
    status, data = _post_json(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
                              {"text": TEST_SENTENCE, "model_id": model}, {"xi-api-key": key})
    if status != 200 or not isinstance(data, dict):
        return False, f"with-timestamps HTTP {status} {str(data)[:120]}"
    audio = data.get("audio_base64")
    align = data.get("alignment") or {}
    if not audio:
        return False, "audio_base64 없음"
    (OUT / "elevenlabs_test.mp3").write_bytes(base64.b64decode(audio))
    chars = align.get("characters", [])
    ends = align.get("character_end_times_seconds", [])
    return True, f"{note}; 오디오 저장, alignment 문자 {len(chars)}개, 마지막 종료 {ends[-1] if ends else '?'}초 — 키: {sorted(align.keys())}"


def check_gemini_tts(env, cfg):
    key = env.get("GEMINI_API_KEY")
    if not key:
        return None, "GEMINI_API_KEY 없음 — 건너뜀"
    model = cfg.get("gemini_tts_model", DEFAULT_GEMINI_TTS_MODEL)
    body = {"contents": [{"parts": [{"text": TEST_SENTENCE}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg.get("gemini_tts_voice", "Kore")}}}}}
    status, data = _post_json(f"{GEMINI_BASE}/models/{model}:generateContent", body, {"x-goog-api-key": key}, timeout=180)
    if status != 200 or not isinstance(data, dict):
        msg = data.get("error", {}).get("message", "") if isinstance(data, dict) else ""
        return False, f"HTTP {status} {msg[:160]}"
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    aud = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not aud:
        return False, "응답에 오디오 없음"
    pcm = base64.b64decode(aud["data"])
    _write_wav(OUT / "gemini_tts_test.wav", pcm, 24000)
    return True, f"{model} → gemini_tts_test.wav ({len(pcm)/48000:.1f}초, mime {aud.get('mimeType')})"


def _write_wav(path: Path, pcm: bytes, rate: int) -> None:
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def check_youtube(env, cfg):
    key = env.get("YOUTUBE_API_KEY")
    if not key:
        return None, "YOUTUBE_API_KEY 없음 — 건너뜀 (없으면 웹 검색으로 대체)"
    url = ("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&order=viewCount&maxResults=3"
           "&q=" + urllib.request.quote("AI 마케팅") + f"&key={key}")
    status, data = _get_json(url, {})
    return status == 200, f"HTTP {status}, 결과 {len(data.get('items', []))}건"


def check_edge_tts(env, cfg):
    """무료 음성 — 키 없이 한 문장 합성 + 단어 타이밍."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from video.tts import synth_edge
    out = OUT / "edge_tts_test.mp3"
    ok, d, words = synth_edge(TEST_SENTENCE, out, cfg)
    if not ok:
        return False, d
    return True, f"{cfg.get('edge_tts_voice') or 'ko-KR-SunHiNeural'} → {out.name} ({out.stat().st_size // 1024} KB, 단어 타이밍 {len(words)}개)"


def check_stock(env, cfg):
    """무료 스톡 — 사진 1장 검색·다운로드 (Pexels 우선, 없으면 Pixabay)."""
    from image import stock
    if not stock.available(env):
        return None, "PEXELS_API_KEY / PIXABAY_API_KEY 없음 — 건너뜀 (https://www.pexels.com/api/ 무료 키)"
    ok, d = stock.fetch("photo", "coffee desk morning", "3:4", OUT / "stock_test.jpg", env, OUT / "stock_credits.json")
    return ok, d


def check_ffmpeg_compose(env, cfg):
    """외부 서비스 없이: 단색 이미지 + 무음으로 2초 mp4 를 만들어 합성 경로가 동작하는지."""
    ff = shutil.which("ffmpeg")
    if not ff:
        return False, "ffmpeg 없음"
    out = OUT / "ffmpeg_smoke.mp4"
    cmd = [ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x224466:s=1080x1920:r=30:d=2",
           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "2",
           "-vf", "zoompan=z='min(zoom+0.0015,1.1)':d=60:s=1080x1920", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return False, p.stderr.strip()[-200:]
    return True, f"{out.name} 생성 ({out.stat().st_size // 1024} KB)"


CHECKS = [
    ("ffmpeg_compose", "FFmpeg 합성(로컬)", check_ffmpeg_compose),
    ("edge_tts", "무료 음성 edge-tts", check_edge_tts),
    ("stock", "무료 스톡 사진 (Pexels/Pixabay)", check_stock),
    ("slack", "Slack 알림", check_slack),
    ("telegram", "텔레그램 알림", check_telegram),
    ("gemini_image", "Gemini 이미지 3:4", check_gemini_image),
    ("pixverse", "Pixverse CLI 로그인", check_pixverse),
    ("elevenlabs", "ElevenLabs TTS + 타임스탬프", check_elevenlabs),
    ("gemini_tts", "Gemini TTS", check_gemini_tts),
    ("youtube", "YouTube Data API", check_youtube),
]


def run(only: set[str] | None = None) -> bool:
    OUT.mkdir(parents=True, exist_ok=True)
    env, cfg = load_env(), load_config()
    all_ok = True
    results = []
    for key, label, fn in CHECKS:
        if only and key not in only:
            continue
        t0 = time.time()
        try:
            ok, detail = fn(env, cfg)
        except Exception as e:  # 검사 자체가 죽어도 다음 항목 진행
            ok, detail = False, f"예외: {type(e).__name__}: {str(e)[:120]}"
        mark = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
        if ok is False:
            all_ok = False
        print(f"[{mark}] {label} ({time.time()-t0:.1f}s): {detail}")
        results.append({"check": key, "result": mark, "detail": detail})
    (OUT / "selftest.json").write_text(json.dumps({"at": kst_now().isoformat(), "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nselftest:", "실패 없음" if all_ok else "실패 항목 있음 — 위 내용 확인")
    return all_ok


if __name__ == "__main__":
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
    sys.exit(0 if run(only) else 1)
