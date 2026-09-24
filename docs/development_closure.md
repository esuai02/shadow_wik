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
