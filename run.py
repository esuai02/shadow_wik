from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
STATE = ROOT / ".shadow"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_dotenv(path: Path | None = None) -> None:
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_state() -> None:
    STATE.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str]) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode


def cmd_doctor(_: argparse.Namespace) -> int:
    load_dotenv()
    ensure_state()
    ok = sys.version_info >= (3, 11)
    checks = {
        "python": sys.version.split()[0],
        "python_ok": ok,
        "repo": str(ROOT),
        "src_exists": SRC.exists(),
        "state_dir": str(STATE),
        "jev_key": "configured" if os.getenv("TYPESAFE_API_KEY") else "not configured (dry-run works)",
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if ok and SRC.exists() else 1


def cmd_test(_: argparse.Namespace) -> int:
    return run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])


def _engine_analyze(snapshot_path: Path, live_jev: bool) -> dict[str, Any]:
    load_dotenv()
    from shadow_wik.engine import ShadowEngine
    from shadow_wik.jev import JevClient
    from shadow_wik.models import MarketSnapshot

    snapshot = MarketSnapshot.from_dict(json.loads(snapshot_path.read_text(encoding="utf-8")))
    jev = JevClient.from_env() if live_jev else None
    return ShadowEngine().analyze(snapshot, jev=jev)


def _print_compact_analysis(result: dict[str, Any]) -> None:
    fp = result.get("fingerprint", {}).get("scores", {})
    signals = [item.get("code") for item in result.get("signals", [])]
    print(" ".join(f"{key}={float(value):.1f}" for key, value in fp.items()))
    print("SIGNALS=" + (",".join(signals) if signals else "none"))


def cmd_analyze(args: argparse.Namespace) -> int:
    ensure_state()
    try:
        result = _engine_analyze(args.snapshot, args.jev)
    except Exception as exc:
        print(f"analysis failed: {exc}", file=sys.stderr)
        return 2
    out = STATE / "latest_analysis.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_compact_analysis(result)
    print(f"DETAIL={out}")
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    ensure_state()
    ledger = args.ledger or (STATE / "paper_trades.jsonl")
    return run([
        sys.executable,
        "-m",
        "shadow_wik.paper_cli",
        str(args.frames),
        str(args.patterns),
        "--ledger",
        str(ledger),
        "--fee-bps",
        str(args.fee_bps),
        "--slippage-bps",
        str(args.slippage_bps),
    ])


def cmd_demo(_: argparse.Namespace) -> int:
    ensure_state()
    print("== dry analysis ==")
    analyze_args = argparse.Namespace(
        snapshot=ROOT / "examples" / "sample_snapshot.json",
        jev=False,
    )
    code = cmd_analyze(analyze_args)
    if code != 0:
        return code
    print("== paper replay ==")
    args = argparse.Namespace(
        frames=ROOT / "examples" / "paper_frames.example.jsonl",
        patterns=ROOT / "config" / "patterns.example.json",
        ledger=STATE / "demo_paper_trades.jsonl",
        fee_bps=1.5,
        slippage_bps=2.0,
    )
    if args.ledger.exists():
        args.ledger.unlink()
    return cmd_paper(args)


def _load_rules(path: Path):
    from shadow_wik.paper_trading import PatternRule
    return [PatternRule.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def cmd_stream(args: argparse.Namespace) -> int:
    """Read one JSON object per line from stdin and emit one result per line.

    Input may be either a MarketSnapshot object plus a top-level `price`, or
    {"price": ..., "snapshot": {...}}. This is intentionally feed-agnostic.
    """
    load_dotenv()
    ensure_state()
    from shadow_wik.engine import ShadowEngine
    from shadow_wik.jev import JevClient
    from shadow_wik.models import MarketSnapshot
    from shadow_wik.paper_trading import MarketFrame, PaperTradingHarness

    jev = JevClient.from_env() if args.jev else None
    engine = ShadowEngine()
    paper = None
    if args.patterns:
        paper = PaperTradingHarness(
            _load_rules(args.patterns),
            fee_bps_per_side=args.fee_bps,
            slippage_bps_per_side=args.slippage_bps,
            ledger_path=args.ledger or (STATE / "stream_paper_trades.jsonl"),
        )

    previous_features: dict[str, float] | None = None
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
            price = float(item["price"])
            snapshot_raw = item.get("snapshot") or {k: v for k, v in item.items() if k != "price"}
            snapshot = MarketSnapshot.from_dict(snapshot_raw)
            result = engine.analyze(snapshot, jev=jev, previous_features=previous_features)
            previous_features = result["features"]
            payload: dict[str, Any] = {
                "timestamp": snapshot.timestamp,
                "symbol": snapshot.symbol,
                "price": price,
                "fingerprint": result["fingerprint"]["scores"],
                "signals": [x["code"] for x in result.get("signals", [])],
            }
            if paper is not None:
                frame = MarketFrame.from_analysis(
                    symbol=snapshot.symbol,
                    timestamp=snapshot.timestamp,
                    price=price,
                    analysis=result,
                )
                events = paper.on_frame(frame)
                payload["paper"] = {
                    "opened": [trade.to_dict() for trade in events["opened"]],
                    "closed": [trade.to_dict() for trade in events["closed"]],
                }
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
        except Exception as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False), flush=True)
            if args.strict:
                return 2
    return 0


def cmd_feed_kiwoom(args: argparse.Namespace) -> int:
    """Emit read-only Kiwoom quotes as `stream` input lines on stdout."""
    load_dotenv()
    from shadow_wik.kiwoom_feed import KiwoomFeedError, KiwoomQuoteClient, run_feed

    try:
        run_feed(
            KiwoomQuoteClient.from_env(),
            args.codes,
            interval=args.interval,
            count=args.count,
            emit=lambda line: print(line, flush=True),
        )
    except KiwoomFeedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        pass
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Zero-install local runner for shadow_wik")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("doctor", help="Check local runtime readiness")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("test", help="Run all unit tests")
    sp.set_defaults(func=cmd_test)

    sp = sub.add_parser("analyze", help="Analyze one MarketSnapshot")
    sp.add_argument("snapshot", type=Path, nargs="?", default=ROOT / "examples" / "sample_snapshot.json")
    sp.add_argument("--jev", action="store_true", help="Call live Jev using .env / TYPESAFE_API_KEY")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("paper", help="Replay scored frames through paper trading")
    sp.add_argument("frames", type=Path)
    sp.add_argument("patterns", type=Path, nargs="?", default=ROOT / "config" / "patterns.example.json")
    sp.add_argument("--ledger", type=Path)
    sp.add_argument("--fee-bps", type=float, default=1.5)
    sp.add_argument("--slippage-bps", type=float, default=2.0)
    sp.set_defaults(func=cmd_paper)

    sp = sub.add_parser("demo", help="Run bundled dry-analysis + paper-trading demo")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("stream", help="Process JSONL snapshots from stdin continuously")
    sp.add_argument("--jev", action="store_true")
    sp.add_argument("--patterns", type=Path)
    sp.add_argument("--ledger", type=Path)
    sp.add_argument("--fee-bps", type=float, default=1.5)
    sp.add_argument("--slippage-bps", type=float, default=2.0)
    sp.add_argument("--strict", action="store_true")
    sp.set_defaults(func=cmd_stream)

    sp = sub.add_parser("feed-kiwoom", help="Poll read-only Kiwoom quotes as stream input (pipe into `stream`)")
    sp.add_argument("codes", nargs="+", help="KRX stock codes, e.g. 005930")
    sp.add_argument("--interval", type=float, default=5.0, help="seconds between polls")
    sp.add_argument("--count", type=int, default=0, help="polls per code; 0 = until Ctrl+C")
    sp.set_defaults(func=cmd_feed_kiwoom)
    return p


def main() -> None:
    args = parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
