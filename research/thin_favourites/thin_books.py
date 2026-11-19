"""Two weeks of order books in thin sports markets, to price the thin-favourite edge (RECORDER_PLAN.md).

Thin "No" favourites at 80-90c made +8.1c per contract on prices a No buyer paid (reports/Yes vs No favourites split
Oct 26.md). This records what those markets really offered, so the report can say what getting in costs, how much
money sits there, and whether "thin" shows early. The pass marks are fixed in RECORDER_PREREG.md.

record: every REFRESH seconds it lists the open markets of SERIES and writes a line for each new or changed one (and
"gone" for each that closed) to data/markets-<UTC day>.jsonl. Each market's order book, top DEPTH levels a side, goes
to data/books-<UTC day>.jsonl every HOT seconds while it is live (an hour before its game time to five hours after, or
trading since the last listing) or its favourite is priced inside BAND, else every COLD seconds. Behind schedule, the
most late for its interval goes first. Gentle: public GETs only, no key, at most RATE a second. The live bot trades
from the Ohio server, so its seconds need no gap here. At each UTC day change the past day's files are gzipped. A
summary goes to data/thin_books.log each listing.

    python thin_books.py record        # two weeks; record 3 for three days. Leave it running.
"""
import gzip
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime, timezone

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ("KXNBASPREAD", "KXNBATOTAL", "KXNFLSPREAD", "KXNHLSPREAD", "KXNCAAMBGAME", "KXITFMATCH", "KXITFWMATCH",
          "KXATPCHALLENGERMATCH", "KXATPMATCH", "KXWTAMATCH")
HOT, COLD = 300, 1800  # seconds between books
BAND = (0.75, 0.95)    # a favourite priced here is checked every HOT seconds
LIVE = (3600, 5 * 3600)  # live from this long before the game time to this long after
DEPTH = 10             # price levels kept a side
RATE = 3.0             # requests a second
REFRESH = 300          # seconds between listings of the open markets
BATCH = 60             # books read between looks at the clock and the listing
TRIES = 6
DAYS = 14
DATA, LOG = "data", "thin_books.log"
DAY_FILE = re.compile(r"^(\w+)-(\d{4}-\d{2}-\d{2})\.jsonl$")


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) if s else None


def day(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")


def stamp(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


# ------------------------------------------------------------------ markets


def parse(m, series):
    """One market from Kalshi's listing, prices and volume as floats, times as unix seconds."""
    num = lambda k: float(m.get(k) or 0)
    return {"ticker": m["ticker"], "series": series, "event": m.get("event_ticker"), "vol": num("volume_fp"),
            "last": num("last_price_dollars"), "yb": num("yes_bid_dollars"), "ya": num("yes_ask_dollars"),
            "occ": ts(m.get("occurrence_datetime")), "close": ts(m.get("close_time"))}


def fav(m):
    """The favourite's price: from the YES quotes' middle when both sides quote, else the last trade; None without
    either."""
    if m["yb"] > 0 and 0 < m["ya"] < 1:
        p = (m["yb"] + m["ya"]) / 2
    elif m["last"] > 0:
        p = m["last"]
    else:
        return None
    return max(p, 1 - p)


def live(m, now):
    occ = m.get("occ")
    return bool(m.get("grew")) or (occ is not None and occ - LIVE[0] <= now <= occ + LIVE[1])


def interval(m, now):
    f = fav(m)
    return HOT if live(m, now) or (f is not None and BAND[0] <= f <= BAND[1]) else COLD


def due(markets, last, now, limit=BATCH):
    """The markets whose book is due, never-checked first, then the most late for their interval first."""
    late = []
    for t, m in markets.items():
        if t not in last:
            late.append((float("inf"), t))
        elif now - last[t] >= interval(m, now):
            late.append(((now - last[t]) / interval(m, now), t))
    return [markets[t] for _, t in sorted(late, key=lambda x: -x[0])[:limit]]


def top(book, n=DEPTH):
    """Each side's n highest bids, in Kalshi's order (lowest first)."""
    return {k: list((book or {}).get(k) or [])[-n:] for k in ("yes_dollars", "no_dollars")}


def mark_growth(old, new):
    """grew: the market traded since the last listing."""
    for t, m in new.items():
        m["grew"] = t in old and m["vol"] > old[t]["vol"]


def changes(old, new, at):
    """Listing lines: each market new or changed since `old`, and "gone" for each no longer open."""
    key = lambda m: (m["vol"], m["last"], m["yb"], m["ya"])
    out = [{"k": "m", "t": t, "at": at, "v": m["vol"], "lp": m["last"], "yb": m["yb"], "ya": m["ya"], "occ": m["occ"],
            "close": m["close"], "e": m["event"], "s": m["series"]}
           for t, m in new.items() if t not in old or key(old[t]) != key(m)]
    return out + [{"k": "gone", "t": t, "at": at} for t in old if t not in new]


# ------------------------------------------------------------------ files


def write(folder, prefix, lines, t):
    if lines:
        with open(os.path.join(folder, f"{prefix}-{day(t)}.jsonl"), "a", encoding="utf-8") as fh:
            fh.writelines(json.dumps(x, separators=(",", ":")) + "\n" for x in lines)


def rotate(folder, today):
    """Gzip each day file older than `today`; the plain file goes once its copy is whole."""
    done = []
    for name in sorted(os.listdir(folder)):
        hit = DAY_FILE.match(name)
        if hit and hit.group(2) < today:
            path = os.path.join(folder, name)
            with open(path, "rb") as src, gzip.open(path + ".gz", "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.remove(path)
            done.append(name)
    return done


def log(folder, t, msg):
    line = f"{stamp(t)}  {msg}"
    print(line, flush=True)
    with open(os.path.join(folder, LOG), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ------------------------------------------------------------------ Kalshi

_lock, _next, _local = threading.Lock(), [0.0], threading.local()


def get(path, params=None):
    """GET BASE + path as JSON; None for a 404. One request at a time, each at least 1/RATE after the last; 429s,
    5xx and dropped connections are tried again after 1, 2, 4, 8 and 16 s, then it gives up with an error."""
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    why = None
    for i in range(TRIES):
        if i:
            time.sleep(2 ** (i - 1))
        try:
            with _lock:
                while (t := time.time()) < _next[0]:
                    time.sleep(_next[0] - t)
                _next[0] = t + 1 / RATE
                r = _local.s.get(BASE + path, params=params, timeout=15)
        except requests.RequestException as e:
            why = repr(e)
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 429 or r.status_code >= 500:
            why = f"HTTP {r.status_code}"
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path} {params or ''}: {why}")


def open_markets():
    """{ticker: parse()} for every open market of every SERIES."""
    out = {}
    for s in SERIES:
        cursor = None
        while True:
            params = {"series_ticker": s, "status": "open", "limit": 1000, **({"cursor": cursor} if cursor else {})}
            d = get("/markets", params) or {}
            out.update((m["ticker"], parse(m, s)) for m in d.get("markets") or [])
            cursor = d.get("cursor")
            if not cursor:
                break
    return out


# ------------------------------------------------------------------ the loop


def record(until, now=time.time, sleep=time.sleep, folder=DATA):
    """Record until `until`. Waits only with `sleep`, 5 s at a time at most."""
    os.makedirs(folder, exist_ok=True)
    start = now()
    today = day(start)
    for name in rotate(folder, today):
        log(folder, start, f"gzipped {name}")
    log(folder, start, f"recording {len(SERIES)} series to {folder} until {stamp(until)}")
    markets, last, listed = {}, {}, None
    books = fails = 0
    while now() < until:
        t = now()
        if day(t) != today:
            today = day(t)
            for name in rotate(folder, today):
                log(folder, t, f"gzipped {name}")
        if listed is None or t - listed >= REFRESH:
            if listed is not None:
                hot = sum(interval(m, t) == HOT for m in markets.values())
                worst = max(((t - last[k]) / interval(m, t) for k, m in markets.items() if k in last), default=0)
                log(folder, t, f"{books} books, {fails} failed since the last listing; {len(markets)} open, {hot} hot;"
                               f" most late {worst:.1f}x its interval")
                books = fails = 0
            listed = t
            try:
                fresh = open_markets()
            except Exception as e:   # keep the last list and try again at the next refresh
                log(folder, t, f"listing the open markets failed: {e!r}")
            else:
                mark_growth(markets, fresh)
                write(folder, "markets", changes(markets, fresh, round(t, 3)), t)
                markets = fresh
        batch = due(markets, last, now())
        for m in batch:
            at = now()
            last[m["ticker"]] = at   # one try: a failed book waits for its next interval
            try:
                b = (get(f"/markets/{m['ticker']}/orderbook", {"depth": DEPTH}) or {}).get("orderbook_fp")
            except Exception as e:
                b, why = None, repr(e)
            else:
                why = "no book"
            if b is None:
                fails += 1
                log(folder, at, f"{m['ticker']}: {why}")
                continue
            got = now()
            write(folder, "books", [{"t": m["ticker"], "s": m["series"], "e": m["event"], "at": round(got, 3),
                                     "book": top(b)}], got)
            books += 1
        if not batch:
            t = now()
            nxt = min((last[k] + interval(m, t) for k, m in markets.items() if k in last), default=until)
            sleep(max(0.0, min(5.0, nxt - t, listed + REFRESH - t, until - t)))
    log(folder, now(), f"stopped: the end of the run ({stamp(until)})")


def main():
    what = sys.argv[1:]
    if what and what[0] == "record":
        record(until=time.time() + (float(what[1]) if len(what) > 1 else DAYS) * 86400)
    else:
        sys.exit("python thin_books.py record [days]")


if __name__ == "__main__":
    main()
