from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

FailureClass = Literal[
    "measurement", "model", "visualization", "interpretation", "aligned", "unknown"
]


@dataclass(slots=True)
class TradeExperience:
    experience_id: str
    timestamp: str
    symbol: str
    regime: str
    setup: str
    system_expectation: str
    realized_outcome: str
    user_observation: str
    visual_feedback: str = "aligned"
    focal_cue: str = "general"
    data_quality_issue: bool = False
    acted_against_signal: bool = False
    system_signal_was_clear: bool = True
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class ExperienceAssessment:
    experience_id: str
    failure_class: FailureClass
    issue_key: str
    rationale: str
    proposed_change: str | None
    auto_apply: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LearningProposal:
    issue_key: str
    repeats: int
    failure_class: FailureClass
    proposal: str
    status: str = "candidate_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperienceHarness:
    """Convert trading experience into bounded learning evidence.

    A single experience never mutates model weights or visual grammar.
    Repeated matching evidence only creates a candidate proposal for review/replay.
    """

    def __init__(self, ledger_path: str | Path, min_repeats_for_proposal: int = 3) -> None:
        if min_repeats_for_proposal < 2:
            raise ValueError("min_repeats_for_proposal must be at least 2")
        self.ledger_path = Path(ledger_path)
        self.min_repeats_for_proposal = min_repeats_for_proposal

    def assess(self, exp: TradeExperience) -> ExperienceAssessment:
        expected_matches = exp.system_expectation == exp.realized_outcome

        if exp.data_quality_issue:
            failure_class: FailureClass = "measurement"
            rationale = "입력 데이터 품질 문제가 있어 모델/시각화를 수정하기 전에 관측 계층을 점검해야 한다."
            proposed = "해당 데이터 소스의 freshness, 누락, timestamp 정합성을 재현 점검한다."
        elif exp.visual_feedback in {"too_strong", "too_weak", "confusing"}:
            failure_class = "visualization"
            rationale = "사용자가 보고 느낀 신호 강도와 실제 의미 사이의 불일치가 명시적으로 보고되었다."
            proposed = "해당 cue의 강도/속도/불확실성 표현을 유사 사례 replay에서 비교한다."
        elif not expected_matches and exp.system_signal_was_clear:
            failure_class = "model"
            rationale = "명확한 시스템 기대와 실제 결과가 불일치했다."
            proposed = "동일 regime/setup 사례를 묶어 feature/Jev 판단 오류가 반복되는지 replay한다."
        elif exp.acted_against_signal and expected_matches:
            failure_class = "interpretation"
            rationale = "시스템 신호는 실제 결과와 일치했지만 행동은 반대였다."
            proposed = "해당 상황의 counter-cue 또는 영점조정 표현을 강화할지 검토한다."
        elif expected_matches:
            failure_class = "aligned"
            rationale = "현재 경험에서는 시스템 기대와 실제 결과가 일치했다."
            proposed = None
        else:
            failure_class = "unknown"
            rationale = "현재 정보만으로 오류의 층위를 분리할 수 없다."
            proposed = "추가 관측 없이 모델이나 시각표현을 수정하지 않는다."

        issue_key = f"{failure_class}:{exp.regime}:{exp.setup}:{exp.focal_cue}"
        return ExperienceAssessment(
            experience_id=exp.experience_id,
            failure_class=failure_class,
            issue_key=issue_key,
            rationale=rationale,
            proposed_change=proposed,
            auto_apply=False,
        )

    def record(self, exp: TradeExperience) -> ExperienceAssessment:
        assessment = self.assess(exp)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "kind": "trade_experience",
            "experience": asdict(exp),
            "assessment": assessment.to_dict(),
        }
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return assessment

    def proposals(self) -> list[LearningProposal]:
        if not self.ledger_path.exists():
            return []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            assessment = item.get("assessment", {})
            key = assessment.get("issue_key")
            failure_class = assessment.get("failure_class")
            if not key or failure_class in {"aligned", "unknown", None}:
                continue
            grouped.setdefault(key, []).append(item)

        proposals: list[LearningProposal] = []
        for key, records in grouped.items():
            if len(records) < self.min_repeats_for_proposal:
                continue
            latest = records[-1]["assessment"]
            proposals.append(LearningProposal(
                issue_key=key,
                repeats=len(records),
                failure_class=latest["failure_class"],
                proposal=latest.get("proposed_change") or "유사 사례 replay 후 수정 후보를 검토한다.",
            ))
        return proposals
