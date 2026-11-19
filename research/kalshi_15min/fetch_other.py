"""Kalshi's other markets, for testing the favourites rule outside the 15-minute ones.

Step 1 (python fetch_other.py list): every hourly, daily and weekly series in Kalshi's catalog (series_catalog.json,
from GET /series), with each series' markets that closed from Jul 18 (the first 15-minute market) to the last full
day: ticker, event, open and close times, result and volume -> other_markets.json.

Step 2 (python fetch_other.py candles): for every one of those markets that traded, its YES bid and ask counting back
from the close -> other_hours.csv, one row per market: b0..b60 and a0..a60, where k is minutes before the close for an
hourly series and hours before it for a daily or weekly one (the "unit" column says which). Resumable.

Markets settled after Kalshi's live/historical cutoff (GET /historical/cutoff) come 20 to a request from the live
endpoint; earlier ones only from the historical store, one market a request. Gentle: at most RATE requests a second
and none while the live bot orders, as fetch_pre.py.
"""
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

import backtest_large
from backtest_large import BASE

RATE = 5.0           # requests a second: the historical candle endpoint starts refusing above about 6 (fetch_pre.py)
QUIET = (470, 560)   # seconds into each quarter hour while the live bot orders: no requests then
_lock, _next = threading.Lock(), [0.0]

FREQS = ("hourly", "daily", "weekly")
SINCE = "2026-07-18T00:00:00Z"
UNTIL = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
MARKETS = "other_markets.json"
HOURS_CSV = "other_hours.csv"
BACK = {"hourly": (60, 1), "daily": (24, 60), "weekly": (24, 60)}   # (steps kept before the close, minutes a step)
BATCH = 20         # markets per candlesticks request
DAY = 86400
PARTS = "other_markets.parts.jsonl"   # series re-listed day by day, one line each, so a stopped run resumes


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def get(url, params=None):
    """backtest_large's get, at most RATE a second and never while the live bot orders; None for a 404 (a market
    the store asked doesn't hold)."""
    while QUIET[0] <= time.time() % 900 <= QUIET[1]:
        time.sleep(QUIET[1] + 1 - time.time() % 900)
    with _lock:
        wait = _next[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        _next[0] = time.time() + 1 / RATE
    try:
        return backtest_large.get(url, params=params)
    except requests.HTTPError as e:
        if getattr(e.response, "status_code", None) == 404:
            return None
        raise


def cutoff():
    """Kalshi's live/historical cutoff: markets settled before it are only in the historical store. 0 if unreadable,
    which sends every market to the live endpoint."""
    d = get(f"{BASE}/historical/cutoff")
    return ts(d["market_settled_ts"]) if d and d.get("market_settled_ts") else 0


def catalog():
    if not os.path.exists("series_catalog.json"):
        json.dump(get(f"{BASE}/series", params={}).get("series", []), open("series_catalog.json", "w"))
    return json.load(open("series_catalog.json"))


def settled(series, step=None):
    """Every market in the series that closed in the period. step (seconds): list it that much at a time instead,
    for a series whose one listing stopped early (Kalshi stops paging after tens of thousands of markets)."""
    out = []
    span = step or ts(UNTIL) - ts(SINCE)
    for a in range(ts(SINCE), ts(UNTIL), span):
        cursor = None
        while True:
            params = {"series_ticker": series, "status": "settled", "limit": 1000, "min_close_ts": a, "max_close_ts": min(a + span, ts(UNTIL))}
            if cursor:
                params["cursor"] = cursor
            d = get(f"{BASE}/markets", params=params)
            if not d:
                break
            out += [{"ticker": m["ticker"], "event": m.get("event_ticker"), "open": m.get("open_time"), "close": m.get("close_time"),
                     "result": m.get("result"), "volume": m.get("volume_fp") or m.get("volume") or 0} for m in d.get("markets", [])]
            cursor = d.get("cursor")
            if not cursor:
                break
    return list({m["ticker"]: m for m in out}.values())


def entry(s, ms):
    return {"series": s["ticker"], "title": s.get("title"), "category": s.get("category"), "frequency": s.get("frequency"),
            "fee_type": s.get("fee_type"), "fee_multiplier": s.get("fee_multiplier"), "markets": ms}


def list_markets():
    """One listing per series; then any series whose listing ended on a round thousand (it stopped paging rather than
    running out) is listed again a day at a time."""
    if not os.path.exists(MARKETS):
        cat = [s for s in catalog() if s.get("frequency") in FREQS]
        print(f"{len(cat)} hourly, daily and weekly series", flush=True)
        with ThreadPoolExecutor(12) as ex:
            found = list(ex.map(lambda s: (s, settled(s["ticker"])), cat))
        json.dump([entry(s, ms) for s, ms in found if ms], open(MARKETS, "w"))
    out = json.load(open(MARKETS))
    done = {}
    if os.path.exists(PARTS):
        with open(PARTS) as fh:
            done = {d["series"]: d for d in map(json.loads, fh)}
    cut = [s for s in out if len(s["markets"]) % 1000 == 0 and s["series"] not in done]
    print(f"{len(out)} series; {len(cut)} stopped early, listing them a day at a time ({len(done)} already done)", flush=True)
    cat = {s["ticker"]: s for s in catalog()}
    with open(PARTS, "a") as fh:
        for s in cut:
            d = entry(cat[s["series"]], settled(s["series"], DAY))
            fh.write(json.dumps(d) + "\n")
            fh.flush()
            done[s["series"]] = d
            print(f"  {s['series']}: {len(s['markets']):,} -> {len(d['markets']):,}", flush=True)
    out = [done.get(s["series"], s) for s in out]
    json.dump(out, open(MARKETS, "w"))
    print(f"{len(out)} series with markets closed {SINCE[:10]} to {UNTIL[:10]}, {sum(len(s['markets']) for s in out):,} markets")


def close(v):
    """A candle field's value at the end of its step: live candles call it close_dollars, historical ones close."""
    if v is None or not isinstance(v, dict):
        return None if v is None else float(v)
    for key in ("close_dollars", "close"):
        if v.get(key) not in (None, ""):
            return float(v[key])
    return None


def fetch(batch):
    """YES bid and ask over the last steps of each market in the batch (one frequency, all closing within the same hour)."""
    back, step = BACK[batch[0]["frequency"]]
    end = max(ts(m["close"]) for m in batch)
    start = min(ts(m["close"]) for m in batch) - (back + 1) * step * 60
    d = get(f"{BASE}/markets/candlesticks", params={"market_tickers": ",".join(m["ticker"] for m in batch),
                                                    "start_ts": start, "end_ts": end, "period_interval": step})
    if not d:
        return []
    return rows_for(batch, {x["market_ticker"]: x["candlesticks"] for x in d.get("markets", [])})


def fetch_old(m):
    """One market settled before the cutoff, from the historical store. One that closed before the cutoff but settled
    after it isn't there yet, so the live endpoint is asked next."""
    back, step = BACK[m["frequency"]]
    end = ts(m["close"])
    d = get(f"{BASE}/historical/markets/{m['ticker']}/candlesticks",
            params={"start_ts": end - (back + 1) * step * 60, "end_ts": end, "period_interval": step})
    return rows_for([m], {m["ticker"]: (d or {}).get("candlesticks") or []}) or fetch([m])


def rows_for(batch, by):
    """other_hours.csv rows for the batch's markets from their candles ({ticker: candles}); none for a market without any."""
    back, step = BACK[batch[0]["frequency"]]
    rows = []
    for m in batch:
        c_end = ts(m["close"])
        hours = {}
        for c in by.get(m["ticker"], []):
            k = (c_end - c["end_period_ts"]) // (step * 60)   # 0: the step ending at the close
            hours[k] = (close(c.get("yes_bid")), close(c.get("yes_ask")))
        if not hours:
            continue
        row = {k: m[k] for k in ("series", "ticker", "event", "close", "result", "volume")}
        row["unit"] = "min" if step == 1 else "hour"
        last = (None, None)
        for k in range(back, -1, -1):   # carry the last quote forward through steps without one
            b, a = hours.get(k, (None, None))
            last = (b if b is not None else last[0], a if a is not None else last[1])
            row[f"b{k}"], row[f"a{k}"] = ("" if last[0] is None else last[0]), ("" if last[1] is None else last[1])
        rows.append(row)
    return rows


def candles():
    series = json.load(open(MARKETS))
    todo = [dict(m, series=s["series"], frequency=s["frequency"]) for s in series for m in s["markets"]
            if m["result"] in ("yes", "no") and float(m["volume"] or 0) > 0]
    done = set()
    if os.path.exists(HOURS_CSV):
        with open(HOURS_CSV) as fh:
            done = {r["ticker"] for r in csv.DictReader(fh)}
    todo = [m for m in todo if m["ticker"] not in done]
    todo.sort(key=lambda m: (m["frequency"], m["close"]))
    cut = cutoff()
    old = [m for m in todo if ts(m["close"]) < cut]
    batches, cur = [], []
    for m in (m for m in todo if ts(m["close"]) >= cut):   # batch markets of one frequency that close within the same
        if cur and (len(cur) == BATCH or m["frequency"] != cur[0]["frequency"]   # hour, so one time range fits them all
                    or ts(m["close"]) - ts(cur[0]["close"]) >= 3600):
            batches.append(cur)
            cur = []
        cur.append(m)
    if cur:
        batches.append(cur)
    print(f"{len(todo):,} markets to fetch: {len(batches):,} batched requests and {len(old):,} historical ones, a market each "
          f"({len(done):,} already saved)", flush=True)
    most = max(b for b, _ in BACK.values())
    fields = ["series", "ticker", "event", "close", "result", "volume", "unit"] + [f"{x}{k}" for k in range(most + 1) for x in "ba"]
    new = not os.path.exists(HOURS_CSV)
    with open(HOURS_CSV, "a", newline="") as fh, ThreadPoolExecutor(12) as ex:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for work, items, label in ((fetch, batches, "batched"), (fetch_old, old, "historical")):
            for i, rows in enumerate(ex.map(work, items)):
                w.writerows(rows)
                if i % 500 == 0:
                    fh.flush()
                    print(f"  {label} {i:,}/{len(items):,}", flush=True)


if __name__ == "__main__":
    {"list": list_markets, "candles": candles}[sys.argv[1] if len(sys.argv) > 1 else "list"]()
