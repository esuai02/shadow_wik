from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
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


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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


def _engine_analyze(
    snapshot_path: Path,
    live_jev: bool,
    *,
    trade_plan=None,
    current_price: float | None = None,
) -> dict[str, Any]:
    load_dotenv()
    from shadow_wik.engine import ShadowEngine
    from shadow_wik.jev import JevClient
    from shadow_wik.models import MarketSnapshot

    snapshot = MarketSnapshot.from_dict(json.loads(snapshot_path.read_text(encoding="utf-8")))
    jev = JevClient.from_env() if live_jev else None
    return ShadowEngine().analyze(
        snapshot,
        jev=jev,
        trade_plan=trade_plan,
        current_price=current_price,
    )


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
    code = cmd_analyze(
        argparse.Namespace(
            snapshot=ROOT / "examples" / "sample_snapshot.json",
            jev=False,
        )
    )
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

    return [
        PatternRule.from_dict(item)
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def _trade_db(path: Path | None) -> Path:
    ensure_state()
    return path or (STATE / "trades.db")


def _entry_context_for(symbol: str) -> dict[str, Any]:
    path = STATE / "latest_analysis.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if data.get("snapshot", {}).get("symbol") != symbol:
        return {}
    return {
        "fingerprint": data.get("fingerprint"),
        "signals": data.get("signals"),
        "features": data.get("features"),
    }


def cmd_trade_open(args: argparse.Namespace) -> int:
    ensure_state()
    from shadow_wik.trade_history import TradeLedger
    from shadow_wik.trade_lifecycle import TradePlan

    trade_id = args.trade_id or f"{args.symbol}-{uuid.uuid4().hex[:10]}"
    plan = TradePlan(
        trade_id=trade_id,
        symbol=args.symbol,
        entry_time=args.entry_time or now_iso(),
        entry_price=args.price,
        horizon_kind=args.horizon,
        planned_exit_at=args.planned_exit_at,
        event_name=args.event_name,
        event_at=args.event_at,
        thesis=args.thesis or "",
        success_min_net_return_pct=args.success_min_return,
    )
    ledger = TradeLedger(_trade_db(args.db))
    try:
        ledger.open_trade(
            plan,
            entry_context=_entry_context_for(args.symbol),
            evidence_kind=args.evidence_kind,
        )
    finally:
        ledger.close()
    payload = plan.to_dict()
    payload["deadline"] = plan.deadline().isoformat()
    payload["status"] = "open"
    payload["evidence_kind"] = args.evidence_kind
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_trade_analyze(args: argparse.Namespace) -> int:
    ensure_state()
    load_dotenv()
    from shadow_wik.engine import ShadowEngine
    from shadow_wik.jev import JevClient
    from shadow_wik.models import MarketSnapshot
    from shadow_wik.trade_history import TradeLedger

    ledger = TradeLedger(_trade_db(args.db))
    try:
        plan = ledger.get_plan(args.trade_id)
    finally:
        ledger.close()

    raw = json.loads(args.snapshot.read_text(encoding="utf-8"))
    raw["symbol"] = plan.symbol
    raw["timestamp"] = args.timestamp or raw.get("timestamp") or now_iso()
    snapshot = MarketSnapshot.from_dict(raw)
    jev = JevClient.from_env() if args.jev else None
    result = ShadowEngine().analyze(
        snapshot,
        jev=jev,
        trade_plan=plan,
        current_price=args.price,
    )
    out = STATE / "latest_exit_analysis.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    focus = result["exit_focus"]
    print(f"TRADE={plan.trade_id} HORIZON={plan.horizon_kind} PHASE={focus['phase']}")
    print(f"PNL={focus['gross_pnl_pct']:.2f}% REMAINING_SECONDS={focus['remaining_seconds']:.0f}")
    print(f"JEV_ACTION={focus.get('action') or 'UNMEASURED'} DRIVER={focus.get('driver') or 'UNMEASURED'}")
    print(f"DETAIL={out}")
    return 0


def _latest_exit_for_trade(trade_id: str) -> dict[str, Any] | None:
    path = STATE / "latest_exit_analysis.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("trade_state", {}).get("plan", {}).get("trade_id") != trade_id:
        return None
    return data


def cmd_trade_close(args: argparse.Namespace) -> int:
    ensure_state()
    from shadow_wik.trade_history import TradeLedger

    latest = _latest_exit_for_trade(args.trade_id)
    focus = (latest or {}).get("exit_focus", {})
    success_override = None if args.success == "auto" else args.success == "yes"

    ledger = TradeLedger(_trade_db(args.db))
    try:
        row = ledger.close_trade(
            args.trade_id,
            exit_time=args.exit_time or now_iso(),
            exit_price=args.price,
            total_cost_bps=args.cost_bps,
            exit_reason=args.reason or focus.get("driver") or "manual",
            final_exit_action=focus.get("action") or "exit",
            exit_context=(latest or {}).get("trade_state"),
            jev_exit=(latest or {}).get("jev"),
            success_override=success_override,
            note=args.note,
        )
    finally:
        ledger.close()
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def cmd_trade_history(args: argparse.Namespace) -> int:
    from shadow_wik.trade_history import TradeLedger

    ledger = TradeLedger(_trade_db(args.db))
    try:
        rows = ledger.history(symbol=args.symbol, limit=args.limit)
    finally:
        ledger.close()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_field_gate(args: argparse.Namespace) -> int:
    ensure_state()
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "field_gate.py"),
        "--db",
        str(args.db or _trade_db(None)),
        "--mode",
        args.mode,
    ]
    if args.automation_config:
        cmd.extend(["--automation-config", str(args.automation_config)])
    if args.require_eligible:
        cmd.append("--require-eligible")
    return run(cmd)


def cmd_stream(args: argparse.Namespace) -> int:
    load_dotenv()
    ensure_state()
    from shadow_wik.engine import ShadowEngine
    from shadow_wik.jev import JevClient
    from shadow_wik.models import MarketSnapshot
    from shadow_wik.paper_trading import MarketFrame, PaperTradingHarness
    from shadow_wik.trade_history import TradeLedger

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

    trade_plan = None
    if args.trade_id:
        ledger = TradeLedger(_trade_db(args.trade_db))
        try:
            trade_plan = ledger.get_plan(args.trade_id)
        finally:
            ledger.close()

    previous_features: dict[str, float] | None = None
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
            price = float(item["price"])
            snapshot_raw = item.get("snapshot") or {
                k: v for k, v in item.items() if k != "price"
            }
            snapshot = MarketSnapshot.from_dict(snapshot_raw)
            result = engine.analyze(
                snapshot,
                jev=jev,
                previous_features=previous_features,
                trade_plan=trade_plan,
                current_price=price if trade_plan else None,
            )
            previous_features = result["features"]
            payload: dict[str, Any] = {
                "timestamp": snapshot.timestamp,
                "symbol": snapshot.symbol,
                "price": price,
                "fingerprint": result["fingerprint"]["scores"],
                "signals": [x["code"] for x in result.get("signals", [])],
            }
            if trade_plan is not None:
                payload["trade_state"] = result["trade_state"]
                payload["exit_focus"] = result["exit_focus"]
                (STATE / "latest_exit_analysis.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
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
            print(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                flush=True,
            )
        except Exception as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False), flush=True)
            if args.strict:
                return 2
    return 0


def cmd_feed_kiwoom(args: argparse.Namespace) -> int:
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


# Per-side cost assumptions (bps). KRX: 1.5 fee + half of the ~0.20 % sell tax.
# US: conservative online commission; set --fee-bps to your actual Kiwoom rate.
DEFAULT_COSTS = {"kr": (11.5, 5.0), "us": (10.0, 3.0)}


def _costs(code: str, args: argparse.Namespace):
    from shadow_wik.zones import CostModel

    fee, slip = DEFAULT_COSTS["us" if ":" in code else "kr"]
    return CostModel(fee_bps_per_side=args.fee_bps if args.fee_bps is not None else fee,
                     slippage_bps_per_side=args.slippage_bps if args.slippage_bps is not None else slip)


def _zone_report(client, code: str, args: argparse.Namespace, rebuild: bool) -> dict[str, Any]:
    from shadow_wik.trader import build_report, save_json

    path = STATE / f"zones_{code.replace(':', '_')}.json"
    if path.exists() and not rebuild:
        return json.loads(path.read_text(encoding="utf-8"))
    bars = client.minute_bars(code, pages=args.pages)
    report = build_report(code, bars, _costs(code, args))
    save_json(path, report)
    return report


def cmd_zones(args: argparse.Namespace) -> int:
    """Rebuild significance zones from Kiwoom minute-bar history."""
    load_dotenv()
    ensure_state()
    from shadow_wik.kiwoom_feed import KiwoomFeedError, KiwoomQuoteClient

    try:
        client = KiwoomQuoteClient.from_env()
        for code in args.codes:
            report = _zone_report(client, code, args, rebuild=True)
            sig = [z["name"] for z in report["zones"] if z["status"] == "significant"]
            print(json.dumps({"symbol": code, "bars": report["bars"], "candidates": len(report["zones"]),
                              "significant": sig}, ensure_ascii=False))
    except KiwoomFeedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """Local paper-trading UI; trades virtually only inside significant zones."""
    load_dotenv()
    ensure_state()
    from shadow_wik.jev import JevClient
    from shadow_wik.kiwoom_feed import KiwoomFeedError, KiwoomQuoteClient
    from shadow_wik.notify_telegram import TelegramError, TelegramNotifier
    from shadow_wik.webui.server import Runtime, serve

    try:
        client = KiwoomQuoteClient.from_env()
        reports = {code: _zone_report(client, code, args, rebuild=False) for code in args.codes}
    except KiwoomFeedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    jev = JevClient.from_env() if os.getenv("TYPESAFE_API_KEY") else None
    try:
        notifier = TelegramNotifier.from_env()
    except TelegramError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"telegram alerts: {'on' if notifier else 'off (TELEGRAM_CHAT_ID / token not set)'}", flush=True)
    serve(Runtime(client, reports, STATE, args.interval, jev=jev, notifier=notifier), args.port)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Zero-install local runner for shadow_wik")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("doctor")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("test")
    sp.set_defaults(func=cmd_test)

    sp = sub.add_parser("analyze")
    sp.add_argument(
        "snapshot",
        type=Path,
        nargs="?",
        default=ROOT / "examples" / "sample_snapshot.json",
    )
    sp.add_argument("--jev", action="store_true")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("paper")
    sp.add_argument("frames", type=Path)
    sp.add_argument(
        "patterns",
        type=Path,
        nargs="?",
        default=ROOT / "config" / "patterns.example.json",
    )
    sp.add_argument("--ledger", type=Path)
    sp.add_argument("--fee-bps", type=float, default=1.5)
    sp.add_argument("--slippage-bps", type=float, default=2.0)
    sp.set_defaults(func=cmd_paper)

    sp = sub.add_parser("demo")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser(
        "trade-open",
        help="Record a buy and precommit its sell horizon",
    )
    sp.add_argument("symbol")
    sp.add_argument("price", type=float)
    sp.add_argument(
        "--horizon",
        required=True,
        choices=["30m", "day", "3d", "1w", "1m", "3m", "6m", "event"],
    )
    sp.add_argument("--trade-id")
    sp.add_argument("--entry-time")
    sp.add_argument("--planned-exit-at")
    sp.add_argument("--event-name")
    sp.add_argument("--event-at")
    sp.add_argument("--thesis")
    sp.add_argument("--success-min-return", type=float, default=0.0)
    sp.add_argument(
        "--evidence-kind",
        choices=["unverified", "live_real", "paper", "synthetic"],
        default="unverified",
        help="Only live_real trades can count toward the field-profitability gate",
    )
    sp.add_argument("--db", type=Path)
    sp.set_defaults(func=cmd_trade_open)

    sp = sub.add_parser(
        "trade-analyze",
        help="Concentrate live state into a sell-side Jev decision",
    )
    sp.add_argument("trade_id")
    sp.add_argument("price", type=float)
    sp.add_argument(
        "snapshot",
        type=Path,
        nargs="?",
        default=ROOT / "examples" / "sample_snapshot.json",
    )
    sp.add_argument("--timestamp")
    sp.add_argument("--jev", action="store_true")
    sp.add_argument("--db", type=Path)
    sp.set_defaults(func=cmd_trade_analyze)

    sp = sub.add_parser(
        "trade-close",
        help="Record the sell and success/failure verdict",
    )
    sp.add_argument("trade_id")
    sp.add_argument("price", type=float)
    sp.add_argument("--exit-time")
    sp.add_argument("--cost-bps", type=float, default=0.0)
    sp.add_argument("--reason")
    sp.add_argument(
        "--success",
        choices=["auto", "yes", "no"],
        default="auto",
    )
    sp.add_argument("--note")
    sp.add_argument("--db", type=Path)
    sp.set_defaults(func=cmd_trade_close)

    sp = sub.add_parser(
        "trade-history",
        help="Show buy-to-sell lifecycle records",
    )
    sp.add_argument("--symbol")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--db", type=Path)
    sp.set_defaults(func=cmd_trade_history)

    sp = sub.add_parser(
        "field-gate",
        help="Evaluate real profitability, automation authority and closure eligibility",
    )
    sp.add_argument("--db", type=Path)
    sp.add_argument("--mode", choices=["manual", "auto"], default="manual")
    sp.add_argument("--automation-config", type=Path)
    sp.add_argument("--require-eligible", action="store_true")
    sp.set_defaults(func=cmd_field_gate)

    sp = sub.add_parser(
        "stream",
        help="Process JSONL snapshots continuously",
    )
    sp.add_argument("--jev", action="store_true")
    sp.add_argument("--patterns", type=Path)
    sp.add_argument("--ledger", type=Path)
    sp.add_argument("--fee-bps", type=float, default=1.5)
    sp.add_argument("--slippage-bps", type=float, default=2.0)
    sp.add_argument("--strict", action="store_true")
    sp.add_argument(
        "--trade-id",
        help="Attach an open trade and emit sell-side horizon/Jev focus every frame",
    )
    sp.add_argument("--trade-db", type=Path)
    sp.set_defaults(func=cmd_stream)

    sp = sub.add_parser(
        "feed-kiwoom",
        help="Poll read-only Kiwoom quotes as stream input",
    )
    sp.add_argument("codes", nargs="+")
    sp.add_argument("--interval", type=float, default=5.0)
    sp.add_argument("--count", type=int, default=0)
    sp.set_defaults(func=cmd_feed_kiwoom)

    sp = sub.add_parser("zones", help="Rebuild statistically significant zones from Kiwoom minute-bar history")
    sp.add_argument("codes", nargs="+", help="KRX code (005930) or US EXCHANGE:TICKER (ND:PLTR)")
    sp.add_argument("--pages", type=int, default=40, help="pages of history (KRX 900 bars/page, US 100 bars/page)")
    sp.add_argument("--fee-bps", type=float, help="per-side fee+tax bps (default KRX 11.5, US 10)")
    sp.add_argument("--slippage-bps", type=float, help="per-side slippage bps (default KRX 5, US 3)")
    sp.set_defaults(func=cmd_zones)

    sp = sub.add_parser("ui", help="Local paper-trading UI (127.0.0.1); trades only in significant zones")
    sp.add_argument("codes", nargs="+")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--interval", type=float, default=60.0, help="seconds between minute-bar polls")
    sp.add_argument("--pages", type=int, default=40, help="history pages if no saved zone report")
    sp.add_argument("--fee-bps", type=float)
    sp.add_argument("--slippage-bps", type=float)
    sp.set_defaults(func=cmd_ui)
    return p


def main() -> None:
    args = parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
