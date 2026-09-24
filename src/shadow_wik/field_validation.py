from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .zones import one_sided_p

EVIDENCE_KINDS = {"unverified", "live_real", "paper", "synthetic"}
REQUIRED_AUTOMATION_CONTROLS = (
    "pre_trade_notional_limit",
    "position_limit",
    "daily_loss_limit",
    "order_rate_limit",
    "stale_data_reject",
    "erroneous_order_guard",
    "duplicate_order_guard",
    "kill_switch",
    "paper_live_separation",
    "post_trade_reconciliation",
)
REQUIRED_LIMITS = (
    "max_order_notional",
    "max_position_notional",
    "max_daily_loss",
    "max_orders_per_minute",
)


@dataclass(frozen=True, slots=True)
class FieldProfitabilityPolicy:
    """Initial project policy, not a universal definition of profitable trading."""

    min_trades: int = 30
    min_distinct_days: int = 10
    alpha: float = 0.05
    min_profit_factor: float = 1.20
    max_drawdown_pct: float = 10.0
    max_top_profit_share: float = 0.50


@dataclass(slots=True)
class GateResult:
    status: str
    checks: dict[str, bool]
    metrics: dict[str, Any]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _ordered_live_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    included: list[dict[str, Any]] = []
    excluded = {"not_live_real": 0, "not_closed": 0, "missing_return": 0, "missing_cost": 0}
    for row in rows:
        if row.get("evidence_kind") != "live_real":
            excluded["not_live_real"] += 1
            continue
        if row.get("status") != "closed":
            excluded["not_closed"] += 1
            continue
        if row.get("net_return_pct") is None:
            excluded["missing_return"] += 1
            continue
        if row.get("total_cost_bps") is None:
            excluded["missing_cost"] += 1
            continue
        included.append(dict(row))
    included.sort(key=lambda r: str(r.get("exit_time") or r.get("entry_time") or ""))
    return included, excluded


def _max_drawdown_pct(returns_pct: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns_pct:
        equity *= max(0.0, 1.0 + value / 100.0)
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak * 100.0)
    return worst


def _profit_factor(returns_pct: list[float]) -> tuple[float | None, bool]:
    gains = sum(v for v in returns_pct if v > 0)
    losses = abs(sum(v for v in returns_pct if v < 0))
    if losses == 0:
        return None, gains > 0
    return gains / losses, False


def _top_profit_share(returns_pct: list[float]) -> float:
    positives = [v for v in returns_pct if v > 0]
    total = sum(positives)
    if total <= 0:
        return 1.0
    return max(positives) / total


def evaluate_field_profitability(
    rows: Iterable[dict[str, Any]],
    policy: FieldProfitabilityPolicy = FieldProfitabilityPolicy(),
) -> GateResult:
    sample, excluded = _ordered_live_rows(rows)
    returns = [float(row["net_return_pct"]) for row in sample]
    days = {
        (str(row.get("exit_time") or row.get("entry_time") or "")[:10])
        for row in sample
        if row.get("exit_time") or row.get("entry_time")
    }
    mean = sum(returns) / len(returns) if returns else 0.0
    p_value = one_sided_p(returns) if len(returns) >= 2 else 1.0
    pf, pf_infinite = _profit_factor(returns)
    max_dd = _max_drawdown_pct(returns)
    top_share = _top_profit_share(returns)

    checks = {
        "min_trades": len(sample) >= policy.min_trades,
        "min_distinct_days": len(days) >= policy.min_distinct_days,
        "positive_mean_net_return": mean > 0,
        "one_sided_p": p_value < policy.alpha,
        "profit_factor": pf_infinite or (pf is not None and pf >= policy.min_profit_factor),
        "max_drawdown": max_dd <= policy.max_drawdown_pct,
        "profit_concentration": top_share <= policy.max_top_profit_share,
    }

    reasons: list[str] = []
    if not checks["min_trades"]:
        reasons.append(f"live_real closed trades {len(sample)} < {policy.min_trades}")
    if not checks["min_distinct_days"]:
        reasons.append(f"distinct live trading days {len(days)} < {policy.min_distinct_days}")

    enough_sample = checks["min_trades"] and checks["min_distinct_days"]
    if not enough_sample:
        status = "OPEN"
    else:
        failed = [name for name, passed in checks.items() if not passed]
        status = "PASS" if not failed else "FAIL"
        reasons.extend(f"failed:{name}" for name in failed)

    return GateResult(
        status=status,
        checks=checks,
        metrics={
            "trades": len(sample),
            "distinct_days": len(days),
            "mean_net_return_pct": round(mean, 8),
            "one_sided_p": round(p_value, 10),
            "profit_factor": None if pf is None else round(pf, 8),
            "profit_factor_infinite": pf_infinite,
            "max_drawdown_pct": round(max_dd, 8),
            "top_profit_share": round(top_share, 8),
            "excluded": excluded,
            "policy": asdict(policy),
        },
        reasons=reasons,
    )


def load_evidence(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def _verified_decision(
    records: Iterable[dict[str, Any]],
    decision_id: str,
    *,
    intent_sha256: str,
    graph_revision: int,
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for record in records:
        if record.get("kind") != "decision":
            continue
        if record.get("decision_id") != decision_id:
            continue
        if record.get("value") != "APPROVE" or record.get("origin") != "verified_host_user":
            continue
        scope = record.get("scope") or {}
        if scope.get("intent_sha256") != intent_sha256:
            continue
        if int(scope.get("graph_revision", -1)) != int(graph_revision):
            continue
        matches.append(record)
    return matches[-1] if matches else None


def evaluate_automation_authority(
    profitability: GateResult,
    config: dict[str, Any] | None,
    evidence_records: Iterable[dict[str, Any]],
    *,
    intent_sha256: str,
    graph_revision: int,
) -> GateResult:
    if profitability.status != "PASS":
        return GateResult(
            status="OPEN",
            checks={"profitability_pass": False},
            metrics={"profitability_status": profitability.status},
            reasons=["M8 profitability must PASS before automation authority can PASS"],
        )

    cfg = config or {}
    requested = bool(cfg.get("requested"))
    controls = cfg.get("controls") if isinstance(cfg.get("controls"), dict) else {}
    limits = cfg.get("limits") if isinstance(cfg.get("limits"), dict) else {}
    allowlist = cfg.get("symbol_allowlist") if isinstance(cfg.get("symbol_allowlist"), list) else []

    checks: dict[str, bool] = {
        "profitability_pass": True,
        "requested": requested,
        "mode_live_authorized": cfg.get("mode") == "live_authorized",
        "execution_adapter_verified": bool(cfg.get("execution_adapter_verified")),
        "symbol_allowlist": bool(allowlist),
    }
    for name in REQUIRED_AUTOMATION_CONTROLS:
        checks[f"control:{name}"] = bool(controls.get(name))
    for name in REQUIRED_LIMITS:
        value = limits.get(name)
        checks[f"limit:{name}"] = isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) > 0

    decision = _verified_decision(
        evidence_records,
        "D9_AUTOMATION_AUTHORITY",
        intent_sha256=intent_sha256,
        graph_revision=graph_revision,
    )
    checks["verified_human_authorization"] = decision is not None

    failed = [name for name, passed in checks.items() if not passed]
    if not requested and decision is None:
        status = "OPEN"
    else:
        status = "PASS" if not failed else "FAIL"
    return GateResult(
        status=status,
        checks=checks,
        metrics={
            "mode": cfg.get("mode", "disabled"),
            "symbol_allowlist_count": len(allowlist),
            "human_decision_id": None if decision is None else decision.get("id"),
        },
        reasons=[f"failed:{name}" for name in failed],
    )


def evaluate_closure(
    *,
    technical_pass: bool,
    profitability: GateResult,
    automation: GateResult,
    mode: str,
    evidence_records: Iterable[dict[str, Any]],
    intent_sha256: str,
    graph_revision: int,
) -> dict[str, Any]:
    manual_eligible = technical_pass and profitability.status == "PASS"
    auto_eligible = manual_eligible and automation.status == "PASS"
    selected_eligible = auto_eligible if mode == "auto" else manual_eligible
    decision = _verified_decision(
        evidence_records,
        "D10_DECLARE_COMPLETE",
        intent_sha256=intent_sha256,
        graph_revision=graph_revision,
    )
    return {
        "mode": mode,
        "technical_pass": technical_pass,
        "manual_eligible": manual_eligible,
        "auto_eligible": auto_eligible,
        "selected_eligible": selected_eligible,
        "declared": bool(selected_eligible and decision is not None),
        "declaration_decision_id": None if decision is None else decision.get("id"),
        "status": "DECLARED" if selected_eligible and decision is not None else ("ELIGIBLE" if selected_eligible else "OPEN"),
    }


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
