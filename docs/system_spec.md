# Shadow Wik system specification

This document is the compact canonical summary of the trading framework developed before the first code commit.

## Objective

The system does not attempt to psychoanalyze the user directly. The user supplies objective observations. The system places the user's position inside a set of hypothesized participant clusters and estimates how each cluster can turn into future order flow.

Primary loop:

```text
objective observations
→ regime state
→ market persona clusters
→ same-position persona
→ catalyst hypothesis
→ micro causal chain
→ Jev scenarios/probabilities
→ advisory signal
→ realized outcome
→ calibration
```

## Regime model

- `uptrend`: resting can mean holding valid trend exposure.
- `downtrend`: cash is a position; resting can mean reducing exposure.
- `range`: mean reversion may work, but repeated success can condition dangerous fading behavior.
- `transition`: maintain competing scenarios and invalidation conditions.

A single apparent breakout does not prove a regime change. Stronger evidence requires persistence, volume, breadth, flow, derivatives and/or information. The strongest warning in a range is failure of the previously profitable mean-reversion pattern.

## Persona model

A persona is a temporary behavioral bias, not identity.

Examples: FOMO-free, periodic-investment, probability-mirage, news/counter-news, scenario-zero, rest.

Market personas are defined by their likely **next orders**, not by stated opinions.

## Conviction and zero-point adjustment

Rarity is not quality. Map each thesis across public consensus, active retail, experienced investors, specialists, contrarians and fringe hypotheses. Keep conviction crowding, reasoning quality and contamination as separate axes.

Recent thesis + recent evidence + recent price is risky because apparently independent inputs may be one recycled signal.

## Algorithmic capture

```text
price → news → commentary/community → recommendation algorithm → conviction → price reinterpreted as confirmation
```

Ask whether the thesis survives hiding recent price, removing recent media, testing source independence, and seeking falsifiers.

## News risk

- Scheduled News Risk: proximity, impact, expectation skew, crowding, prepricing.
- Unscheduled News Risk: surprise vulnerability and rumor-sensitive structure.
- News Shock Score: reliability, novelty, unabsorbed content, diffusion speed and market reaction.

News direction and news risk are separate.

## Catalyst taxonomy

- `visible_news`
- `hidden_flow`
- `reflexive_positioning`
- `unknown`

Unknown means cause not observed, not cause absent.

## Hidden-flow traces

Abnormal time-adjusted volume, repetitive execution, absorption, book replenishment/cancellation change, peer synchronization, derivatives pressure, short/lending changes, closing concentration, persistence, and institutional/program flow.

Often the useful quantity is price movement per unit of aggressive flow.

## Micro causality

Intraday order-flow can expose local causal chains:

```text
sell orders
→ absorption
→ offer depletion
→ aggressive buys
→ price lift
→ short invalidation
→ short covering
→ momentum entry
```

This supports a local causal hypothesis when time order and mechanism are observed, without pretending to know the higher-level institutional motive.

## TPE and breakout

TPE compresses trend persistence, impulse retention, volume asymmetry, recovery efficiency, rejection compression, absorption and breadth. It is a feature, not a probability.

Breakout Readiness adds near-resistance dwell, aggressive buy pressure, resistance liquidity depletion, VWAP hold, abnormal volume, breadth and institutional flow.

Repeated resistance tests are constructive only when rejection shrinks and supply appears to deplete.

## Browser-agent role

Browser agent = visual sensor. APIs = precise measurement. Extract objective state, calculate deterministic features, send compact state to Jev, alert a human, record realized outcomes. Do not initially grant browser agents order authority.

## Jev role

Jev receives compact structured state and narrow questions:

- Noul: breakout? range ending?
- Choice: next scenario? catalyst? dominant persona?
- Score: news destabilization? same-position bias?

Raw Jev probabilities are model judgments until calibrated against realized outcomes for the same horizon, regime and setup.
