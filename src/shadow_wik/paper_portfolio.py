from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paper_trading import MarketFrame, PaperTrade, PatternRule


@dataclass(slots=True)
class PortfolioPosition:
    key: str
    symbol: str
    pattern: str
    notional_krw: float
    entry_time: str
    entry_price: float
    mark_return_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "symbol": self.symbol,
            "pattern": self.pattern,
            "notional_krw": round(self.notional_krw, 2),
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "mark_return_pct": round(self.mark_return_pct, 6),
        }


@dataclass
class PaperPortfolio:
    seed_krw: float = 100_000_000.0
    per_trade_fraction: float = 0.10
    max_positions: int = 10
    event_path: Path | None = None
    cash_krw: float = field(init=False)
    realized_pnl_krw: float = field(default=0.0, init=False)
    closed_trades: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.seed_krw <= 0:
            raise ValueError("seed_krw must be positive")
        if not (0 < self.per_trade_fraction <= 1):
            raise ValueError("per_trade_fraction must be in (0,1]")
        if self.max_positions < 1:
            raise ValueError("max_positions must be >= 1")
        self.cash_krw = float(self.seed_krw)
        self._reservations: dict[tuple[str, str], float] = {}
        self._positions: dict[str, PortfolioPosition] = {}
        self._lock = threading.Lock()

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self.event_path is None:
            return
        self.event_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": kind, **payload}, ensure_ascii=False, separators=(",", ":")) + "\n")

    @staticmethod
    def _trade_key(trade: PaperTrade) -> str:
        return f"{trade.symbol}|{trade.pattern}|{trade.entry_time}"

    def reserve(self, rule: PatternRule, frame: MarketFrame) -> bool:
        pair = (frame.symbol, rule.name)
        with self._lock:
            if pair in self._reservations:
                return False
            if any(p.symbol == frame.symbol and p.pattern == rule.name for p in self._positions.values()):
                return False
            if len(self._positions) + len(self._reservations) >= self.max_positions:
                return False
            target = min(self.seed_krw * self.per_trade_fraction, self.cash_krw)
            if target <= 0:
                return False
            self.cash_krw -= target
            self._reservations[pair] = target
            return True

    def confirm_open(self, trade: PaperTrade) -> None:
        pair = (trade.symbol, trade.pattern)
        with self._lock:
            notional = self._reservations.pop(pair, None)
            if notional is None:
                return
            key = self._trade_key(trade)
            self._positions[key] = PortfolioPosition(
                key=key,
                symbol=trade.symbol,
                pattern=trade.pattern,
                notional_krw=notional,
                entry_time=trade.entry_time,
                entry_price=trade.entry_price,
            )
            self._emit("portfolio_open", {"trade_id": trade.trade_id, "position": self._positions[key].to_dict()})

    def mark(self, trade: PaperTrade, raw_price: float) -> None:
        key = self._trade_key(trade)
        with self._lock:
            pos = self._positions.get(key)
            if pos is None:
                return
            if trade.side == "long":
                pos.mark_return_pct = (float(raw_price) / trade.entry_price - 1.0) * 100.0
            else:
                pos.mark_return_pct = (trade.entry_price - float(raw_price)) / trade.entry_price * 100.0

    def close(self, trade: PaperTrade) -> None:
        key = self._trade_key(trade)
        with self._lock:
            pos = self._positions.pop(key, None)
            if pos is None:
                return
            net_pct = float(trade.net_return_pct or 0.0)
            pnl = pos.notional_krw * net_pct / 100.0
            self.cash_krw += pos.notional_krw + pnl
            self.realized_pnl_krw += pnl
            self.closed_trades += 1
            self._emit("portfolio_close", {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "pattern": trade.pattern,
                "net_return_pct": net_pct,
                "pnl_krw": round(pnl, 2),
                "cash_krw": round(self.cash_krw, 2),
            })

    def state(self) -> dict[str, Any]:
        with self._lock:
            open_value = sum(p.notional_krw * (1.0 + p.mark_return_pct / 100.0) for p in self._positions.values())
            equity = self.cash_krw + open_value
            return {
                "seed_krw": round(self.seed_krw, 2),
                "cash_krw": round(self.cash_krw, 2),
                "open_value_krw": round(open_value, 2),
                "equity_krw": round(equity, 2),
                "realized_pnl_krw": round(self.realized_pnl_krw, 2),
                "return_pct": round((equity / self.seed_krw - 1.0) * 100.0, 6),
                "open_positions": len(self._positions),
                "max_positions": self.max_positions,
                "per_trade_krw": round(self.seed_krw * self.per_trade_fraction, 2),
                "closed_trades": self.closed_trades,
                "positions": [p.to_dict() for p in self._positions.values()],
                "note": "Paper-only KRW notional model; FX effects are not modeled for non-KRW symbols.",
            }
