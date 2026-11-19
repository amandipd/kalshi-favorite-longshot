"""
Large-sample version of the 15-minute-market backtest.

For every settled Kalshi 15-minute up/down market we can reach, record the
traded price 8 minutes into the 15-minute window and whether it settled YES.
Raw rows go to CSV so the analysis can be redone without re-fetching.
"""
import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = [
    "KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M", "KXHYPE15M",
    "KXNEAR15M", "KXDOGE15M", "KXZEC15M", "KXGOLD15M", "KXSILVER15M",
    "KXPLATINUM15M", "KXCOPPER15M", "KXPALLADIUM15M", "KXNATGAS15M", "KXWTI15M",
]

MARKETS_PER_SERIES = 2000
MINUTE_MARK = 8
REQUESTS_PER_SEC = 14.0   # Basic tier allows ~20 reads/sec; stay under it
WORKERS = 12
OUT_CSV = "snapshots_8min.csv"

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=WORKERS * 2))
        _local.s = s
    return s


class RateLimiter:
    """Global pacer: spaces every outbound call >= 1/rate apart."""

    def __init__(self, rate):
        self.min_interval = 1.0 / rate
        self.lock = threading.Lock()
        self.next_allowed = 0.0

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            wait = self.next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self.next_allowed = now + self.min_interval


limiter = RateLimiter(REQUESTS_PER_SEC)


def get(url, params=None, retries=5):
    for i in range(retries):
        limiter.acquire()
        try:
            r = session().get(url, params=params, timeout=15)
        except requests.RequestException:
            time.sleep(0.5 * (i + 1))
            continue
        if r.status_code == 429:
            time.sleep(1.0 + i)
            continue
        if r.status_code >= 500:
            time.sleep(0.5 * (i + 1))
            continue
        r.raise_for_status()
        return r.json()
    return None


def iso_to_ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def fetch_settled_markets(series_ticker, n):
    out, cursor = [], None
    while len(out) < n:
        params = {"series_ticker": series_ticker, "status": "settled", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = get(f"{BASE}/markets", params=params)
        if not d:
            break
        batch = d.get("markets", [])
        if not batch:
            break
        out.extend(batch)
        cursor = d.get("cursor")
        if not cursor:
            break
    return out[:n]


def snapshot(series_ticker, market):
    """Price at the 8-minute mark plus the eventual result, or None."""
    result = market.get("result")
    if result not in ("yes", "no"):
        return None
    open_ts = iso_to_ts(market["open_time"])
    end_ts = open_ts + MINUTE_MARK * 60
    d = get(
        f"{BASE}/series/{series_ticker}/markets/{market['ticker']}/candlesticks",
        params={"start_ts": open_ts, "end_ts": end_ts, "period_interval": 1},
    )
    if not d:
        return None
    candles = d.get("candlesticks", [])
    if not candles:
        return None
    target = [c for c in candles if c["end_period_ts"] == end_ts]
    c = target[0] if target else candles[-1]
    close = c["price"].get("close_dollars")
    if close is None:
        return None
    vol = c.get("volume_fp")
    return {
        "series": series_ticker,
        "ticker": market["ticker"],
        "open_time": market["open_time"],
        "price_8min": float(close),
        "volume_8min": float(vol) if vol is not None else 0.0,
        "resolved_yes": int(result == "yes"),
    }


def main():
    started = time.time()
    all_markets = []
    for s in SERIES:
        ms = fetch_settled_markets(s, MARKETS_PER_SERIES)
        print(f"{s}: {len(ms)} settled markets listed", flush=True)
        all_markets.extend((s, m) for m in ms)

    print(f"\nListing done in {time.time()-started:.0f}s. "
          f"Fetching candlesticks for {len(all_markets)} markets...", flush=True)

    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(snapshot, s, m): (s, m["ticker"]) for s, m in all_markets}
        for f in as_completed(futures):
            done += 1
            try:
                r = f.result()
            except Exception:
                r = None
            if r:
                rows.append(r)
            if done % 2000 == 0:
                print(f"  {done}/{len(all_markets)} fetched "
                      f"({time.time()-started:.0f}s elapsed)", flush=True)

    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {len(rows)} snapshots to {OUT_CSV} in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
