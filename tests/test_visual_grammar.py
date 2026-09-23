import unittest

from shadow_wik.visual_grammar import build_visual_state


class VisualGrammarTests(unittest.TestCase):
    def _features(self):
        return {
            "tpe": 80,
            "breakout_readiness": 75,
            "hidden_flow": 70,
            "range_exit_risk": 65,
            "news_shock_score": 20,
            "reflexive_pressure": 60,
        }

    def test_inferred_and_derived_are_distinct(self):
        state = build_visual_state(self._features(), flow_persistence=80)
        styles = {cue.key: cue.evidence_style for cue in state.cues}
        self.assertEqual(styles["trend_pressure"], "derived")
        self.assertEqual(styles["hidden_flow"], "inferred")

    def test_velocity_uses_previous_state(self):
        previous = dict(self._features())
        previous["tpe"] = 60
        state = build_visual_state(self._features(), previous_features=previous)
        cue = next(c for c in state.cues if c.key == "trend_pressure")
        self.assertEqual(cue.velocity, 20)

    def test_jev_unknown_increases_uncertainty(self):
        jev = {"answers": {"catalyst_type": {"probabilities": {
            "hidden_flow": 0.35, "unknown": 0.55, "visible_news": 0.1
        }}}}
        state = build_visual_state(self._features(), jev_response=jev)
        self.assertEqual(state.uncertainty, 55)


if __name__ == "__main__":
    unittest.main()
