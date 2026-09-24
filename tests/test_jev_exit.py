import unittest
from shadow_wik.jev import build_questions, summarize_exit_focus


class JevExitTests(unittest.TestCase):
    def test_exit_questions_only_when_trade_context_is_present(self):
        self.assertNotIn("exit_action", build_questions())
        qs = build_questions(include_exit=True)
        self.assertEqual(qs["exit_action"]["type"], "choice")
        self.assertEqual(qs["sell_urgency"]["type"], "score")

    def test_final_exit_choice_is_concentrated(self):
        r = {"answers": {
            "exit_action": {"choice": "reduce", "probabilities": {"hold": .2, "reduce": .6, "exit": .2}},
            "exit_driver": {"choice": "time_window"},
            "position_continue_to_horizon": {"noul": .42},
            "original_trade_thesis_intact": {"noul": .7},
            "sell_urgency": {"type": "score", "score": 2.8},
        }}
        out = summarize_exit_focus(r)
        self.assertEqual(out["action"], "reduce")
        self.assertEqual(out["driver"], "time_window")
        self.assertEqual(out["continue_probability"], .42)


if __name__ == "__main__":
    unittest.main()
