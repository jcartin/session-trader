# Simulation Mode

Status: draft v0.1, 2026-10-17. Companion to `design.md` section 3 (operating
modes) and section 10 (roadmap), `backtester.md` sections 2 to 6 and 9,
`execution.md` (Broker protocol), `session-controller.md`,
`journal-and-reporting.md`.

Simulation mode runs the complete live system, on real-time market data, in
real time, inside a normal time-gated session, with no broker account and no
money. Orders go to a `SimulatedBroker` that fills them from the live quote
and trade stream using the same fill model as the backtester. The result is a
risk-free test of the whole pipeline, from data stall detection to the
flatten deadline, that reports efficiency and efficacy with stated accuracy.

It is a fourth operating mode, between backtest and broker paper trading, and
it is where most strategy evaluation should happen.

---

## 1. Why a fourth mode

| Mode | Data | Clock | Fills | What it tests | What it cannot test |
|---|---|---|---|---|---|
| Backtest | Historical | Accelerated | Our fill model | Strategy logic over years, walk-forward validity | Live timing, data stalls, real halts as they happen, operator workflow |
| **Simulation** | **Live SIP stream** | **Real time** | **Our fill model, against live prints and queue** | Everything the live system does except placing orders: timing, stalls, halts, session timers, alerts, runbook, operator UI, strategy behavior on today's market | Market impact of our orders, broker rejections and API quirks |
| Paper (broker) | Live | Real time | Broker's paper engine | Order lifecycle, API integration, reconciliation, rejections, rate limits | Honest fills: broker paper engines fill at the touch with no queue or partial fills, and have had reliability incidents |
| Live | Live | Real time | The market | Everything | Nothing, at a cost |

Two problems with going straight from backtest to broker paper drove this
design. First, the broker's paper fills are optimistic, so a strategy that
"works" in paper may be living on fills it would never get. Second, paper
environments fail in ways live does not (the status history in
`regulatory-and-constraints.md` section 7), which confuses system testing
with vendor testing. Simulation uses the fill model we control and can
calibrate, so its results are comparable to backtests by construction, and
its only external dependency is the data feed.

Simulation also enables things the other modes cannot:

- **Parallel variants.** Several virtual accounts with different parameter
  sets run off one data stream in one session, so A/B comparisons share the
  same market day.
- **Shadow mode.** Once live trading exists, a simulation runs alongside it on
  the same signals; the fill-by-fill difference between the two is a direct
  measurement of the simulation's error and of our market impact.
- **Operator rehearsal.** Kill-switch drills, halt handling and alert
  responses can be practiced on a real market day with nothing at stake.

---

## 2. Architecture

```
 live SIP stream (quotes, trades, bars, halts)
          |
          v
  +----------------+        +------------------+
  | Stream fan-out |------->| StreamRecorder   |  raw stream to parquet for replay
  +-------+--------+        +------------------+
          |
          v
  Session controller -> screener -> strategies -> risk manager -> execution adapter
                                                                       |
                                                                       v
                                                            +---------------------+
                                                            |  SimulatedBroker    |
                                                            |  - virtual accounts |
                                                            |  - queue model      |
                                                            |  - fill model       |
                                                            |  - fee table        |
                                                            +---------------------+
                                                                       |
                                                                       v
                                                                   Journal (mode=simulation)
```

Everything above the `SimulatedBroker` is the live code path, unchanged. The
session controller does not know it is simulating; `PREFLIGHT` runs the same
checks except broker connectivity, which is replaced by a stream-health
check. The `Broker` protocol gains one mode value and one implementation.

**Shared fill engine.** The fill, impact, spread and fee logic lives in one
module, `fills/`, used by both `BacktestBroker` and `SimulatedBroker`. The
backtester feeds it stored events; the simulator feeds it live ones. A
change to the fill model therefore changes both, and the equivalence tests
in section 8 prove they agree on the same input.

---

## 3. The fill model against live data

The backtester's fill rules (`backtester.md` section 2) assume bars or
sampled quotes. Simulation has the full live stream, so it can be stricter
and more realistic. The rules below replace the bar-based approximations
when a live stream is present; everything else (pessimism levels, impact,
fees, stop gaps) is inherited.

**Latency.** Every order intent carries the decision timestamp. The simulator
treats the order as arriving at the market `latency_ms` later (default 150)
and judges it against the quote at that moment, not the quote the strategy
saw. Cancels and replaces carry the same latency. This is the first and
cheapest source of realism: a quote that was there when we decided is often
gone when we arrive.

**Marketable orders.** A buy limit at or above the ask on arrival fills
immediately up to the displayed ask size at that moment, at the ask price.
Any remainder rests at the limit as a passive order. The same in mirror for
sells against the bid. This is where broker paper engines are most generous
(they fill the whole order), and where thin $1 to $5 books punish real
orders.

**Passive orders and the queue model.** A resting order joins a queue at its
price level. At placement the simulator records `queue_ahead`, the displayed
size at that price on our side (ask size for a buy resting at the ask, bid
size for a sell resting at the bid) as a proxy for shares ahead of us. The
order then fills only from prints:

- A trade printing at a price better than our limit (below our buy, above
  our sell) fills us for the print size: anyone willing to trade through our
  price would have hit us first.
- A trade printing at exactly our limit first reduces `queue_ahead`; only
  the volume beyond it fills us. Cumulative volume at our price since
  placement must exceed `queue_ahead` plus our size for a complete fill.
- Trades at worse prices do not fill us.
- Fill quantity is further limited by the participation cap in
  `risk-manager.md`, exactly as live.

`queue_ahead` is a proxy, not a measurement: displayed size understates hidden
liquidity and overstates how much is actually ahead of a new order at a
non-primary venue. The `pessimism` setting scales it (optimistic 0.5x,
realistic 1.0x, pessimistic 2.0x), and shadow mode (section 7) calibrates it.

**Protective stops.** A stop-limit triggers when a print at or below the stop
price arrives, then follows the passive rules with the configured gap term.
In practice sub-$3 names gap through stops; the print-based trigger captures
this because the first print below the stop is often far below it.

**Halts.** The live halt feed drives the same `HALTED_EXPOSURE` logic as live.
Resting orders in a halted symbol are held and then cancelled by the session
controller as in live; the simulator never fills during a halt and treats the
first print after resumption as the reopen price.

**Partial fills.** Normal and expected. The position manager receives fills
incrementally, exactly as from Alpaca, so partial-fill handling in the live
code gets exercised every session.

**Impact.** The impact model from `backtester.md` section 3 is applied as a
price penalty on each fill. It is the acknowledged gap: a simulated order
does not move the market and does not consume liquidity that real traders
would otherwise have taken. The penalty is the stand-in until shadow mode
measures it.

---

## 4. Virtual accounts

A simulation session hosts one or more virtual accounts, each with its own
starting equity, parameter set and journal stream, sharing one data stream
and one session controller.

| Field | Notes |
|---|---|
| `account_id` | `sim-<slug>`; appears on every journal row |
| `starting_equity` | default $5,000 to match the risk defaults |
| `config_hash` | the strategy and risk parameters this account runs |
| `pessimism` | optimistic, realistic, pessimistic |
| `cash`, `positions`, `gross_exposure`, `realized_pnl`, `fees` | maintained by the simulator, same math as live including the intraday margin rule |

The risk manager runs once per account, so a rejection in one variant does
not affect another. Operator commands (`deactivate`, `flatten now`, `kill`)
apply to all accounts in the session; there is no per-account flatten, by
design, because the session is the unit the operator reasons about.

Default session shapes:

- **Evaluation**: one account, realistic pessimism, the candidate
  configuration. The standard phase 2 session.
- **Bracket**: three accounts, same configuration at the three pessimism
  levels. Shows how much of the result is fill assumption.
- **A/B**: two or more accounts with different strategy parameters, same
  risk parameters. Compares variants on the same day.
- **Shadow**: one account mirroring the live configuration while live runs
  (section 7).

A maximum of 8 accounts per session keeps the per-bar work bounded.

---

## 5. Recording and replay

The `StreamRecorder` writes the raw live stream of every simulation session
(quotes, trades, bars, halt messages, with receive timestamps) to
`data/raw/<vendor>/stream/<YYYY-MM-DD>/` as parquet. This serves three
purposes:

1. **Deterministic replay.** A recorded day can be re-streamed into a
   simulation session at 1x or Nx speed. The same code, config and seed on
   the same recording produce the same journal, byte for byte, which makes
   simulation sessions reproducible and lets a bug found on Tuesday be
   reproduced on Wednesday.
2. **Backtest fidelity.** Recorded quote and trade streams are the best
   possible input to the backtester's spread model and queue logic. Over
   months of simulation sessions the recordings become a tick-level history
   of exactly the names we trade.
3. **Regression fixtures.** A handful of recorded days with known behavior
   (a halt, a data stall, a reverse-split day) become CI fixtures for the
   session controller and execution tests.

Storage is modest: a 50-name watchlist generates on the order of 1 to 3 GB of
raw quotes and trades per session day uncompressed, under 500 MB as parquet.
Retention: all recordings for the watchlist names indefinitely; full-universe
recordings, if ever taken, for 90 days.

Replay is a `Clock` implementation. The session controller's timers (09:45
entry open, 15:30 cutoff, 15:45 flatten) read the replay clock, so a recorded
day replays its whole session lifecycle in minutes at 20x.

---

## 6. Reporting: efficiency and efficacy

Simulation sessions produce the standard session report
(`journal-and-reporting.md`) plus a simulation section. Every number carries
the pessimism level and the simulation version, and the report header states
in one line what simulation cannot see (section 9).

**Efficacy (did the strategy make money, and how)**

| Metric | Definition |
|---|---|
| Expectancy per trade | Net of modeled fees and modeled fills, per account |
| Profit factor, hit rate, max drawdown, session Sharpe | As defined in `journal-and-reporting.md` |
| Fill rate | Filled candidates over accepted candidates; a low fill rate on a profitable strategy means the edge is in orders that do not fill |
| Decision-to-fill slippage | Fill price minus the mid at decision time, in basis points, by strategy and symbol. The simulation's own cost estimate |
| Bracket spread | Realistic result minus optimistic result; large means fill assumptions dominate |
| Queue outcome mix | Share of passive fills from prints through the price, at the price past the queue, or never filled |

**Efficiency (did the system behave well)**

| Metric | Definition |
|---|---|
| Decision latency | Bar or quote receipt to candidate emission, p50 and p99 |
| Order latency | Candidate to simulated order arrival, p50 and p99 |
| Data staleness | Time since last quote per symbol at each decision; count of decisions made on stale data |
| Orders, cancels and replaces per fill | The conduct-invariant monitor from `regulatory-and-constraints.md` section 3, alerting at 10 to 1 |
| Time in market and capital utilization | Fraction of the session with open exposure; mean gross exposure over equity |
| Risk rejection mix | Which rules rejected, how often |
| Session lifecycle | Timer accuracy, flatten completion time, halted exposure incidents |
| Resource use | CPU, memory, stream message rate; a slow strategy shows up here before it shows up as missed fills |

**Rolling evaluation.** Simulation sessions count toward the 20- and
60-session rolling metrics, tagged by mode, so the phase 2 exit criteria can
be read off the same reports as live later.

---

## 7. Calibration: shadow mode and the accuracy claim

The question "how accurate is the simulation" has an empirical answer once
any real fills exist.

- **Against broker paper (phase 2b).** Run simulation and broker paper on the
  same signals for the same session. Paper fills are optimistic, so the
  comparison bounds the simulation from above: the simulation should fill no
  better than paper, and the difference is a lower bound on what paper
  overstates.
- **Against live (phase 3 onward).** Shadow mode runs a simulated account on
  the live configuration during every live session. Each live fill is matched
  to its simulated twin by candidate id. The differences, in price and in
  whether a fill happened at all, are the simulation error. Weekly, the
  calibration job (`agent-operating-model.md` section 5) fits `latency_ms`,
  the `queue_ahead` scale and the impact coefficient to minimize it, and
  opens a calibration PR when the error drifts past tolerance.

The accuracy claim in reports is therefore a measured one after phase 3
begins, and before that an explicit assumption stated as "uncalibrated,
realistic level; expect live fills to be worse by an unknown amount, see
the pessimistic bracket". The design does not promise accuracy it has not
measured.

---

## 8. Equivalence tests

Three properties, tested in CI:

1. **Backtest equals replayed simulation.** Feeding a recorded day to the
   backtester and replaying it into a simulation session with the same
   config and seed produces identical fills. This proves the shared fill
   engine is actually shared and that the live code path has no hidden
   dependency on wall-clock time.
2. **Replay is deterministic.** Two replays of the same recording produce
   identical journals.
3. **Live equals replay.** The journal of a live-streamed simulation session,
   replayed from its own recording, matches except for receive-timestamp
   jitter within the latency parameter. Any other difference is a bug in
   stream handling.

---

## 9. What simulation cannot see

Stated once here and in every simulation report header.

- Our orders do not move the market or consume liquidity. Real orders of our
  size in these names would. The impact model is a placeholder until shadow
  mode measures it.
- Queue position is a proxy from displayed size. Hidden and non-displayed
  liquidity, and venue routing, are invisible.
- Broker behavior: rejections, rate limits, outages, margin checks,
  reconciliation errors. These need broker paper and live.
- Reopen auctions after halts are approximated by the first print.
- Self-selection: in the real market, a fill on a passive order often means
  the price is moving against us. The queue model captures some of this
  (fills come from adverse prints), not all.

---

## 10. Interfaces

```python
class SimulatedBroker(Broker):
    mode = "simulation"
    def __init__(self, accounts: list[VirtualAccount], stream: MarketStream,
                 fills: FillEngine, fees: FeeTable, clock: Clock, latency_ms: int): ...
    # Broker protocol methods as in execution.md; `place` enqueues with arrival time
    # = now + latency; `on_quote` / `on_trade` advance queue and fill state.

class StreamRecorder:
    def start(self, session_id: str, symbols: list[str]) -> None: ...
    def stop(self) -> RecordingManifest: ...

class ReplayClock(Clock):
    def __init__(self, recording: RecordingManifest, speed: float): ...

class QueueModel:
    def on_place(self, order: Order, book: TopOfBook) -> QueueState: ...
    def on_trade(self, state: QueueState, trade: Trade) -> FillEvent | None: ...
```

The `Broker.mode` literal becomes `"backtest" | "simulation" | "paper" | "live"`.
`PREFLIGHT` in simulation mode substitutes a stream-health check for the
broker-connectivity check and records `mode=simulation` and the account
roster in the session header.

---

## 11. Configuration

| Key | Default | Notes |
|---|---|---|
| `simulation.latency_ms` | 150 | decision to market arrival; calibrated in shadow mode |
| `simulation.queue_ahead_scale` | 1.0 | multiplied by displayed size; pessimism levels override |
| `simulation.marketable_fill_cap` | displayed size | shares filled immediately against the touch |
| `simulation.max_accounts` | 8 | |
| `simulation.record_stream` | true | |
| `simulation.replay_speed` | 1.0 | greater than 1 for accelerated replay |
| `simulation.default_shape` | evaluation | evaluation, bracket, ab, shadow |
| `simulation.starting_equity` | 5000 | per account unless overridden |

---

## 12. Test cases

| Id | Given | When | Then |
|---|---|---|---|
| SM-01 | Buy limit at the ask, displayed ask size 300, order 500 | Order arrives | 300 fill at the ask immediately; 200 rest at the limit |
| SM-02 | Resting buy at $2.10 with queue_ahead 1,000 | Prints at $2.10 total 800 | No fill |
| SM-03 | Same | A further 400 print at $2.10 | Fill 200 (1,200 minus 1,000), remainder resting |
| SM-04 | Resting buy at $2.10 | Print at $2.09 of 150 | Fill 150 at $2.10 or better per fill engine rules |
| SM-05 | Any resting order | Halt message for the symbol | No fills during halt; session controller cancels per its rules |
| SM-06 | Strategy emits at T, latency 150 ms, ask moves away at T plus 100 ms | Order arrives | Judged against the moved quote; rests, does not fill at the old ask |
| SM-07 | Bracket session, three accounts | Same market day | Optimistic fills at least realistic fills at least pessimistic fills, by count and by price |
| SM-08 | Recorded day replayed twice | Same seed and config | Identical journals |
| SM-09 | Recorded day run through backtester and replayed simulation | Same config | Identical fills |
| SM-10 | Stream silent for 2 minutes | Stall detector | Session behaves as live: no new entries, flatten rule if positions open |
| SM-11 | Eight accounts configured | Session start | Accepted; a ninth is refused at PREFLIGHT |
| SM-12 | Stop at $1.95, print at $1.88 arrives | Stop trigger | Trigger recorded at $1.88 print; fill follows gap rule, not at $1.95 |

---

## 13. Roadmap placement

Phase 2 splits into two overlapping parts, both before any live key exists:

- **Phase 2a, simulation (the longer part, at least 40 sessions).** Strategy
  evaluation, operator rehearsal, parallel variants, recordings accumulate.
  Exit when: 40 simulation sessions at realistic pessimism with positive
  expectancy, pessimistic bracket not deeply negative, zero unhandled
  incidents, replay determinism tests green.
- **Phase 2b, broker paper (shorter, integration focus).** The same sessions
  also run against the Alpaca paper adapter to exercise the order lifecycle,
  rejections, rate limits and reconciliation. Exit when: 20 paper sessions
  with zero reconciliation mismatches and the simulation-versus-paper
  comparison report produced automatically.

Phase 3 adds shadow mode on every live session and the weekly calibration
job.

## 14. Changelog

- v0.1: initial design.
