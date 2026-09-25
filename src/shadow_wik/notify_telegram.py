"""Telegram alert when a symbol enters a statistically significant zone.

The bot token is not copied into this repo: TELEGRAM_TOKEN_FILE points to an
existing env file (the mathking project's) and only TELEGRAM_BOT_TOKEN is read
from it. TELEGRAM_CHAT_ID is the recipient. Missing config disables alerts.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .envfile import read_env_key

TOKEN_KEY = "TELEGRAM_BOT_TOKEN"
MAX_TEXT = 3500


class TelegramError(RuntimeError):
    pass


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 10.0) -> None:
        self._token = token
        self.chat_id = chat_id
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "TelegramNotifier | None":
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        token = os.getenv(TOKEN_KEY, "").strip()
        token_file = os.getenv("TELEGRAM_TOKEN_FILE", "").strip()
        if not token and token_file:
            try:
                token = read_env_key(token_file, TOKEN_KEY)
            except ValueError as exc:
                raise TelegramError(f"notify_telegram.py: TELEGRAM_TOKEN_FILE: {exc}") from None
        if not token or not chat_id:
            return None
        return cls(token, chat_id)

    def send(self, text: str) -> dict[str, Any]:
        data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text[:MAX_TEXT]}).encode("utf-8")
        req = urllib.request.Request(f"https://api.telegram.org/bot{self._token}/sendMessage", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # the URL embeds the token: report only Telegram's description, never the URL
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("description", detail)
            except json.JSONDecodeError:
                pass
            raise TelegramError(f"notify_telegram.py: HTTP {exc.code}: {str(detail)[:200]}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise TelegramError(f"notify_telegram.py: network error: {getattr(exc, 'reason', exc)}") from None


def zone_entry_message(symbol: str, entry: dict[str, Any], report: dict[str, Any]) -> str:
    stats = {z["name"]: z for z in report["zones"]}
    lines = [f"[shadow_wik] {symbol} 통계적 유의 구간 진입", f"{entry['timestamp']}  가격 {entry['price']:g}"]
    for name in entry["zone"]["zones"][:3]:
        z = stats.get(name, {})
        lines.append(f"- {name.replace('zone:', '')}: 검증 n={z.get('holdout_n')} 평균 {z.get('holdout_mean_pct', 0):.3f}% p={z.get('holdout_p', 1):.3g}")
    if entry["opened"]:
        lines.append("가상 롱 진입 기록됨 (실주문 아님)")
    lines.append("실제 주문은 직접 판단하세요. 과거 통계이며 수익을 보장하지 않습니다.")
    return "\n".join(lines)
