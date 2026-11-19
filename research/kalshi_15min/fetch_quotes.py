"""Record quotes and liquidity at the 8-minute mark for markets whose favourite
traded at 85c+, so fills can be priced at the real ask and thin markets spotted.

Buying YES costs the YES ask; buying NO costs 1 - YES bid.
Rows are appended as they arrive, and a rerun skips tickers already saved, so
an interrupted run resumes instead of starting over.
"""
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from backtest_large import BASE, get, iso_to_ts

WORKERS = 32
OUT_CSV = "quotes_30d.csv"
FIELDS = ["series", "ticker", "open_time", "price_8min", "yes_bid", "yes_ask",
          "vol_0_8", "vol_min8", "mins_since_trade", "oi_8", "price_7", "resolved_yes"]


def val(block):
    v = (block or {}).get("close_dollars")
    return float(v) if v is not None else ""


def quote(r):
    open_ts = iso_to_ts(r["open_time"])
    end_ts = open_ts + 8 * 60
    d = get(f"{BASE}/series/{r['series']}/markets/{r['ticker']}/candlesticks",
            params={"start_ts": open_ts, "end_ts": end_ts, "period_interval": 1})
    if not d or not d.get("candlesticks"):
        return None
    cs = sorted(d["candlesticks"], key=lambda x: x["end_period_ts"])
    c = next((x for x in cs if x["end_period_ts"] == end_ts), cs[-1])
    vols = [float(x.get("volume_fp") or 0) for x in cs]
    traded = [x["end_period_ts"] for x in cs if float(x.get("volume_fp") or 0) > 0]
    return {"series": r["series"], "ticker": r["ticker"], "open_time": r["open_time"],
            "price_8min": r["price_8min"], "yes_bid": val(c.get("yes_bid")),
            "yes_ask": val(c.get("yes_ask")),
            "vol_0_8": sum(vols),
            "vol_min8": float(c.get("volume_fp") or 0),
            "mins_since_trade": (end_ts - traded[-1]) // 60 if traded else "",
            "oi_8": float(c.get("open_interest_fp") or 0),
            "price_7": val((cs[-2] if len(cs) > 1 else {}).get("price")),
            "resolved_yes": r["resolved_yes"]}


def main(limit=None):
    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV) as fh:
            done = {r["ticker"] for r in csv.DictReader(fh)}

    todo = []
    with open("snapshots_30d.csv") as fh:
        for r in csv.DictReader(fh):
            p = float(r["price_8min"])
            if max(p, 1 - p) >= 0.85 and r["ticker"] not in done:
                todo.append(r)
    if limit:
        todo = todo[:limit]

    started = time.time()
    print(f"{len(done)} already saved, fetching {len(todo)} more...", flush=True)
    new_file = not os.path.exists(OUT_CSV)
    with open(OUT_CSV, "a", newline="") as fh, \
            ThreadPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        n = 0
        for f in as_completed([pool.submit(quote, r) for r in todo]):
            n += 1
            try:
                q = f.result()
            except Exception:
                q = None
            if q:
                w.writerow(q)
            if n % 200 == 0:
                fh.flush()
            if n % 1000 == 0:
                print(f"  {n}/{len(todo)} ({time.time()-started:.0f}s)", flush=True)
    print(f"\nDone: {len(todo)} fetched in {time.time()-started:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
