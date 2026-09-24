import unittest
from shadow_wik.paper_trading import MarketFrame, PaperTradingHarness, PatternRule


class PaperLifecycleTests(unittest.TestCase):
    def test_horizon_and_success_are_recorded(self):
        h = PaperTradingHarness([PatternRule("p", "long", {"EDGE": 70}, take_profit_pct=.5, holding_horizon="day")], fee_bps_per_side=0, slippage_bps_per_side=0)
        h.on_frame(MarketFrame("X", "2026-09-24T10:00:00+09:00", 100, {"EDGE": 80}))
        t = h.on_frame(MarketFrame("X", "2026-09-24T10:00:10+09:00", 101, {"EDGE": 80}))["closed"][0]
        self.assertEqual(t.holding_horizon, "day")
        self.assertTrue(t.success)

    def test_short_return_is_not_overstated(self):
        h = PaperTradingHarness([PatternRule("p", "short", {"EDGE": 70}, take_profit_pct=9, stop_loss_pct=20)], fee_bps_per_side=0, slippage_bps_per_side=0)
        h.on_frame(MarketFrame("X", "2026-09-24T10:00:00+09:00", 100, {"EDGE": 80}))
        t = h.on_frame(MarketFrame("X", "2026-09-24T10:00:10+09:00", 90, {"EDGE": 80}))["closed"][0]
        self.assertAlmostEqual(t.gross_return_pct, 10.0)


if __name__ == "__main__":
    unittest.main()
