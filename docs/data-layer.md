# Data Layer Design

Status: draft v0.2, 2026-10-16. Companion to `design.md` section 4,
`backtester.md` sections 1, 4, 5 and 7, and `screener.md` section 5.

The data layer is the first code the project writes, because the phase 0
measurements, the backtester and the live session all read through it. Its
job is boring on purpose: store what vendors send, adjust it correctly, flag
what looks wrong, and never let a reader see the future.

---

## 1. Layout

```
data/                              # gitignored, local or on the VPS volume
  raw/<vendor>/bars_1m/<SYMBOL>/<YYYY-MM>.parquet     # as received, unadjusted
  raw/<vendor>/bars_1d/<YYYY>.parquet                 # all symbols, one file per year
  raw/<vendor>/quotes/<SYMBOL>/<YYYY-MM-DD>.parquet   # NBBO samples, where collected
  raw/<vendor>/halts/<YYYY-MM-DD>.parquet
  ref/symbols.parquet                # symbol master with listing and delisting dates
  ref/corporate_actions.parquet      # splits, reverse splits, symbol changes
  ref/reference_daily.parquet        # per symbol per day: price, volume, float, flags
  catalog.duckdb                     # views over the parquet files plus small tables
```

Parquet files are the system of record for market data. DuckDB holds views
over them plus the small reference tables, and is what every reader queries.
Postgres (design.md section 3) holds the operational journal, not market data;
the two are joined only in reports.

Why not Postgres for bars: a year of minute bars for 1,500 symbols is around
150 million rows. Parquet compresses that to a few gigabytes and DuckDB scans
it faster than Postgres would, with no server to run during research.

---

## 2. Schema

**bars_1m** (view over raw parquet)

| column | type | notes |
|---|---|---|
| symbol | varchar | as traded on that date; see symbol changes below |
| ts | timestamp (UTC) | bar open time |
| open, high, low, close | double | unadjusted |
| volume | bigint | |
| trade_count | int | null when the vendor does not supply it |
| vwap | double | vendor-supplied where available |
| vendor | varchar | |

**bars_1d**: same columns at daily granularity.

**quotes** (sampled, not full depth)

| column | type | notes |
|---|---|---|
| symbol, ts | | |
| bid, ask | double | |
| bid_size, ask_size | int | |
| sample_kind | varchar | `scheduled` (fixed times of day), `signal` (attached to a candidate), `fill` (attached to an order) |

**halts**

| column | type | notes |
|---|---|---|
| symbol, halt_ts, resume_ts | | |
| reason | varchar | LULD, news pending, regulatory, other |
| source | varchar | `vendor`, `exchange_list`, `simulated` |
| reopen_price | double | first trade after resume |

**symbols** (reference)

| column | type | notes |
|---|---|---|
| symbol | varchar | |
| name | varchar | |
| exchange | varchar | NASDAQ, NYSE, AMEX (NYSE American), ARCA, OTC |
| listed_from | date | first date the symbol appears in daily bars |
| listed_to | date | null while listed; set when the vendor marks it inactive or bars stop for 10 sessions |
| tradable_at_broker | boolean | current value from the broker's assets endpoint; history lives in `symbol_attributes` |
| cik | varchar | SEC identifier, for filings lookups |

**corporate_actions**

| column | type | notes |
|---|---|---|
| symbol | varchar | |
| effective_date | date | |
| kind | varchar | `split`, `reverse_split`, `symbol_change`, `delisting` |
| ratio | double | new shares per old share; 0.1 for a 1-for-10 reverse split |
| new_symbol | varchar | for symbol changes |
| source | varchar | |

**reference_daily**

| column | type | notes |
|---|---|---|
| symbol, date | | |
| close, volume, dollar_volume | | |
| adv20_dollar | double | 20-session average dollar volume |
| spread_pct_est | double | from scheduled quote samples, null if none |
| halt_count_10d | int | |
| float_shares | bigint | approximate, with `float_source`; the value valid on `date`, taken from `symbol_attributes` |
| bid_price_deficiency | boolean | from exchange notices or 8-K, phase 2 |
| pump_score | double | design.md 5.2 |
| quality_flags | varchar[] | see section 5 |

**symbol_attributes** (point-in-time history for mutable reference fields)

| column | type | notes |
|---|---|---|
| symbol | varchar | |
| attribute | varchar | `tradable_at_broker`, `float_shares`, `shares_outstanding`, `exchange`, `bid_price_deficiency` |
| value | varchar | serialized |
| valid_from | date | first date this value was observed |
| valid_to | date | null while current |
| source | varchar | |

Readers ask for an attribute `as_of` a date and get the row whose
`valid_from <= as_of < valid_to`. This is what lets the screener run on a
historical date without seeing today's float or tradability
(`screener.md` section 5). The `symbols` and `reference_daily` tables carry
the convenient current or per-day value, derived from this table.

**filings** (phase 2, for the pump filter and the pre-session note)

| column | type | notes |
|---|---|---|
| cik, symbol | | |
| filed_at | timestamp | |
| form | varchar | 8-K, S-1, S-3, 424B, 10-Q, 10-K, SC 13D, and others |
| items | varchar[] | 8-K item numbers where applicable |
| url | varchar | EDGAR link |
| summary | varchar | one line, agent-written, optional |

**universe_snapshots**: `date`, `symbol`, `rank`, `score`, `config_hash`.
One row per symbol the screener selected for that date. This is the
point-in-time universe the backtester replays. The screener also writes
`screener_funnel` (counts per filter per date) and `screener_rejections`
(symbol, date, filter, value) so a backtest can show why a name was absent.

---

## 3. Vendor adapter interface

```python
class MarketDataVendor(Protocol):
    name: str
    def list_symbols(self, as_of: date | None) -> list[SymbolRecord]: ...
    def daily_bars(self, symbols: list[str], start: date, end: date) -> Frame: ...
    def minute_bars(self, symbol: str, start: date, end: date) -> Frame: ...
    def quotes(self, symbol: str, start: datetime, end: datetime, limit: int) -> Frame: ...
    def corporate_actions(self, start: date, end: date) -> Frame: ...
    def halts(self, day: date) -> Frame | None: ...        # None = not supported
    def supports_delisted(self) -> bool: ...
```

Implementations planned: `AlpacaVendor` (phase 0 onward), `PolygonVendor`
(if phase 0 shows Alpaca lacks delisted coverage or NBBO history),
`NasdaqHaltList` (halts only, scraped from the public halt page).

Vendor adapters write raw parquet and nothing else. Adjustment, flags and
reference tables are computed by the loader from raw data, so a vendor swap
never changes downstream logic.

---

## 4. Adjustment

Readers request bars with `adjusted=True` by default. The loader applies the
cumulative split factor from `corporate_actions` to every bar dated before
each action's effective date, multiplying prices by the inverse ratio and
volume by the ratio. Factors are applied only backward in time, never
forward, which is what keeps a reader at time T from seeing an action that
had not happened yet.

Symbol changes are handled by a `symbol_lineage` view that maps every
historical symbol to a stable internal id, so a backtest can follow a company
through a rename without special cases in strategy code.

Adjusted bars are computed on read, not stored. If a corporate action is
corrected, nothing has to be rebuilt.

---

## 5. Quality flags

Computed by the loader on ingest and stored in `reference_daily.quality_flags`
and as a per-bar bitmask in a sidecar parquet:

| flag | rule |
|---|---|
| `ohlc_inconsistent` | open or close outside [low, high] |
| `price_jump_no_action` | close moves more than 50 percent versus prior close with no corporate action within 2 sessions |
| `zero_volume_day` | daily volume 0 on a day the exchange was open |
| `sparse_minutes` | fewer than 200 minute bars in a regular session |
| `stale_quote` | a scheduled quote sample older than 60 seconds at sample time |
| `vendor_gap` | a trading day with no daily bar while the symbol is listed |

Strategies never see flagged bars as signal input; the `MarketContext`
filters them and reports the count. Reports show flag rates per vendor,
which is how a bad vendor gets caught.

---

## 6. Ingestion jobs

| Job | Schedule | Scope |
|---|---|---|
| `ingest_daily` | 18:00 ET every trading day | daily bars for every listed symbol, assets refresh, corporate actions, reference_daily recompute |
| `ingest_minutes_watchlist` | 18:30 ET | minute bars for today's watchlist plus every symbol traded |
| `ingest_minutes_backfill` | on demand | minute bars for a symbol list and date range, for research |
| `sample_quotes` | 10:00, 11:30, 14:00, 15:30 ET during sessions | NBBO for the watchlist, `sample_kind=scheduled` |
| `ingest_halts` | 18:00 ET | the day's halt list |
| `refresh_symbols` | 06:00 ET | assets endpoint, listing and delisting dates |

All jobs are idempotent: re-running a day overwrites that day's parquet
partition and recomputes derived rows for that day only.

---

## 7. Size and retention

Rough sizes at 1,500 listed symbols in the $1 to $5 band:

| Dataset | Rows per year | Compressed size per year |
|---|---|---|
| minute bars, full band | ~150 million | 4 to 8 GB |
| minute bars, watchlist only (50 per day) | ~5 million | under 300 MB |
| daily bars, all US listed | ~2.5 million | under 100 MB |
| quote samples, watchlist | ~50 thousand | negligible |

Phase 1 stores minute bars for the full band for two years to support
survivorship-safe backtests. Watchlist-only storage is not enough, because
the screener itself has to be backtested over the whole band.

---

## 8. Phase 0 measurements

`scripts/phase0/measure_universe.py` is the first consumer of this design and
answers the questions the design document leaves open:

1. Does the broker account payload carry the post-June-2026 intraday buying
   power fields, and what are their names?
2. How many listed symbols are in the $1 to $5 band with at least $2M average
   daily dollar volume, and what does the distribution of dollar volume look like?
3. For the top 50 by dollar volume: real spread as a percent of mid at four
   times of day, minute-bar sparsity, and the count of simulated LULD band
   breaches over 20 sessions.
4. Does the vendor return bars for symbols known to be delisted?

Its output is a CSV per question and a Markdown summary, which go into
`docs/phase0-results.md` with the numbers that replace the design's
assumptions.

## 9. Changelog

- v0.2: `symbol_attributes` history table for point-in-time reads, `filings`
  table, screener funnel and rejection tables, after `screener.md` review.
- v0.1: initial design.
