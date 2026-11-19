"""Fetch every minute (1-15) of every 15-minute market in snapshots_30d.csv.

One batch request per window returns all of that window's markets, since they
share an open and close time. For each market and minute k, records the last
traded price and the YES bid/ask at the end of minute k. A minute with no
candle carries the previous minute forward. Appends as it goes; a rerun skips
windows already saved.
"""
import csv
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from backtest_large import BASE, get, iso_to_ts

OUT_CSV = "minutes_30d.csv"
WORKERS = 12
MINUTES = range(1, 16)
FIELDS = (["series", "ticker", "open_time", "resolved_yes"]
          + [f"p{k}" for k in MINUTES] + [f"b{k}" for k in MINUTES] + [f"a{k}" for k in MINUTES])


def close(block):
    block = block or {}
    v = block.get("close_dollars", block.get("previous_dollars"))
    return float(v) if v is not None else None


def fetch_window(open_time, markets):
    open_ts = iso_to_ts(open_time)
    d = get(f"{BASE}/markets/candlesticks", params={
        "market_tickers": ",".join(m["ticker"] for m in markets),
        "start_ts": open_ts, "end_ts": open_ts + 900, "period_interval": 1})
    if not d:
        return []
    by_ticker = {m["market_ticker"]: m["candlesticks"] for m in d.get("markets", [])}
    rows = []
    for m in markets:
        candles = {(c["end_period_ts"] - open_ts) // 60: c for c in by_ticker.get(m["ticker"], [])}
        if not candles:
            continue
        row = {"series": m["series"], "ticker": m["ticker"], "open_time": open_time,
               "resolved_yes": m["resolved_yes"]}
        last = {"p": None, "b": None, "a": None}
        for k in MINUTES:
            c = candles.get(k)
            if c:
                for f, key in (("p", "price"), ("b", "yes_bid"), ("a", "yes_ask")):
                    v = close(c.get(key))
                    if v is not None:
                        last[f] = v
            for f in "pba":
                row[f"{f}{k}"] = "" if last[f] is None else last[f]
        rows.append(row)
    return rows


def main():
    windows = defaultdict(list)
    with open("snapshots_30d.csv") as fh:
        for r in csv.DictReader(fh):
            windows[r["open_time"]].append(r)

    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV) as fh:
            done = {r["open_time"] for r in csv.DictReader(fh)}
    todo = [(t, ms) for t, ms in sorted(windows.items()) if t not in done]
    print(f"{len(windows)} windows, {len(done)} already saved, fetching {len(todo)}", flush=True)

    started = time.time()
    new_file = not os.path.exists(OUT_CSV)
    with open(OUT_CSV, "a", newline="") as fh, ThreadPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        futures = [pool.submit(fetch_window, t, ms) for t, ms in todo]
        for n, f in enumerate(as_completed(futures), 1):
            try:
                w.writerows(f.result())
            except Exception as e:
                print("  window failed:", e, flush=True)
            if n % 100 == 0:
                fh.flush()
            if n % 500 == 0:
                print(f"  {n}/{len(todo)} windows ({time.time()-started:.0f}s)", flush=True)
    print(f"Done in {time.time()-started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
