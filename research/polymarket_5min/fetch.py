"""Every Polymarket US 5-minute up/down market (BTC, ETH, SOL, XRP) since they launched, with its result and its
book-derived price history.

Public GETs only, no key: gateway.polymarket.us /v1/markets?slug= (result, open and close values, fee coefficient)
and /v1/price-history (one point a minute: longPrice = the Yes ask, shortPrice = 1 - the Yes bid, so the No ask).
About 8 requests a second in all, under the documented 20 a second public limit. Resumes: a slug already in
markets.jsonl is not asked for again. A window with no market (maintenance, before launch) is written as missing.

    python fetch.py            # from FIRST to 10 minutes ago
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

G = "https://gateway.polymarket.us"
PRE = {"btc": "cpc-btc", "eth": "cpceth-eth", "sol": "cpcsol-sol", "xrp": "cpcxrp-xrp"}
FIRST = int(datetime(2026, 10, 22, 12, tzinfo=timezone.utc).timestamp())   # none exist before Oct 22 12:00 UTC
OUT = "markets.jsonl"
RATE = 8.0          # requests a second, all threads together
BEFORE, AFTER = 150, 360   # history asked for from start - BEFORE to start + AFTER

_lock = threading.Lock()
_next = [0.0]
_s = threading.local()


def slug(coin, t):
    return f"{PRE[coin]}-updown-5m-{datetime.fromtimestamp(t, timezone.utc):%Y-%m-%d-%H%M}z"


def get(path, params):
    with _lock:
        wait = _next[0] - time.time()
        _next[0] = max(time.time(), _next[0]) + 1 / RATE
    if wait > 0:
        time.sleep(wait)
    if not hasattr(_s, "s"):
        _s.s = requests.Session()
    for attempt in range(6):
        try:
            r = _s.s.get(G + path, params=params, timeout=20)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r.json()
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"gave up on {path} {params}")


def val(x):
    return None if not x else float(x["value"])


def one(coin, t):
    s = slug(coin, t)
    d = get("/v1/markets", {"slug": s})
    ms = [m for m in d.get("markets") or [] if m.get("slug") == s]
    if not ms:
        return {"slug": s, "coin": coin, "start": t, "missing": True}
    m = ms[0]
    terms = m.get("assetPriceTerms") or {}
    prices = json.loads(m.get("outcomePrices") or "[]")
    won = None
    if m.get("status") == "MARKET_STATUS_RESOLVED" and [float(x) for x in prices] in ([1.0, 0.0], [0.0, 1.0]):
        won = float(prices[0]) == 1.0
    h = get("/v1/price-history", {"symbol": s, "timestamp.startTimestamp": t - BEFORE,
                                  "timestamp.endTimestamp": t + AFTER, "fidelity": 1})
    pts = [[p["timestamp"] - t, p.get("longPrice"), p.get("shortPrice")] for p in h.get("history") or []]
    return {"slug": s, "coin": coin, "start": t, "status": m.get("status"), "yes": won,
            "open": val(terms.get("priceToBeat")), "close": val(terms.get("settlementPrice")),
            "index": terms.get("indexSymbol"), "fee": m.get("feeCoefficient"),
            "ws": terms.get("windowStart"), "we": terms.get("windowEnd"), "h": pts}


def main():
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            done = {json.loads(line)["slug"] for line in f if line.strip()}
    last = int((time.time() - 600) // 300) * 300
    todo = [(c, t) for t in range(FIRST, last, 300) for c in PRE if slug(c, t) not in done]
    print(f"{len(done):,} done, {len(todo):,} to fetch", flush=True)
    n = 0
    with open(OUT, "a") as f, ThreadPoolExecutor(6) as pool:
        for rec in pool.map(lambda ct: one(*ct), todo):
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n += 1
            if n % 500 == 0:
                f.flush()
                print(f"{n:,}/{len(todo):,} {datetime.fromtimestamp(rec['start'], timezone.utc):%m-%d %H:%M}",
                      flush=True)
    print("all done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
