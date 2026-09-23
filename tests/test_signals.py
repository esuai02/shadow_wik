import unittest

from shadow_wik.signals import build_signals


class SignalTests(unittest.TestCase):
    def test_breakout_confluence_signal(self):
        features = {
            "algorithmic_capture_risk": 20,
            "scheduled_news_risk": 20,
            "unscheduled_news_risk": 20,
            "range_exit_risk": 75,
            "tpe": 80,
            "breakout_readiness": 85,
        }
        jev = {"answers": {
            "breakout_next_window": {"type": "noul", "noul": 0.76},
            "range_regime_ending": {"type": "noul", "noul": 0.68},
        }}
        codes = [s.code for s in build_signals(features, jev)]
        self.assertIn("JEV_BREAKOUT_CONFLUENCE", codes)
        self.assertIn("RANGE_EXIT_WATCH", codes)


if __name__ == "__main__":
    unittest.main()
