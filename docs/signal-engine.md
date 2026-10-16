# Signal Engine Design

Status: draft v0.1, 2026-10-16
Companion to `design.md` sections 3, 5.3, 5.4 and 5.7; `backtester.md` sections 1 and 2; `data-layer.md` sections 2 and 5.

The signal engine turns market data into ranked trade candidates. It never
creates an order. A `Candidate` is a proposal with its evidence attached; the
risk manager decides whether it becomes an `OrderIntent`. The engine runs
identically in backtest, paper and live because it only ever reads through the
`MarketContext` and only ever writes `Candidate` and `ExitSignal` objects.

---

## 1. Responsibilities and boundaries

The engine owns:

- The `Strategy` protocol and the registry of enabled strategies.
- The `MarketContext` read API, including the look-ahead guard.
- Indicator computation (VWAP, relative volume, opening range, slopes).
- Candidate ranking and conflict resolution across strategies.
- Exit signal generation for open positions.

The engine does not own: sizing, any risk rule, order placement, position
accounting, or the session clock. Those belong to the risk manager, execution
adapter, position manager and session controller respectively.

---

## 2. Strategy protocol

```python
class Strategy(Protocol):
    name: str                       # stable identifier, snake_case, e.g. "orb_delayed"
    version: str                    # semver; bump on any logic change
    params: StrategyParams          # pydantic model, validated at load

    def warmup_bars(self) -> int: ...
    def on_bar(self, ctx: MarketContext) -> list[Candidate]: ...
    def on_quote(self, ctx: MarketContext) -> list[Candidate]: ...   # default: return []
    def exit_rule(self, position: Position, ctx: MarketContext) -> ExitSignal | None: ...
```

Rules for implementations:

- Pure with respect to the context: given the same `ctx` and params, the same
  output. No wall-clock reads, no network, no file I/O, no module-level state.
  Per-symbol internal state (such as an opening range) is allowed only inside
  the strategy instance and must be rebuilt from `ctx` on restart.
- `on_bar` is called once per completed 1-minute bar per watchlist symbol, in
  symbol order, with `ctx.symbol` set. `on_quote` is called on quote updates
  for symbols the strategy has subscribed to via `params.quote_symbols`, and
  is optional; the starter strategies do not use it.
- `exit_rule` is called by the position manager on each bar for each open
  position owned by this strategy. It may return `None` (hold) or an
  `ExitSignal`. The position manager also enforces the max hold time (default
  90 minutes) and the stop, regardless of what `exit_rule` says.
- A strategy that raises is disabled for the rest of the session and an
  `incident` event is journaled. One bad strategy never stops the session.

### 2.1 Parameters

```python
class StrategyParams(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")
    quote_symbols: tuple[str, ...] = ()

    def params_hash(self) -> str:
        return sha256(self.model_dump_json(sort_keys=True)).hexdigest()[:16]
```

Each strategy subclasses `StrategyParams` with typed fields, defaults and
`Field(ge=..., le=...)` ranges. `strategies.yaml` holds one entry per enabled
strategy: name, version, params. Loading fails on unknown fields, out-of-range
values or a version string that does not match the code. The tuple
`(name, version, params_hash)` is stamped on every `Candidate` and is what the
journal and reports group by.

---

## 3. MarketContext API

`MarketContext` is the only read path to market data. One instance per session
is shared by all strategies; `ctx.symbol` is set before each call.

| Method | Returns | Notes |
|---|---|---|
| `now()` | aware datetime (UTC) | The current clock. In backtest this is the replay clock, never the wall clock. |
| `now_et()` | aware datetime (ET) | Convenience for time-of-day rules. |
| `bars(symbol, n, include_flagged=False)` | last `n` completed 1-minute bars, oldest first | Excludes bars whose quality bitmask is non-zero unless asked. Never includes the bar currently forming. |
| `daily(symbol, n)` | last `n` completed daily bars | Prior sessions only; today's partial day is never present. |
| `quote(symbol)` | `Quote(bid, ask, bid_size, ask_size, ts)` or `None` | `None` if no quote within `stale_quote_seconds` (default 60). |
| `spread_pct(symbol)` | float or `None` | `(ask - bid) / mid`. |
| `vwap(symbol)` | float or `None` | Session VWAP from 09:30 over unflagged bars (section 6). |
| `rel_volume(symbol, minutes)` | float or `None` | Volume in the trailing window divided by the 20-session average volume for the same clock window. |
| `opening_range(symbol, minutes)` | `(high, low, volume)` or `None` | `None` until `minutes` after 09:30. |
| `slope(symbol, minutes)` | float or `None` | Least-squares slope of closes over the window, as a fraction of the first close per minute. |
| `index_return(symbol, minutes)` | float or `None` | Same as a stock; used for the small-cap proxy (default `IWM`). |
| `is_halted(symbol)` | bool | |
| `last_halt_age(symbol)` | timedelta or `None` | |
| `staleness(symbol)` | timedelta | Time since the last bar. |
| `flagged_count(symbol, n)` | int | Flagged bars dropped from the last `n`, for the input snapshot. |
| `reference(symbol)` | `ReferenceDaily` row for the prior session | adv20_dollar, spread_pct_est, halt_count_10d, float_shares, pump_score. |

### 3.1 Look-ahead guard

Every method takes its time bound from `now()`. Internally, `bars` is a
slice of a per-symbol array indexed by bar timestamp with an upper bound of
`now() - 1 minute` (a bar whose open time is `now() - 1 minute` has just
completed). A request with an explicit timestamp past `now()` raises
`LookAheadError`. In backtest the replayer advances `now()` only after all
events at the prior timestamp have been delivered. The guard is tested, not
assumed (section 9).

### 3.2 Warm-up

A strategy declares `warmup_bars()`. The engine does not call `on_bar` for a
symbol until that many unflagged bars exist for the session, except that
`daily()` is available from the first bar because it reads prior sessions.
Indicators return `None` rather than a partial value when their window is not
full, and strategies must treat `None` as "no signal".

---

## 4. Candidate schema

```python
class Candidate(BaseModel, frozen=True):
    candidate_id: UUID               # new per emission; correlates journal rows
    session_id: UUID
    ts: datetime                     # ctx.now() at emission
    symbol: str
    side: Literal["long"]            # v1 is long only
    strategy: str
    strategy_version: str
    params_hash: str
    reference_price: float           # last trade or mid the signal was computed against
    limit_price: float               # suggested entry limit; risk manager may lower, never raise
    stop_price: float                # initial protective stop; placed broker-side after fill
    target_price: float | None       # None for strategies that exit by rule only
    confidence: float                # 0 to 1, strategy-specific calibration (section 5)
    expected_hold: timedelta         # informs the position manager, not a hard limit
    expected_edge_pct: float         # (target - limit) / limit minus spread_pct, or a strategy estimate
    spread_pct: float | None
    inputs: dict[str, Any]           # the input snapshot (4.1)
    notes: str                       # one line, human readable, for the advisory card
```

Field purposes:

- `reference_price`, `limit_price`, `stop_price`, `target_price` are what the
  risk manager sizes against and what the advisory card shows. The risk
  manager computes shares from `(limit_price - stop_price)` and the max risk
  per trade; the strategy never sizes.
- `confidence` is a ranking signal, not a probability claim. Each strategy
  documents its own mapping (section 5). Reports calibrate it after the fact:
  win rate by confidence decile.
- `expected_edge_pct` is what makes candidates comparable across strategies.
  It must already subtract the current spread. A candidate with
  `expected_edge_pct <= 0` is dropped by the engine before ranking.
- `inputs` is the complete snapshot (4.1).

### 4.1 Input snapshot

The snapshot is what makes a decision reproducible from the journal alone. It
contains every value the strategy read, not a description of them:

```json
{
  "bars": [{"ts": "...", "o": 2.31, "h": 2.35, "l": 2.30, "c": 2.34, "v": 18200}, "... n bars"],
  "quote": {"bid": 2.33, "ask": 2.35, "bid_size": 1200, "ask_size": 800, "ts": "..."},
  "indicators": {"vwap": 2.312, "rel_volume_5m": 3.4, "opening_range": [2.40, 2.21, 410000]},
  "index": {"symbol": "IWM", "return_15m": 0.0021},
  "reference": {"adv20_dollar": 4100000, "spread_pct_est": 0.011, "halt_count_10d": 0, "pump_score": 0.12},
  "flagged_dropped": 0,
  "staleness_s": 4
}
```

The engine assembles the snapshot by recording every `ctx` call made during
`on_bar`, so a strategy cannot forget to include an input. Snapshot size is
bounded by `warmup_bars()`; 60 bars is about 6 KB.

---

## 5. Ranking and conflict resolution

After every bar, the engine collects candidates from all strategies and
resolves them before handing the survivors to the risk manager:

1. Drop candidates with `expected_edge_pct <= 0`, a `None` quote, or a
   symbol that is halted or inside the per-symbol cooldown (the engine
   checks cooldown too so the journal shows fewer redundant rejections; the
   risk manager remains the authority).
2. Same symbol from multiple strategies: keep the one with the highest
   `expected_edge_pct * confidence`. Journal the losers as
   `candidate` events with `superseded_by` set, so strategy agreement is
   visible in reports.
3. Rank the remainder by `expected_edge_pct * confidence` descending.
4. Pass at most `max_concurrent_positions - open_positions` candidates to the
   risk manager this bar (default max 3). Lower ranked candidates are
   journaled with `outcome: "not_ranked"`.

The risk manager then applies its rules independently and may reject any of
them. The engine never retries a rejected candidate; the strategy will emit
again on a later bar if the setup persists.

Confidence mapping per strategy (documented here so it is not folklore):

| Strategy | confidence |
|---|---|
| orb_delayed | `clip(rel_volume_15m / 5, 0.2, 1.0)` |
| vwap_reclaim | `clip(reclaim_volume_ratio / 3, 0.2, 1.0)` |
| relvol_momentum | `clip(rel_volume_5m / 8, 0.2, 1.0) * (1 if index_return_15m > 0 else 0)` |

---

## 6. Indicator computation rules

- **Bars that count**: completed, regular-session (09:30 to 15:59 ET open
  times), unflagged bars. Pre-market and after-hours bars are never used in
  v1. A bar with zero volume counts for time but contributes nothing to
  volume-based indicators.
- **VWAP**: `sum(close * volume) / sum(volume)` over session bars since 09:30.
  Vendor VWAP is ignored so backtest and live agree exactly. `None` before
  the third bar.
- **Relative volume** over `m` minutes: trailing `m` bars' volume divided by
  the mean of the same clock window's volume over the prior 20 sessions,
  computed from stored minute bars. Sessions with `sparse_minutes` are
  excluded from the baseline. `None` if fewer than 10 baseline sessions.
- **Opening range**: high, low and summed volume of bars with open times
  09:30 to 09:44 inclusive. `None` until 09:45 or if fewer than 10 of those
  15 bars exist.
- **Slope**: ordinary least squares on closes over the window, divided by the
  first close, so it reads as fraction per minute.
- **Day range so far**: `max(high) - min(low)` over session bars.
- **Ticks**: price increments are $0.01 at or above $1.00. All limit and
  stop prices are rounded to the tick toward the conservative side (limits
  down, stops down for longs).

---

## 7. Starter strategies

These three exist to exercise the machinery end to end. None of them is an
edge claim. The backtester's walk-forward protocol is expected to reject or
heavily reshape all three, and that outcome is a success for phase 1, not a
failure.

### 7.1 `orb_delayed` (opening range breakout, delayed)

Idea: the first 15 minutes set a range; a break above it on strong volume
after 09:45 continues for a while.

| Parameter | Default | Range |
|---|---|---|
| `range_minutes` | 15 | 10 to 30 |
| `min_rel_volume_15m` | 2.0 | 1.0 to 10.0 |
| `breakout_buffer_ticks` | 1 | 0 to 5 |
| `max_range_pct` | 0.08 | 0.02 to 0.20 |
| `target_r` | 1.5 | 0.5 to 4.0 |
| `entry_deadline_et` | 11:30 | 10:00 to 15:00 |

Entry (evaluated on each completed bar): time is at or after 09:45 and before
`entry_deadline_et`; opening range exists and `(high - low) / low <= max_range_pct`;
the bar's close is above `range_high + breakout_buffer_ticks * tick`; the
previous bar's close was at or below `range_high`; `rel_volume_15m >= min_rel_volume_15m`;
no candidate already emitted for this symbol today by this strategy.

Candidate: `reference_price` = bar close; `limit_price` = `min(ask, close * 1.003)`;
`stop_price` = `range_low` rounded down; `target_price` = `limit + target_r * (limit - stop)`;
`expected_hold` = 45 minutes.

Exit rule: target touched (position manager handles via resting order), stop
(broker-side), or close back below `vwap` for two consecutive bars. Max hold
is the position manager's 90 minutes.

### 7.2 `vwap_reclaim`

Idea: a dip below session VWAP that is bought back above it on rising volume
suggests buyers defending the average price.

| Parameter | Default | Range |
|---|---|---|
| `min_dip_bars` | 3 | 2 to 15 |
| `max_dip_pct` | 0.03 | 0.005 to 0.10 |
| `reclaim_volume_ratio_min` | 1.5 | 1.0 to 5.0 |
| `target_day_range_fraction` | 0.5 | 0.2 to 1.0 |
| `stop_buffer_ticks` | 2 | 0 to 10 |

Entry: at least `min_dip_bars` consecutive completed bars closed below VWAP,
the lowest of them no more than `max_dip_pct` below VWAP; the current bar
closes above VWAP; the current bar's volume divided by the mean volume of the
dip bars is at least `reclaim_volume_ratio_min`; time between 09:45 and the
entry cutoff.

Candidate: `reference_price` = close; `limit_price` = `min(ask, close * 1.003)`;
`stop_price` = dip low minus `stop_buffer_ticks`; `target_price` =
`limit + target_day_range_fraction * day_range_so_far`, but at least
`limit + 1.0 * (limit - stop)` so the reward to risk ratio is never below 1;
`expected_hold` = 30 minutes.

Exit rule: two consecutive closes below VWAP after entry.

### 7.3 `relvol_momentum`

Idea: among watchlist names, the one with the most unusual recent volume and a
rising price continues short term, when small caps as a group are rising.

| Parameter | Default | Range |
|---|---|---|
| `rel_volume_minutes` | 5 | 3 to 15 |
| `min_rel_volume` | 4.0 | 2.0 to 20.0 |
| `slope_minutes` | 15 | 5 to 30 |
| `min_slope_per_min` | 0.0005 | 0.0 to 0.005 |
| `index_symbol` | IWM | |
| `index_minutes` | 15 | 5 to 60 |
| `stop_atr_bars` | 10 | 5 to 30 |
| `stop_atr_mult` | 1.5 | 0.5 to 4.0 |
| `target_r` | 1.0 | 0.5 to 3.0 |

Entry: `rel_volume(rel_volume_minutes) >= min_rel_volume`;
`slope(slope_minutes) >= min_slope_per_min`; `index_return(index_symbol, index_minutes) > 0`;
the candidate's close is above VWAP. The strategy emits for every qualifying
symbol; ranking (section 5) picks the strongest, since `confidence` scales
with relative volume.

Candidate: `limit_price` = `min(ask, close * 1.003)`; `stop_price` = close minus
`stop_atr_mult` times the mean true range of the last `stop_atr_bars` bars;
`target_price` = `limit + target_r * (limit - stop)`; `expected_hold` = 20 minutes.

Exit rule: `rel_volume(rel_volume_minutes)` falls below 1.0, or
`index_return(index_symbol, 5) < -0.003`.

### 7.4 What all three share

- Entries require a live quote and `spread_pct <= 0.015`, mirroring the risk
  manager's spread gate so candidates that will be rejected are not emitted.
- `expected_edge_pct = (target - limit) / limit - spread_pct` when a target
  exists; otherwise `0.5 * (limit - stop) / limit - spread_pct`.
- Nothing is emitted while `is_halted` or within 15 minutes of a resume.

---

## 8. Configuration

`strategies.yaml`:

```yaml
engine:
  index_symbol: IWM
  stale_quote_seconds: 60
  min_expected_edge_pct: 0.0
  max_candidates_per_bar: 3        # equals risk.max_concurrent_positions by default
strategies:
  - name: orb_delayed
    version: 0.1.0
    enabled: true
    params: {range_minutes: 15, min_rel_volume_15m: 2.0, target_r: 1.5}
  - name: vwap_reclaim
    version: 0.1.0
    enabled: true
    params: {}
  - name: relvol_momentum
    version: 0.1.0
    enabled: false
    params: {min_rel_volume: 4.0}
```

Changes follow `design.md` 6.4: a pull request with a walk-forward report
attached. The loader records the file's hash as part of the session config
hash. Parameters never change mid-session.

---

## 9. Test cases

| Test | Assertion |
|---|---|
| Deterministic replay | Replaying one stored session twice with the same config hash and seed produces byte-identical `candidate` event streams. |
| Look-ahead violation | A test strategy that calls `ctx.bars(symbol, n)` and then asks for a bar at `now()` or later gets `LookAheadError`; a strategy that reads `daily()` on the first bar gets only prior sessions. |
| Forming bar excluded | At 10:03:30 replay time, `bars(symbol, 1)` returns the 10:02 bar, never 10:03. |
| Warm-up honored | `on_bar` is not called before `warmup_bars()` unflagged bars exist; indicators return `None` with partial windows. |
| Flagged bars dropped | Inject an `ohlc_inconsistent` bar; VWAP and relative volume exclude it; snapshot `flagged_dropped` is 1. |
| Snapshot completeness | Every `ctx` call made during `on_bar` appears in `inputs`; a strategy cannot emit a candidate whose inputs are empty. |
| Conflict resolution | Two strategies emit for the same symbol; one survives; the other is journaled with `superseded_by`. |
| Ranking cap | Five candidates with two open positions and max 3: exactly one reaches the risk manager, four are journaled `not_ranked`. |
| Non-positive edge dropped | A candidate whose target minus spread is zero or negative never reaches ranking. |
| Strategy exception isolation | A strategy that raises on bar 7 is disabled, an `incident` is journaled, other strategies keep running. |
| Params validation | Unknown field, out-of-range value, or version mismatch fails load with a clear message. |
| orb_delayed fixture | Synthetic session with a known range and breakout bar emits exactly one candidate with the expected stop and target. |
| vwap_reclaim fixture | Synthetic dip and reclaim emits once; a reclaim on low volume emits nothing. |
| relvol_momentum index filter | Identical stock data with a negative index return emits nothing. |
| Tick rounding | Limits round down, stops round down, to $0.01. |

## 10. Changelog

- v0.1: initial design.
