from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

HorizonKind = Literal["30m", "day", "3d", "1w", "1m", "3m", "6m", "event"]

_HORIZONS = {"30m", "day", "3d", "1w", "1m", "3m", "6m", "event"}
_REVIEW_LEAD_SECONDS = {
    "30m": 5 * 60,
    "day": 60 * 60,
    "3d": 6 * 60 * 60,
    "1w": 24 * 60 * 60,
    "1m": 3 * 24 * 60 * 60,
    "3m": 7 * 24 * 60 * 60,
    "6m": 14 * 24 * 60 * 60,
    "event": 60 * 60,
}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


@dataclass(slots=True)
class TradePlan:
    trade_id: str
    symbol: str
    entry_time: str
    entry_price: float
    horizon_kind: HorizonKind
    planned_exit_at: str | None = None
    event_name: str | None = None
    event_at: str | None = None
    thesis: str = ""
    success_min_net_return_pct: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id is required")
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.entry_price <= 0:
            raise ValueError("entry_price must be positive")
        if self.horizon_kind not in _HORIZONS:
            raise ValueError(f"unsupported horizon_kind: {self.horizon_kind}")
        parse_time(self.entry_time)
        if self.planned_exit_at:
            parse_time(self.planned_exit_at)
        if self.event_at:
            parse_time(self.event_at)
        if self.horizon_kind == "event" and (not self.event_name or not self.event_at):
            raise ValueError("event horizon requires event_name and event_at")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TradePlan":
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def deadline(self) -> datetime:
        if self.planned_exit_at:
            return parse_time(self.planned_exit_at)
        entry = parse_time(self.entry_time)
        if self.horizon_kind == "30m":
            return entry + timedelta(minutes=30)
        if self.horizon_kind == "day":
            return entry.replace(hour=23, minute=59, second=59, microsecond=0)
        if self.horizon_kind == "3d":
            return entry + timedelta(days=3)
        if self.horizon_kind == "1w":
            return entry + timedelta(days=7)
        if self.horizon_kind == "1m":
            return _add_months(entry, 1)
        if self.horizon_kind == "3m":
            return _add_months(entry, 3)
        if self.horizon_kind == "6m":
            return _add_months(entry, 6)
        if self.horizon_kind == "event":
            return parse_time(self.event_at or "")
        raise ValueError(f"unsupported horizon_kind: {self.horizon_kind}")


@dataclass(slots=True)
class TradeClock:
    now: str
    deadline: str
    elapsed_seconds: float
    remaining_seconds: float
    progress_pct: float
    exit_window_open: bool
    expired: bool
    event_name: str | None
    event_at: str | None
    event_remaining_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["elapsed_seconds"] = round(self.elapsed_seconds, 3)
        data["remaining_seconds"] = round(self.remaining_seconds, 3)
        data["progress_pct"] = round(self.progress_pct, 2)
        if data["event_remaining_seconds"] is not None:
            data["event_remaining_seconds"] = round(float(data["event_remaining_seconds"]), 3)
        return data


def build_trade_clock(plan: TradePlan, now: str) -> TradeClock:
    start = parse_time(plan.entry_time)
    current = parse_time(now)
    deadline = plan.deadline()
    total = max(1.0, (deadline - start).total_seconds())
    elapsed = (current - start).total_seconds()
    remaining = (deadline - current).total_seconds()
    progress = max(0.0, min(100.0, elapsed / total * 100.0))
    lead = _REVIEW_LEAD_SECONDS[plan.horizon_kind]
    event_remaining = None
    if plan.event_at:
        event_remaining = (parse_time(plan.event_at) - current).total_seconds()
    return TradeClock(
        now=current.isoformat(),
        deadline=deadline.isoformat(),
        elapsed_seconds=elapsed,
        remaining_seconds=remaining,
        progress_pct=progress,
        exit_window_open=remaining <= lead,
        expired=remaining <= 0,
        event_name=plan.event_name,
        event_at=plan.event_at,
        event_remaining_seconds=event_remaining,
    )


def build_trade_state(plan: TradePlan, *, now: str, current_price: float) -> dict[str, Any]:
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    clock = build_trade_clock(plan, now)
    pnl_pct = (current_price / plan.entry_price - 1.0) * 100.0
    if clock.expired:
        phase = "decision_due"
    elif clock.exit_window_open:
        phase = "exit_window"
    else:
        phase = "holding"
    return {
        "plan": plan.to_dict(),
        "clock": clock.to_dict(),
        "current_price": float(current_price),
        "gross_pnl_pct": round(pnl_pct, 6),
        "phase": phase,
        "final_decision_owner": "human",
    }
