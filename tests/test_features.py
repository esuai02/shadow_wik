import unittest

from shadow_wik.engine import ShadowEngine
from shadow_wik.features import compute_features
from shadow_wik.models import MarketSnapshot


class FeatureTests(unittest.TestCase):
    def test_scores_are_bounded(self):
        snapshot = MarketSnapshot(symbol="X", timestamp="now", volume_anomaly=500, absorption=-20)
        scores = compute_features(snapshot)
        for value in scores.to_dict().values():
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)

    def test_hidden_flow_discounted_by_visible_news(self):
        common = dict(
            symbol="X", timestamp="now", volume_anomaly=90, absorption=90,
            book_imbalance_change=90, institutional_flow=90, sector_confirmation=90,
            derivatives_pressure=80, flow_persistence=90,
        )
        quiet = compute_features(MarketSnapshot(**common, visible_news_strength=0)).hidden_flow
        public = compute_features(MarketSnapshot(**common, visible_news_strength=100)).hidden_flow
        self.assertGreater(quiet, public)

    def test_engine_builds_jev_contract(self):
        result = ShadowEngine().analyze(MarketSnapshot(symbol="X", timestamp="now"))
        questions = result["jev_request"]["questions"]
        self.assertEqual(questions["breakout_next_window"]["type"], "noul")
        self.assertEqual(questions["catalyst_type"]["type"], "choice")
        self.assertEqual(questions["news_risk_level"]["type"], "score")


if __name__ == "__main__":
    unittest.main()
