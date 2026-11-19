"""Step 1 of the settle-average test: in a 15-minute crypto market's last minute, do favourites win more often than
their price says?

Kalshi's 15-minute bitcoin and ether markets pay on the simple average of the CF Benchmarks index over the 60 seconds
before the close, and trading stays open through that minute. Part of the answer is fixed while people still trade,
so a price that reads the live index alone overstates the risk. If that shows in the prices, favourites bought in the
last minute win more often than they cost. If they win about as often as their price, or less, the idea stops here.

Data: every settled KXBTC15M and KXETH15M market from SINCE to the start of today (UTC), with the public trade tape of
its last SPAN seconds. A trade is [unix ts, YES price, contracts, taker side]; the taker bought the side named, at the
YES price for "yes" and 1 minus it for "no". So every price used was really paid by a buyer of that side.

Two views:
    bets   at each checkpoint (CHECKS seconds before the close), the last favourite buy (paid over 50c) in the FRESH
           seconds up to it, one per market: what a bet at that moment would have paid
    buys   every favourite buy in the last LAST seconds, weighted by contracts: the money that really traded there

Profit is per contract, after Kalshi's taker fee (0.07 x price x (1 - price), unrounded; the rounding costs ~nothing).
Bets on the same 15-minute window (BTC and ETH together) count as one cluster for the t. The pass bar is fixed in
PREREG.md before any result.

    python last_minute.py fetch      # resumable, a gzip file a UTC day in tape/
    python last_minute.py report     # no requests; writes last_minute.json

The fresh test (PREREG_FRESH.md) scores the pattern step 1 found, fixed, on Dec 2025 to Aug 2026, which step 1 never
saw:

    python last_minute.py fetch-old  # resumable, into tape_old/
    python last_minute.py fresh      # no requests; writes fresh.json
"""
import gzip
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ("KXBTC15M", "KXETH15M")
SINCE = "2026-09-01T00:00:00Z"
SPAN = 100                          # tape fetched: this many seconds before the close, to the close
CHECKS = (90, 60, 45, 30, 20, 10, 5)  # seconds before the close; 90 is before the averaging minute starts
FRESH = 10                          # a checkpoint's price must be a trade at most this many seconds before it
LAST = 60                           # the buys view: the averaging minute
FEE = 0.07
BANDS = ((0.80, "50-80c"), (0.90, "80-90c"), (0.95, "90-95c"), (0.98, "95-98c"), (0.99, "98-99c"), (1.01, "99c+"))
RATE = 3.0                          # requests a second; the thin-market recorder and other fetches share the limit
TRIES = 12                          # network errors
BUSY_TRIES = 240                    # 429s and server errors, at up to 60 s apart
HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = os.path.join(HERE, "tape")
OUT = os.path.join(HERE, "last_minute.json")
# the fresh test on data step 1 never saw (PREREG_FRESH.md)
OLD = ("2025-12-01T00:00:00Z", "2026-09-01T00:00:00Z")
TAPE_OLD = os.path.join(HERE, "tape_old")
STRIKES = os.path.join(HERE, "..", "kalshi_15min", "lab", "spot", "strikes.npz")  # Oct 11 listing
OUT_FRESH = os.path.join(HERE, "fresh.json")
RULE_CHECKS = (45, 30, 20, 10)
RULE_BAND = (0.80, 0.98)
LIST_LIMIT = 200                    # /historical/markets answers a 1000-market page with a 429


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def day(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")


def num(x):
    return math.nan if x in (None, "") else float(str(x).replace(",", ""))


# ------------------------------------------------------------------ prices and profit


def fee(p):
    """Kalshi's taker fee per contract at price p, unrounded."""
    return FEE * p * (1 - p)


def bought(x):
    """(side, price) the trade's taker bought."""
    return x[3], (x[1] if x[3] == "yes" else round(1 - x[1], 4))


def profit(side, p, result):
    return (side == result) - p - fee(p)


def band(p):
    """The price band of a favourite's price, or None for 50c and under."""
    if p <= 0.5:
        return None
    for hi, label in BANDS:
        if p < hi - 1e-9:
            return label


def bet_at(trades, close, left, fresh=FRESH):
    """(side, price) of the last favourite buy in the `fresh` seconds up to `left` seconds before the close, or None."""
    hi, lo = close - left, close - left - fresh
    best = None
    for x in trades:
        if lo < x[0] <= hi:
            side, p = bought(x)
            if p > 0.5 and (best is None or x[0] >= best[0]):
                best = (x[0], side, p)
    return best and best[1:]


# ------------------------------------------------------------------ rows


def coin(series):
    return series[2:-3]


def bets(lines, checks=CHECKS):
    """A row for every market and checkpoint that has a fresh favourite price."""
    rows = []
    for m in lines:
        for left in checks:
            b = bet_at(m["tr"], m["c"], left)
            if b:
                rows.append({"check": left, "coin": coin(m["s"]), "window": m["c"], "day": day(m["c"]),
                             "side": b[0], "price": b[1], "won": int(b[0] == m["r"])})
    return rows


def buys(lines, last=LAST):
    """A row for every favourite buy in the last `last` seconds, with its size."""
    rows = []
    for m in lines:
        for x in m["tr"]:
            if m["c"] - last <= x[0] <= m["c"]:
                side, p = bought(x)
                if p > 0.5:
                    rows.append({"left": m["c"] - x[0], "coin": coin(m["s"]), "window": m["c"], "day": day(m["c"]),
                                 "side": side, "price": p, "n": x[2], "won": int(side == m["r"])})
    return rows


def stats(rows, min_n=30, weight=None):
    """Win rate, profit per contract after fee (cents), cents per $1 bet, and a t clustered on the 15-minute window."""
    if len(rows) < min_n:
        return {"n": len(rows), "too_few": True}
    w = [r[weight] if weight else 1.0 for r in rows]
    x = [profit("yes", r["price"], "yes" if r["won"] else "no") for r in rows]
    tw = sum(w)
    m = sum(a * b for a, b in zip(w, x)) / tw
    g = defaultdict(float)
    for r, a, b in zip(rows, w, x):
        g[r["window"]] += a * (b - m)
    se = math.sqrt(sum(v * v for v in g.values())) / tw
    dollars = sum(a * r["price"] for a, r in zip(w, rows))
    out = {"n": len(rows), "windows": len(g), "price": dollars / tw, "won": sum(a * r["won"] for a, r in zip(w, rows)) / tw,
           "edge_c": m * 100, "per_dollar_c": m * tw / dollars * 100, "t": m / se if se else math.nan}
    if weight:
        out.update(contracts=tw, dollars=dollars)
    return out


# ------------------------------------------------------------------ the fetch

_s = requests.Session()
_last = [0.0]


def get(path, params=None):
    """A gentle public GET: at most RATE a second. A network error is retried TRIES times. Rate limits (429) and server
    errors are waited out for up to BUSY_TRIES tries, about 4 hours, since the limit is shared with other jobs on the
    laptop and can stay busy for an hour."""
    fails = busy = 0
    while fails < TRIES and busy < BUSY_TRIES:
        wait = _last[0] + 1 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = _s.get(BASE + path, params=params, timeout=30)
        except requests.RequestException:
            fails += 1
            time.sleep(2 + 2 * fails)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            busy += 1
            time.sleep(min(60, 5 * busy))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path} {params}")


def settled(series, lo, hi, get=get):
    """The series' markets that closed between lo and hi (unix) and settled yes or no."""
    out, cursor = [], None
    while True:
        d = get("/markets", {"series_ticker": series, "status": "settled", "min_close_ts": lo, "max_close_ts": hi,
                             "limit": 1000, **({"cursor": cursor} if cursor else {})})
        ms = d.get("markets") or []
        out += [{"t": m["ticker"], "s": series, "c": int(ts(m["close_time"])), "r": m["result"],
                 "k": num(m.get("floor_strike")), "v": num(m.get("expiration_value"))}
                for m in ms if m.get("result") in ("yes", "no")]
        cursor = d.get("cursor")
        if not cursor or not ms:
            return out


def settled_old(series, lo, hi, get=get):
    """The same from /historical/markets, which ignores close-time filters and serves newest first: the range is kept
    here, and paging stops once a page reaches past lo."""
    out, cursor = [], None
    while True:
        d = get("/historical/markets", {"series_ticker": series, "limit": LIST_LIMIT,
                                        **({"cursor": cursor} if cursor else {})})
        ms = d.get("markets") or []
        rows = [{"t": m["ticker"], "s": series, "c": int(ts(m["close_time"])), "r": m["result"],
                 "k": num(m.get("floor_strike")), "v": num(m.get("expiration_value"))} for m in ms]
        out += [r for r in rows if lo <= r["c"] <= hi and r["r"] in ("yes", "no")]
        cursor = d.get("cursor")
        if not cursor or not ms or min(r["c"] for r in rows) < lo:
            return out


def markets_between(series, lo, hi, cutoff, get=get):
    """Every series' settled markets closing from lo to hi, oldest first: before Kalshi's live/historical cutoff from
    the historical listing, after it from the live one, each ticker once."""
    found = {}
    for s in series:
        if lo < cutoff:
            found.update((m["t"], m) for m in settled_old(s, lo, min(hi, cutoff), get=get))
        if hi >= cutoff:
            found.update((m["t"], m) for m in settled(s, max(lo, int(cutoff)), hi, get=get))
    return sorted(found.values(), key=lambda m: (m["c"], m["s"]))


def tape(ticker, close, get=get, old=False):
    """The market's trades in its last SPAN seconds, oldest first. A market from before the cutoff (old) asks the
    historical endpoint first; either way the other endpoint is asked when the first has nothing."""
    for path in (("/historical/trades", "/markets/trades") if old else ("/markets/trades", "/historical/trades")):
        got, cursor = [], None
        while True:
            d = get(path, {"ticker": ticker, "min_ts": close - SPAN, "max_ts": close, "limit": 1000,
                           **({"cursor": cursor} if cursor else {})})
            page = d.get("trades") or []
            got += page
            cursor = d.get("cursor")
            if not cursor or not page:
                break
        if got:
            break
    return sorted([round(ts(x["created_time"]), 3), float(x["yes_price_dollars"]), float(x["count_fp"]), x["taker_side"]]
                  for x in got)


def from_strikes(path, series, lo, hi):
    """The settled markets of `series` closing from lo to hi, from the listing fetch_strikes.py saved on Oct 11
    (research/kalshi_15min/lab/spot/strikes.npz). Used when /historical/markets keeps answering 429."""
    import numpy as np
    z = np.load(path, allow_pickle=True)
    out = [{"t": str(t), "s": str(t).split("-")[0], "c": int(o) + 900, "r": "yes" if y else "no", "k": float(k),
            "v": float(v)}
           for t, o, k, v, y in zip(z["ticker"], z["open_ts"], z["strike"], z["settle"], z["yes"])
           if str(t).split("-")[0] in series and lo <= int(o) + 900 <= hi]
    return sorted(out, key=lambda m: (m["c"], m["s"]))


def market_list(folder, build):
    """The market list saved in folder, or build() saved there first, so a restart doesn't page the listing again."""
    path = os.path.join(folder, "markets.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    out = build()
    with open(path + ".tmp", "w") as f:
        json.dump(out, f)
    os.replace(path + ".tmp", path)
    return out


def fetch(since=SINCE, until=None, folder=TAPE, listing=None):
    """Every market closing from `since` up to `until` (default: the start of today, UTC), a gzip file a UTC day.
    The market list comes from Kalshi's listings, or from listing(lo, hi) when given."""
    os.makedirs(folder, exist_ok=True)
    lo = int(ts(since))
    hi = int(ts(until or datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z"))) - 1
    cutoff = ts(get("/historical/cutoff")["market_settled_ts"])
    markets = market_list(folder, lambda: listing(lo, hi) if listing else markets_between(SERIES, lo, hi, cutoff))
    by_day = defaultdict(list)
    for m in markets:
        by_day[day(m["c"])].append(m)
    print(f"{len(markets)} markets over {len(by_day)} days", flush=True)
    for d in sorted(by_day):
        path = os.path.join(folder, f"{d}.jsonl.gz")
        if os.path.exists(path):
            continue
        t0, lines = time.time(), []
        for m in by_day[d]:
            lines.append(dict(m, tr=tape(m["t"], m["c"], old=m["c"] < cutoff)))
        with gzip.open(path + ".tmp", "wt") as f:
            for m in lines:
                f.write(json.dumps(m, separators=(",", ":")) + "\n")
        os.replace(path + ".tmp", path)
        print(f"{d}: {len(lines)} markets, {sum(len(m['tr']) for m in lines)} trades, {time.time() - t0:.0f}s", flush=True)
    print("all done", flush=True)


# ------------------------------------------------------------------ the report


def load(folder=TAPE):
    for name in sorted(os.listdir(folder)):
        if name.endswith(".jsonl.gz"):
            with gzip.open(os.path.join(folder, name), "rt") as f:
                for row in f:
                    yield json.loads(row)


def cells(rows, key):
    out = defaultdict(list)
    for r in rows:
        out[(key(r), band(r["price"]))].append(r)
    return out


def fmt(s):
    if s.get("too_few"):
        return f"n={s['n']:>5}  too few"
    extra = f" ${s['dollars']:>10,.0f}" if "dollars" in s else ""
    return (f"n={s['n']:>6} win={s['won'] * 100:6.2f}% price={s['price'] * 100:6.2f}c "
            f"edge={s['edge_c']:+6.2f}c/contract {s['per_dollar_c']:+6.2f}c/$1 t={s['t']:+6.2f}{extra}")


def checks(rows, weight=None):
    """The usual checks on one cell: older and newer half of the days, each coin, and without its best day."""
    days = sorted({r["day"] for r in rows})
    cut = days[len(days) // 2] if days else ""
    by_day = defaultdict(float)
    for r in rows:
        by_day[r["day"]] += (r[weight] if weight else 1) * profit("yes", r["price"], "yes" if r["won"] else "no")
    best = max(by_day, key=by_day.get) if by_day else None
    return {"older half": stats([r for r in rows if r["day"] < cut], weight=weight),
            "newer half": stats([r for r in rows if r["day"] >= cut], weight=weight),
            "BTC": stats([r for r in rows if r["coin"] == "BTC"], weight=weight),
            "ETH": stats([r for r in rows if r["coin"] == "ETH"], weight=weight),
            f"without best day {best}": stats([r for r in rows if r["day"] != best], weight=weight)}


def report():
    lines = list(load())
    b, u = bets(lines), buys(lines)
    days = sorted({day(m["c"]) for m in lines})
    print(f"{len(lines)} markets, {days[0]} to {days[-1]}; {len(b)} checkpoint bets, {len(u)} last-minute favourite buys")
    out = {"markets": len(lines), "days": [days[0], days[-1]], "bets": {}, "buys": {}}
    labels = [label for _, label in BANDS]
    print("\n=== bets: one per market at each checkpoint (seconds before the close) ===")
    by = cells(b, lambda r: r["check"])
    for left in CHECKS:
        print(f"\n-- {left}s left --")
        for label in labels:
            rows = by.get((left, label), [])
            s = stats(rows)
            out["bets"][f"{left}s {label}"] = {"all": s, **({"checks": checks(rows)} if not s.get("too_few") else {})}
            print(f"{label:>7} {fmt(s)}")
    print("\n=== buys: every favourite buy in the last minute, by contracts ===")
    zones = ((60, 30, "60-30s"), (30, 10, "30-10s"), (10, -1, "10-0s"))
    zone = lambda r: next(z for hi, lo, z in zones if lo < r["left"] <= hi)
    by = cells(u, zone)
    for _, _, z in zones:
        print(f"\n-- {z} left --")
        for label in labels:
            rows = by.get((z, label), [])
            s = stats(rows, weight="n")
            out["buys"][f"{z} {label}"] = {"all": s, **({"checks": checks(rows, "n")} if not s.get("too_few") else {})}
            print(f"{label:>7} {fmt(s)}")
    print("\n=== checks on the cells where the bet is far from luck either way (|t| > 2) ===")
    for view in ("bets", "buys"):
        for k, v in out[view].items():
            if not v["all"].get("too_few") and abs(v["all"]["t"]) > 2:
                print(f"\n{view} {k}: {fmt(v['all'])}")
                for name, s in v["checks"].items():
                    print(f"   {name:>28} {fmt(s)}")
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)


# ------------------------------------------------------------------ the fresh test (PREREG_FRESH.md)


def in_rule_band(r):
    return RULE_BAND[0] - 1e-9 <= r["price"] < RULE_BAND[1] - 1e-9


def rule(rows):
    """The pattern step 1 found, fixed: favourites at 80c to under 98c, 45, 30, 20 and 10 seconds before the close."""
    return [r for r in rows if r["check"] in RULE_CHECKS and in_rule_band(r)]


def before_minute(rows):
    """The same band 90 seconds before the close, before the averaging starts."""
    return [r for r in rows if r["check"] == 90 and in_rule_band(r)]


def verdict(s, older, newer, without_best):
    """PREREG_FRESH.md's bar: pass needs t above 2 and a profit above zero on both halves and without the best day;
    fail is a profit at or below zero or t under 1; anything else is in between."""
    if s.get("too_few"):
        return "too few"
    if s["edge_c"] <= 0 or s["t"] < 1:
        return "fail"
    if s["t"] > 2 and all(not x.get("too_few") and x["edge_c"] > 0 for x in (older, newer, without_best)):
        return "pass"
    return "in between"


def by_month(rows, min_n=30):
    g = defaultdict(list)
    for r in rows:
        g[r["day"][:7]].append(r)
    return {k: stats(g[k], min_n=min_n) for k in sorted(g)}


def fresh():
    lines = list(load(TAPE_OLD))
    b = bets(lines)
    days = sorted({day(m["c"]) for m in lines})
    print(f"{len(lines)} markets, {days[0]} to {days[-1]}; {len(b)} checkpoint bets")
    rows = rule(b)
    s, ch = stats(rows), checks(rows)
    best = next(v for k, v in ch.items() if k.startswith("without best day"))
    v = verdict(s, ch["older half"], ch["newer half"], best)
    print(f"\n=== the rule: favourites 80-98c, 45/30/20/10 s left ===\n{fmt(s)}\nVERDICT: {v}")
    for name, x in ch.items():
        print(f"   {name:>28} {fmt(x)}")
    side = before_minute(b)
    print(f"\n=== reported only: the same band at 90 s, before the averaging ===\n{fmt(stats(side))}")
    for name, x in checks(side).items():
        print(f"   {name:>28} {fmt(x)}")
    print("\n=== reported only: the rule by month ===")
    months = by_month(rows)
    for k, x in months.items():
        print(f"{k} {fmt(x)}")
    print("\n=== reported only: step 1's main cells ===")
    main = {}
    for left in (30, 10):
        for lo, hi, label in ((0.90, 0.95, "90-95c"), (0.95, 0.98, "95-98c")):
            main[f"{left}s {label}"] = stats([r for r in b if r["check"] == left and lo - 1e-9 <= r["price"] < hi - 1e-9])
            print(f"{left}s {label} {fmt(main[f'{left}s {label}'])}")
    with open(OUT_FRESH, "w") as f:
        json.dump({"markets": len(lines), "days": [days[0], days[-1]], "rule": s, "checks": ch, "verdict": v,
                   "before_minute": stats(side), "by_month": months, "step1_main_cells": main}, f, indent=1)


if __name__ == "__main__":
    {"fetch": fetch, "fetch-old": lambda: fetch(*OLD, folder=TAPE_OLD, listing=lambda lo, hi: from_strikes(STRIKES, SERIES, lo, hi)), "report": report,
     "fresh": fresh}[sys.argv[1] if len(sys.argv) > 1 else "report"]()
