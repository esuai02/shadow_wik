import unittest

from shadow_wik.calibration import ProbabilityCalibrator


class CalibrationTests(unittest.TestCase):
    def test_returns_raw_until_enough_trials(self):
        c = ProbabilityCalibrator(width=0.1)
        c.update(0.72, True)
        self.assertEqual(c.calibrated(0.72, min_trials=20), 0.72)

    def test_calibrates_with_beta_smoothing(self):
        c = ProbabilityCalibrator(width=0.1)
        for i in range(20):
            c.update(0.72, i < 10)
        self.assertAlmostEqual(c.calibrated(0.72, min_trials=20), 11 / 22)


if __name__ == "__main__":
    unittest.main()
