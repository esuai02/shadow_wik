from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    regime TEXT NOT NULL,
    horizon_minutes INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer_type TEXT NOT NULL,
    raw_probability REAL,
    answer_json TEXT NOT NULL,
    realized_label TEXT,
    success INTEGER
);
CREATE INDEX IF NOT EXISTS idx_decisions_lookup
ON decisions(question, regime, horizon_minutes, raw_probability);
"""


class DecisionLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def record_response(self, *, timestamp: str, symbol: str, regime: str, horizon_minutes: int, response: dict[str, Any]) -> list[int]:
        ids: list[int] = []
        for question, answer in response.get("answers", {}).items():
            answer_type = answer.get("type", "unknown")
            raw_probability = None
            if answer_type == "noul":
                raw_probability = float(answer["noul"])
            elif answer_type == "choice":
                choice = answer.get("choice")
                probabilities = answer.get("probabilities", {})
                if choice in probabilities:
                    raw_probability = float(probabilities[choice])
            cursor = self.db.execute(
                """INSERT INTO decisions (
                    timestamp, symbol, regime, horizon_minutes, question,
                    answer_type, raw_probability, answer_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    timestamp, symbol, regime, horizon_minutes, question,
                    answer_type, raw_probability,
                    json.dumps(answer, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            ids.append(int(cursor.lastrowid))
        self.db.commit()
        return ids

    def resolve(self, decision_id: int, *, success: bool | None = None, realized_label: str | None = None) -> None:
        self.db.execute(
            "UPDATE decisions SET success = ?, realized_label = ? WHERE id = ?",
            (None if success is None else int(success), realized_label, decision_id),
        )
        self.db.commit()

    def calibration_rows(self, *, question: str, regime: str, horizon_minutes: int) -> list[tuple[float, bool]]:
        rows = self.db.execute(
            """SELECT raw_probability, success FROM decisions
            WHERE question = ? AND regime = ? AND horizon_minutes = ?
              AND raw_probability IS NOT NULL AND success IS NOT NULL""",
            (question, regime, horizon_minutes),
        ).fetchall()
        return [(float(p), bool(success)) for p, success in rows]
