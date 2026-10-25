"""FFmpeg 공용 — 실행 파일 위치와 H.264 인코더 선택(libx264 가 없는 빌드에서도 동작하게)."""
from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

FF = shutil.which("ffmpeg")
FP = shutil.which("ffprobe")

# 품질 우선순위. libx264 가 없으면(일부 Windows·리눅스 배포판 빌드) OS 내장 하드웨어 인코더로.
_CANDIDATES = [
    ("libx264", ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]),
    ("libopenh264", ["-c:v", "libopenh264", "-b:v", "8M"]),
    ("h264_videotoolbox", ["-c:v", "h264_videotoolbox", "-b:v", "8M"]),
    ("h264_mf", ["-c:v", "h264_mf", "-b:v", "8M"]),
    ("h264_nvenc", ["-c:v", "h264_nvenc", "-b:v", "8M"]),
    ("mpeg4", ["-c:v", "mpeg4", "-q:v", "3"]),
]


@lru_cache(maxsize=1)
def encoder_args() -> tuple[str, ...]:
    if not FF:
        return tuple(_CANDIDATES[0][1])
    try:
        out = subprocess.run([FF, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30,
                             encoding="utf-8", errors="replace").stdout
    except (OSError, subprocess.TimeoutExpired):
        return tuple(_CANDIDATES[0][1])
    for name, args in _CANDIDATES:
        if f" {name} " in out:
            return tuple(args)
    return tuple(_CANDIDATES[0][1])


@lru_cache(maxsize=1)
def _filters() -> str:
    if not FF:
        return ""
    try:
        return subprocess.run([FF, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30,
                              encoding="utf-8", errors="replace").stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def has_filter(name: str) -> bool:
    return f" {name} " in _filters()
