import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseCheckTests(unittest.TestCase):
    def test_release_contract_is_self_consistent(self):
        result = subprocess.run(
            [sys.executable, "scripts/release_check.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["real_order_markers"], [])


if __name__ == "__main__":
    unittest.main()
