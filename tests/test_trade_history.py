import tempfile
import unittest
from shadow_wik.trade_history import TradeLedger
from shadow_wik.trade_lifecycle import TradePlan


class TradeHistoryTests(unittest.TestCase):
    def test_open_records_horizon_and_event(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = TradeLedger(f"{d}/trades.db")
            try:
                p = TradePlan("t1", "X", "2026-09-24T10:00:00+09:00", 100, "event", event_name="earnings", event_at="2026-10-01T08:00:00+09:00")
                ledger.open_trade(p)
                row = ledger.get("t1")
                self.assertEqual(row["horizon_kind"], "event")
                self.assertEqual(row["event_name"], "earnings")
                self.assertEqual(row["status"], "open")
            finally:
                ledger.close()

    def test_close_records_return_and_automatic_success(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = TradeLedger(f"{d}/trades.db")
            try:
                p = TradePlan("t1", "X", "2026-09-24T10:00:00+09:00", 100, "1w", success_min_net_return_pct=1.0)
                ledger.open_trade(p)
                row = ledger.close_trade("t1", exit_time="2026-09-25T10:00:00+09:00", exit_price=102, total_cost_bps=10, exit_reason="jev_exit")
                self.assertEqual(row["status"], "closed")
                self.assertAlmostEqual(row["net_return_pct"], 1.9)
                self.assertEqual(row["success"], 1)
                self.assertTrue(row["success_basis"].startswith("auto:"))
            finally:
                ledger.close()

    def test_manual_success_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = TradeLedger(f"{d}/trades.db")
            try:
                ledger.open_trade(TradePlan("t1", "X", "2026-09-24T10:00:00+09:00", 100, "day"))
                row = ledger.close_trade("t1", exit_time="2026-09-24T14:00:00+09:00", exit_price=99, success_override=True)
                self.assertEqual(row["success"], 1)
                self.assertEqual(row["success_basis"], "manual_override")
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
