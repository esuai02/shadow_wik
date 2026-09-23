from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(slots=True)
class VisualCue:
    key: str
    intensity: float
    velocity: float
    stability: float
    evidence_style: str
    meaning: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["intensity"] = round(self.intensity, 2)
        data["velocity"] = round(self.velocity, 2)
        data["stability"] = round(self.stability, 2)
        return data


@dataclass(slots=True)
class VisualState:
    cues: list[VisualCue]
    uncertainty: float
    dominant_cue: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cues": [cue.to_dict() for cue in self.cues],
            "uncertainty": round(self.uncertainty, 2),
            "dominant_cue": self.dominant_cue,
        }


def _delta(current: float, previous: dict[str, float] | None, key: str) -> float:
    if previous is None or key not in previous:
        return 0.0
    return max(-100.0, min(100.0, current - float(previous[key])))


def build_visual_state(
    features: dict[str, float],
    *,
    flow_persistence: float = 50.0,
    jev_response: dict[str, Any] | None = None,
    previous_features: dict[str, float] | None = None,
) -> VisualState:
    """Map analysis state into a stable sensory grammar.

    Deterministic derived features are visually distinct from model probability.
    Hidden flow remains an inference even when its score is high.
    """
    required = {
        "tpe", "breakout_readiness", "hidden_flow", "range_exit_risk",
        "news_shock_score", "reflexive_pressure",
    }
    missing = sorted(required - set(features))
    if missing:
        raise ValueError(f"missing visual features: {', '.join(missing)}")

    cue_specs = [
        ("trend_pressure", "tpe", "derived", "누적 추세 압력"),
        ("resistance_tension", "breakout_readiness", "derived", "저항 부근 돌파 준비도"),
        ("hidden_flow", "hidden_flow", "inferred", "보이는 뉴스로 설명되지 않는 수급 압력"),
        ("range_instability", "range_exit_risk", "derived", "횡보 레짐의 불안정성"),
        ("news_shock", "news_shock_score", "derived", "현재 정보 충격"),
        ("reflexive_pressure", "reflexive_pressure", "inferred", "포지션 피드백에 의한 자기증폭 압력"),
    ]

    cues: list[VisualCue] = []
    for cue_key, feature_key, style, meaning in cue_specs:
        value = _clamp(features[feature_key])
        cues.append(VisualCue(
            key=cue_key,
            intensity=value,
            velocity=_delta(value, previous_features, feature_key),
            stability=_clamp(flow_persistence),
            evidence_style=style,
            meaning=meaning,
        ))

    uncertainty = 50.0
    if jev_response:
        catalyst = jev_response.get("answers", {}).get("catalyst_type", {})
        probabilities = catalyst.get("probabilities", {})
        if isinstance(probabilities, dict) and probabilities:
            max_p = max(float(v) for v in probabilities.values())
            unknown_p = float(probabilities.get("unknown", 0.0))
            uncertainty = round(_clamp(max(unknown_p, 1.0 - max_p) * 100.0), 8)
            cues.append(VisualCue(
                key="jev_catalyst_confidence",
                intensity=_clamp(max_p * 100.0),
                velocity=0.0,
                stability=_clamp(flow_persistence),
                evidence_style="model_probability",
                meaning="Jev 촉매 분류의 현재 확률 집중도",
            ))

    dominant = max(cues, key=lambda cue: cue.intensity).key if cues else "none"
    return VisualState(cues=cues, uncertainty=uncertainty, dominant_cue=dominant)
