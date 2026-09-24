import tempfile
import unittest
from pathlib import Path

from shadow_wik.field_validation import (
    FieldProfitabilityPolicy,
    evaluate_automation_authority,
    evaluate_closure,
    evaluate_field_profitability,
)
from shadow_wik.trade_history import TradeLedger
from shadow_wik.trade_lifecycle import TradePlan


INTENT = "intent-hash"
REVISION = 5


def rows(kind="live_real", value=0.2, n=30):
    out = []
    for i in range(n):
        day = i % 10 + 1
        out.append({
            "trade_id": f"t{i}",
            "evidence_kind": kind,
            "status": "closed",
            "entry_time": f"2026-09-{day:02d}T09:00:00+09:00",
            "exit_time": f"2026-09-{day:02d}T10:00:00+09:00",
            "net_return_pct": value,
            "total_cost_bps": 12.0,
        })
    return out


def automation_config():
    return {
        "requested": True,
        "mode": "live_authorized",
        "execution_adapter_verified": True,
        "execution_adapter_path": "src/shadow_wik/execution/live_adapter.py",
        "symbol_allowlist": ["005930"],
        "limits": {
            "max_order_notional": 1000000,
            "max_position_notional": 3000000,
            "max_daily_loss": 100000,
            "max_orders_per_minute": 5,
        },
        "controls": {
            "pre_trade_notional_limit": True,
            "position_limit": True,
            "daily_loss_limit": True,
            "order_rate_limit": True,
            "stale_data_reject": True,
            "erroneous_order_guard": True,
            "duplicate_order_guard": True,
            "kill_switch": True,
            "paper_live_separation": True,
            "post_trade_reconciliation": True,
        },
    }


def decision(decision_id):
    return {
        "id": f"{decision_id}-record",
        "kind": "decision",
        "decision_id": decision_id,
        "value": "APPROVE",
        "origin": "verified_host_user",
        "scope": {"intent_sha256": INTENT, "graph_revision": REVISION},
    }


class FieldProfitabilityTests(unittest.TestCase):
    def test_qualifying_live_real_sample_passes(self):
        result = evaluate_field_profitability(rows())
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.metrics["trades"], 30)
        self.assertTrue(all(result.checks.values()))

    def test_insufficient_sample_is_open(self):
        result = evaluate_field_profitability(rows(n=8))
        self.assertEqual(result.status, "OPEN")
        self.assertFalse(result.checks["min_trades"])

    def test_sufficient_negative_sample_fails(self):
        result = evaluate_field_profitability(rows(value=-0.2))
        self.assertEqual(result.status, "FAIL")
        self.assertFalse(result.checks["positive_mean_net_return"])

    def test_paper_and_synthetic_do_not_count(self):
        sample = rows(kind="paper") + rows(kind="synthetic")
        result = evaluate_field_profitability(sample)
        self.assertEqual(result.status, "OPEN")
        self.assertEqual(result.metrics["trades"], 0)
        self.assertEqual(result.metrics["excluded"]["not_live_real"], 60)

    def test_missing_cost_is_excluded(self):
        sample = rows()
        sample[0]["total_cost_bps"] = None
        result = evaluate_field_profitability(sample)
        self.assertEqual(result.status, "OPEN")
        self.assertEqual(result.metrics["trades"], 29)
        self.assertEqual(result.metrics["excluded"]["missing_cost"], 1)


class AutomationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.profit = evaluate_field_profitability(rows())

    def test_config_alone_cannot_authorize(self):
        result = evaluate_automation_authority(
            self.profit,
            automation_config(),
            [],
            intent_sha256=INTENT,
            graph_revision=REVISION,
            adapter_path_exists=True,
        )
        self.assertEqual(result.status, "FAIL")
        self.assertFalse(result.checks["verified_human_authorization"])

    def test_verified_current_scope_decision_can_pass_complete_contract(self):
        result = evaluate_automation_authority(
            self.profit,
            automation_config(),
            [decision("D9_AUTOMATION_AUTHORITY")],
            intent_sha256=INTENT,
            graph_revision=REVISION,
            adapter_path_exists=True,
        )
        self.assertEqual(result.status, "PASS")
        self.assertTrue(all(result.checks.values()))

    def test_stale_decision_does_not_authorize(self):
        record = decision("D9_AUTOMATION_AUTHORITY")
        record["scope"]["graph_revision"] = 4
        result = evaluate_automation_authority(
            self.profit,
            automation_config(),
            [record],
            intent_sha256=INTENT,
            graph_revision=REVISION,
            adapter_path_exists=True,
        )
        self.assertEqual(result.status, "FAIL")

    def test_automation_cannot_pass_before_profitability(self):
        open_profit = evaluate_field_profitability(rows(n=5))
        result = evaluate_automation_authority(
            open_profit,
            automation_config(),
            [decision("D9_AUTOMATION_AUTHORITY")],
            intent_sha256=INTENT,
            graph_revision=REVISION,
            adapter_path_exists=True,
        )
        self.assertEqual(result.status, "OPEN")


class ClosureTests(unittest.TestCase):
    def test_manual_route_becomes_eligible_after_profitability(self):
        profit = evaluate_field_profitability(rows())
        auto = evaluate_automation_authority(
            profit, None, [], intent_sha256=INTENT, graph_revision=REVISION
        )
        result = evaluate_closure(
            technical_pass=True,
            profitability=profit,
            automation=auto,
            mode="manual",
            evidence_records=[],
            intent_sha256=INTENT,
            graph_revision=REVISION,
        )
        self.assertTrue(result["manual_eligible"])
        self.assertEqual(result["status"], "ELIGIBLE")
        self.assertFalse(result["declared"])

    def test_final_declaration_requires_current_human_decision(self):
        profit = evaluate_field_profitability(rows())
        auto = evaluate_automation_authority(
            profit, None, [], intent_sha256=INTENT, graph_revision=REVISION
        )
        result = evaluate_closure(
            technical_pass=True,
            profitability=profit,
            automation=auto,
            mode="manual",
            evidence_records=[decision("D10_DECLARE_COMPLETE")],
            intent_sha256=INTENT,
            graph_revision=REVISION,
        )
        self.assertEqual(result["status"], "DECLARED")
        self.assertTrue(result["declared"])


class TradeLedgerEvidenceTests(unittest.TestCase):
    def test_ledger_persists_evidence_kind_and_cost(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trades.db"
            ledger = TradeLedger(path)
            try:
                plan = TradePlan("r1", "X", "2026-09-01T09:00:00+09:00", 100, "day")
                ledger.open_trade(plan, evidence_kind="live_real")
                row = ledger.close_trade(
                    "r1",
                    exit_time="2026-09-01T10:00:00+09:00",
                    exit_price=101,
                    total_cost_bps=12,
                )
            finally:
                ledger.close()
            self.assertEqual(row["evidence_kind"], "live_real")
            self.assertEqual(row["total_cost_bps"], 12)


if __name__ == "__main__":
    unittest.main()
