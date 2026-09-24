"""GET /api/zones?symbol=005930 — significance report (significant zones first)."""
from __future__ import annotations

from typing import Any


def handle(runtime: Any, query: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
    symbol = (query.get("symbol") or [""])[0]
    report = runtime.reports.get(symbol)
    if report is None:
        return 404, {"ok": False, "data": None, "error": f"api_zones.py: no zone report for symbol '{symbol}'"}
    zones = sorted(report["zones"], key=lambda z: (z["status"] != "significant", z["train_p"]))
    summary = {k: report.get(k) for k in ("symbol", "bars", "train", "holdout", "costs", "exits", "method")}
    return 200, {"ok": True, "data": {**summary, "zones": zones[:40], "total": len(zones)}, "error": None}
