import unittest

from shadow_wik.fingerprint import build_breakout_long_fingerprint


class FingerprintTests(unittest.TestCase):
    def base(self):
        return {
            "tpe": 80,
            "breakout_readiness": 82,
            "hidden_flow": 75,
            "range_exit_risk": 78,
            "algorithmic_capture_risk": 30,
            "scheduled_news_risk": 20,
            "unscheduled_news_risk": 25,
            "news_shock_score": 20,
            "reflexive_pressure": 70,
        }

    def test_all_scores_are_higher_is_better_and_bounded(self):
        fp = build_breakout_long_fingerprint(self.base())
        for value in fp.scores().values():
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)

    def test_more_risk_reduces_safety(self):
        safe = build_breakout_long_fingerprint(self.base()).safety
        risky_features = self.base()
        risky_features["unscheduled_news_risk"] = 95
        risky = build_breakout_long_fingerprint(risky_features).safety
        self.assertGreater(safe, risky)

    def test_jev_probability_can_raise_timing_when_supportive(self):
        base = build_breakout_long_fingerprint(self.base()).timing
        jev = {"answers": {
            "breakout_next_window": {"noul": 0.95},
            "range_regime_ending": {"noul": 0.90},
        }}
        with_jev = build_breakout_long_fingerprint(self.base(), jev).timing
        self.assertGreater(with_jev, base)


if __name__ == "__main__":
    unittest.main()
