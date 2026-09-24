from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .trade_lifecycle import TradePlan

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'long',
    entry_time TEXT NOT NULL,
    entry_price REAL NOT NULL,
    horizon_kind TEXT NOT NULL,
    planned_exit_at TEXT,
    event_name TEXT,
    event_at TEXT,
    thesis TEXT NOT NULL DEFAULT '',
    success_min_net_return_pct REAL NOT NULL DEFAULT 0,
    evidence_kind TEXT NOT NULL DEFAULT 'unverified',
    status TEXT NOT NULL DEFAULT 'open',
    exit_time TEXT,
    exit_price REAL,
    gross_return_pct REAL,
    net_return_pct REAL,
    total_cost_bps REAL,
    success INTEGER,
    success_basis TEXT,
    exit_reason TEXT,
    final_exit_action TEXT,
    entry_context_json TEXT,
    exit_context_json TEXT,
    jev_exit_json TEXT,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON trades(symbol, status, entry_time);
"""


class TradeLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._migrate_schema()
        self.db.commit()

    def _migrate_schema(self) -> None:
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(trades)").fetchall()}
        if "evidence_kind" not in columns:
            self.db.execute("ALTER TABLE trades ADD COLUMN evidence_kind TEXT NOT NULL DEFAULT 'unverified'")
        if "total_cost_bps" not in columns:
            self.db.execute("ALTER TABLE trades ADD COLUMN total_cost_bps REAL")

    def close(self) -> None:
        self.db.close()

    def open_trade(
        self,
        plan: TradePlan,
        *,
        entry_context: dict[str, Any] | None = None,
        evidence_kind: str = "unverified",
    ) -> None:
        if evidence_kind not in {"unverified", "live_real", "paper", "synthetic"}:
            raise ValueError(f"unsupported evidence_kind: {evidence_kind}")
        self.db.execute(
            """INSERT INTO trades (
                trade_id, symbol, entry_time, entry_price, horizon_kind,
                planned_exit_at, event_name, event_at, thesis,
                success_min_net_return_pct, evidence_kind, entry_context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan.trade_id, plan.symbol, plan.entry_time, plan.entry_price,
                plan.horizon_kind, plan.planned_exit_at, plan.event_name, plan.event_at,
                plan.thesis, plan.success_min_net_return_pct, evidence_kind,
                json.dumps(entry_context or {}, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        self.db.commit()

    def get(self, trade_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        if row is None:
            raise KeyError(f"trade not found: {trade_id}")
        return dict(row)

    def get_plan(self, trade_id: str, *, require_open: bool = True) -> TradePlan:
        row = self.get(trade_id)
        if require_open and row["status"] != "open":
            raise ValueError(f"trade is not open: {trade_id}")
        return TradePlan(
            trade_id=row["trade_id"], symbol=row["symbol"], entry_time=row["entry_time"],
            entry_price=float(row["entry_price"]), horizon_kind=row["horizon_kind"],
            planned_exit_at=row["planned_exit_at"], event_name=row["event_name"], event_at=row["event_at"],
            thesis=row["thesis"] or "", success_min_net_return_pct=float(row["success_min_net_return_pct"]),
        )

    def close_trade(
        self,
        trade_id: str,
        *,
        exit_time: str,
        exit_price: float,
        total_cost_bps: float = 0.0,
        exit_reason: str = "manual",
        final_exit_action: str = "exit",
        exit_context: dict[str, Any] | None = None,
        jev_exit: dict[str, Any] | None = None,
        success_override: bool | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        row = self.get(trade_id)
        if row["status"] != "open":
            raise ValueError(f"trade already closed: {trade_id}")
        if exit_price <= 0:
            raise ValueError("exit_price must be positive")
        entry_price = float(row["entry_price"])
        gross = (float(exit_price) / entry_price - 1.0) * 100.0
        net = gross - float(total_cost_bps) / 100.0
        threshold = float(row["success_min_net_return_pct"])
        if success_override is None:
            success = net >= threshold
            basis = f"auto:net_return>={threshold:g}%"
        else:
            success = bool(success_override)
            basis = "manual_override"
        self.db.execute(
            """UPDATE trades SET
                status='closed', exit_time=?, exit_price=?, gross_return_pct=?, net_return_pct=?, total_cost_bps=?,
                success=?, success_basis=?, exit_reason=?, final_exit_action=?, exit_context_json=?,
                jev_exit_json=?, note=? WHERE trade_id=?""",
            (
                exit_time, float(exit_price), gross, net, float(total_cost_bps), int(success), basis, exit_reason,
                final_exit_action,
                json.dumps(exit_context or {}, ensure_ascii=False, separators=(",", ":")),
                json.dumps(jev_exit or {}, ensure_ascii=False, separators=(",", ":")),
                note, trade_id,
            ),
        )
        self.db.commit()
        return self.get(trade_id)

    def history(self, *, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if symbol:
            rows = self.db.execute(
                "SELECT * FROM trades WHERE symbol=? ORDER BY entry_time DESC LIMIT ?", (symbol, limit)
            ).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
