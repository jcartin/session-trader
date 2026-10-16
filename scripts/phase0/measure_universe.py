"""Phase 0 measurements for Session Trader.

Answers the open questions in docs/data-layer.md section 8 against a live
Alpaca paper account. Read-only: it never places an order.

Usage:
    python scripts/phase0/measure_universe.py --out data/phase0 [--top 50] [--days 20]
        [--delisted SYM1,SYM2,...]

Requires ALPACA_API_KEY and ALPACA_SECRET_KEY in the environment or in .env.

STATUS: written without network access, so it has not been executed yet.
Expect small API shape corrections on first run; the logic is the point.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

try:
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, StockQuotesRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import AssetClass, AssetStatus
    from alpaca.trading.requests import GetAssetsRequest
except ImportError:  # pragma: no cover
    sys.exit("alpaca-py is not installed. Run: pip install -e .")

ET = ZoneInfo("America/New_York")
LISTED_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "ARCA", "NYSEARCA"}
PRICE_LOW, PRICE_HIGH = 1.00, 5.00
MIN_ADV_DOLLARS = 2_000_000
QUOTE_SAMPLE_TIMES = [time(10, 0), time(11, 30), time(14, 0), time(15, 30)]


# ----------------------------------------------------------------------------
# LULD band model (design.md C5). Data, not code, so a rule change is an edit.
# ----------------------------------------------------------------------------
def luld_band_pct(ref_price: float, t: time) -> float:
    """Return the band as a fraction of the reference price for a Tier 2 stock."""
    if ref_price > 3.00:
        band = 0.10
    elif ref_price >= 0.75:
        band = 0.20
    else:
        return max(0.15 / ref_price, 0.75) if ref_price > 0 else 0.75
    if t >= time(15, 35) and ref_price <= 3.00:
        band *= 2
    return band


def simulated_breaches(bars: list[dict]) -> int:
    """Count minute bars whose close sits outside the LULD band around the
    trailing 5-minute volume-weighted average. Approximates design.md C5."""
    breaches = 0
    window: list[tuple[float, int]] = []
    for b in bars:
        if window:
            vol = sum(v for _, v in window) or 1
            ref = sum(p * v for p, v in window) / vol
            band = luld_band_pct(ref, b["ts_et"].time())
            if b["close"] > ref * (1 + band) or b["close"] < ref * (1 - band):
                breaches += 1
        window.append((b["close"], max(b["volume"], 1)))
        if len(window) > 5:
            window.pop(0)
    return breaches


# ----------------------------------------------------------------------------
# Clients
# ----------------------------------------------------------------------------
def clients() -> tuple[TradingClient, StockHistoricalDataClient, DataFeed]:
    load_dotenv()
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set ALPACA_API_KEY and ALPACA_SECRET_KEY (see .env.example)")
    paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    feed = DataFeed.SIP if os.getenv("ALPACA_FEED", "iex").lower() == "sip" else DataFeed.IEX
    return TradingClient(key, secret, paper=paper), StockHistoricalDataClient(key, secret), feed


# ----------------------------------------------------------------------------
# Q1: account payload fields
# ----------------------------------------------------------------------------
def q1_account_fields(trading: TradingClient, out: Path) -> dict:
    acct = trading.get_account()
    payload = acct.model_dump() if hasattr(acct, "model_dump") else dict(acct)
    # Redact identifiers; keep field names and numeric values.
    for k in ("id", "account_number"):
        payload.pop(k, None)
    (out / "q1_account_fields.json").write_text(json.dumps(payload, indent=2, default=str))
    keys = sorted(payload)
    deprecated = [k for k in keys if "daytrade" in k or "pattern_day" in k or k == "daytrading_buying_power"]
    intraday = [k for k in keys if "intraday" in k or "buying_power" in k]
    return {"all_fields": keys, "day_trade_fields_present": deprecated, "buying_power_fields": intraday}


# ----------------------------------------------------------------------------
# Q2: universe size
# ----------------------------------------------------------------------------
def q2_universe(trading: TradingClient, data: StockHistoricalDataClient, feed: DataFeed,
                out: Path, days: int) -> list[dict]:
    assets = trading.get_all_assets(GetAssetsRequest(asset_class=AssetClass.US_EQUITY,
                                                     status=AssetStatus.ACTIVE))
    listed = [a for a in assets if a.tradable and str(a.exchange).split(".")[-1] in LISTED_EXCHANGES]
    symbols = [a.symbol for a in listed]
    print(f"Q2: {len(assets)} active assets, {len(listed)} tradable on listed exchanges")

    end = datetime.now(timezone.utc) - timedelta(minutes=20)  # IEX free tier blocks the last 15 min
    start = end - timedelta(days=int(days * 1.6) + 5)
    rows: dict[str, list] = {}
    for i in range(0, len(symbols), 200):
        chunk = symbols[i:i + 200]
        req = StockBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Day,
                               start=start, end=end, feed=feed)
        bars = data.get_stock_bars(req)
        for sym, series in bars.data.items():
            rows[sym] = [(b.close, b.volume) for b in series]
        print(f"  daily bars: {min(i + 200, len(symbols))}/{len(symbols)}", end="\r")
    print()

    universe = []
    for sym, series in rows.items():
        if len(series) < max(5, days // 2):
            continue
        last = series[-days:]
        close = last[-1][0]
        adv = sum(c * v for c, v in last) / len(last)
        if PRICE_LOW <= close <= PRICE_HIGH and adv >= MIN_ADV_DOLLARS:
            universe.append({"symbol": sym, "close": round(close, 4), "adv_dollars": round(adv),
                             "sessions": len(last)})
    universe.sort(key=lambda r: -r["adv_dollars"])
    with (out / "q2_universe.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "close", "adv_dollars", "sessions"])
        w.writeheader(); w.writerows(universe)
    print(f"Q2: {len(universe)} symbols in ${PRICE_LOW:.2f}-${PRICE_HIGH:.2f} with ADV >= ${MIN_ADV_DOLLARS:,}")
    return universe


# ----------------------------------------------------------------------------
# Q3: spreads, sparsity, simulated halts for the top N
# ----------------------------------------------------------------------------
def q3_microstructure(data: StockHistoricalDataClient, feed: DataFeed, out: Path,
                      universe: list[dict], top: int, days: int) -> list[dict]:
    end = datetime.now(timezone.utc) - timedelta(minutes=20)
    start = end - timedelta(days=int(days * 1.6) + 5)
    results = []
    for n, row in enumerate(universe[:top], 1):
        sym = row["symbol"]
        req = StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute,
                               start=start, end=end, feed=feed)
        series = data.get_stock_bars(req).data.get(sym, [])
        bars = []
        for b in series:
            ts_et = b.timestamp.astimezone(ET)
            if time(9, 30) <= ts_et.time() < time(16, 0):
                bars.append({"ts_et": ts_et, "close": b.close, "volume": b.volume})
        sessions = {b["ts_et"].date() for b in bars}
        per_session = len(bars) / max(len(sessions), 1)

        # Spread samples: a short quote window at each scheduled time over the last 5 sessions.
        spreads = []
        for d in sorted(sessions)[-5:]:
            for t in QUOTE_SAMPLE_TIMES:
                t0 = datetime.combine(d, t, ET)
                qreq = StockQuotesRequest(symbol_or_symbols=sym, start=t0,
                                          end=t0 + timedelta(seconds=30), limit=5, feed=feed)
                try:
                    quotes = data.get_stock_quotes(qreq).data.get(sym, [])
                except Exception as e:  # rate limits, entitlement errors
                    print(f"  {sym} quotes {d} {t}: {e}")
                    quotes = []
                for q in quotes:
                    if q.bid_price and q.ask_price and q.ask_price >= q.bid_price:
                        mid = (q.bid_price + q.ask_price) / 2
                        spreads.append((q.ask_price - q.bid_price) / mid)
                        break
        spreads.sort()
        med = spreads[len(spreads) // 2] if spreads else None
        p90 = spreads[int(len(spreads) * 0.9)] if spreads else None

        results.append({
            "symbol": sym, "adv_dollars": row["adv_dollars"], "close": row["close"],
            "sessions": len(sessions), "minute_bars_per_session": round(per_session),
            "spread_median_pct": round(med * 100, 3) if med is not None else "",
            "spread_p90_pct": round(p90 * 100, 3) if p90 is not None else "",
            "quote_samples": len(spreads),
            "simulated_luld_breaches": simulated_breaches(bars),
        })
        print(f"Q3: {n}/{min(top, len(universe))} {sym}: {per_session:.0f} bars/session, "
              f"median spread {'' if med is None else f'{med*100:.2f}%'}, "
              f"breaches {results[-1]['simulated_luld_breaches']}")
    with (out / "q3_microstructure.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else ["symbol"])
        w.writeheader(); w.writerows(results)
    return results


# ----------------------------------------------------------------------------
# Q4: delisted ticker coverage
# ----------------------------------------------------------------------------
def q4_delisted(data: StockHistoricalDataClient, feed: DataFeed, out: Path,
                delisted: list[str]) -> list[dict]:
    results = []
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=730)
    for sym in delisted:
        try:
            series = data.get_stock_bars(StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Day,
                                                          start=start, end=end, feed=feed)).data.get(sym, [])
            first = series[0].timestamp.date().isoformat() if series else ""
            last = series[-1].timestamp.date().isoformat() if series else ""
            results.append({"symbol": sym, "daily_bars": len(series), "first": first, "last": last, "error": ""})
        except Exception as e:
            results.append({"symbol": sym, "daily_bars": 0, "first": "", "last": "", "error": str(e)[:120]})
        print(f"Q4: {sym}: {results[-1]}")
    with (out / "q4_delisted.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "daily_bars", "first", "last", "error"])
        w.writeheader(); w.writerows(results)
    return results


# ----------------------------------------------------------------------------
def summarize(out: Path, q1: dict, universe: list[dict], micro: list[dict], delisted: list[dict],
              feed: DataFeed) -> None:
    def med(vals):
        vals = sorted(v for v in vals if v != "")
        return vals[len(vals) // 2] if vals else "n/a"
    lines = [
        f"# Phase 0 results ({date.today().isoformat()}, feed={feed.value})", "",
        "## Q1 account fields",
        f"- day-trade era fields still present: {q1['day_trade_fields_present'] or 'none'}",
        f"- buying power fields: {q1['buying_power_fields']}", "",
        "## Q2 universe",
        f"- symbols in band with ADV >= ${MIN_ADV_DOLLARS:,}: {len(universe)}",
        f"- median ADV among them: ${med([u['adv_dollars'] for u in universe]):,}" if universe else "- none", "",
        "## Q3 microstructure (top names by ADV)",
        f"- median of median spreads: {med([m['spread_median_pct'] for m in micro])} %",
        f"- median p90 spread: {med([m['spread_p90_pct'] for m in micro])} %",
        f"- median minute bars per session (390 is complete): {med([m['minute_bars_per_session'] for m in micro])}",
        f"- names with any simulated LULD breach: {sum(1 for m in micro if m['simulated_luld_breaches'])}/{len(micro)}", "",
        "## Q4 delisted coverage",
        *[f"- {d['symbol']}: {d['daily_bars']} daily bars {d['first']}..{d['last']} {d['error']}" for d in delisted],
        "", "Note: on the IEX feed, spreads and volume understate consolidated reality (design.md C6).",
    ]
    (out / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/phase0")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--delisted", default="", help="comma-separated symbols known to be delisted")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    trading, data, feed = clients()
    q1 = q1_account_fields(trading, out)
    universe = q2_universe(trading, data, feed, out, args.days)
    micro = q3_microstructure(data, feed, out, universe, args.top, args.days)
    delisted = q4_delisted(data, feed, out, [s.strip().upper() for s in args.delisted.split(",") if s.strip()])
    summarize(out, q1, universe, micro, delisted, feed)


if __name__ == "__main__":
    main()
