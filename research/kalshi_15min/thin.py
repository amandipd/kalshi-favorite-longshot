"""Does skipping thin markets improve the 90c+ strategy at real ask prices?

Strategy: at the 8-minute mark, buy the favoured side whose ask is 90-99.9c, $10 per trade,
filled at the ask, standard taker fee rounded up per order, held to settlement; each liquidity
measure below is tested as a reason to skip the bet.

Only the 30 days in quotes_30d.csv (Aug 24 - Sep 23) record the volume and time since the last trade
this needs, so it stays on those days. The full history's spreads and price moves are tested in
stress_signals.py and findings.py.

1. Profit per bet broken out by each liquidity measure.
2. Filter chosen on the first half of the month, scored on the second half.
3. Full-month bankroll ($240, $10/trade) with and without that filter.
"""
import csv
import itertools
import math
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import stdev
from history import strategy

strategy(__doc__)

STAKE, START = 10.0, 240.0
LO, HI = 0.90, 0.999


def num(x):
    return float(x) if x != "" else None


bets = []
with open("quotes_30d.csv") as fh:
    for r in csv.DictReader(fh):
        bid, ask = num(r["yes_bid"]), num(r["yes_ask"])
        if bid is None or ask is None:
            continue
        last, p7 = float(r["price_8min"]), num(r["price_7"])
        yes = r["resolved_yes"] == "1"
        no_ask = 1 - bid
        yes_ok, no_ok = LO <= ask <= HI, LO <= no_ask <= HI
        if yes_ok == no_ok:
            continue
        fill, won = (ask, yes) if yes_ok else (no_ask, not yes)
        mid_fav = (bid + ask) / 2 if yes_ok else 1 - (bid + ask) / 2
        c = STAKE / fill
        fee = math.ceil(0.07 * c * fill * (1 - fill) * 100 - 1e-9) / 100
        t = datetime.fromisoformat(r["open_time"].replace("Z", "+00:00"))
        bets.append({
            "t": t, "series": r["series"], "fill": fill, "won": won,
            "pnl": (c if won else 0.0) - STAKE - fee,
            "spread": (ask - bid) * 100,
            "stale": num(r["mins_since_trade"]),
            "vol": float(r["vol_0_8"]),
            "outside": not (bid - 1e-9 <= last <= ask + 1e-9),
            "jump": abs(last - p7) * 100 if p7 is not None else None,
            "mid_fav": mid_fav,
            "hour_et": (t + timedelta(minutes=8) - timedelta(hours=4)).hour,
        })

bets.sort(key=lambda b: b["t"])
windows = sorted({b["t"] for b in bets})
mid_t = windows[len(windows) // 2]
vol_cuts = sorted(b["vol"] for b in bets)
q = lambda f: vol_cuts[int(f * (len(vol_cuts) - 1))]


def stats(bs):
    """Profit per bet with a 95% CI clustered by 15-minute window."""
    n = len(bs)
    if n < 30:
        return n, None, None, None, None
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b["pnl"])
    mu = sum(b["pnl"] for b in bs) / n
    resid = [sum(v) - mu * len(v) for v in by_w.values()]
    se = stdev(resid) / ((n / len(by_w)) * math.sqrt(len(by_w))) if len(by_w) > 1 else float("nan")
    win = sum(b["won"] for b in bs) / n
    return n, mu, mu - 1.96 * se, mu + 1.96 * se, win


def row(label, bs):
    n, mu, lo, hi, win = stats(bs)
    if mu is None:
        print(f"  {label:<26}{n:>7,}   (too few)")
        return
    flag = "+" if lo > 0 else ("-" if hi < 0 else " ")
    print(f"  {label:<26}{n:>7,}{win*100:>7.1f}%{mu*100:>+9.1f}c   [{lo*100:+6.1f}c, {hi*100:+6.1f}c] {flag}")


print(f"Bets (ask 90-99.9c, filled at ask): {len(bets):,} over {len(windows):,} windows\n")
print(f"  {'':<26}{'bets':>7}{'win%':>8}{'profit/$10 bet':>15}{'95% CI':>20}")
row("ALL BETS", bets)

groups = [
    ("SPREAD (ask - bid)", "spread",
     [("<= 0.1c", 0, 0.1001), ("0.1-0.5c", 0.1001, 0.5001), ("0.5-1c", 0.5001, 1.0001),
      ("1-2c", 1.0001, 2.0001), ("> 2c", 2.0001, 1e9)]),
    ("MINUTES SINCE LAST TRADE", "stale",
     [("traded in minute 8", 0, 0.5), ("1 min", 0.5, 1.5), ("2-3 min", 1.5, 3.5),
      ("4+ min", 3.5, 1e9)]),
    ("VOLUME, MINUTES 0-8", "vol",
     [(f"quintile {i+1}", q(i / 5) - (1e-9 if i == 0 else 0), q((i + 1) / 5) + (1e-9 if i == 4 else 0))
      for i in range(5)]),
    ("LAST-MINUTE PRICE MOVE", "jump",
     [("< 1c", 0, 1), ("1-5c", 1, 5), ("> 5c", 5, 1e9)]),
    ("HOUR (US Eastern)", "hour_et",
     [("00-06", 0, 6), ("06-12", 6, 12), ("12-18", 12, 18), ("18-24", 18, 24)]),
]
for title, key, cuts in groups:
    print(f"\n{title}")
    for label, a, b in cuts:
        row(label, [x for x in bets if x[key] is not None and a <= x[key] < b])

print("\nLAST TRADE OUTSIDE CURRENT QUOTES")
row("inside", [b for b in bets if not b["outside"]])
row("outside (stale)", [b for b in bets if b["outside"]])

print("\nSERIES")
by_s = defaultdict(list)
for b in bets:
    by_s[b["series"]].append(b)
for s, bs in sorted(by_s.items(), key=lambda x: -len(x[1])):
    row(s, bs)

# ------------------------------------------------ filter chosen out of sample
first = [b for b in bets if b["t"] < mid_t]
second = [b for b in bets if b["t"] >= mid_t]
grid = list(itertools.product(
    (None, 0.2, 0.5, 1.0),          # max spread, cents
    (None, 0, 1, 2),                # max minutes since last trade
    (None, 0.2, 0.4),               # min volume quantile
    (False, True),                  # skip if last trade outside quotes
))


def apply(bs, f):
    ms, st, vq, inside = f
    vmin = q(vq) if vq is not None else None
    return [b for b in bs
            if (ms is None or b["spread"] <= ms + 1e-9)
            and (st is None or (b["stale"] is not None and b["stale"] <= st))
            and (vmin is None or b["vol"] >= vmin)
            and (not inside or not b["outside"])]


def describe(f):
    ms, st, vq, inside = f
    parts = []
    if ms is not None: parts.append(f"spread <= {ms}c")
    if st is not None: parts.append(f"traded within {st} min")
    if vq is not None: parts.append(f"volume above {int(vq*100)}th pct")
    if inside: parts.append("last trade inside quotes")
    return ", ".join(parts) or "no filter"


scored = []
for f in grid:
    sel = apply(first, f)
    if len(sel) >= len(first) * 0.25:          # keep at least a quarter of bets
        scored.append((sum(b["pnl"] for b in sel), f))
scored.sort(key=lambda x: -x[0])
best = scored[0][1]

print(f"\nFILTER PICKED ON FIRST HALF (before {mid_t:%b %d}), SCORED ON SECOND HALF")
print(f"  best filter: {describe(best)}")
print(f"  {'':<26}{'bets':>7}{'win%':>8}{'profit/$10 bet':>15}{'95% CI':>20}")
row("1st half, no filter", first)
row("1st half, filtered", apply(first, best))
row("2nd half, no filter", second)
row("2nd half, filtered", apply(second, best))
print("  top 5 filters on the first half, and how each did on the second:")
for tot, f in scored[:5]:
    s2 = apply(second, f)
    print(f"    {describe(f):<70} 1st {tot:>+8.2f}   2nd {sum(b['pnl'] for b in s2):>+8.2f} ({len(s2)} bets)")


def bankroll(bs):
    b = START
    peak, dd = START, 0.0
    by_w = defaultdict(list)
    for x in bs:
        by_w[x["t"]].append(x)
    for t in sorted(by_w):
        avail, pnl = b, 0.0
        for x in by_w[t]:
            if avail < STAKE + 0.05:
                continue
            avail -= STAKE
            pnl += x["pnl"]
        b += pnl
        peak = max(peak, b)
        dd = max(dd, 1 - b / peak)
        if b < STAKE:
            return b, dd, t
    return b, dd, None


print("\nFULL MONTH, $240 start, $10 per trade, real ask + fees:")
for label, bs in (("no filter", bets), (f"filter: {describe(best)}", apply(bets, best))):
    fin, dd, broke = bankroll(bs)
    print(f"  {label:<80} ${fin:>9,.2f}   max drawdown {dd*100:.1f}%"
          f"{f'   BROKE {broke:%b %d}' if broke else ''}")
