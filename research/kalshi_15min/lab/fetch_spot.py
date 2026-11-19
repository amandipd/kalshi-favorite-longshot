"""One-minute spot candles for the 15-minute crypto markets' coins, from Coinbase Exchange's public API -> spot/{COIN}.npz.

Kalshi settles these markets on CF Benchmarks' real-time indices (BRTI for BTC, and the like), which blend several
exchanges; Coinbase is one of them, so its candles are a close proxy, not the index itself (fair_value.py measures the
gap against each market's strike).

Each file is a dense grid of minutes from the day before the coin's first Kalshi market to END: t0 (the first minute's
start, unix seconds) and per minute the close, the (open+high+low+close)/4 average, the volume and whether Coinbase had a
candle. A minute with no trade carries the last close forward (and averages at it).

Gentle: at most RATE requests a second across the workers, and none during minutes 7:50-9:20 of each quarter hour, when
the live bot orders. A coin whose file exists is skipped, so a stopped run resumes by coin.

    python fetch_spot.py                 (every coin, BTC and ETH first)
    python fetch_spot.py BTC ETH
"""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import requests

URL = "https://api.exchange.coinbase.com/products/{}-USD/candles"
# coin -> the day its first 15-minute Kalshi market opened (fetch_pre.py's notes)
COINS = {"BTC": "2025-12-10", "ETH": "2025-12-10", "SOL": "2026-01-09", "XRP": "2026-02-11", "DOGE": "2026-03-18",
         "BNB": "2026-03-07", "HYPE": "2026-03-18", "NEAR": "2026-06-30", "ZEC": "2026-06-30"}
END = "2026-10-09T00:00:00Z"
PER = 300                       # candles per request, Coinbase's most
RATE, WORKERS = 6.0, 4
QUIET = (470, 560)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spot")

_lock, _next, _local = threading.Lock(), [0.0], threading.local()


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def chunks(t0, t1):
    """[(first minute start, last minute start)] of at most PER minutes each, covering [t0, t1) in order."""
    out, a = [], t0
    while a < t1:
        b = min(a + 60 * (PER - 1), t1 - 60)
        out.append((a, b))
        a = b + 60
    return out


def to_grid(rows, t0, n):
    """Coinbase rows ([time, low, high, open, close, volume], any order) -> dense per-minute arrays of length n from t0."""
    close = np.full(n, np.nan)
    avg = np.full(n, np.nan)
    vol = np.zeros(n, dtype=np.float32)
    have = np.zeros(n, dtype=bool)
    for t, lo, hi, op, cl, v in rows:
        i = (int(t) - t0) // 60
        if 0 <= i < n and (int(t) - t0) % 60 == 0:
            close[i], avg[i], vol[i], have[i] = cl, (lo + hi + op + cl) / 4, v, True
    last = np.nan
    for i in range(n):            # carry the last close over quiet minutes
        if have[i]:
            last = close[i]
        else:
            close[i] = avg[i] = last
    return {"close": close, "avg": avg, "vol": vol, "have": have}


def pace():
    while QUIET[0] <= time.time() % 900 <= QUIET[1]:
        time.sleep(QUIET[1] + 1 - time.time() % 900)
    with _lock:
        wait = _next[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        _next[0] = time.time() + 1 / RATE


def get(coin, a, b):
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i in range(12):
        pace()
        try:
            r = _local.s.get(URL.format(coin), params={"granularity": 60, "start": iso(a), "end": iso(b)}, timeout=20)
        except requests.RequestException:
            time.sleep(1 + i)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 + 2 * i)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {coin} {a}")


def fetch(coin):
    path = os.path.join(OUT, f"{coin}.npz")
    if os.path.exists(path):
        return
    t0, t1 = ts(COINS[coin] + "T00:00:00Z") - 86400, ts(END)
    cs = chunks(t0, t1)
    rows = []
    with ThreadPoolExecutor(WORKERS) as ex:
        for i, got in enumerate(ex.map(lambda c: get(coin, *c), cs)):
            rows.append(np.asarray(got, dtype=float).reshape(-1, 6))
            if i % 200 == 0:
                print(coin, f"{i}/{len(cs)}", flush=True)
    g = to_grid(np.concatenate(rows), t0, (t1 - t0) // 60)
    np.savez_compressed(path + ".tmp.npz", t0=t0, **g)
    os.replace(path + ".tmp.npz", path)
    print(coin, "done", int(g["have"].sum()), "of", len(g["have"]), "minutes had a candle", flush=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for c in sys.argv[1:] or list(COINS):
        fetch(c)
