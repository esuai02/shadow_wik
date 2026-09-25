import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shadow_wik.bar_features import WINDOW  # noqa: E402
from shadow_wik.engine import ShadowEngine  # noqa: E402
from shadow_wik.trader import LiveTrader, snapshot_from_bars  # noqa: E402

REPORT = {"zones": [], "costs": {"fee_bps_per_side": 1.5, "slippage_bps_per_side": 2.0},
          "exits": {"take_profit_pct": 0.6, "stop_loss_pct": 0.4, "max_hold_seconds": 900, "cooldown_seconds": 60}}


class CountingJev:
    def __init__(self):
        self.calls = []

    def evaluate(self, state, questions):
        self.calls.append(state)
        return {"model": "fake", "answers": {"breakout_next_window": {"type": "noul", "noul": 0.9}}, "usage": {}}


def rising_bars(n):
    base = datetime.fromisoformat("2026-09-23T09:00:00+09:00")
    out, price = [], 10000.0
    for i in range(n):
        price += 40 if i % 3 else -5
        out.append({"time": (base + timedelta(minutes=i)).isoformat(timespec="seconds"),
                    "open": price - 20, "high": price + 5, "low": price - 25, "close": price, "volume": 100 + 30 * i})
    return out


class JevAdvisoryTests(unittest.TestCase):
    def test_default_mode_without_trigger_never_calls_jev_or_trades(self):
        jev = CountingJev()
        with tempfile.TemporaryDirectory() as d:
            trader = LiveTrader("SYN", REPORT, Path(d) / "paper.jsonl", jev=jev)
            bars = rising_bars(WINDOW + 40)
            trader.on_bars(bars[:WINDOW + 5])
            events = trader.on_bars(bars)
        self.assertEqual(trader.paper_mode, "statistical_zone")
        self.assertFalse(any(e["opened"] for e in events))
        self.assertEqual(len(jev.calls), sum(1 for e in events if e["jev_trigger"]))

    def test_trigger_is_rate_limited_and_logged(self):
        # a zone that is always significant triggers every bar; the 10-minute cooldown must thin the calls
        report = {**REPORT, "zones": [{"name": "zone:EDGE>=0", "entry_min": {"EDGE": 0}, "status": "significant"}]}
        jev = CountingJev()
        with tempfile.TemporaryDirectory() as d:
            trader = LiveTrader("SYN", report, Path(d) / "paper.jsonl", jev=jev, jev_log_path=Path(d) / "jev.sqlite")
            bars = rising_bars(WINDOW + 40)
            trader.on_bars(bars[:WINDOW + 5])
            events = trader.on_bars(bars)           # 35 new one-minute bars
            rows = sqlite3.connect(Path(d) / "jev.sqlite").execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        self.assertEqual(len(events), 35)
        self.assertEqual(len(jev.calls), 4)          # minutes 0, 10, 20, 30
        self.assertEqual(rows, 4)
        self.assertTrue(all(e["jev_trigger"] == "significant_zone" for e in events if e["jev_trigger"]))
        self.assertTrue(all(t["pattern"] == "zone:EDGE>=0" for e in events for t in e["opened"]))

    def test_scalp_mode_requires_jev(self):
        with self.assertRaises(ValueError):
            LiveTrader("SYN", REPORT, Path(tempfile.gettempdir()) / "x.jsonl", paper_mode="jev_scalp")


class UnobservedMaskTests(unittest.TestCase):
    def test_unmeasured_inputs_are_sent_as_null(self):
        bars = rising_bars(WINDOW + 1)
        snap = snapshot_from_bars("SYN", bars[-WINDOW:], bars)
        state = ShadowEngine().analyze(snap)["jev_request"]["state"]
        self.assertIsNone(state["microstructure"]["absorption"])
        self.assertIsNone(state["features"]["hidden_flow"])
        self.assertIsNone(state["information"]["news"]["news_novelty"])
        self.assertIsNotNone(state["microstructure"]["volume_anomaly"])     # measured from bars
        self.assertIn("unobserved", state["rules"])


if __name__ == "__main__":
    unittest.main()
