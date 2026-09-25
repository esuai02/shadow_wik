from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .features import compute_features
from .fingerprint import build_breakout_long_fingerprint
from .jev import JevClient, build_questions, summarize_exit_focus, summarize_opening_hour_focus, summarize_scalp_patterns
from .models import MarketSnapshot
from .personas import infer_market_persona_clusters, infer_position_personas
from .scalp_patterns import pattern_catalog
from .signals import build_signals
from .trade_lifecycle import TradePlan, build_trade_state
from .visual_grammar import build_visual_state


# Features whose weight is mostly unobservable from price/volume bars alone (see features.py).
MOSTLY_UNOBSERVED_FEATURES = (
    "hidden_flow", "scheduled_news_risk", "unscheduled_news_risk", "news_shock_score", "algorithmic_capture_risk",
)


def mask_unobserved(state: dict[str, Any], unobserved: set[str]) -> dict[str, Any]:
    """Send unobserved inputs to Jev as null instead of their neutral defaults.

    A neutral default (e.g. 50) otherwise reads as a measurement: Jev judged a
    `hidden_flow` catalyst from all-default flow fields in the 2026-09-25 E0 call.
    """
    info = state["information"]
    masked_info = {k: (None if "information" in unobserved else v) for k, v in info.items() if k != "news"}
    masked_info["news"] = {k: None for k in info["news"]} if "news" in unobserved else info["news"]
    return {
        **state,
        "features": {k: (None if k in MOSTLY_UNOBSERVED_FEATURES else v) for k, v in state["features"].items()},
        "microstructure": {k: (None if k in unobserved else v) for k, v in state["microstructure"].items()},
        "information": masked_info,
        "unobserved_fields": sorted(unobserved),
        "rules": {**state["rules"], "unobserved": "null means not observed. Do not infer flow, news, or catalysts from missing values."},
    }


class ShadowEngine:
    def analyze(
        self,
        snapshot: MarketSnapshot,
        jev: JevClient | None = None,
        previous_features: dict[str, float] | None = None,
        trade_plan: TradePlan | None = None,
        current_price: float | None = None,
        include_scalp_patterns: bool = False,
        include_opening_hour: bool = False,
    ) -> dict[str, Any]:
        s = snapshot.normalized()
        features = compute_features(s)
        market_personas = infer_market_persona_clusters(s, features)
        position_personas = infer_position_personas(s, features)

        trade_state = None
        if trade_plan is not None:
            if current_price is None:
                raise ValueError("current_price is required when trade_plan is supplied")
            trade_state = build_trade_state(trade_plan, now=s.timestamp, current_price=current_price)

        questions = build_questions(
            include_exit=trade_plan is not None,
            include_scalp=include_scalp_patterns,
            include_opening_hour=include_opening_hour,
        )
        jev_state = {
            "symbol": s.symbol,
            "timestamp": s.timestamp,
            "regime_hint": s.regime_hint,
            "horizon_minutes": s.horizon_minutes,
            "position": asdict(s.position),
            "features": features.to_dict(),
            "microstructure": {
                "volume_anomaly": s.volume_anomaly,
                "absorption": s.absorption,
                "book_imbalance_change": s.book_imbalance_change,
                "institutional_flow": s.institutional_flow,
                "sector_confirmation": s.sector_confirmation,
                "derivatives_pressure": s.derivatives_pressure,
                "flow_persistence": s.flow_persistence,
                "mean_reversion_failure": s.mean_reversion_failure,
                "resistance_liquidity_depletion": s.resistance_liquidity_depletion,
                "rejection_compression": s.rejection_compression,
            },
            "information": {
                "visible_news_strength": s.visible_news_strength,
                "source_independence": s.source_independence,
                "thesis_recency": s.thesis_recency,
                "evidence_recency": s.evidence_recency,
                "repeated_narrative_exposure": s.repeated_narrative_exposure,
                "contrarian_evidence_seen": s.contrarian_evidence_seen,
                "news": asdict(s.news),
            },
            "persona_hypotheses": {
                "same_position": [p.to_dict() for p in position_personas],
                "market": [p.to_dict() for p in market_personas],
            },
            "rules": {
                "causality": "Treat correlations as causal hypotheses only when time order, mechanism, and falsification conditions are present.",
                "unknown_catalyst": "Unknown means cause not observed, not cause absent.",
                "probability": "Jev outputs are raw model probabilities until calibrated on realized market outcomes.",
                "exit_horizon": "When a trade lifecycle is supplied, judge hold/reduce/exit inside the precommitted time or event horizon; do not silently convert a short trade into a longer investment thesis.",
                "final_authority": "Jev exit_action is advisory. The human owns the final sell decision.",
            },
        }
        unobserved = set(s.metadata.get("unmeasured", []))
        if unobserved:
            jev_state = mask_unobserved(jev_state, unobserved)
        if trade_state is not None:
            jev_state["trade_lifecycle"] = trade_state
        if include_scalp_patterns:
            jev_state["scalp_pattern_hypotheses"] = pattern_catalog()
        if include_opening_hour:
            jev_state["opening_hour_contract"] = {
                "market_window": "KRX 09:00-09:59 KST only",
                "decision": "choose buy_state or sell_state from current evidence; sell_state may remain cash all day",
                "buy_state": "if long exposure exists, decide hold/reduce/exit inside the opening-hour window",
                "sell_state": "decide enter/wait/observe_today; missed upside is not a realized loss",
                "fomo": "uncaptured upside is hypothetical money and must not be treated as a loss to recover",
                "falling_price": "a lower price alone is not an opportunity; require stabilization/reversal evidence",
                "long_term": "passive long-term holdings are outside this opening-hour decision and must not rescue the thesis",
            }

        result: dict[str, Any] = {
            "snapshot": s.to_dict(),
            "features": features.to_dict(),
            "position_personas": [p.to_dict() for p in position_personas],
            "market_personas": [p.to_dict() for p in market_personas],
            "trade_state": trade_state,
            "jev_request": {"state": jev_state, "questions": questions},
            "jev": None,
            "scalp_patterns": {},
            "opening_hour": summarize_opening_hour_focus(None) if include_opening_hour else None,
        }
        if jev is not None:
            result["jev"] = jev.evaluate(jev_state, questions)
            if include_scalp_patterns:
                result["scalp_patterns"] = summarize_scalp_patterns(result["jev"])
            if include_opening_hour:
                result["opening_hour"] = summarize_opening_hour_focus(result["jev"])

        fingerprint = build_breakout_long_fingerprint(result["features"], result["jev"])
        result["fingerprint"] = {
            "mode": fingerprint.mode,
            "scores": fingerprint.scores(),
            "note": "Synthetic v1 mapping; higher is better on every human-facing axis and values are not calibrated win probabilities.",
        }
        result["visual"] = build_visual_state(
            result["features"],
            flow_persistence=s.flow_persistence,
            jev_response=result["jev"],
            previous_features=previous_features,
        ).to_dict()
        result["signals"] = [
            x.to_dict() for x in build_signals(result["features"], result["jev"])
        ]
        if trade_state is not None:
            result["exit_focus"] = summarize_exit_focus(result["jev"])
            result["exit_focus"]["phase"] = trade_state["phase"]
            result["exit_focus"]["deadline"] = trade_state["clock"]["deadline"]
            result["exit_focus"]["remaining_seconds"] = trade_state["clock"]["remaining_seconds"]
            result["exit_focus"]["gross_pnl_pct"] = trade_state["gross_pnl_pct"]
            result["exit_focus"]["decision_owner"] = "human"
        return result
