import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shadow_wik.kiwoom_feed import KiwoomFeedError, KiwoomQuoteClient, parse_bar, US_EASTERN  # noqa: E402
from shadow_wik.notify_telegram import TelegramNotifier, zone_entry_message  # noqa: E402


class UsBarTests(unittest.TestCase):
    def test_us_bar_uses_eastern_time_and_tolerates_extra_digits(self):
        bar = parse_bar({"cntr_tm": "2026092321520000", "open_pric": "190.70", "high_pric": "190.85",
                         "low_pric": "190.70", "cur_prc": "190.77", "trde_qty": "613"}, US_EASTERN)
        self.assertEqual(bar["time"], "2026-09-23T21:52:00-04:00")
        self.assertEqual(bar["close"], 190.77)

    def test_hours_past_midnight_roll_to_next_day(self):
        bar = parse_bar({"cntr_tm": "20260922274400", "open_pric": "1", "high_pric": "1", "low_pric": "1",
                         "cur_prc": "1", "trde_qty": "1"}, US_EASTERN)
        self.assertEqual(bar["time"], "2026-09-23T03:44:00-04:00")

    def test_us_symbol_routes_to_us_chart_and_dedups_pages(self):
        calls = []

        def http(url, headers, body):
            calls.append((url, headers.get("api-id"), body))
            if url.endswith("/oauth2/token"):
                return {"return_code": 0, "token": "T"}, {}
            row = {"cntr_tm": "20260923215200", "open_pric": "1", "high_pric": "1", "low_pric": "1", "cur_prc": "1", "trde_qty": "1"}
            return {"return_code": 0, "result_list": [row]}, {"cont-yn": "Y", "next-key": "k"}

        bars = KiwoomQuoteClient("k", "s", paper=False, http=http).minute_bars("ND:PLTR", pages=2, sleep=lambda _: None)
        self.assertEqual(len(bars), 1)
        chart_calls = [c for c in calls if not c[0].endswith("/oauth2/token")]
        self.assertTrue(all(c[0].endswith("/api/us/chart") and c[1] == "usa06011" for c in chart_calls))
        self.assertEqual(chart_calls[0][2]["stex_tp"], "ND")
        self.assertEqual(chart_calls[0][2]["stk_cd"], "PLTR")

    def test_missing_return_code_is_an_error_and_token_is_retried_once(self):
        tokens = []

        def http(url, headers, body):
            if url.endswith("/oauth2/token"):
                tokens.append(1)
                return {"return_code": 0, "token": "T"}, {}
            return {"error": "Too Many Requests"}, {}

        with self.assertRaises(KiwoomFeedError):
            KiwoomQuoteClient("k", "s", paper=False, http=http).minute_bars("005930", pages=3)
        self.assertEqual(len(tokens), 2)


class TelegramTests(unittest.TestCase):
    def test_token_read_from_file_only_by_key(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("OTHER=x\nTELEGRAM_BOT_TOKEN=abc:123\n")
        env = {"TELEGRAM_TOKEN_FILE": f.name, "TELEGRAM_CHAT_ID": "42", "TELEGRAM_BOT_TOKEN": ""}
        with mock.patch.dict(os.environ, env):
            n = TelegramNotifier.from_env()
        os.unlink(f.name)
        self.assertIsNotNone(n)
        self.assertEqual((n._token, n.chat_id), ("abc:123", "42"))

    def test_disabled_without_chat_id(self):
        with mock.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_TOKEN_FILE": ""}):
            self.assertIsNone(TelegramNotifier.from_env())

    def test_message_mentions_zone_and_disclaimer(self):
        entry = {"timestamp": "2026-09-24T10:00:00-04:00", "price": 190.5, "zone": {"zones": ["zone:EDGE>=60"]}, "opened": [{}]}
        report = {"zones": [{"name": "zone:EDGE>=60", "holdout_n": 12, "holdout_mean_pct": 0.21, "holdout_p": 0.004}]}
        text = zone_entry_message("ND:PLTR", entry, report)
        self.assertIn("ND:PLTR", text)
        self.assertIn("EDGE>=60", text)
        self.assertIn("실주문 아님", text)


if __name__ == "__main__":
    unittest.main()
