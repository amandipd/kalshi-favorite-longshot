"""Every settled 15-minute market in the bot's 16 series that opened Oct 9 - Oct 29 2026 (UTC), minute by minute
(PREREG.md). Uses the research's own candle code (research/kalshi_15min/fetch_minutes.py fetch_window), so the rows
match the ones lab/markets.npz was built from. Resumable: a rerun skips windows already saved.

    python fetch_recent.py      -> recent_minutes.csv
"""
import csv
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kalshi_15min"))
from backtest_large import BASE, SERIES, get, iso_to_ts  # noqa: E402
from fetch_minutes import FIELDS, fetch_window  # noqa: E402

START, END = "2026-10-09T00:00:00Z", "2026-10-30T00:00:00Z"
OUT = os.path.join(HERE, "recent_minutes.csv")
WORKERS = 3   # gentle: the laptop's thin-market recorder shares Kalshi's rate limit


def settled(series):
    out, cursor = [], None
    while True:
        params = {"series_ticker": series, "status": "settled", "limit": 1000,
                  "min_close_ts": iso_to_ts(START), "max_close_ts": iso_to_ts(END) + 900}
        if cursor:
            params["cursor"] = cursor
        d = get(f"{BASE}/markets", params=params)
        if not d:
            return out
        out += d.get("markets", [])
        cursor = d.get("cursor")
        if not cursor:
            return out


def main():
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as fh:
            done = {r["open_time"] for r in csv.DictReader(fh)}
    windows = defaultdict(list)
    for s in SERIES:
        n = 0
        for m in settled(s):
            if m.get("result") in ("yes", "no") and START <= m["open_time"] < END:
                windows[m["open_time"]].append({"ticker": m["ticker"], "series": s, "open_time": m["open_time"],
                                                "resolved_yes": "1" if m["result"] == "yes" else "0"})
                n += 1
        print(f"  {s}: {n} settled markets", flush=True)
    todo = [t for t in sorted(windows) if t not in done]
    print(f"{sum(len(v) for v in windows.values())} markets in {len(windows)} windows; fetching {len(todo)}", flush=True)
    started = time.time()
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as fh, ThreadPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        futures = {pool.submit(fetch_window, t, windows[t]): t for t in todo}
        for n, f in enumerate(as_completed(futures), 1):
            try:
                w.writerows(f.result())
            except Exception as e:  # a failed window is picked up by a rerun
                print("  window failed:", futures[f], e, flush=True)
            if n % 200 == 0:
                fh.flush()
                print(f"  {n}/{len(todo)} windows ({time.time() - started:.0f}s)", flush=True)
    print(f"done in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
