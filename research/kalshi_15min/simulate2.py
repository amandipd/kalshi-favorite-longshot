"""Bankroll simulations over every window since Jul 18 (snapshots_all.csv): 70c vs heavy favourites,
proportional ($24, 1/24 per bet) vs fixed ($240, $10 per bet) sizing.

Strategy: at the 8-minute mark, the favoured side of each crypto, metals and energy market (YES if YES >= 50c,
else NO) is bet if its price falls in the band. Bets settle at minute 15,
before the next window's bets are placed.
"""
import csv
import math
from collections import defaultdict
from datetime import datetime
from history import strategy

strategy(__doc__)

Z = 1.96

rows = []
with open("snapshots_all.csv") as fh:
    for r in csv.DictReader(fh):
        rows.append((datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")),
                     r["series"], float(r["price_8min"]), int(r["resolved_yes"])))

windows = defaultdict(list)
for t, s, p, y in rows:
    windows[t].append((s, p, y))
order = sorted(windows)


def bets_in(window, lo, hi):
    out = []
    for s, p, y in window:
        if p >= 0.5:
            fav, won = p, y == 1
        else:
            fav, won = 1 - p, y == 0
        if lo <= fav <= hi and fav < 1.0:
            out.append((fav, won))
    return out


def run(lo, hi, start, mode, amt, fees, slip):
    """mode 'prop': stake = bankroll/amt.  mode 'fixed': stake = amt."""
    b, peak, max_dd, low = start, start, 0.0, start
    n = wins = skipped = 0
    fees_paid = 0.0
    daily, broke_at = {}, None
    floor = amt if mode == "fixed" else start / amt / 100
    for t in order:
        bets = bets_in(windows[t], lo, hi)
        if bets:
            stake = amt if mode == "fixed" else b / amt
            avail, pnl = b, 0.0
            for price, won in bets:
                fill = price + slip
                if fill >= 1.0:
                    skipped += 1
                    continue
                contracts = stake / fill
                fee = (math.ceil(0.07 * contracts * fill * (1 - fill) * 100 - 1e-9) / 100
                       if fees else 0.0)
                if mode == "fixed" and avail < stake + fee:
                    skipped += 1
                    continue
                avail -= stake + fee
                fees_paid += fee
                pnl += (contracts if won else 0.0) - stake - fee
                n += 1
                wins += won
            b += pnl
            peak = max(peak, b)
            low = min(low, b)
            max_dd = max(max_dd, 1 - b / peak)
        daily[t.date()] = b
        if b < floor:
            broke_at = t
            break
    return {"final": b, "n": n, "wins": wins, "fees": fees_paid, "dd": max_dd,
            "low": low, "broke": broke_at, "daily": daily, "skipped": skipped}


def wilson(k, n):
    p = k / n
    d = 1 + Z**2 / n
    c = (p + Z**2 / (2 * n)) / d
    h = (Z / d) * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2))
    return c - h, c + h


print(f"Period: {order[0]:%Y-%m-%d} -> {order[-1]:%Y-%m-%d} "
      f"({len(order):,} windows, {len(rows):,} market snapshots)\n")

for name, lo, hi in (("65-75c favourites", 0.65, 0.75), ("90c+ favourites", 0.90, 0.999)):
    bs = [x for w in order for x in bets_in(windows[w], lo, hi)]
    n = len(bs)
    k = sum(w for _, w in bs)
    P = sum(p for p, _ in bs) / n
    l, h = wilson(k, n)
    print(f"{name}: {n:,} bets ({n/len(order):.1f} per window), avg price {P:.4f}, "
          f"win {k/n:.4f} [95% CI {l:.4f}-{h:.4f}], gross edge {(k/n-P)/P*100:+.2f}% per $1, "
          f"taker fee {0.07*(1-P)*100:.2f}% per $1")
print()

strategies = [
    ("baseline: 65-75c, $24, 1/24 of bankroll", 0.65, 0.75, 24.0, "prop", 24),
    ("(a) 90c+,  $24, 1/24 of bankroll",       0.90, 0.999, 24.0, "prop", 24),
    ("(b) 65-75c, $240, $10 per trade",         0.65, 0.75, 240.0, "fixed", 10.0),
    ("(a+b) 90c+, $240, $10 per trade",         0.90, 0.999, 240.0, "fixed", 10.0),
]
scenarios = [
    ("A no fees", False, 0.00),
    ("B taker fees", True, 0.00),
    ("C fees + 1c worse fill", True, 0.01),
]

results = {}
for sname, lo, hi, start, mode, amt in strategies:
    print("=" * 104)
    print(sname)
    print("=" * 104)
    print(f"{'scenario':<26}{'final $':>11}{'return':>10}{'bets':>8}{'win%':>7}"
          f"{'fees $':>10}{'max DD':>8}{'low $':>10}  status")
    for cname, fees, slip in scenarios:
        r = run(lo, hi, start, mode, amt, fees, slip)
        results[(sname, cname)] = r
        status = f"broke {r['broke']:%b %d}" if r["broke"] else "survived to the end"
        print(f"{cname:<26}{max(r['final'],0):>11,.2f}{(max(r['final'],0)/start-1)*100:>9.1f}%"
              f"{r['n']:>8,}{r['wins']/max(r['n'],1)*100:>6.1f}%{r['fees']:>10,.2f}"
              f"{r['dd']*100:>7.1f}%{max(r['low'],0):>10,.2f}  {status}")
    print()

key = strategies[3][0]
print(f"End-of-day bankroll, {key}:")
print(f"  {'date':<12}" + "".join(f"{c[0]:>26}" for c in scenarios))
for d in sorted(results[(key, scenarios[0][0])]["daily"]):
    vals = [results[(key, c[0])]["daily"].get(d) for c in scenarios]
    print(f"  {str(d):<12}" + "".join(f"{v:>26,.2f}" if v is not None else f"{'-':>26}"
                                      for v in vals))
