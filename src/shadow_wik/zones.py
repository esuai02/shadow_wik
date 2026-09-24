"""Split fingerprint space into statistically significant vs non-significant zones.

A zone is a PatternRule whose entry is `axis >= threshold` on one or two
fingerprint axes (every axis is "higher is better"). Each candidate is traded
virtually through PaperTradingHarness on the older part of the history
(train). Its non-overlapping net returns are tested for mean > 0; the
Benjamini-Hochberg procedure controls false discoveries across all candidates.
A zone is `significant` only if it also shows mean > 0 on the newer, untouched
part of the history (holdout) at p < ALPHA / number of BH survivors. Everything else is
`not_significant` and must not trade.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any, Iterable

from .paper_trading import MarketFrame, PaperTradingHarness, PatternRule

AXES = ("EDGE", "FLOW", "STRUCTURE", "SAFETY", "TIMING")
PERCENTILES = (50, 70, 80, 90)
TRAIN_FRACTION = 0.7
FDR_Q = 0.05
ALPHA = 0.05
MIN_TRAIN_TRADES = 30
MIN_HOLDOUT_TRADES = 10


@dataclass(frozen=True, slots=True)
class CostModel:
    """Per-side costs in bps. KRX sell tax is split evenly across both sides."""
    fee_bps_per_side: float = 1.5 + 10.0
    slippage_bps_per_side: float = 5.0


@dataclass(frozen=True, slots=True)
class ExitModel:
    take_profit_pct: float = 0.6
    stop_loss_pct: float = 0.4
    max_hold_seconds: int = 900
    cooldown_seconds: int = 60


@dataclass(slots=True)
class ZoneStat:
    name: str
    entry_min: dict[str, float]
    train_n: int
    train_mean_pct: float
    train_p: float
    holdout_n: int = 0
    holdout_mean_pct: float = 0.0
    holdout_p: float = 1.0
    status: str = "not_significant"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta (Numerical Recipes 6.4)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def student_t_sf(t: float, df: int) -> float:
    """P(T > t) for Student's t with `df` degrees of freedom."""
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return tail if t >= 0 else 1.0 - tail


def one_sided_p(returns: list[float]) -> float:
    """One-sided one-sample t-test p-value for H1: mean > 0."""
    n = len(returns)
    if n < 2:
        return 1.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return 0.0 if mean > 0 else 1.0
    return student_t_sf(mean / math.sqrt(var / n), n - 1)


def benjamini_hochberg(p_values: dict[str, float], q: float = FDR_Q) -> set[str]:
    ranked = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ranked)
    cutoff = 0
    for i, (_, p) in enumerate(ranked, start=1):
        if p <= q * i / m:
            cutoff = i
    return {name for name, _ in ranked[:cutoff]}


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * pct / 100))]


def candidate_rules(frames: list[MarketFrame], exits: ExitModel = ExitModel()) -> list[PatternRule]:
    varying = [a for a in AXES if len({round(f.scores[a], 2) for f in frames}) > 5]
    levels = {a: sorted({round(_percentile([f.scores[a] for f in frames], p), 2) for p in PERCENTILES}) for a in varying}
    entries: list[dict[str, float]] = [{a: t} for a in varying for t in levels[a]]
    entries += [{a: ta, b: tb} for a, b in combinations(varying, 2) for ta in levels[a] for tb in levels[b]]
    return [
        PatternRule(
            name="zone:" + ",".join(f"{k}>={v:g}" for k, v in entry.items()),
            side="long",
            entry_min=entry,
            hypothesis_status="candidate",
            **asdict(exits),
        )
        for entry in entries
    ]


def replay(frames: Iterable[MarketFrame], rules: list[PatternRule], costs: CostModel = CostModel()) -> PaperTradingHarness:
    """Trade `rules` virtually; open trades are closed at each session's last bar (no overnight gaps)."""
    harness = PaperTradingHarness(rules, fee_bps_per_side=costs.fee_bps_per_side,
                                  slippage_bps_per_side=costs.slippage_bps_per_side)
    previous: MarketFrame | None = None
    for frame in frames:
        if previous is not None and previous.timestamp[:10] != frame.timestamp[:10]:
            harness.close_all(previous)
        harness.on_frame(frame)
        previous = frame
    if previous is not None:
        harness.close_all(previous)
    return harness


def _returns_by_rule(harness: PaperTradingHarness) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for trade in harness.closed_trades:
        out.setdefault(trade.pattern, []).append(float(trade.net_return_pct or 0.0))
    return out


def evaluate_zones(frames: list[MarketFrame], costs: CostModel = CostModel(), exits: ExitModel = ExitModel()) -> dict[str, Any]:
    split = int(len(frames) * TRAIN_FRACTION)
    train, holdout = frames[:split], frames[split:]
    rules = candidate_rules(train, exits)
    train_returns = _returns_by_rule(replay(train, rules, costs))

    stats: dict[str, ZoneStat] = {}
    for rule in rules:
        r = train_returns.get(rule.name, [])
        stats[rule.name] = ZoneStat(rule.name, rule.entry_min, len(r),
                                    sum(r) / len(r) if r else 0.0, one_sided_p(r) if len(r) >= MIN_TRAIN_TRADES else 1.0)
    discovered = benjamini_hochberg({n: s.train_p for n, s in stats.items() if s.train_n >= MIN_TRAIN_TRADES})

    survivors = [rule for rule in rules if rule.name in discovered]
    holdout_returns = _returns_by_rule(replay(holdout, survivors, costs)) if survivors else {}
    holdout_alpha = ALPHA / max(1, len(survivors))
    for name, stat in stats.items():
        if stat.train_n < MIN_TRAIN_TRADES:
            stat.reason = f"train trades {stat.train_n} < {MIN_TRAIN_TRADES}"
            continue
        if name not in discovered:
            stat.reason = f"train p={stat.train_p:.3g} fails BH q={FDR_Q}"
            continue
        r = holdout_returns.get(name, [])
        stat.holdout_n = len(r)
        stat.holdout_mean_pct = sum(r) / len(r) if r else 0.0
        stat.holdout_p = one_sided_p(r) if len(r) >= MIN_HOLDOUT_TRADES else 1.0
        if stat.holdout_n < MIN_HOLDOUT_TRADES:
            stat.reason = f"holdout trades {stat.holdout_n} < {MIN_HOLDOUT_TRADES}"
        elif stat.holdout_p >= holdout_alpha:
            stat.reason = f"holdout p={stat.holdout_p:.3g} >= {holdout_alpha:.3g} (Bonferroni over {len(survivors)})"
        else:
            stat.status = "significant"
            stat.reason = "train BH + holdout confirmed"

    return {
        "train": {"frames": len(train), "from": train[0].timestamp if train else None, "to": train[-1].timestamp if train else None},
        "holdout": {"frames": len(holdout), "from": holdout[0].timestamp if holdout else None, "to": holdout[-1].timestamp if holdout else None},
        "costs": asdict(costs),
        "exits": asdict(exits),
        "method": f"one-sided t-test mean>0; BH q={FDR_Q} on train; holdout p<{ALPHA}/survivors (Bonferroni)",
        "zones": [s.to_dict() for s in sorted(stats.values(), key=lambda s: s.train_p)],
    }


def significant_rules(report: dict[str, Any]) -> list[PatternRule]:
    exits = report["exits"]
    return [
        PatternRule(name=z["name"], side="long", entry_min=z["entry_min"], hypothesis_status="significant", **exits)
        for z in report["zones"] if z["status"] == "significant"
    ]
