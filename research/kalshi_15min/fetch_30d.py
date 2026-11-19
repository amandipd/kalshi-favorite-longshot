"""Collect 8-minute snapshots for every 15-min market opened in the last 30 days.

Reuses rows already in snapshots_8min.csv and only fetches candlesticks for
markets not seen before.
"""
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from backtest_large import BASE, SERIES, get, iso_to_ts, snapshot

DAYS = 30
WORKERS = 16
OUT_CSV = "snapshots_30d.csv"

now = datetime.now(timezone.utc)
cutoff_ts = int((now - timedelta(days=DAYS)).timestamp())

cache = {}
with open("snapshots_8min.csv") as fh:
    for r in csv.DictReader(fh):
        cache[r["ticker"]] = r


def list_recent(series_ticker):
    out, cursor = [], None
    while True:
        params = {"series_ticker": series_ticker, "status": "settled", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = get(f"{BASE}/markets", params=params)
        if not d or not d.get("markets"):
            break
        page = d["markets"]
        out.extend(m for m in page if iso_to_ts(m["open_time"]) >= cutoff_ts)
        if all(iso_to_ts(m["open_time"]) < cutoff_ts for m in page):
            break
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


started = time.time()
todo, rows = [], []
for s in SERIES:
    ms = list_recent(s)
    hit = sum(1 for m in ms if m["ticker"] in cache)
    print(f"{s}: {len(ms)} markets in window ({hit} cached)", flush=True)
    for m in ms:
        if m["ticker"] in cache:
            c = cache[m["ticker"]]
            rows.append({k: c[k] for k in
                         ("series", "ticker", "open_time", "price_8min", "resolved_yes")})
        else:
            todo.append((s, m))

print(f"\nFetching {len(todo)} new candlestick snapshots...", flush=True)
done = 0
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    futs = [pool.submit(snapshot, s, m) for s, m in todo]
    for f in as_completed(futs):
        done += 1
        try:
            r = f.result()
        except Exception:
            r = None
        if r:
            rows.append({k: r[k] for k in
                         ("series", "ticker", "open_time", "price_8min", "resolved_yes")})
        if done % 1000 == 0:
            print(f"  {done}/{len(todo)} ({time.time()-started:.0f}s)", flush=True)

with open(OUT_CSV, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["series", "ticker", "open_time",
                                       "price_8min", "resolved_yes"])
    w.writeheader()
    w.writerows(rows)

print(f"\nWrote {len(rows)} rows to {OUT_CSV} "
      f"(window starts {datetime.fromtimestamp(cutoff_ts, timezone.utc):%Y-%m-%d %H:%M} UTC) "
      f"in {time.time()-started:.0f}s")
