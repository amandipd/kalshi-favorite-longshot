"""Forward paper test of the minute-4 rule, with no peeking (PREREG_FORWARD.md).

Every 5-minute window on Polymarket US (BTC, ETH, SOL, XRP): price-history polls at about 3:46 and 3:54 server time
and an order-book read at about 3:50, all public GETs (about 12 a window). The bet is decided from the latest poll at
or before 3:58 server time with the backtest's own rule (score.rule, minute 4, 90-99c floor), and written to
forward.jsonl with every poll. Results are not read here; forward_report.py scores them at the end.

Runs until 72 hours from the first record with at least 1,000 bets, or 7 days, whichever stop comes first under
should_stop(); then writes forward_done.json so the watchdog (keep_running.py) leaves it stopped. On a restart it
picks up the first record's time and the bet count from forward.jsonl.

    python forward.py record
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as S  # noqa: E402

G = "https://gateway.polymarket.us"
PRE = {"btc": "cpc-btc", "eth": "cpceth-eth", "sol": "cpcsol-sol", "xrp": "cpcxrp-xrp"}
OUT, LOG, DONE = "forward.jsonl", "forward.log", "forward_done.json"
POLLS, BOOK, CUTOFF = (226, 234), 230, 238      # seconds into a window, server time
M, LO = 4, 0.90
MIN_HOURS, MIN_BETS, MAX_DAYS = 72, 1000, 7
TIMEOUT = 8


def path(name):
    return os.path.join(HERE, name)


def log(msg):
    with open(path(LOG), "a") as f:
        f.write(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ} {msg}\n")


def slug(coin, t):
    return f"{PRE[coin]}-updown-5m-{datetime.fromtimestamp(t, timezone.utc):%Y-%m-%d-%H%M}z"


# ------------------------------------------------------------------ pure parts (tested)


def server_time(headers):
    """The response's Date header as unix seconds, or None."""
    h = {k.lower(): v for k, v in (headers or {}).items()}
    try:
        return parsedate_to_datetime(h["date"]).timestamp()
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def skew(samples):
    """server - local clock, from (sent, received, Date header) samples. Date floors to the second, so + 0.5."""
    if not samples:
        return 0.0
    return float(np.mean([d + 0.5 - (a + b) / 2 for a, b, d in samples]))


def schedule(start, skew=0.0):
    """[(what, local time)] for one window: polls at POLLS and the book at BOOK, in server time."""
    return sorted([("poll", start + POLLS[0] - skew), ("book", start + BOOK - skew), ("poll", start + POLLS[1] - skew)],
                  key=lambda x: x[1])


def visible(polls, cutoff=CUTOFF):
    """The latest poll whose server time ("sw", seconds into the window) is at most `cutoff`, or None."""
    ok = [p for p in polls if p.get("sw") is not None and p["sw"] <= cutoff]
    return max(ok, key=lambda p: p["sw"]) if ok else None


def decide(points):
    """{"bet", "side", "top", "why"}: the backtest's rule at minute 4 on one market's history points as seen."""
    bid, ask = S.quotes(points, offset=60)
    if np.isnan(ask[M - 1]) or np.isnan(bid[M - 1]):
        return {"bet": False, "side": None, "top": None, "why": "no minute-4 price"}
    d = {"bid": bid[None, :], "ask": ask[None, :], "yes": np.array([0]), "open_ts": np.array([0]),
         "coin": np.array(["x"])}
    m, side_yes, top = S.rule(d, M=M, lo=LO, fed=False)
    if not m[0]:
        return {"bet": False, "side": None, "top": None, "why": "rule says no"}
    return {"bet": True, "side": "yes" if side_yes[0] else "no", "top": round(float(top[0]), 4), "why": "bet"}


def should_stop(now, first, bets):
    if now - first >= MAX_DAYS * 86400:
        return True
    return now - first >= MIN_HOURS * 3600 and bets >= MIN_BETS


# ------------------------------------------------------------------ the recorder


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.samples = []

    def get(self, p, params=None):
        """(json or None, server time or None)."""
        a = time.time()
        try:
            r = self.s.get(G + p, params=params, timeout=TIMEOUT)
            b = time.time()
            st = server_time(r.headers)
            if st is not None:
                self.samples = (self.samples + [(a, b, st)])[-60:]
            try:
                return r.json(), st, dict(r.headers)
            except ValueError:
                return None, st, dict(r.headers)
        except requests.RequestException as e:
            log(f"request failed {p}: {e!r}"[:300])
            return None, None, {}


def poll(c, start):
    out = {}
    for coin in PRE:
        sl = slug(coin, start)
        data, st, _ = c.get("/v1/price-history", {"symbol": sl, "timestamp.startTimestamp": start - 120,
                                                  "timestamp.endTimestamp": int(time.time() + skew(c.samples)),
                                                  "fidelity": 1})
        pts = [[p["timestamp"] - start, p.get("longPrice"), p.get("shortPrice")]
               for p in ((data or {}).get("history") or [])]
        out[coin] = {"sw": None if st is None else round(st - start, 1), "lw": round(time.time() - start, 2),
                     "pts": pts}
    return out


def book(c, start):
    out = {}
    for coin in PRE:
        data, st, headers = c.get(f"/v1/markets/{slug(coin, start)}/book")
        md = (data or {}).get("marketData") or {}
        lv = lambda side: [[float(x["px"]["value"]), float(x["qty"])] for x in (md.get(side) or [])]
        lm = server_time({"date": headers.get("last-modified") or headers.get("Last-Modified")}) if headers else None
        out[coin] = {"sw": None if st is None else round(st - start, 1),
                     "bt": None if lm is None else round(lm - start, 1), "bids": lv("bids"), "offers": lv("offers")}
    return out


def history():
    """(first record time, bets so far) from forward.jsonl."""
    first, bets = None, 0
    if os.path.exists(path(OUT)):
        with open(path(OUT)) as f:
            for line in f:
                r = json.loads(line)
                first = r["start"] if first is None else min(first, r["start"])
                bets += bool(r["decision"]["bet"])
    return first, bets


def record():
    c = Client()
    for _ in range(3):                       # a first clock reading
        c.get("/v1/price-history", {"symbol": slug("btc", 0), "fidelity": 1})
    first, bets = history()
    log(f"start: skew {skew(c.samples):+.2f} s, first record {first}, {bets} bets so far")
    while True:
        now = time.time() + skew(c.samples)
        if first is not None and should_stop(now, first, bets):
            with open(path(DONE), "w") as f:
                json.dump({"stopped": now, "first": first, "bets": bets}, f)
            log(f"done: {bets} bets since {first}")
            return
        start = int(now // 300) * 300
        if now - start > POLLS[0] - 2:       # too late for this window's first poll: wait for the next
            start += 300
        polls = {coin: [] for coin in PRE}
        books = {}
        for what, at in schedule(start, skew(c.samples)):
            wait = at - time.time()
            if wait > 0:
                time.sleep(wait)
            if what == "poll":
                for coin, p in poll(c, start).items():
                    polls[coin].append(p)
            else:
                books = book(c, start)
        n = 0
        with open(path(OUT), "a") as f:
            for coin in PRE:
                seen = visible(polls[coin])
                dec = decide(seen["pts"]) if seen else {"bet": False, "side": None, "top": None,
                                                        "why": "no poll by 3:58"}
                bets += dec["bet"]
                n += dec["bet"]
                f.write(json.dumps({"start": start, "coin": coin, "slug": slug(coin, start), "decision": dec,
                                    "seen_sw": seen and seen["sw"], "polls": polls[coin],
                                    "book": books.get(coin)}, separators=(",", ":")) + "\n")
        first = start if first is None else first
        if start % 3600 == 0:
            log(f"{datetime.fromtimestamp(start, timezone.utc):%m-%d %H:%M}Z ok, {bets} bets, "
                f"skew {skew(c.samples):+.2f} s")


if __name__ == "__main__":
    if sys.argv[1:] == ["record"]:
        try:
            record()
        except Exception as e:  # noqa: BLE001  the watchdog restarts it; leave a trace
            log(f"crashed: {e!r}"[:500])
            raise
