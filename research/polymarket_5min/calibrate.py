"""How far behind the book is a Polymarket US price-history point?

record.py (scratch) saved live 5-minute books with their Last-Modified time. For each recorded market this asks the
price history and compares every point stamped T with the live book as it stood at T + offset, for a few offsets.
The offset whose best ask and best bid match most often is the lag. Prices only: no result is read.

    python calibrate.py <live_books.jsonl>
"""
import json
import sys
from collections import defaultdict

import requests

G = "https://gateway.polymarket.us"
OFFSETS = (-30, 0, 15, 30, 45, 60, 75, 90, 120)
FRESH = 20   # a recorded book counts for a moment only if it is at most this many seconds older


def main(path):
    books = defaultdict(list)
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if "err" in r or not r.get("asks") or not r.get("bids"):
                continue
            books[r["slug"]].append((r["bt"], r["start"], r["asks"][0][0], max(b[0] for b in r["bids"])))
    s = requests.Session()
    hit, tried = defaultdict(int), defaultdict(int)
    for slug, rows in sorted(books.items()):
        rows.sort()
        start = rows[0][1]
        h = s.get(G + "/v1/price-history", params={"symbol": slug, "timestamp.startTimestamp": start - 120,
                                                    "timestamp.endTimestamp": start + 300, "fidelity": 1},
                  timeout=20).json().get("history") or []
        for p in h:
            t, lp, sp = p["timestamp"], p.get("longPrice"), p.get("shortPrice")
            if lp is None or sp is None or not (0 < lp < 1) or not (0 < sp < 1):
                continue
            for o in OFFSETS:
                at = [r for r in rows if t + o - FRESH <= r[0] <= t + o]
                if not at:
                    continue
                _, _, ask, bid = at[-1]
                tried[o] += 1
                hit[o] += abs(ask - lp) < 1e-6 and abs((1 - bid) - sp) < 1e-6
    for o in OFFSETS:
        if tried[o]:
            print(f"offset {o:+4d}s: {hit[o]:4d} of {tried[o]:4d} points match the live book ({hit[o] / tried[o]:.0%})")


if __name__ == "__main__":
    main(sys.argv[1])
