import unittest
from shadow_wik.trade_lifecycle import TradePlan, build_trade_clock, build_trade_state


class TradeLifecycleTests(unittest.TestCase):
    def test_30m_horizon_opens_exit_window_near_deadline(self):
        p = TradePlan("t1", "X", "2026-09-24T10:00:00+09:00", 100, "30m")
        early = build_trade_clock(p, "2026-09-24T10:20:00+09:00")
        late = build_trade_clock(p, "2026-09-24T10:26:00+09:00")
        self.assertFalse(early.exit_window_open)
        self.assertTrue(late.exit_window_open)
        self.assertEqual(late.deadline, "2026-09-24T10:30:00+09:00")

    def test_event_horizon_requires_named_event_and_time(self):
        with self.assertRaises(ValueError):
            TradePlan("t1", "X", "2026-09-24T10:00:00+09:00", 100, "event")
        p = TradePlan("t2", "X", "2026-09-24T10:00:00+09:00", 100, "event", event_name="earnings", event_at="2026-10-01T08:00:00+09:00")
        self.assertEqual(p.deadline().isoformat(), "2026-10-01T08:00:00+09:00")

    def test_trade_state_concentrates_horizon_and_current_pnl(self):
        p = TradePlan("t1", "X", "2026-09-24T10:00:00+09:00", 100, "3d")
        s = build_trade_state(p, now="2026-09-25T10:00:00+09:00", current_price=105)
        self.assertAlmostEqual(s["gross_pnl_pct"], 5.0)
        self.assertEqual(s["plan"]["horizon_kind"], "3d")
        self.assertEqual(s["final_decision_owner"], "human")


if __name__ == "__main__":
    unittest.main()
