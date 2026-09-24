"""Read-only Kiwoom REST quote feed that emits `run.py stream` input lines.

Only market data (ka10001) is requested. No order endpoint is referenced here.
Snapshot score fields are left at their neutral defaults: a single quote does
not measure TPE / hidden-flow features, so the fingerprint is plumbing only
until real feature extraction is added.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo
from typing import Any, Callable

REAL_HOST = "https://api.kiwoom.com"
MOCK_HOST = "https://mockapi.kiwoom.com"
QUOTE_API_ID = "ka10001"
QUOTE_PATH = "/api/dostk/stkinfo"
KST = timezone(timedelta(hours=9))

CHART_API_ID = "ka10080"
CHART_PATH = "/api/dostk/chart"
US_CHART_API_ID = "usa06011"
US_CHART_PATH = "/api/us/chart"
US_EASTERN = ZoneInfo("America/New_York")
MAX_THROTTLE_RETRIES = 5
THROTTLE_BACKOFF = 1.0  # seconds; Kiwoom allows ~5 requests/s per API

# (url, headers, body) -> (response body, response headers)
Http = Callable[[str, dict[str, str], dict[str, Any]], tuple[dict[str, Any], dict[str, str]]]


class KiwoomFeedError(RuntimeError):
    pass


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 10.0) -> tuple[dict[str, Any], dict[str, str]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json;charset=UTF-8", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}"), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw)
            raw = f"({detail.get('return_code')}) {detail.get('return_msg') or detail}"
        except (json.JSONDecodeError, AttributeError):
            pass
        raise KiwoomFeedError(f"kiwoom_feed.py: HTTP {exc.code} from {url}: {raw[:200]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise KiwoomFeedError(f"kiwoom_feed.py: network error for {url}: {exc}") from exc


def _check(res: dict[str, Any], what: str) -> dict[str, Any]:
    if str(res.get("return_code")) != "0":
        raise KiwoomFeedError(f"kiwoom_feed.py: {what} failed ({res.get('return_code')}): {res.get('return_msg')}")
    return res


def parse_price(raw: str) -> float:
    """Kiwoom prices carry a direction sign ("+70100", "-70100"); price is its magnitude."""
    text = str(raw or "").replace(",", "").strip()
    if not text:
        raise KiwoomFeedError("kiwoom_feed.py: empty cur_prc in quote response")
    return abs(float(text))


class KiwoomQuoteClient:
    def __init__(self, app_key: str, secret_key: str, paper: bool, http: Http = _post_json,
                 sleep: Callable[[float], None] = time.sleep):
        self.host = MOCK_HOST if paper else REAL_HOST
        self._app_key = app_key
        self._secret_key = secret_key
        self._http = http
        self._sleep = sleep
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
            })[0], "token")
            if not res.get("token"):
                raise KiwoomFeedError("kiwoom_feed.py: token response has no token")
            self._token = res["token"]
        return self._token

    def _call(self, api_id: str, path: str, body: dict[str, Any],
              extra: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
        """Authenticated call. Rate-limit replies (HTTP 429) back off and retry; any other failure
        drops the token and retries once (token-expiry recovery)."""
        token_retried, throttled = False, 0
        while True:
            headers = {"authorization": f"Bearer {self._ensure_token()}", "api-id": api_id, **(extra or {})}
            try:
                res, resp_headers = self._http(f"{self.host}{path}", headers, body)
                return _check(res, api_id), resp_headers
            except KiwoomFeedError as exc:
                if "HTTP 429" in str(exc) and throttled < MAX_THROTTLE_RETRIES:
                    throttled += 1
                    self._sleep(THROTTLE_BACKOFF * throttled)
                    continue
                if token_retried:
                    raise
                token_retried = True
                self._token = None

    def quote(self, code: str) -> dict[str, Any]:
        return self._call(QUOTE_API_ID, QUOTE_PATH, {"stk_cd": code})[0]

    def minute_bars(self, symbol: str, pages: int = 1, page_delay: float = 0.3,
                    sleep: Callable[[float], None] = time.sleep) -> list[dict[str, Any]]:
        """1-minute bars, oldest first. `005930` = KRX (ka10080, 900/page, KST);
        `ND:PLTR` = US exchange:ticker (usa06011, 100/page, US/Eastern)."""
        if ":" in symbol:
            exchange, ticker = symbol.split(":", 1)
            api_id, path, list_key, tz = US_CHART_API_ID, US_CHART_PATH, "result_list", US_EASTERN
            body = {"stex_tp": exchange, "stk_cd": ticker, "tic_scope": "1", "upd_stkpc_tp": "1"}
        else:
            api_id, path, list_key, tz = CHART_API_ID, CHART_PATH, "stk_min_pole_chart_qry", KST
            body = {"stk_cd": symbol, "tic_scope": "1", "upd_stkpc_tp": "1"}
        rows: list[dict[str, Any]] = []
        cont, next_key = "N", ""
        for page in range(pages):
            res, resp_headers = self._call(api_id, path, body, {"cont-yn": cont, "next-key": next_key})
            rows.extend(res.get(list_key) or [])
            cont, next_key = resp_headers.get("cont-yn", "N"), resp_headers.get("next-key", "")
            if cont != "Y" or not next_key:
                break
            if page + 1 < pages:
                sleep(page_delay)
        bars: dict[str, dict[str, Any]] = {}  # keyed by time: pages can overlap at edges
        bad: list[str] = []
        for r in rows:
            try:
                b = parse_bar(r, tz)
            except (ValueError, KeyError, KiwoomFeedError):
                bad.append(str(r.get("cntr_tm")))
                continue
            bars[b["time"]] = b
        if bad:
            print(f"kiwoom_feed.py: skipped {len(bad)} malformed {symbol} bars, e.g. cntr_tm={bad[:3]}", file=sys.stderr)
        return [bars[k] for k in sorted(bars)]


def parse_bar(raw: dict[str, Any], tz: tzinfo = KST) -> dict[str, Any]:
    digits = re.sub(r"\D", "", str(raw["cntr_tm"]))[:14]  # YYYYMMDDHHMMSS (+ occasional extra digits)
    if len(digits) != 14:
        raise ValueError(f"kiwoom_feed.py: bad cntr_tm {raw['cntr_tm']!r}")
    # Sessions past midnight are reported on the trading date with hours 24..47 (e.g. 27:44 = next day 03:44).
    hour = int(digits[8:10])
    base = datetime.strptime(digits[:8] + f"{hour % 24:02d}" + digits[10:], "%Y%m%d%H%M%S")
    stamp = (base + timedelta(days=hour // 24)).replace(tzinfo=tz)
    return {
        "time": stamp.isoformat(timespec="seconds"),
        "open": parse_price(raw.get("open_pric")),
        "high": parse_price(raw.get("high_pric")),
        "low": parse_price(raw.get("low_pric")),
        "close": parse_price(raw.get("cur_prc")),
        "volume": abs(float(str(raw.get("trde_qty") or "0").replace(",", ""))),
    }


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
