import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shadow_wik.jev import build_questions, summarize_scalp_patterns
from shadow_wik.paper_portfolio import PaperPortfolio
from shadow_wik.paper_trading import MarketFrame, PaperTrade, PaperTradingHarness, PatternRule
from shadow_wik.trader import LiveTrader
from shadow_wik.scalp_patterns import (
    SCALP_PATTERNS,
    build_scalp_rules,
    jev_probability_floor,
    pattern_evidence_strength,
)


def trade(ret: float, i: int = 0) -> PaperTrade:
    return PaperTrade(
        trade_id=f"t{i}",
        pattern="intraday_momentum",
        symbol="X",
        side="long",
        entry_time=f"2026-09-25T09:{i:02d}:00+09:00",
        entry_raw_price=100.0,
        entry_price=100.0,
        entry_scores={},
        hypothesis_status="synthetic_scalp_hypothesis",
        holding_horizon="30m",
        exit_time=f"2026-09-25T09:{i+1:02d}:00+09:00",
        exit_raw_price=100.0 * (1 + ret / 100),
        exit_price=100.0 * (1 + ret / 100),
        net_return_pct=ret,
    )


class JevScalpQuestionsTests(unittest.TestCase):
    def test_scalp_questions_are_opt_in(self):
        self.assertNotIn("scalp_intraday_momentum", build_questions())
        qs = build_questions(include_scalp=True)
        self.assertEqual(qs["scalp_intraday_momentum"]["type"], "noul")
        self.assertEqual(len([k for k in qs if k.startswith("scalp_")]), len(SCALP_PATTERNS))

    def test_raw_pattern_probabilities_are_extracted(self):
        response = {"answers": {
            "scalp_intraday_momentum": {"noul": 0.73},
            "scalp_order_flow_persistence": {"noul": 0.61},
        }}
        out = summarize_scalp_patterns(response)
        self.assertEqual(out["intraday_momentum"], 0.73)
        self.assertEqual(out["order_flow_persistence"], 0.61)


class PatternGateTests(unittest.TestCase):
    def test_default_zero_is_exploration_with_50pct_jev_floor(self):
        rules = build_scalp_rules(0)
        self.assertEqual(jev_probability_floor(0), 0.5)
        self.assertTrue(all(r.min_jev_probability == 0.5 for r in rules))

    def test_slider_raises_jev_floor(self):
        self.assertEqual(jev_probability_floor(100), 0.9)
        self.assertGreater(jev_probability_floor(75), jev_probability_floor(25))

    def test_positive_repeated_paper_returns_raise_evidence_strength(self):
        weak = pattern_evidence_strength([trade(0.2, i) for i in range(3)])
        strong = pattern_evidence_strength([trade(0.2, i) for i in range(30)])
        self.assertGreater(strong["strength"], weak["strength"])
        self.assertGreater(strong["strength"], 0)

    def test_negative_history_has_zero_strength(self):
        result = pattern_evidence_strength([trade(-0.2, i) for i in range(30)])
        self.assertEqual(result["strength"], 0)


class PortfolioTests(unittest.TestCase):
    def test_seed_is_100m_and_ten_10pct_positions_exhaust_cash_without_leverage(self):
        portfolio = PaperPortfolio()
        rule = PatternRule("p", "long", {})
        reservations = []
        for i in range(10):
            frame = MarketFrame(f"X{i}", f"2026-09-25T09:{i:02d}:00+09:00", 100.0, {})
            reservations.append(portfolio.reserve(rule, frame))
        self.assertTrue(all(reservations))
        self.assertFalse(portfolio.reserve(rule, MarketFrame("X10", "2026-09-25T09:11:00+09:00", 100.0, {})))
        self.assertEqual(portfolio.state()["cash_krw"], 0)
        self.assertEqual(portfolio.state()["seed_krw"], 100_000_000)

    def test_close_books_net_pnl_against_allocated_notional(self):
        portfolio = PaperPortfolio()
        rule = PatternRule("p", "long", {})
        frame = MarketFrame("X", "2026-09-25T09:00:00+09:00", 100.0, {})
        self.assertTrue(portfolio.reserve(rule, frame))
        opened = PaperTrade(
            trade_id="paper-1", pattern="p", symbol="X", side="long",
            entry_time=frame.timestamp, entry_raw_price=100, entry_price=100,
            entry_scores={}, hypothesis_status="synthetic", holding_horizon="30m",
        )
        portfolio.confirm_open(opened)
        opened.net_return_pct = 1.0
        portfolio.close(opened)
        state = portfolio.state()
        self.assertEqual(state["realized_pnl_krw"], 100_000)
        self.assertEqual(state["equity_krw"], 100_100_000)

    def test_harness_respects_portfolio_open_guard(self):
        rule = PatternRule("p", "long", {"EDGE": 1})
        harness = PaperTradingHarness([rule])
        frame = MarketFrame("X", "2026-09-25T09:00:00+09:00", 100.0, {"EDGE": 100})
        result = harness.on_frame(frame, allow_open=lambda _rule, _frame: False)
        self.assertEqual(result["opened"], [])


class FakeJev:
    def evaluate(self, _state, questions):
        answers = {}
        for key, spec in questions.items():
            if key.startswith("scalp_"):
                answers[key] = {"noul": 0.95}
            elif spec.get("type") == "noul":
                answers[key] = {"noul": 0.7}
        return {"answers": answers}


def trending_bars(n: int):
    base = datetime(2026, 9, 25, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    price = 10000.0
    out = []
    for i in range(n):
        price += 20
        out.append({
            "time": (base + timedelta(minutes=i)).isoformat(timespec="seconds"),
            "open": price - 20,
            "high": price + 10,
            "low": price - 30,
            "close": price,
            "volume": 1000 + i * 50,
        })
    return out


class LiveScalpIntegrationTests(unittest.TestCase):
    def test_low_default_threshold_can_open_paper_pattern_with_jev(self):
        report = {
            "zones": [],
            "costs": {"fee_bps_per_side": 1.5, "slippage_bps_per_side": 2.0},
            "exits": {"take_profit_pct": 0.6, "stop_loss_pct": 0.4, "max_hold_seconds": 900, "cooldown_seconds": 60},
        }
        with tempfile.TemporaryDirectory() as d:
            trader = LiveTrader("005930", report, Path(d) / "paper.jsonl", jev=FakeJev())
            history = trending_bars(45)
            first_now = datetime.fromisoformat(history[-3]["time"]) + timedelta(minutes=2)
            trader.on_bars(history[:-2], now=first_now)
            second_now = datetime.fromisoformat(history[-1]["time"]) + timedelta(minutes=2)
            events = trader.on_bars(history, now=second_now)
            self.assertEqual(trader.paper_mode, "jev_scalp")
            self.assertEqual(trader.validation_level, 0)
            self.assertTrue(any(e["patterns"] for e in events))
            self.assertTrue(trader.state()["open_trades"])
            self.assertLess(trader.portfolio.state()["cash_krw"], 100_000_000)


if __name__ == "__main__":
    unittest.main()
