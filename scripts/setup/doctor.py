"""도구 점검 (doctor) — 설치자 PC에 필요한 외부 도구가 있는지 OS별로 확인한다. LLM·네트워크 호출 없음."""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IS_WINDOWS, ROOT, load_env  # noqa: E402

REQUIRED_FILTERS = ["zoompan", "loudnorm", "overlay", "concat", "freezedetect", "ebur128"]
REQUIRED_ENCODERS = ["libx264", "aac"]


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout + p.stderr)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""


def _which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def check_all() -> list[dict]:
    """각 항목: {name, ok, detail, required, hint}"""
    rows: list[dict] = []

    def add(name, ok, detail="", required=True, hint=""):
        rows.append({"name": name, "ok": bool(ok), "detail": detail, "required": required, "hint": hint})

    add("OS", True, f"{platform.system()} {platform.release()} ({platform.machine()})")

    v = sys.version_info
    add("Python ≥ 3.10", v >= (3, 10), f"{v.major}.{v.minor}.{v.micro} — {sys.executable}",
        hint="https://www.python.org/downloads/ (Windows: 설치 시 'Add to PATH' 체크)")

    claude = _which("claude", "claude.exe", "claude.cmd")
    code, out = _run([claude, "--version"]) if claude else (127, "")
    add("Claude Code", claude is not None and code == 0, (out.strip().splitlines() or [claude or ""])[0],
        hint="https://code.claude.com/docs/en/setup")
    if claude and claude.lower().endswith(".cmd"):
        add("Claude Code 실행 파일 형식", False, "npm .cmd 래퍼 — 예약 작업에서 불안정할 수 있음", required=False,
            hint="네이티브 설치(claude.exe) 권장")

    ff = _which("ffmpeg")
    code, out = _run([ff, "-version"]) if ff else (127, "")
    add("FFmpeg", ff is not None and code == 0, (out.splitlines() or [""])[0][:60],
        hint="macOS: brew install ffmpeg / Windows: winget install Gyan.FFmpeg")
    if ff:
        _, filters = _run([ff, "-hide_banner", "-filters"])
        missing = [f for f in REQUIRED_FILTERS if f" {f} " not in filters]
        add("FFmpeg 필터", not missing, "모두 있음" if not missing else f"없음: {', '.join(missing)}")
        _, encoders = _run([ff, "-hide_banner", "-encoders"])
        missing_enc = [e for e in REQUIRED_ENCODERS if f" {e} " not in encoders]
        add("FFmpeg 인코더", not missing_enc, "libx264, aac 있음" if not missing_enc else f"없음: {', '.join(missing_enc)}")
    add("ffprobe", _which("ffprobe") is not None, hint="FFmpeg와 함께 설치됨")

    node = _which("node")
    code, out = _run([node, "--version"]) if node else (127, "")
    add("Node.js (모션그래픽용)", node is not None and code == 0, out.strip(), required=False,
        hint="없으면 모션그래픽 주제는 실사로 대체. macOS: brew install node / Windows: winget install OpenJS.NodeJS.LTS")

    if IS_WINDOWS:
        bash = _which("bash")
        add("Git Bash", bash is not None, bash or "", hint="winget install Git.Git (Claude Code의 Bash 도구와 윤문 스크립트에 필요)")
    add("git", _which("git") is not None, hint="https://git-scm.com/")

    try:
        import PIL  # noqa: F401
        add("Pillow (이미지 합성)", True, PIL.__version__)
    except ImportError:
        add("Pillow (이미지 합성)", False, "미설치", hint="pip install -r requirements.txt (.venv 안에서)")
    try:
        import openpyxl  # noqa: F401
        add("openpyxl (xlsx 주제 소스)", True, openpyxl.__version__, required=False)
    except ImportError:
        add("openpyxl (xlsx 주제 소스)", False, "미설치", required=False, hint="xlsx 를 쓸 때만 필요")

    code, out = _run([claude, "plugin", "list"]) if claude else (127, "")
    has_humanize = "humanize-korean" in out
    add("humanize-korean 플러그인 (윤문)", has_humanize, "설치됨" if has_humanize else "미설치 — 윤문 단계 건너뜀", required=False,
        hint="/plugin marketplace add epoko77-ai/im-not-ai → /plugin install humanize-korean@im-not-ai")

    pix = _which("pixverse", "pixverse.cmd")
    add("Pixverse CLI (이미지 서비스 선택 시)", pix is not None, pix or "미설치", required=False,
        hint="npm install -g pixverse 후 pixverse auth login")

    env = load_env()
    for key, label in [("GEMINI_API_KEY", "Gemini"), ("ELEVENLABS_API_KEY", "ElevenLabs"),
                       ("SLACK_WEBHOOK_URL", "Slack 웹훅"), ("TELEGRAM_BOT_TOKEN", "텔레그램 봇"), ("YOUTUBE_API_KEY", "YouTube Data API")]:
        add(f".env {key} ({label})", bool(env.get(key)), "있음" if env.get(key) else "없음", required=False)

    add("폰트 (assets/fonts)", any((ROOT / "assets" / "fonts").glob("*.?tf")) if (ROOT / "assets" / "fonts").exists() else False,
        required=False, hint="저장소에 동봉 예정 (OFL 한글 폰트)")
    return rows


def print_report(rows: list[dict]) -> bool:
    ok_all = True
    for r in rows:
        mark = "OK " if r["ok"] else ("--" if not r["required"] else "FAIL")
        if not r["ok"] and r["required"]:
            ok_all = False
        line = f"[{mark:4}] {r['name']}"
        if r["detail"]:
            line += f": {r['detail']}"
        print(line)
        if not r["ok"] and r["hint"]:
            print(f"        → {r['hint']}")
    print("\ndoctor:", "필수 항목 모두 통과" if ok_all else "필수 항목 미충족 — 위 안내대로 설치 후 다시 실행")
    return ok_all


if __name__ == "__main__":
    sys.exit(0 if print_report(check_all()) else 1)
