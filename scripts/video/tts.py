"""TTS + 문장별 타이밍 — 공급자 무관(문장별 합성 → ffprobe 길이 누적 → concat). 양 OS.

  python3 scripts/osmu.py tts --run <run> [--provider edge|elevenlabs|gemini|pixverse|silent]

입력: <run>/08_shorts/script.json (beats[].narration / tts_text 또는 beats[].tts)
출력: <run>/08_shorts/narration.mp3, timing.json
  timing.json = {"provider": "edge", "fallback": [], "total_s": 29.8,
                 "units": [{"beat": "hook", "text": "하루 30분, 진짜 될까요?", "tts": "하루 삼십 분…", "start": 0.0, "end": 2.1,
                            "words": [{"text": "하루", "start": 0.1, "end": 0.4}, …]}, …]}   # words 는 edge 일 때만

공급자가 실패하면(키 없음·한도·네트워크) config `tts_fallback`(기본 edge → silent) 순서로 내려간다.
- edge: Microsoft Edge 무료 음성(edge-tts 패키지, 키 불필요, 인터넷 필요). 단어별 타이밍도 받는다.
- silent: 음성 없이 글자 수로 길이를 추정한 무음 — 자막만 있는 숏츠라도 끝까지 만든다.
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
from common import load_env, redact  # noqa: E402

GAP_S = 0.18  # 문장 사이 쉼
SENT_RX = re.compile(r"(?<=[.?!…])\s+")
PROVIDERS = ("edge", "elevenlabs", "gemini", "pixverse", "silent")
DEFAULT_FALLBACK = ["edge", "silent"]
EDGE_VOICE = "ko-KR-SunHiNeural"
SILENT_CPS = 7.0  # 무음 모드 길이 추정: 약 7자/초 (rules/shorts-script.md)


class ProviderUnavailable(RuntimeError):
    """이 공급자로는 진행 불가 — 다음 폴백으로 넘어간다."""


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


def synth_edge(text: str, out: Path, cfg) -> tuple[bool, str, list[dict]]:
    """무료 Edge 음성. 단어 경계 타이밍(초, 문장 기준)을 함께 돌려준다."""
    try:
        import asyncio
        import edge_tts
    except ImportError:
        return False, "edge-tts 패키지 없음 — `pip install -r requirements.txt` 를 .venv 안에서 다시 실행하세요", []
    voice = cfg.get("edge_tts_voice") or EDGE_VOICE
    rate = cfg.get("edge_tts_rate") or "+0%"
    if not re.fullmatch(r"[+-]\d{1,3}%", rate):
        rate = "+0%"

    async def go():
        com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        audio, words = bytearray(), []
        async for ch in com.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                st = ch["offset"] / 1e7
                words.append({"text": ch["text"], "start": round(st, 3), "end": round(st + ch["duration"] / 1e7, 3)})
        return bytes(audio), words

    try:
        audio, words = asyncio.run(go())
    except Exception as e:  # 네트워크 차단·음성 이름 오류 등
        return False, f"{type(e).__name__}: {str(e)[:120]} (인터넷 연결 또는 config edge_tts_voice 확인)", []
    if len(audio) < 1000:
        return False, "오디오가 비어 있음", []
    out.write_bytes(audio)
    return True, "ok", words


def synth_silent(text: str, out: Path) -> tuple[bool, str]:
    seconds = max(0.8, len(text.strip()) / SILENT_CPS)
    p = subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                        "-t", f"{seconds:.3f}", "-codec:a", "libmp3lame", "-b:a", "128k", str(out)], capture_output=True, text=True)
    return (p.returncode == 0), (p.stderr[-160:] or "ok")


# ---------- 조립 ----------
def ffprobe_duration(p: Path) -> float:
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def provider_chain(primary: str, cfg: dict) -> list[str]:
    """설정 공급자 → tts_fallback 순. 알 수 없는 이름은 건너뛴다(오타가 있어도 실행은 이어지게)."""
    fallback = cfg.get("tts_fallback", DEFAULT_FALLBACK)
    if not isinstance(fallback, list):
        fallback = DEFAULT_FALLBACK
    chain: list[str] = []
    for p in [primary, *fallback]:
        if p not in PROVIDERS:
            print(f"[알림] 알 수 없는 음성 공급자 '{p}' 는 건너뜁니다 (가능: {', '.join(PROVIDERS)})")
        elif p not in chain:
            chain.append(p)
    return chain or ["silent"]


def _precheck(provider: str, env: dict, cfg: dict) -> str | None:
    """돈·시간을 쓰기 전에 확인. 문제가 있으면 쉬운 설명을 돌려준다."""
    if provider == "elevenlabs" and not env.get("ELEVENLABS_API_KEY"):
        return ".env 에 ELEVENLABS_API_KEY 가 없습니다"
    if provider == "gemini" and not env.get("GEMINI_API_KEY"):
        return ".env 에 GEMINI_API_KEY 가 없습니다"
    if provider == "pixverse":
        from image.generate import pixverse_cmd
        if not pixverse_cmd(env):
            return "Pixverse CLI 가 없습니다 (npm install -g pixverse 후 pixverse auth login)"
    return None


def _synth_all(provider: str, units: list[dict], parts_dir: Path, env: dict, cfg: dict) -> None:
    """한 공급자로 모든 문장을 합성한다. 한 문장이라도 실패하면 ProviderUnavailable (목소리가 섞이지 않게 통째로 폴백)."""
    reason = _precheck(provider, env, cfg)
    if reason:
        raise ProviderUnavailable(reason)
    voice = None
    if provider == "elevenlabs":
        voice = eleven_voice(env, cfg)
        if not voice:
            raise ProviderUnavailable("ElevenLabs 음성 목록을 받지 못했습니다(키 오류 또는 네트워크)")
    t = 0.0
    for i, u in enumerate(units):
        out = parts_dir / f"{provider}_{i:02d}.mp3"
        words: list[dict] = []
        if provider == "edge":
            ok, d, words = synth_edge(u["tts"], out, cfg)
        elif provider == "elevenlabs":
            ok, d = synth_elevenlabs(u["tts"], out, env, cfg, voice)
        elif provider == "gemini":
            ok, d = synth_gemini(u["tts"], out, env, cfg)
        elif provider == "pixverse":
            ok, d = synth_pixverse(u["tts"], out, env, cfg)
        else:
            ok, d = synth_silent(u["tts"], out)
        if not ok:
            raise ProviderUnavailable(f"{i + 1}번째 문장 실패: {d}")
        dur = ffprobe_duration(out)
        u["start"], u["end"], u["file"] = round(t, 3), round(t + dur, 3), out.name
        if words:
            u["words"] = [{**w, "start": round(t + w["start"], 3), "end": round(t + w["end"], 3)} for w in words]
        else:
            u.pop("words", None)
        t += dur + GAP_S
        print(f"[{i:02d}] {u['start']:5.2f}-{u['end']:5.2f}s  {u['text']}")


def run(run_dir: Path, cfg: dict, provider: str | None = None) -> dict:
    env = load_env()
    sdir = run_dir / "08_shorts"
    script = json.loads((sdir / "script.json").read_text(encoding="utf-8"))
    primary = provider or cfg.get("tts_provider", "edge")
    units = units_from_script(script)
    parts_dir = sdir / "tts_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    fallback_log: list[dict] = []
    used = None
    for p in provider_chain(primary, cfg):
        print(f"음성 공급자: {p}")
        try:
            _synth_all(p, units, parts_dir, env, cfg)
            used = p
            break
        except ProviderUnavailable as e:
            fallback_log.append({"provider": p, "reason": redact(str(e), env)})
            print(f"[알림] {p} 음성을 쓸 수 없어 다음 방법으로 넘어갑니다 — {fallback_log[-1]['reason']}")
    if not used:
        raise RuntimeError("모든 음성 방법이 실패했습니다: " + " / ".join(f"{f['provider']}: {f['reason']}" for f in fallback_log))

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
    timing = {"provider": used, "fallback": fallback_log, "total_s": round(total, 3), "units": units}
    (sdir / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"narration.mp3 {total:.1f}s (대본 목표 {script.get('duration_s')}s, 음성 {used})")
    if used == "silent":
        print("[알림] 음성 없이 자막만 있는 숏츠가 됩니다. 음성을 넣으려면 인터넷 연결을 확인하거나 `osmu.py selftest --only edge_tts` 를 실행해 보세요.")
    return timing
