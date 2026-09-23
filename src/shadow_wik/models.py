from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Regime = Literal["uptrend", "downtrend", "range", "transition", "unknown"]
CatalystType = Literal["visible_news", "hidden_flow", "reflexive_positioning", "unknown"]
PositionSide = Literal["long", "short", "flat"]


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(slots=True)
class PositionContext:
    side: PositionSide = "flat"
    pnl_pct: float = 0.0
    weight_pct: float = 0.0
    holding_days: int = 0
    added_recently: bool = False
    entry_recency_days: int | None = None


@dataclass(slots=True)
class NewsState:
    scheduled_event_proximity: float = 0.0
    scheduled_event_impact: float = 0.0
    expectation_skew: float = 0.0
    crowding: float = 0.0
    prepriced_move: float = 0.0
    unscheduled_exposure: float = 0.0
    rumor_sensitivity: float = 0.0
    news_novelty: float = 0.0
    source_reliability: float = 0.0
    diffusion_speed: float = 0.0
    price_unabsorbed: float = 0.0


@dataclass(slots=True)
class MarketSnapshot:
    symbol: str
    timestamp: str
    regime_hint: Regime = "unknown"
    horizon_minutes: int = 15

    trend_persistence: float = 50.0
    impulse_retention: float = 50.0
    up_down_volume_asymmetry: float = 50.0
    recovery_efficiency: float = 50.0
    rejection_compression: float = 50.0

    volume_anomaly: float = 50.0
    absorption: float = 50.0
    book_imbalance_change: float = 50.0
    institutional_flow: float = 50.0
    sector_confirmation: float = 50.0
    derivatives_pressure: float = 50.0
    flow_persistence: float = 50.0

    range_break_distance: float = 0.0
    outside_range_persistence: float = 0.0
    mean_reversion_failure: float = 0.0
    near_resistance_dwell: float = 0.0
    resistance_liquidity_depletion: float = 0.0
    aggressive_buy_pressure: float = 50.0
    vwap_hold: float = 50.0

    visible_news_strength: float = 0.0
    source_independence: float = 50.0
    thesis_recency: float = 0.0
    evidence_recency: float = 0.0
    repeated_narrative_exposure: float = 0.0
    contrarian_evidence_seen: float = 50.0

    position: PositionContext = field(default_factory=PositionContext)
    news: NewsState = field(default_factory=NewsState)
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "MarketSnapshot":
        data = asdict(self)
        score_fields = [
            "trend_persistence", "impulse_retention", "up_down_volume_asymmetry",
            "recovery_efficiency", "rejection_compression", "volume_anomaly",
            "absorption", "book_imbalance_change", "institutional_flow",
            "sector_confirmation", "derivatives_pressure", "flow_persistence",
            "range_break_distance", "outside_range_persistence",
            "mean_reversion_failure", "near_resistance_dwell",
            "resistance_liquidity_depletion", "aggressive_buy_pressure",
            "vwap_hold", "visible_news_strength", "source_independence",
            "thesis_recency", "evidence_recency", "repeated_narrative_exposure",
            "contrarian_evidence_seen",
        ]
        for name in score_fields:
            data[name] = clamp(data[name])
        for name, value in asdict(self.news).items():
            data["news"][name] = clamp(value)
        data["position"]["weight_pct"] = clamp(data["position"]["weight_pct"])
        return MarketSnapshot.from_dict(data)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MarketSnapshot":
        data = dict(raw)
        data["position"] = PositionContext(**data.get("position", {}))
        data["news"] = NewsState(**data.get("news", {}))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
