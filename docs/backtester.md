# Backtester Design

Status: draft v0.2, 2026-10-17. Companion to `design.md` sections 3, 5 and 7, and `simulation-mode.md`.

The backtester exists to answer one question honestly: would this strategy,
run through this risk manager, against these fills, have had positive
expectancy after costs? Most retail backtesters answer a different, easier
question by assuming fills at the close and ignoring spreads, halts and
partial fills. In a $1 to $5 universe those three assumptions are where the
whole edge disappears, so the backtester is built around them.

Decision: **hand-built, event-driven**, not a library. Libraries model fills
at bar prices and know nothing about LULD halts or participation caps.
The cost is a few weeks of work; the benefit is that the same `Strategy`,
`RiskManager`, `PositionManager` and `Broker` interfaces run in backtest,
paper and live with no translation layer.

---

## 1. Event model

The backtester is a clock that replays stored market events in timestamp
order into the same components the live system uses.

```
for event in replay(universe, start, end):
    match event:
        Bar      -> strategies.on_bar(ctx); position_manager.on_bar(ctx)
        Quote    -> ctx.update_quote(); backtest_broker.try_fill()
        Halt     -> backtest_broker.mark_halted(); position_manager.on_halt()
        Resume   -> backtest_broker.mark_resumed(reopen_price)
        Clock    -> session_controller.on_time(ts)   # 09:45, 15:30, 15:45, 16:00
```

Event types and their sources:

| Event | Source in backtest | Granularity |
|---|---|---|
| Bar | stored 1-minute bars, split-adjusted | 1 min |
| Quote | stored NBBO snapshots where available, else a synthetic quote derived from the spread model (section 4) | 1 min or finer |
| Halt / Resume | stored halt history where available, else simulated from LULD bands (section 5) | event |
| Clock | generated from the session schedule | event |

Strict rule: a component at time T sees only events with timestamp at or
before T. The `MarketContext` object is the only way to read market data,
and it refuses lookups past the current clock. This is the look-ahead guard.

Determinism: all randomness (fill probability, partial-fill ratios) is drawn
from a seeded generator recorded in the run metadata. Same seed, same data,
same config hash, same result, byte for byte.

---

## 2. Fill model

The `BacktestBroker` implements the same `Broker` interface as the live
adapter. Orders are resting limit orders evaluated against each subsequent
quote or bar.

**Entry (buy limit at price L):**

- If the ask at the next quote is at or below L, fill at the ask, not at L.
  The live system pays the ask; the backtest must too.
- If only bars are available: fill only if the bar's low is at or below
  L minus one tick. Trading at exactly L does not guarantee a fill because we
  are behind the queue. Fill price is L.
- Fill quantity is limited by the participation cap: at most
  `participation_rate` (default 2 percent) of the bar's volume. The remainder
  stays resting and may fill on later bars, or is cancelled at the order's
  time-in-force limit (default 45 seconds, so effectively one bar).
- Entries never fill inside a halt. An order resting into a halt is cancelled,
  mirroring the live adapter's behavior.

**Exit (sell limit at price L):**

- If the bid at the next quote is at or above L, fill at the bid.
- Bar-only: fill if the bar's high is at or above L plus one tick, at L.
- Same participation cap. Unfilled remainder follows the live step-down
  ladder: reprice one tick lower each 20 seconds (so each bar in 1-minute
  data steps down up to three ticks), up to the max-slippage budget.
- During FLATTENING, after the ladder is exhausted, a marketable limit fills
  at the bid minus `flatten_impact` (section 3).

**Protective stop:** modeled as a stop-limit at the broker. Triggers when
the bar's low touches the stop price. Fill price is the stop price minus a
gap term: the larger of one tick and the bar's open-to-low distance scaled
by `stop_gap_factor` (default 0.5). Penny stocks gap through stops; the model
must not assume the stop price.

The fill model has a `pessimism` setting with three levels used in reports:

| Level | Entry | Exit | Use |
|---|---|---|---|
| optimistic | at L when bar touches L | at L when bar touches L | upper bound only, never for decisions |
| realistic (default) | rules above | rules above | decisions |
| pessimistic | ask plus one tick, half the participation cap | bid minus one tick, half the cap | stress test; a strategy that fails here is fragile |

A strategy is reported with all three. The gap between optimistic and
realistic is itself a diagnostic: a large gap means the edge lives in the
fill assumption, not the signal.

---

## 3. Market impact

Our own orders move thin stocks. The model adds impact proportional to our
share of recent volume:

```
impact_bps = impact_coeff * sqrt(order_qty / trailing_15m_volume) * 10_000
```

`impact_coeff` default 0.1, calibrated in phase 3 against live fills. Impact
is applied to the fill price on top of the spread. `flatten_impact` for
marketable exits uses the same formula with double the coefficient.

This is deliberately crude. Its job is to make the backtest punish size, so
that "trade more shares" never looks like free money.

---

## 4. Spread model

Minute bars do not carry the spread, and the spread is the dominant cost.
Three sources in order of preference:

1. **Stored NBBO snapshots** at 1-minute granularity from a SIP feed. Phase 0
   decides whether the data vendor can supply these historically at acceptable
   cost. This is the preferred source and the reason SIP data is budgeted from
   the paper phase.
2. **Per-symbol spread model** fitted from whatever NBBO history we have:
   spread as a function of price, time of day, and trailing volume. Used to
   synthesize quotes for bars with no stored snapshot.
3. **Universe prior** when a symbol has no history at all: a conservative
   table by price band (default 1.0 percent for $3 to $5, 1.5 percent for $1
   to $3, widened by 50 percent in the first and last 15 minutes).

Each fill records which source priced its spread. Reports show the share of
fills priced from each source, because a backtest that is mostly priced from
the prior is not a backtest, it is a guess.

---

## 5. Halt simulation

When stored halt history exists, it is replayed. When it does not, halts are
simulated from the LULD rules in `design.md` C5:

- Reference price: trailing 5-minute average of trade prices (bar closes
  weighted by volume as the approximation).
- Band width by price regime: 10 percent above $3.00, 20 percent from $0.75
  to $3.00; doubled from 15:35 to 16:00 for prices at or below $3.00. The
  table is data, not code, so rule changes are a config edit.
- A bar whose high or low breaches the band for the equivalent of 15 seconds
  (approximated as: the close is also outside the band) triggers a 5-minute
  pause. The pause is extended by 5 minutes with probability
  `halt_extension_prob` (default 0.2).
- During a pause: no fills, orders resting into the pause are cancelled, and
  the position manager receives the `on_halt` event exactly as live.
- Reopen price: the first bar's open after the pause, with a reopen slippage
  term drawn from a distribution calibrated to observed reopen gaps (default
  normal, mean 0, standard deviation 2 percent).

Simulated halts are marked as such in the journal so reports can show
realized versus simulated halt exposure.

---

## 6. Fee model

A table of date-ranged rates, loaded from `fees.yaml`:

```yaml
- from: 2026-04-04
  sec_section31_per_million_sold: 20.60
- from: 2026-01-01
  finra_taf_per_share_sold: 0.000195
  finra_taf_cap_per_trade: 9.79
- from: 2026-10-01
  to: 2026-12-31
  finra_taf_per_share_sold: 0.0        # Q4 2026 waiver
- from: 2026-01-01
  cat_fee_per_share: 0.000035          # placeholder, confirm from broker schedule
commission_per_share: 0.0
```

The TAF waiver is the reason this is a table. A backtest over Q4 2026 with a
constant rate would either overstate or understate fees for a quarter.

For the OTC future (design.md section 11) a second schedule models IBKR's
per-share commission with the $0.35 minimum and 1 percent maximum.

---

## 7. Data hygiene

- **Split adjustment**: bars are stored raw and adjusted at load time using
  the corporate actions table. Reverse splits are the common case here.
  Adjustment factors are applied only to bars before the effective date,
  never forward (look-ahead guard).
- **Point-in-time universe**: the screener runs inside the backtest on each
  session's prior-day data, over all symbols that were listed on that date,
  including ones later delisted. The universe is never built from today's
  symbol list. Phase 0 confirms the vendor serves delisted tickers; if it
  does not, the vendor is unsuitable.
- **Bar gaps**: a minute with no eligible trades has no bar. The replayer
  does not fabricate bars; the `MarketContext` reports staleness and the
  strategy interface must tolerate it, exactly as live.
- **Bad prints**: bars where open or close fall outside high to low, or
  where the close moves more than 50 percent from the prior close with no
  corporate action, are flagged and excluded from signal computation but
  kept in the data with a quality flag.

---

## 8. Validation protocol

Parameters are tuned on one window and judged on another, always.

- **Walk-forward**: tune on 6 months, test on the following 2 months, roll
  forward by 2 months. Report the concatenated out-of-sample results only.
  In-sample results are shown greyed out and never used for a go decision.
- **Parameter count**: every run records how many parameter combinations were
  evaluated in the tuning window. The report divides out-of-sample
  performance by a deflation factor that grows with that count, and shows
  both numbers.
- **Three pessimism levels** (section 2) on every out-of-sample run.
- **Regime slices**: results broken down by month, by small-cap index trend
  (up, flat, down months), and by price band. An edge that exists only in
  one slice is reported as such.
- **Trade count floor**: fewer than 100 out-of-sample trades means "not yet
  evaluable", regardless of the numbers.
- **Go criteria** for promoting a strategy to paper: positive out-of-sample
  expectancy at the realistic level, profit factor at least 1.3, expectancy
  still positive at the pessimistic level, and at least 100 trades.

---

## 9. Backtest to simulation to paper to live equivalence

The fill, impact, spread and fee logic is one shared module used by both the
backtester and the simulation mode's `SimulatedBroker` (`simulation-mode.md`
sections 2 and 8), so the two agree by construction on recorded input.

The strongest check on the backtester is to feed it a day that actually
happened in simulation, paper or live trading and compare.

- Every paper and live session's journal can be replayed through the
  backtester using the stored quotes and bars from that day.
- The replay report compares, trade by trade: signal time, intended price,
  modeled fill, actual fill, modeled fees, actual fees.
- Systematic differences become calibration changes to `impact_coeff`, the
  spread model, or the stop gap factor. This loop runs weekly in phase 2 and
  3 and is the agent's main maintenance job on the backtester.

---

## 10. Outputs

Every run produces a directory keyed by run id containing: the config hash
and full config, the data manifest (symbols, date range, vendor, adjustment
version), the seed, the journal in the same event schema as live, and a
report with the metrics in `design.md` section 7 at all three pessimism
levels, the spread-source mix, simulated versus realized halt counts, the
parameter count and deflated results, and regime slices.

Reports are plain Markdown plus a small set of charts so they can be
attached to pull requests that change `strategies.yaml`.

---

## 11. Build order (phase 1)

1. Storage and loader with split adjustment and quality flags.
2. Replayer and `MarketContext` with the look-ahead guard, plus tests that
   prove a strategy cannot read the future.
3. `BacktestBroker` with the realistic fill model and participation cap.
4. Fee table and spread prior.
5. Risk manager and position manager (shared with live).
6. Halt simulation.
7. Walk-forward harness and report.
8. Impact model and pessimism levels.
9. Per-symbol spread model, once NBBO history is available.

Steps 1 to 5 give a usable backtester for the three starter strategies.
Steps 6 to 9 make it honest enough for a go decision.

## 12. Changelog

- v0.2: shared fill engine with simulation mode noted; equivalence section renamed.
- v0.1: initial design.
