# Development closure gate

Status: **TECHNICAL_BASELINE_PASS / FIELD_GATE_OPEN**

The current repository has a technically stable baseline. That is no longer sufficient for final development closure.

## Gate chain

- M7 — technical release stability
- M8 — real-field profitability
- M9 — automation authority and execution safety, only when automatic operation is the intended final mode
- M10 — final human closure declaration

Two closure routes exist:

1. **Manual-operation route:** M7 PASS + M8 PASS -> closure becomes ELIGIBLE.
2. **Automatic-operation route:** M7 PASS + M8 PASS + M9 PASS -> closure becomes ELIGIBLE.

In either route, M10 remains undeclared until a current-scope verified human decision for `D10_DECLARE_COMPLETE` exists.

## M7 — technical baseline

Run from a clean checkout:

```bash
python scripts/release_check.py
python run.py doctor
python run.py test
python run.py demo
```

GitHub Actions repeats compile, release-check, doctor, full unit regression, field-gate dry execution and demo on Python 3.11, 3.12 and 3.13.

Technical PASS proves reproducibility of the software contracts only.

## M8 — field profitability

Only actual completed trades explicitly recorded as `evidence_kind=live_real` can count.

The initial field policy requires all of:

- at least 30 closed real trades
- at least 10 distinct trading days
- positive average net return after recorded costs
- one-sided mean > 0 with p < 0.05
- profit factor >= 1.20
- maximum compounded-path drawdown <= 10%
- largest winning trade <= 50% of total positive trade returns

Paper, synthetic, reconstructed or unverified trades never count. Missing cost information excludes the trade.

Run:

```bash
python run.py field-gate --db .shadow/trades.db
```

Insufficient evidence returns `OPEN`; sufficient evidence that violates a criterion returns `FAIL`; all criteria passing returns `PASS`.

These thresholds are the project's initial field policy, not a universal investment-success standard. They may only be changed through a new Intent/Graph revision, not after observing a failure merely to obtain PASS.

## M9 — automation authority

M9 cannot PASS unless M8 already PASS.

If automatic execution is selected as the final operating mode, the gate additionally requires bounded pre-trade notional, position, daily-loss and order-rate limits; a symbol allowlist; stale-data rejection; erroneous and duplicate-order guards; a kill switch; paper/live separation; post-trade reconciliation; a verified execution adapter; and a current-scope verified human decision for `D9_AUTOMATION_AUTHORITY`.

A JSON config alone never grants authority. The repository's example config is intentionally disabled.

The current repository has no real-order adapter, therefore the present expected state is **M9 OPEN**.

## Safety boundary

- This Intent revision does not authorize automatic trading.
- Actual orders and position changes remain human-reserved.
- A config file cannot substitute for a verified human authorization record.
- Paper/synthetic results cannot promote themselves into M8.
- A short-horizon losing trade cannot silently extend its horizon.
- Regressions or contrary field evidence reopen the affected node.
- M9 engineering controls are not a substitute for broker, exchange, or jurisdiction-specific legal and regulatory obligations.

## Reopen conditions

Reopen the affected node if:

- supported-version regression fails;
- Intent or field thresholds change;
- live data violate freshness/source assumptions;
- measured field results contradict a locked inference;
- execution authority or order-capability scope changes;
- repeated field evidence justifies a fingerprint, pattern, calibration or visual-grammar change.

## Current declaration state

The correct current state is:

> **기술 baseline PASS. M8 실전 수익성은 실제 `live_real` 표본으로 검증 전이므로 OPEN. M9 자동주문 권한도 OPEN. 따라서 M10 최종 개발종료 선언은 아직 불가.**

## Final declaration draft — manual route

When M8 is PASS and `D10_DECLARE_COMPLETE` is explicitly approved:

> **shadow_wik의 현재 Intent에 정의된 개발을 종료한다. 기술 회귀와 실제 체결 기반 수익성 Gate가 모두 통과했으며, 이후 변경은 회귀·반증되는 field evidence·Intent 변경 또는 명시적 재개 결정이 있을 때만 REOPEN한다. 실제 주문 권한은 계속 인간에게 있다.**

## Final declaration draft — automatic route

When M8 and M9 are PASS and `D10_DECLARE_COMPLETE` is explicitly approved:

> **shadow_wik의 현재 Intent에 정의된 자동운영 개발을 종료한다. 기술 회귀, 실제 체결 기반 수익성, 자동주문 안전·권한 Gate가 모두 통과한 현재 범위를 baseline으로 고정한다. 승인된 한도 밖의 주문권한 확대는 새로운 Intent/Graph revision 없이 허용하지 않는다.**
