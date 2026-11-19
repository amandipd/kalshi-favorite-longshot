"""Every settled 15-minute crypto market's strike and settlement value, from Kalshi's public listings -> spot/strikes.npz.

A KXBTC15M-style market resolves YES when the simple average of the 60 seconds of CF Benchmarks' index before the close
is at least the same average before the open (rules_primary). floor_strike is that opening average (it equals the
previous window's expiration_value) and expiration_value the closing one.

/historical/markets lists the markets settled before Kalshi's live/historical cutoff and /markets?status=settled the rest;
both page 1000 at a time. Gentle: about 5 requests a second, none during minutes 7:50-9:20 of a quarter hour.

    python fetch_strikes.py
"""
import math
import os
import time
from datetime import datetime

import numpy as np
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M"]
QUIET = (470, 560)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spot", "strikes.npz")
_s = requests.Session()


def strike_row(m):
    """(ticker, open ts, floor_strike, expiration_value, 1 if YES won); NaN where a value is missing."""
    num = lambda x: math.nan if x in (None, "") else float(str(x).replace(",", ""))
    t = int(datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")).timestamp())
    return m["ticker"], t, num(m.get("floor_strike")), num(m.get("expiration_value")), int(m.get("result") == "yes")


def get(path, params):
    for i in range(10):
        while QUIET[0] <= time.time() % 900 <= QUIET[1]:
            time.sleep(QUIET[1] + 1 - time.time() % 900)
        time.sleep(0.2)
        try:
            r = _s.get(BASE + path, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 + i)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(3 + 3 * i)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path}")


def listing(path, series, extra=None):
    out, cursor = [], None
    while True:
        d = get(path, {"series_ticker": series, "limit": 1000, **(extra or {}), **({"cursor": cursor} if cursor else {})})
        ms = d.get("markets") or []
        out += [strike_row(m) for m in ms if m.get("result") in ("yes", "no")]
        cursor = d.get("cursor")
        if not cursor or not ms:
            return out


def main():
    rows = {}
    for s in SERIES:
        for path, extra in (("/historical/markets", None), ("/markets", {"status": "settled"})):
            for r in listing(path, s, extra):
                rows[r[0]] = r
        print(s, len(rows), flush=True)
    rs = sorted(rows.values(), key=lambda r: (r[1], r[0]))
    np.savez_compressed(OUT, ticker=np.array([r[0] for r in rs]), open_ts=np.array([r[1] for r in rs], dtype=np.int64),
                        strike=np.array([r[2] for r in rs]), settle=np.array([r[3] for r in rs]),
                        yes=np.array([r[4] for r in rs], dtype=np.int8))


if __name__ == "__main__":
    main()
