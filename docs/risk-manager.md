# Risk Manager Design

Status: draft v0.1, 2026-10-16
Companion to `design.md` sections 2 (C1, C3, C4, C5, C11), 5.4, 5.6, 5.7, 6.4 and 8; `backtester.md` sections 2 and 3; `data-layer.md` section 2.

The risk manager is the one component that can turn a strategy's `Candidate` into an `OrderIntent`. Strategies propose, the risk manager disposes. It is deliberately dull: a fixed chain of pure functions over typed inputs, with every decision journaled, so that no trade can ever be placed that the rules did not explicitly allow, and so that every rejection can be explained after the fact.

---

## 1. Position in the system

```
Strategy.on_bar(ctx) -> [Candidate]
        |
        v
RiskManager.evaluate(candidate, account_state, market_state, session_state)
        |            -> RiskDecision(allow | reject, reason, inputs, size)
        v
OrderIntent (only when allow) -> ExecutionAdapter.place()
```

Three facts the rest of the system relies on:

1. Nothing else constructs an `OrderIntent`. The type's constructor is private to the risk module; the execution adapter refuses an intent whose `decision_id` does not resolve to a journaled `allow`.
2. Exits are also intents. Exit candidates from the position manager pass through a shorter chain (section 4.3) so that an exit is never blocked by an entry rule, but is still sized, journaled and halt-aware.
3. The risk manager never sleeps, retries or waits. It evaluates and returns. Anything stateful (loss counters, cooldowns) is read from and written to `RiskState`, which the journal rebuilds on restart.

---

## 2. The rule chain

Every rule has the signature:

```python
class Rule(Protocol):
    name: str
    def check(self, c: Candidate, s: RiskInputs) -> RuleResult: ...

@dataclass(frozen=True)
class RuleResult:
    rule: str
    allow: bool
    reason: str                 # human readable, stable wording
    inputs: dict[str, Any]      # exactly the values the rule looked at
    size_cap: int | None = None # a rule may cap size instead of rejecting
```

`RiskInputs` is an immutable snapshot assembled once per evaluation: account equity, gross exposure, intraday buying power, open positions, realized and unrealized P&L for the day and week, the current quote and trailing volumes for the symbol, halt status, the clock in exchange time, the session state, and the `RiskState` counters.

The chain runs every rule, not just until the first rejection. A candidate rejected by three rules produces three reasons in the journal, which is what makes the "risk rejection mix" report in `design.md` section 7 meaningful. The decision is `allow` only when every rule allows; the final size is the minimum of all `size_cap` values and the sizing formula in section 3.

Rules are pure: same inputs, same result. No rule reads the clock, the broker or the database directly. That is what makes them trivially testable and what lets the backtester run the exact same chain.

### 2.1 Entry rules, in evaluation order

Order does not affect the decision, only the readability of the journal. Cheap structural checks run first.

| # | Rule | Default (`risk.yaml` key) | Rejects when | Addresses |
|---|---|---|---|---|
| 1 | `session_state` | n/a | session is not ACTIVE | design 5.6 |
| 2 | `time_gate` | `entry_window: ["09:45", "15:30"]` | exchange time outside the window | C11 |
| 3 | `symbol_tradable` | n/a | broker asset record is not `tradable=true` or exchange not in listed set | C9, data-layer 2 |
| 4 | `halt_gate` | `halt_cooldown_min: 15` | symbol halted now, or resumed less than 15 minutes ago | C5 |
| 5 | `spread_gate` | `max_spread_pct: 1.5` | `(ask - bid) / mid * 100 > 1.5`, or quote older than `max_quote_age_s: 5` | C3 |
| 6 | `max_concurrent` | `max_open_positions: 3` | open positions plus pending entry intents already at 3 | |
| 7 | `symbol_cooldown` | `reentry_cooldown_min: 30` | an exit in this symbol closed less than 30 minutes ago | |
| 8 | `one_position_per_symbol` | n/a | already long the symbol or an entry is pending | |
| 9 | `daily_loss_limit` | `daily_loss_pct: 1.5` | day P&L (realized plus unrealized) at or below minus 1.5 percent of start-of-day equity | |
| 10 | `weekly_loss_limit` | `weekly_loss_pct: 4.0` | week-to-date P&L at or below minus 4 percent of start-of-week equity | |
| 11 | `consecutive_loss_brake` | `max_consecutive_losses: 3` | the last 3 closed trades today were all losers | |
| 12 | `risk_per_trade` | `risk_per_trade_pct: 0.5` | sizes the order (section 3); rejects if the resulting size is below `min_shares: 10` | |
| 13 | `max_notional` | `max_position_pct_equity: 10` | caps size so `size * limit_price <= 10 percent of equity` | |
| 14 | `participation_adv` | `max_adv_participation_pct: 0.5` | caps size so `size * limit_price <= 0.5 percent of adv20_dollar` | C4 |
| 15 | `participation_recent` | `max_recent_vol_participation_pct: 2.0` | caps size so `size <= 2 percent of trailing 15-minute share volume` | C4 |
| 16 | `leverage_gate` | `max_gross_exposure_pct: 100` | `gross_exposure + size * limit_price > 100 percent of equity`, or broker intraday buying power minus pending intents would not cover the notional | C1 |
| 17 | `settled_cash_gate` | `account_mode: margin` | only when `account_mode: cash`: notional exceeds settled cash minus pending intents | C2 |
| 18 | `stop_sanity` | `min_stop_distance_ticks: 2`, `max_stop_distance_pct: 8` | stop at or above entry, closer than 2 ticks, or further than 8 percent | |
| 19 | `price_band` | `price_floor: 1.00`, `price_ceiling: 5.00` | limit price outside the universe band (a screener name can drift out intraday) | C12 |

Rules 12 to 16 are the sizing rules. Each returns a `size_cap`; the final size is their minimum. If that minimum is below `min_shares`, the decision is `reject` with reason `size_below_minimum` and the journal shows which cap bound.

### 2.2 Why these defaults

The defaults are for the phase 3 starting account in `design.md` section 9: $5,000 equity, margin account, leverage disabled.

- 0.5 percent risk per trade is $25. Ten consecutive losers cost 5 percent. That is survivable while the fill model is being calibrated.
- 1.5 percent daily loss is three full-risk losers. Hitting it ends the day, which is the point: a system that keeps trading after three losses in thin stocks is usually trading a regime it does not understand.
- 10 percent notional cap is $500. At $2.50 per share that is 200 shares, which is well inside the participation caps for any name that passes the $2M ADV screen.
- 100 percent gross exposure means the account can never owe the broker money intraday, so the intraday margin framework (C1) never binds.

---

## 3. Position sizing

Sizing is derived from risk, never from "how many shares can I afford".

```
risk_dollars     = equity * risk_per_trade_pct / 100
stop_distance    = limit_price - stop_price            # must be > 0 (rule 18)
risk_size        = floor(risk_dollars / stop_distance)

notional_cap     = floor(equity * max_position_pct_equity / 100 / limit_price)
adv_cap          = floor(adv20_dollar * max_adv_participation_pct / 100 / limit_price)
recent_cap       = floor(trailing_15m_volume * max_recent_vol_participation_pct / 100)
leverage_cap     = floor((equity * max_gross_exposure_pct / 100 - gross_exposure - pending_notional) / limit_price)

size = min(risk_size, notional_cap, adv_cap, recent_cap, leverage_cap)
reject if size < min_shares
```

All quantities are whole shares; every division floors. Fractional shares are never used, because partial fills and the participation caps are reasoned about in whole shares and because the broker's fractional handling differs between paper and live.

### 3.1 Worked examples at $5,000 equity

| Case | Limit | Stop | adv20 $ | 15m vol | Gross exp. | risk_size | notional_cap | adv_cap | recent_cap | leverage_cap | Size | Binding |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 2.50 | 2.40 | 8,000,000 | 60,000 | 0 | 250 | 200 | 16,000 | 1,200 | 2,000 | 200 | notional |
| B | 1.20 | 1.17 | 2,500,000 | 15,000 | 0 | 833 | 416 | 104 | 300 | 4,166 | 104 | adv |
| C | 4.80 | 4.50 | 30,000,000 | 200,000 | 4,600 | 83 | 104 | 312 | 4,000 | 83 | 83 | risk and leverage tie |
| D | 3.10 | 3.08 | 5,000,000 | 9,000 | 0 | 1,250 | 161 | 80 | 180 | 1,612 | 80 | adv |
| E | 1.05 | 1.04 | 2,100,000 | 400 | 0 | 2,500 | 476 | 100 | 8 | 4,761 | reject | recent, below min_shares |

Case B is the instructive one: a $1.20 stock with a 3-cent stop allows 833 shares by risk, but the ADV cap holds it to 104. The journal records `participation_adv` as the binding rule. If that rule binds often, the universe is too thin for the account, not the other way round.

Case E shows the recent-volume cap doing its job in a dead tape: 400 shares traded in 15 minutes means we may take 8, which is below `min_shares`, so there is no trade.

### 3.2 Sizing on partial fills

The size above is the intended quantity. If the execution adapter reports a partial fill and the remainder is cancelled, the position manager re-registers the position at the filled quantity and the actual risk is `filled * stop_distance`, which is at or below the intended risk. No re-evaluation is needed for a smaller position. A fill can never exceed the intent because the broker enforces the order quantity.

---

## 4. Equity, P&L and state

### 4.1 Definitions

| Term | Definition |
|---|---|
| `equity` | broker-reported equity at the last account snapshot, adjusted for fills since: cash plus marked positions |
| `start_of_day_equity` | equity recorded at PREFLIGHT; the base for the daily loss limit |
| `start_of_week_equity` | equity at the first PREFLIGHT of the week (Monday or first trading day) |
| `realized_pnl_day` | sum over closed positions today of `(exit_fill - entry_fill) * qty - fees` |
| `unrealized_pnl` | sum over open positions of `(mark - entry_fill) * qty`, mark is the bid (conservative for longs) |
| `day_pnl` | `realized_pnl_day + unrealized_pnl` |
| `gross_exposure` | sum over open positions of `qty * mark` plus notional of pending entry intents |
| `pending_notional` | notional of allowed entry intents not yet filled or cancelled |

Marking at the bid rather than the mid is intentional. In a 1.5 percent spread the difference is 0.75 percent of position value, and using the bid means the daily loss limit trips slightly early rather than slightly late.

### 4.2 RiskState

Mutable counters, persisted as journal events and rebuilt from them:

- `consecutive_losses_today`
- `last_exit_ts_by_symbol`
- `daily_limit_hit` and `weekly_limit_hit` flags with timestamps
- `start_of_day_equity`, `start_of_week_equity`

On process restart, the risk manager replays today's and this week's `position_close` and `session_state` events to rebuild these before accepting any candidate. PREFLIGHT fails if the rebuild does not reconcile with broker positions.

### 4.3 Exit chain

Exit candidates come from the position manager (stop hit, target hit, exit signal, max hold time of 90 minutes, or FLATTENING). They pass through:

| Rule | Behaviour |
|---|---|
| `position_exists` | reject if no open position matches |
| `halt_gate_exit` | if halted, defer rather than reject: the intent is parked and resubmitted on resume (design 5.6 HALTED_EXPOSURE) |
| `exit_size` | size is the full open quantity; partial exits are not used in v1 |
| `exit_price_sanity` | limit must be within `max_exit_slippage_pct` of the bid unless the session is FLATTENING, where the marketable-limit allowance in `backtester.md` 2 applies |

No loss limit, time gate or participation rule ever blocks an exit. Getting flat is always allowed.

---

## 5. What happens when a limit is hit

| Event | Risk manager action | Session effect |
|---|---|---|
| `daily_loss_limit` trips | set `daily_limit_hit`; all further entry candidates rejected with `daily_limit_hit` | emits `LimitHit(daily)`; session controller moves ACTIVE to WINDING_DOWN, then FLATTENING at the deadline or immediately if `flatten_on_daily_limit: true` (default true); activation locked for the rest of the day |
| `weekly_loss_limit` trips | set `weekly_limit_hit` | same as daily, plus PREFLIGHT refuses activation until the next trading week |
| `consecutive_loss_brake` trips | entries rejected for the rest of the session | no state change; positions keep running their exits |
| `leverage_gate` would be breached by a fill discrepancy | impossible by construction, but if the reconciliation at CLOSED finds gross exposure above 100 percent, it is an incident and activation is locked until an operator clears it | |

Loss limits are evaluated on `day_pnl` including unrealized, so the limit can trip while positions are still open. That is deliberate: the system stops adding risk when it is already in the hole, and the open positions exit through their own rules or the flatten.

Limits are never raised mid-session. A change to `risk.yaml` (section 6) takes effect at the next PREFLIGHT.

---

## 6. Configuration and change path

Two files, different owners, different rules:

| File | Contains | Who changes it | Takes effect |
|---|---|---|---|
| `risk.yaml` | every value in section 2.1 and the account mode | a human, through a pull request they review themselves; the agent may propose but never merges | next PREFLIGHT |
| `strategies.yaml` | strategy parameters | agent-drafted PR with attached walk-forward backtest; human merges | next PREFLIGHT |

Each value in `risk.yaml` is declared with a name, type, default, allowed range and a one-line rationale. The loader rejects a file with a value outside its allowed range, which stops a typo from setting `risk_per_trade_pct: 5.0`. The allowed ranges themselves are in code, not config, and widening one is a code change.

```yaml
# risk.yaml (excerpt)
account_mode: margin                  # margin | cash
risk_per_trade_pct: 0.5               # range 0.1 .. 1.0
max_position_pct_equity: 10           # range 1 .. 25
max_open_positions: 3                 # range 1 .. 5
daily_loss_pct: 1.5                   # range 0.5 .. 3.0
weekly_loss_pct: 4.0                  # range 1.0 .. 8.0
max_consecutive_losses: 3             # range 2 .. 5
max_spread_pct: 1.5                   # range 0.5 .. 3.0
max_quote_age_s: 5
max_adv_participation_pct: 0.5        # range 0.1 .. 1.0
max_recent_vol_participation_pct: 2.0 # range 0.5 .. 5.0
max_gross_exposure_pct: 100           # range 10 .. 100, never above 100
entry_window: ["09:45", "15:30"]
halt_cooldown_min: 15
reentry_cooldown_min: 30
min_shares: 10
min_stop_distance_ticks: 2
max_stop_distance_pct: 8
flatten_on_daily_limit: true
```

The config hash recorded at PREFLIGHT covers both files, so every journaled decision is traceable to the exact rules that made it.

---

## 7. Journaling

Every `evaluate` call emits one `risk_decision` event:

```json
{
  "type": "risk_decision",
  "ts": "2026-10-16T14:02:11.004Z",
  "session_id": "...",
  "config_hash": "...",
  "decision_id": "...",
  "candidate_id": "...",
  "symbol": "XYZ",
  "allow": false,
  "size": 0,
  "rules": [
    {"rule": "spread_gate", "allow": false, "reason": "spread 2.1% > 1.5%", "inputs": {"bid": 2.38, "ask": 2.43, "mid": 2.405, "quote_age_s": 1.2}},
    {"rule": "participation_adv", "allow": true, "size_cap": 160, "inputs": {"adv20_dollar": 4000000, "limit": 2.43}}
  ],
  "equity": 5012.40,
  "gross_exposure": 486.00,
  "day_pnl": -31.20
}
```

Allowed decisions carry the same shape with `allow: true` and the binding rule named in a `binding_rule` field. The post-session report groups rejections by rule and allowed trades by binding rule.

---

## 8. Invariants

Properties that must hold after every evaluation and every fill, checked by assertions in the live process and by property-based tests:

1. `gross_exposure <= equity * max_gross_exposure_pct / 100` after any allowed entry, assuming fills at or below the limit price.
2. No allowed entry has `size * stop_distance > equity * risk_per_trade_pct / 100`.
3. No allowed entry exists while `daily_limit_hit` or `weekly_limit_hit` is set.
4. No two allowed, unfilled entry intents share a symbol.
5. Count of open positions plus pending entry intents never exceeds `max_open_positions`.
6. An exit intent is never rejected for any reason other than `position_exists` or a halt deferral.
7. Every `OrderIntent` references exactly one journaled `risk_decision` with `allow: true`.
8. The rule chain is deterministic: identical `RiskInputs` and `Candidate` yield byte-identical `RiskDecision` (ignoring `decision_id` and `ts`).

Property-based testing (Hypothesis) generates random candidates and account states and asserts 1 to 5 and 8 directly. Invariant 6 is tested by generating every rejection condition for entries and asserting that the same conditions do not reject an exit. Invariant 7 is enforced by the type system and checked in the execution adapter's tests.

---

## 9. Test cases

Unit tests, one rule at a time, with table-driven inputs:

| ID | Rule | Setup | Expected |
|---|---|---|---|
| RM-01 | time_gate | 09:44:59 ET | reject `before_entry_window` |
| RM-02 | time_gate | 09:45:00 ET | allow |
| RM-03 | time_gate | 15:30:01 ET | reject `after_entry_cutoff` |
| RM-04 | halt_gate | resumed 14 min ago | reject `halt_cooldown` |
| RM-05 | halt_gate | resumed 16 min ago | allow |
| RM-06 | spread_gate | bid 2.00 ask 2.03 | allow (1.49 percent) |
| RM-07 | spread_gate | bid 2.00 ask 2.04 | reject (1.98 percent) |
| RM-08 | spread_gate | quote age 6 s | reject `stale_quote` |
| RM-09 | max_concurrent | 2 open, 1 pending | reject |
| RM-10 | symbol_cooldown | exit 29 min ago | reject; 31 min ago allow |
| RM-11 | daily_loss_limit | start equity 5000, day_pnl -75.00 | reject (exactly at limit) |
| RM-12 | daily_loss_limit | day_pnl -74.99 | allow |
| RM-13 | weekly_loss_limit | week_pnl -200 on 5000 | reject |
| RM-14 | consecutive_loss_brake | closes today: L, L, L | reject; L, L, W, L allow |
| RM-15 | sizing | case A in 3.1 | size 200, binding `max_notional` |
| RM-16 | sizing | case B | size 104, binding `participation_adv` |
| RM-17 | sizing | case E | reject `size_below_minimum`, binding `participation_recent` |
| RM-18 | leverage_gate | equity 5000, gross 4700, candidate 200 x 2.50 | reject |
| RM-19 | leverage_gate | equity 5000, gross 4400, candidate 200 x 2.50 | allow, cap 240 so size 200 |
| RM-20 | settled_cash_gate | account_mode cash, settled 300, notional 500 | reject; in margin mode allow |
| RM-21 | stop_sanity | stop >= limit | reject; stop 9 percent below | reject |
| RM-22 | price_band | limit 5.01 | reject; 0.99 reject; 1.00 and 5.00 allow |
| RM-23 | exit chain | all entry-blocking conditions true, exit candidate | allow |
| RM-24 | exit chain | symbol halted | deferred, not rejected; resubmitted on resume |
| RM-25 | multi-reason | spread 2 percent and 3 open positions | both rules in journal, allow false |
| RM-26 | state rebuild | replay journal with 3 losses today | brake active after restart |
| RM-27 | config loader | `risk_per_trade_pct: 5.0` | load fails with range error |
| RM-28 | config loader | `max_gross_exposure_pct: 150` | load fails |
| RM-29 | determinism | same inputs twice | identical decision minus id and ts |

Integration tests run the chain inside the backtester (`backtester.md` section 1) over a synthetic day and assert the invariants in section 8 hold at every event.

---

## 10. Open questions

1. Whether to allow partial exits (scale-outs) in v2. Not in v1; it complicates the one-position-per-symbol invariant.
2. Whether the daily loss limit should include fees. Current definition does, through `realized_pnl_day`.
3. Whether `recent_cap` should use 15 minutes or a configurable window. Fixed at 15 for v1 to match the market impact formula in `backtester.md` section 3.

## 11. Changelog

- v0.1: initial design.
