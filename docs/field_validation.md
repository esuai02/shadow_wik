# Field validation and closure gate

Technical regression is necessary but no longer sufficient for development closure.

## M8 — real profitability

Only closed trades explicitly marked `evidence_kind=live_real` are eligible. Paper, synthetic and unverified trades are excluded.

The initial project policy requires all of:

- at least 30 closed real trades
- at least 10 distinct trading days
- mean net return > 0 after recorded costs
- one-sided one-sample mean>0 test with p < 0.05
- profit factor >= 1.20
- compounded-path maximum drawdown <= 10%
- no single winning trade contributes more than 50% of total positive trade returns

These are project gate thresholds, not a universal definition of a profitable strategy. Changing them requires an explicit Intent/Graph revision; they must not be loosened after seeing a failing result merely to obtain PASS.

Insufficient samples return `OPEN`, not PASS.

Run:

```bash
python run.py field-gate --db .shadow/trades.db
```

A real manually executed trade should be recorded explicitly:

```bash
python run.py trade-open 005930 84200 --horizon 3d --evidence-kind live_real
# ... after the actual human sell:
python run.py trade-close <TRADE_ID> 86100 --cost-bps 12
```

Do not use `live_real` for paper, synthetic or reconstructed trades.

## M9 — automation authority

Automation is a stronger route. M8 must already PASS.

The gate additionally requires positive finite limits, a symbol allowlist, verified execution-adapter tests, stale-data rejection, erroneous/duplicate-order guards, a kill switch, paper/live separation, post-trade reconciliation, and a verified human decision record for `D9_AUTOMATION_AUTHORITY`.

A config file alone cannot authorize trading. The example is intentionally disabled:

```bash
cp config/automation_authority.example.json .shadow/automation_authority.json
python run.py field-gate --mode auto --automation-config .shadow/automation_authority.json
```

The current repository has no real-order adapter, so M9 is expected to remain OPEN until a separately reviewed implementation and actual human authorization exist.

The control principles are aligned with well-established algorithmic-trading risk practice: pre-production testing, pre-trade financial/error controls, restricted authorized access, monitoring and kill/disconnect capability. They are engineering benchmarks, not a claim that this project satisfies any specific jurisdiction's legal obligations.

## M10 — closure

Two operating routes exist:

- manual route: M7 technical baseline PASS + M8 profitability PASS
- automatic route: manual route + M9 automation authority PASS

Even when a route is eligible, final status remains `ELIGIBLE` until a current-scope `D10_DECLARE_COMPLETE` verified human decision exists. Only then is status `DECLARED`.

Any regression, contrary field evidence, changed Intent, changed gate threshold, or expansion of execution authority reopens the affected nodes.
