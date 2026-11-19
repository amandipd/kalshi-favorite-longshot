"""The depth check's live half: a week of real order books at the passed groups' checkpoints, and what they say.

other_markets.py's pass test found four liquid groups that paid in both halves (other_markets_findings.md): hourly
temperature 30 and 10 minutes before the close, and the daily gas, SOFR and ERCOT markets 2 and 1 hours before it.
Its backtest fills a full $10 at the recorded ask plus 0.4c. This records each market's whole order book at those
moments for a week, so the report can say how much $10, $25, $50 and $100 would really have bought there.

Strategy: other_markets.py's favourites rule on the four groups that passed (hourly temperature 30 and 10 minutes
before the close; daily gas, SOFR and ERCOT 2 and 1 hours before). At the checkpoint, buy the favourite (the side
with the higher ask) when its ask is 90-99.9c and its own bid is within 3c of it, $10 a bet, paying up to the ask
plus 0.4c, taker fee with the series' multiplier, and hold it to settlement.

record: every REFRESH seconds it lists the open markets of the FAMILIES series; at each of their checkpoints (up to
GRACE seconds late) it reads the market's order book once and appends it to depth_books.jsonl as Kalshi sent it, a
line a book. Gentle: public GETs only, at most RATE a second, none in seconds 470-560 of a quarter hour (the live
bot's entry). Resumable: a book already in the file isn't read again. Each batch and each failure is logged to
depth_books.log.

report: per family and checkpoint, the bets (liquid and 90-99.9c), the share whose $10, $25, $50 and $100 orders
would have filled in full at the ask plus 0.4c (and $10 at a cent more), the median dollars offered there, and for
the settled bets the profit per $10 bet at the book (only what the book held) against the backtest's (all of it).
Settlements come from Kalshi once and are cached in depth_books_results.json; fee multipliers from other_markets.json.

    python depth_books.py record        # a week; record 2 for two days. Leave it running.
    python depth_books.py report
"""
import json
import os
import re
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import requests

from backtest_large import BASE
from history import strategy
from other_markets import HI, LO, SLIP, fee

GAS = ["KXAAAGASD"] + [f"KXAAAGASD{s}" for s in "TX CA NJ IL FL NY OH WA NC GA PA TN MI VA AZ MA SC OR CO MD MN NV CT IN".split()]
FAMILIES = {   # checks x unit = seconds before the close
    "temp": {"series": ("KXTEMPMIAH", "KXTEMPLAXH", "KXTEMPLAXHS", "KXTEMPNYCH", "KXTEMPNYCHS", "KXTEMPAUSH", "KXTEMPCHIH",
                        "KXTEMPCHIHS", "KXTEMPDCH"), "checks": (30, 10), "unit": 60},
    "econ": {"series": tuple(GAS + ["KXSOFRD", "KXTXERCOTPEAKD"]), "checks": (2, 1), "unit": 3600},
}
STAKES = (10, 25, 50, 100)
LIQUID = 0.03        # the spread screen: the favourite's own bid within 3c of its ask
FULL = 0.999         # a fill of this share of the stake or more counts as full
RATE = 4.0           # requests a second
QUIET = (470, 560)   # seconds into each quarter hour while the live bot orders: no requests then
GRACE = 180          # a checkpoint is still read this many seconds late, then counted missed
REFRESH = 300        # seconds between listings of the open markets
TRIES = 6
WEEK = 7 * 86400
OUT, LOG, RESULTS, FEES = "depth_books.jsonl", "depth_books.log", "depth_books_results.json", "other_markets.json"


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def stamp(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


# ------------------------------------------------------------------ the book


def ladder(book, side):
    """The asks for buying `side`, cheapest first, as [(price, contracts)]: the other side's bids, a bid at p being
    an ask at 1 - p."""
    bids = (book or {}).get("no_dollars" if side == "yes" else "yes_dollars") or []
    return sorted((round(1 - float(p), 4), float(n)) for p, n in bids)


def quote(book):
    """(best YES bid, YES ask): None for a side with no bids."""
    yes = [float(p) for p, _ in (book or {}).get("yes_dollars") or []]
    no = [float(p) for p, _ in (book or {}).get("no_dollars") or []]
    return (max(yes) if yes else None), (round(1 - max(no), 4) if no else None)


def favourite(book):
    """The side other_markets.bets() would buy, with its ask, its own best bid and the spread; None without a real
    bid and ask, or on a tie. No price band here."""
    b, a = quote(book)
    if b is None or a is None or b <= 0 or a >= 1:
        return None
    yes, no = a, round(1 - b, 4)
    if abs(yes - no) < 1e-9:
        return None
    spread = round(a - b, 4)   # the same for both sides
    if yes > no:
        return {"side": "yes", "ask": yes, "bid": b, "spread": spread}
    return {"side": "no", "ask": no, "bid": round(1 - a, 4), "spread": spread}


def walk(levels, dollars, limit):
    """(contracts, cost) of spending up to `dollars` on the levels in turn, at prices up to `limit` only; the last
    level taken may be taken in part."""
    c = cost = 0.0
    for p, n in levels:
        if cost >= dollars:
            break
        if p > limit + 1e-9:
            continue
        take = min(n, (dollars - cost) / p)
        c += take
        cost += take * p
    return c, cost


# ------------------------------------------------------------------ checkpoints


def checkpoints(family, close):
    """[(k, ts)]: each checkpoint of a market closing at `close` (unix seconds)."""
    f = FAMILIES[family]
    return [(k, close - k * f["unit"]) for k in f["checks"]]


def due(markets, now, done):
    """[(market, k)] for each checkpoint that has come and is less than GRACE seconds old, not yet in `done`
    ({(ticker, k)}), oldest first."""
    out = [(ts, m, k) for m in markets for k, ts in checkpoints(m["family"], m["close"])
           if ts <= now < ts + GRACE and (m["ticker"], k) not in done]
    return [(m, k) for _, m, k in sorted(out, key=lambda x: x[0])]


def snap(market, k, book, at):
    """One line of depth_books.jsonl."""
    return {"t": market["ticker"], "s": market["series"], "f": market["family"], "k": k, "close": market["close"],
            "at": at, "book": book}


# ------------------------------------------------------------------ what a book says


def row(rec):
    """A recorded book as the rule sees it; None when it has no favourite. late: seconds after the checkpoint;
    at_ask: dollars offered on the favourite's side up to its ask + SLIP; fill: {stake: the share of it that
    would have filled there}; fill_1c: the same for $10 at a cent more."""
    f = favourite(rec["book"])
    if f is None:
        return None
    levels, top = ladder(rec["book"], f["side"]), f["ask"] + SLIP
    return {**{k: rec[k] for k in ("t", "s", "f", "k", "close", "at")},
            "late": rec["at"] - (rec["close"] - rec["k"] * FAMILIES[rec["f"]]["unit"]),
            "side": f["side"], "ask": f["ask"], "spread": f["spread"],
            "liquid": f["spread"] <= LIQUID + 1e-9, "band": LO <= f["ask"] <= HI,
            "at_ask": sum(p * n for p, n in levels if p <= top + 1e-9),
            "fill": {s: walk(levels, s, top)[1] / s for s in STAKES},
            "fill_1c": walk(levels, 10, top + 0.01)[1] / 10}


def pnl(rec, won, mult, stake=10):
    """Profit of a $stake order at the book: only what it held up to the ask + SLIP, at the prices it held them."""
    f = favourite(rec["book"])
    c, cost = walk(ladder(rec["book"], f["side"]), stake, f["ask"] + SLIP)
    if c == 0:
        return 0.0
    return (c if won else 0.0) - cost - fee(c, cost / c, mult)


def pnl_backtest(rec, won, mult):
    """Profit as other_markets.py has it: the full $10 at the ask + SLIP (99.9c at most)."""
    p = min(favourite(rec["book"])["ask"] + SLIP, 0.999)
    c = 10 / p
    return (c if won else 0.0) - 10 - fee(c, p, mult)


def summarise(records, results, mults):
    """{(family, k): what the report prints} over the records (any iterable, read once). Only the bets count past
    "snaps": liquid and in the band. results: {ticker: "yes"|"no"} for the settled ones; mults: {series: fee
    multiplier}, 1 if missing."""
    snaps, bets = Counter(), defaultdict(list)   # bets: (row, (pnl at the book, backtest's) or None if unsettled)
    for rec in records:
        key = (rec["f"], rec["k"])
        snaps[key] += 1
        r = row(rec)
        if not (r and r["liquid"] and r["band"]):
            continue
        res, made = results.get(rec["t"]), None
        if res is not None:
            won, mult = (r["side"] == "yes") == (res == "yes"), mults.get(rec["s"], 1)
            made = (pnl(rec, won, mult), pnl_backtest(rec, won, mult))
        bets[key].append((r, made))
    keys = [(f, k) for f, v in FAMILIES.items() for k in v["checks"]]
    out = {}
    for key in keys + sorted(set(snaps) - set(keys)):
        bs = bets[key]
        done = [made for _, made in bs if made]
        share = lambda ok: sum(1 for r, _ in bs if ok(r)) / len(bs) if bs else None
        mean = lambda xs: sum(xs) / len(xs) if xs else None
        out[key] = {"snaps": snaps[key], "bets": len(bs),
                    **{f"full{s}": share(lambda r, s=s: r["fill"][s] >= FULL - 1e-9) for s in STAKES},
                    "full10_1c": share(lambda r: r["fill_1c"] >= FULL - 1e-9),
                    "median_at_ask": statistics.median(r["at_ask"] for r, _ in bs) if bs else None,
                    "settled": len(done), "pnl_book": mean([d[0] for d in done]), "pnl_backtest": mean([d[1] for d in done])}
    return out


def report(summary):
    pct = lambda x: f"{'-' if x is None else f'{x:.0%}':>5}"
    cents = lambda x: f"{'-' if x is None else f'{x * 100:+.1f}c':>9}"
    print(f"\n   {'':<12} {'':>6} {'':>6} {'median $':>9}   {'filled in full':^23}   {'':>15}  "
          f"{'':>7} {'per $10 bet':^19}")
    print(f"   {'':<12} {'books':>6} {'bets':>6} {'at ask':>9}   {'$10':>5} {'$25':>5} {'$50':>5} {'$100':>5}"
          f"   {'$10 a cent more':>15}  {'settled':>7} {'at book':>9} {'backtest':>9}")
    for (f, k), v in summary.items():
        label = f"{f} {k}{'min' if FAMILIES.get(f, {}).get('unit') == 60 else 'h'}"
        at = "-" if v["median_at_ask"] is None else f"${v['median_at_ask']:,.0f}"
        print(f"   {label:<12} {v['snaps']:>6,} {v['bets']:>6,} {at:>9}   "
              + " ".join(pct(v[f"full{s}"]) for s in STAKES)
              + f"   {pct(v['full10_1c']):>15}  {v['settled']:>7,} {cents(v['pnl_book'])} {cents(v['pnl_backtest'])}")
    print("\nBets: the favourite liquid (spread 3c or less) and 90-99.9c. Filled in full: the order got 99.9% of its"
          " dollars at the ask + 0.4c or better. At book: a $10 order that buys only what the book held up to the"
          " ask + 0.4c. Backtest: the full $10 at the ask + 0.4c, as other_markets.py has it.")


# ------------------------------------------------------------------ Kalshi

_lock, _next, _local = threading.Lock(), [0.0], threading.local()


def get(path, params=None):
    """GET BASE + path as JSON; None for a 404. One request at a time across threads, each at least 1/RATE after
    the last and never in the QUIET seconds; 429s, 5xx and dropped connections are tried again after 1, 2, 4, 8
    and 16 s, then it gives up with an error."""
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    why = None
    for i in range(TRIES):
        if i:
            time.sleep(2 ** (i - 1))
        try:
            with _lock:   # the wait and the request under one lock, so no other thread slips in between
                while True:
                    t = time.time()
                    if QUIET[0] <= t % 900 <= QUIET[1]:
                        time.sleep(QUIET[1] + 1 - t % 900)
                    elif t < _next[0]:
                        time.sleep(_next[0] - t)
                    else:
                        break
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
    """Every open market of every FAMILIES series: {"ticker", "series", "family", "close" (unix seconds)}."""
    out = []
    for family, f in FAMILIES.items():
        for s in f["series"]:
            cursor = None
            while True:
                params = {"series_ticker": s, "status": "open", "limit": 1000, **({"cursor": cursor} if cursor else {})}
                d = get("/markets", params) or {}
                out += [{"ticker": m["ticker"], "series": s, "family": family, "close": ts(m["close_time"])}
                        for m in d.get("markets") or []]
                cursor = d.get("cursor")
                if not cursor:
                    break
    return out


def load(path=OUT):
    """The books recorded in `path`, one at a time (none without the file); a line cut short by a stopped run is
    skipped."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def log(t, msg):
    line = f"{stamp(t)}  {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def record(path=OUT, until=None, now=time.time, sleep=time.sleep):
    """Read every due book into `path` until `until` (a week from the start without one). Waits only with `sleep`,
    5 s at a time at most, waking at each next checkpoint."""
    start = now()
    until = start + WEEK if until is None else until
    done = {(r["t"], r["k"]) for r in load(path)}
    log(start, f"recording books to {path} until {stamp(until)}; {len(done):,} already there")
    markets, listed, counts = [], None, None
    with open(path, "a", encoding="utf-8") as fh:
        while now() < until:
            if listed is None or now() - listed >= REFRESH:
                listed = now()
                try:
                    markets = open_markets()
                except Exception as e:   # keep the last list and try again at the next refresh
                    log(now(), f"listing the open markets failed: {e!r}")
                if Counter(m["family"] for m in markets) != counts:   # logged when the numbers change
                    counts = Counter(m["family"] for m in markets)
                    log(now(), f"{len(markets)} open markets ({', '.join(f'{f} {n}' for f, n in sorted(counts.items()))})")
            batch, got, missed, t0 = due(markets, now(), done), Counter(), 0, now()
            for m, k in batch:
                done.add((m["ticker"], k))   # one try only: a book that fails isn't asked for again
                if now() >= m["close"] - k * FAMILIES[m["family"]]["unit"] + GRACE:
                    missed += 1   # the batch ran so long that this checkpoint is past
                    continue
                try:
                    book = (get(f"/markets/{m['ticker']}/orderbook") or {})["orderbook_fp"]
                except Exception as e:
                    log(now(), f"{m['ticker']} {k}: no book: {e!r}")
                    continue
                fh.write(json.dumps(snap(m, k, book, round(now(), 3)), separators=(",", ":")) + "\n")
                fh.flush()
                got[(m["family"], k)] += 1
            if batch:
                log(now(), f"{sum(got.values())} of {len(batch)} books in {now() - t0:.0f} s"
                           f" ({', '.join(f'{f} {k}: {n}' for (f, k), n in sorted(got.items())) or 'none'})"
                           + (f"; {missed} missed" if missed else ""))
            t = now()
            nxt = min((ts for m in markets for k, ts in checkpoints(m["family"], m["close"])
                       if t < ts + GRACE and (m["ticker"], k) not in done), default=until)
            sleep(max(0.0, min(5.0, nxt - t, listed + REFRESH - t, until - t)))
    log(now(), f"stopped: the end of the run ({stamp(until)})")


def results(tickers, cache=RESULTS):
    """{ticker: "yes"|"no"} for the settled ones among `tickers`. Each is asked of Kalshi once and kept in `cache`;
    one not settled yet is left out and asked again next time."""
    have = {}
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            have = json.load(fh)
    try:
        for t in tickers:
            if t not in have:
                m = (get(f"/markets/{t}") or {}).get("market") or {}
                if m.get("result") in ("yes", "no"):
                    have[t] = m["result"]
    finally:   # what was learned is kept even if Kalshi stops answering part way
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump(have, fh)
    return {t: have[t] for t in tickers if t in have}


HEAD = re.compile(r'"series": "([^"]+)"[^\[\]]*?"fee_multiplier": (null|[-+0-9.eE]+), "markets"')


def multipliers(path=FEES):
    """{series: fee multiplier} for the FAMILIES series from fetch_other.py's other_markets.json (1 where it says
    none). That file is ~170 MB of market lists, so it is scanned a piece at a time for the series' headers rather
    than loaded whole."""
    want = {s for f in FAMILIES.values() for s in f["series"]}
    out, tail = {}, ""
    with open(path, encoding="utf-8") as fh:
        while chunk := fh.read(1 << 20):
            text = tail + chunk
            for s, m in HEAD.findall(text):
                if s in want:
                    out[s] = 1.0 if m == "null" else float(m)
            tail = text[-4096:]
    return out


def main():
    what = sys.argv[1:] or ["report"]
    if what[0] == "record":
        record(until=time.time() + float(what[1]) * 86400 if len(what) > 1 else None)
    elif what[0] == "report":
        strategy(__doc__)
        seen = {r["t"]: r["close"] for r in load(OUT)}
        closed = sorted(t for t, c in seen.items() if c < time.time())
        print(f"{OUT}: {len(seen):,} markets, {len(closed):,} closed; their settlements from Kalshi"
              f" (cached in {RESULTS})", flush=True)
        res = results(closed)
        mults = multipliers() if os.path.exists(FEES) else {}
        print(f"{len(res):,} settled; fee multipliers: " + (
            f"{len(mults)} series from {FEES} ({', '.join(sorted({f'{m:g}' for m in mults.values()}))}), 1 for the rest"
            if mults else f"1 for all (no {FEES} here)"))
        report(summarise(load(OUT), res, mults))
    else:
        sys.exit("python depth_books.py record [days] | report")


if __name__ == "__main__":
    main()
