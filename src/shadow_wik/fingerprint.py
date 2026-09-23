from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _weighted(items: list[tuple[float, float]]) -> float:
    total = sum(weight for _, weight in items)
    if total <= 0:
        return 0.0
    return _clamp(sum(_clamp(value) * weight for value, weight in items) / total)


@dataclass(slots=True)
class MarketFingerprint:
    edge: float
    flow: float
    structure: float
    safety: float
    timing: float
    mode: str = "breakout_long_v1"

    def to_dict(self) -> dict[str, float | str]:
        data = asdict(self)
        for key in ("edge", "flow", "structure", "safety", "timing"):
            data[key] = round(float(data[key]), 2)
        return data

    def scores(self) -> dict[str, float]:
        return {
            "EDGE": round(self.edge, 2),
            "FLOW": round(self.flow, 2),
            "STRUCTURE": round(self.structure, 2),
            "SAFETY": round(self.safety, 2),
            "TIMING": round(self.timing, 2),
        }


def _jev_probability(jev_response: dict[str, Any] | None, question: str) -> float | None:
    if not jev_response:
        return None
    answer = jev_response.get("answers", {}).get(question, {})
    value = answer.get("noul")
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return None


def build_breakout_long_fingerprint(
    features: dict[str, float],
    jev_response: dict[str, Any] | None = None,
) -> MarketFingerprint:
    """Create five human-facing scores where higher is always better.

    This is a synthetic v1 mapping for calibration, not a validated profitability model.
    Raw Jev probability is only one input and is never presented as realized win rate.
    """
    required = {
        "tpe",
        "breakout_readiness",
        "hidden_flow",
        "range_exit_risk",
        "algorithmic_capture_risk",
        "scheduled_news_risk",
        "unscheduled_news_risk",
        "news_shock_score",
        "reflexive_pressure",
    }
    missing = sorted(required - set(features))
    if missing:
        raise ValueError(f"missing fingerprint features: {', '.join(missing)}")

    structure = _weighted([
        (features["tpe"], 40),
        (features["breakout_readiness"], 35),
        (features["range_exit_risk"], 25),
    ])
    flow = _weighted([
        (features["hidden_flow"], 60),
        (features["reflexive_pressure"], 40),
    ])
    safety = 100.0 - _weighted([
        (features["scheduled_news_risk"], 25),
        (features["unscheduled_news_risk"], 30),
        (features["news_shock_score"], 20),
        (features["algorithmic_capture_risk"], 25),
    ])

    breakout_p = _jev_probability(jev_response, "breakout_next_window")
    regime_p = _jev_probability(jev_response, "range_regime_ending")
    probability_score = None
    if breakout_p is not None or regime_p is not None:
        available: list[tuple[float, float]] = []
        if breakout_p is not None:
            available.append((breakout_p * 100.0, 70))
        if regime_p is not None:
            available.append((regime_p * 100.0, 30))
        probability_score = _weighted(available)

    timing_items = [
        (features["breakout_readiness"], 55),
        (features["reflexive_pressure"], 20),
        (features["range_exit_risk"], 25),
    ]
    if probability_score is not None:
        timing_items = [
            (features["breakout_readiness"], 40),
            (features["reflexive_pressure"], 15),
            (features["range_exit_risk"], 20),
            (probability_score, 25),
        ]
    timing = _weighted(timing_items)

    edge_items = [
        (structure, 35),
        (flow, 25),
        (safety, 15),
        (timing, 25),
    ]
    if probability_score is not None:
        edge_items = [
            (structure, 30),
            (flow, 20),
            (safety, 15),
            (timing, 20),
            (probability_score, 15),
        ]
    edge = _weighted(edge_items)

    return MarketFingerprint(
        edge=edge,
        flow=flow,
        structure=structure,
        safety=safety,
        timing=timing,
    )
