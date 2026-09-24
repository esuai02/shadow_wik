import unittest

from shadow_wik.engine import ShadowEngine
from shadow_wik.models import MarketSnapshot
from shadow_wik.trade_lifecycle import TradePlan


class FakeJev:
    def evaluate(self, state, questions):
        self.state = state
        self.questions = questions
        return {
            "answers": {
                "exit_action": {
                    "type": "choice",
                    "choice": "reduce",
                    "probabilities": {"hold": 0.2, "reduce": 0.6, "exit": 0.2},
                },
                "exit_driver": {"type": "choice", "choice": "time_window"},
                "position_continue_to_horizon": {"type": "noul", "noul": 0.42},
                "original_trade_thesis_intact": {"type": "noul", "noul": 0.7},
                "sell_urgency": {"type": "score", "score": 2.8},
            }
        }


class EngineExitTests(unittest.TestCase):
    def test_trade_plan_adds_exit_questions_and_focus(self):
        plan = TradePlan(
            "t1",
            "X",
            "2026-09-24T10:00:00+09:00",
            100,
            "30m",
        )
        jev = FakeJev()
        result = ShadowEngine().analyze(
            MarketSnapshot(symbol="X", timestamp="2026-09-24T10:26:00+09:00"),
            jev=jev,
            trade_plan=plan,
            current_price=102,
        )
        self.assertIn("exit_action", result["jev_request"]["questions"])
        self.assertEqual(result["exit_focus"]["action"], "reduce")
        self.assertEqual(result["exit_focus"]["decision_owner"], "human")
        self.assertEqual(result["trade_state"]["phase"], "exit_window")
        self.assertEqual(jev.state["trade_lifecycle"]["plan"]["trade_id"], "t1")


if __name__ == "__main__":
    unittest.main()
