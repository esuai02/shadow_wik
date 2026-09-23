import tempfile
import unittest

from shadow_wik.experience_harness import ExperienceHarness, TradeExperience


class ExperienceHarnessTests(unittest.TestCase):
    def _exp(self, n: int, **kw):
        base = dict(
            experience_id=f"e{n}",
            timestamp=f"t{n}",
            symbol="X",
            regime="range",
            setup="prior_high_test",
            system_expectation="breakout",
            realized_outcome="reject",
            user_observation="상단 압력이 실제보다 강하게 느껴졌다.",
            visual_feedback="too_strong",
            focal_cue="resistance_tension",
        )
        base.update(kw)
        return TradeExperience(**base)

    def test_single_recent_experience_never_creates_proposal(self):
        with tempfile.TemporaryDirectory() as d:
            h = ExperienceHarness(f"{d}/exp.jsonl", min_repeats_for_proposal=3)
            a = h.record(self._exp(1))
            self.assertEqual(a.failure_class, "visualization")
            self.assertFalse(a.auto_apply)
            self.assertEqual(h.proposals(), [])

    def test_repeated_same_issue_creates_candidate_only(self):
        with tempfile.TemporaryDirectory() as d:
            h = ExperienceHarness(f"{d}/exp.jsonl", min_repeats_for_proposal=3)
            for n in range(3):
                h.record(self._exp(n))
            p = h.proposals()
            self.assertEqual(len(p), 1)
            self.assertEqual(p[0].status, "candidate_only")
            self.assertEqual(p[0].repeats, 3)

    def test_data_quality_precedes_model_blame(self):
        with tempfile.TemporaryDirectory() as d:
            h = ExperienceHarness(f"{d}/exp.jsonl")
            a = h.assess(self._exp(
                1,
                data_quality_issue=True,
                visual_feedback="aligned",
            ))
            self.assertEqual(a.failure_class, "measurement")


if __name__ == "__main__":
    unittest.main()
