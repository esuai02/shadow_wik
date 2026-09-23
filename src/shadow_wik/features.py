from __future__ import annotations

from dataclasses import dataclass, asdict

from .models import MarketSnapshot, clamp


def weighted_score(items: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in items)
    if total_weight <= 0:
        return 0.0
    return clamp(sum(clamp(value) * weight for value, weight in items) / total_weight)


@dataclass(slots=True)
class FeatureScores:
    tpe: float
    breakout_readiness: float
    hidden_flow: float
    range_exit_risk: float
    algorithmic_capture_risk: float
    scheduled_news_risk: float
    unscheduled_news_risk: float
    news_shock_score: float
    reflexive_pressure: float

    def to_dict(self) -> dict[str, float]:
        return {k: round(v, 2) for k, v in asdict(self).items()}


def trend_potential_energy(s: MarketSnapshot) -> float:
    return weighted_score([
        (s.trend_persistence, 15),
        (s.impulse_retention, 15),
        (s.up_down_volume_asymmetry, 10),
        (s.recovery_efficiency, 20),
        (s.rejection_compression, 15),
        (s.absorption, 10),
        (s.sector_confirmation, 10),
        (max(s.visible_news_strength, s.institutional_flow), 5),
    ])


def breakout_readiness(s: MarketSnapshot) -> float:
    return weighted_score([
        (s.near_resistance_dwell, 12),
        (s.aggressive_buy_pressure, 18),
        (s.resistance_liquidity_depletion, 18),
        (s.rejection_compression, 15),
        (s.volume_anomaly, 10),
        (s.vwap_hold, 10),
        (s.sector_confirmation, 9),
        (s.institutional_flow, 8),
    ])


def hidden_flow_score(s: MarketSnapshot) -> float:
    raw = weighted_score([
        (s.volume_anomaly, 15),
        (s.absorption, 20),
        (s.book_imbalance_change, 15),
        (s.institutional_flow, 20),
        (s.sector_confirmation, 15),
        (s.derivatives_pressure, 10),
        (s.flow_persistence, 5),
    ])
    visible_discount = 1.0 - 0.55 * (clamp(s.visible_news_strength) / 100.0)
    return clamp(raw * visible_discount)


def range_exit_risk(s: MarketSnapshot) -> float:
    return weighted_score([
        (s.range_break_distance, 16),
        (s.outside_range_persistence, 16),
        (s.volume_anomaly, 12),
        (s.absorption, 10),
        (s.sector_confirmation, 12),
        (s.institutional_flow, 12),
        (s.mean_reversion_failure, 17),
        (max(s.visible_news_strength, s.derivatives_pressure), 5),
    ])


def algorithmic_capture_risk(s: MarketSnapshot) -> float:
    position_bias = 0.0
    if s.position.side != "flat":
        position_bias += min(abs(s.position.pnl_pct) * 1.25, 35.0)
        if s.position.added_recently:
            position_bias += 15.0
    position_bias = clamp(position_bias)
    lack_of_counterevidence = 100.0 - clamp(s.contrarian_evidence_seen)
    return weighted_score([
        (s.thesis_recency, 20),
        (s.evidence_recency, 15),
        (100.0 - s.source_independence, 15),
        (s.repeated_narrative_exposure, 20),
        (position_bias, 15),
        (lack_of_counterevidence, 15),
    ])


def scheduled_news_risk(s: MarketSnapshot) -> float:
    n = s.news
    return weighted_score([
        (n.scheduled_event_proximity, 20),
        (n.scheduled_event_impact, 25),
        (n.expectation_skew, 20),
        (n.crowding, 20),
        (n.prepriced_move, 15),
    ])


def unscheduled_news_risk(s: MarketSnapshot) -> float:
    n = s.news
    return weighted_score([
        (n.unscheduled_exposure, 30),
        (n.rumor_sensitivity, 15),
        (s.derivatives_pressure, 10),
        (s.volume_anomaly, 10),
        (s.position.weight_pct, 10),
        (n.crowding, 10),
        (s.flow_persistence, 15),
    ])


def news_shock_score(s: MarketSnapshot) -> float:
    n = s.news
    return weighted_score([
        (n.source_reliability, 20),
        (n.news_novelty, 25),
        (n.price_unabsorbed, 20),
        (n.diffusion_speed, 20),
        (max(s.volume_anomaly, s.sector_confirmation), 15),
    ])


def reflexive_pressure(s: MarketSnapshot) -> float:
    return weighted_score([
        (s.derivatives_pressure, 25),
        (s.aggressive_buy_pressure, 15),
        (s.mean_reversion_failure, 15),
        (s.rejection_compression, 10),
        (s.range_break_distance, 10),
        (s.outside_range_persistence, 10),
        (s.volume_anomaly, 15),
    ])


def compute_features(snapshot: MarketSnapshot) -> FeatureScores:
    s = snapshot.normalized()
    return FeatureScores(
        tpe=trend_potential_energy(s),
        breakout_readiness=breakout_readiness(s),
        hidden_flow=hidden_flow_score(s),
        range_exit_risk=range_exit_risk(s),
        algorithmic_capture_risk=algorithmic_capture_risk(s),
        scheduled_news_risk=scheduled_news_risk(s),
        unscheduled_news_risk=unscheduled_news_risk(s),
        news_shock_score=news_shock_score(s),
        reflexive_pressure=reflexive_pressure(s),
    )
