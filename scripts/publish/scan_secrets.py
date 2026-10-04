#!/usr/bin/env python3
"""커밋 전 비밀값·개인 경로 검사.

사용:
  python3 scripts/publish/scan_secrets.py            # git에 추적되는 파일 전체
  python3 scripts/publish/scan_secrets.py --staged   # 스테이징된 파일만 (pre-commit)
  python3 scripts/publish/scan_secrets.py --files a b

걸리면 종료 코드 1. 값 자체는 출력하지 않고 파일·줄·패턴 이름만 보여준다.
개인 패턴은 config/private-patterns.local.txt (git 제외) 에 한 줄씩 정규식으로 추가한다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATTERNS: list[tuple[str, str]] = [
    ("macOS 개인 경로", r"/Users/(?!<|\{|\$|USER|you|username|your)[A-Za-z0-9._-]+"),
    ("Windows 개인 경로", r"C:\\Users\\(?!<|\{|%|USER|you|username|your)[A-Za-z0-9._-]+"),
    ("Slack 웹훅", r"hooks\.slack\.com/services/"),
    ("Slack 토큰", r"xox[abp]-[A-Za-z0-9-]{10,}"),
    ("OpenAI/일반 sk- 키", r"\bsk-[A-Za-z0-9_-]{20,}"),
    ("ElevenLabs 형태 키", r"\bsk_[a-f0-9]{40,}"),
    ("Google API 키", r"\bAIza[0-9A-Za-z_-]{35}"),
    ("텔레그램 봇 토큰", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("AWS 키", r"\bAKIA[0-9A-Z]{16}\b"),
    ("개인키 블록", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("구글시트 ID", r"docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]{20,}"),
    ("이메일 주소", r"\b[A-Za-z0-9._%+-]+@(gmail|naver|daum|kakao|hanmail|outlook|icloud)\.(com|net)\b"),
]

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mp3", ".wav", ".ttf", ".otf", ".woff", ".woff2", ".zip", ".gz"}
SKIP_PARTS = {"node_modules", ".venv", "output", "_workspace", "__pycache__"}


def git_files(staged: bool) -> list[Path]:
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged else ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if line.strip()]


def load_private_patterns() -> list[tuple[str, str]]:
    extra = ROOT / "config" / "private-patterns.local.txt"
    if not extra.exists():
        return []
    pats = []
    for i, line in enumerate(extra.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append((f"개인 패턴 #{i}", line))
    return pats


def scan(files: list[Path]) -> list[tuple[Path, int, str]]:
    compiled = [(name, re.compile(p)) for name, p in PATTERNS + load_private_patterns()]
    hits: list[tuple[Path, int, str]] = []
    for f in files:
        if not f.is_file() or f.suffix.lower() in SKIP_SUFFIXES or SKIP_PARTS & set(f.parts):
            continue
        if f.name == "scan_secrets.py":  # 패턴 정의 자체는 제외
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "scan-secrets:ignore" in line:  # 테스트용 가짜 값 등, 줄 단위 예외
                continue
            for name, rx in compiled:
                if rx.search(line):
                    hits.append((f, lineno, name))
    return hits


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔(cp1252/cp949)에서 한글 출력 깨짐 방지
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--files", nargs="*")
    args = ap.parse_args()
    files = [Path(f).resolve() for f in args.files] if args.files else git_files(args.staged)
    hits = scan(files)
    if not hits:
        print(f"scan_secrets: OK ({len(files)}개 파일 검사)")
        return 0
    print("scan_secrets: 커밋 차단 — 아래 항목을 제거하거나 .env/로컬 파일로 옮기세요")
    for f, lineno, name in hits:
        print(f"  {f.relative_to(ROOT)}:{lineno}  [{name}]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
