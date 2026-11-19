"""Watch live Polymarket US 5-minute windows, for two things the stored history can't show.

1. Timing: every POLL seconds, the price history of each live window (BTC, ETH, SOL, XRP) up to now. Each minute's
   point is logged with when it first appeared and every later change, so its final value can be matched to the time
   it was taken.
2. Depth: once a window, between minute 2:45 and 3:15, the public order book (cached by Polymarket's CDN for up to
   30 s; its Last-Modified time is kept), for how much is on offer at the favourite's ask.

Public GETs only, about 0.5 a second.

    python live.py <minutes>        # writes live.jsonl
"""
import json
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

G = "https://gateway.polymarket.us"
PRE = {"btc": "cpc-btc", "eth": "cpceth-eth", "sol": "cpcsol-sol", "xrp": "cpcxrp-xrp"}
POLL = 10
BOOK_AT = (165, 195)


def slug(coin, t):
    return f"{PRE[coin]}-updown-5m-{datetime.fromtimestamp(t, timezone.utc):%Y-%m-%d-%H%M}z"


def main(minutes):
    s = requests.Session()
    end = time.time() + minutes * 60
    booked = set()
    with open("live.jsonl", "a") as f:
        while time.time() < end:
            now = time.time()
            t0 = int(now // 300) * 300
            for coin in PRE:
                for start in (t0, t0 - 300):   # this window, and the one that just closed (its last points)
                    sl = slug(coin, start)
                    try:
                        r = s.get(G + "/v1/price-history", params={"symbol": sl, "timestamp.startTimestamp": start - 120,
                                                                   "timestamp.endTimestamp": int(time.time()),
                                                                   "fidelity": 1}, timeout=10)
                        pts = [[p["timestamp"] - start, p.get("longPrice"), p.get("shortPrice")]
                               for p in (r.json().get("history") or [])]
                        f.write(json.dumps({"k": "h", "slug": sl, "start": start, "w": time.time() - start,
                                            "pts": pts}) + "\n")
                    except Exception as e:
                        f.write(json.dumps({"k": "err", "slug": sl, "e": repr(e)[:120]}) + "\n")
                sl = slug(coin, t0)
                if BOOK_AT[0] <= now - t0 <= BOOK_AT[1] and sl not in booked:
                    booked.add(sl)
                    try:
                        r = s.get(f"{G}/v1/markets/{sl}/book", timeout=10)
                        lm = r.headers.get("last-modified")
                        md = (r.json() or {}).get("marketData") or {}
                        lv = lambda side: [[float(x["px"]["value"]), float(x["qty"])] for x in (md.get(side) or [])]
                        f.write(json.dumps({"k": "book", "slug": sl, "start": t0, "w": now - t0,
                                            "bt": parsedate_to_datetime(lm).timestamp() - t0 if lm else None,
                                            # Polymarket US calls the Yes asks "offers"
                                            "bids": lv("bids"), "asks": lv("offers") or lv("asks")}) + "\n")
                    except Exception as e:
                        f.write(json.dumps({"k": "err", "slug": sl, "e": repr(e)[:120]}) + "\n")
            f.flush()
            time.sleep(max(0.5, POLL - (time.time() - now)))


if __name__ == "__main__":
    main(float(sys.argv[1]))
