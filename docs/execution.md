# Execution Design

Status: draft v0.1, 2026-10-16
Companion to `design.md` sections 5.5, 5.7 and C1, `session-controller.md`
sections 5, 8 and 10, `backtester.md` sections 2 and 3 (the `BacktestBroker`
implements the same interface), `data-layer.md` section 2 (quotes schema).

The execution layer is the only code that talks to a broker. It has one
interface, `Broker`, and three implementations: `BacktestBroker`,
`AlpacaPaperBroker`, `AlpacaLiveBroker`. Everything above it, including the
risk manager and the session controller, cannot tell which one it is talking
to. That is what makes paper results meaningful and what lets a crash be
reconciled instead of guessed at.

Two rules the rest of the system depends on:

1. **Only `OrderIntent` objects from the risk manager become orders.** The
   execution adapter has no public method that takes a symbol and a quantity.
2. **Every order carries a client order id we generated**, so a retry after a
   timeout can never place a duplicate.

---

## 1. Broker protocol

```python
class Broker(Protocol):
    name: str                       # "backtest", "alpaca-paper", "alpaca-live"
    mode: Literal["backtest", "paper", "live"]

    # account and state
    def account(self) -> AccountSnapshot: ...
    def positions(self) -> list[PositionSnapshot]: ...
    def orders(self, status: OrderStatusFilter = "open") -> list[OrderSnapshot]: ...
    def is_tradable(self, symbol: str) -> bool: ...
    def clock(self) -> BrokerClock: ...              # broker's view of market open/close and server time

    # orders
    def place(self, intent: OrderIntent) -> OrderSnapshot: ...
    def replace(self, client_order_id: str, limit_price: Decimal, qty: int | None = None) -> OrderSnapshot: ...
    def cancel(self, client_order_id: str) -> None: ...
    def cancel_all(self) -> int: ...                  # returns count cancelled
    def liquidate_all(self) -> list[OrderSnapshot]: ... # marketable limits for every position

    # streaming
    def subscribe(self, on_update: Callable[[OrderUpdate], None]) -> None: ...
```

`place`, `replace` and `cancel` are synchronous requests that return the
broker's acknowledgement. Fills, partial fills, cancels and rejects arrive
through `subscribe` as `OrderUpdate` events. The adapter also polls `orders()`
every 5 seconds as a safety net against a dropped stream, and reconciles
(section 8).

### Broker-neutral models

**AccountSnapshot**

| field | type | source at Alpaca (post June 2026) |
|---|---|---|
| `equity` | Decimal | `equity` |
| `cash` | Decimal | `cash` |
| `settled_cash` | Decimal or None | derived: `cash` minus unsettled proceeds where the broker exposes them; None in margin mode where it does not apply |
| `intraday_buying_power` | Decimal | the post-PDT intraday buying power field; its exact name is confirmed by the phase 0 script (Q1) |
| `gross_exposure` | Decimal | computed by the adapter as the sum of absolute position market values; used by the leverage gate |
| `multiplier` | int | `multiplier` (1 under 2,000 equity, otherwise up to 4) |
| `restricted` | bool | `trading_blocked` or `account_blocked` or any restriction flag |
| `status` | str | `status` |
| `as_of` | datetime | adapter timestamp |

The leverage gate (design.md 5.4) reads `gross_exposure` and `equity` only.
It does not read `intraday_buying_power`, because our rule is stricter than
the broker's: exposure may never exceed 100 percent of equity regardless of
how much the broker would lend.

**PositionSnapshot**: `symbol`, `qty`, `avg_entry_price`, `market_value`,
`unrealized_pnl`, `as_of`.

**OrderIntent** (produced only by the risk manager):

| field | notes |
|---|---|
| `client_order_id` | `st-<session_id>-<seq>`; unique per session, monotonic |
| `symbol`, `side` (`buy`/`sell`), `qty` | |
| `kind` | `entry`, `exit`, `protective_stop`, `flatten`, `liquidate` |
| `limit_price` | required for every kind except `protective_stop` which carries `stop_price` and `stop_limit_price` |
| `time_in_force` | `day` always |
| `ttl_seconds` | 45 for entries, None for exits (ladder manages them), None for stops |
| `max_slippage_pct` | the budget the ladder may consume, from risk config |
| `reference_price` | the price the candidate was evaluated at, for slippage accounting |
| `position_id` | for exits and stops |
| `candidate_id`, `strategy`, `strategy_version`, `risk_decision_id` | journal links |

**OrderSnapshot**: `client_order_id`, `broker_order_id`, `status`,
`filled_qty`, `filled_avg_price`, `limit_price`, `stop_price`,
`submitted_at`, `updated_at`, `reject_reason`.

---

## 2. Order lifecycle

```
INTENT -> SUBMITTED -> ACKED -> PARTIALLY_FILLED -> FILLED
                 |        |            |
                 |        +------------+--> CANCELLED
                 |        +------------+--> EXPIRED      (ttl or day end)
                 +--> REJECTED                           (broker refused)
                 +--> UNKNOWN                            (timeout, see 8)
```

| State | Set when | Journal event |
|---|---|---|
| INTENT | risk manager emits the intent | `order_intent` |
| SUBMITTED | adapter sent the request | `order_intent` with `submitted_at` |
| ACKED | broker returned an id | `order_ack` |
| PARTIALLY_FILLED | fill update with `filled_qty` under `qty` | `fill` per update |
| FILLED | `filled_qty` equals `qty` | `fill` |
| CANCELLED | cancel confirmed, including ttl expiry we requested | `cancel` |
| EXPIRED | broker expired it at day end | `cancel` with `reason=expired` |
| REJECTED | broker refused | `order_ack` with `reject_reason` |
| UNKNOWN | no response within `ack_timeout` | `incident` kind `order_unknown` until resolved |

A partially filled order that is then cancelled ends CANCELLED with
`filled_qty` greater than zero; the position manager owns the filled part.

---

## 3. Entry pricing

Given a candidate with `reference_price` R and the current quote (bid B,
ask A):

- limit L = min(A + 1 tick, R × (1 + `entry_max_slippage_pct`)), default
  budget 0.3 percent.
- If A is already above R × (1 + budget), the risk manager rejects the
  candidate before it becomes an intent (spread gate plus slippage gate). The
  adapter never widens L on its own.
- Tick is 0.01 above 1.00 (our floor is 1.00, so sub-penny ticks never apply).
- `ttl_seconds` 45. At expiry the adapter cancels; any filled part stays as a
  position and the risk manager re-evaluates the position at its actual size.
- Entries are never replaced upward. One shot, then the candidate is gone.
  Chasing is a strategy decision, and the strategy may emit a new candidate
  after the per-symbol cooldown.

---

## 4. Exit ladder

Exits (strategy exit signal, max hold time, WINDING_DOWN management,
FLATTENING) all use the same ladder:

1. Place sell limit at the current bid B0. Record `ladder_start`.
2. Every `ladder_step_seconds` (default 20) with unfilled quantity remaining:
   `replace` the limit one tick lower.
3. Stop stepping when the limit would fall below
   B0 × (1 minus `exit_max_slippage_pct`), default 1.0 percent. Hold at that
   price.
4. Outside FLATTENING: hold and alert the operator (`exit_ladder_exhausted`).
   The protective stop remains at the broker as the backstop.
5. In FLATTENING only: after the ladder is exhausted, or immediately if fewer
   than `flatten_minutes_left` (default 3) minutes remain before
   `market_close`, replace with a marketable limit at B minus
   `marketable_offset_pct` (default 2 percent). A marketable limit, not a
   market order, so a crossed or empty book cannot fill at an absurd price.

Each `replace` keeps the same client order id lineage: the adapter records
`replaced_by` on the old snapshot and the new snapshot carries
`client_order_id` with a `-r<n>` suffix. Fills on any rung are attributed to
the same position.

With 1-minute bars the backtester approximates rung timing as up to three
rungs per bar (backtester.md section 2), which matches 20-second steps.

---

## 5. liquidate_all and kill

`liquidate_all` is what `kill` and the watchdog call. It skips the ladder:
for each position, cancel any resting exit, then place a marketable limit at
bid minus `marketable_offset_pct`, all in parallel, and return the snapshots.
It does not wait for fills; the caller decides how long to wait.

`cancel_all` cancels every open order of ours and also any open order on the
account that we do not recognize, journaling the latter as an incident. In
paper and live, "ours" is determined by the client order id prefix.

---

## 6. Protective stops

Within 1 second of the first fill on an entry (and again after each
additional partial fill, by replacing the stop's quantity), the adapter places
a broker-side stop-limit sell:

- `stop_price` from the candidate's stop (risk manager computed size from it).
- `stop_limit_price` = stop_price × (1 minus `stop_limit_gap_pct`), default 3
  percent, so a gap through the stop still leaves a resting order that can
  fill rather than a market order into a vacuum.
- `kind=protective_stop`, same `position_id`.

The stop is the backstop for a process crash, not the primary exit. When the
ladder begins for a position, the stop is cancelled first, then the sell limit
is placed, in that order, so the broker never holds two sells for the same
shares. If the stop triggers during the ladder's placement window (a race),
the ladder order is cancelled on the next reconciliation pass and the fill is
attributed normally.

If the stop placement fails twice, the position is exited immediately via the
ladder and an incident is journaled. We never hold an unprotected position for
more than 10 seconds.

---

## 7. Partial fills

- A partial fill on an entry creates or grows the position immediately; the
  position manager recomputes risk dollars on the real size, and the risk
  manager may emit a `reduce` if the partial pushed something out of bounds
  (it cannot, by construction, since risk was sized on the full quantity, but
  the check is cheap).
- Protective stop quantity is replaced to match filled quantity.
- A partial fill on an exit leaves the remainder in the ladder. Average exit
  price is tracked per rung for slippage reporting.
- The journal stores every fill as its own `fill` event with price, quantity,
  rung and timestamp. P&L is computed from fills, never from order snapshots.

---

## 8. Idempotency, timeouts and reconciliation

**Client order ids** are generated before the request. If `place` times out
(`ack_timeout`, default 3 seconds), the adapter does not retry blindly. It
queries `orders()` filtered by that client id:

- found: adopt the snapshot, continue.
- not found after 2 queries 1 second apart: mark the intent REJECTED with
  reason `timeout_unplaced` and let the caller decide. Never re-send with the
  same id, never re-send with a new id automatically.

**Reconciliation pass** every 5 seconds and on every stream reconnect:

1. Fetch open orders and positions.
2. For every broker order with our prefix not known locally: adopt it and
   journal `incident` kind `orphan_order`.
3. For every local open order not at the broker: query by id; if gone, mark
   CANCELLED or FILLED from the broker's terminal snapshot.
4. Positions: broker quantity wins. A difference journals
   `reconciliation_drift` and, mid-session, is fatal to the session
   (`session-controller.md` section 10).

**Stream health**: if no stream message (including heartbeats) for 30
seconds, reconnect; while disconnected the poll interval drops to 2 seconds.

---

## 9. Error taxonomy

| Class | Examples | Adapter action | Session effect |
|---|---|---|---|
| `Transient` | HTTP 429, 5xx, connection reset | retry with backoff 0.5, 1, 2 seconds, max 3 | none unless exhausted, then `BrokerUnavailable` |
| `BrokerUnavailable` | retries exhausted, DNS failure | raise | FLATTENING with layer 3 alert; keep retrying exits every 15 seconds |
| `OrderRejected` | insufficient buying power, symbol not tradable, price outside collar, halted | mark REJECTED with reason | logged; a halt reason sets HALTED_EXPOSURE for held symbols; three `insufficient buying power` rejects in a session is fatal since our leverage gate should make it impossible |
| `AuthFailure` | 401, 403 | raise | fatal |
| `AccountRestricted` | `trading_blocked` true on any account poll | raise | fatal |
| `RateLimited` | 429 with retry-after | honor retry-after, shed non-critical calls (account polls) first | none |
| `Inconsistent` | fill for unknown order, negative position | journal incident | fatal mid-session |

Rate limiting: a token bucket per endpoint class sized at 80 percent of the
broker's published limit, with exits and cancels drawing from a reserved
bucket that account polls cannot drain.

---

## 10. Alpaca adapter

- **Endpoints**: paper and live are different hosts and different key pairs.
  The adapter refuses to start if the configured mode and the key pair's
  endpoint disagree (a paper key against the live host or vice versa). Keys
  for both modes never live on the same host (design.md 6.5).
- **Account fields**: read `equity`, `cash`, `multiplier`, the intraday
  buying power field, `trading_blocked`, `account_blocked`, `status`. The
  day-trade era fields (`daytrading_buying_power`, `daytrade_count`,
  `pattern_day_trader`) were deprecated June 3 and removed July 6, 2026; the
  adapter treats their presence as a warning that the SDK is stale and never
  reads them. The phase 0 script dumps the live field list to pin the name.
- **Tradability**: `is_tradable` reads the cached assets list (refreshed at
  PREFLIGHT and every 4 hours) and requires `status=active`, `tradable=true`,
  exchange in the listed set. OTC symbols are `tradable=false` at Alpaca and
  are refused before any request is built.
- **Orders**: limit and stop-limit with `time_in_force=day` and
  `client_order_id`. `extended_hours=false` always. Replace via the order
  replace endpoint; if the broker rejects a replace because the order just
  filled, treat as FILLED on the next reconciliation.
- **Stream**: the trade updates websocket for fills and status; market data
  comes from the data layer, not from this adapter.
- **Fees**: the adapter does not compute fees; the fee table
  (backtester.md section 6) does, from fills, and reconciliation against the
  broker's activity report happens at CLOSED.
- **Clock**: `clock()` wraps the broker clock endpoint; PREFLIGHT compares it
  to local time for P2.

---

## 11. Fake broker for tests

`FakeBroker` implements `Broker` in memory with a scripted market:

- A quote tape the test supplies (`(ts, bid, ask, bid_size, ask_size)`).
- Fill rules identical to `BacktestBroker` at the realistic pessimism level,
  so unit tests and backtests agree on what a fill is.
- Fault injection: `fail_next(n, error_class)`, `delay_ack(seconds)`,
  `drop_stream()`, `inject_orphan_order()`, `set_restricted()`,
  `halt(symbol)`, `resume(symbol, price)`.
- Full recording of every call for assertions.

`BacktestBroker` is `FakeBroker` driven by the replayer instead of a test.

---

## 12. Test cases

| ID | Given | When | Then |
|---|---|---|---|
| EX-01 | intent buy 500 at R=2.00, quote 1.99/2.01 | `place` | limit min(2.02, 2.006) rounded down to the tick, so 2.00; see note below |
| EX-02 | intent buy, ask 2.03, R=2.00 | risk manager evaluates | rejected before intent (slippage gate), adapter never called |
| EX-03 | entry acked, no fill for 45 seconds | ttl | cancel sent, order CANCELLED, no position |
| EX-04 | entry fills 200 of 500 then ttl | ttl | remainder cancelled, position of 200, stop placed for 200 |
| EX-05 | entry fill | within 1 second | protective stop-limit placed with stop at candidate stop and limit 3 percent lower |
| EX-06 | stop placement fails twice | second failure | ladder exit started, incident journaled |
| EX-07 | exit ladder, bid 2.10, no fills | 20, 40, 60 seconds | limits 2.10, 2.09, 2.08, 2.07 in order via replace |
| EX-08 | ladder reaches 1 percent below start, not FLATTENING | next step due | holds price, alert `exit_ladder_exhausted`, stop still at broker |
| EX-09 | same, in FLATTENING | ladder exhausted | marketable limit at bid minus 2 percent |
| EX-10 | FLATTENING, 2 minutes to close, ladder just started | step | marketable limit immediately |
| EX-11 | `place` times out, order exists at broker | timeout | adopted from `orders()` query, no duplicate sent |
| EX-12 | `place` times out, order absent at broker | two queries | REJECTED `timeout_unplaced`, nothing re-sent |
| EX-13 | broker returns 429 three times then 200 | `place` | backoff 0.5, 1, 2 seconds, then success |
| EX-14 | broker returns 5xx four times | `place` | `BrokerUnavailable` raised |
| EX-15 | account poll shows `trading_blocked` | reconciliation | `AccountRestricted`, controller notified fatal |
| EX-16 | broker holds an order with our prefix unknown locally | reconciliation | adopted, `orphan_order` incident |
| EX-17 | broker position 300, local 500 | reconciliation | `reconciliation_drift` incident, fatal mid-session |
| EX-18 | paper key configured with live host | start | adapter refuses to start |
| EX-19 | symbol with `tradable=false` | risk manager asks `is_tradable` | false, candidate rejected |
| EX-20 | two positions, `liquidate_all` | call | two marketable limits placed in parallel, resting exits cancelled first, returns within 1 second |
| EX-21 | position with protective stop, ladder starts | start | stop cancelled before sell limit placed, never two sells resting |
| EX-22 | stop triggers while ladder order is being placed | next reconciliation | ladder order cancelled, fill attributed to position, P&L from fills |
| EX-23 | stream silent 30 seconds | watchdog | reconnect, poll interval 2 seconds meanwhile |
| EX-24 | three `insufficient buying power` rejects | third | fatal (leverage gate should have prevented them) |

Note on EX-01: the entry rule is min(ask plus one tick, R times 1.003), then
rounded down to the tick. With ask 2.01 and R 2.00 the cap is 2.006, so the
limit is 2.00, which is below the ask and will not fill immediately. That is
intended: the 0.3 percent budget is the budget. The test asserts 2.00.

---

## 13. Configuration

`execution.yaml`, loaded at PREFLIGHT, hash recorded.

| Key | Default | Notes |
|---|---|---|
| `entry_max_slippage_pct` | 0.3 | over reference price |
| `entry_ttl_seconds` | 45 | |
| `exit_max_slippage_pct` | 1.0 | ladder budget below starting bid |
| `ladder_step_seconds` | 20 | |
| `marketable_offset_pct` | 2.0 | FLATTENING and liquidate only |
| `flatten_minutes_left` | 3 | skip ladder when this close to market close |
| `stop_limit_gap_pct` | 3.0 | |
| `stop_place_deadline_seconds` | 1 | after entry fill |
| `ack_timeout_seconds` | 3 | |
| `reconcile_interval_seconds` | 5 | 2 while stream is down |
| `stream_silence_seconds` | 30 | |
| `rate_limit_fraction` | 0.8 | of published broker limit |
| `assets_refresh_hours` | 4 | |
| `mode` | `paper` | `backtest`, `paper`, `live`; must match key pair |

## 14. Changelog

- v0.1: initial design. Resolves the entry pricing rule precisely (min of ask
  plus a tick and the slippage cap, rounded down), names the `liquidate` and
  `flatten` intent kinds, and defines the fake broker's fault injection API.
