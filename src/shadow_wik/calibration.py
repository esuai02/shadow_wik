from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CalibrationBin:
    lower: float
    upper: float
    successes: int = 0
    trials: int = 0

    @property
    def empirical_rate(self) -> float | None:
        if self.trials == 0:
            return None
        return self.successes / self.trials


class ProbabilityCalibrator:
    """Simple bucket calibration with Beta(1,1) shrinkage for small samples."""

    def __init__(self, width: float = 0.1) -> None:
        if not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        self.width = width
        count = round(1 / width)
        self.bins = [CalibrationBin(i * width, min(1.0, (i + 1) * width)) for i in range(count)]

    def _bin(self, p: float) -> CalibrationBin:
        p = min(1.0, max(0.0, p))
        index = min(int(p / self.width), len(self.bins) - 1)
        return self.bins[index]

    def update(self, raw_probability: float, success: bool) -> None:
        bucket = self._bin(raw_probability)
        bucket.trials += 1
        bucket.successes += int(success)

    def calibrated(self, raw_probability: float, min_trials: int = 20) -> float:
        bucket = self._bin(raw_probability)
        if bucket.trials < min_trials:
            return raw_probability
        return (bucket.successes + 1) / (bucket.trials + 2)
