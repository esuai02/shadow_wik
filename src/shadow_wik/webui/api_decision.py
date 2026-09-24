"""POST /api/decision — record the human's follow/skip on a recommendation (journal only, no orders)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

ACTIONS = {"follow", "skip"}
MAX_NOTE = 500


def handle(runtime: Any, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    symbol = str(body.get("symbol", ""))
    action = str(body.get("action", ""))
    frame_time = str(body.get("timestamp", ""))
    if symbol not in runtime.traders:
        return 400, {"ok": False, "data": None, "error": f"api_decision.py: unknown symbol '{symbol}'"}
    if action not in ACTIONS:
        return 400, {"ok": False, "data": None, "error": f"api_decision.py: action must be one of {sorted(ACTIONS)}"}
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbol": symbol,
        "frame_timestamp": frame_time,
        "action": action,
        "note": str(body.get("note", ""))[:MAX_NOTE],
    }
    runtime.decisions_path.parent.mkdir(parents=True, exist_ok=True)
    with runtime.decisions_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 200, {"ok": True, "data": record, "error": None}
