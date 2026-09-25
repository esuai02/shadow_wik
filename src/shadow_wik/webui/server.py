"""Local paper-trading server: polls Kiwoom minute bars and serves the UI on 127.0.0.1 only."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..kiwoom_feed import KiwoomQuoteClient
from ..notify_telegram import TelegramError, TelegramNotifier, zone_entry_message
from ..paper_portfolio import PaperPortfolio
from ..trader import LiveTrader
from . import api_decision, api_settings, api_state, api_zones

STATIC = Path(__file__).resolve().parent / "static"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
MAX_BODY = 4096
GET_ROUTES = {"/api/state": api_state.handle, "/api/zones": api_zones.handle}
POST_ROUTES = {"/api/decision": api_decision.handle, "/api/settings": api_settings.handle}


class Runtime:
    def __init__(self, client: KiwoomQuoteClient, reports: dict[str, dict[str, Any]], state_dir: Path,
                 interval: float, jev: Any = None, notifier: TelegramNotifier | None = None,
                 paper_mode: str = "statistical_zone") -> None:
        self.client = client
        self.reports = reports
        self.interval = interval
        self.decisions_path = state_dir / "decisions.jsonl"
        self.settings_path = state_dir / "ui_settings.json"
        self.validation_level = self._load_validation_level()
        self.portfolio = PaperPortfolio(
            seed_krw=100_000_000.0,
            per_trade_fraction=0.10,
            max_positions=10,
            event_path=state_dir / "paper_portfolio.jsonl",
        )
        self.traders = {
            code: LiveTrader(
                code,
                report,
                state_dir / f"live_paper_{code}.jsonl",
                jev=jev,
                portfolio=self.portfolio,
                validation_level=self.validation_level,
                paper_mode=paper_mode,
                jev_log_path=state_dir / "jev_decisions.sqlite",
            )
            for code, report in reports.items()
        }
        self.errors: dict[str, str | None] = {code: None for code in reports}
        self.last_poll: str | None = None
        self.jev_enabled = jev is not None
        self.notifier = notifier
        self.alerts_path = state_dir / "alerts.jsonl"
        self._stop = threading.Event()

    def _load_validation_level(self) -> int:
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return max(0, min(100, int(data.get("validation_level", 0))))
        except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def set_validation_level(self, level: int) -> int:
        value = max(0, min(100, int(level)))
        self.validation_level = value
        for trader in self.traders.values():
            trader.set_validation_level(value)
        self.settings_path.write_text(
            json.dumps({"validation_level": value}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return value

    def poll_once(self) -> None:
        for code, trader in self.traders.items():
            try:
                events = trader.on_bars(self.client.minute_bars(code, pages=1))
                self.errors[code] = None
            except Exception as exc:  # keep polling other symbols; surface the error in the UI
                self.errors[code] = f"{type(exc).__name__}: {exc}"
                continue
            for entry in events:
                if entry["zone_entered"]:
                    self._alert(code, entry)
        self.last_poll = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    def _alert(self, code: str, entry: dict[str, Any]) -> None:
        record = {"symbol": code, "timestamp": entry["timestamp"], "zones": entry["zone"]["zones"], "sent": False, "error": None}
        if self.notifier is not None:
            try:
                self.notifier.send(zone_entry_message(code, entry, self.reports[code]))
                record["sent"] = True
            except TelegramError as exc:
                record["error"] = str(exc)
        with self.alerts_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def loop(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict[str, Any]:
        return {
            "last_poll": self.last_poll,
            "interval": self.interval,
            "jev_enabled": self.jev_enabled,
            "telegram_enabled": self.notifier is not None,
            "validation_level": self.validation_level,
            "portfolio": self.portfolio.state(),
            "symbols": {code: {**t.state(), "error": self.errors[code]} for code, t in self.traders.items()},
        }


def make_handler(runtime: Runtime) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # keep the terminal quiet
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            # DNS-rebinding guard: only accept requests addressed to this loopback server
            port = self.server.server_address[1]
            if self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}"):
                return True
            self._json(421, {"ok": False, "data": None, "error": "server.py: unexpected Host header"})
            return False

        def do_GET(self) -> None:
            if not self._host_ok():
                return
            url = urlparse(self.path)
            if url.path in GET_ROUTES:
                self._json(*GET_ROUTES[url.path](runtime, parse_qs(url.query)))
                return
            name = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
            target = (STATIC / name).resolve()
            if STATIC not in target.parents or not target.is_file() or target.suffix not in CONTENT_TYPES:
                self._json(404, {"ok": False, "data": None, "error": f"server.py: not found {url.path}"})
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPES[target.suffix])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if not self._host_ok():
                return
            url = urlparse(self.path)
            route = POST_ROUTES.get(url.path)
            if route is None:
                self._json(404, {"ok": False, "data": None, "error": f"server.py: not found {url.path}"})
                return
            # application/json forces a CORS preflight, which this server never answers -> blocks cross-site posts
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self._json(415, {"ok": False, "data": None, "error": "server.py: Content-Type must be application/json"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY:
                self._json(400, {"ok": False, "data": None, "error": "server.py: body size out of range"})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"ok": False, "data": None, "error": "server.py: invalid JSON body"})
                return
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "data": None, "error": "server.py: JSON body must be an object"})
                return
            self._json(*route(runtime, body))

    return Handler


def serve(runtime: Runtime, port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(runtime))
    poller = threading.Thread(target=runtime.loop, daemon=True)
    poller.start()
    print(f"shadow_wik paper UI: http://127.0.0.1:{port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop()
        server.server_close()
