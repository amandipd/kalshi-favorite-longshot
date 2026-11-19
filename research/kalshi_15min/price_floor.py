"""Where to start buying: the live bot's rule with its lowest price at 90, 91, 92, 93 or 95c, on every window since Dec 10, 2025.

Strategy: the live bot's rule (strategies_backtest.LIVE) - the minute-8 favourite of every crypto, metals and energy
market whose ask is in the band, 3% a bet and 20% a window, skipping both warning signs, whole contracts, no bets in a
Fed decision's windows, held to settlement - with only its lowest price changed: 90, 91, 92, 93 or 95c.

Live, the 90-91c bets lost far more often than the rest (37 won and 10 lost by Oct 11, 2026, while every band from 92c
up made money). Three questions:

  1. Per bet: does 90-91c earn less than the dearer bands, at $10 a bet with fills 0.4c worse than the recorded ask?
     Each band's edge comes with a 95% range clustered by window, for each period and the whole history.
  2. Fills: Kalshi's trade tape (liquidity.json, around every live-rule bet) says which orders would have filled. Do the ones that
     don't fill win more often than the ones that do (adverse selection: sellers pull their offers from a favourite
     that's about to win), and most at 90-91c?
  3. With the bot's own sizing from $500, which floor ends highest and falls least, with every order filled in full and
     with fills limited by the tape?

The loader keeps only the minutes the rule reads (6-8) and the favourites at 90c or more, so the whole history fits in
little memory. The replays are strategies_backtest's own run(); the tests check both loaders give the same one.

    python price_floor.py       -> price_floor.json (about 4 minutes)
"""
import csv
import json
import math
import os
from collections import defaultdict

import history
import strategies_backtest as sb
from history import strategy

FLOORS = (0.90, 0.91, 0.92, 0.93, 0.95)
BANDS = ((90, 91), (92, 94), (95, 97), (98, 99))   # whole cents; bot/dashboard.py's PRICE_BANDS are the same
SLIP = sb.SCENARIOS["live"]                         # live-like fills, 0.4c worse than the recorded ask
START = 500.0                                       # a round starting amount
TAPE_FROM = history.FIRST                           # liquidity.json holds the tape around every live-rule bet since then
MINUTES = (6, 7, 8)                                 # what the rule reads: the late-favourite check, then the entry
OUT = "price_floor.json"


def band_of(price):
    """The index in BANDS of a price's whole cents (0.9199999999 is 92c, a 90.75c fill 90c), or None outside them."""
    c = int(price * 100 + 1e-6)
    return next((i for i, (lo, hi) in enumerate(BANDS) if lo <= c <= hi), None)


def label(lo, hi):
    return {"key": f"{lo}-{hi}", "label": f"{lo}–{hi}¢", "lo": lo, "hi": hi}


def load():
    """strategies_backtest.load()'s windows with only what the rule can bet: crypto, metals and energy favourites at the
    lowest floor or more at minute 8, with their quotes at minutes 6-8. Every window keeps an entry, bets or not."""
    with open("universe.json", encoding="utf-8") as fh:
        groups = {u["ticker"]: u["group"] for u in json.load(fh)["series"]}
    num = lambda x: float(x) if x != "" else None
    first, last = sb.ts(sb.PERIODS[0][2]), sb.ts(sb.PERIODS[-1][3]) - 900
    windows, seen = defaultdict(list), set()
    for path in history.FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen:   # a market in two files: the first one read wins, as in strategies_backtest
                    continue
                seen.add(r["ticker"])
                t = sb.ts(r["open_time"])
                if not first <= t <= last:
                    continue
                ms = windows[t]
                group = groups.get(r["series"], "other")
                side, top = sb.favourite(num(r["b8"]), num(r["a8"]))
                if group in sb.EDGE_GROUPS and side and top >= min(FLOORS) - 1e-9:
                    ms.append({"ticker": r["ticker"], "series": r["series"], "group": group, "yes": r["resolved_yes"] == "1",
                               "q": {k: (num(r[f"b{k}"]), num(r[f"a{k}"])) for k in MINUTES}})
    return dict(windows), first, last


def bets(windows, lo):
    """Every bet the live rule places with `lo` as its lowest price, from a bankroll that can't run out:
    (window open, recorded ask, won, market)."""
    strat = {**sb.LIVE[0], "lo": lo}
    out = []
    for t in sorted(windows):
        if any(t < z and t + 900 > a for a, z in strat["blackouts"]):
            continue
        for m in windows[t]:
            side, top = sb.favourite(*m["q"][strat["minute"]])
            if side and lo <= top <= sb.HI and not sb.skipped(strat, m, side):
                out.append((t, top, (side == "yes") == m["yes"], m))
    return out


def edge(rows, slip):
    """$10 bets at the ask plus `slip`: how many, the share won, the break-even share (cost and fee per contract), cents
    per $10 after fees with its 95% range clustered by window (a window's bets move together), and the dollars made."""
    if not rows:
        return None
    per, by_window, need = [], defaultdict(list), 0.0
    for t, top, won, _ in rows:
        price = min(top + slip, 0.999)
        c = 10 / price
        f = sb.fee(c, price)
        x = ((c if won else 0.0) - 10 - f) * 100
        per.append(x)
        by_window[t].append(x)
        need += price + f / c
    n = len(per)
    mu = sum(per) / n
    k = len(by_window)
    se = math.sqrt(sum((sum(v) - mu * len(v)) ** 2 for v in by_window.values()) * k / max(k - 1, 1)) / n
    return {"n": n, "win": sum(r[2] for r in rows) / n, "need": need / n, "mu": mu, "lo": mu - 1.96 * se,
            "hi": mu + 1.96 * se, "usd": sum(per) / 100}


def fills(rows):
    """From TAPE_FROM, the bets in markets the trade tape covers, by band: how many a $10 order would have filled at least
    in part (strategies_backtest.available), how often the filled and the unfilled ones won, and the edge of the filled
    ones at the ask itself (an immediate-or-cancel order never pays more than its limit). None without a tape."""
    if not sb.LIQUIDITY:
        return None
    since = sb.ts(TAPE_FROM)
    by = [[] for _ in BANDS]
    for r in rows:
        t, top, _, m = r
        i = band_of(top)
        if t >= since and i is not None and m["ticker"] in sb.LIQUIDITY:
            by[i].append((r, sb.available(m, top, math.floor(10 / top + 1e-9)) > 0))
    share = lambda xs: sum(x[2] for x in xs) / len(xs) if xs else None
    out = []
    for (lo, hi), got in zip(BANDS, by):
        filled, missed = [r for r, ok in got if ok], [r for r, ok in got if not ok]
        out.append({**label(lo, hi), "bets": len(got), "filled": len(filled), "winFilled": share(filled),
                    "winMissed": share(missed), "edge": edge(filled, 0.0)})
    return {"from": TAPE_FROM, "bands": out}


def periods(first, last):
    """strategies_backtest's periods, then the whole history: (key, label, from, to) with ISO dates."""
    return [(k, lab, a, b) for k, lab, a, b in sb.PERIODS] + [("all", "Whole history", sb.PERIODS[0][2], sb.PERIODS[-1][3])]


def summary(r):
    return {k: r[k] for k in ("start", "final", "ret", "bets", "maxDD", "worstDay", "broke")}


def runs(windows, first, last):
    """{floor: {period: {"full", "tape"}}}: the live rule with its own sizing from START at the start of each period (and
    of the whole history), every order filled in full 0.4c worse than the ask, and again with fills limited by the trade
    tape (None without one). A period with no windows is left out."""
    out = {lo: {} for lo in FLOORS}
    for key, _, a, z in periods(first, last):
        sub = {t: ms for t, ms in windows.items() if sb.ts(a) <= t < sb.ts(z)}
        if not sub:
            continue
        t0 = min(sub)
        hours = int((max(sub) + 900 - t0) // sb.HOUR) + 1
        for lo in FLOORS:
            strat = {**sb.LIVE[0], "lo": lo, "start": START}
            full = sb.run(strat, sub, SLIP, t0, hours)
            tape = sb.run({**strat, "liquidity": True}, sub, SLIP, t0, hours) if sb.LIQUIDITY else None
            out[lo][key] = {"full": summary(full), "tape": tape and summary(tape)}
    return out


def build(windows, first, last):
    """Everything price_floor.json holds (the Research tab's Edge view draws it)."""
    ps = periods(first, last)
    every = bets(windows, min(FLOORS))
    in_band = [[r for r in every if band_of(r[1]) == i] for i in range(len(BANDS))]
    bands = []
    for (lo, hi), rows in zip(BANDS, in_band):
        by = {k: edge([r for r in rows if sb.ts(a) <= r[0] < sb.ts(z)], SLIP) for k, _, a, z in ps}
        bands.append({**label(lo, hi), "all": by["all"], "periods": by})
    rs = runs(windows, first, last)
    floors = [{"lo": lo, "edge": edge([r for r in every if r[1] >= lo - 1e-9], SLIP), "runs": rs[lo]} for lo in FLOORS]
    return {"from": ps[-1][2], "to": ps[-1][3], "slip": SLIP, "start": START,
            "periods": [{"key": k, "label": lab, "from": a, "to": z} for k, lab, a, z in ps],
            "bands": bands, "fills": fills(every), "floors": floors}


def main():
    strategy(__doc__)
    out = build(*load())
    print(f"\n{out['from'][:10]} to {out['to'][:10]} · $10 a bet, fills {SLIP * 100:.1f}c worse than the ask: cents per $10 [95% range]")
    for b in out["bands"]:
        e = b["all"]
        print(f"  {b['label']:>7}  " + ("no bets" if not e else f"{e['n']:>6} bets  won {e['win']:.1%}  break-even {e['need']:.1%}"
                                         f"  {e['mu']:+.1f}c [{e['lo']:+.1f}, {e['hi']:+.1f}]  ${e['usd']:+,.0f}"))
    if out["fills"]:
        print(f"\nfrom {out['fills']['from'][:10]}, markets the trade tape covers: share filled, won if filled / if not")
        for b in out["fills"]["bands"]:
            if b["bets"]:
                print(f"  {b['label']:>7}  {b['bets']:>6} bets  {b['filled'] / b['bets']:.0%} filled  "
                      f"{b['winFilled'] or 0:.1%} / {b['winMissed'] or 0:.1%}")
    print(f"\nthe bot's sizing from ${START:,.0f} over the whole history: ends at (deepest fall), full fills | trade-tape fills")
    for f in out["floors"]:
        r = f["runs"].get("all")
        if r:
            cell = lambda x: "—" if not x else f"${x['final']:>10,.2f} ({x['maxDD']:.0%})"
            print(f"  {f['lo'] * 100:.0f}c and up  {cell(r['full'])} | {cell(r['tape'])}")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
