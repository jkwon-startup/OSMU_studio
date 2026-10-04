"""TTS + 문장별 타이밍 — 공급자 무관(문장별 합성 → ffprobe 길이 누적 → concat). 양 OS.

  python3 scripts/osmu.py tts --run <run> [--provider elevenlabs|gemini|pixverse]

입력: <run>/08_shorts/script.json (beats[].narration / tts_text 또는 beats[].tts)
출력: <run>/08_shorts/narration.mp3, timing.json
  timing.json = {"total_s": 29.8, "units": [{"beat": "hook", "text": "하루 30분, 진짜 될까요?", "tts": "하루 삼십 분…", "start": 0.0, "end": 2.1}, …]}
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import load_env  # noqa: E402

GAP_S = 0.18  # 문장 사이 쉼
SENT_RX = re.compile(r"(?<=[.?!…])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_RX.split(text.strip()) if s.strip()]


def units_from_script(script: dict) -> list[dict]:
    """beat 별 내레이션을 문장 단위로 나누고, tts 텍스트(숫자 한글)를 같은 개수로 맞춘다."""
    units = []
    all_tts = split_sentences(script.get("tts_text", "")) if script.get("tts_text") else []
    cursor = 0
    for b in script["beats"]:
        sents = split_sentences(b["narration"])
        if b.get("tts"):
            tts_sents = split_sentences(b["tts"])
        else:
            tts_sents = all_tts[cursor:cursor + len(sents)]
            cursor += len(sents)
        if len(tts_sents) != len(sents):
            tts_sents = sents  # 개수가 안 맞으면 원문 사용
        for s, t in zip(sents, tts_sents):
            units.append({"beat": b["id"], "text": s, "tts": t})
    return units


# ---------- 공급자 ----------
def _post(url: str, body: dict, headers: dict, timeout=120) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), ""


def eleven_voice(env, cfg) -> str | None:
    v = cfg.get("elevenlabs_voice_id")
    if v:
        return v
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": env["ELEVENLABS_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            voices = json.loads(r.read()).get("voices", [])
        return voices[0]["voice_id"] if voices else None
    except Exception:
        return None


def synth_elevenlabs(text: str, out: Path, env, cfg, voice: str) -> tuple[bool, str]:
    status, raw, _ = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                           {"text": text, "model_id": cfg.get("elevenlabs_model", "eleven_multilingual_v2")},
                           {"xi-api-key": env["ELEVENLABS_API_KEY"]})
    if status != 200:
        return False, f"HTTP {status} {raw[:120].decode('utf-8', 'replace')}"
    out.write_bytes(raw)
    return True, "ok"


def synth_gemini(text: str, out: Path, env, cfg) -> tuple[bool, str]:
    model = cfg.get("gemini_tts_model", "gemini-2.5-flash-preview-tts")
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg.get("gemini_tts_voice", "Kore")}}}}}
    status, raw, _ = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", body,
                           {"x-goog-api-key": env["GEMINI_API_KEY"]}, timeout=180)
    if status != 200:
        return False, f"HTTP {status} {raw[:120].decode('utf-8', 'replace')}"
    data = json.loads(raw)
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    aud = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not aud:
        return False, "오디오 없음"
    pcm = base64.b64decode(aud["data"])
    wav = out.with_suffix(".wav")
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
    wav.unlink(missing_ok=True)
    return True, "ok"


def synth_pixverse(text: str, out: Path, env, cfg) -> tuple[bool, str]:
    from image.generate import pixverse_cmd, _url_from_json, _download
    cli = pixverse_cmd(env)
    if not cli:
        return False, "Pixverse CLI 없음"
    cmd = cli + ["create", "voice", "--text", text, "--json"]
    if cfg.get("pixverse_voice_id"):
        cmd += ["--voice-id", cfg["pixverse_voice_id"]]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
    url = _url_from_json(p.stdout) or next(iter(re.findall(r"https://[^\"\s]+\.(?:mp3|wav|m4a)[^\"\s]*", p.stdout)), None)
    if p.returncode != 0 or not url:
        return False, f"exit {p.returncode}: {(p.stderr or p.stdout)[-160:]}"
    tmp = out.with_suffix(".dl")
    _download(url, tmp)
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-i", str(tmp), "-codec:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
    tmp.unlink(missing_ok=True)
    return True, "ok"


# ---------- 조립 ----------
def ffprobe_duration(p: Path) -> float:
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def run(run_dir: Path, cfg: dict, provider: str | None = None) -> dict:
    env = load_env()
    sdir = run_dir / "08_shorts"
    script = json.loads((sdir / "script.json").read_text(encoding="utf-8"))
    provider = provider or cfg.get("tts_provider", "elevenlabs")
    units = units_from_script(script)
    parts_dir = sdir / "tts_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    voice = eleven_voice(env, cfg) if provider == "elevenlabs" else None
    if provider == "elevenlabs" and not (env.get("ELEVENLABS_API_KEY") and voice):
        raise RuntimeError("ELEVENLABS_API_KEY 또는 음성 없음")
    if provider == "gemini" and not env.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY 없음")

    t = 0.0
    for i, u in enumerate(units):
        out = parts_dir / f"{i:02d}.mp3"
        if provider == "elevenlabs":
            ok, d = synth_elevenlabs(u["tts"], out, env, cfg, voice)
        elif provider == "gemini":
            ok, d = synth_gemini(u["tts"], out, env, cfg)
        elif provider == "pixverse":
            ok, d = synth_pixverse(u["tts"], out, env, cfg)
        else:
            raise RuntimeError(f"알 수 없는 tts_provider {provider}")
        if not ok:
            raise RuntimeError(f"TTS 실패({i}: {u['text'][:20]}…): {d}")
        dur = ffprobe_duration(out)
        u["start"], u["end"], u["file"] = round(t, 3), round(t + dur, 3), out.name
        t += dur + GAP_S
        print(f"[{i:02d}] {u['start']:5.2f}-{u['end']:5.2f}s  {u['text']}")

    # concat (문장 사이 GAP 무음 삽입)
    listing = sdir / "tts_concat.txt"
    lines = []
    silence = parts_dir / "gap.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", str(GAP_S), "-codec:a", "libmp3lame", "-b:a", "128k", str(silence)], check=True)
    for u in units:
        lines.append(f"file '{(parts_dir / u['file']).resolve().as_posix()}'")
        lines.append(f"file '{silence.resolve().as_posix()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    narration = sdir / "narration.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-codec:a", "libmp3lame", "-b:a", "128k", str(narration)], check=True)
    total = ffprobe_duration(narration)
    timing = {"provider": provider, "total_s": round(total, 3), "units": units}
    (sdir / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"narration.mp3 {total:.1f}s (대본 목표 {script.get('duration_s')}s)")
    return timing
