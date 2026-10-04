"""claude 실행 파일 탐색과 헤드리스 호출 — 양 OS 공통.

원칙
- argv 는 ASCII 만. 한글 프롬프트는 stdin 으로 UTF-8 전달한다 (Windows 콘솔 인코딩 문제 회피).
- 서브프로세스 환경에 .env 의 비밀값을 넣지 않는다.
- 실행 파일 경로는 설치 때 확정해 config 에 저장하고, 없으면 PATH 와 기본 설치 위치를 찾는다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IS_WINDOWS, ROOT  # noqa: E402


def find_claude(configured: str | None = None) -> str | None:
    if configured and Path(configured).expanduser().exists():
        return str(Path(configured).expanduser())
    home = Path.home()
    # 고정 설치 위치를 먼저 본다 — 터미널 앱이 PATH 앞에 끼워 넣는 임시 shim(예: */T/*/cli-shims/*)은 예약 실행 때 없다.
    candidates = [home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude",
                  Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude"),
                  home / "AppData" / "Roaming" / "npm" / "claude.cmd"]
    for c in candidates:
        if c.exists():
            return str(c)
    for name in ("claude", "claude.exe", "claude.cmd"):
        p = shutil.which(name)
        if p and "shim" not in p.lower():
            return p
    return None


@dataclass
class ClaudeCall:
    """한 번의 `claude -p` 호출 사양."""
    prompt: str                                  # stdin 으로 전달
    cwd: Path = ROOT
    agent: str | None = None                     # --agent
    settings: Path | None = None                 # --settings 파일
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    permission_mode: str = "dontAsk"
    max_budget_usd: float | None = None
    output_json: bool = True
    strict_mcp: bool = True
    extra: list[str] = field(default_factory=list)

    def argv(self, claude_path: str) -> list[str]:
        a = [claude_path, "-p"]
        if self.agent:
            a += ["--agent", self.agent]
        if self.settings:
            a += ["--settings", str(self.settings)]
        if self.allowed_tools:
            a += ["--allowedTools", ",".join(self.allowed_tools), "--tools", ",".join(self.allowed_tools)]
        if self.disallowed_tools:
            a += ["--disallowedTools", ",".join(self.disallowed_tools)]
        if self.permission_mode:
            a += ["--permission-mode", self.permission_mode]
        # --max-turns 는 2.1.288 --help 에 없어 쓰지 않는다. 상한은 --max-budget-usd 와 subprocess timeout 으로 건다.
        if self.max_budget_usd:
            a += ["--max-budget-usd", str(self.max_budget_usd)]
        if self.output_json:
            a += ["--output-format", "json"]
        if self.strict_mcp:
            a += ["--strict-mcp-config"]
        a += self.extra
        bad = [x for x in a if not x.isascii()]
        if bad:
            raise ValueError(f"argv 에 ASCII 가 아닌 인자가 있음: {bad[:3]} — 프롬프트는 stdin 으로 넘길 것")
        return a


@dataclass
class ClaudeResult:
    returncode: int
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def json(self) -> dict | None:
        import json
        try:
            return json.loads(self.stdout)
        except (json.JSONDecodeError, TypeError):
            return None


def _clean_env() -> dict[str, str]:
    """비밀값이 새지 않도록 최소 환경만 넘긴다."""
    keep = ("PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
            "SYSTEMROOT", "COMSPEC", "PATHEXT", "SHELL", "USER", "USERNAME", "TERM", "XDG_CONFIG_HOME",
            "CLAUDE_CONFIG_DIR", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")  # 인증은 claude 가 자기 설정에서 읽음
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_claude(call: ClaudeCall, claude_path: str, timeout_s: int = 1800, log_path: Path | None = None) -> ClaudeResult:
    argv = call.argv(claude_path)
    t0 = time.time()
    try:
        p = subprocess.run(argv, input=call.prompt, cwd=str(call.cwd), env=_clean_env(), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout_s,
                           shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0)
        res = ClaudeResult(p.returncode, p.stdout, p.stderr, time.time() - t0)
    except subprocess.TimeoutExpired as e:
        res = ClaudeResult(124, (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                           (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or ""),
                           time.time() - t0, timed_out=True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"$ {' '.join(argv)}\n[exit {res.returncode}, {res.seconds:.0f}s, timeout={res.timed_out}]\n"
                            f"--- stdout ---\n{res.stdout}\n--- stderr ---\n{res.stderr}\n", encoding="utf-8")
    return res
