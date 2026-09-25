# Scalping pattern hypothesis library

These patterns are **paper-trading hypotheses**, not validated profit claims. Jev answers only whether the current state resembles the pattern thesis more than its falsification condition. Jev raw probability is not a realized win rate or a p-value.

## 1. Opening-range breakout

**Operational intuition:** an early range breaks with acceptance and continued order pressure rather than immediately returning to the range.

**Jev question:** `scalp_opening_range_breakout`

**Falsification:** breakout rejection, rapid range re-entry, or loss of flow/acceptance.

**Paper exit v1:** +0.60% TP / -0.40% SL / 15 minute max hold.

**Evidence context:** Marshall, Nguyen and Visaltanachoti (2013) reported positive evidence for an opening-range-breakout rule in crude-oil futures. A 2026 pre-registered futures study reported that simple ORB variants did not survive realistic costs. This conflict is the reason the rule starts as a hypothesis rather than a trusted edge.

Sources:
- https://www.sciencedirect.com/science/article/pii/S1544612312000438
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398

## 2. Intraday momentum continuation

**Operational intuition:** an early directional move persists when volume/volatility and participant behavior reinforce rather than exhaust it.

**Jev question:** `scalp_intraday_momentum`

**Falsification:** directional persistence disappears or evidence shifts toward reversal/mean reversion.

**Paper exit v1:** +0.50% TP / -0.35% SL / 12 minute max hold.

**Evidence context:** Gao, Han, Li and Zhou documented that the first half-hour market return predicted the last half-hour return in actively traded ETFs, with stronger effects on high-volume/high-volatility days. Evidence from China also documents both intraday momentum and reversal, warning that the sign is regime-dependent.

Sources:
- https://www.sciencedirect.com/science/article/pii/S0304405X18301351
- https://www.sciencedirect.com/science/article/pii/S1544612318307414

## 3. Order-flow persistence

**Operational intuition:** persistent buy-side imbalance or hidden flow continues to exert short-horizon positive price pressure.

**Jev question:** `scalp_order_flow_persistence`

**Falsification:** imbalance dissipates, absorption flips adverse, or price stops responding to apparent flow.

**Paper exit v1:** +0.45% TP / -0.32% SL / 10 minute max hold.

**Evidence context:** order-imbalance research finds a relation between imbalance and returns; short-horizon work finds order-flow imbalance closely related to price changes, and intraday Chinese evidence reports predictive power from 1 to 90 minutes. Transfer to KRX minute trading remains unverified.

Sources:
- https://www.sciencedirect.com/science/article/pii/S0304405X03001752
- https://academic.oup.com/jfec/article-abstract/12/1/47/816163
- https://www.sciencedirect.com/science/article/pii/S0927538X15300056

## 4. Opening shock reversal

**Operational intuition:** an opening shock or overshoot is more likely to mean-revert than continue after liquidity and participant response are considered.

**Jev question:** `scalp_opening_shock_reversal`

**Falsification:** order flow remains one-sided and structure confirms continuation.

**Paper exit v1:** +0.50% TP / -0.35% SL / 10 minute max hold.

**Evidence context:** intraday studies document reversal as well as momentum. A 2026 U.S. index study reports that overnight return can negatively predict the first half-hour return, with time-varying strength. This is not direct evidence for individual KRX stocks and therefore remains a transfer hypothesis.

Sources:
- https://www.sciencedirect.com/science/article/pii/S1544612318307414
- https://www.sciencedirect.com/science/article/pii/S1062940826001294

## Dashboard validation strength

`0` is **exploration**, not statistical significance. In exploration mode a pattern can paper-trade when its Jev probability is at least 0.50 and the deterministic safety floor is met.

Raising the slider does two things:

1. increases the minimum Jev pattern probability from 0.50 toward 0.90;
2. requires the pattern's accumulated paper-trade evidence-strength to meet the selected level.

Paper evidence-strength is an intuitive 0-100 transformation of positive-mean one-sided p-value, multiplied by a sample-size factor that reaches 1 at 30 trades. It is not itself a probability and cannot satisfy the M8 `live_real` profitability gate.

## Paper capital

- seed: KRW 100,000,000
- default allocation: 10% of seed per opened pattern
- maximum concurrent positions: 10
- leverage: none
- realized capital update: cost-adjusted paper net return
- non-KRW FX: not modeled in the paper capital view

The initial allocation and exits are observation settings, not optimized parameters.
