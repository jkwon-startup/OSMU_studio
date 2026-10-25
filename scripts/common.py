"""공통 유틸 — 표준 라이브러리만 사용 (양 OS).

- ROOT: 저장소 루트
- load_env(): .env 를 읽어 dict 로 반환 (os.environ 에는 넣지 않는다 — 서브프로세스로 새지 않게)
- load_config(): config.example.json(기본값) 위에 config.local.json 을 덮어쓴 실제 설정
- redact(): 로그·알림에서 비밀값 가리기
- kst_now(): 한국시간 (UTC+9 고정, tzdata 불필요)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
KST = timezone(timedelta(hours=9), name="KST")

IS_WINDOWS = os.name == "nt"


def kst_now() -> datetime:
    return datetime.now(tz=KST)


def load_env(path: Path | None = None) -> dict[str, str]:
    """`.env` 파싱. KEY=VALUE 한 줄씩, 따옴표 허용, # 주석 무시. 값은 절대 로그에 찍지 않는다."""
    path = path or ROOT / ".env"
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            env[key] = value
    return env


# 선택지가 정해진 설정 — 잘못된 값이면 기본값으로 바꾸고 경고한다(업데이트 후 옛 설정·오타로 실행이 멈추지 않게).
CHOICES = {
    "image_provider": ("stock", "gemini", "pixverse"),
    "tts_provider": ("edge", "elevenlabs", "gemini", "pixverse", "silent"),
    "motion_engine": ("html", "remotion", "pillow"),
    "shorts_aspect": ("9:16", "1:1", "16:9"),
    "threads_style": ("반말", "혼잣말", "존댓말"),
}
_warned: set[str] = set()


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _read_json_lenient(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        if str(path) not in _warned:
            _warned.add(str(path))
            print(f"[설정 경고] {path.name} 을 읽지 못해 기본값을 씁니다 — {e}", file=sys.stderr)
        return {}


def load_config() -> dict:
    """config.example.json(기본값) 위에 config.local.json(설치자 값)을 덮어쓴다.
    새 버전에 추가된 설정은 기본값으로 채워지고, 잘못된 선택지는 기본값으로 돌아간다."""
    example = CONFIG_DIR / "config.example.json"
    local = CONFIG_DIR / "config.local.json"
    base = _read_json_lenient(example) if example.exists() else {}
    cfg = _deep_merge(base, _read_json_lenient(local)) if local.exists() else base
    for key, allowed in CHOICES.items():
        if key in cfg and cfg[key] not in allowed:
            fallback = base.get(key) if base.get(key) in allowed else allowed[0]
            if key not in _warned:
                _warned.add(key)
                print(f"[설정 경고] {key}='{cfg[key]}' 는 지원하지 않는 값이라 '{fallback}' 로 실행합니다 (가능: {', '.join(allowed)})",
                      file=sys.stderr)
            cfg[key] = fallback
    return cfg


_SECRET_RX = None


def redact(text: str, env: dict | None = None) -> str:
    """로그·알림·오류 메시지에서 비밀값을 가린다. .env 의 값 + 흔한 키 모양(sk-…, AIza…, xoxb-…, 웹훅 주소)."""
    global _SECRET_RX
    import re
    if not text:
        return text
    env = load_env() if env is None else env
    for v in sorted({v for v in env.values() if len(v) >= 8}, key=len, reverse=True):
        text = text.replace(v, "***")
    if _SECRET_RX is None:
        _SECRET_RX = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{30,}|xox[abpr]-[0-9A-Za-z\-]{10,}|"
                                r"https://hooks\.slack\.com/services/[^\s\"']+|bot\d{6,}:[A-Za-z0-9_\-]{20,}|"
                                r"(?i:(?:api[_-]?key|token|key)=)[^\s&\"']{8,})")
    return _SECRET_RX.sub("***", text)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_utf8_stdout() -> None:
    """Windows 콘솔(cp949)에서 한글 출력이 깨지지 않게."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
