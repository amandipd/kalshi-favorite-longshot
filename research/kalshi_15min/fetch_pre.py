"""Every 15-minute crypto market before the minute files begin, back to the first one (Dec 10, 2025) -> minutes_pre.csv.

The minute files (fetch_minutes.py, fetch_all15.py, fetch_history.py) list markets from Kalshi's live endpoint, which holds
only markets settled after the live/historical cutoff (GET /historical/cutoff). When they were built the cutoff sat near
Jul 18, so the history looked as if it began there. It doesn't. GET /historical/markets lists every settled market back to
each series' first: BTC and ETH from Dec 10, 2025, SOL from Jan 9, XRP from Feb 11, BNB from Mar 7, DOGE and HYPE from
Mar 18, NEAR and ZEC from Jun 30 (112,384 markets opening before Jul 20, measured Oct 9). Metals and energy began on Jul 31,
inside the minute files already.

This takes each listed market's open time and result from that listing, and its one-minute candles from
GET /historical/markets/{ticker}/candlesticks. Rows have the minute files' columns: the last trade (p), YES bid (b) and YES
ask (a) at the end of each minute 1-15, a minute with no candle carrying the one before it forward.

Gentle and resumable. About 5 requests a second (the historical candle endpoint starts refusing above about 6), slower
after a 429; nothing during minutes 7:50-9:20 of every quarter hour, when the live bot orders; markets already in a minute
file, or already found without candles (minutes_pre_missing.txt), are skipped. Newest windows first, so a stopped run still
holds an unbroken stretch back from Jul 19.

    python fetch_pre.py                                   (all of it: about 7 hours)
    python fetch_pre.py --series KXBTC15M --limit 20 --out test.csv
"""
import argparse
import csv
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M"]
END = "2026-07-20T00:00:00Z"                                # markets opening before this; the minute files hold the rest
FILES = ("minutes_30d.csv", "minutes_new.csv", "minutes_ext.csv")
OUT, MISSING = "minutes_pre.csv", "minutes_pre_missing.txt"
MINUTES = range(1, 16)
FIELDS = (["series", "ticker", "open_time", "resolved_yes"]
          + [f"p{k}" for k in MINUTES] + [f"b{k}" for k in MINUTES] + [f"a{k}" for k in MINUTES])
RATE, WORKERS = 5.0, 4
QUIET = (470, 560)                                          # seconds into each quarter hour: the live bot's entry

_lock, _next, _slow, _local = threading.Lock(), [0.0], [1.0], threading.local()


def pace():
    """At most RATE requests a second across every worker (fewer after a 429), and none while the live bot orders."""
    while QUIET[0] <= time.time() % 900 <= QUIET[1]:
        time.sleep(QUIET[1] + 1 - time.time() % 900)
    with _lock:
        wait = _next[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        _next[0] = time.time() + _slow[0] / RATE


def get(path, params=None):
    """The JSON, or None for a 404. Retries rate limits, server errors and network errors, slowing down on a 429."""
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    for i in range(10):
        pace()
        try:
            r = _local.s.get(BASE + path, params=params, timeout=20)
        except requests.RequestException:
            time.sleep(2 + i)
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 429:
            with _lock:
                _slow[0] = min(_slow[0] * 1.5, 8.0)
            time.sleep(3 + 3 * i)
            continue
        if r.status_code >= 500:
            time.sleep(2 + 2 * i)
            continue
        r.raise_for_status()
        with _lock:
            _slow[0] = max(1.0, _slow[0] * 0.98)
        return r.json()
    raise RuntimeError(f"gave up on {path}")


def listing(series):
    """{ticker: market} for every settled market of the series that /historical/markets lists."""
    out, cursor = {}, None
    while True:
        d = get("/historical/markets", {"series_ticker": series, "limit": 1000, **({"cursor": cursor} if cursor else {})})
        for m in (d or {}).get("markets", []):
            out[m["ticker"]] = m
        cursor = (d or {}).get("cursor")
        if not cursor or not (d or {}).get("markets"):
            return out


def candle_close(block):
    """A candle field's value at the end of its minute: historical candles call it `close`, live ones `close_dollars`;
    a minute with no trade has only the last value before it (`previous`)."""
    block = block or {}
    for key in ("close", "close_dollars"):
        if key in block:
            return None if block[key] is None else float(block[key])
    for key in ("previous", "previous_dollars"):
        if block.get(key) is not None:
            return float(block[key])
    return None


def minute_row(series, market, candles):
    """The market's row in the minute files' columns, or None without a single candle."""
    open_ts = int(datetime.fromisoformat(market["open_time"].replace("Z", "+00:00")).timestamp())
    by_minute = {(c["end_period_ts"] - open_ts) // 60: c for c in candles}
    if not by_minute:
        return None
    row = {"series": series, "ticker": market["ticker"], "open_time": market["open_time"],
           "resolved_yes": "1" if market["result"] == "yes" else "0"}
    last = {"p": None, "b": None, "a": None}
    for k in MINUTES:
        c = by_minute.get(k)
        if c:
            for f, key in (("p", "price"), ("b", "yes_bid"), ("a", "yes_ask")):
                v = candle_close(c.get(key))
                if v is not None:
                    last[f] = v
        for f in "pba":
            row[f"{f}{k}"] = "" if last[f] is None else last[f]
    return row


def repair_tail(path):
    """Drop a half-written last line, which a run stopped mid-write can leave behind."""
    if os.path.exists(path) and os.path.getsize(path):
        with open(path, "rb") as fh:
            data = fh.read()
        if not data.endswith(b"\n"):
            with open(path, "wb") as fh:
                fh.write(data[: data.rfind(b"\n") + 1])


def saved(paths):
    have = set()
    for p in paths:
        if os.path.exists(p):
            with open(p) as fh:
                have |= {r["ticker"] for r in csv.DictReader(fh)}
    return have


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--series", nargs="*", default=SERIES)
    ap.add_argument("--limit", type=int, help="fetch at most this many markets (a test)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--missing", default=MISSING)
    a = ap.parse_args(argv)

    repair_tail(a.out)
    repair_tail(a.missing)
    have = saved(FILES + (a.out,))
    if os.path.exists(a.missing):
        with open(a.missing) as fh:
            have |= {line.split()[0] for line in fh if line.strip()}
    tasks, unsettled = [], 0
    for s in a.series:
        listed = [m for m in listing(s).values() if m["open_time"] < END]
        todo = [m for m in listed if m["ticker"] not in have and m.get("result") in ("yes", "no")]
        unsettled += sum(m.get("result") not in ("yes", "no") for m in listed)
        tasks += [(m["open_time"], s, m) for m in todo]
        first = min((m["open_time"] for m in listed), default="none")
        print(f"{s}: {len(listed)} markets from {first[:10]}, {len(todo)} to fetch", flush=True)
    tasks.sort(key=lambda x: x[0], reverse=True)
    if a.limit:
        tasks = tasks[:a.limit]
    print(f"{len(tasks)} markets to fetch ({unsettled} listed without a yes/no result, left out)", flush=True)

    wlock, counts, started = threading.Lock(), {"rows": 0, "missing": 0}, time.time()
    new_file = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as out, open(a.missing, "a") as miss:
        w = csv.DictWriter(out, fieldnames=FIELDS)
        if new_file:
            w.writeheader()

        def work(task):
            when, s, m = task
            o = int(datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")).timestamp())
            d = get(f"/historical/markets/{m['ticker']}/candlesticks", {"start_ts": o, "end_ts": o + 900, "period_interval": 1})
            row = minute_row(s, m, (d or {}).get("candlesticks") or [])
            with wlock:
                if row:
                    w.writerow(row)
                    counts["rows"] += 1
                else:
                    miss.write(f"{m['ticker']} no-candles\n")
                    counts["missing"] += 1
                done = counts["rows"] + counts["missing"]
                if done % 200 == 0:
                    out.flush()
                    miss.flush()
                if done % 2000 == 0:
                    rate = done / (time.time() - started)
                    print(f"  {done}/{len(tasks)} ({counts['missing']} without candles) · back to {when[:10]} · "
                          f"~{(len(tasks) - done) / rate / 3600:.1f} h left", flush=True)

        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(work, tasks))
    print(f"done: {counts['rows']} markets written to {a.out}, {counts['missing']} without candles", flush=True)


if __name__ == "__main__":
    main()
