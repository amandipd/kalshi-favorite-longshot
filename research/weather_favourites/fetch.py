"""The data for PREREG.md: settled KXRAIN and daily-high markets, their hourly quotes before the close, and the NWS
daily climate reports they settle on.

    python fetch.py list      every settled market in the two families -> data/listed.jsonl
    python fetch.py candles   hourly YES bid/ask over the last 25 hours of each -> data/markets.jsonl (resumable)
    python fetch.py cli       NWS daily climate reports from the Iowa Environmental Mesonet -> data/cli/<station>.json

Gentle: at most RATE Kalshi requests a second from one thread. One machine shares one Kalshi rate limit, so check no
other Kalshi fetch is running first. A request that keeps failing is written to data/failed.txt, never treated as
"no data"; a re-run retries it.

Markets settled before Kalshi's live/historical cutoff come from the historical store, one a request; later ones
from the live endpoint, 20 a request.
"""
import json
import os
import re
import sys
import time
from datetime import datetime

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BASE = "https://api.elections.kalshi.com/trade-api/v2"
IEM = "https://mesonet.agron.iastate.edu/json/cli.py"
RATE = 3.0
BACK = 25                 # hours of candles kept before the close
BATCH = 20

SERIES = ("KXRAIN", "KXHIGHAUS", "KXHIGHCHI", "KXHIGHDEN", "KXHIGHLAX", "KXHIGHMIA", "KXHIGHNY", "KXHIGHPHIL",
          "KXHIGHTATL", "KXHIGHTBOS", "KXHIGHTDAL", "KXHIGHTDC", "KXHIGHTEWR", "KXHIGHTHOU", "KXHIGHTLV", "KXHIGHTMIN",
          "KXHIGHTNOLA", "KXHIGHTOKC", "KXHIGHTPHX", "KXHIGHTSAN", "KXHIGHTSATX", "KXHIGHTSDF", "KXHIGHTSEA",
          "KXHIGHTSFO", "KXHIGHTTTN")

sys.path.insert(0, HERE)
import score  # noqa: E402

_last = [0.0]
_session = requests.Session()
_session.headers["User-Agent"] = "kalshi-weather-favourites-research"


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def get(url, params=None, tries=8):
    """JSON from url at most RATE a second; None for a 404; raises after tries failures."""
    for i in range(tries):
        wait = _last[0] + 1 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = _session.get(url, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 * (i + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(3 * (i + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up after {tries} tries: {url} {params}")


def wanted(m):
    """A settled market of either family whose climate date is in a part of PREREG.md."""
    return (m["series"] in SERIES and m.get("result") in ("yes", "no")
            and score.part(score.climate_date(m["event"])) is not None)


def batches(ms):
    """Markets in groups of at most BATCH that all close within the same hour (one time range fits them all)."""
    out, cur = [], []
    for m in sorted(ms, key=lambda m: m["close"]):
        if cur and (len(cur) == BATCH or m["close"] - cur[0]["close"] >= 3600):
            out.append(cur)
            cur = []
        cur.append(m)
    return out + ([cur] if cur else [])


def value(v):
    if not isinstance(v, dict):
        return None
    for key in ("close_dollars", "close"):
        if v.get(key) not in (None, ""):
            return float(v[key])
    return None


def compact(c):
    """[end_ts, yes bid, yes ask] from one candle, historical (close) or live (close_dollars)."""
    return [c["end_period_ts"], value(c.get("yes_bid")), value(c.get("yes_ask"))]


def station(rules):
    m = re.search(r"\bCLI([A-Z]{3})\b", rules or "")
    return m.group(1) if m else None


def listing(series, path):
    """Every settled market of a series from one endpoint, following the cursor."""
    out, cursor = [], None
    while True:
        params = {"series_ticker": series, "limit": 1000}
        if path == "/markets":
            params["status"] = "settled"
        if cursor:
            params["cursor"] = cursor
        d = get(BASE + path, params) or {}
        for m in d.get("markets", []):
            out.append({"series": series, "ticker": m["ticker"], "event": m["event_ticker"], "close": ts(m["close_time"]),
                        "result": m.get("result"), "value": m.get("expiration_value"), "volume": m.get("volume_fp"),
                        "station": station(m.get("rules_primary"))})
        cursor = d.get("cursor")
        if not cursor or not d.get("markets"):
            return out


def list_markets():
    os.makedirs(DATA, exist_ok=True)
    seen = {}
    for s in SERIES:
        n = 0
        for path in ("/historical/markets", "/markets"):
            for m in listing(s, path):
                if m["ticker"] not in seen and wanted(m):
                    seen[m["ticker"]] = m
                    n += 1
        print(f"  {s}: {n:,} markets", flush=True)
    with open(os.path.join(DATA, "listed.jsonl"), "w") as fh:
        for m in seen.values():
            fh.write(json.dumps(m) + "\n")
    print(f"{len(seen):,} markets listed")


def order(m):
    """Test data first (recent, then older), the seen half last."""
    return {"recent": 0, "older": 1, "seen": 2}[score.part(score.climate_date(m["event"]))], -m["close"]


def candles():
    listed = [json.loads(x) for x in open(os.path.join(DATA, "listed.jsonl"))]
    out_path = os.path.join(DATA, "markets.jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(x)["ticker"] for x in open(out_path)}
    todo = sorted((m for m in listed if m["ticker"] not in done), key=order)
    cut = ts((get(BASE + "/historical/cutoff") or {}).get("market_settled_ts") or "1970-01-01T00:00:00Z")
    old = [m for m in todo if m["close"] < cut - 86400]      # settled before the cutoff: historical store
    new = [m for m in todo if m["close"] >= cut - 86400]
    print(f"{len(todo):,} markets to fetch ({len(done):,} saved): {len(new):,} live in batches, {len(old):,} historical",
          flush=True)
    failed = []
    with open(out_path, "a") as fh:
        def save(m, cs):
            fh.write(json.dumps(dict(m, candles=[compact(c) for c in cs])) + "\n")

        for i, b in enumerate(batches(new)):
            p = {"market_tickers": ",".join(m["ticker"] for m in b), "start_ts": min(m["close"] for m in b) - BACK * 3600,
                 "end_ts": max(m["close"] for m in b), "period_interval": 60}
            try:
                d = get(BASE + "/markets/candlesticks", p) or {}
            except RuntimeError:
                failed += [m["ticker"] for m in b]
                continue
            by = {x["market_ticker"]: x.get("candlesticks") or [] for x in d.get("markets", [])}
            for m in b:
                if m["ticker"] in by:
                    save(m, by[m["ticker"]])
                else:
                    old.append(m)        # not served live: try the historical store
            if i % 50 == 0:
                fh.flush()
                print(f"  live batch {i:,}", flush=True)
        for i, m in enumerate(old):
            p = {"start_ts": m["close"] - BACK * 3600, "end_ts": m["close"], "period_interval": 60}
            try:
                d = get(f"{BASE}/historical/markets/{m['ticker']}/candlesticks", p)
            except RuntimeError:
                failed.append(m["ticker"])
                continue
            save(m, (d or {}).get("candlesticks") or [])
            if i % 500 == 0:
                fh.flush()
                print(f"  historical {i:,}/{len(old):,}", flush=True)
    with open(os.path.join(DATA, "failed.txt"), "w") as fh:
        fh.write("\n".join(failed))
    print(f"done; {len(failed):,} failed (data/failed.txt)", flush=True)


def cli():
    """Each station's daily climate reports for every year the listed markets touch."""
    import check
    listed = [json.loads(x) for x in open(os.path.join(DATA, "listed.jsonl"))]
    st = check.stations(listed)
    years = {}
    for m in listed:
        if st[m["ticker"]]:
            years.setdefault(st[m["ticker"]], set()).add(score.climate_date(m["event"]).year)
    os.makedirs(os.path.join(DATA, "cli"), exist_ok=True)
    for st, ys in sorted(years.items()):
        path = os.path.join(DATA, "cli", st + ".json")
        if os.path.exists(path):
            continue
        rows = []
        for y in sorted(ys):
            for i in range(6):
                time.sleep(1.0 + 3 * i)
                try:
                    r = _session.get(IEM, params={"station": "K" + st, "year": y}, timeout=60)
                    r.raise_for_status()
                    rows += r.json().get("results", [])
                    break
                except (requests.RequestException, ValueError):
                    continue
            else:
                print(f"  {st} {y}: failed", flush=True)
        json.dump(rows, open(path, "w"))
        print(f"  {st}: {len(rows):,} days", flush=True)


if __name__ == "__main__":
    {"list": list_markets, "candles": candles, "cli": cli}[sys.argv[1]]()
