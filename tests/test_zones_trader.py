import random
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shadow_wik.bar_features import WINDOW, measure  # noqa: E402
from shadow_wik.paper_trading import MarketFrame  # noqa: E402
from shadow_wik.trader import LiveTrader, zone_status  # noqa: E402
from shadow_wik.zones import CostModel, benjamini_hochberg, evaluate_zones, one_sided_p, student_t_sf  # noqa: E402

KST = timezone(timedelta(hours=9))
AXES = ("EDGE", "FLOW", "STRUCTURE", "SAFETY", "TIMING")


def synthetic_frames(edge: bool, days: int = 60, per_day: int = 300, seed: int = 7,
                     drift: float = -0.0005) -> list[MarketFrame]:
    """Scores are random; price drifts by `drift` per bar. With edge=True, EDGE >= 88 is followed by a ~+1.2% move."""
    rng = random.Random(seed)
    frames: list[MarketFrame] = []
    for d in range(days):
        start = datetime(2026, 1, 5, 9, 0, tzinfo=KST) + timedelta(days=d)
        price, boost = 100.0, 0
        for m in range(per_day):
            scores = {a: rng.uniform(20, 95) for a in AXES}
            if boost:
                price *= 1.003
                boost -= 1
            else:
                price *= 1 + rng.gauss(drift, 0.0008)
            if edge and scores["EDGE"] >= 88 and not boost:
                boost = 4
            frames.append(MarketFrame("SYN", (start + timedelta(minutes=m)).isoformat(), price, scores))
    return frames


class StatsTests(unittest.TestCase):
    def test_one_sided_p_direction(self):
        self.assertLess(one_sided_p([0.5, 0.6, 0.4, 0.55] * 10), 0.01)
        self.assertGreater(one_sided_p([-0.5, -0.6, -0.4, -0.55] * 10), 0.99)

    def test_student_t_matches_table(self):
        self.assertAlmostEqual(student_t_sf(2.262, 9), 0.025, places=3)
        self.assertAlmostEqual(student_t_sf(1.70, 9), 0.0617, places=3)

    def test_benjamini_hochberg_step_up(self):
        passed = benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}, q=0.05)
        self.assertEqual(passed, {"a", "b"})


class ZoneTests(unittest.TestCase):
    def test_planted_edge_is_found_significant(self):
        report = evaluate_zones(synthetic_frames(edge=True))
        sig = [z for z in report["zones"] if z["status"] == "significant"]
        self.assertTrue(sig, "planted EDGE signal should yield a significant zone")
        self.assertTrue(all("EDGE" in z["entry_min"] for z in sig))

    def test_null_market_without_costs_yields_no_significant_zone(self):
        # type-I check: zero drift, zero costs, scores unrelated to price
        for seed in range(5):
            report = evaluate_zones(synthetic_frames(edge=False, seed=seed, drift=0.0), CostModel(0.0, 0.0))
            self.assertFalse([z["name"] for z in report["zones"] if z["status"] == "significant"], f"seed {seed}")

    def test_zone_status_matches_only_significant(self):
        report = {"zones": [
            {"name": "z1", "entry_min": {"EDGE": 70}, "status": "significant"},
            {"name": "z2", "entry_min": {"FLOW": 10}, "status": "not_significant"},
        ]}
        self.assertEqual(zone_status({"EDGE": 75, "FLOW": 90}, report), {"significant": True, "zones": ["z1"]})
        self.assertFalse(zone_status({"EDGE": 60, "FLOW": 90}, report)["significant"])


def bars(n: int, day: str = "2026-09-23", step: float = 10.0) -> list[dict]:
    base = datetime.fromisoformat(f"{day}T09:00:00+09:00")
    out, price = [], 10000.0
    for i in range(n):
        price += step
        out.append({"time": (base + timedelta(minutes=i)).isoformat(timespec="seconds"),
                    "open": price - step, "high": price + 5, "low": price - step - 5, "close": price, "volume": 100 + i})
    return out


class CompletedBarTests(unittest.TestCase):
    def test_forming_bar_is_dropped(self):
        from shadow_wik.trader import completed
        b = bars(3)
        now = datetime.fromisoformat(b[-1]["time"]) + timedelta(seconds=30)
        self.assertEqual([x["time"] for x in completed(b, now)], [x["time"] for x in b[:-1]])


class SessionFilterTests(unittest.TestCase):
    def test_krx_keeps_only_regular_continuous_session(self):
        from shadow_wik.trader import session_bars
        times = ["08:59", "09:00", "15:19", "15:20", "15:30", "16:00"]
        b = [{"time": f"2026-09-23T{t}:00+09:00"} for t in times]
        self.assertEqual([x["time"][11:16] for x in session_bars("005930", b)], ["09:00", "15:19"])
        self.assertEqual(len(session_bars("ND:PLTR", b)), len(b))


class BarFeatureTests(unittest.TestCase):
    def test_uptrend_measures_high(self):
        b = bars(WINDOW + 5)
        m = measure(b[-WINDOW:], b)
        self.assertEqual(m["trend_persistence"], 100)
        self.assertGreater(m["impulse_retention"], 90)
        self.assertEqual(m["vwap_hold"], 100)

    def test_requires_full_window(self):
        with self.assertRaises(ValueError):
            measure(bars(WINDOW - 1), bars(WINDOW - 1))


class LiveTraderTests(unittest.TestCase):
    def test_first_call_warms_up_without_trading(self):
        report = {"zones": [], "costs": {"fee_bps_per_side": 1.5, "slippage_bps_per_side": 2.0}, "exits": {"take_profit_pct": 0.6, "stop_loss_pct": 0.4, "max_hold_seconds": 900, "cooldown_seconds": 60}}
        trader = LiveTrader("SYN", report, ROOT / ".shadow" / "test_live_paper.jsonl")
        history = bars(WINDOW + 10)
        warm = trader.on_bars(history[:-2])
        self.assertTrue(warm and all(e["warmup"] for e in warm))
        fresh = trader.on_bars(history)
        self.assertEqual([e["timestamp"] for e in fresh], [b["time"] for b in history[-2:]])
        self.assertFalse(any(e["warmup"] for e in fresh))
        self.assertEqual(trader.state()["significant_zone_count"], 0)
        self.assertFalse(trader.state()["open_trades"])


if __name__ == "__main__":
    unittest.main()
