import unittest

from shadow_wik.paper_trading import MarketFrame, PaperTradingHarness, PatternRule


class PaperTradingTests(unittest.TestCase):
    def setUp(self):
        self.rule = PatternRule(
            name="p1",
            side="long",
            entry_min={"EDGE": 70, "TIMING": 70},
            exit_below={"EDGE": 45},
            take_profit_pct=1.0,
            stop_loss_pct=0.7,
            max_hold_seconds=60,
            cooldown_seconds=0,
        )
        self.h = PaperTradingHarness([self.rule], fee_bps_per_side=1, slippage_bps_per_side=2)

    def frame(self, sec, price, edge=80, timing=80):
        return MarketFrame(
            symbol="X",
            timestamp=f"2026-09-24T10:00:{sec:02d}+09:00",
            price=price,
            scores={"EDGE": edge, "TIMING": timing},
        )

    def test_opens_only_when_pattern_matches(self):
        self.assertEqual(self.h.on_frame(self.frame(0, 100, edge=60))["opened"], [])
        opened = self.h.on_frame(self.frame(1, 100))["opened"]
        self.assertEqual(len(opened), 1)
        self.assertGreater(opened[0].entry_price, 100)

    def test_take_profit_closes_with_positive_net_return(self):
        self.h.on_frame(self.frame(0, 100))
        result = self.h.on_frame(self.frame(10, 101.5))
        self.assertEqual(result["closed"][0].close_reason, "take_profit")
        self.assertGreater(result["closed"][0].net_return_pct, 0)

    def test_stop_loss_closes_negative(self):
        self.h.on_frame(self.frame(0, 100))
        result = self.h.on_frame(self.frame(10, 99.0))
        self.assertEqual(result["closed"][0].close_reason, "stop_loss")
        self.assertLess(result["closed"][0].net_return_pct, 0)

    def test_pattern_invalidation_closes(self):
        self.h.on_frame(self.frame(0, 100))
        result = self.h.on_frame(self.frame(10, 100.1, edge=40))
        self.assertEqual(result["closed"][0].close_reason, "pattern_invalidation")

    def test_max_hold_closes(self):
        self.h.on_frame(self.frame(0, 100))
        result = self.h.on_frame(MarketFrame(
            symbol="X",
            timestamp="2026-09-24T10:01:00+09:00",
            price=100.1,
            scores={"EDGE": 80, "TIMING": 80},
        ))
        self.assertEqual(result["closed"][0].close_reason, "max_hold")

    def test_costs_are_reflected(self):
        self.h.on_frame(self.frame(0, 100))
        trade = self.h.close_all(self.frame(10, 100))[0]
        self.assertLess(trade.net_return_pct, 0)

    def test_performance_groups_closed_trades(self):
        self.h.on_frame(self.frame(0, 100))
        self.h.on_frame(self.frame(10, 101.5))
        stats = self.h.performance("p1")[0]
        self.assertEqual(stats.trades, 1)
        self.assertEqual(stats.wins, 1)
        self.assertGreater(stats.average_return_pct, 0)

    def test_frame_can_be_built_from_engine_analysis(self):
        analysis = {
            "fingerprint": {"scores": {"EDGE": 80, "TIMING": 77}},
            "jev": {"answers": {}},
        }
        frame = MarketFrame.from_analysis(
            symbol="X",
            timestamp="2026-09-24T10:00:00+09:00",
            price=100,
            analysis=analysis,
        )
        self.assertEqual(frame.scores["EDGE"], 80)
        self.assertEqual(frame.jev_response, analysis["jev"])

    def test_jev_gate_is_optional_but_enforced_when_configured(self):
        rule = PatternRule(
            name="jev",
            side="long",
            entry_min={"EDGE": 70},
            jev_question="breakout_next_window",
            min_jev_probability=0.7,
        )
        h = PaperTradingHarness([rule])
        no_jev = MarketFrame("X", "2026-09-24T10:00:00+09:00", 100, {"EDGE": 80})
        self.assertEqual(h.on_frame(no_jev)["opened"], [])
        yes_jev = MarketFrame(
            "X", "2026-09-24T10:00:01+09:00", 100, {"EDGE": 80},
            {"answers": {"breakout_next_window": {"noul": 0.75}}},
        )
        self.assertEqual(len(h.on_frame(yes_jev)["opened"]), 1)


if __name__ == "__main__":
    unittest.main()
