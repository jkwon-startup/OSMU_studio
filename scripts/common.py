"""공통 유틸 — 표준 라이브러리만 사용 (양 OS).

- ROOT: 저장소 루트
- load_env(): .env 를 읽어 dict 로 반환 (os.environ 에는 넣지 않는다 — 서브프로세스로 새지 않게)
- load_config(): config/config.local.json (없으면 config.example.json)
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


def load_config() -> dict:
    local = CONFIG_DIR / "config.local.json"
    example = CONFIG_DIR / "config.example.json"
    path = local if local.exists() else example
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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
