# Universe Screener Design

Status: draft v0.1, 2026-10-16
Companion to `design.md` sections 2 (C3, C4, C5, C7, C12), 5.1, 5.2, 6.1 and 8; `data-layer.md` sections 2, 6 and 8; `backtester.md` section 7; `risk-manager.md` section 2.

The screener decides what the system is allowed to look at. It runs once before each session, reads only data that existed at that moment, and writes a ranked watchlist. Everything downstream, from strategies to the risk manager's price band, assumes the watchlist has already removed the names that cannot be traded profitably or safely. The pump detector is its most important part, because in this universe the loudest names are usually the ones to avoid.

---

## 1. Inputs

All inputs come from the data layer as of a single `as_of` date, which is the prior trading day for a live run or the historical date for a backtest.

| Source (data-layer.md 2) | Fields used |
|---|---|
| `symbols` | `exchange`, `listed_from`, `listed_to`, `tradable_at_broker`, `cik` |
| `reference_daily` | `close`, `volume`, `dollar_volume`, `adv20_dollar`, `spread_pct_est`, `halt_count_10d`, `float_shares`, `float_source`, `bid_price_deficiency`, `quality_flags` |
| `bars_1d` | 60 sessions of OHLCV for surge, range and volume features |
| `corporate_actions` | `reverse_split`, `split`, `symbol_change` within lookback windows |
| `halts` | counts by day for the halt filter and the pump score |
| `filings` (phase 2, EDGAR index) | 8-K, S-1, S-3, 424B prospectus supplements, 10-Q share counts by `cik` |
| `blacklist.yaml` | operator-maintained symbols with a reason and an expiry |

The screener never reads quotes, minute bars or anything timestamped after `as_of` 16:00 ET. Pre-market activity on the session day is excluded in v1; `design.md` 5.1 mentions it and it is deferred to section 9.

---

## 2. Filter pipeline

Filters run in order. Each records how many symbols it removed, and every removed symbol is journaled with the filter name, so the funnel is visible per day.

| # | Filter | Default (`screener.yaml`) | Removes a symbol when |
|---|---|---|---|
| 1 | `listed_exchange` | `exchanges: [NASDAQ, NYSE, AMEX]` | exchange not in the set (ARCA and NYSEARCA are ETFs, excluded; OTC excluded, design 11) |
| 2 | `listed_as_of` | n/a | `listed_from > as_of` or `listed_to <= as_of` |
| 3 | `tradable_at_broker` | n/a | broker asset record not tradable as of the latest refresh before `as_of` |
| 4 | `price_band` | `price_floor: 1.00`, `price_ceiling: 5.00` | prior close outside the band |
| 5 | `min_history` | `min_sessions: 40` | fewer than 40 daily bars; too new to compute features (also excludes fresh IPOs and SPAC de-SPACs, which is intended) |
| 6 | `min_adv` | `min_adv_dollar: 2000000` | `adv20_dollar < 2,000,000` |
| 7 | `max_spread` | `max_spread_pct: 1.5`, `spread_lookback_sessions: 5` | mean `spread_pct_est` over 5 sessions above 1.5 percent, or no estimate and the universe prior for the price band (backtester.md 4) exceeds the limit |
| 8 | `max_halts` | `max_halts_10d: 1` | `halt_count_10d >= 2` |
| 9 | `no_recent_reverse_split` | `reverse_split_lookback_days: 30` | a `reverse_split` action with effective date in the last 30 days |
| 10 | `no_bid_price_deficiency` | n/a | `bid_price_deficiency` true (phase 2; passes everything in phase 1 with a journaled warning) |
| 11 | `quality` | `max_flagged_sessions_20d: 2` | more than 2 of the last 20 sessions carry `ohlc_inconsistent`, `price_jump_no_action` or `vendor_gap` |
| 12 | `pump_filter` | `pump_exclude_threshold: 0.70` | pump score at or above 0.70 (section 4) |
| 13 | `blacklist` | `blacklist.yaml` | symbol listed and not expired |

Filter 7 is the one most likely to be too loose or too tight. Phase 0's spread measurements (`data-layer.md` 8) set it; until then 1.5 percent is the design assumption from `design.md` C3.

Filter 10 depends on exchange notice ingestion that does not exist until phase 2. Until then, the reverse-split filter and the pump score's compliance feature are the proxies.

---

## 3. Ranking

Survivors are scored and the top `watchlist_size: 40` (range 20 to 50) are written. The score is a weighted sum of three features, each normalized to 0 to 1 by percentile rank within the day's survivors so the weights mean the same thing on quiet and busy days.

| Feature | Definition | Weight (`rank_weights`) | Why |
|---|---|---|---|
| `relative_volume` | `dollar_volume(as_of) / adv20_dollar`, clipped to [0.2, 5] | 0.40 | the intraday strategies in design 5.3 need participation |
| `range_consistency` | `median(high - low) / median(close)` over 20 sessions, divided by its own standard deviation; higher means the stock moves a repeatable amount each day | 0.35 | a stock that reliably moves 4 percent a day can pay a 1 percent spread; one that moves 1 percent cannot |
| `spread_tightness` | `1 - spread_pct_est / max_spread_pct` | 0.25 | cost |

```
score = 0.40 * pct_rank(relative_volume)
      + 0.35 * pct_rank(range_consistency)
      + 0.25 * pct_rank(spread_tightness)
      - pump_penalty                                 # section 4.4
```

Ties break on `adv20_dollar` descending. Weights are parameters in `screener.yaml` and changing them follows the `strategies.yaml` change path in `design.md` 6.4: the agent proposes with a backtest, the human merges.

---

## 4. Pump detection

### 4.1 Why it is its own component

`design.md` C7: promotions dominate volume spikes in this price band. A naive screener that ranks by relative volume will fill the watchlist with promoted names, and a momentum strategy will then buy the top of them. The pump detector is therefore run before ranking, as filter 12, and feeds a penalty into the rank for names that pass.

The detector does not try to prove manipulation. It estimates the probability that recent activity is driven by promotion or dilution rather than business news, and treats that as a cost.

### 4.2 Features

Each feature is computed from data available as of `as_of` and produces a value in [0, 1].

| Feature | Computation | Data needed | Phase |
|---|---|---|---|
| `surge_no_news` | 1 if close up more than 50 percent over any 1 to 3 session window in the last 5 sessions **and** mean volume in that window above 5x `adv20_dollar / close` **and** no 8-K or press release from the issuer within 2 sessions before the surge; scaled linearly from 0 at 25 percent / 3x | `bars_1d`; `filings` 8-K index by `cik` | 1 (without filings: surge only, weight halved); 2 (with filings) |
| `dilution` | relative increase in shares outstanding between the two most recent 10-Q or 10-K filings, plus 0.5 if an S-1, S-3 or 424B was filed in the last 90 days; capped at 1 | `filings`, `float_shares` history | 2 |
| `reverse_split_history` | number of `reverse_split` actions in the last 3 years, scaled 0 at zero, 0.5 at one, 1 at two or more | `corporate_actions` | 1 |
| `compliance_history` | 1 if a bid-price deficiency notice or 8-K item 3.01 in the last 12 months; 0.5 if in the last 24 months | `filings`, exchange notices | 2 |
| `float_turnover` | `volume(as_of) / float_shares`; scaled 0 at 0.2, 1 at 2.0 (the float changing hands twice in a day is a promotion signature) | `reference_daily`, `float_shares` with `float_source` not `unknown` | 1 |
| `halt_cluster` | 1 if 2 or more LULD halts in the last 3 sessions, 0.5 if one | `halts` | 1 |
| `promo_mentions` | keyword scan of press-release feeds and public social sources for the symbol in the last 5 sessions; scaled by mention count relative to the symbol's own 60-day baseline | news and social ingest | 3 (zero until then) |

Features whose data is unavailable for a phase contribute 0 and are reported as `unavailable`, so the score is honest about what it knows.

### 4.3 Score and threshold

```
pump_score = 0.30 * surge_no_news
           + 0.20 * dilution
           + 0.15 * reverse_split_history
           + 0.10 * compliance_history
           + 0.15 * float_turnover
           + 0.05 * halt_cluster
           + 0.05 * promo_mentions
```

The weights sum to 1. Where features are unavailable the remaining weights are renormalized to sum to 1, and the result is marked `partial`. The journal stores every feature value alongside the score.

| Band | Score | Treatment |
|---|---|---|
| clear | below 0.40 | no penalty |
| borderline | 0.40 to 0.70 | stays in the universe; `pump_penalty = (score - 0.40) * 0.5` subtracted from the rank score; listed in the agent's pre-session note |
| excluded | 0.70 and above | removed by filter 12, journaled with its feature vector |

A single feature at 1.0 cannot exclude a name on its own (maximum single weight is 0.30), which is intended: a legitimate 60 percent gap on earnings should not be excluded by `surge_no_news` alone, and the feature's filing check would zero it anyway. Two or three co-occurring features do exclude, which matches the description in `design.md` 5.2.

### 4.4 The agent's pre-session note

At 08:30 ET (`design.md` 6.1) the agent reviewer reads the day's `universe_snapshots` and the pump feature vectors and writes a short note:

- every borderline name with the two features that drove its score, one line each;
- any excluded name that would otherwise have ranked in the top 10, so the operator sees what the filter cost;
- any name whose `partial` flag is set because filings were unavailable;
- a recommendation per borderline name: keep, drop for today, or add to `blacklist.yaml` with an expiry.

The operator can drop names at 09:00 by adding them to the blacklist. The note is advisory; the screener's output is what runs. This keeps the LLM out of the deterministic path (`design.md` 8) while using it where reading filings is the job.

---

## 5. Point-in-time guarantee

The screener must produce the same watchlist for a historical date whether it runs today or ran on that date. Three mechanisms:

1. Every input query carries `as_of` and the data layer enforces it: `reference_daily` and `bars_1d` rows with `date > as_of` are invisible, `corporate_actions` with `effective_date > as_of` are invisible, `symbols.listed_to` is compared to `as_of`, and `filings` are filtered on their filing timestamp, not their period date.
2. Reference tables that are overwritten in place (`tradable_at_broker`, `float_shares`) are stored with a `valid_from` date and read as of `as_of`. Where no historical value exists (the first months of operation), the screener uses the earliest known value and marks the snapshot `reference_backfilled`, and the backtester reports the share of such days.
3. The screener's own code version and `screener.yaml` hash are written into every snapshot row, so two snapshots for the same date can be compared and the difference attributed.

The `backtester.md` section 7 point-in-time universe is exactly this screener run on each session date of the backtest window. The screener has no separate "backtest mode"; it only ever has an `as_of`.

---

## 6. Output

`universe_snapshots` (data-layer.md 2), one row per selected symbol:

| column | type | notes |
|---|---|---|
| `date` | date | session date the snapshot is for (`as_of` plus one trading day) |
| `as_of` | date | the data date used |
| `symbol` | varchar | |
| `rank` | int | 1 is best |
| `score` | double | section 3 |
| `pump_score` | double | section 4.3 |
| `pump_band` | varchar | clear, borderline |
| `features` | json | relative_volume, range_consistency, spread_tightness and all pump features with `unavailable` markers |
| `config_hash` | varchar | hash of `screener.yaml` plus `blacklist.yaml` |
| `code_version` | varchar | git SHA |
| `flags` | varchar[] | `reference_backfilled`, `partial_pump_score`, `spread_from_prior` |

A companion `screener_funnel` table stores, per `date`, the count entering and leaving each filter, and a `screener_rejections` table stores every removed symbol with the filter name and the pump feature vector when filter 12 did it. The funnel is what the weekly review looks at first: if filter 7 removes 80 percent of names, the spread assumption is wrong or the data is.

---

## 7. Run schedule

| When (ET) | What |
|---|---|
| 18:00 prior day | `ingest_daily` completes (data-layer.md 6); `reference_daily` is current |
| 08:00 | screener runs with `as_of` = prior trading day; writes `universe_snapshots`, funnel and rejections |
| 08:30 | agent pre-session note |
| 09:00 | operator blacklist edits; screener re-runs if `blacklist.yaml` changed, same `as_of` |
| 09:15 | PREFLIGHT loads the snapshot; refuses to activate if the snapshot's `as_of` is not the prior trading day or its `config_hash` does not match the files on disk |

The run is idempotent for a given `as_of` and config hash. Re-running overwrites that date's rows.

Runtime budget: under 2 minutes for roughly 6,000 listed symbols on a laptop. The pipeline is a handful of DuckDB queries over `reference_daily` plus per-symbol feature computation for the few hundred names that survive filter 6.

---

## 8. Configuration

```yaml
# screener.yaml
exchanges: [NASDAQ, NYSE, AMEX]
price_floor: 1.00
price_ceiling: 5.00
min_sessions: 40
min_adv_dollar: 2000000
max_spread_pct: 1.5
spread_lookback_sessions: 5
max_halts_10d: 1
reverse_split_lookback_days: 30
max_flagged_sessions_20d: 2
watchlist_size: 40                 # range 20 .. 50
rank_weights:
  relative_volume: 0.40
  range_consistency: 0.35
  spread_tightness: 0.25
pump:
  weights:
    surge_no_news: 0.30
    dilution: 0.20
    reverse_split_history: 0.15
    compliance_history: 0.10
    float_turnover: 0.15
    halt_cluster: 0.05
    promo_mentions: 0.05
  borderline_threshold: 0.40
  exclude_threshold: 0.70
  surge:
    price_pct_full: 50
    price_pct_zero: 25
    volume_mult_full: 5
    volume_mult_zero: 3
    news_window_sessions: 2
```

```yaml
# blacklist.yaml
- symbol: ABCD
  reason: "promotion run 2026-09, spread never recovered"
  added: 2026-10-02
  expires: 2027-01-02
```

Changes to `screener.yaml` follow the `strategies.yaml` path (agent proposes with backtest evidence, human merges). `blacklist.yaml` is operator-owned and needs no backtest; its edits are journaled as `operator_action` events.

---

## 9. Deferred

- **Pre-market activity** as a ranking feature. Requires pre-market bars and a definition of "as of" that includes the session morning; deferred until the point-in-time story for intraday data exists.
- **Short interest and borrow** features; not needed for long-only.
- **Sector and index context**, such as the small-cap index trend used by strategy 3 in `design.md` 5.3; belongs to the signal engine's market context, not the screener.

---

## 10. Test cases

Unit tests on a synthetic `reference_daily` fixture of 30 symbols covering every filter edge:

| ID | Filter or feature | Setup | Expected |
|---|---|---|---|
| SC-01 | price_band | close 0.99, 1.00, 5.00, 5.01 | out, in, in, out |
| SC-02 | min_adv | adv 1,999,999 and 2,000,000 | out, in |
| SC-03 | max_spread | 5-session mean 1.49 and 1.51 | in, out |
| SC-04 | max_spread, no estimate | `spread_pct_est` null, price 1.50 (prior 1.5 percent) | out, flag `spread_from_prior` |
| SC-05 | max_halts | 1 halt in 10 sessions, 2 halts | in, out |
| SC-06 | reverse split | effective 29 days ago, 31 days ago | out, in |
| SC-07 | listed_as_of | `listed_to` equal to `as_of` | out |
| SC-08 | tradable | broker flag false | out |
| SC-09 | quality | 3 flagged sessions of 20 | out |
| SC-10 | ranking | three survivors with known features | order and scores match hand computation |
| SC-11 | ranking normalization | identical features on a 5-name and a 500-name day | identical scores |
| SC-12 | pump surge | +60 percent in 2 sessions, 7x volume, no filing | `surge_no_news` 1.0 |
| SC-13 | pump surge with news | same, 8-K filed the day before | `surge_no_news` 0.0 |
| SC-14 | pump surge partial | +35 percent, 4x volume | 0.4 and 0.5 scaled, feature 0.45 (mean of the two scalings) |
| SC-15 | pump reverse splits | 0, 1, 2, 3 in 3 years | 0, 0.5, 1, 1 |
| SC-16 | pump float turnover | volume equals 1.1x float | 0.5 |
| SC-17 | pump renormalization | filings unavailable | weights renormalize, flag `partial_pump_score` |
| SC-18 | pump bands | scores 0.39, 0.40, 0.69, 0.70 | clear, borderline, borderline, excluded |
| SC-19 | pump penalty | borderline 0.60 | penalty 0.10 subtracted from rank score |
| SC-20 | blacklist | expired entry | symbol passes |
| SC-21 | point in time | run with `as_of` D using a dataset that also contains D+1 rows | identical output to the same run on a dataset truncated at D |
| SC-22 | point in time, corporate action | reverse split effective D+1 | not visible for `as_of` D |
| SC-23 | idempotence | run twice | same rows, same hashes |
| SC-24 | funnel | fixture | per-filter counts sum to input count minus output count |

Fixture-based regression test on a known pump:

| ID | Setup | Expected |
|---|---|---|
| SC-30 | A recorded fixture of a real 2024 or 2025 promotion in the $1 to $5 band (symbol redacted in the repo, data in `tests/fixtures/pump_001/`): daily bars, corporate actions, filing index and float history for 90 sessions around the surge | pump score below 0.40 for every `as_of` before the surge begins; crosses 0.70 within 2 sessions of the surge day; the symbol is absent from `universe_snapshots` for the 5 sessions following; the journal shows `surge_no_news` and `float_turnover` as the top two features |
| SC-31 | A control fixture: a legitimate 50 percent earnings gap with an 8-K the same day | score stays below 0.40; symbol remains eligible |

SC-30 and SC-31 are the acceptance tests for the pump detector. Phase 0 or early phase 1 selects the two fixtures from real data; the test files hold the data, and the symbol names live only in a local notes file.

---

## 11. Changelog

- v0.1: initial design.
