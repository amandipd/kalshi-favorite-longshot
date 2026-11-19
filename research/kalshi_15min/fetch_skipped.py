"""Per-minute history for the 15-minute series the bot skips, so the live rule can be replayed on them.

skipped_scan.json (scan_skipped) says which of the 16 skipped series have ever settled a market. This
fetches every minute 1-15 of every settled market in them -- the last traded price and the YES bid/ask at
the end of each minute -- into minutes_skipped.csv, the same columns as the other minute files, with the
same code as fetch_minutes.py.

Markets in one window share an open and close time, so a window's markets go in one candlesticks call
whatever series they belong to, up to TICKERS_PER_CALL. Appends as it goes; a rerun skips windows already
saved.

    python fetch_skipped.py
"""
import csv
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from backtest_large import BASE, get
from fetch_minutes import FIELDS, fetch_window

OUT_CSV = "minutes_skipped.csv"
SCAN = "skipped_scan.json"
TICKERS_PER_CALL = 20   # Kalshi's candlesticks endpoint takes a list; keep each call small
WORKERS = 8


def scanned():
    """scan_skipped.py's rows, from the file it writes or a bare list of them."""
    with open(SCAN, encoding="utf-8") as fh:
        d = json.load(fh)
    return d["series"] if isinstance(d, dict) else d


def all_markets(series):
    out, cursor = [], None
    while True:
        params = {"series_ticker": series, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get(f"{BASE}/markets", params=params)
        if not d:
            return out
        out += d.get("markets", [])
        cursor = d.get("cursor")
        if not cursor:
            return out


def settled(series):
    """Every settled market in these series, as fetch_window wants them."""
    out = []
    for s in series:
        out += [{"ticker": m["ticker"], "series": s, "open_time": m["open_time"],
                 "resolved_yes": "1" if m.get("result") == "yes" else "0"}
                for m in all_markets(s) if m.get("result") in ("yes", "no")]
    return out


def batches(markets):
    """(open_time, markets) a call at a time: one window's markets together, capped at TICKERS_PER_CALL."""
    windows = defaultdict(list)
    for m in markets:
        windows[m["open_time"]].append(m)
    for t in sorted(windows):
        ms = windows[t]
        for i in range(0, len(ms), TICKERS_PER_CALL):
            yield t, ms[i:i + TICKERS_PER_CALL]


def done():
    if not os.path.exists(OUT_CSV):
        return set()
    with open(OUT_CSV) as fh:
        return {r["open_time"] for r in csv.DictReader(fh)}


def main():
    series = [s["ticker"] for s in scanned() if s["settled"]]
    if not series:
        print("no skipped series has settled a market yet; nothing to fetch")
        return
    print(f"listing settled markets in {len(series)} series", flush=True)
    markets = settled(series)
    saved = done()
    todo = [(t, ms) for t, ms in batches(markets) if t not in saved]
    print(f"{len(markets)} settled markets, {len(saved)} windows already saved, {len(todo)} calls to make", flush=True)
    if not todo:
        return
    started = time.time()
    new_file = not os.path.exists(OUT_CSV)
    with open(OUT_CSV, "a", newline="") as fh, ThreadPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        futures = [pool.submit(fetch_window, t, ms) for t, ms in todo]
        rows = 0
        for n, f in enumerate(as_completed(futures), 1):
            try:
                got = f.result()
            except Exception as e:
                print("  call failed:", e, flush=True)
                continue
            w.writerows(got)
            rows += len(got)
            if n % 100 == 0:
                fh.flush()
            if n % 500 == 0:
                print(f"  {n}/{len(todo)} calls, {rows} markets ({time.time() - started:.0f}s)", flush=True)
    print(f"wrote {rows} markets to {OUT_CSV} in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
