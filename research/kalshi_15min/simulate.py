"""Bankroll simulation of the 70% strategy over every window since Jul 18 (snapshots_all.csv).

Strategy: start with $24. Each 15-minute window, at the 8-minute mark, every market whose
favoured side trades at 65-75c gets a bet of (current bankroll / 24) on that
side, held to settlement. Bets settle at minute 15, before the next window's
bets go on, so each window is sized off the bankroll left by the previous one.
"""
import csv
import math
from collections import defaultdict
from datetime import datetime
from history import strategy

strategy(__doc__)

START = 24.0
DIVISOR = 24
BROKE = START / DIVISOR / 100          # stake would fall below one cent
LO, HI = 0.65, 0.75

rows = []
with open("snapshots_all.csv") as fh:
    for r in csv.DictReader(fh):
        rows.append((datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")),
                     r["series"], float(r["price_8min"]), int(r["resolved_yes"])))

windows = defaultdict(list)
for t, s, p, y in rows:
    windows[t].append((s, p, y))
order = sorted(windows)


def bets_in(window, both_sides):
    out = []
    for s, p, y in window:
        if LO <= p <= HI:
            out.append((p, y == 1))
        elif both_sides and LO <= 1 - p <= HI:
            out.append((1 - p, y == 0))
    return out


def run(both_sides, fees, slip):
    b, peak, max_dd, low = START, START, 0.0, START
    n = wins = 0
    fees_paid = 0.0
    daily = {}
    broke_at = None
    for t in order:
        bets = bets_in(windows[t], both_sides)
        if bets:
            stake = b / DIVISOR
            pnl = 0.0
            for price, won in bets:
                fill = min(price + slip, 0.99)
                contracts = stake / fill
                fee = 0.0
                if fees:
                    fee = math.ceil(0.07 * contracts * fill * (1 - fill) * 100 - 1e-9) / 100
                fees_paid += fee
                pnl += (contracts if won else 0.0) - stake - fee
                n += 1
                wins += won
            b += pnl
            peak = max(peak, b)
            low = min(low, b)
            max_dd = max(max_dd, 1 - b / peak)
        daily[t.date()] = b
        if b < BROKE:
            broke_at = t
            break
    return {"final": b, "n": n, "wins": wins, "fees": fees_paid, "dd": max_dd,
            "low": low, "broke": broke_at, "daily": daily}


print(f"Period : {order[0]:%Y-%m-%d %H:%M} -> {order[-1]:%Y-%m-%d %H:%M} UTC "
      f"({(order[-1]-order[0]).total_seconds()/86400:.1f} days, {len(order):,} windows, "
      f"{len(rows):,} market snapshots)\n")

scenarios = [
    ("A. no fees, fill at last trade", False, 0.00),
    ("B. + taker fees (M=1, rounded up to 1c/order)", True, 0.00),
    ("C. + fees and pay 1c above last trade", True, 0.01),
]

results = {}
for both, label in ((True, "EITHER SIDE at 65-75c (the first rule tested)"),
                    (False, "YES SIDE ONLY at 65-75c (earlier analysis)")):
    print("=" * 96)
    print(label)
    print("=" * 96)
    print(f"{'scenario':<48}{'final $':>10}{'return':>10}{'bets':>7}{'win%':>7}"
          f"{'fees $':>8}{'max DD':>8}{'low $':>8}")
    for name, fees, slip in scenarios:
        r = run(both, fees, slip)
        results[(both, name)] = r
        tag = f"  BROKE {r['broke']:%m-%d}" if r["broke"] else ""
        print(f"{name:<48}{r['final']:>10.2f}{(r['final']/START-1)*100:>9.1f}%"
              f"{r['n']:>7,}{r['wins']/max(r['n'],1)*100:>6.1f}%{r['fees']:>8.2f}"
              f"{r['dd']*100:>7.1f}%{r['low']:>8.2f}{tag}")
    print()

print("End-of-day bankroll, either side (A = no fees | B = fees | C = fees + 1c):")
days = sorted(results[(True, scenarios[0][0])]["daily"])
for d in days:
    vals = [results[(True, s[0])]["daily"].get(d) for s in scenarios]
    print(f"  {d}  " + "  ".join(f"{v:>9.2f}" if v is not None else f"{'-':>9}" for v in vals))
