"""GET /api/state — live frames, zone status, paper trades per symbol."""
from __future__ import annotations

from typing import Any


def handle(runtime: Any, _query: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
    return 200, {"ok": True, "data": runtime.snapshot(), "error": None}
