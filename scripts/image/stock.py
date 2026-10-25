"""무료 스톡 사진·영상 — Pexels(우선) → Pixabay. 둘 다 가입만 하면 무료 키가 나온다.

  PEXELS_API_KEY  : https://www.pexels.com/api/  (여러 개면 쉼표로 구분 — 한도에 걸리면 다음 키)
  PIXABAY_API_KEY : https://pixabay.com/api/docs/

- 검색어는 영어 키워드가 잘 맞는다. 항목에 "query" 가 없으면 영어 프롬프트에서 키워드를 뽑는다.
- 같은 실행에서 같은 사진을 두 번 쓰지 않도록 출처 기록(credits.json)을 함께 본다.
- 두 서비스 모두 상업적 사용 무료·출처 표기 의무 없음(권장). 출처는 credits.json 에 남긴다.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (OSMU Studio)"}
STOP = {"a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to", "by", "for", "from", "is", "are", "no", "not",
        "photo", "photorealistic", "realistic", "image", "shot", "scene", "style", "light", "lighting", "soft", "warm", "cinematic",
        "depth", "field", "shallow", "lens", "mm", "camera", "close", "up", "wide", "medium", "detail", "mood", "atmosphere",
        "text", "letters", "numbers", "logos", "logo", "watermark", "ui", "korean", "korea", "person", "people", "their", "its",
        "his", "her", "while", "into", "over", "under", "near", "behind", "front", "background", "foreground", "subtle", "natural"}


def keys(env: dict, name: str) -> list[str]:
    return [k.strip() for k in (env.get(name) or "").split(",") if k.strip()]


def available(env: dict) -> bool:
    return bool(keys(env, "PEXELS_API_KEY") or keys(env, "PIXABAY_API_KEY"))


def query_from_prompt(prompt: str, n: int = 4) -> str:
    """영어 프롬프트 → 검색 키워드 몇 개. 'No text…' 꼬리와 촬영 용어는 버린다."""
    head = re.split(r"\bno text\b", prompt, flags=re.I)[0]
    words = re.findall(r"[A-Za-z]+", head.lower())
    picked: list[str] = []
    for w in words:
        if len(w) > 2 and w not in STOP and w not in picked:
            picked.append(w)
        if len(picked) >= n:
            break
    return " ".join(picked) or "workspace"


def orientation(ratio: str) -> str:
    try:
        w, h = (float(x) for x in ratio.split(":"))
    except ValueError:
        return "landscape"
    return "landscape" if w > h else ("portrait" if h > w else "square")


def _get(url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        out.write_bytes(r.read())


# ---------- 검색: 후보 목록 [{id, url, author, page, source}] ----------
def _pexels(kind: str, query: str, orient: str, key: str) -> list[dict]:
    q = urllib.parse.quote(query)
    if kind == "photo":
        data = _get(f"https://api.pexels.com/v1/search?query={q}&orientation={orient}&per_page=15", {"Authorization": key})
        return [{"id": f"pexels:{p['id']}", "url": p["src"]["original"] + "?auto=compress&cs=tinysrgb&w=2400",
                 "author": p.get("photographer", ""), "page": p.get("url", ""), "source": "Pexels"} for p in data.get("photos", [])]
    data = _get(f"https://api.pexels.com/videos/search?query={q}&orientation={orient}&per_page=15", {"Authorization": key})
    out = []
    for v in data.get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("link") and f.get("width") and f.get("height")]
        files.sort(key=lambda f: f["width"] * f["height"])
        # 1080p 근처 중 가장 작은 것(다운로드 시간 절약). 없으면 가장 큰 것.
        good = [f for f in files if min(f["width"], f["height"]) >= 1080] or files[-1:]
        if good:
            out.append({"id": f"pexels-v:{v['id']}", "url": good[0]["link"], "author": (v.get("user") or {}).get("name", ""),
                        "page": v.get("url", ""), "source": "Pexels", "duration": v.get("duration")})
    return out


def _pixabay(kind: str, query: str, orient: str, key: str) -> list[dict]:
    q = urllib.parse.quote(query)
    o = {"landscape": "horizontal", "portrait": "vertical"}.get(orient, "all")
    if kind == "photo":
        data = _get(f"https://pixabay.com/api/?key={key}&q={q}&image_type=photo&orientation={o}&safesearch=true&per_page=15")
        return [{"id": f"pixabay:{h['id']}", "url": h["largeImageURL"], "author": h.get("user", ""), "page": h.get("pageURL", ""),
                 "source": "Pixabay"} for h in data.get("hits", [])]
    data = _get(f"https://pixabay.com/api/videos/?key={key}&q={q}&safesearch=true&per_page=15")
    out = []
    for h in data.get("hits", []):
        vids = [v for v in (h.get("videos") or {}).values() if v.get("url")]
        vids.sort(key=lambda v: v.get("width", 0) * v.get("height", 0))
        good = [v for v in vids if min(v.get("width", 0), v.get("height", 0)) >= 1080] or vids[-1:]
        if good:
            out.append({"id": f"pixabay-v:{h['id']}", "url": good[0]["url"], "author": h.get("user", ""), "page": h.get("pageURL", ""),
                        "source": "Pixabay", "duration": h.get("duration"), "_portrait": good[0].get("height", 0) > good[0].get("width", 0)})
    if orient == "portrait":  # Pixabay 영상 검색엔 방향 필터가 없다 — 세로 영상을 앞으로 (가로는 중앙 크롭됨)
        out.sort(key=lambda c: not c.get("_portrait"))
    return out


def search(kind: str, query: str, ratio: str, env: dict) -> tuple[list[dict], str]:
    """(후보, 오류 설명). 키가 여러 개면 한도(429)·권한 오류 때 다음 키로."""
    orient = orientation(ratio)
    errors = []
    for name, fn in (("PEXELS_API_KEY", _pexels), ("PIXABAY_API_KEY", _pixabay)):
        for key in keys(env, name):
            try:
                found = fn(kind, query, orient, key)
                if found:
                    return found, ""
                errors.append(f"{name.split('_')[0].title()}: '{query}' 결과 없음")
                break  # 결과 없음은 키 문제가 아니다 — 다음 서비스로
            except urllib.error.HTTPError as e:
                errors.append(f"{name.split('_')[0].title()} HTTP {e.code}" + (" (키 확인)" if e.code in (401, 403) else " (한도)" if e.code == 429 else ""))
                if e.code == 429:
                    time.sleep(2)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                errors.append(f"{name.split('_')[0].title()} 연결 실패 {type(e).__name__}")
                break
    if not available(env):
        return [], "스톡 키가 없습니다 — https://www.pexels.com/api/ 에서 무료 키를 받아 .env 에 PEXELS_API_KEY=… 로 넣으세요"
    return [], " / ".join(errors)


def _load_credits(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def fetch(kind: str, query: str, ratio: str, out: Path, env: dict, credits_path: Path, raw_out: Path | None = None) -> tuple[bool, str]:
    """검색 → 아직 안 쓴 첫 후보 다운로드 → credits 기록. 사진은 raw_out 에 받은 뒤 호출자가 크롭한다."""
    cands, err = search(kind, query, ratio, env)
    if not cands and " " in query.strip():
        # 키워드가 너무 구체적이면 앞의 두 단어로 한 번 더
        cands, err = search(kind, " ".join(query.split()[:2]), ratio, env)
    if not cands:
        return False, err
    credits = _load_credits(credits_path)
    used = {c.get("id") for c in credits}
    pick = next((c for c in cands if c["id"] not in used), cands[0])
    try:
        _download(pick["url"], raw_out or out)
    except Exception as e:
        return False, f"다운로드 실패 {type(e).__name__}"
    credits = [c for c in credits if c.get("file") != out.name]
    credits.append({"file": out.name, "id": pick["id"], "source": pick["source"], "author": pick["author"], "page": pick["page"], "query": query})
    credits_path.parent.mkdir(parents=True, exist_ok=True)
    credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"{pick['source']} · {pick['author']}"
