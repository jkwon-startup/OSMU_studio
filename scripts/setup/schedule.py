"""OS 스케줄러 등록 — macOS launchd / Windows 작업 스케줄러. 매시 정각 daily.py 를 깨운다.

  python3 scripts/osmu.py schedule install   [--label com.osmu-studio.daily]
  python3 scripts/osmu.py schedule uninstall [--label …]
  python3 scripts/osmu.py schedule status
  python3 scripts/osmu.py schedule run-now           # 등록된 잡을 즉시 1회 실행 (테스트)
  python3 scripts/osmu.py schedule render --out F    # 등록하지 않고 plist/xml 만 생성 (CI·점검용)
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IS_WINDOWS, ROOT  # noqa: E402

DEFAULT_LABEL = "com.osmu-studio.daily"
TASK_NAME = "OSMU Studio"
TPL_DIR = Path(__file__).resolve().parent


def _python() -> Path:
    venv = ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python")
    return venv if venv.exists() else Path(sys.executable)


def render_launchd(label: str) -> str:
    tpl = (TPL_DIR / "launchd.plist.template").read_text(encoding="utf-8")
    path_env = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    for extra in ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin")):
        if extra not in path_env.split(":"):
            path_env = f"{extra}:{path_env}"
    return (tpl.replace("{{LABEL}}", label).replace("{{PYTHON}}", str(_python())).replace("{{ROOT}}", str(ROOT))
            .replace("{{PATH}}", path_env).replace("{{HOME}}", str(Path.home())))


def render_task_xml() -> str:
    tpl = (TPL_DIR / "task.xml.template").read_text(encoding="utf-8")
    py = _python()
    pyw = py.with_name("pythonw.exe") if py.name.lower() == "python.exe" and py.with_name("pythonw.exe").exists() else py
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    return tpl.replace("{{START}}", start).replace("{{PYTHONW}}", str(pyw)).replace("{{ROOT}}", str(ROOT))


def _plist_path(label: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _uid() -> str:
    return str(os.getuid())


def install(label: str = DEFAULT_LABEL) -> str:
    (ROOT / "logs").mkdir(exist_ok=True)
    if IS_WINDOWS:
        xml = ROOT / "config" / "task.local.xml"
        xml.write_text(render_task_xml(), encoding="utf-16")
        p = subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml), "/F"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise RuntimeError(f"schtasks /Create 실패: {p.stderr or p.stdout}")
        return f"작업 스케줄러에 '{TASK_NAME}' 등록 ({xml})"
    plist = _plist_path(label)
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(render_launchd(label), encoding="utf-8")
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}", str(plist)], capture_output=True)  # 기존 것 있으면 내림
    p = subprocess.run(["launchctl", "bootstrap", f"gui/{_uid()}", str(plist)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"launchctl bootstrap 실패: {p.stderr or p.stdout}")
    return f"launchd 에 {label} 등록 ({plist})"


def uninstall(label: str = DEFAULT_LABEL) -> str:
    if IS_WINDOWS:
        p = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return "작업 삭제됨" if p.returncode == 0 else f"삭제 실패/없음: {(p.stderr or p.stdout).strip()}"
    plist = _plist_path(label)
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}", str(plist)], capture_output=True)
    if plist.exists():
        plist.unlink()
    return f"{label} 해제됨"


def status(label: str = DEFAULT_LABEL) -> str:
    if IS_WINDOWS:
        p = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.stdout.strip() if p.returncode == 0 else "등록되지 않음"
    p = subprocess.run(["launchctl", "print", f"gui/{_uid()}/{label}"], capture_output=True, text=True)
    if p.returncode != 0:
        return "등록되지 않음"
    keep = [ln.strip() for ln in p.stdout.splitlines() if any(k in ln for k in ("state", "last exit", "runs", "program"))]
    return "\n".join(keep[:8]) or "등록됨"


def run_now(label: str = DEFAULT_LABEL) -> str:
    if IS_WINDOWS:
        p = subprocess.run(["schtasks", "/Run", "/TN", TASK_NAME], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return (p.stdout or p.stderr).strip()
    p = subprocess.run(["launchctl", "kickstart", f"gui/{_uid()}/{label}"], capture_output=True, text=True)
    return "실행 요청됨" if p.returncode == 0 else (p.stderr or p.stdout).strip()
