# Session Trader: System and Operational Design

Status: draft v0.3, 2026-10-16
Scope decisions agreed: listed US stocks between $1 and $5, **margin account
with leverage disabled by configuration** (changed from cash account in v0.3,
see C1, C2 and section 15), intraday only, advisory mode first, Alpaca first
with the broker behind an interface. OTC is out of scope for v1 and tracked in
section 11 as a future optimization.

Items marked **[verify]** are facts still to confirm. Items marked
**[verified 2026-10-16]** were checked in phase 0; sources are in section 15.
Pricing and API features change often, so re-check before phase 3.

---

## 1. Goals and non-goals

**Goals**

- Activate for a bounded window (minutes to a few hours) within the regular
  session, produce ranked trade recommendations, optionally execute them, and
  be flat (no positions) when deactivated or at a hard cutoff time.
- Every decision reproducible from logged inputs. No trade that cannot be
  explained after the fact.
- Risk limits enforced by code that strategies cannot bypass.
- A single personal account. No management of other people's money, no
  distribution of recommendations to others.

**Non-goals for v1**

- OTC / pink-sheet securities (section 11).
- Overnight positions, options, shorting. Shorting penny stocks is rarely
  possible for retail anyway (hard-to-borrow).
- Sub-second or latency-sensitive strategies. We are not competing with
  market makers on speed.
- An LLM making real-time entry or exit decisions.

**Definition of success for the first live phase**: positive expectancy after
real fees and real slippage over at least 60 sessions, with max drawdown inside
the configured budget. Not "made money this week."

---

## 2. Constraints register

| # | Constraint | Effect on design |
|---|---|---|
| C1 | **The Pattern Day Trader rule no longer exists.** FINRA Regulatory Notice 26-10 replaced the day-trade count test and the $25,000 minimum with risk-based "intraday margin" standards under Rule 4210, effective June 4, 2026; brokers may phase in until October 20, 2027. Alpaca implemented it on June 4, 2026 and removed its PDT API fields on July 6, 2026. Regulation T still applies: a margin account needs $2,000 equity for leverage; under $2,000 it is restricted to 1x buying power. Repeated failure to meet an intraday margin call within five business days can restrict the account for 90 days. **[verified 2026-10-16]** | Use a **margin account**, which lets sale proceeds be reused the same day with no day-trade counting. Disable leverage in configuration: gross exposure may never exceed 100 percent of equity, so an intraday margin call cannot occur. The execution adapter must read the new intraday buying power fields, not the deprecated day-trade fields. |
| C2 | T+1 settlement still governs **cash** accounts: reusing unsettled proceeds and selling before settlement is a good-faith violation, and brokers typically restrict the account for 90 days after the third in 12 months. **[verified 2026-10-16]** | Not binding for a margin account. Kept here because the `Broker` interface must still expose settled versus unsettled cash so the cash-account mode remains available as a fallback if a broker has not phased in the new rule. |
| C3 | Bid-ask spread on sub-$5 stocks is often 1 to 5 percent on listed names, 5 to 20 percent OTC | Minimum expected move must exceed spread plus fees plus slippage buffer. Spread is a hard screener filter. Limit orders only. |
| C4 | Low float: our orders move price | Participation cap: a position may not exceed X percent of average daily dollar volume (default 0.5 percent) and X percent of the volume in the last N minutes. |
| C5 | Limit Up Limit Down (LULD) halts. Tier 2 bands: 10 percent above $3.00; 20 percent from $0.75 to $3.00; below $0.75 the lesser of $0.15 or 75 percent. Bands double from 15:35 to 16:00 for Tier 2 stocks at or below $3.00. Reference price is the trailing 5-minute average. Fifteen seconds in a limit state triggers a 5-minute pause, extendable by 5 more. **[verified 2026-10-16]** | Deactivate cannot promise to be flat if a holding is halted. Session controller needs a HALTED_EXPOSURE state, alerting, and a post-halt exit rule. Screener penalizes names with recent halt history. The band table is encoded as data so the backtester can model halts per price regime. The 15:45 flatten deadline sits inside the doubled-band window, which lowers halt risk during exits. |
| C6 | Alpaca Basic (free) streams IEX-only real-time data and delays recent SIP data by 15 minutes over REST. Alpaca Algo Trader Plus is about $99 per month for full SIP real-time stocks plus options, with much higher rate limits. Polygon, now branded Massive, charges about $199 per month for full SIP real-time (Advanced), $79 for single-exchange real-time (Developer), $29 for delayed. Databento is usage-priced. Prices from third-party listings; official pages were unreachable from this session. **[verified 2026-10-16, prices approximate]** | Budget about $99 per month for SIP before paper trading in earnest, not just before live. Paper trading on IEX data would give false confidence in exactly the thin names we trade. Alpaca Algo Trader Plus is the default choice because it is the cheapest SIP feed and comes from the same vendor as the broker. |
| C7 | Promotions and pump-and-dump schemes dominate volume spikes in this universe | Dedicated pump-detection filter in the screener (section 5.2). Treat the biggest percentage gainers of the day as suspect by default. |
| C8 | Fees on Alpaca: zero commission; SEC Section 31 fee of $20.60 per million dollars sold (from April 4, 2026) on sells only; FINRA Trading Activity Fee of $0.000195 per share sold, capped at $9.79 per trade, **waived October 1 to December 31, 2026** and returning in January 2027; a small FINRA CAT fee on both buys and sells. Alpaca lists one OTC share as 0.01 fee-equivalent shares. No sub-$1 surcharge found on Alpaca. **[verified 2026-10-16]** | The fee model is a table of date-ranged rates, not constants, because rates change every year and the TAF waiver would otherwise flatter any backtest run on Q4 2026 data. Per trade of $500 the regulatory cost is about one cent, so fees are negligible on listed names and spread is the whole story. |
| C9 | Regulatory: own account only. Managing others' money or selling signals requires registration | Architecture has no multi-user or distribution features. |
| C10 | Taxes: all gains are short-term; wash-sale rule applies to repeated trades in the same name within 30 days | Journal exports a tax lot report. Not a design driver otherwise. |
| C11 | Market hours: 09:30 to 16:00 ET. Opening 15 minutes and closing 15 minutes have the worst spreads and most halts | Default activation window excludes 09:30 to 09:45 and all entries stop by 15:30. Hard flatten deadline 15:45. Configurable. |
| C12 | Nasdaq's $1.00 minimum bid price rule, tightened in January 2025: a company below $1.00 for 30 consecutive days gets a deficiency notice; more than 360 days non-compliant means suspension; a company that falls below $1.00 within a year of a reverse split is delisted with no grace period. Sub-$1 listed stocks are therefore structurally headed for a reverse split or delisting. **[verified 2026-10-16]** | Raise the universe price floor from $0.50 to **$1.00**. This also avoids the sub-$0.75 LULD regime where bands are 75 percent and spreads are widest. Sub-$1 names remain a possible later extension with their own study. |

---

## 3. Architecture overview

```
                 +-------------------+
                 |   Data Ingestion  |  real-time quotes/bars, daily reference data
                 +---------+---------+
                           |
                 +---------v---------+
                 | Universe Screener |  pre-session, produces watchlist
                 +---------+---------+
                           |
   +-----------------------v------------------------+
   |              Session Controller                 |  state machine, activation window
   |  +---------------+   +------------------+       |
   |  | Signal Engine |-->|  Risk Manager    |--+    |
   |  +---------------+   +------------------+  |    |
   |         ^                                   v    |
   |         |            +------------------+  |    |
   |         +------------| Position Manager |<-+    |
   |                      +--------+---------+       |
   +-------------------------------|-----------------+
                                   v
                 +-------------------+     +-------------------+
                 | Execution Adapter |---->|  Broker (paper /  |
                 | (limit orders)    |<----|  live)            |
                 +-------------------+     +-------------------+
                           |
                 +---------v---------+
                 |  Journal / Store  |  every event, full input snapshot
                 +---------+---------+
                           |
          +----------------+----------------+
          v                                 v
  +---------------+                 +------------------+
  | Advisory UI   |                 | Agent Reviewer   |  post-session analysis,
  | (recommend,   |                 | (reads journal,  |  tuning proposals
  |  approve)     |                 |  never trades)   |
  +---------------+                 +------------------+
```

**Principles**

1. Deterministic hot path. Signal, risk, and execution are rule-based code
   with versioned parameters. Same inputs, same outputs, always.
2. One execution interface. Backtest, paper and live use the same
   `Broker` interface. The strategy code cannot tell which it is talking to.
3. Risk manager is the only component that can create an order. Strategies
   produce candidates; only the risk manager promotes a candidate to an order.
4. Append-only journal. Nothing is updated in place; state is rebuilt from
   events. This is what makes post-mortems and agent review trustworthy.
5. Fail flat. Any unrecoverable error during ACTIVE moves to FLATTENING, not
   to a retry loop holding positions.

**Recommended stack**

- Python 3.12 for the whole quant core. The research, backtesting and broker
  SDK ecosystem is Python-first (pandas, polars, vectorbt or a hand-rolled
  event backtester, alpaca-py). Choosing anything else means rewriting libraries.
- Postgres for operational state and the journal. DuckDB over Parquet files for
  historical bars and research queries. Both run locally; no cloud needed in
  phase 1 and 2.
- Typed config (pydantic) loaded from versioned YAML. Every parameter has a
  name, default, allowed range, and a changelog entry.
- A thin web UI (FastAPI + HTMX, or a Next.js app if we prefer) for the
  advisory view. Optional until phase 2.
- Process supervision with systemd or a container with restart policy.
  NTP-synced clock; timestamps in UTC with exchange-time rendering.

---

## 4. Data layer

**Sources**

| Need | Source options | Notes |
|---|---|---|
| Real-time quotes and 1-minute bars | Alpaca Algo Trader Plus (~$99/mo, SIP), Polygon/Massive Advanced (~$199/mo, SIP), Databento (usage-priced) | SIP required before serious paper trading (C6). **[verified 2026-10-16, approximate]** |
| Historical minute bars, 2+ years | Same vendors; Polygon and Databento have deeper history | Needed for backtests. Survivorship-bias-free data matters here: many penny stocks delist. Vendor must include delisted tickers. **[verify hands-on in phase 0: pull bars for five tickers delisted in 2024 and 2025 from each candidate vendor]** |
| Reference data: exchange, shares outstanding, float | Vendor fundamentals endpoints, SEC EDGAR | Float is the hardest to get right; treat as approximate. |
| Corporate actions: splits, reverse splits | Vendor | Reverse splits are very common in this universe and corrupt backtests if unadjusted. |
| Halt feed (LULD) | Nasdaq Trader halt list, vendor status messages | Needed live for C5. |
| Short interest, borrow data | Optional later | Not needed for long-only v1. |
| News / filings / promotions | EDGAR full-text search, press release feeds | Used by screener pump filter and by the agent for pre-session research. |

**Storage layout**

- `bars_1m/{symbol}/{yyyy-mm}.parquet` adjusted for splits, with a raw
  unadjusted copy kept for audit.
- `quotes` not stored in full in v1; we store the quote snapshot attached to
  each signal and order event in the journal instead.
- `reference_daily` table: one row per symbol per day with price, volume,
  float, exchange, halt count, screener scores.

**Data quality checks** (run before every session, block activation on failure)

- Clock skew vs vendor server under 500 ms.
- Last bar timestamp within 2 minutes of now for a liquid control symbol.
- Bar count for the control symbol matches expected count since open.
- Reference data refreshed within 24 hours.

---

## 5. Components in detail

### 5.1 Universe screener (pre-session)

Runs 30 minutes before the activation window on the previous day's data plus
pre-market activity. Produces a watchlist of 20 to 50 names.

Default filters, all configurable:


- Exchange in {NASDAQ, NYSE, NYSE American}. No OTC in v1.
- Close price between $1.00 and $5.00 (floor raised from $0.50, see C12).
- Not under a Nasdaq or NYSE bid-price deficiency notice (public via exchange
  notices and 8-K filings).
- Average daily dollar volume over 20 days at least $2M.
- Average spread over the last 5 sessions under 1.5 percent of mid.
- Fewer than 2 LULD halts in the last 10 sessions.
- No reverse split in the last 30 days.
- Pump score below threshold (5.2).
- Not in a user-maintained blacklist (names that burned us).

Ranking: a weighted score of relative volume, intraday range consistency, and
spread tightness. Weights are parameters.

### 5.2 Pump detection filter

A name is flagged when several of these co-occur:

- Price up more than 50 percent over 1 to 3 sessions on volume more than 5x
  its 20-day average, with no 8-K or press release from the issuer.
- Shares outstanding increased sharply in recent filings (dilution via
  offerings, warrants, convertible notes).
- Promotional mentions detected in a keyword scan of press release feeds and
  social sources (phase 3; start with filings only).
- Issuer has a history of reverse splits or compliance notices.

Flagged names are excluded or heavily down-weighted. The agent reviewer
produces a short pre-session note on any borderline name.

### 5.3 Signal engine

Interface every strategy implements:

```
class Strategy:
    name: str
    version: str
    params: StrategyParams          # typed, validated, versioned

    def on_bar(self, ctx: MarketContext) -> list[Candidate]: ...
    def on_quote(self, ctx: MarketContext) -> list[Candidate]: ...  # optional
    def exit_rule(self, position: Position, ctx: MarketContext) -> ExitSignal | None: ...
```

`Candidate` carries: symbol, side (long only in v1), reference price,
suggested limit price, stop price, target price, confidence score 0 to 1,
expected hold time, the strategy name and version, and a snapshot of every
input the strategy used. The snapshot is what makes the journal reproducible.

Initial strategy set (each one small and testable on its own):

1. **Opening range breakout, delayed.** After 09:45, buy a break above the
   first 15-minute high on volume above threshold, stop under the range low.
2. **VWAP reclaim.** Price dips below VWAP and reclaims it with rising volume.
   Stop below the dip low. Target a fraction of the day's range.
3. **Relative volume momentum.** Among watchlist names, buy the one with the
   strongest 5-minute relative volume and positive 15-minute slope, only when
   the broad small-cap index is also positive.

These are starting points for learning the machinery, not an edge claim.
Expect to discard or heavily modify all three after backtesting.

### 5.4 Risk manager

The only component allowed to emit an `OrderIntent`. Every rule is a pure
function returning allow or reject with a reason, and every rejection is
journaled. Defaults for a $5,000 cash account:

| Rule | Default | Notes |
|---|---|---|
| Max risk per trade (entry minus stop times size) | 0.5 percent of equity ($25) | Sizing is derived from this, not the other way round |
| Max position notional | 10 percent of equity | |
| Max concurrent positions | 3 | |
| Daily loss limit | 1.5 percent of equity | Hitting it moves the session to FLATTENING and locks activation for the day |
| Weekly loss limit | 4 percent | Locks activation for the rest of the week |
| Participation cap | 0.5 percent of 20-day average daily dollar volume, and 2 percent of the trailing 15-minute volume | Addresses C4 |
| Spread gate | Reject if current spread over mid exceeds 1.5 percent | Addresses C3 |
| Leverage gate | Reject any entry that would take gross exposure above 100 percent of equity, or that the broker's intraday buying power would not cover without a debit | Addresses C1. Makes an intraday margin call impossible by construction |
| Settled-cash gate (cash-account mode only) | Reject if entry would spend unsettled funds | Addresses C2. Inactive in margin mode |
| Time gate | No new entries before 09:45 or after the configured entry cutoff (default 15:30) | Addresses C11 |
| Halt gate | Reject any symbol currently halted or halted within the last 15 minutes | Addresses C5 |
| Consecutive loss brake | After 3 losing trades in a session, stop new entries | Behavioral guard against tilt, for the system and the human |
| Per-symbol cooldown | No re-entry in a symbol for 30 minutes after an exit | |

Risk parameters live in a separate config file from strategy parameters, with
a separate change approval path (section 8).

### 5.5 Execution adapter

- Limit orders only. Entry limit is at or slightly through the ask, bounded by
  a max-slippage parameter (default 0.3 percent over the reference price).
- Day time-in-force. Unfilled entries are cancelled after N seconds (default 45).
- Partial fills are normal here. The position manager tracks filled quantity
  and re-evaluates risk on the actual size.
- Exits are placed as limit orders at the bid with a step-down ladder: if not
  filled in 20 seconds, reprice one tick lower, repeat up to a max slippage.
  Past that, during FLATTENING only, a marketable limit is allowed.
- A broker-side protective stop is placed immediately after each entry fill so
  that a process crash does not leave an unprotected position.
- `Broker` interface: `place`, `cancel`, `replace`, `positions`, `orders`,
  `account`, `cancel_all`, `liquidate_all`, plus a streaming `on_fill` callback.
  `account` returns equity, cash, settled cash, intraday buying power and
  gross exposure in a broker-neutral shape. The Alpaca adapter must use the
  post-June-2026 intraday buying power fields; the day-trade fields were
  removed from the API on July 6, 2026.
- Alpaca's assets endpoint marks OTC symbols `tradable=false`; the adapter
  refuses any symbol not marked tradable before the order reaches the broker,
  and the screener re-checks tradability at PREFLIGHT since the asset master
  refreshes three times a day.
  Implementations: `BacktestBroker`, `AlpacaPaperBroker`, `AlpacaLiveBroker`.
  IBKR and Tradier adapters later.

### 5.6 Session controller

State machine:

```
IDLE -> PREFLIGHT -> ACTIVE -> WINDING_DOWN -> FLATTENING -> CLOSED
                       |            |              |
                       +------------+--------------+--> HALTED_EXPOSURE (sub-state)
any state --(fatal error / kill switch)--> FLATTENING
```

- **PREFLIGHT**: data quality checks (section 4), broker connectivity, account
  snapshot, settled cash computed, watchlist loaded, parameters hash recorded.
  Any failure blocks activation with a reason.
- **ACTIVE**: strategies run on each bar; risk manager gates; orders placed.
- **WINDING_DOWN**: triggered by user deactivate, by the entry cutoff time, or
  by the daily loss limit. No new entries. Open positions managed by exit
  rules until the flatten deadline.
- **FLATTENING**: cancel all open orders, exit all positions via the ladder.
  Triggered by the flatten deadline (default 15:45), by explicit "flatten now",
  or by a fatal error.
- **HALTED_EXPOSURE**: a held symbol is halted. Alert the operator. On resume,
  exit immediately at the reopening auction price if within max slippage,
  otherwise ladder. If still halted at 16:00 the position carries overnight;
  that is journaled as an incident.
- **CLOSED**: end-of-session reconciliation against broker positions and
  balances. Any discrepancy is an incident.

The operator controls: `activate`, `deactivate` (graceful), `flatten now`,
`kill` (flatten plus process stop plus broker-side cancel-all).

### 5.7 Position manager

Tracks per-position: entry fills, stop, target, trailing rules, time in trade,
unrealized P&L, and the exit signals received. Enforces max hold time (default
90 minutes) regardless of strategy.

### 5.8 Journal and reporting

Append-only event table. Event types: `session_state`, `bar`, `quote_snapshot`,
`candidate`, `risk_decision`, `order_intent`, `order_ack`, `fill`, `cancel`,
`position_open`, `position_close`, `incident`, `param_change`, `operator_action`.

Every event carries: UTC timestamp, session id, parameter set hash, code
version (git SHA), and a JSON payload.

Reports produced automatically at CLOSED:

- Session summary: trades, win rate, gross and net P&L, fees, slippage vs
  model, time in market, risk rejections by rule.
- Running metrics over the last 20 and 60 sessions: expectancy per trade,
  profit factor, max drawdown, Sharpe (session-level), slippage drift.
- Reconciliation report against broker statements.

### 5.9 Advisory UI (phase 2)

A single page showing the live watchlist, each candidate as a card (symbol,
reason, limit, stop, target, size, risk dollars, confidence), and an approve
or skip control. Approve sends the order through the same execution adapter.
In advisory mode the operator is the final gate; in live mode the risk manager
is. Same code path either way, which is the point.

---

## 6. Operational design

### 6.1 Daily runbook

| Time (ET) | Step | Who |
|---|---|---|
| 08:00 | Reference data refresh, screener run, pump filter, watchlist published | System |
| 08:30 | Pre-session note: watchlist review, filings scan, borderline names | Agent |
| 09:00 | Operator reads the note, blacklists anything uncomfortable, confirms parameters hash | Operator |
| 09:15 | PREFLIGHT runs automatically; result pushed to operator | System |
| 09:45 or later | Operator activates (or scheduled activation) | Operator |
| During | Alerts only on: fill deviation, halt exposure, data stall, loss limit, broker error | System |
| 15:30 | Entry cutoff, WINDING_DOWN | System |
| 15:45 | Flatten deadline | System |
| 16:05 | Reconciliation, session report, incident list | System |
| Evening | Post-session review: what fired, what was rejected and why, slippage, proposed tuning with backtest evidence | Agent |
| Weekly | Metrics review, parameter change decisions, blacklist pruning | Operator with agent |

### 6.2 Monitoring and alerting

- Heartbeat every 10 seconds during ACTIVE; a missed heartbeat for 30 seconds
  pages the operator and triggers FLATTENING if positions are open.
- Data stall detector: no bar for a liquid control symbol in 2 minutes.
- Fill deviation: fill price differs from intended limit by more than the
  slippage budget.
- Broker rejection or error rate above threshold.
- Alert channels: push notification plus SMS for FLATTENING and
  HALTED_EXPOSURE; everything else to a log channel.

### 6.3 Kill switch

Three layers, each independent of the others:

1. In-app `kill` command.
2. A standalone script with its own credentials that calls the broker's
   cancel-all and liquidate-all. Lives on a different device (phone shortcut).
3. Broker web or mobile app, used manually.

Practiced once a week in paper mode so it is muscle memory.

### 6.4 Configuration and change management

- Two config files: `risk.yaml` and `strategies.yaml`. Both under git.
- Any change to `risk.yaml` requires a human-approved PR and takes effect only
  at the next PREFLIGHT, never mid-session.
- Any change to `strategies.yaml` requires an attached backtest report
  comparing old and new parameters on the same data window, plus a
  walk-forward result. The agent drafts these PRs; the operator merges.
- Every session records the config hash; reports group results by hash so
  changes can be evaluated honestly.

### 6.5 Secrets and accounts

- Paper and live API keys never coexist on the same host in phase 2.
- Live keys are read-only until the operator passes the phase 3 gate.
- Keys stored in the OS keychain or an env file with restrictive permissions;
  never in the repo, never in the journal.
- The agent reviewer process has no broker credentials at all. It reads the
  journal database with a read-only role.

### 6.6 Deployment

- Phase 1 and 2: the operator's workstation or a home server. Local Postgres.
- Phase 3: a small VPS in a US-East region (close to the broker's endpoints),
  2 vCPU, 4 GB RAM is plenty. Container with restart policy. Daily database
  backup to object storage.
- Clock discipline: chrony or systemd-timesyncd; PREFLIGHT fails on skew.

### 6.7 Failure scenarios and responses

| Scenario | Response |
|---|---|
| Process crash with open positions | Broker-side stops already in place. Supervisor restarts the process; on start it reconciles positions from the broker, enters WINDING_DOWN, and alerts. |
| Data feed stalls | Stall detector fires; no new entries; if positions open and stall exceeds 2 minutes, FLATTENING using broker quotes as fallback. |
| Broker API down | Cannot flatten via API. Alert with instructions to use layer 3 kill switch. Journal an incident. |
| Held symbol halted at deactivate | HALTED_EXPOSURE path (5.6). Accept that "flat on deactivate" is best-effort under halts and say so in the UI. |
| Exit ladder exhausts slippage budget | During FLATTENING, marketable limit is permitted. Outside FLATTENING, hold and alert. |
| Good-faith violation risk | Settled-cash gate prevents it; if the broker reports one anyway, lock activation and investigate. |
| Reconciliation mismatch | Lock activation until resolved. Mismatches are usually fee or partial-fill accounting; occasionally a real missed fill. |

---

## 7. Metrics that matter

- **Expectancy per trade** net of fees and slippage. The one number that
  decides whether to continue.
- **Profit factor** (gross wins over gross losses). Below 1.2 after costs is
  noise.
- **Slippage vs model**: actual fill price minus intended price, tracked per
  strategy and per symbol. Rising slippage means our size is too big for the
  names we trade.
- **Max drawdown** in dollars and percent, and time to recover.
- **Risk rejection mix**: which rules reject most. Tells us whether the
  screener and strategies are tuned to the risk envelope or fighting it.
- **Halt exposure incidents** per 20 sessions.

Backtest honesty rules: include fees from the broker's schedule, model fills
at the ask for entries and the bid for exits plus a slippage term, use
survivorship-bias-free data, walk-forward validate, and never tune on the
evaluation window. Report the number of parameter combinations tried.

---

## 8. The AI agent: roles and guardrails

| Role | Autonomous | Needs operator approval | Never |
|---|---|---|---|
| Build | Write code, tests, backtests, docs; open PRs | Merge to main | Push to a branch the live system deploys from without review |
| Run | Run PREFLIGHT, publish reports, raise alerts, restart crashed processes | Activate a live session | Change risk parameters mid-session |
| Advise | Pre-session notes, post-session review, tuning proposals with evidence | Apply a tuning proposal | Place or modify an order; hold broker credentials |
| Maintain | Data quality monitoring, dependency updates in a PR, regression backtests | Deploy | Alter the journal |

Why the agent stays out of the hot path: an LLM call takes seconds and costs
money per call, its output is not deterministic, and it cannot be
backtested. Those three properties are each disqualifying for a component
whose decisions must be reproducible. The agent's leverage is in research,
code, review and explanation, where those properties do not matter.

What the agent will be genuinely good at here:

- Turning the journal into a readable narrative of the session.
- Spotting that a parameter change improved backtests only because of three
  outlier trades.
- Reading filings for the watchlist and flagging dilution or promotion.
- Writing and maintaining the fee and slippage models against broker statements.
- Keeping the design document and the code in agreement.

---

## 9. Investment and operating cost

| Item | Phase 1 (research) | Phase 2 (paper / advisory) | Phase 3 (live small) |
|---|---|---|---|
| Trading capital | 0 | 0 | 5,000 to 10,000, sized so total loss is acceptable; at least 2,000 to keep margin-account features |
| Historical data | 0 to 50 per month | same | same |
| Real-time data | 0 (IEX) | ~99 per month (Alpaca SIP) | ~99 to 199 per month (SIP) |
| Hosting | 0 (local) | 0 | 20 to 50 per month |
| LLM usage | 20 to 50 per month | 50 to 100 per month | 50 to 150 per month |
| Operator time | 5 to 10 hours per week | 1 hour per session day plus weekly review | same |

Expect phase 3 to lose money initially while fee and slippage models are
corrected against reality. Budget for that explicitly.

---

## 10. Phased roadmap with exit criteria

**Phase 0: Constraints and vendor verification (1 to 2 weeks)**
Desk research done 2026-10-16 (section 15). Remaining hands-on items:
open an Alpaca paper account and confirm the intraday buying power fields and
the $2,000 margin threshold in the account payload; pull one month of minute
bars for 50 names in the $1 to $5 band and measure actual spreads and halt
frequency; test delisted-ticker coverage at Alpaca and Polygon; read the
current Alpaca and IBKR fee schedules directly (unreachable from this session).
Exit when: spread and halt numbers are measured, not assumed, and the data
vendor is chosen.

**Phase 1: Data and backtester (3 to 5 weeks)**
Storage, adjustments, survivorship-safe universe, event-driven backtester with
the fee and slippage model, three starter strategies, risk manager, journal.
Exit when: a full backtest of 2 years runs end to end and the walk-forward
report is produced automatically.

**Phase 2: Paper and advisory (6 to 8 weeks, at least 40 sessions)**
Session controller, Alpaca paper adapter, advisory UI, alerts, runbook, kill
switch drills, agent pre- and post-session notes.
Exit when: 40 paper sessions with zero reconciliation mismatches, zero
unhandled incidents, and paper expectancy positive after modeled costs.

**Phase 3: Live small (ongoing, review at 60 sessions)**
SIP data, live keys, minimum sizes. Compare live slippage to paper model
weekly and recalibrate.
Exit criteria to scale up: 60 live sessions, net positive expectancy,
drawdown within budget, slippage model within tolerance. Any one failing
means stay small or go back to phase 2.

---

## 11. OTC as a future optimization

Held out of v1, kept alive because the inefficiencies are real.

**What changes if we add OTC**

- Broker: Alpaca does not allow new OTC positions; its assets endpoint lists
  OTC symbols as `tradable=false` and only closing is permitted. OTC market
  data requires a direct agreement with OTC Markets. **[verified 2026-10-16]**
  Interactive Brokers trades OTC. IBKR Pro tiered pricing is up to $0.0035 per
  share, minimum $0.35 and maximum 1 percent of trade value per order, plus
  exchange, clearing and regulatory fees; fixed pricing is $0.005 per share,
  minimum $1. At $0.50 per share, 5,000 shares is a $2,500 order costing about
  $17.50, or 0.7 percent, each way. Per-share pricing is a real tax on
  low-priced stocks and must be in the OTC fee model. A second adapter.
- Data: OTC Markets quotes are a separate feed with its own cost. Level 2 is
  far more important here because the inside quote is often stale.
- No LULD halts, but SEC trading suspensions and "caveat emptor" designations.
  Rule 15c2-11 limits quoting in shell and delinquent companies.
- Tiers matter: OTCQX and OTCQB have reporting requirements; Pink has
  essentially none. A v2 universe would start with OTCQX and OTCQB only.
- Spreads of 5 to 20 percent mean strategies must target multi-day holds, which
  conflicts with the intraday session model. OTC would likely be a separate
  "swing" session type with its own risk envelope.
- Pump-and-dump prevalence is much higher. The pump filter becomes the primary
  component, not a secondary one.

**Where the opportunity might be**

- Less algorithmic competition, so simple inefficiencies persist longer.
- Patient limit orders inside a wide spread can capture the spread rather than
  pay it, if the risk manager treats "time to fill" as a first-class budget.
- Our journal and backtester are the prerequisites for finding out whether
  any of this holds. That is the real reason to build v1 well.

**Entry condition for taking it on**: phase 3 exit criteria met on listed
names, plus a dedicated OTC backtest showing positive expectancy after the
wider spread model.

---

## 12. Concepts worth knowing (learning notes)

- **VWAP**: volume-weighted average price for the day. Institutions benchmark
  against it, so price reacts around it.
- **Float**: shares available to trade. Low float plus high volume equals
  violent moves in both directions.
- **LULD**: exchange rule that halts a stock for 5 minutes when it moves
  outside a price band. Bands are wider for low-priced stocks but still trip
  constantly in this universe.
- **PDT, historical**: the FINRA rule that limited day trades in margin
  accounts under $25k. Retired June 4, 2026.
- **Intraday margin**: its replacement. Brokers compute a running intraday
  buying power from your equity and open exposure, and reject orders that
  would create a deficit. With leverage disabled, it never binds on us.
- **T+1 and good-faith violations**: in a cash account, money must settle
  before being reused. Not relevant in a margin account.
- **Bid-price deficiency**: Nasdaq and NYSE require a $1.00 minimum bid.
  Companies below it for 30 days enter a compliance process that usually
  ends in a reverse split or delisting.
- **Slippage**: the difference between the price you wanted and the price you
  got. In this universe it is often the whole edge.
- **Survivorship bias**: backtesting only on stocks that still exist. Penny
  stocks delist constantly, so this bias is enormous here.
- **Look-ahead bias**: using data in a backtest that would not have been
  available at that moment. Reverse-split adjustments and float updates are
  common sources.
- **Overfitting**: tuning parameters until the backtest looks good. Walk-forward
  testing and counting the number of combinations tried are the defenses.
- **Expectancy**: average dollars won per trade, including losers. The only
  number that matters long term.

---

## 13. Open questions

1. Which real-time data vendor, after phase 0 price checks.
2. Whether to build the backtester by hand (full control, more work) or adopt
   a library (faster start, less control over fills and halts). Leaning
   hand-built because halt and partial-fill modeling matter here and most
   libraries ignore them.
3. Activation trigger: always manual, or allow scheduled activation with the
   operator only approving the watchlist.
4. Alert delivery: which channel reaches the operator fastest in practice.
5. Whether the advisory UI is a web page or a terminal dashboard for phase 2.

## 14. Changelog

- v0.1: initial scoping conversation.
- v0.2: full system and operational design; OTC moved to future section.
- v0.3: phase 0 desk research. PDT retirement changes account type to margin
  with leverage disabled. Price floor raised to $1.00. Fee, data, LULD and OTC
  facts filled in. Verification log added.

## 15. Verification log (phase 0 desk research, 2026-10-16)

Official vendor pages were unreachable from the research session, so facts
below come from search excerpts of primary documents and from reputable
secondary sources. Re-read the primary pages before phase 3.

| Fact | Finding | Sources |
|---|---|---|
| PDT rule status | Retired. FINRA Rule 4210 amended; effective June 4, 2026; phase-in to October 20, 2027. Replaced by intraday margin standards. Regulation T $2,000 minimum for margin privileges remains. | FINRA Regulatory Notice 26-10 (finra.org/rules-guidance/notices/26-10); Federal Register 2026-00519; King & Spalding and ACA summaries |
| Alpaca implementation | Implemented June 4, 2026. PDT designation, $25k minimum and day-trade counting removed. Intraday Buying Power replaces Day Trade Buying Power. PDT API fields deprecated June 3 and removed July 6, 2026. Accounts under $2,000 restricted to 1x buying power. | docs.alpaca.markets "The Intraday Margin Rule", "Understanding FINRA's New Intraday Margin Rule and the End of PDT", changelog 2026-06-03; alpaca.markets blog |
| Good-faith violations (cash accounts) | Third violation in 12 months typically triggers a 90-day settled-cash restriction; thresholds vary by broker. T+1 settlement since May 28, 2024. | Schwab, E*TRADE, M1 help pages |
| Alpaca data plans | Basic free: IEX real-time stream, delayed SIP over REST, 200 requests per minute. Algo Trader Plus about $99 per month: full SIP real-time, options, up to 10,000 requests per minute. | docs.alpaca.markets About Market Data API; alpaca.markets/elite; TradingDataCompare, apis.io |
| Alpaca fees | Zero commission. SEC fee on sells. FINRA TAF shown as $0 (consistent with Q4 2026 waiver). CAT fee both sides. OTC share counts as 0.01 fee shares. | Alpaca Brokerage Fee Schedule PDF (files.alpaca.markets/disclosures/library/BrokFeeSched.pdf) |
| Regulatory fee rates 2026 | SEC Section 31: $20.60 per million sold from April 4, 2026. FINRA TAF: $0.000195 per share sold, cap $9.79, set to $0 for October 1 to December 31, 2026, prior rate returns January 2027. | SEC Fee Rate Advisory 2026-2; FINRA Information Notice 2026-03-17; SEC release 34-106409 |
| Alpaca OTC support | OTC symbols present in the assets list with exchange OTC and tradable=false. Closing existing positions allowed, opening not. OTC data requires a direct OTC Markets agreement. | Alpaca Broker API FAQ; Alpaca community forum staff replies; Alpaca Python SDK asset model |
| Polygon/Massive pricing | Basic $0, Starter $29 delayed, Developer $79 real-time single exchange, Advanced $199 full SIP. Rebranded to Massive. | Multiple 2026 comparison articles; official pricing page unreachable |
| Databento pricing | Usage-priced; sources conflict on fixed tiers. | Comparison articles |
| LULD bands | Tier 2: 10 percent above $3; 20 percent at $0.75 to $3; lesser of $0.15 or 75 percent below $0.75. Doubled 15:35 to 16:00 for Tier 2 at or below $3. 15-second limit state, 5-minute pause, extendable. Reference price trailing 5-minute average. | investor.gov LULD bulletin; FINRA "Guardrails" page; Wharton Jacobs Levy LULD presentation |
| IBKR commissions | Pro tiered $0.0005 to $0.0035 per share, minimum $0.35, maximum 1 percent of trade value, plus fees. Fixed $0.005 per share, minimum $1, maximum 1 percent. Lite: listed stocks commission-free, OTC billed under fixed pricing. | interactivebrokers.com commissions pages |
| Nasdaq $1 rule | January 2025 amendments: suspension after 360 days non-compliant (was up to 540); no grace period if below $1 within a year of a reverse split; discretionary delisting at or below $0.10 for 10 days. | Goodwin, Cooley, Norton Rose Fulbright, Taft client alerts |

Still open after desk research: exact Alpaca historical depth and delisted
ticker coverage; whether Alpaca's intraday buying power payload exposes gross
exposure directly or we compute it; Polygon delisted ticker entitlements.
These are hands-on tests with API keys.
