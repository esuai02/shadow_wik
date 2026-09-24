"""Measure MarketSnapshot fields from 1-minute OHLCV bars.

Only fields that price/volume bars can actually observe are filled. Everything
else keeps its neutral default and is listed in metadata["unmeasured"], so the
UI and reports can show it as Unknown rather than as a measurement.
"""
from __future__ import annotations

from typing import Any

from .models import MarketSnapshot, clamp

WINDOW = 30          # bars used for trend/range state
RECENT = 5           # bars used for "just now" measurements
DWELL_BAND_PCT = 0.2  # within this % of the window high counts as "near resistance"

MEASURED = (
    "trend_persistence", "impulse_retention", "up_down_volume_asymmetry",
    "recovery_efficiency", "rejection_compression", "volume_anomaly",
    "range_break_distance", "outside_range_persistence", "near_resistance_dwell",
    "aggressive_buy_pressure", "vwap_hold",
)
UNMEASURED = (
    "absorption", "book_imbalance_change", "institutional_flow", "sector_confirmation",
    "derivatives_pressure", "flow_persistence", "mean_reversion_failure",
    "resistance_liquidity_depletion", "news", "information",
)


def _ratio(num: float, den: float, default: float = 0.5) -> float:
    return num / den if den > 0 else default


def _close_location(bar: dict[str, float]) -> float:
    return _ratio(bar["close"] - bar["low"], bar["high"] - bar["low"])


def measure(bars: list[dict[str, Any]], session: list[dict[str, Any]]) -> dict[str, float]:
    """`bars` = trailing window ending at the current bar; `session` = same-day bars up to now (for VWAP)."""
    if len(bars) < WINDOW:
        raise ValueError(f"bar_features.py: need {WINDOW} bars, got {len(bars)}")
    w = bars[-WINDOW:]
    last = w[-1]
    closes = [b["close"] for b in w]
    moves = [b - a for a, b in zip(closes, closes[1:])]
    ups = sum(1 for m in moves if m > 0)
    downs = sum(1 for m in moves if m < 0)
    vol_up = sum(b["volume"] for a, b in zip(w, w[1:]) if b["close"] > a["close"])
    vol_down = sum(b["volume"] for a, b in zip(w, w[1:]) if b["close"] < a["close"])
    hi = max(b["high"] for b in w)
    lo = min(b["low"] for b in w)
    prior = w[:-RECENT]
    prior_hi = max(b["high"] for b in prior)
    prior_width = prior_hi - min(b["low"] for b in prior)
    recent = w[-RECENT:]
    avg_vol = sum(b["volume"] for b in w) / len(w)
    recent_vol = sum(b["volume"] for b in recent) / len(recent)
    sess_vol = sum(b["volume"] for b in session)
    vwap = _ratio(sum(b["close"] * b["volume"] for b in session), sess_vol, last["close"])
    last10 = w[-10:]
    wick = [_ratio(b["high"] - b["close"], b["high"] - b["low"], 0.0) for b in last10]
    loc_weight = sum(b["volume"] for b in last10)

    return {
        "trend_persistence": 100 * _ratio(ups, ups + downs),
        "impulse_retention": 100 * _ratio(last["close"] - lo, hi - lo),
        "up_down_volume_asymmetry": 100 * _ratio(vol_up, vol_up + vol_down),
        "recovery_efficiency": 50 + 50 * _ratio(closes[-1] - closes[0], sum(abs(m) for m in moves), 0.0),
        "rejection_compression": 100 * (1 - sum(wick) / len(wick)),
        "volume_anomaly": clamp(50 * _ratio(recent_vol, avg_vol, 1.0)),
        "range_break_distance": clamp(50 + 50 * _ratio(last["close"] - prior_hi, prior_width, 0.0)),
        "outside_range_persistence": 100 * sum(1 for b in recent if b["close"] > prior_hi) / len(recent),
        "near_resistance_dwell": 100 * sum(1 for b in last10 if b["high"] >= hi * (1 - DWELL_BAND_PCT / 100)) / len(last10),
        "aggressive_buy_pressure": 100 * _ratio(sum(_close_location(b) * b["volume"] for b in last10), loc_weight),
        "vwap_hold": 100 * sum(1 for b in last10 if b["close"] >= vwap) / len(last10),
    }


def snapshot_from_bars(symbol: str, bars: list[dict[str, Any]], session: list[dict[str, Any]]) -> MarketSnapshot:
    fields = {k: round(clamp(v), 2) for k, v in measure(bars, session).items()}
    return MarketSnapshot(
        symbol=symbol,
        timestamp=bars[-1]["time"],
        metadata={"source": "kiwoom:ka10080", "measured": list(MEASURED), "unmeasured": list(UNMEASURED)},
        **fields,
    )
