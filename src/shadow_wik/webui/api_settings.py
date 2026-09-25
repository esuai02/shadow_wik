"""POST /api/settings — update local paper-trading dashboard settings."""
from __future__ import annotations

from typing import Any


def handle(runtime: Any, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if "validation_level" not in body:
        return 400, {"ok": False, "data": None, "error": "api_settings.py: validation_level is required"}
    try:
        value = int(body["validation_level"])
    except (TypeError, ValueError):
        return 400, {"ok": False, "data": None, "error": "api_settings.py: validation_level must be an integer"}
    if value < 0 or value > 100:
        return 400, {"ok": False, "data": None, "error": "api_settings.py: validation_level must be 0..100"}
    applied = runtime.set_validation_level(value)
    return 200, {
        "ok": True,
        "data": {
            "validation_level": applied,
            "mode": "exploration" if applied == 0 else "evidence_gated",
        },
        "error": None,
    }
