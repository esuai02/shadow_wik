"""Bars -> fingerprint -> significance zones (or explicit Jev scalp mode) -> funded live paper trading.

Paper only: this module has no broker order path. Default mode trades only zones marked
`significant` by zones.evaluate_zones; Jev, when configured, is advisory: asked on
pre-registered triggers, shown in the UI and logged for calibration. The Jev scalp
hypothesis library trades only when paper_mode="jev_scalp" is chosen explicitly.
"""
from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .bar_features import WINDOW, snapshot_from_bars, snapshot_from_opening_bars
from .engine import ShadowEngine
from .jev import JevClient
from .journal import DecisionLedger
from .models import MarketSnapshot
from .paper_portfolio import PaperPortfolio
from .paper_trading import MarketFrame, PaperTradingHarness
from .scalp_patterns import SCALP_PATTERNS, build_scalp_rules, jev_probability_floor, pattern_evidence_by_name
from .zones import CostModel, evaluate_zones, significant_rules

RECENT_FRAMES = 120
BAR_SECONDS = timedelta(seconds=60)
PAPER_MODES = ("statistical_zone", "jev_scalp")
JEV_COOLDOWN = timedelta(minutes=10)
KRX_OPEN, KRX_OPENING_HOUR_END, KRX_CLOSE = "09:00", "10:00", "15:20"  # opening focus is 09:00-09:59


def in_opening_hour(symbol: str, timestamp: str) -> bool:
    """The project's primary decision window: KRX 09:00-09:59 KST.

    US symbols are excluded until a separate market-open contract is explicitly defined.
    """
    return len(symbol) == 6 and symbol.isdigit() and KRX_OPEN <= timestamp[11:16] < KRX_OPENING_HOUR_END


def session_bars(symbol: str, bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """KRX codes keep only the continuous regular session (09:00-15:19 KST): the 15:20 closing
    auction and NXT pre/after-market bars trade under different liquidity and are dropped.
    US `EXCHANGE:TICKER` symbols are returned unchanged."""
    if ":" in symbol:
        return bars
    return [b for b in bars if KRX_OPEN <= b["time"][11:16] < KRX_CLOSE]


def frames_from_bars(symbol: str, bars: list[dict[str, Any]], engine: ShadowEngine | None = None,
                     jev: JevClient | None = None, opening_partial: bool = False) -> list[tuple[MarketFrame, dict[str, Any]]]:
    """One frame per bar; live opening mode may start from 3 completed bars for Jev observation."""
    engine = engine or ShadowEngine()
    bars = session_bars(symbol, bars)
    out: list[tuple[MarketFrame, dict[str, Any]]] = []
    previous: dict[str, float] | None = None
    session_start = 0
    for i, bar in enumerate(bars):
        if i and bar["time"][:10] != bars[i - 1]["time"][:10]:
            session_start, previous = i, None
        session = bars[session_start:i + 1]
        if len(session) < WINDOW:
            if not (opening_partial and len(session) >= 3 and in_opening_hour(symbol, bar["time"])):
                continue
            snapshot = snapshot_from_opening_bars(symbol, session)
        else:
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
    portfolio: PaperPortfolio | None = None
    validation_level: int = 0
    # "statistical_zone": trade only significant zones; Jev (if set) is advisory, trigger-gated and logged.
    # "jev_scalp": trade Jev scalp hypotheses every bar (must be chosen explicitly).
    paper_mode: str = "statistical_zone"
    jev_log_path: Path | None = None

    def __post_init__(self) -> None:
        costs = CostModel(**self.report["costs"])
        self.validation_level = max(0, min(100, int(self.validation_level)))
        if self.paper_mode not in PAPER_MODES:
            raise ValueError(f"trader.py: paper_mode must be one of {PAPER_MODES}")
        if self.paper_mode == "jev_scalp" and self.jev is None:
            raise ValueError("trader.py: paper_mode 'jev_scalp' needs a Jev client")
        self.last_jev_at: datetime | None = None
        self._jev_ledger: DecisionLedger | None = None
        rules = build_scalp_rules(self.validation_level) if self.paper_mode == "jev_scalp" else significant_rules(self.report)
        self.harness = PaperTradingHarness(
            rules,
            fee_bps_per_side=costs.fee_bps_per_side,
            slippage_bps_per_side=costs.slippage_bps_per_side,
            ledger_path=self.ledger_path,
        )
        self.portfolio = self.portfolio or PaperPortfolio()
        self.engine = ShadowEngine()
        self.last_time: str | None = None
        self.recent: deque[dict[str, Any]] = deque(maxlen=RECENT_FRAMES)
        self.lock = threading.Lock()

    def _jev_trigger(self, frame: MarketFrame, analysis: dict[str, Any], zone: dict[str, Any]) -> str | None:
        """Why Jev should be asked about this bar, or None. Scalp mode asks every bar (its own design);
        zone mode asks only on pre-registered triggers, at most once per JEV_COOLDOWN per symbol."""
        if self.paper_mode == "jev_scalp":
            return "scalp_mode_every_bar"
        now = datetime.fromisoformat(frame.timestamp)
        if in_opening_hour(self.symbol, frame.timestamp):
            self.last_jev_at = now
            return "opening_hour"
        if self.last_jev_at is not None and now - self.last_jev_at < JEV_COOLDOWN:
            return None
        signals = [x["code"] for x in analysis["signals"] if x["code"] != "NO_EDGE"]
        reason = "significant_zone" if zone["significant"] else ("signal:" + ",".join(signals) if signals else None)
        if reason is not None:
            self.last_jev_at = now
        return reason

    def _log_jev(self, frame: MarketFrame, analysis: dict[str, Any], response: dict[str, Any] | None) -> None:
        """Keep every Jev answer for later outcome resolution and calibration (never used to trade here)."""
        if self.jev_log_path is None or not response or "answers" not in response:
            return
        if self._jev_ledger is None:
            self.jev_log_path.parent.mkdir(parents=True, exist_ok=True)
            self._jev_ledger = DecisionLedger(self.jev_log_path)
        snap = analysis["snapshot"]
        self._jev_ledger.record_response(timestamp=frame.timestamp, symbol=self.symbol, regime=snap["regime_hint"],
                                         horizon_minutes=snap["horizon_minutes"], response=response)

    def set_validation_level(self, level: int) -> None:
        self.validation_level = max(0, min(100, int(level)))
        self._refresh_pattern_rules()

    def _pattern_evidence(self) -> dict[str, dict[str, Any]]:
        if self.paper_mode != "jev_scalp":
            return {}
        return pattern_evidence_by_name(self.harness.closed_trades)

    def _refresh_pattern_rules(self) -> None:
        if self.paper_mode != "jev_scalp":
            return
        evidence = self._pattern_evidence()
        floor = jev_probability_floor(self.validation_level)
        for pattern in SCALP_PATTERNS:
            rule = self.harness.rules.get(pattern.key)
            if rule is None:
                continue
            strength = float(evidence.get(pattern.key, {}).get("strength", 0.0))
            # 0 explicitly means exploration: no historical significance gate.
            rule.min_jev_probability = floor if self.validation_level == 0 or strength >= self.validation_level else 2.0

    def _pattern_view(self, probabilities: dict[str, float]) -> list[dict[str, Any]]:
        evidence = self._pattern_evidence()
        floor = jev_probability_floor(self.validation_level)
        out: list[dict[str, Any]] = []
        for pattern in SCALP_PATTERNS:
            prob = probabilities.get(pattern.key)
            strength = float(evidence.get(pattern.key, {}).get("strength", 0.0))
            history_ok = self.validation_level == 0 or strength >= self.validation_level
            out.append({
                "key": pattern.key,
                "label": pattern.label,
                "probability": prob,
                "jev_floor": floor,
                "paper_evidence_strength": strength,
                "history_gate": history_ok,
                "recognized": bool(prob is not None and prob >= floor),
                "eligible": bool(prob is not None and prob >= floor and history_ok),
            })
        return out

    def on_bars(self, bars: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
        """Feed a bar history (oldest first). The first call only warms up; later calls trade
        completed bars newer than the last processed one.

        Zone matching and paper trades always use Jev-free scores, because zones were tested
        on Jev-free scores. Jev (if set) is asked only for new bars and shown as raw context."""
        events: list[dict[str, Any]] = []
        bars = completed(bars, now or datetime.now(timezone.utc))
        today = [b for b in bars if b["time"][:10] == bars[-1]["time"][:10]] if bars else []
        warmup = self.last_time is None
        for frame, analysis in frames_from_bars(self.symbol, today, self.engine, opening_partial=True):
            if not warmup and frame.timestamp <= self.last_time:
                continue
            jev_view = None
            scalp_probabilities: dict[str, float] = {}
            opening_hour = None
            primitive_mechanisms = None
            partial_opening = bool(analysis["snapshot"]["metadata"].get("partial_opening"))
            zone = zone_status(frame.scores, self.report)
            jev_trigger = None if warmup or self.jev is None else self._jev_trigger(frame, analysis, zone)
            if jev_trigger is not None:
                try:
                    live_analysis = self.engine.analyze(
                        MarketSnapshot.from_dict(analysis["snapshot"]),
                        jev=self.jev,
                        include_scalp_patterns=self.paper_mode == "jev_scalp",
                        include_opening_hour=in_opening_hour(self.symbol, frame.timestamp),
                    )
                    jev_view = live_analysis.get("jev")
                    scalp_probabilities = live_analysis.get("scalp_patterns", {})
                    opening_hour = live_analysis.get("opening_hour")
                    primitive_mechanisms = live_analysis.get("primitive_mechanisms")
                    self._log_jev(frame, analysis, jev_view)
                except Exception as exc:  # Jev is advisory; a failed call must not fabricate a pattern
                    jev_view = {"error": f"{type(exc).__name__}: {exc}"}
            with self.lock:
                if not warmup and self.last_time[:10] != frame.timestamp[:10]:
                    day_closed = self.harness.close_all(
                        MarketFrame(self.symbol, self.last_time, self.recent[-1]["price"], self.recent[-1]["scores"])
                    )
                    for trade in day_closed:
                        self.portfolio.close(trade)
                was_significant = bool(self.recent) and self.recent[-1]["zone"]["significant"]
                self._refresh_pattern_rules()
                trade_frame = MarketFrame(
                    self.symbol,
                    frame.timestamp,
                    frame.price,
                    frame.scores,
                    jev_view if self.paper_mode == "jev_scalp" else None,
                )
                result = {"opened": [], "closed": []} if warmup or partial_opening else self.harness.on_frame(
                    trade_frame,
                    allow_open=self.portfolio.reserve,
                )
                for trade in result["opened"]:
                    self.portfolio.confirm_open(trade)
                for trade in result["closed"]:
                    self.portfolio.close(trade)
                for trade in self.harness.open_trades.values():
                    self.portfolio.mark(trade, frame.price)
                patterns = self._pattern_view(scalp_probabilities) if self.paper_mode == "jev_scalp" else []
                self.last_time = frame.timestamp
                entry = {
                    "timestamp": frame.timestamp,
                    "price": frame.price,
                    "scores": frame.scores,
                    "signals": [sig["code"] for sig in analysis["signals"]],
                    "zone": zone,
                    "zone_entered": zone["significant"] and not was_significant and not warmup,
                    "paper_mode": self.paper_mode,
                    "validation_level": self.validation_level,
                    "patterns": patterns,
                    "pattern_entered": bool(result["opened"]),
                    "jev": jev_view,
                    "jev_trigger": jev_trigger,
                    "opening_hour": opening_hour,
                    "primitive_mechanisms": primitive_mechanisms,
                    "partial_opening": partial_opening,
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
                "paper_mode": self.paper_mode,
                "validation_level": self.validation_level,
                "significant_zone_count": len([z for z in self.report.get("zones", []) if z.get("status") == "significant"]),
                "latest": self.recent[-1] if self.recent else None,
                "recent": list(self.recent),
                "open_trades": [t.to_dict() for t in self.harness.open_trades.values()],
                "closed_trades": [t.to_dict() for t in self.harness.closed_trades[-50:]],
                "performance": [p.to_dict() for p in self.harness.performance()],
                "pattern_evidence": self._pattern_evidence(),
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
