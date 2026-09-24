import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shadow_wik.kiwoom_feed import (  # noqa: E402
    MOCK_HOST,
    REAL_HOST,
    KiwoomFeedError,
    KiwoomQuoteClient,
    parse_price,
    run_feed,
)


class FakeHttp:
    def __init__(self, quote=None, token_res=None):
        self.calls = []
        self.quote = quote or {"return_code": 0, "stk_nm": "삼성전자", "cur_prc": "-70100", "flu_rt": "-0.85", "trde_qty": "123"}
        self.token_res = token_res or {"return_code": 0, "token": "T"}

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, body))
        return self.token_res if url.endswith("/oauth2/token") else self.quote


class KiwoomFeedTests(unittest.TestCase):
    def test_parse_price_strips_direction_sign(self):
        self.assertEqual(parse_price("-70100"), 70100.0)
        self.assertEqual(parse_price("+1,234"), 1234.0)
        with self.assertRaises(KiwoomFeedError):
            parse_price("")

    def test_host_follows_paper_flag(self):
        self.assertEqual(KiwoomQuoteClient("k", "s", paper=True).host, MOCK_HOST)
        self.assertEqual(KiwoomQuoteClient("k", "s", paper=False).host, REAL_HOST)

    def test_feed_reuses_token_and_uses_quote_api_only(self):
        http = FakeHttp()
        lines = []
        run_feed(KiwoomQuoteClient("k", "s", paper=True, http=http), ["005930"], interval=0, count=2,
                 emit=lines.append, sleep=lambda _: None)
        urls = [c[0] for c in http.calls]
        self.assertEqual(sum(u.endswith("/oauth2/token") for u in urls), 1)
        self.assertTrue(all(u.endswith(("/oauth2/token", "/api/dostk/stkinfo")) for u in urls))
        line = json.loads(lines[0])
        self.assertEqual(line["price"], 70100.0)
        self.assertEqual(line["snapshot"]["symbol"], "005930")

    def test_error_code_raises_with_message(self):
        http = FakeHttp(token_res={"return_code": 3, "return_msg": "IP not registered"})
        with self.assertRaisesRegex(KiwoomFeedError, "IP not registered"):
            KiwoomQuoteClient("k", "s", paper=True, http=http).quote("005930")

    def test_feed_line_is_accepted_by_stream(self):
        lines = []
        run_feed(KiwoomQuoteClient("k", "s", paper=True, http=FakeHttp()), ["005930"], interval=0, count=1,
                 emit=lines.append, sleep=lambda _: None)
        result = subprocess.run([sys.executable, "run.py", "stream"], cwd=ROOT, input=lines[0] + "\n",
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout.strip())
        self.assertNotIn("error", out)
        self.assertEqual(out["price"], 70100.0)


if __name__ == "__main__":
    unittest.main()
