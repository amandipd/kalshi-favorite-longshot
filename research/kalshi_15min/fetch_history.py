"""Every 15-minute market Kalshi has, back to the first one: the rest of the history.

Kalshi's 15-minute markets began on Jul 18, 2026 (crypto); gold, silver and oil followed on Jul 31,
copper and natural gas on Aug 27, platinum and palladium on Sep 17, Coin Race on Aug 20 and FX on
Sep 23. minutes_30d.csv (Aug 24 - Sep 23) and minutes_new.csv already hold part of that; this fetches
every other settled market up to the last full day, with the same per-window candle code (fetch_minutes.py),
into minutes_ext.csv. Resumable: a rerun skips markets already saved in any of the three files.

    python fetch_history.py
"""
import csv
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetch_all15 import all_markets
from fetch_minutes import FIELDS, fetch_window

START = "2026-07-18T00:00:00Z"
END = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")  # up to the last full day (UTC)
OUT_CSV = "minutes_ext.csv"


def saved_tickers():
    have = set()
    for path in ("minutes_30d.csv", "minutes_new.csv", OUT_CSV):
        if os.path.exists(path):
            with open(path) as fh:
                have |= {r["ticker"] for r in csv.DictReader(fh)}
    return have


def main():
    with open("universe.json", encoding="utf-8") as fh:
        series = [u["ticker"] for u in json.load(fh)["series"] if u["markets"]]
    have = saved_tickers()
    windows = defaultdict(list)
    for s in series:
        for m in all_markets(s):
            if m.get("result") in ("yes", "no") and START <= m["open_time"] < END and m["ticker"] not in have:
                windows[m["open_time"]].append({"ticker": m["ticker"], "series": s, "open_time": m["open_time"],
                                                "resolved_yes": "1" if m["result"] == "yes" else "0"})
    total = sum(len(v) for v in windows.values())
    print(f"{len(series)} series; {total} markets to fetch in {len(windows)} windows ({len(have)} already saved)", flush=True)
    started = time.time()
    new_file = not os.path.exists(OUT_CSV)
    done = 0
    with open(OUT_CSV, "a", newline="") as fh, ThreadPoolExecutor(max_workers=3) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        futures = {pool.submit(fetch_window, o, windows[o]): o for o in sorted(windows)}
        for f in as_completed(futures):
            rows = f.result()
            w.writerows(rows)
            done += 1
            if done % 200 == 0:
                fh.flush()
                print(f"  {done}/{len(windows)} windows ({time.time() - started:.0f}s)", flush=True)
    print(f"done in {time.time() - started:.0f}s; rerun to pick up any window that failed", flush=True)


if __name__ == "__main__":
    main()
