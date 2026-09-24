"""Read-only Kiwoom REST quote feed that emits `run.py stream` input lines.

Only market data (ka10001) is requested. No order endpoint is referenced here.
Snapshot score fields are left at their neutral defaults: a single quote does
not measure TPE / hidden-flow features, so the fingerprint is plumbing only
until real feature extraction is added.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

REAL_HOST = "https://api.kiwoom.com"
MOCK_HOST = "https://mockapi.kiwoom.com"
QUOTE_API_ID = "ka10001"
QUOTE_PATH = "/api/dostk/stkinfo"
KST = timezone(timedelta(hours=9))

Http = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


class KiwoomFeedError(RuntimeError):
    pass


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json;charset=UTF-8", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise KiwoomFeedError(f"kiwoom_feed.py: HTTP {exc.code} from {url}: {raw[:200]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise KiwoomFeedError(f"kiwoom_feed.py: network error for {url}: {exc}") from exc


def _check(res: dict[str, Any], what: str) -> dict[str, Any]:
    if str(res.get("return_code", "0")) != "0":
        raise KiwoomFeedError(f"kiwoom_feed.py: {what} failed ({res.get('return_code')}): {res.get('return_msg')}")
    return res


def parse_price(raw: str) -> float:
    """Kiwoom prices carry a direction sign ("+70100", "-70100"); price is its magnitude."""
    text = str(raw or "").replace(",", "").strip()
    if not text:
        raise KiwoomFeedError("kiwoom_feed.py: empty cur_prc in quote response")
    return abs(float(text))


class KiwoomQuoteClient:
    def __init__(self, app_key: str, secret_key: str, paper: bool, http: Http = _post_json):
        self.host = MOCK_HOST if paper else REAL_HOST
        self._app_key = app_key
        self._secret_key = secret_key
        self._http = http
        self._token: str | None = None

    @classmethod
    def from_env(cls) -> "KiwoomQuoteClient":
        app_key = os.getenv("KIWOOM_APP_KEY", "").strip()
        secret_key = os.getenv("KIWOOM_SECRET_KEY", "").strip()
        if not app_key or not secret_key:
            raise KiwoomFeedError("kiwoom_feed.py: KIWOOM_APP_KEY / KIWOOM_SECRET_KEY missing in .env")
        paper = os.getenv("KIWOOM_PAPER", "true").strip().lower() != "false"
        return cls(app_key, secret_key, paper)

    def _ensure_token(self) -> str:
        if self._token is None:
            res = _check(self._http(f"{self.host}/oauth2/token", {}, {
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._secret_key,
            }), "token")
            if not res.get("token"):
                raise KiwoomFeedError("kiwoom_feed.py: token response has no token")
            self._token = res["token"]
        return self._token

    def quote(self, code: str) -> dict[str, Any]:
        headers = {"authorization": f"Bearer {self._ensure_token()}", "api-id": QUOTE_API_ID}
        return _check(self._http(f"{self.host}{QUOTE_PATH}", headers, {"stk_cd": code}), QUOTE_API_ID)


def quote_to_line(code: str, quote: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    stamp = (now or datetime.now(KST)).isoformat(timespec="seconds")
    return {
        "price": parse_price(quote.get("cur_prc", "")),
        "snapshot": {
            "symbol": code,
            "timestamp": stamp,
            "metadata": {
                "source": f"kiwoom:{QUOTE_API_ID}",
                "name": quote.get("stk_nm"),
                "change_rate": quote.get("flu_rt"),
                "volume": quote.get("trde_qty"),
                "features": "neutral defaults (not measured)",
            },
        },
    }


def run_feed(client: KiwoomQuoteClient, codes: list[str], interval: float, count: int,
             emit: Callable[[str], None] = print, sleep: Callable[[float], None] = time.sleep) -> None:
    """Poll each code `count` times (0 = forever) and emit one JSON line per quote."""
    done = 0
    while count == 0 or done < count:
        for code in codes:
            line = quote_to_line(code, client.quote(code))
            emit(json.dumps(line, ensure_ascii=False, separators=(",", ":")))
        done += 1
        if count == 0 or done < count:
            sleep(interval)
