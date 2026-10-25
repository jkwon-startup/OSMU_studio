"""완료 알림 — Slack 웹훅 또는 텔레그램 봇. 표준 라이브러리만 사용.

텔레그램은 parse_mode 를 쓰지 않는다(평문). `&`·`<` 가 든 제목이 HTML 모드에서 400 으로 조용히 사라지는 사고 방지.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from common import redact

TIMEOUT = 15


def send_slack(webhook_url: str, text: str) -> tuple[bool, str]:
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status == 200, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"연결 실패: {type(e).__name__}"


def send_telegram(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(url, data=body)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status == 200, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"연결 실패: {type(e).__name__}"


def send(channel: str, env: dict[str, str], text: str) -> tuple[bool, str]:
    """channel: 'slack' | 'telegram'. 키는 env dict 에서 읽는다 (값은 로그에 남기지 않는다)."""
    text = redact(text, env)  # 오류 메시지에 섞인 키가 알림으로 나가지 않게
    if channel == "slack":
        url = env.get("SLACK_WEBHOOK_URL", "")
        if not url:
            return False, "SLACK_WEBHOOK_URL 없음"
        return send_slack(url, text)
    if channel == "telegram":
        token, chat = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat:
            return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 없음"
        return send_telegram(token, chat, text)
    return False, f"알 수 없는 채널: {channel}"
