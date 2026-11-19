"""Can a bad window be seen coming? Warning signs at the moment of entry, tested on every bet since Dec 10, 2025.

Strategy: buy the favourite of every crypto, metals and energy market at minute 8 when its ask is
90-99.9c, $10 a bet, filled 0.4c worse than the recorded ask, held to settlement; each warning sign
below is tested as a reason to skip the bet.

For every minute-8 favourite the strategy would have bought (crypto, metals, energy; 90-99.9c;
fills 0.4c worse than the recorded ask, $10 a bet), this measures things the trader can see at
minute 8, before betting:

  market   gap between buy and sell price; how far the favourite moved in the last minute and
           since minute 5; how low it was earlier in the window; how much the price whipsawed
  window   how far crypto prices moved in the first 8 minutes, across all crypto markets (a
           stand-in for how volatile the coins are right now); how many bets the window has
  clock    US economic-news slots (8:30 and 10:00 ET releases, 2:00 ET Fed decisions, 9:30 ET
           stock open), Fed decision days, weekends, hour of day
  recent   losses in the previous window and the last 24 hours

and splits the bets into fifths by each measure. A warning sign is worth acting on only if its
worst fifth loses money in every part of the history (Dec 10 - Jul 17, Jul 18 - Aug 23, and Aug 24 on),
which guards against finding patterns in noise. The crypto-move measure is also tested as a filter
(skip windows above a cut-off).

    python stress_signals.py
"""
import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import strategies_backtest as sb  # the accounts' rules and sizing constants
from strategies_backtest import favourite, fee, ts
import history
from history import strategy

SLIP = 0.004
JUL18, SPLIT = ts(history.JUL18), ts("2026-08-24T00:00:00Z")
PARTS = ("Dec 10 - Jul 17", "Jul 18 - Aug 23", "Aug 24 on")
FED_DAYS = set(sb.FED_DAYS)  # FOMC decisions in the data, 2:00 pm ET
ET = ZoneInfo("America/New_York")  # EST until Mar 8, EDT after


def load():
    with open("universe.json", encoding="utf-8") as fh:
        groups = {u["ticker"]: u["group"] for u in json.load(fh)["series"]}
    first, last = ts(history.FIRST), ts(history.end()) - 900
    num = lambda x: float(x) if x != "" else None
    windows, seen = defaultdict(list), set()
    for path in history.FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen:
                    continue
                seen.add(r["ticker"])
                t = ts(r["open_time"])
                if not first <= t <= last:
                    continue
                g = groups.get(r["series"], "other")
                mids = {k: (num(r[f"b{k}"]) + num(r[f"a{k}"])) / 2 for k in range(1, 9)
                        if num(r[f"b{k}"]) is not None and num(r[f"a{k}"]) is not None}
                m = {"group": g, "mids": mids}
                if g in sb.EDGE_GROUPS and 8 in mids:
                    side, top = favourite(num(r["b8"]), num(r["a8"]))
                    if side and sb.LO <= top <= sb.HI:
                        price = min(top + SLIP, 0.999)
                        c = sb.STAKE / price
                        won = (side == "yes") == (r["resolved_yes"] == "1")
                        fav = {k: v if side == "yes" else 1 - v for k, v in mids.items()}
                        path = [mids[k] for k in sorted(mids)]
                        m["bet"] = {
                            "won": won, "price": price,
                            "pnl": (c if won else 0.0) - sb.STAKE - fee(c, price),
                            "spread": num(r["a8"]) - num(r["b8"]),
                            "d78": fav[8] - fav.get(7, fav[8]),
                            "d58": fav[8] - fav.get(5, fav[8]),
                            "low": min(fav.values()),
                            "chop": sum(abs(b - a) for a, b in zip(path, path[1:])) - abs(path[-1] - path[0]),
                        }
                windows[t].append(m)
    return windows


def window_features(windows):
    """Per window: crypto move over minutes 1-8, bet count, clock, and recent losses."""
    out, loss_hist = {}, []
    for t in sorted(windows):
        ms = windows[t]
        moves = [abs(m["mids"][8] - m["mids"][1]) for m in ms if m["group"] == "crypto" and 1 in m["mids"] and 8 in m["mids"]]
        bets = [m["bet"] for m in ms if "bet" in m]
        et = datetime.fromtimestamp(t, ET)
        hm = et.hour * 60 + et.minute  # the window runs hm .. hm+15 ET

        def slot(h, mi):
            return hm <= h * 60 + mi < hm + 15

        out[t] = {
            "move": sum(moves) / len(moves) if moves else None,
            "nbets": len(bets),
            "news": et.weekday() < 5 and (slot(8, 30) or slot(10, 0) or slot(14, 0)),
            "open": et.weekday() < 5 and slot(9, 30),
            "fed": et.strftime("%Y-%m-%d") in FED_DAYS and 14 * 60 <= hm < 16 * 60,
            "weekend": et.weekday() >= 5,
            "hour": et.hour,
            "prev_losses": loss_hist[-1] if loss_hist else 0,
            "day_losses": sum(loss_hist[-96:]),
        }
        loss_hist.append(sum(not b["won"] for b in bets))
    return out


def stats(rows):
    """n, win rate, price paid, cents per $10 bet and a 95% range clustered by window."""
    if not rows:
        return None
    n = len(rows)
    mu = sum(r["pnl"] for _, r in rows) / n * 100
    by_w = defaultdict(list)
    for t, r in rows:
        by_w[t].append(r["pnl"] * 100)
    k = len(by_w)
    se = None
    if k > 1:
        resid = [sum(v) - mu * len(v) for v in by_w.values()]
        se = (sum(x * x for x in resid) / (k - 1)) ** 0.5 / ((n / k) * math.sqrt(k))
    return {"n": n, "win": sum(r["won"] for _, r in rows) / n, "need": sum(r["price"] for _, r in rows) / n,
            "mu": mu, "lo": mu - 1.96 * se if se else None, "hi": mu + 1.96 * se if se else None}


def fmt(s):
    if not s:
        return f"{'-':>40}"
    rng = f"({s['lo']:+5.1f} to {s['hi']:+5.1f})" if s["lo"] is not None else ""
    return f"{s['n']:5d} {s['win']:6.1%} {s['need']:6.1%} {s['mu']:+6.1f}c {rng:<17}"


def part(t):
    return 0 if t < JUL18 else 1 if t < SPLIT else 2


def split(rows):
    """fmt() of the rows in each part of the history."""
    return tuple(fmt(stats([x for x in rows if part(x[0]) == i])) for i in range(len(PARTS)))


def by_fifths(bets, key, label):
    vals = sorted(v for v in (key(t, b) for t, b in bets) if v is not None)
    if not vals:
        return
    cuts = [vals[int(len(vals) * q / 5)] for q in range(1, 5)]
    print(f"\n{label}")
    print(f"  {'fifth':<22}" + "   ".join(f"{p:^40}" for p in PARTS))
    for i in range(5):
        lo = cuts[i - 1] if i else -math.inf
        hi = cuts[i] if i < 4 else math.inf
        sel = [(t, b) for t, b in bets if key(t, b) is not None and lo <= key(t, b) < hi]
        rng = ("" if i == 0 else f"{lo:.3g}") + " to " + ("" if i == 4 else f"{hi:.3g}")
        print(f"  {i + 1} {rng:<20}" + "   ".join(split(sel)))


def by_flag(bets, key, label):
    print(f"\n{label}")
    for v in (True, False):
        print(f"  {'yes' if v else 'no':<22}" + "   ".join(split([(t, x) for t, x in bets if key(t, x) == v])))


def main():
    strategy(__doc__)
    windows = load()
    W = window_features(windows)
    bets = [(t, m["bet"]) for t in sorted(windows) for m in windows[t] if "bet" in m]
    print(f"{len(bets)} bets in {len(windows)} windows. Columns: bets, won, needed to break even, profit per $10 bet, 95% range")
    print(f"  {'':<22}" + "   ".join(f"{p:^40}" for p in PARTS))
    print(f"  {'all':<22}" + "   ".join(split(bets)))

    print("\n=== THE MARKET ITSELF, AT MINUTE 8")
    by_fifths(bets, lambda t, b: b["spread"], "gap between buy and sell price (dollars)")
    by_fifths(bets, lambda t, b: b["d78"], "favourite's move over the last minute (7 -> 8)")
    by_fifths(bets, lambda t, b: b["d58"], "favourite's move since minute 5")
    by_fifths(bets, lambda t, b: b["low"], "favourite's lowest price in minutes 1-8")
    by_fifths(bets, lambda t, b: b["chop"], "whipsaw: price path length beyond the net move, minutes 1-8")

    print("\n=== THE WINDOW")
    by_fifths(bets, lambda t, b: W[t]["move"], "how far crypto prices moved in minutes 1-8 (average across crypto markets)")
    by_fifths(bets, lambda t, b: W[t]["nbets"] + 0.0, "bets in the window")

    print("\n=== THE CLOCK")
    by_flag(bets, lambda t, b: W[t]["news"], "US news slot (8:30, 10:00 or 2:00 ET window, weekdays)")
    by_flag(bets, lambda t, b: W[t]["open"], "US stock open (9:30 ET window, weekdays)")
    by_flag(bets, lambda t, b: W[t]["fed"], f"Fed decision afternoon (2:00-4:00 ET on {', '.join(sorted(FED_DAYS))})")
    by_flag(bets, lambda t, b: W[t]["weekend"], "weekend (ET)")
    print("\nhour of day (ET), every part together")
    for h in range(24):
        print(f"  {h:02d}:00  {fmt(stats([(t, b) for t, b in bets if W[t]['hour'] == h]))}")

    print("\n=== RECENT RESULTS")
    by_fifths(bets, lambda t, b: W[t]["prev_losses"] + 0.0, "losses in the previous window")
    by_fifths(bets, lambda t, b: W[t]["day_losses"] + 0.0, "losses in the last 24 hours")

    print("\n=== SKIPPING WINDOWS WHERE CRYPTO MOVED A LOT (a filter)")
    moves = sorted(W[t]["move"] for t in W if W[t]["move"] is not None)
    for q in (None, 0.99, 0.95, 0.90, 0.80):
        cut = moves[int(len(moves) * q)] if q else math.inf
        kept = [(t, b) for t, b in bets if W[t]["move"] is None or W[t]["move"] < cut]
        label = "skip nothing" if q is None else f"skip top {1 - q:.0%} (move > {cut:.3f})"
        cells = []
        for i, name in enumerate(PARTS):
            rows = [x for x in kept if part(x[0]) == i]
            cells.append(f"{name}: ${sum(b['pnl'] for _, b in rows):+8.0f} on {len(rows):5d} bets")
        print(f"  {label:<30} " + "   ".join(cells))

    print("\n=== THE 12 WORST WINDOWS ($10 a bet) AND WHAT THEY LOOKED LIKE AT MINUTE 8")
    pct = lambda v: sum(x <= v for x in moves) / len(moves)
    wsum = lambda t: sum(m["bet"]["pnl"] for m in windows[t] if "bet" in m)
    for t in sorted(W, key=wsum)[:12]:
        bs = [m["bet"] for m in windows[t] if "bet" in m]
        et = datetime.fromtimestamp(t, ET)
        print(f"  {et:%a %b %d %H:%M} ET  {sum(not b['won'] for b in bs)}/{len(bs)} lost  ${wsum(t):+7.2f}"
              f"  crypto move {W[t]['move'] or 0:.3f} (percentile {pct(W[t]['move'] or 0):.0%})"
              f"{'  news slot' if W[t]['news'] else ''}{'  Fed' if W[t]['fed'] else ''}")

    print("\n=== DAYS (ET): the 8 worst, with how much crypto moved that day")
    days = defaultdict(lambda: [0.0, 0, 0, []])
    for t, b in bets:
        d = days[datetime.fromtimestamp(t, ET).strftime("%a %b %d")]
        d[0] += b["pnl"]
        d[1] += 1
        d[2] += not b["won"]
    for t in W:
        if W[t]["move"] is not None:
            days[datetime.fromtimestamp(t, ET).strftime("%a %b %d")][3].append(W[t]["move"])
    avgs = sorted(sum(v[3]) / len(v[3]) for v in days.values() if v[3])
    med = avgs[len(avgs) // 2]
    for k, v in sorted(days.items(), key=lambda kv: kv[1][0])[:8]:
        avg = sum(v[3]) / len(v[3]) if v[3] else 0
        print(f"  {k}  ${v[0]:+8.2f}  {v[2]}/{v[1]} lost  crypto move {avg:.3f} ({avg / med:.1f}x a typical day)")


if __name__ == "__main__":
    main()
