# shadow_wik

Evidence-first market persona and regime-transition engine with optional **TypeSafe Jev** probabilistic decisions.

The project converts the investment framework developed in conversation into a small, testable system. It does **not** treat the trader's feelings as the primary object. It treats a position as one node inside a market of competing participant clusters and asks what order-flow pressure those clusters can create next.

## Fast local runtime

The default local path is **zero-install**: Python 3.11+ is enough. No package install or Docker is required for the core engine.

```bash
git clone https://github.com/esuai02/shadow_wik.git
cd shadow_wik

python run.py doctor
python run.py demo
python run.py test
```

If your system exposes Python as `python3`, use `python3 run.py ...`. On Windows, `py run.py ...` also works when the Python launcher is installed.

Useful commands:

```bash
# dry analysis; writes full output to .shadow/latest_analysis.json
python run.py analyze

# live Jev analysis; run after copying .env.example to .env and setting TYPESAFE_API_KEY
python run.py analyze --jev

# replay pattern-triggered paper trades
python run.py paper examples/paper_frames.example.jsonl

# continuous feed-agnostic runtime: one JSON object per line on stdin
your_feed | python run.py stream --patterns config/patterns.example.json

# same stream with live Jev
your_feed | python run.py stream --jev --patterns config/patterns.example.json
```

Kiwoom REST quotes (read-only, market data only) can feed `stream` directly. Set `KIWOOM_APP_KEY`, `KIWOOM_SECRET_KEY` and `KIWOOM_PAPER` (`false` = real host) in `.env`, and register this machine's public IP in the Kiwoom OpenAPI portal:

```bash
python run.py feed-kiwoom 005930 --interval 5 | python run.py stream --patterns config/patterns.example.json
```

The feed only fills `symbol`, `timestamp`, `price` and metadata; snapshot score fields stay at neutral defaults until feature extraction is added.

`stream` expects each line to contain `price` plus either the MarketSnapshot fields directly or a nested `snapshot` object. It emits a compact JSON line containing the five-axis fingerprint, signals, and any paper-trade open/close events.

Runtime state is kept under `.shadow/` and ignored by Git. This is the intended local handoff point for a future browser/chart capture process or broker market-data websocket. It does **not** send real orders.

Optional shortcuts:

```bash
make demo
make test

# POSIX shell
sh scripts/dev.sh demo

# PowerShell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 demo
```

## Trade lifecycle and sell focus

Every tracked trade is treated as **buy → hold inside a precommitted horizon → sell → outcome verdict**. The entry record must choose one of:

- `30m`
- `day`
- `3d`
- `1w`
- `1m`
- `3m`
- `6m`
- `event` for earnings, scheduled news, or another named catalyst

For an exact session deadline, pass `--planned-exit-at`. The default `day` fallback is the end of the entry calendar date, so exchange-specific session-close timing should be explicit until a market-calendar adapter exists.

Example:

```bash
# record the buy and its intended ending
python run.py trade-open 005930 84200 \
  --horizon 3d \
  --thesis "prior-high breakout with persistent hidden flow" \
  --success-min-return 0.5

# event-based trade
python run.py trade-open 005930 84200 \
  --horizon event \
  --event-name "earnings" \
  --event-at "2026-10-29T08:00:00+09:00"

# concentrate current state into sell-side Jev questions
python run.py trade-analyze <TRADE_ID> 85500 --jev

# attach the open trade to a live stream; every frame emits trade_state + exit_focus
python run.py feed-kiwoom 005930 --interval 5 | \
  python run.py stream --jev --trade-id <TRADE_ID>

# after the human actually sells, close and score the trade
python run.py trade-close <TRADE_ID> 86100 --cost-bps 12

# inspect lifecycle history
python run.py trade-history --symbol 005930
```

When a trade context is present, Jev adds sell-side questions for:

1. whether holding to the remaining horizon still has value
2. whether the original thesis is still intact
3. the dominant exit driver
4. sell urgency
5. one concentrated `exit_action`: `hold`, `reduce`, or `exit`

The Jev action is advisory. It never sends an order. The real trade is closed only through an explicit human action such as `trade-close`.

`trade-close` records entry/exit prices and times, the original horizon/event, gross and net return, exit reason, the latest matching Jev exit analysis, and a success verdict. By default success is `net_return_pct >= success_min_net_return_pct`; `--success yes|no` preserves a manual human override separately.

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


## Sensory fingerprint and prospective paper trading

`ShadowEngine.analyze()` now exposes a human-facing five-axis fingerprint:

- `EDGE`
- `FLOW`
- `STRUCTURE`
- `SAFETY`
- `TIMING`

All five axes are normalized so **higher is better** for the configured pattern context. The current mapping is `breakout_long_v1` and is a **synthetic starting hypothesis**, not a validated win-rate model.

A pattern can be defined in `config/patterns.example.json`. When a scored live/replay frame crosses the pattern thresholds, `PaperTradingHarness` opens a virtual position immediately at the observed price adjusted for slippage. It then closes on the first matching condition:

- take profit
- stop loss
- pattern invalidation
- maximum holding time
- explicit/manual end-of-replay close

Closed trades include round-trip fees and slippage. Per-pattern performance includes trade count, win rate, average net return, compounded return, profit factor, average MFE and average MAE.

Replay usage:

```bash
PYTHONPATH=src python -m shadow_wik.paper_cli \
  frames.jsonl config/patterns.example.json \
  --ledger paper_trades.jsonl
```

Each frame is one JSONL object:

```json
{"symbol":"005930","timestamp":"2026-09-24T10:31:02+09:00","price":84200,"scores":{"EDGE":78,"FLOW":82,"STRUCTURE":75,"SAFETY":68,"TIMING":86},"jev_response":{"answers":{"breakout_next_window":{"noul":0.73}}}}
```

The same harness can receive frames created directly from engine analysis with `MarketFrame.from_analysis(...)`.

**No broker/order API exists in this paper-trading path.** Promotion to real execution requires separate field evidence and explicit human authorization.
