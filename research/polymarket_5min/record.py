"""Scratch recorder: Polymarket US 5-minute books (public, cached) for timing calibration and depth.
Usage: python record.py <hours>. Writes live_books.jsonl. Public GETs only, ~0.8 a second."""
import json, sys, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import requests
G = "https://gateway.polymarket.us"
PRE = {"btc": "cpc-btc", "eth": "cpceth-eth", "sol": "cpcsol-sol", "xrp": "cpcxrp-xrp"}
S = requests.Session()
end = time.time() + float(sys.argv[1]) * 3600
seen = set()
with open("live_books.jsonl", "a") as f:
    while time.time() < end:
        now = time.time()
        t0 = int(now // 300) * 300
        for coin, pre in PRE.items():
            slug = f"{pre}-updown-5m-{datetime.fromtimestamp(t0, timezone.utc):%Y-%m-%d-%H%M}z"
            try:
                r = S.get(f"{G}/v1/markets/{slug}/book", timeout=10)
                lm = r.headers.get("last-modified")
                bt = parsedate_to_datetime(lm).timestamp() if lm else now - float(r.headers.get("Age", 0))
                if (slug, bt) in seen:
                    continue
                seen.add((slug, bt))
                md = (r.json() or {}).get("marketData") or {}
                lv = lambda side: [[float(x["px"]["value"]), float(x["qty"])] for x in (md.get(side) or [])[:15]]
                f.write(json.dumps({"slug": slug, "coin": coin, "start": t0, "req": now, "bt": bt,
                                    "bids": lv("bids"), "asks": lv("asks")}) + "\n")
                f.flush()
            except Exception as e:
                f.write(json.dumps({"slug": slug, "err": repr(e)[:200], "req": now}) + "\n")
        time.sleep(max(0.5, 5 - (time.time() - now)))
