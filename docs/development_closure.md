# Development closure candidate

Status: **TECHNICAL_COMPLETION_CANDIDATE — TECHNICAL GATES PASS**

This document prepares, but does not itself make, the final development-closure declaration for the current `intent.md`.

## Frozen technical scope

The current technical baseline is complete when the repository can repeatedly verify these paths without live credentials:

1. MarketSnapshot normalization and deterministic feature boundaries.
2. Persona / regime / Jev judgment separation.
3. Five-axis human fingerprint and sensory grammar.
4. Experience Harness anti-overfit rule: one experience cannot auto-mutate behavior.
5. Pattern-triggered paper entry/exit with fees, slippage, MFE/MAE and performance aggregation.
6. Trade lifecycle with fixed entry horizon, sell-focus `hold/reduce/exit`, trade history, and success verdict provenance.
7. Zero-install local runtime: `doctor`, full tests, `demo`, and stream plumbing.
8. Read-only market-data adapters and paper-only live trader; no real broker order path.

## Closure verification

Run from a clean checkout with Python 3.11+:

```bash
python scripts/release_check.py
python run.py doctor
python run.py test
python run.py demo
```

GitHub Actions repeats compile, release-check, doctor, full unit regression and demo on Python 3.11, 3.12 and 3.13.

## Explicitly outside the technical closure claim

The following gates remain **OPEN / UNVERIFIED** and are not evidence against technical completion:

- Real-market profitability of any pattern or fingerprint threshold.
- Calibration of raw Jev probabilities to realized market frequencies with sufficient field samples.
- Human perceptual validation that the visual grammar improves reaction quality in live trading.
- Reliability of live external providers under real outages, throttling and market stress.
- Real broker order execution.
- Any automatic-trading authority.

Synthetic and paper-trading results must never be described as realized investment performance.

## Locked safety boundary

- Actual orders and position changes remain human-reserved.
- Kiwoom integration is market-data only.
- Paper trading cannot promote itself to real execution.
- One recent trade cannot rewrite model or visual behavior.
- A short-horizon trade cannot automatically extend its horizon to avoid a loss.

## Reopen conditions

Development is reopened if any of the following occurs:

- A release regression fails on a supported Python version.
- Intent changes.
- A measured field failure contradicts a locked technical contract.
- A live-data adapter violates freshness or source assumptions.
- A real-order capability is proposed or introduced.
- Repeated field evidence justifies a change to fingerprint, pattern, calibration or visual grammar.
- The user explicitly changes the system mission or human-reserved authority.

## Final declaration hold

Technical completion may be declared only after the M7 release-readiness checks pass on the repository baseline.

The final declaration is intentionally reserved for the human owner. Until that explicit decision, the correct status is:

> **개발종료 후보 — 기술적 기준 PASS. 실전 성과와 자동매매 권한은 별도 검증 대상이며, 최종 개발종료 선언은 human hold `D7_DECLARE_COMPLETE`에 남아 있다.**


## Final declaration draft

아래 문구는 `D7_DECLARE_COMPLETE`의 최종 인간 결정이 내려질 때 사용하는 선언 초안이다.

> **shadow_wik의 현재 Intent에 정의된 기술 개발 범위는 종료한다.**
>
> M1 관측 신뢰성부터 M7 릴리스 안정성까지의 기술 계약은 정본 저장소의 자동 회귀 기준으로 고정한다. 이후 변경은 버그·회귀·Intent 변경·반복된 field evidence 또는 명시적 재개 결정이 있을 때만 REOPEN한다.
>
> 이 선언은 실전 수익성, Jev 확률의 충분한 실현빈도 calibration, 인간 감각 향상 효과, 외부 데이터 공급자의 실전 안정성, 실제 주문 실행 또는 자동매매 권한의 검증 완료를 의미하지 않는다. 이 항목들은 별도 field gate로 계속 열린 상태다.
>
> 실제 주문과 포지션 변경의 최종 권한은 계속 인간에게 있다.
