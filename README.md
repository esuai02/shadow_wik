# shadow_wik

Evidence-first market persona and regime-transition engine with optional **TypeSafe Jev** probabilistic decisions.

The project converts the investment framework developed in conversation into a small, testable system. It does **not** treat the trader's feelings as the primary object. It treats a position as one node inside a market of competing participant clusters and asks what order-flow pressure those clusters can create next.

## Core principles

1. **Analyze positions, not identity.** The unit is `position × recent experience × market regime`, not a permanent personality label.
2. **Market regime and participant state are separate.** Uptrend, downtrend, range, and transition require different behavior.
3. **Range success is dangerous at regime change.** Repeated mean-reversion wins can train a trader to fade the exact move that ends the range.
4. **A regime change has a cause, but the cause may be hidden.** `Unknown` means not observed; it does not mean absent.
5. **News is broader than text.** Large order flow, institutional rebalancing, short covering, hedging and liquidity depletion can behave like "invisible news".
6. **Recent evidence is suspicious when it creates a recent thesis.** Price → news → commentary → algorithmic recommendation → conviction can be one recycled signal, not many independent signals.
7. **Correlation is not automatically causation.** Promote a causal hypothesis only when time order, a plausible mechanism, and falsification conditions exist.
8. **Jev is the judgment layer, not the measurement layer.** Deterministic code computes measurable features; Jev answers narrow ambiguous questions.
9. **Jev probability is raw until calibrated.** Realized outcomes must be stored and used to map Jev raw probabilities to empirical market frequencies.
10. **Signal generation and order execution are separate.** Browser/AI analysis should not automatically acquire trading authority.

## System map

```text
browser chart / market API / news
              |
              v
      deterministic features
              |
      +-------+--------+
      |       |        |
     TPE   Hidden   News Risk
            Flow
      |       |        |
      +-------+--------+
              v
  Persona / Regime state
              |
              v
       Jev System One
   Noul / Choice / Score
              |
              v
      raw probabilities
              |
              v
    empirical calibration
              |
              v
            signal
```

## Deterministic scores

All scores are `0..100` and are **features, not event probabilities**.

### TPE — Trend Potential Energy

A compressed measure of recent directional energy:

- trend persistence
- retained prior impulse after pullback
- up/down volume asymmetry
- intraday recovery efficiency
- rejection compression near resistance
- absorption
- sector confirmation
- visible catalyst or larger flow

A high TPE means the move retained structural energy. It does **not** mean "breakout probability = TPE%".

### Breakout Readiness

Near-resistance state:

- dwell time near resistance
- aggressive buy pressure
- resistance liquidity depletion
- shrinking rejection distance
- abnormal volume
- VWAP hold
- sector confirmation
- institutional flow

### Hidden Flow

Evidence of meaningful order flow without enough visible information to explain it:

- abnormal time-adjusted volume
- absorption
- order-book imbalance change
- institutional/program flow
- sector breadth
- derivatives pressure
- persistence

Visible public news discounts the hidden-flow interpretation.

### Range Exit Risk

Evidence that a range regime may be ending:

- distance outside range
- persistence outside range
- abnormal volume
- absorption
- sector confirmation
- institutional flow
- **mean-reversion failure**
- catalyst/derivatives confirmation

A one-off breakout is intentionally insufficient.

### Algorithmic Capture Risk

Measures how easily the position thesis may be reinforcing itself through recent inputs:

- thesis recency
- evidence recency
- source dependence
- repeated narrative exposure
- position ownership / recent P&L
- lack of counterevidence

### News risks

- `scheduled_news_risk`: known-event proximity × impact × expectations × crowding × prepricing
- `unscheduled_news_risk`: exposure to surprises and rumor-sensitive position structure
- `news_shock_score`: reliability × novelty × unabsorbed information × diffusion speed × market reaction

## Catalyst types

Jev classifies the current move into:

- `visible_news`
- `hidden_flow`
- `reflexive_positioning`
- `unknown`

`unknown` is a first-class outcome. The system must not invent a story merely because price moved.

## Persona clusters

The system creates hypotheses about participant groups such as:

- momentum breakout buyers
- early-long profit takers
- short-cover buyers
- mean-reversion traders
- institutional hidden flow
- same-position narrative-captured longs
- breakeven-anchored longs

The important relationship is not merely whether two groups share an opinion, but whether their **next orders** align. Two bullish groups can be trading against each other if one is a low-cost holder selling into a late bullish entrant.

## Jev integration

TypeSafe's current API accepts `state`, `model`, and named `questions` at `POST /v1/systemone`. The code uses all three primitive types:

- **Noul:** probability of yes/true
- **Choice:** selected class plus probability distribution
- **Score:** expected rubric score plus distribution

Official docs: <https://api.typesafe.ai/docs>

Environment:

```bash
cp .env.example .env
export TYPESAFE_API_KEY="..."
export JEV_MODEL="jev-latest"
```

Dry run:

```bash
PYTHONPATH=src python -m shadow_wik.cli examples/sample_snapshot.json
```

Live Jev call:

```bash
PYTHONPATH=src python -m shadow_wik.cli examples/sample_snapshot.json --live-jev
```

The included Jev questions are intentionally narrow:

1. breakout before material rejection
2. next scenario distribution
3. whether the range regime is ending
4. catalyst type
5. dominant next-order persona
6. news risk level
7. same-position bias risk

## Calibration

Never display a Jev Noul value as an empirical market win rate until calibrated.

Store each decision:

```text
(timestamp, symbol, regime, horizon, question, jev_raw_p, realized_outcome)
```

Then compare predictions with realized outcomes inside probability buckets. `ProbabilityCalibrator` supplies a minimal Beta-smoothed bucket calibrator; production should additionally segment by regime, horizon, liquidity class, and setup type once sample sizes are sufficient.

## Browser-chart workflow

For a browser-agent prototype:

1. capture the visible chart repeatedly
2. extract objective observations only
3. convert observations to the `MarketSnapshot` schema
4. calculate deterministic scores
5. send the compact state to Jev
6. alert a human
7. record the realized outcome

Prefer APIs for exact ticks/order-book/volume and use the browser as a visual sensor. Do not give a browser agent trading authority in the first version.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The first version deliberately has no broker or news-feed dependency. Feed adapters should be added only after their source contracts are known. This keeps the core state model testable and prevents a data-vendor choice from becoming architecture.
