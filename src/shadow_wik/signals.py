from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class Signal:
    code: str
    severity: str
    rationale: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def build_signals(features: dict[str, float], jev_response: dict[str, Any] | None) -> list[Signal]:
    out: list[Signal] = []

    if features["algorithmic_capture_risk"] >= 70:
        out.append(Signal("ZERO_POINT_RESET", "high", "Recent evidence/positioning may be reinforcing the thesis; re-check independent counterevidence."))
    if features["scheduled_news_risk"] >= 70 or features["unscheduled_news_risk"] >= 75:
        out.append(Signal("NEWS_RISK", "high", "Position structure is vulnerable to scheduled or surprise information."))
    if features["range_exit_risk"] >= 70:
        out.append(Signal("RANGE_EXIT_WATCH", "medium", "Mean-reversion assumptions are becoming less reliable; treat the range persona as provisional."))
    if features["tpe"] >= 70 and features["breakout_readiness"] >= 75:
        out.append(Signal("STRUCTURAL_BREAKOUT_WATCH", "medium", "Stored trend energy and near-resistance readiness are jointly elevated."))

    if jev_response:
        answers = jev_response.get("answers", {})
        breakout = answers.get("breakout_next_window", {}).get("noul")
        range_end = answers.get("range_regime_ending", {}).get("noul")
        scenario = answers.get("next_scenario", {})
        if isinstance(breakout, (int, float)) and isinstance(range_end, (int, float)):
            if breakout >= 0.70 and range_end >= 0.60:
                out.append(Signal("JEV_BREAKOUT_CONFLUENCE", "medium", "Jev raw probabilities favor both breakout and range-regime transition; calibration is still required."))
        if scenario.get("choice") == "false_break_return_range" and scenario.get("confidence", 0) >= 0.65:
            out.append(Signal("FALSE_BREAK_RISK", "medium", "Jev currently favors a false break and return to range."))

    if not out:
        out.append(Signal("NO_EDGE", "low", "No configured evidence threshold is currently strong enough for an advisory signal."))
    return out
