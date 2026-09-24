import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TradeCliTests(unittest.TestCase):
    def test_open_close_history_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "trades.db"
            opened = subprocess.run(
                [
                    sys.executable,
                    "run.py",
                    "trade-open",
                    "X",
                    "100",
                    "--horizon",
                    "30m",
                    "--entry-time",
                    "2026-09-24T10:00:00+09:00",
                    "--trade-id",
                    "cli-t1",
                    "--db",
                    str(db),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)
            self.assertEqual(json.loads(opened.stdout)["horizon_kind"], "30m")

            closed = subprocess.run(
                [
                    sys.executable,
                    "run.py",
                    "trade-close",
                    "cli-t1",
                    "102",
                    "--exit-time",
                    "2026-09-24T10:20:00+09:00",
                    "--cost-bps",
                    "10",
                    "--db",
                    str(db),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(closed.returncode, 0, closed.stderr)
            row = json.loads(closed.stdout)
            self.assertEqual(row["status"], "closed")
            self.assertEqual(row["success"], 1)
            self.assertAlmostEqual(row["net_return_pct"], 1.9)

            history = subprocess.run(
                [sys.executable, "run.py", "trade-history", "--db", str(db)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(history.returncode, 0, history.stderr)
            rows = json.loads(history.stdout)
            self.assertEqual(rows[0]["trade_id"], "cli-t1")
            self.assertEqual(rows[0]["success_basis"], "auto:net_return>=0%")


if __name__ == "__main__":
    unittest.main()
