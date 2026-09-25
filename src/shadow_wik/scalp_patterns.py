from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .paper_trading import PaperTrade, PatternRule
from .zones import one_sided_p


@dataclass(frozen=True, slots=True)
class ScalpPattern:
    key: str
    label: str
    jev_question: str
    thesis: str
    falsification: str
    entry_min: dict[str, float]
    take_profit_pct: float
    stop_loss_pct: float
    max_hold_seconds: int
    cooldown_seconds: int
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCALP_PATTERNS: tuple[ScalpPattern, ...] = (
    ScalpPattern(
        key="opening_range_breakout",
        label="Opening-range breakout",
        jev_question="scalp_opening_range_breakout",
        thesis="Opening range gives way with acceptance, flow support, and continuation rather than an immediate false break.",
        falsification="Breakout is rejected, range is re-entered, or flow/acceptance fails to persist.",
        entry_min={"STRUCTURE": 42.0, "TIMING": 45.0},
        take_profit_pct=0.60,
        stop_loss_pct=0.40,
        max_hold_seconds=900,
        cooldown_seconds=120,
        source_ids=("B-SCALP-ORB-2013", "B-SCALP-ORB-COST-2026"),
    ),
    ScalpPattern(
        key="intraday_momentum",
        label="Intraday momentum continuation",
        jev_question="scalp_intraday_momentum",
        thesis="Early directional move is reinforced by volume/volatility and participant behavior rather than being exhausted.",
        falsification="Directional persistence disappears or evidence shifts toward reversal/mean reversion.",
        entry_min={"EDGE": 40.0, "TIMING": 42.0},
        take_profit_pct=0.50,
        stop_loss_pct=0.35,
        max_hold_seconds=720,
        cooldown_seconds=90,
        source_ids=("B-SCALP-MOM-2018", "B-SCALP-MOM-2019"),
    ),
    ScalpPattern(
        key="order_flow_persistence",
        label="Order-flow persistence",
        jev_question="scalp_order_flow_persistence",
        thesis="Persistent buy-side imbalance/hidden flow is likely to continue exerting short-horizon positive price pressure.",
        falsification="Imbalance dissipates, absorption flips adverse, or price fails to respond despite continued apparent flow.",
        entry_min={"FLOW": 45.0},
        take_profit_pct=0.45,
        stop_loss_pct=0.32,
        max_hold_seconds=600,
        cooldown_seconds=90,
        source_ids=("B-SCALP-OFI-2004", "B-SCALP-OFI-2013", "B-SCALP-OFI-2015"),
    ),
    ScalpPattern(
        key="opening_shock_reversal",
        label="Opening shock reversal",
        jev_question="scalp_opening_shock_reversal",
        thesis="An opening shock/overshoot is more likely to mean-revert than continue after liquidity and participant response are considered.",
        falsification="Flow remains one-sided and structure confirms continuation rather than mean reversion.",
        entry_min={"SAFETY": 30.0},
        take_profit_pct=0.50,
        stop_loss_pct=0.35,
        max_hold_seconds=600,
        cooldown_seconds=120,
        source_ids=("B-SCALP-REV-2019", "B-SCALP-REV-2026"),
    ),
)


def jev_probability_floor(validation_level: int) -> float:
    level = max(0, min(100, int(validation_level)))
    return round(0.50 + 0.004 * level, 4)


def pattern_evidence_strength(trades: Iterable[PaperTrade]) -> dict[str, Any]:
    values = [float(t.net_return_pct) for t in trades if t.net_return_pct is not None]
    n = len(values)
    mean = sum(values) / n if n else 0.0
    p_value = one_sided_p(values) if n >= 2 else 1.0
    if mean <= 0 or n < 2:
        strength = 0.0
    else:
        # Intuitive paper-evidence scale, not a probability:
        # p=.05 ~43 before sample penalty; p=.01 ~67; p<=.001 ~100.
        p_strength = min(100.0, max(0.0, -math.log10(max(p_value, 1e-12)) / 3.0 * 100.0))
        sample_factor = min(1.0, n / 30.0)
        strength = p_strength * sample_factor
    return {
        "trades": n,
        "mean_net_return_pct": round(mean, 6),
        "one_sided_p": round(p_value, 8),
        "strength": round(strength, 2),
    }


def pattern_evidence_by_name(trades: Iterable[PaperTrade]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[PaperTrade]] = {p.key: [] for p in SCALP_PATTERNS}
    for trade in trades:
        if trade.pattern in groups:
            groups[trade.pattern].append(trade)
    return {name: pattern_evidence_strength(group) for name, group in groups.items()}


def build_scalp_rules(validation_level: int = 0) -> list[PatternRule]:
    floor = jev_probability_floor(validation_level)
    return [
        PatternRule(
            name=p.key,
            side="long",
            entry_min=dict(p.entry_min),
            take_profit_pct=p.take_profit_pct,
            stop_loss_pct=p.stop_loss_pct,
            max_hold_seconds=p.max_hold_seconds,
            cooldown_seconds=p.cooldown_seconds,
            jev_question=p.jev_question,
            min_jev_probability=floor,
            hypothesis_status="synthetic_scalp_hypothesis",
            holding_horizon="30m",
        )
        for p in SCALP_PATTERNS
    ]


def pattern_catalog() -> list[dict[str, Any]]:
    return [p.to_dict() for p in SCALP_PATTERNS]
