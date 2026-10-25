"""도구 점검 (doctor) — 설치자 PC에 필요한 외부 도구가 있는지 OS별로 확인한다. LLM 호출 없음(업데이트 확인만 git 으로 짧게)."""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IS_WINDOWS, ROOT, load_config, load_env  # noqa: E402

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
        import edge_tts  # noqa: F401
        add("edge-tts (무료 음성)", True, getattr(edge_tts, "__version__", "설치됨"))
    except ImportError:
        add("edge-tts (무료 음성)", False, "미설치 — 숏츠가 무음(자막만)으로 만들어짐", required=False,
            hint="pip install -r requirements.txt (.venv 안에서)")
    pw_ok, pw_detail, pw_hint = _playwright_status()
    add("Playwright + Chromium (모션그래픽 HTML 템플릿)", pw_ok, pw_detail, required=False, hint=pw_hint)
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
    if not (ROOT / ".env").exists():
        add(".env 파일", False, "없음", required=False, hint=".env.example 을 복사해 .env 로 이름을 바꾸고 필요한 키만 넣으세요")
    for key, label in [("PEXELS_API_KEY", "Pexels 무료 스톡"), ("PIXABAY_API_KEY", "Pixabay 무료 스톡"),
                       ("GEMINI_API_KEY", "Gemini"), ("ELEVENLABS_API_KEY", "ElevenLabs"),
                       ("SLACK_WEBHOOK_URL", "Slack 웹훅"), ("TELEGRAM_BOT_TOKEN", "텔레그램 봇"), ("YOUTUBE_API_KEY", "YouTube Data API")]:
        add(f".env {key} ({label})", bool(env.get(key)), "있음" if env.get(key) else "없음", required=False)
    cfg = load_config()
    if cfg.get("image_provider") == "stock" and not (env.get("PEXELS_API_KEY") or env.get("PIXABAY_API_KEY")):
        add("이미지 서비스 준비", False, "image_provider=stock 인데 스톡 키가 없음 — 블로그 이미지가 비고 숏츠는 글자 카드로 대체됨",
            required=False, hint="https://www.pexels.com/api/ 에서 무료 키(1분) → .env 에 PEXELS_API_KEY=… 추가")

    add("폰트 (assets/fonts)", any((ROOT / "assets" / "fonts").glob("*.?tf")) if (ROOT / "assets" / "fonts").exists() else False,
        hint="저장소의 assets/fonts 가 비었습니다 — git pull 또는 저장소를 다시 받으세요")
    bgm = sorted(p.name for p in (ROOT / "assets" / "bgm").glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")) \
        if (ROOT / "assets" / "bgm").exists() else []
    add("배경음악 (assets/bgm)", bool(bgm), f"{len(bgm)}곡" if bgm else "없음 — 배경음악 없이 만들어짐", required=False,
        hint="저작권 걱정 없는 음악(직접 만든 곡, YouTube 오디오 보관함 등)을 assets/bgm/ 에 mp3 로 넣으면 자동 사용")
    upd = _update_status()
    if upd:
        add("새 버전", False, upd, required=False, hint="저장소 폴더에서 git pull 후 pip install -r requirements.txt")
    return rows


def _playwright_status() -> tuple[bool, str, str]:
    hint = "pip install -r requirements.txt 후 python -m playwright install chromium (없으면 정적 카드로 대체)"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "미설치", hint
    try:
        with sync_playwright() as p:
            exe = Path(p.chromium.executable_path)
        return (exe.exists(), "Chromium 있음" if exe.exists() else "Chromium 미설치", hint)
    except Exception as e:  # 드라이버 문제 등
        return False, f"확인 실패 {type(e).__name__}", hint


def _update_status() -> str | None:
    """원격 main 과 비교해 새 커밋이 있으면 안내(2초 안에 안 되면 조용히 넘어감)."""
    git = _which("git")
    if not git or not (ROOT / ".git").exists():
        return None
    try:
        local = subprocess.run([git, "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
        remote = subprocess.run([git, "-C", str(ROOT), "ls-remote", "origin", "refs/heads/main"], capture_output=True, text=True,
                                timeout=4).stdout.split()
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not remote or not local or remote[0] == local:
        return None
    known = subprocess.run([git, "-C", str(ROOT), "cat-file", "-e", remote[0]], capture_output=True).returncode == 0
    return None if known else "저장소에 새 업데이트가 있습니다"


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
