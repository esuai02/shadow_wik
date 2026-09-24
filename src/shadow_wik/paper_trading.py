from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

Side = Literal["long", "short"]
CloseReason = Literal["take_profit", "stop_loss", "max_hold", "pattern_invalidation", "manual"]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _bps(value: float) -> float:
    return float(value) / 10_000.0


@dataclass(slots=True)
class PatternRule:
    name: str
    side: Side
    entry_min: dict[str, float]
    exit_below: dict[str, float] = field(default_factory=dict)
    take_profit_pct: float = 1.0
    stop_loss_pct: float = 0.7
    max_hold_seconds: int = 900
    cooldown_seconds: int = 60
    jev_question: str | None = None
    min_jev_probability: float | None = None
    hypothesis_status: str = "synthetic"
    holding_horizon: str = "30m"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PatternRule":
        return cls(**raw)

    def matches(self, scores: dict[str, float], jev_response: dict[str, Any] | None = None) -> bool:
        for key, threshold in self.entry_min.items():
            if float(scores.get(key, -math.inf)) < float(threshold):
                return False
        if self.jev_question is not None and self.min_jev_probability is not None:
            if not jev_response:
                return False
            answer = jev_response.get("answers", {}).get(self.jev_question, {})
            value = answer.get("noul")
            if not isinstance(value, (int, float)) or float(value) < self.min_jev_probability:
                return False
        return True

    def invalidated(self, scores: dict[str, float]) -> bool:
        return any(float(scores.get(key, -math.inf)) < float(threshold) for key, threshold in self.exit_below.items())


@dataclass(slots=True)
class MarketFrame:
    symbol: str
    timestamp: str
    price: float
    scores: dict[str, float]
    jev_response: dict[str, Any] | None = None

    @classmethod
    def from_analysis(cls, *, symbol: str, timestamp: str, price: float, analysis: dict[str, Any]) -> "MarketFrame":
        fingerprint = analysis.get("fingerprint", {})
        scores = fingerprint.get("scores") if isinstance(fingerprint, dict) else None
        if not isinstance(scores, dict):
            raise ValueError("analysis.fingerprint.scores is required")
        return cls(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            scores={str(k): float(v) for k, v in scores.items()},
            jev_response=analysis.get("jev"),
        )


@dataclass(slots=True)
class PaperTrade:
    trade_id: str
    pattern: str
    symbol: str
    side: Side
    entry_time: str
    entry_raw_price: float
    entry_price: float
    entry_scores: dict[str, float]
    hypothesis_status: str
    holding_horizon: str
    exit_time: str | None = None
    exit_raw_price: float | None = None
    exit_price: float | None = None
    exit_scores: dict[str, float] | None = None
    close_reason: CloseReason | None = None
    gross_return_pct: float | None = None
    net_return_pct: float | None = None
    success: bool | None = None
    success_basis: str | None = None
    mfe_pct: float = 0.0
    mae_pct: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PatternPerformance:
    pattern: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    average_return_pct: float
    compounded_return_pct: float
    profit_factor: float | None
    average_mfe_pct: float
    average_mae_pct: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "win_rate",
            "average_return_pct",
            "compounded_return_pct",
            "average_mfe_pct",
            "average_mae_pct",
        ):
            data[key] = round(float(data[key]), 6)
        if data["profit_factor"] is not None:
            data["profit_factor"] = round(float(data["profit_factor"]), 6)
        return data


class PaperTradingHarness:
    def __init__(
        self,
        rules: list[PatternRule],
        *,
        fee_bps_per_side: float = 1.5,
        slippage_bps_per_side: float = 2.0,
        ledger_path: str | Path | None = None,
    ) -> None:
        self.rules = {rule.name: rule for rule in rules}
        self.fee_bps_per_side = float(fee_bps_per_side)
        self.slippage_bps_per_side = float(slippage_bps_per_side)
        self.ledger_path = Path(ledger_path) if ledger_path is not None else None
        self.open_trades: dict[tuple[str, str], PaperTrade] = {}
        self.closed_trades: list[PaperTrade] = []
        self.last_close_at: dict[tuple[str, str], datetime] = {}
        self._sequence = 0

    def _execution_price(self, raw_price: float, side: Side, opening: bool) -> float:
        slip = _bps(self.slippage_bps_per_side)
        if side == "long":
            return raw_price * (1.0 + slip if opening else 1.0 - slip)
        return raw_price * (1.0 - slip if opening else 1.0 + slip)

    def _mark_return_pct(self, trade: PaperTrade, raw_price: float) -> float:
        if trade.side == "long":
            return (raw_price / trade.entry_price - 1.0) * 100.0
        return (trade.entry_price - raw_price) / trade.entry_price * 100.0

    def _net_return_pct(self, trade: PaperTrade, exit_price: float) -> tuple[float, float]:
        if trade.side == "long":
            gross = (exit_price / trade.entry_price - 1.0) * 100.0
        else:
            gross = (trade.entry_price - exit_price) / trade.entry_price * 100.0
        fee_pct = self.fee_bps_per_side * 2.0 / 100.0
        return gross, gross - fee_pct

    def _write_event(self, kind: str, trade: PaperTrade) -> None:
        if self.ledger_path is None:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"kind": kind, "trade": trade.to_dict()},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "
"
            )

    def _open(self, rule: PatternRule, frame: MarketFrame) -> PaperTrade:
        self._sequence += 1
        trade = PaperTrade(
            trade_id=f"paper-{self._sequence}",
            pattern=rule.name,
            symbol=frame.symbol,
            side=rule.side,
            entry_time=frame.timestamp,
            entry_raw_price=float(frame.price),
            entry_price=self._execution_price(float(frame.price), rule.side, opening=True),
            entry_scores=dict(frame.scores),
            hypothesis_status=rule.hypothesis_status,
            holding_horizon=rule.holding_horizon,
        )
        self.open_trades[(frame.symbol, rule.name)] = trade
        self._write_event("paper_open", trade)
        return trade

    def _close(self, key: tuple[str, str], frame: MarketFrame, reason: CloseReason) -> PaperTrade:
        trade = self.open_trades.pop(key)
        exit_price = self._execution_price(float(frame.price), trade.side, opening=False)
        gross, net = self._net_return_pct(trade, exit_price)
        trade.exit_time = frame.timestamp
        trade.exit_raw_price = float(frame.price)
        trade.exit_price = exit_price
        trade.exit_scores = dict(frame.scores)
        trade.close_reason = reason
        trade.gross_return_pct = gross
        trade.net_return_pct = net
        trade.success = net > 0.0
        trade.success_basis = "auto:net_return>0%"
        self.closed_trades.append(trade)
        self.last_close_at[key] = _parse_time(frame.timestamp)
        self._write_event("paper_close", trade)
        return trade

    def on_frame(self, frame: MarketFrame) -> dict[str, list[PaperTrade]]:
        if frame.price <= 0:
            raise ValueError("frame.price must be positive")
        now = _parse_time(frame.timestamp)
        opened: list[PaperTrade] = []
        closed: list[PaperTrade] = []
        for rule in self.rules.values():
            key = (frame.symbol, rule.name)
            trade = self.open_trades.get(key)
            if trade is not None:
                mark = self._mark_return_pct(trade, float(frame.price))
                trade.mfe_pct = max(trade.mfe_pct, mark)
                trade.mae_pct = min(trade.mae_pct, mark)
                elapsed = (now - _parse_time(trade.entry_time)).total_seconds()
                reason: CloseReason | None = None
                if mark >= rule.take_profit_pct:
                    reason = "take_profit"
                elif mark <= -rule.stop_loss_pct:
                    reason = "stop_loss"
                elif rule.invalidated(frame.scores):
                    reason = "pattern_invalidation"
                elif elapsed >= rule.max_hold_seconds:
                    reason = "max_hold"
                if reason is not None:
                    closed.append(self._close(key, frame, reason))
                    continue
            if key in self.open_trades:
                continue
            last_close = self.last_close_at.get(key)
            if last_close is not None and (now - last_close).total_seconds() < rule.cooldown_seconds:
                continue
            if rule.matches(frame.scores, frame.jev_response):
                opened.append(self._open(rule, frame))
        return {"opened": opened, "closed": closed}

    def close_all(self, frame: MarketFrame) -> list[PaperTrade]:
        closed: list[PaperTrade] = []
        for key in list(self.open_trades):
            if key[0] == frame.symbol:
                closed.append(self._close(key, frame, "manual"))
        return closed

    def performance(self, pattern: str | None = None) -> list[PatternPerformance]:
        groups: dict[str, list[PaperTrade]] = {}
        for trade in self.closed_trades:
            if pattern is None or trade.pattern == pattern:
                groups.setdefault(trade.pattern, []).append(trade)

        results: list[PatternPerformance] = []
        for name, trades in sorted(groups.items()):
            returns = [float(t.net_return_pct or 0.0) for t in trades]
            wins = sum(1 for value in returns if value > 0)
            losses = len(returns) - wins
            average = sum(returns) / len(returns)
            compounded = 1.0
            for value in returns:
                compounded *= 1.0 + value / 100.0
            gains = sum(value for value in returns if value > 0)
            losses_abs = abs(sum(value for value in returns if value < 0))
            profit_factor = None if losses_abs == 0 else gains / losses_abs
            results.append(
                PatternPerformance(
                    pattern=name,
                    trades=len(trades),
                    wins=wins,
                    losses=losses,
                    win_rate=wins / len(trades),
                    average_return_pct=average,
                    compounded_return_pct=(compounded - 1.0) * 100.0,
                    profit_factor=profit_factor,
                    average_mfe_pct=sum(t.mfe_pct for t in trades) / len(trades),
                    average_mae_pct=sum(t.mae_pct for t in trades) / len(trades),
                )
            )
        return results
