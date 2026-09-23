import tempfile
import unittest

from shadow_wik.journal import DecisionLedger


class JournalTests(unittest.TestCase):
    def test_record_and_resolve_noul(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            ledger = DecisionLedger(f.name)
            try:
                ids = ledger.record_response(
                    timestamp="t", symbol="X", regime="range", horizon_minutes=15,
                    response={"answers": {"breakout_next_window": {"type": "noul", "noul": 0.72}}},
                )
                ledger.resolve(ids[0], success=True)
                rows = ledger.calibration_rows(question="breakout_next_window", regime="range", horizon_minutes=15)
                self.assertEqual(rows, [(0.72, True)])
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
