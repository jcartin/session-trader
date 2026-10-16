# Journal and Reporting Design

Status: draft v0.1, 2026-10-16
Companion to `design.md` sections 3, 5.6, 5.8, 6.4, 7 and 8; `backtester.md` sections 9 and 10; `data-layer.md` section 1; `signal-engine.md` section 4.

The journal is the system's memory and its evidence. Every decision, order,
fill and operator action is an immutable row with the full context needed to
explain it later. State is derived from the journal, never the other way
round, so a post-mortem, a report and the agent reviewer all read the same
facts.

---

## 1. Principles

1. **Append only.** Rows are inserted, never updated or deleted. Corrections
   are new rows that reference the row they correct.
2. **Self-describing.** Every row carries the session id, the config hash and
   the code version, so a row can be interpreted without external context.
3. **Same schema everywhere.** Backtest, paper and live write the same event
   types with the same payloads, into different databases. A backtest run is
   a session like any other, which is what makes `backtester.md` section 9
   possible.
4. **Market data by reference.** Bars live in Parquet (`data-layer.md`). The
   journal stores quote snapshots and bar references, not copies of bar
   history, except inside candidate input snapshots.
5. **Readable by a human in SQL.** No binary blobs; payloads are JSONB.

---

## 2. Storage

Postgres 16, one database per environment: `journal_backtest`, `journal_paper`,
`journal_live`. The live database has no DELETE or UPDATE grants for any role
except migrations.

```sql
CREATE TABLE events (
  event_id      BIGSERIAL PRIMARY KEY,          -- insertion order within this database
  event_uuid    UUID NOT NULL UNIQUE,            -- stable across exports and replays
  ts            TIMESTAMPTZ NOT NULL,            -- event time (UTC); replay clock in backtest
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id    UUID NOT NULL,
  env           TEXT NOT NULL CHECK (env IN ('backtest','paper','live')),
  event_type    TEXT NOT NULL,
  symbol        TEXT,                            -- null for session-level events
  candidate_id  UUID,
  order_id      UUID,                            -- our id; broker ids live in the payload
  client_order_id TEXT,                          -- what we send to the broker, unique per order
  config_hash   TEXT NOT NULL,                   -- hash of risk.yaml + strategies.yaml + fees.yaml
  code_sha      TEXT NOT NULL,                   -- git SHA of the running build
  seq           INTEGER NOT NULL,                -- per-session monotonic counter, detects gaps
  payload       JSONB NOT NULL,
  corrects      UUID REFERENCES events(event_uuid)
);
CREATE INDEX ON events (session_id, seq);
CREATE INDEX ON events (event_type, ts);
CREATE INDEX ON events (symbol, ts) WHERE symbol IS NOT NULL;
CREATE INDEX ON events (order_id) WHERE order_id IS NOT NULL;
CREATE INDEX ON events (candidate_id) WHERE candidate_id IS NOT NULL;
```

Supporting tables, also append-only:

- `sessions(session_id, env, started_at, config_hash, code_sha, mode, operator, notes)`
  where `mode` is `advisory` or `auto`.
- `config_snapshots(config_hash, risk_yaml, strategies_yaml, fees_yaml, recorded_at)`
  so a hash can always be expanded to its content.
- `report_runs(report_id, session_id, kind, generated_at, location)`.

Writes go through a single `Journal.write(event)` function that assigns
`seq`, stamps `config_hash` and `code_sha`, validates the payload against the
event type's pydantic model, and inserts in a transaction. The hot path uses a
bounded in-memory queue with a writer thread; if the queue exceeds 1,000
events or the writer falls more than 5 seconds behind, the session controller
is told and moves to WINDING_DOWN, because a session we cannot record is a
session we should not be running.

---

## 3. Event types and payloads

Correlation ids: `session_id` ties everything in one session; `candidate_id`
follows a signal through risk decision, order and fills; `order_id` is ours
and is generated at `order_intent`; `client_order_id` is `"<session_short>-<order_short>"`
and is sent to the broker so broker records map back to us without a lookup.

| event_type | symbol | ids set | payload fields |
|---|---|---|---|
| `session_state` | no | session | `from_state`, `to_state`, `reason`, `trigger` (`clock`, `operator`, `risk`, `error`, `halt`), `open_positions`, `open_orders` |
| `heartbeat` | no | session | `state`, `data_lag_s`, `broker_ok`, `queue_depth`, `equity`, `gross_exposure` |
| `bar_ref` | yes | session | `bar_ts`, `vendor`, `partition` (parquet path), `quality_flags` |
| `quote_snapshot` | yes | session, optional candidate/order | `bid`, `ask`, `bid_size`, `ask_size`, `quote_ts`, `kind` (`scheduled`, `signal`, `fill`) |
| `candidate` | yes | session, candidate | the full `Candidate` (signal-engine.md 4) plus `outcome` (`ranked`, `not_ranked`, `superseded`), `superseded_by` |
| `risk_decision` | yes | session, candidate | `decision` (`allow`, `reject`), `rule` (null if allow), `reason`, `proposed_qty`, `risk_dollars`, `equity`, `gross_exposure_after`, `rules_evaluated` (list of rule name and result) |
| `order_intent` | yes | session, candidate, order | `side`, `qty`, `limit_price`, `stop_price`, `tif`, `purpose` (`entry`, `exit`, `stop`, `flatten`), `ladder_step`, `max_slippage_pct` |
| `order_ack` | yes | session, order | `broker_order_id`, `status` (`accepted`, `rejected`), `broker_message`, `latency_ms` |
| `fill` | yes | session, candidate, order | `fill_qty`, `fill_price`, `cum_qty`, `remaining_qty`, `broker_fill_id`, `fill_ts`, `liquidity_flag` if provided, `fees` (object: `sec`, `taf`, `cat`, `commission`) |
| `cancel` | yes | session, order | `requested_by` (`ladder`, `tif`, `flatten`, `operator`, `halt`), `status`, `filled_before_cancel` |
| `position_open` | yes | session, candidate | `position_id`, `strategy`, `strategy_version`, `params_hash`, `avg_entry`, `qty`, `stop_price`, `target_price`, `entry_slippage_pct` (fill minus intended, over intended) |
| `position_close` | yes | session, candidate | `position_id`, `avg_exit`, `qty`, `gross_pnl`, `fees`, `net_pnl`, `hold_seconds`, `exit_reason` (`target`, `stop`, `exit_rule`, `max_hold`, `flatten`, `operator`, `halt_reopen`), `exit_slippage_pct`, `r_multiple` |
| `incident` | optional | session | `severity` (`info`, `warning`, `critical`), `kind` (`data_stall`, `broker_error`, `reconciliation_mismatch`, `halt_exposure`, `overnight_carry`, `strategy_exception`, `journal_lag`, `fill_deviation`), `detail`, `resolved_by` (event_uuid, later row) |
| `param_change` | no | session | `file`, `old_hash`, `new_hash`, `approved_by`, `pr_url`, `effective_session` |
| `operator_action` | no | session | `action` (`activate`, `deactivate`, `flatten_now`, `kill`, `approve_candidate`, `skip_candidate`, `blacklist`), `actor`, `candidate_id` if any, `note` |

Each payload has a pydantic model; `Journal.write` rejects a payload that does
not validate, and that rejection is itself journaled as an `incident` with
`kind: journal_validation`.

---

## 4. Rebuilding state from events

The position manager and session controller hold in-memory state during a
session, but that state must be reconstructible:

```
state = empty
for e in events where session_id = S order by seq:
    apply(state, e)
```

`apply` is a pure function per event type. On process restart mid-session
(`design.md` 6.7) the controller rebuilds state this way, then reconciles
against the broker's `positions()` and `orders()`. Any difference between
rebuilt and broker state is a `reconciliation_mismatch` incident and the
session enters WINDING_DOWN.

A gap in `seq` within a session is a critical incident: it means a write was
lost. Backtest runs are also checked for gaps as a regression test of the
writer.

---

## 5. Retention and backup

- Live and paper journals are kept indefinitely. Size is small: a busy session
  is under 20,000 rows, around 20 MB with snapshots.
- Backtest journals are kept for 90 days unless the run is referenced by a
  `param_change` event or a pull request, in which case they are archived to
  Parquet alongside the run directory (`backtester.md` section 10).
- Nightly `pg_dump` of live and paper to object storage with 35-day retention;
  weekly restore test into a scratch database that replays one session and
  compares its report to the stored one.

---

## 6. Session report

Generated automatically at CLOSED, written as Markdown plus a JSON sidecar,
and linked from `report_runs`. Contents:

1. **Header**: session id, env, mode, config hash, code SHA, operator,
   activation and deactivation times, final state, incidents count by severity.
2. **Account**: starting and ending equity, gross and net P&L, fees by type,
   max gross exposure, time in market (minutes with at least one position).
3. **Trades table**: one row per closed position with strategy, entry and exit
   times, quantities, prices, slippage each side, fees, net P&L, R multiple,
   exit reason.
4. **Candidates funnel**: emitted, superseded, not ranked, risk-allowed,
   risk-rejected by rule, acknowledged, filled (full or partial), unfilled
   and cancelled.
5. **Execution quality**: entry and exit slippage versus intended price,
   median and worst, by strategy; fill rate of entry orders; average ladder
   steps on exits; marketable limits used during FLATTENING.
6. **Risk**: rejection mix by rule; closest approach to the daily loss limit;
   consecutive loss brake triggered or not.
7. **Data health**: data lag percentiles, flagged bars dropped, quote
   staleness incidents.
8. **Halts**: halts in watchlist symbols, halt exposure incidents, overnight
   carries.
9. **Reconciliation**: section 8 result.

## 7. Rolling metrics

Computed over the last 20 and 60 sessions of the same `env`, grouped overall
and by `(strategy, strategy_version, params_hash)`. Definitions are fixed here
so numbers mean the same thing in every report:

| Metric | Definition |
|---|---|
| Trades | Count of `position_close` events. |
| Win rate | Closes with `net_pnl > 0` divided by trades. |
| Expectancy per trade | Mean `net_pnl` over trades. Also shown in R: mean `r_multiple`. Net means after fees and actual slippage. |
| Profit factor | Sum of positive `net_pnl` divided by absolute sum of negative `net_pnl`. Undefined if no losers; reported as "n/a" not infinity. |
| Max drawdown | On the equity curve built from session-end equity, the largest peak-to-trough decline in dollars and as a percent of the peak; plus sessions from peak to recovery, or "open" if not recovered. |
| Session-level Sharpe | Mean of daily net return divided by its standard deviation, times the square root of 252, over the window. Daily return is session net P&L over starting equity. Reported with the trade count because 20 sessions is a small sample. |
| Slippage vs model | For each fill, actual fill price minus the backtester's modeled fill price for the same intent under the realistic level, as a percent of intended price. Mean and p90, by strategy and by symbol. Positive means worse than modeled. |
| Slippage drift | Slope of the 20-session mean slippage over the 60-session window. |
| Risk rejection mix | Share of `risk_decision` rejects by rule. |
| Halt exposure incidents | Count of `incident` rows with `kind = halt_exposure` per 20 sessions. |
| Fill rate | Entry `order_intent` rows that produced at least one `fill`, divided by entry intents. |
| Average R per strategy | Mean `r_multiple` where R is `(avg_exit - avg_entry) / (avg_entry - stop_price)`. |

Metrics are recomputed from events on every report run rather than
incrementally maintained, so a bug fix in a definition applies to history.

---

## 8. Reconciliation at CLOSED

Inputs: the rebuilt journal state (section 4) and three broker reads:
`positions()`, `orders()` for today, `account()`.

| Check | Mismatch handling |
|---|---|
| Open positions: journal says zero, broker says zero | Pass. Otherwise `critical` incident; if the broker shows a position, the session is not CLOSED until the position is journaled (as an `overnight_carry` incident if halted, otherwise as an operator decision). |
| Fills: every broker fill today maps to a `fill` event by `client_order_id` and `broker_fill_id`, and quantities match | Missing or extra fill is `critical`. The missing fill is journaled as a `fill` with `corrects` set to the reconciliation incident. |
| Orders: no broker order is open | Any open order is cancelled and journaled; `warning`. |
| Cash and equity: broker equity equals journal starting equity plus net P&L within a tolerance of $0.50 plus 0.01 percent | Outside tolerance is `warning` first; two sessions in a row is `critical`. Usually fees. |
| Fees: broker-reported fees per fill equal our fee model within one cent per fill | Mismatch updates the fee model's calibration note and is `info`. |

Any `critical` reconciliation incident locks the next activation until an
operator writes an `operator_action` with `action: acknowledge_incident`
referencing it. This is the only way the lock clears.

---

## 9. Tax lot export

A quarterly and annual export in a Form 8949 style layout from
`position_open` and `position_close` events: description, quantity, date
acquired, date sold, proceeds, cost basis, gain or loss, with each fill as its
own lot when a position had multiple entry fills.

A `wash_sale_candidate` column flags any loss closed within 30 days before or
after an acquisition of the same symbol, which in an intraday system that
re-enters names will be frequent. The export does not compute wash sale
adjustments: the broker's 1099-B is the authoritative source and the
operator's CPA decides treatment. The export's job is to make the broker's
numbers checkable, not to replace them.

---

## 10. Agent reviewer access

The agent reviewer connects with role `reviewer`, which has `SELECT` on
`events`, `sessions`, `config_snapshots` and `report_runs` and nothing else,
in the paper and live databases. It holds no broker credentials. Its standing
queries, each shipped as a SQL file under `reports/queries/`:

- Session narrative: ordered `session_state`, `candidate`, `risk_decision`,
  `fill`, `position_close` and `incident` rows for one session, to be turned
  into prose.
- Rejections by rule and strategy over the last 20 sessions.
- Slippage versus model by symbol, worst ten.
- Confidence calibration: win rate and mean R by confidence decile per
  strategy.
- Candidates superseded: how often strategies agree and which one wins.
- Incidents open without an acknowledging `operator_action`.
- Parameter changes with the sessions before and after, for the weekly review.

The reviewer writes its output as Markdown files in the repository under
`reports/reviews/`, never into the journal.

---

## 11. Configuration

```yaml
journal:
  dsn_env_var: JOURNAL_DSN            # never the DSN itself
  queue_max_events: 1000
  writer_lag_warning_s: 2
  writer_lag_critical_s: 5
  snapshot_max_bytes: 32768           # candidate input snapshot cap; larger is an incident
reporting:
  rolling_windows: [20, 60]
  equity_tolerance_abs: 0.50
  equity_tolerance_pct: 0.0001
  fee_tolerance_per_fill: 0.01
  backtest_retention_days: 90
  reviewer_role: reviewer
```

---

## 12. Test cases

| Test | Assertion |
|---|---|
| Append only | An UPDATE or DELETE on `events` as the application role fails with a permission error. |
| Validation | A `fill` payload missing `fill_price` is refused and produces a `journal_validation` incident. |
| Sequence integrity | Dropping one row from a copied session makes the gap detector raise. |
| State rebuild | Replaying a recorded paper session's events reproduces the final positions, orders and equity the controller held in memory, field for field. |
| Correlation | For every `fill`, the `order_id` resolves to exactly one `order_intent` and one `order_ack`, and the `candidate_id` to exactly one `candidate` with `outcome = ranked` and one `risk_decision` with `decision = allow`. |
| Config expansion | Every `config_hash` in `events` exists in `config_snapshots`. |
| Backpressure | Stalling the writer thread for 6 seconds moves the session controller to WINDING_DOWN and journals a `journal_lag` incident once the writer resumes. |
| Metric definitions | Fixture sessions with known trades produce the hand-computed expectancy, profit factor, max drawdown and Sharpe; the no-losers case reports profit factor as n/a. |
| Slippage sign | A fill above the intended buy price yields positive slippage; above the intended sell price yields negative. |
| Reconciliation lock | A fabricated extra broker fill produces a `critical` incident and blocks PREFLIGHT until acknowledged; acknowledging clears it. |
| Fee tolerance | Broker fees differing by two cents on a fill produce an `info` incident, not a lock. |
| Tax export | Two entry fills and one exit produce two 8949 rows whose proceeds and basis sum to the position's totals; a re-entry 10 days after a loss is flagged `wash_sale_candidate`. |
| Reviewer role | The `reviewer` role cannot INSERT into `events` and cannot read any table outside the allowed four. |
| Backtest equivalence | A backtest run journals the same event types with payloads that validate against the same models as a paper session. |

## 13. Changelog

- v0.1: initial design.
