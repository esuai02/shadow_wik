from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from shadow_wik.field_validation import (  # noqa: E402
    evaluate_automation_authority,
    evaluate_closure,
    evaluate_field_profitability,
    load_evidence,
)
from shadow_wik.trade_history import TradeLedger  # noqa: E402


def _technical_pass() -> tuple[bool, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release_check.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"status": "FAIL", "error": proc.stdout or proc.stderr}
    return proc.returncode == 0 and payload.get("status") == "PASS", payload


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    ledger = TradeLedger(path)
    try:
        return ledger.history(limit=100000)
    finally:
        ledger.close()


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("automation config must be a JSON object")
    return value


def main() -> int:
    p = argparse.ArgumentParser(description="Evaluate field profitability, automation authority and closure eligibility.")
    p.add_argument("--db", type=Path, default=ROOT / ".shadow" / "trades.db")
    p.add_argument("--evidence", type=Path, default=ROOT / "evidence.jsonl")
    p.add_argument("--automation-config", type=Path, default=ROOT / ".shadow" / "automation_authority.json")
    p.add_argument("--mode", choices=["manual", "auto"], default="manual")
    p.add_argument("--require-eligible", action="store_true")
    args = p.parse_args()

    graph = json.loads((ROOT / "graph.json").read_text(encoding="utf-8"))
    technical_pass, technical = _technical_pass()
    evidence = load_evidence(args.evidence)
    rows = _load_rows(args.db)
    profitability = evaluate_field_profitability(rows)
    automation_config = _load_json(args.automation_config)
    adapter_path = None if not automation_config else automation_config.get("execution_adapter_path")
    adapter_exists = bool(
        isinstance(adapter_path, str)
        and adapter_path.strip()
        and (ROOT / adapter_path).resolve().is_file()
        and ROOT.resolve() in (ROOT / adapter_path).resolve().parents
    )
    automation = evaluate_automation_authority(
        profitability,
        automation_config,
        evidence,
        intent_sha256=graph["intent_sha256"],
        graph_revision=int(graph["revision"]),
        adapter_path_exists=adapter_exists,
    )
    closure = evaluate_closure(
        technical_pass=technical_pass,
        profitability=profitability,
        automation=automation,
        mode=args.mode,
        evidence_records=evidence,
        intent_sha256=graph["intent_sha256"],
        graph_revision=int(graph["revision"]),
    )
    payload = {
        "graph_revision": graph["revision"],
        "focus": graph["focus"],
        "technical": technical,
        "profitability": profitability.to_dict(),
        "automation": automation.to_dict(),
        "closure": closure,
        "sources": {
            "trade_db": str(args.db),
            "automation_config": str(args.automation_config),
            "evidence": str(args.evidence),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.require_eligible and not closure["selected_eligible"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
