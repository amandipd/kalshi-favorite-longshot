"""How the live bot's losses happened, and the skip rule they suggested, tested on the backtest.

Live (the bot's own ledger, read-only): its settled bets by the price band of the ask it saw, the ones the rule would
have skipped against the rest, how often 90-92c lost against the backtest's rate (a Poisson tail: the chance of that
many losses or more by luck), the minute each loss first fell under 50c (Kalshi's minute candles, cached in
live_losses_paths.csv), how crypto losses cluster in a window, and each ET day's bets, losses and average stake.

The rule: skip a 90-92c favourite (the ask, inclusive) whose spread is over 0.2c. It came from the live bets of Sep 28 -
Oct 12, 2026, so the backtest before them never saw it. On the strategy lab's machinery (lab/common.py and
lab/edge_map.py: the live rule at minute 8, $10 bets at the ask + 0.4c with fees, 95% ranges clustered by window, the
bot's sizing from $500), each of the skipped, kept and whole-band bets and the live rule by period; 20 nearby versions
(top price 91-94c x spread any / over 0.1, 0.2, 0.4, 0.9c), each half choosing the one whose skipped bets did worst and
scoring it on the other half (it holds only if the skipped bets lose there too: the range under 0 both ways); and the
bot's sizing with and without the skip.

    python live_losses.py       -> live_losses.json (about a minute; fetches only the candles not cached yet)
"""
import csv
import json
import math
import os
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lab"))
import common as C  # noqa: E402
import edge_map as E  # noqa: E402
from backtest_large import BASE, get  # noqa: E402

LEDGER = os.path.normpath(os.path.join(HERE, "..", "..", "bot", "state", "live-prod.db"))   # opened read-only
CACHE = os.path.join(HERE, "live_losses_paths.csv")
OUT = os.path.join(HERE, "live_losses.json")
ET = ZoneInfo("America/New_York")
NOT_CRYPTO = {"KXCOPPER15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXWTI15M", "KXNATGAS15M"}
BANDS = (("90-92", "90–92¢", 0.90, 0.92), ("92-94", "92–94¢", 0.92, 0.94), ("94+", "94¢ and up", 0.94, 0.999))
WIDE = 0.002            # the rule skips a 90-92c favourite whose spread is over this
EPS = 1e-9              # float noise: 0.913 - 0.911 is a 0.2c spread, not a wider one
FAMILY_HI = (0.91, 0.92, 0.93, 0.94)
FAMILY_SPREAD = (None, 0.001, 0.002, 0.004, 0.009)
S_KEYS = ("bets", "perBet", "mu", "lo", "hi", "pnl", "lost", "implied")
LATE = range(9, 16)     # the minutes after the bot's minute-8 entry


# ------------------------------------------------------------------ the live bets
def read_bets(db_path):
    """The ledger's settled bets, oldest placed first: each the bets row plus ask (the favourite's ask the bot saw,
    decisions.fav_price, else the price paid), spread (that decision's YES ask - bid, to 4 places, else None) and crypto.
    Read-only: the file is never written, and [] if there's no ledger."""
    path = Path(db_path)
    if not path.exists():
        return []
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        cur = con.execute("SELECT b.*, d.fav_price AS _fav, d.yes_bid AS _bid, d.yes_ask AS _ask FROM bets b "
                          "LEFT JOIN decisions d ON d.ticker = b.ticker WHERE b.status IN ('won', 'lost') "
                          "ORDER BY b.placed_ts, b.id")
        names = [c[0] for c in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        x = dict(zip(names, r))
        fav, bid, ask = x.pop("_fav"), x.pop("_bid"), x.pop("_ask")
        x["ask"] = fav if fav is not None else x["price"]
        x["spread"] = round(ask - bid, 4) if bid is not None and ask is not None else None
        x["crypto"] = x["series"] not in NOT_CRYPTO
        out.append(x)
    return out


def band_of(ask):
    """The key of the first band whose range covers the ask, None outside 90-99.9c."""
    for key, _, lo, hi in BANDS:
        if lo - EPS <= ask <= hi + EPS:
            return key
    return None


def is_wide(b):
    return b["spread"] is not None and b["spread"] > WIDE + EPS


def skipped(b):
    """A bet the rule would have skipped: 90-92c and wide."""
    return band_of(b["ask"]) == "90-92" and is_wide(b)


def fav_mids(rows, sides):
    """{ticker: [mid at minute 1 .. 15]} of the favourite side (sides: {ticker: "yes"|"no"}): the YES mid, else the last
    price, 1 minus that for a NO bet; a minute without one carries the last forward (None before the first)."""
    yes = defaultdict(dict)
    for r in rows:
        if r["ticker"] in sides and 1 <= r["k"] <= 15:
            mid = (r["b"] + r["a"]) / 2 if r["b"] is not None and r["a"] is not None else r["p"]
            yes[r["ticker"]][r["k"]] = mid
    out = {}
    for t, by in yes.items():
        cur, mids = None, []
        for k in range(1, 16):
            if by.get(k) is not None:
                cur = by[k] if sides[t] == "yes" else 1 - by[k]
            mids.append(cur)
        out[t] = mids
    return out


def first_flip(mids):
    """The first minute from 9 (after the entry) whose favourite mid is under 50c, or None."""
    for k in LATE:
        m = mids[k - 1]
        if m is not None and m < 0.5:
            return k
    return None


def poisson_tail(k, mu):
    """P(X >= k) for X ~ Poisson(mu)."""
    if k <= 0:
        return 1.0
    if mu <= 0:
        return 0.0
    below = math.fsum(math.exp(-mu + i * math.log(mu) - math.lgamma(i + 1)) for i in range(k))
    return max(0.0, 1.0 - below)


def tally(bs):
    return {"bets": len(bs), "lost": sum(b["status"] == "lost" for b in bs), "pnl": round(float(sum(b["pnl"] for b in bs)), 2),
            "staked": round(float(sum(b["cost"] for b in bs)), 2)}


def live_summary(bets, mids, backtest_loss):
    """The "live" part of live_losses.json (see the spec): totals, bands, the rule's skipped bets against the rest, the
    90-92c watch, when losses flipped, how crypto losses cluster, and each ET day."""
    bands = []
    for key, label, _, _ in BANDS:
        bs = [b for b in bets if band_of(b["ask"]) == key]
        bands.append({"key": key, "label": label, **tally(bs),
                      "implied": sum(1 - b["ask"] for b in bs) / len(bs) if bs else None, "backtest": backtest_loss.get(key)})
    cheap, share = bands[0], backtest_loss.get("90-92")
    watch = None
    if cheap["bets"] and share is not None:
        expected = round(cheap["bets"] * share, 2)
        watch = {"bets": cheap["bets"], "lost": cheap["lost"], "expected": expected,
                 "p": round(poisson_tail(cheap["lost"], expected), 3)}
    flips, flips_of = {str(k): 0 for k in LATE}, 0
    for b in bets:
        if b["status"] == "lost" and b["ticker"] in mids:
            flips_of += 1
            k = first_flip(mids[b["ticker"]])
            if k:
                flips[str(k)] += 1
    by_window = defaultdict(int)
    for b in bets:
        if b["crypto"] and b["status"] == "lost":
            by_window[b["window_open"]] += 1
    by_day = defaultdict(list)
    for b in bets:
        by_day[datetime.fromtimestamp(b["close_ts"], ET).date().isoformat()].append(b)
    days = [{"day": day, **tally(bs), "stake": round(sum(b["cost"] for b in bs) / len(bs), 2)} for day, bs in sorted(by_day.items())]
    return {"from": bets[0]["window_open"] if bets else None, "to": bets[-1]["close_ts"] if bets else None, **tally(bets),
            "bands": bands, "wide": tally([b for b in bets if skipped(b)]), "rest": tally([b for b in bets if not skipped(b)]),
            "watch": watch, "flips": flips, "flipsOf": flips_of,
            "clusters": {"cryptoLost": sum(by_window.values()), "inMulti": sum(n for n in by_window.values() if n >= 2)},
            "days": days}


# ------------------------------------------------------------------ the rule on the backtest
def rule_test(d):
    """(the "rule" part of live_losses.json, {band key: share of live-rule bets lost over the whole backtest}) on a
    markets dict shaped like common.load()'s."""
    m, sy, top = C.live_rule(d)
    w = C.won(d, sy)
    sp = E.spread(d, sy, 8)
    t = d["open_ts"]
    per = C.period_of(t)
    sel = {"pre": per == "pre", "post": np.isin(per, ("before", "build", "paper")), "all": np.ones(len(t), bool)}
    band = lambda hi: m & (top >= 0.90 - EPS) & (top <= hi + EPS)   # noqa: E731
    wide = lambda thr: sp > thr + EPS                               # noqa: E731

    def stats(mask, keys=("pre", "post", "all")):
        pnl, cost, tt, wins, price = E.run_bets(d, mask, top, w)
        p = C.period_of(tt)
        at = {"pre": p == "pre", "post": np.isin(p, ("before", "build", "paper")), "all": np.ones(len(tt), bool)}
        out = {}
        for k in keys:
            s = at[k]
            if not s.any():
                out[k] = {**dict.fromkeys(S_KEYS), "bets": 0}
                continue
            out[k] = {**C.summary(pnl[s], cost[s], tt[s]), "lost": float(1 - wins[s].mean()),
                      "implied": float((1 - price[s]).mean())}
        return out

    skip = band(0.92) & wide(WIDE)
    rows = {"skipped": stats(skip), "kept": stats(band(0.92) & ~wide(WIDE)), "band": stats(band(0.92)), "live": stats(m)}
    family = [{"hi": hi, "spread": s, **stats(band(hi) & (wide(s) if s is not None else True), ("pre", "post"))}
              for hi in FAMILY_HI for s in FAMILY_SPREAD]
    holdout = []
    for a, b in (("pre", "post"), ("post", "pre")):
        fs = [f for f in family if f[a]["bets"]]
        if fs:
            best = min(fs, key=lambda f: f[a]["mu"])
            holdout.append({"chosenOn": a, "scoredOn": b, "hi": best["hi"], "spread": best["spread"],
                            "chosen": best[a], "scored": best[b]})
    holds = len(holdout) == 2 and all(h["scored"]["hi"] is not None and h["scored"]["hi"] < 0 for h in holdout)

    def label(mask):
        ts = t[mask]
        day = lambda x: (lambda u: f"{u:%b} {u.day}")(datetime.fromtimestamp(int(x), timezone.utc))   # noqa: E731
        return f"{day(ts.min())} – {day(ts.max() + 899)}"

    sizing = {name: {k: E.replay(d, mk & sel[k], top, w) for k in ("all", "pre", "post")}
              for name, mk in (("live", m), ("skip", m & ~skip))}
    rule = {"lo": 0.90, "hi": 0.92, "spread": WIDE, "slip": C.SLIP, "start": E.START, "from": int(t.min()),
            "to": int(t.max()) + 900,
            "periods": [{"key": k, "label": label(sel[k])} for k in ("pre", "post", "all") if sel[k].any()],
            "rows": rows, "family": family, "holdout": holdout, "holds": holds, "sizing": sizing}

    # the backtest's loss share per band, each bet in the first band covering its ask (as band_of)
    lost, left, backtest = ~w, m.copy(), {}
    for key, _, lo, hi in BANDS:
        inb = left & (top >= lo - EPS) & (top <= hi + EPS)
        left &= ~inb
        backtest[key] = float(lost[inb].mean()) if inb.any() else None
    return rule, backtest


# ------------------------------------------------------------------ Kalshi's minute candles, cached
FIELDS = ("ticker", "k", "b", "a", "p")


def _num(x):
    return None if x in (None, "") else float(x)


def _close(block):
    block = block or {}
    v = block.get("close_dollars")
    if v is None:
        v = block.get("previous_dollars")
    return _num(v)


def fetch_paths(bets, cache, get):
    """Every bet's minute candles ({ticker, k, b, a, p}: the YES bid, ask and last price at the end of minute k), from
    the cache, fetching only the windows with nothing cached (one call per 20 of a window's markets) and appending them.
    A failed or empty reply adds nothing, so that window is fetched again next run."""
    windows = defaultdict(list)
    for b in bets:
        ts = windows[int(b["window_open"])]
        if b["ticker"] not in ts:
            ts.append(b["ticker"])
    wanted = {t for ts in windows.values() for t in ts}
    cached = []
    if os.path.exists(cache):
        with open(cache, newline="", encoding="utf-8") as fh:
            cached = [{"ticker": r["ticker"], "k": int(r["k"]), "b": _num(r["b"]), "a": _num(r["a"]), "p": _num(r["p"])}
                      for r in csv.DictReader(fh)]
    have = {r["ticker"] for r in cached}
    new = []
    for w, ts in sorted(windows.items()):
        if any(t in have for t in ts):
            continue
        for i in range(0, len(ts), 20):
            d = get(f"{BASE}/markets/candlesticks", params={"market_tickers": ",".join(ts[i:i + 20]), "start_ts": w,
                                                            "end_ts": w + 900, "period_interval": 1})
            for mk in (d or {}).get("markets") or []:
                for c in mk.get("candlesticks") or []:
                    new.append({"ticker": mk["market_ticker"], "k": int((c["end_period_ts"] - w) // 60),
                                "b": _close(c.get("yes_bid")), "a": _close(c.get("yes_ask")), "p": _close(c.get("price"))})
    if new:
        fresh = not os.path.exists(cache)
        with open(cache, "a", newline="", encoding="utf-8") as fh:
            out = csv.writer(fh)
            if fresh:
                out.writerow(FIELDS)
            out.writerows([["" if r[f] is None else r[f] for f in FIELDS] for r in new])
    return [r for r in cached if r["ticker"] in wanted] + new


# ------------------------------------------------------------------ the whole thing
def main():
    bets = read_bets(LEDGER)
    rows = fetch_paths(bets, CACHE, get)
    rule, backtest = rule_test(C.load())
    live = live_summary(bets, fav_mids(rows, {b["ticker"]: b["side"] for b in bets}), backtest)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"asOf": time.time(), "live": live, "rule": rule}, fh, indent=1, allow_nan=False)
    os.replace(tmp, OUT)
    print(f"wrote {OUT}: {live['bets']} live bets, {live['lost']} lost; the rule "
          f"{'holds' if rule['holds'] else 'does not hold'} out of sample")


if __name__ == "__main__":
    main()
