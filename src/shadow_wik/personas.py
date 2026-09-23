from __future__ import annotations

from dataclasses import dataclass, asdict

from .features import FeatureScores
from .models import MarketSnapshot


@dataclass(slots=True)
class PersonaHypothesis:
    name: str
    intensity: float
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def infer_position_personas(s: MarketSnapshot, f: FeatureScores) -> list[PersonaHypothesis]:
    out: list[PersonaHypothesis] = []
    p = s.position
    if p.side == "long":
        if p.pnl_pct > 8:
            out.append(PersonaHypothesis(
                "profit_long_hold_or_expand",
                min(100.0, 45 + p.pnl_pct * 1.5),
                "Profitable longs may extrapolate recent gains or delay profit-taking.",
            ))
        if p.pnl_pct < -5:
            out.append(PersonaHypothesis(
                "breakeven_anchored_long",
                min(100.0, 45 + abs(p.pnl_pct) * 1.5),
                "Loss-making longs may anchor to entry price and become supply near breakeven.",
            ))
        if f.algorithmic_capture_risk >= 60:
            out.append(PersonaHypothesis(
                "narrative_captured_long",
                f.algorithmic_capture_risk,
                "Recent evidence and repeated narratives may be reinforcing the existing long thesis.",
            ))
    elif p.side == "short":
        if p.pnl_pct < -5 and f.breakout_readiness >= 60:
            out.append(PersonaHypothesis(
                "short_cover_risk",
                min(100.0, (f.breakout_readiness + abs(p.pnl_pct) * 2) / 1.5),
                "Losing shorts near resistance can become forced buyers if price confirms a breakout.",
            ))
        if p.pnl_pct > 8:
            out.append(PersonaHypothesis(
                "profitable_short_hold",
                min(100.0, 45 + p.pnl_pct * 1.5),
                "Profitable shorts may press the trade until downside momentum weakens.",
            ))
    else:
        if f.breakout_readiness >= 65:
            out.append(PersonaHypothesis(
                "fomo_waiting_cash",
                f.breakout_readiness,
                "Flat observers may become breakout buyers once resistance is visibly cleared.",
            ))
    if not out:
        out.append(PersonaHypothesis(
            "neutral_observer",
            50.0,
            "No position-specific behavioral pressure dominates the supplied state.",
        ))
    return out


def infer_market_persona_clusters(s: MarketSnapshot, f: FeatureScores) -> list[PersonaHypothesis]:
    clusters = [
        PersonaHypothesis(
            "momentum_breakout_buyers",
            round((f.breakout_readiness + s.aggressive_buy_pressure + s.volume_anomaly) / 3, 2),
            "Activated by resistance depletion, aggressive buying and abnormal volume.",
        ),
        PersonaHypothesis(
            "early_long_profit_takers",
            round((s.rejection_compression * 0.2 + (100 - s.resistance_liquidity_depletion) * 0.5 + s.volume_anomaly * 0.3), 2),
            "Existing low-cost longs can become supply as price returns to prior highs.",
        ),
        PersonaHypothesis(
            "short_cover_buyers",
            round((s.derivatives_pressure * 0.45 + f.breakout_readiness * 0.35 + s.range_break_distance * 0.2), 2),
            "Shorts may turn into buyers when breakout evidence invalidates the short thesis.",
        ),
        PersonaHypothesis(
            "mean_reversion_traders",
            round(max(0.0, 100 - f.range_exit_risk), 2),
            "Range traders remain active while range-exit evidence is weak.",
        ),
        PersonaHypothesis(
            "institutional_hidden_flow",
            round(f.hidden_flow, 2),
            "Large or persistent order flow may be present without a visible public catalyst.",
        ),
    ]
    return sorted(clusters, key=lambda x: x.intensity, reverse=True)
