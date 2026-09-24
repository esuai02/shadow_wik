"""Bars -> fingerprint frames -> significance zones -> live paper trading.

Paper only: this module has no broker order path. Live entries are limited to
zones marked `significant` by zones.evaluate_zones; with no such zone, the
trader observes and never trades.
"""
from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .bar_features import WINDOW, snapshot_from_bars
from .engine import ShadowEngine
from .jev import JevClient
from .models import MarketSnapshot
from .paper_trading import MarketFrame, PaperTradingHarness
from .zones import CostModel, evaluate_zones, significant_rules

RECENT_FRAMES = 120
BAR_SECONDS = timedelta(seconds=60)
KRX_OPEN, KRX_CLOSE = "09:00", "15:20"  # half-open: last bar used is 15:19


def session_bars(symbol: str, bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """KRX codes keep only the continuous regular session (09:00-15:19 KST): the 15:20 closing
    auction and NXT pre/after-market bars trade under different liquidity and are dropped.
    US `EXCHANGE:TICKER` symbols are returned unchanged."""
    if ":" in symbol:
        return bars
    return [b for b in bars if KRX_OPEN <= b["time"][11:16] < KRX_CLOSE]


def frames_from_bars(symbol: str, bars: list[dict[str, Any]], engine: ShadowEngine | None = None,
                     jev: JevClient | None = None) -> list[tuple[MarketFrame, dict[str, Any]]]:
    """One frame per bar once WINDOW bars of the same session exist (after the session filter)."""
    engine = engine or ShadowEngine()
    bars = session_bars(symbol, bars)
    out: list[tuple[MarketFrame, dict[str, Any]]] = []
    previous: dict[str, float] | None = None
    session_start = 0
    for i, bar in enumerate(bars):
        if i and bar["time"][:10] != bars[i - 1]["time"][:10]:
            session_start, previous = i, None
        if i + 1 - session_start < WINDOW:
            continue
        session = bars[session_start:i + 1]
        snapshot = snapshot_from_bars(symbol, session[-WINDOW:], session)
        analysis = engine.analyze(snapshot, jev=jev, previous_features=previous)
        previous = analysis["features"]
        frame = MarketFrame.from_analysis(symbol=symbol, timestamp=bar["time"], price=bar["close"], analysis=analysis)
        out.append((frame, analysis))
    return out


def zone_status(scores: dict[str, float], report: dict[str, Any]) -> dict[str, Any]:
    matched = [z["name"] for z in report["zones"]
               if z["status"] == "significant" and all(scores.get(k, -1) >= v for k, v in z["entry_min"].items())]
    return {"significant": bool(matched), "zones": matched}


def completed(bars: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Drop bars still forming: bar time is the minute start, so it is final only after +60 s."""
    return [b for b in bars if datetime.fromisoformat(b["time"]) + BAR_SECONDS <= now]


@dataclass
class LiveTrader:
    symbol: str
    report: dict[str, Any]
    ledger_path: Path
    jev: JevClient | None = None

    def __post_init__(self) -> None:
        costs = CostModel(**self.report["costs"])  # trade with the same costs the zones were tested with
        self.harness = PaperTradingHarness(significant_rules(self.report), fee_bps_per_side=costs.fee_bps_per_side,
                                           slippage_bps_per_side=costs.slippage_bps_per_side,
                                           ledger_path=self.ledger_path)
        self.engine = ShadowEngine()
        self.last_time: str | None = None
        self.recent: deque[dict[str, Any]] = deque(maxlen=RECENT_FRAMES)
        self.lock = threading.Lock()

    def on_bars(self, bars: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
        """Feed a bar history (oldest first). The first call only warms up; later calls trade
        completed bars newer than the last processed one.

        Zone matching and paper trades always use Jev-free scores, because zones were tested
        on Jev-free scores. Jev (if set) is asked only for new bars and shown as raw context."""
        events: list[dict[str, Any]] = []
        bars = completed(bars, now or datetime.now(timezone.utc))
        today = [b for b in bars if b["time"][:10] == bars[-1]["time"][:10]] if bars else []
        warmup = self.last_time is None
        for frame, analysis in frames_from_bars(self.symbol, today, self.engine):
            if not warmup and frame.timestamp <= self.last_time:
                continue
            jev_view = None
            if not warmup and self.jev is not None:
                try:
                    jev_view = self.engine.analyze(MarketSnapshot.from_dict(analysis["snapshot"]), jev=self.jev).get("jev")
                except Exception as exc:  # Jev is advisory; never block measurement or paper trading
                    jev_view = {"error": f"{type(exc).__name__}: {exc}"}
            zone = zone_status(frame.scores, self.report)
            with self.lock:
                if not warmup and self.last_time[:10] != frame.timestamp[:10]:
                    self.harness.close_all(MarketFrame(self.symbol, self.last_time, self.recent[-1]["price"], {}))
                was_significant = bool(self.recent) and self.recent[-1]["zone"]["significant"]
                result = {"opened": [], "closed": []} if warmup else self.harness.on_frame(frame)
                self.last_time = frame.timestamp
                entry = {
                    "timestamp": frame.timestamp,
                    "price": frame.price,
                    "scores": frame.scores,
                    "signals": [s["code"] for s in analysis["signals"]],
                    "zone": zone,
                    "zone_entered": zone["significant"] and not was_significant and not warmup,
                    "jev": jev_view,
                    "unmeasured": analysis["snapshot"]["metadata"].get("unmeasured", []),
                    "opened": [t.to_dict() for t in result["opened"]],
                    "closed": [t.to_dict() for t in result["closed"]],
                    "warmup": warmup,
                }
                self.recent.append(entry)
            events.append(entry)
        return events

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {
                "symbol": self.symbol,
                "significant_zone_count": len(self.harness.rules),
                "latest": self.recent[-1] if self.recent else None,
                "recent": list(self.recent),
                "open_trades": [t.to_dict() for t in self.harness.open_trades.values()],
                "closed_trades": [t.to_dict() for t in self.harness.closed_trades[-50:]],
                "performance": [p.to_dict() for p in self.harness.performance()],
            }


def build_report(symbol: str, bars: list[dict[str, Any]], costs: CostModel = CostModel()) -> dict[str, Any]:
    frames = [f for f, _ in frames_from_bars(symbol, bars)]
    report = evaluate_zones(frames, costs)
    report["symbol"] = symbol
    report["bars"] = {"count": len(bars), "from": bars[0]["time"], "to": bars[-1]["time"]} if bars else {}
    report["session"] = "all bars" if ":" in symbol else f"KRX regular {KRX_OPEN}-{KRX_CLOSE} (excl.)"
    return report


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
