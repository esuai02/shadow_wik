from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .features import compute_features
from .jev import JevClient, build_questions
from .models import MarketSnapshot
from .personas import infer_market_persona_clusters, infer_position_personas
from .signals import build_signals
from .visual_grammar import build_visual_state


class ShadowEngine:
    def analyze(
        self,
        snapshot: MarketSnapshot,
        jev: JevClient | None = None,
        previous_features: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        s = snapshot.normalized()
        features = compute_features(s)
        market_personas = infer_market_persona_clusters(s, features)
        position_personas = infer_position_personas(s, features)

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
            },
        }

        result: dict[str, Any] = {
            "snapshot": s.to_dict(),
            "features": features.to_dict(),
            "position_personas": [p.to_dict() for p in position_personas],
            "market_personas": [p.to_dict() for p in market_personas],
            "jev_request": {"state": jev_state, "questions": build_questions()},
            "jev": None,
        }
        if jev is not None:
            result["jev"] = jev.evaluate(jev_state, build_questions())

        result["visual"] = build_visual_state(
            result["features"],
            flow_persistence=s.flow_persistence,
            jev_response=result["jev"],
            previous_features=previous_features,
        ).to_dict()
        result["signals"] = [
            x.to_dict() for x in build_signals(result["features"], result["jev"])
        ]
        return result
