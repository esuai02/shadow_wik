import unittest

from shadow_wik.jev import build_questions, summarize_opening_hour_focus


class OpeningHourJevTests(unittest.TestCase):
    def test_opening_hour_questions_are_bounded(self):
        q = build_questions(include_opening_hour=True)
        self.assertEqual(set(q["opening_hour_stance"]["criteria"]), {"buy_state", "sell_state"})
        self.assertEqual(set(q["buy_state_action"]["criteria"]), {"hold", "reduce", "exit"})
        self.assertEqual(set(q["sell_state_action"]["criteria"]), {"enter", "wait", "observe_today"})
        self.assertIn("fomo_risk", q)
        self.assertIn("falling_knife_risk", q)
        self.assertIn("objectivity_risk", q)

    def test_summary_preserves_current_state(self):
        response = {"answers": {
            "opening_hour_stance": {"type": "choice", "choice": "sell_state", "probabilities": {"buy_state": 0.25, "sell_state": 0.75}},
            "opening_hour_flow": {"type": "choice", "choice": "downtrend"},
            "buy_state_action": {"type": "choice", "choice": "exit"},
            "sell_state_action": {"type": "choice", "choice": "observe_today"},
            "fomo_risk": {"type": "score", "score": 20},
            "falling_knife_risk": {"type": "score", "score": 80},
            "objectivity_risk": {"type": "score", "score": 30},
        }}
        out = summarize_opening_hour_focus(response)
        self.assertEqual(out["stance"], "sell_state")
        self.assertEqual(out["sell_action"], "observe_today")
        self.assertEqual(out["flow"], "downtrend")


if __name__ == "__main__":
    unittest.main()
