# Session Controller Design

Status: draft v0.1, 2026-10-16
Companion to `design.md` sections 5.6, 6.1, 6.2, 6.3 and 6.7, `execution.md`
(order lifecycle, kill mechanics), `backtester.md` section 1 (Clock events),
`data-layer.md` section 1 (data quality checks).

The session controller is the component that owns the activation window. It
decides when strategies may run, when entries stop, when positions must be
gone, and what happens when the world does not cooperate. It is deliberately
small: it holds the state, runs the timers, dispatches operator commands, and
calls into the risk manager, position manager and execution adapter. It makes
no trading decisions of its own.

Two properties the whole design leans on:

1. **Every transition is journaled** as a `session_state` event with the
   trigger, the previous state and the wall-clock time, before any side effect
   of the new state runs.
2. **The controller is restartable.** State is rebuilt from the journal plus
   a broker reconciliation, never from memory, so a crash is a transition, not
   a catastrophe.

---

## 1. States

| State | Meaning | Entries allowed | Exits allowed | Heartbeat |
|---|---|---|---|---|
| IDLE | No session today, or the session has ended and the process is waiting | no | no | off |
| PREFLIGHT | Running the activation checklist | no | no | off |
| ACTIVE | Strategies running, risk manager gating, orders flowing | yes | yes | on |
| WINDING_DOWN | No new entries; open positions managed by their exit rules | no | yes | on |
| FLATTENING | Cancel everything open, exit everything held via the ladder | no | yes, forced | on |
| CLOSED | All positions gone or carried as incidents; reconciliation running | no | no | off |
| LOCKED | Activation refused for the rest of the day or week by a loss limit or an unresolved incident | no | no | off |

**HALTED_EXPOSURE** is a sub-state flag, not a top-level state. It is set
whenever at least one held symbol is halted and cleared when none is. It can
be set during ACTIVE, WINDING_DOWN and FLATTENING. It changes behavior inside
those states (section 4) rather than replacing them, so the timers and the
operator commands keep their meaning.

LOCKED is new relative to `design.md` 5.6. It makes the "locks activation for
the day" consequence of the daily loss limit (design.md 5.4) an explicit state
rather than a side flag, so PREFLIGHT can refuse with a reason.

---

## 2. Transition table

| From | To | Trigger | Guard | On transition |
|---|---|---|---|---|
| IDLE | PREFLIGHT | operator `activate`, or scheduled activation time | not LOCKED for today; before `entry_cutoff` | journal `operator_action`; start checklist |
| PREFLIGHT | ACTIVE | checklist passed | current time at or after `entry_open` | record config hash and code SHA; start heartbeat; arm timers; load watchlist into strategies |
| PREFLIGHT | IDLE | checklist failed | | journal failure reasons; alert operator (log channel) |
| PREFLIGHT | IDLE | operator `deactivate` | | abort checklist |
| ACTIVE | WINDING_DOWN | `entry_cutoff` timer (15:30) | | cancel all resting entry orders |
| ACTIVE | WINDING_DOWN | operator `deactivate` | | same |
| ACTIVE | WINDING_DOWN | daily loss limit hit | | same, plus set LOCKED-for-today flag to apply at CLOSED |
| ACTIVE | WINDING_DOWN | consecutive-loss brake or weekly loss limit | | same; weekly limit sets LOCKED-for-week |
| ACTIVE | FLATTENING | `flatten_deadline` timer (15:45) | | cancel all; begin forced exits |
| ACTIVE | FLATTENING | operator `flatten now` or `kill` | | same |
| ACTIVE | FLATTENING | fatal error (section 6) | | same; alert (push plus SMS) |
| ACTIVE | FLATTENING | data stall over 2 minutes with positions open | | same; use broker quotes as price source |
| WINDING_DOWN | FLATTENING | `flatten_deadline` timer | | cancel all; forced exits |
| WINDING_DOWN | FLATTENING | operator `flatten now` or `kill`, fatal error, data stall | | same |
| WINDING_DOWN | CLOSED | position count reaches zero and no resting orders | | stop heartbeat; reconcile |
| FLATTENING | CLOSED | position count reaches zero | | stop heartbeat; reconcile |
| FLATTENING | CLOSED | 16:00 `market_close` timer with positions still held | only when every remaining position is halted | journal `incident` per carried position; alert |
| CLOSED | IDLE | reconciliation clean | | publish session report |
| CLOSED | LOCKED | reconciliation mismatch, or LOCKED flag set during session | | journal incident; alert |
| LOCKED | IDLE | operator `unlock` with a reason, or the lock period expires at the next trading day (daily) or Monday (weekly) | mismatch incidents require `unlock`, loss-limit locks expire on their own | journal `operator_action` |
| any | FLATTENING | `kill` | | see section 5 |

Transitions not in the table are rejected and journaled as `operator_action`
with `result=rejected`. There is no path back from WINDING_DOWN to ACTIVE
within a session: once entries stop, they stay stopped. Re-activating means
a new session, which PREFLIGHT will refuse after `entry_cutoff`.

---

## 3. Timers

All times are exchange time (America/New_York) and configurable. The
controller arms them at the ACTIVE transition and from a clock source that
PREFLIGHT has already validated for skew.

| Timer | Default | Fires | Action |
|---|---|---|---|
| `entry_open` | 09:45 | guard, not an event | PREFLIGHT may complete into ACTIVE only at or after this time; earlier completion waits |
| `entry_cutoff` | 15:30 | once | ACTIVE to WINDING_DOWN |
| `flatten_deadline` | 15:45 | once | ACTIVE or WINDING_DOWN to FLATTENING |
| `market_close` | 16:00 | once | FLATTENING to CLOSED if only halted positions remain; otherwise journal an incident per position still held and keep trying until 16:00 plus `post_close_grace` |
| `post_close_grace` | 5 minutes | once | hard stop of all exit attempts; carry remaining positions as incidents |
| `heartbeat_interval` | 10 seconds | repeating | write heartbeat; watchdog checks |
| `stall_threshold` | 2 minutes | condition | data stall detector (design.md 6.2) |

Timers are evaluated against the exchange calendar: on an early-close day
(13:00 close) every timer shifts by the same offset, loaded from the calendar
table at PREFLIGHT. Activation on a market holiday fails PREFLIGHT.

Timers fire from the controller's own loop, not from the data feed. A stalled
feed must never stop the flatten deadline from firing.

---

## 4. HALTED_EXPOSURE

Set when the position manager reports a held symbol as halted (from the halt
feed, or inferred when the broker rejects an order with a halt reason, or when
no quote has updated for 60 seconds while the symbol's last trade was within
the LULD band edge). Cleared when the last halted holding resumes or is
exited.

Behavior while set:

| In state | Effect |
|---|---|
| ACTIVE | No new entries in the halted symbol (risk manager halt gate). Other symbols unaffected. Alert operator once per halt (push plus SMS). |
| WINDING_DOWN | Exit rules for the halted symbol are suspended; the position is marked `awaiting_resume`. |
| FLATTENING | The ladder for the halted symbol is paused. On resume: place a limit at the reopening price if it is within `max_exit_slippage` of the pre-halt mark, otherwise start the ladder from the reopening bid. Marketable-limit fallback applies as in any FLATTENING exit. |
| At `market_close` | If still halted, the position carries overnight. Journal `incident` with kind `overnight_carry`, alert, and set a PREFLIGHT item for the next session that requires the operator to acknowledge the carried position before activation. |

On resume the controller treats the first 60 seconds after the reopening
print as a cooldown: it does not re-enter the symbol that day under any
strategy, and it halves `participation_rate` for exits in that symbol because
reopening volume is misleading.

The UI shows HALTED_EXPOSURE as a banner with the symbol, time halted, and
the statement that "flat on deactivate" is best effort while it is set.

---

## 5. Operator commands

| Command | IDLE | PREFLIGHT | ACTIVE | WINDING_DOWN | FLATTENING | CLOSED | LOCKED |
|---|---|---|---|---|---|---|---|
| `activate` | start PREFLIGHT | rejected | rejected | rejected | rejected | rejected | rejected with lock reason |
| `deactivate` | no-op | abort to IDLE | to WINDING_DOWN | no-op | rejected (use `flatten now`) | no-op | no-op |
| `flatten now` | rejected | rejected | to FLATTENING | to FLATTENING | no-op | rejected | rejected |
| `kill` | stop process | abort and stop | to FLATTENING, then stop | same | continue flattening, then stop | stop | stop |
| `unlock <reason>` | no-op | rejected | rejected | rejected | rejected | rejected | to IDLE |
| `acknowledge_carry <symbol>` | allowed | allowed | rejected | rejected | rejected | allowed | allowed |

`kill` is the layer 1 kill switch (design.md 6.3). Its exact sequence:

1. Journal `operator_action kill`.
2. Call `Broker.cancel_all()` and wait up to 5 seconds for acknowledgement.
3. Call `Broker.liquidate_all()` which places marketable limits for every
   position (see `execution.md` section 5). Wait up to `kill_wait` (default
   30 seconds) for fills.
4. Journal remaining positions as incidents.
5. Write a `kill_marker` file next to the journal so the supervisor does not
   restart the process automatically.
6. Exit the process with a non-zero code.

`kill` never waits for the ladder. It trades price for certainty, which is
the point of a kill switch. Layers 2 and 3 (design.md 6.3) are outside this
component and are the fallback when the process cannot run step 2 or 3.

Every command carries an operator identity and arrives over the local control
socket or the UI; the agent process has no access to the control socket
(design.md section 8).

---

## 6. PREFLIGHT checklist

Each item returns pass, fail or warn with a message. Any fail blocks
activation. Warns are shown to the operator and journaled; the operator may
proceed. Items run in parallel where independent; total budget 60 seconds.

| # | Item | Pass criterion | On fail |
|---|---|---|---|
| P1 | Exchange calendar | Today is a trading day; early-close offset loaded | fail |
| P2 | Clock skew | Local clock within 500 ms of the vendor's server time | fail |
| P3 | Data freshness | Last 1-minute bar for the control symbol (default SPY) within 2 minutes of now, or within 2 minutes of 09:30 if before the open | fail |
| P4 | Bar continuity | Control symbol bar count since 09:30 matches the expected count within 2 bars | warn |
| P5 | Reference data age | `reference_daily` refreshed within 24 hours | fail |
| P6 | Broker connectivity | `Broker.account()` succeeds within 5 seconds | fail |
| P7 | Account state | Account not restricted; equity at or above `min_equity` (default 2,000); intraday buying power present and non-null in the payload | fail |
| P8 | Leverage posture | Gross exposure at start equals zero, or equals exactly the acknowledged carried positions | fail |
| P9 | Carried positions acknowledged | Every `overnight_carry` incident from the prior session has an `acknowledge_carry` | fail |
| P10 | Watchlist | `universe_snapshots` has rows for today under the current screener config hash; count between 5 and `max_watchlist` | fail below 5, warn above max |
| P11 | Tradability | Every watchlist symbol is `tradable=true` at the broker as of the latest assets refresh | drop symbol, warn |
| P12 | Config integrity | `risk.yaml` and `strategies.yaml` parse, validate against their schemas, and their hashes match the last approved hashes in the journal | fail |
| P13 | Lock state | Not LOCKED for today or this week | fail with reason |
| P14 | Journal writable | A test event round-trips to Postgres | fail |
| P15 | Alert channel | A test notification reaches the log channel; push and SMS channels report configured | fail on log, warn on push or SMS |
| P16 | Kill switch rehearsal age | Layer 2 kill script last tested within 7 days (paper mode) | warn |
| P17 | Disk and memory | At least 2 GB free disk and 1 GB free memory | warn |

The checklist result is a single `session_state` event with a `preflight`
payload listing every item and its outcome, so the agent's pre-session note
can quote it.

---

## 7. Heartbeat and watchdog

During ACTIVE, WINDING_DOWN and FLATTENING the controller writes a heartbeat
row (timestamp, state, open position count, resting order count, last bar
timestamp seen) every `heartbeat_interval`.

A separate watchdog process, started by the supervisor alongside the
controller, reads the heartbeat:

- Missing for 30 seconds: page the operator (push plus SMS).
- Missing for 30 seconds with open positions recorded in the last heartbeat:
  the watchdog itself calls the layer 2 kill script (`Broker.cancel_all` plus
  `liquidate_all` with its own credentials). The controller, if it comes
  back, will find the positions gone and reconcile.
- Missing for 30 seconds with no open positions: alert only; the supervisor
  restart policy handles it.

The watchdog has no strategy logic and about a hundred lines of code. It is
the one component allowed to be dumb.

---

## 8. Crash recovery

On process start the controller never assumes a clean slate. Sequence:

1. Read the last `session_state` event for today from the journal.
2. If none, or it is CLOSED or IDLE: start in IDLE.
3. If a `kill_marker` exists: start in LOCKED with reason `killed`, do not
   touch the broker, alert.
4. Otherwise reconcile with the broker: fetch positions and open orders.
   Rebuild the position manager from fills in the journal and correct it with
   the broker's positions; the broker is authoritative on quantities, the
   journal on intent. Every difference is journaled as an `incident` with kind
   `reconciliation_drift`.
5. Cancel any resting entry orders found at the broker (we do not know what
   state they were placed under).
6. Verify every open position has a broker-side protective stop; place one if
   missing (`execution.md` section 6).
7. Enter WINDING_DOWN regardless of the state at crash time, re-arm timers for
   the current clock, alert the operator with a summary. The operator may
   `flatten now`; nothing re-enters ACTIVE.

If the crash happened during FLATTENING, step 7 enters FLATTENING instead.

---

## 9. Interfaces

**To the UI** (local HTTP plus server-sent events):

- `GET /state`: current state, HALTED_EXPOSURE flag and symbols, timers with
  time remaining, position count, resting order count, equity, gross exposure,
  daily P&L versus limit, last heartbeat age.
- `GET /preflight`: last checklist result.
- `POST /command` with `{command, args, operator}` for section 5 commands.
- `GET /events`: stream of `session_state`, `incident`, `operator_action`,
  `position_open`, `position_close`.

**To the agent** (read-only Postgres role, design.md 6.5): the journal only.
The agent gets no control socket and no HTTP access to `/command`.

**From the risk manager**: `on_limit_breached(kind)` where kind is one of
`daily_loss`, `weekly_loss`, `consecutive_losses`. Drives the transitions in
section 2.

**From the position manager**: `on_positions_changed(count)`,
`on_halt(symbol)`, `on_resume(symbol, reopen_price)`.

**From the data layer**: `on_stall(seconds)` and `on_stall_cleared()`.

**From the execution adapter**: `on_fatal(error)` for the error classes that
`execution.md` section 9 marks fatal.

---

## 10. Fatal errors

An error is fatal, and moves the session to FLATTENING, when the controller
can no longer trust its own view of the account:

- Broker authentication failure or account restriction mid-session.
- Reconciliation drift detected mid-session (a fill the broker reports that
  the journal cannot match to an order, or a position the journal says is
  closed but the broker holds).
- Journal write failure for more than 10 seconds.
- Risk manager raised an exception while evaluating a candidate (fail closed:
  a broken gate is treated as a breached one).
- Data stall over `stall_threshold` with open positions.

Broker API unavailability is handled differently: FLATTENING is entered, but
the exit attempts will fail, so the controller alerts with the explicit
instruction to use the layer 3 kill switch and keeps retrying exits every 15
seconds until `post_close_grace`.

---

## 11. Test cases

Phase 1 ships the controller with a fake clock, a fake broker
(`execution.md` section 11) and an in-memory journal. Every case below is a
unit test.

| ID | Given | When | Then |
|---|---|---|---|
| SC-01 | IDLE at 09:20, checklist all pass | `activate` | PREFLIGHT completes, waits, enters ACTIVE at 09:45:00 exactly |
| SC-02 | IDLE, P7 reports equity 1,500 | `activate` | PREFLIGHT fails, state IDLE, journal lists P7 as the reason |
| SC-03 | IDLE at 15:31 | `activate` | rejected, reason `after_entry_cutoff` |
| SC-04 | ACTIVE with 2 positions and 1 resting entry | clock reaches 15:30 | WINDING_DOWN, resting entry cancelled, positions untouched |
| SC-05 | WINDING_DOWN with 2 positions | clock reaches 15:45 | FLATTENING, ladder started for both |
| SC-06 | FLATTENING, both positions fill | last fill arrives | CLOSED, heartbeat stopped, reconciliation ran |
| SC-07 | ACTIVE, realized plus unrealized loss reaches 1.5 percent of equity | next bar | WINDING_DOWN, LOCKED-for-today flag set, applied at CLOSED |
| SC-08 | LOCKED for today | `activate` | rejected with reason `daily_loss_lock` |
| SC-09 | LOCKED for today | next trading day 06:00 | IDLE |
| SC-10 | ACTIVE, held symbol halted | `on_halt` | HALTED_EXPOSURE set, alert sent once, other symbols still tradable |
| SC-11 | FLATTENING, one symbol halted | 16:00 | CLOSED with one `overnight_carry` incident, alert sent |
| SC-12 | IDLE next day, carry not acknowledged | `activate` | PREFLIGHT fails on P9 |
| SC-13 | FLATTENING, halted symbol resumes at a price within slippage budget | `on_resume` | limit placed at reopen price within 1 second |
| SC-14 | ACTIVE, no bar for control symbol for 2 minutes, positions open | stall detector fires | FLATTENING, price source switched to broker quotes |
| SC-15 | ACTIVE, no bar for 2 minutes, no positions | stall detector fires | stays ACTIVE with entries blocked, alert sent |
| SC-16 | ACTIVE with positions | `kill` | cancel_all then liquidate_all called in order, kill marker written, process exit code non-zero |
| SC-17 | process start, journal shows ACTIVE at crash, broker holds 1 position with no stop | start | protective stop placed, state WINDING_DOWN, drift incident if quantity differs |
| SC-18 | process start, kill marker present | start | LOCKED, broker not called, alert |
| SC-19 | ACTIVE | `deactivate` then `activate` | WINDING_DOWN, then second command rejected |
| SC-20 | early-close day | PREFLIGHT | timers shifted by 3 hours |
| SC-21 | ACTIVE, heartbeat writer blocked | 30 seconds pass | watchdog pages and calls layer 2 kill since positions are open |
| SC-22 | ACTIVE, risk manager raises an exception | candidate evaluated | FLATTENING with fatal reason `risk_manager_exception` |
| SC-23 | any state | unknown command | rejected, journaled, state unchanged |
| SC-24 | PREFLIGHT, P11 finds one watchlist symbol not tradable | checklist | symbol dropped, warn, activation proceeds |

Property test: for any random sequence of triggers at random times, the
journal's `session_state` events must form a path allowed by the transition
table, and no `order_intent` event may appear after the first FLATTENING
event unless it is an exit.

---

## 12. Configuration

`session.yaml`, loaded at PREFLIGHT, hash recorded.

| Key | Default | Notes |
|---|---|---|
| `entry_open` | `09:45` | exchange time |
| `entry_cutoff` | `15:30` | |
| `flatten_deadline` | `15:45` | |
| `post_close_grace_minutes` | 5 | |
| `heartbeat_interval_seconds` | 10 | |
| `heartbeat_miss_seconds` | 30 | watchdog threshold |
| `stall_threshold_seconds` | 120 | |
| `control_symbol` | `SPY` | for freshness checks |
| `min_equity` | 2000 | Reg T margin threshold |
| `max_watchlist` | 50 | |
| `kill_wait_seconds` | 30 | |
| `resume_cooldown_seconds` | 60 | no re-entry after a halt resumes |
| `scheduled_activation` | null | an exchange time, or null for manual only |
| `alert.push`, `alert.sms`, `alert.log` | channel configs | |

Changes take effect at the next PREFLIGHT only.

## 13. Changelog

- v0.1: initial design. Adds the LOCKED state and the `unlock` and
  `acknowledge_carry` commands, which `design.md` 5.6 implied but did not name.
