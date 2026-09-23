import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LocalRuntimeTests(unittest.TestCase):
    def test_doctor_runs_without_install(self):
        result = subprocess.run(
            [sys.executable, "run.py", "doctor"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["python_ok"])
        self.assertTrue(payload["src_exists"])

    def test_demo_runs_end_to_end_without_jev(self):
        result = subprocess.run(
            [sys.executable, "run.py", "demo"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EDGE=", result.stdout)
        self.assertIn("average_return_pct", result.stdout)


if __name__ == "__main__":
    unittest.main()
