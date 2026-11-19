"""
Backtest: across Kalshi's 15-minute up/down markets, look at the price 8 minutes
into the 15-minute window. Where that price sits near 70c (65-75c band), what
fraction of those contracts actually settled YES, and what's the resulting EV?
"""
import requests
import time
from datetime import datetime, timezone

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = [
    "KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M", "KXHYPE15M",
    "KXNEAR15M", "KXDOGE15M", "KXZEC15M", "KXGOLD15M", "KXSILVER15M",
    "KXPLATINUM15M", "KXCOPPER15M", "KXPALLADIUM15M", "KXNATGAS15M", "KXWTI15M",
]

MARKETS_PER_SERIES = 150
PRICE_LOW, PRICE_HIGH = 0.65, 0.75
MINUTE_MARK = 8  # minutes elapsed into the 15-min window

session = requests.Session()


def get(url, params=None, retries=4):
    for i in range(retries):
        r = session.get(url, params=params, timeout=10)
        if r.status_code == 429:
            time.sleep(1.0 + i)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def iso_to_ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def fetch_settled_markets(series_ticker, n):
    out = []
    cursor = None
    while len(out) < n:
        params = {"series_ticker": series_ticker, "status": "settled", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = get(f"{BASE}/markets", params=params)
        batch = d.get("markets", [])
        if not batch:
            break
        out.extend(batch)
        cursor = d.get("cursor")
        if not cursor:
            break
        time.sleep(0.05)
    return out[:n]


def price_at_minute(series_ticker, ticker, open_ts, minute):
    end_ts = open_ts + minute * 60
    d = get(
        f"{BASE}/series/{series_ticker}/markets/{ticker}/candlesticks",
        params={"start_ts": open_ts, "end_ts": end_ts, "period_interval": 1},
    )
    candles = d.get("candlesticks", [])
    if not candles:
        return None
    # candle whose end_period_ts matches the target minute mark
    target = [c for c in candles if c["end_period_ts"] == end_ts]
    c = target[0] if target else candles[-1]
    close = c["price"].get("close_dollars")
    if close is None:
        return None
    return float(close)


results = []  # (series, ticker, price_at_8min, resolved_yes)
per_series_counts = {}

for s in SERIES:
    markets = fetch_settled_markets(s, MARKETS_PER_SERIES)
    per_series_counts[s] = len(markets)
    print(f"{s}: fetched {len(markets)} settled markets")
    for m in markets:
        if m.get("result") not in ("yes", "no"):
            continue
        open_ts = iso_to_ts(m["open_time"])
        try:
            p = price_at_minute(s, m["ticker"], open_ts, MINUTE_MARK)
        except requests.HTTPError:
            continue
        time.sleep(0.03)
        if p is None:
            continue
        if PRICE_LOW <= p <= PRICE_HIGH:
            results.append((s, m["ticker"], p, m["result"] == "yes"))

print(f"\nTotal settled markets scanned: {sum(per_series_counts.values())}")
print(f"Contracts found priced {PRICE_LOW}-{PRICE_HIGH} at minute {MINUTE_MARK}: {len(results)}")

if results:
    n = len(results)
    wins = sum(1 for r in results if r[3])
    win_rate = wins / n
    avg_price = sum(r[2] for r in results) / n
    print(f"Win rate (actually resolved YES): {win_rate:.4f} ({wins}/{n})")
    print(f"Average entry price in this band: {avg_price:.4f}")

    # EV per $1 of capital allocated to a single contract at avg_price:
    # buy 1/avg_price contracts, payoff 1 if win else 0.
    ev_per_dollar = win_rate / avg_price - 1
    print(f"EV per $1 staked (buying YES at ~{avg_price:.2f}): {ev_per_dollar:+.4f}  ({ev_per_dollar*100:+.2f}%)")

    # by-series breakdown
    from collections import defaultdict
    by_series = defaultdict(list)
    for s, t, p, w in results:
        by_series[s].append(w)
    print("\nBy series:")
    for s, ws in sorted(by_series.items(), key=lambda x: -len(x[1])):
        wr = sum(ws) / len(ws)
        print(f"  {s}: n={len(ws)} win_rate={wr:.3f}")
else:
    print("No contracts found in that price band at that minute mark.")
