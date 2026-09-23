from __future__ import annotations

import argparse
import json
from pathlib import Path

from .paper_trading import MarketFrame, PaperTradingHarness, PatternRule


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay scored market frames through pattern-triggered paper trading.")
    parser.add_argument("frames", type=Path, help="JSONL frames: symbol,timestamp,price,scores[,jev_response]")
    parser.add_argument("patterns", type=Path, help="JSON array of PatternRule objects")
    parser.add_argument("--ledger", type=Path, default=Path("paper_trades.jsonl"))
    parser.add_argument("--fee-bps", type=float, default=1.5)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    args = parser.parse_args()

    rules = [PatternRule.from_dict(item) for item in json.loads(args.patterns.read_text(encoding="utf-8"))]
    harness = PaperTradingHarness(
        rules,
        fee_bps_per_side=args.fee_bps,
        slippage_bps_per_side=args.slippage_bps,
        ledger_path=args.ledger,
    )
    last_frame: dict[str, MarketFrame] = {}
    for line in args.frames.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        frame = MarketFrame(**json.loads(line))
        harness.on_frame(frame)
        last_frame[frame.symbol] = frame

    for frame in last_frame.values():
        harness.close_all(frame)

    print(json.dumps([item.to_dict() for item in harness.performance()], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
