from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import ShadowEngine
from .jev import JevClient, JevError
from .models import MarketSnapshot
from .journal import DecisionLedger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a market snapshot and optionally query Jev.")
    parser.add_argument("snapshot", type=Path, help="Path to snapshot JSON")
    parser.add_argument("--live-jev", action="store_true", help="Call TypeSafe Jev using TYPESAFE_API_KEY")
    parser.add_argument("--compact", action="store_true", help="Compact JSON output")
    parser.add_argument("--ledger", type=Path, help="SQLite path for recording live Jev decisions")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raw = json.loads(args.snapshot.read_text(encoding="utf-8"))
    snapshot = MarketSnapshot.from_dict(raw)
    jev = None
    if args.live_jev:
        try:
            jev = JevClient.from_env()
        except JevError as exc:
            raise SystemExit(str(exc)) from exc
    result = ShadowEngine().analyze(snapshot, jev=jev)
    if args.ledger and result.get("jev"):
        ledger = DecisionLedger(args.ledger)
        try:
            result["ledger_decision_ids"] = ledger.record_response(
                timestamp=snapshot.timestamp,
                symbol=snapshot.symbol,
                regime=snapshot.regime_hint,
                horizon_minutes=snapshot.horizon_minutes,
                response=result["jev"],
            )
        finally:
            ledger.close()
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
