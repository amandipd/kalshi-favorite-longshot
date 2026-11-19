"""Net-of-fee edge by price band, every market since Jul 18 (snapshots_all.csv, from history.py).

Strategy: at minute 8 of each window, buy YES at its last trade price in one 10c price band, in every
crypto, metals and energy market, and hold it to settlement. One row per band: as a taker (the full
fee, and again paying 1c above the last trade) and as a maker (a quarter of the fee).

Fees scale with P*(1-P), so they bite hardest near 50c and are almost free at
the extremes. That changes which band is actually worth trading.
"""
import csv
import math
from collections import defaultdict
from history import strategy

strategy(__doc__)

Z = 1.96


def wilson(k, n):
    p = k / n
    d = 1 + Z**2 / n
    c = (p + Z**2 / (2 * n)) / d
    h = (Z / d) * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2))
    return c - h, c + h


rows = []
with open("snapshots_all.csv") as fh:
    for r in csv.DictReader(fh):
        rows.append((float(r["price_8min"]), int(r["resolved_yes"])))

bands = defaultdict(list)
for p, y in rows:
    bands[min(int(p * 10), 9)].append((p, y))

print("NET EDGE BY BAND, buying YES and holding to settlement")
print("(taker fee M=1.0; 'ask cost' assumes paying 1 cent above last trade)")
print()
print(f"{'band':>10} {'n':>7} {'gross':>8} {'fee':>7} {'net':>8} "
      f"{'net/$1':>8} {'net w/ 1c ask':>14} {'edge signif?':>13}")

for b in sorted(bands):
    g = bands[b]
    n = len(g)
    k = sum(y for _, y in g)
    ap = sum(p for p, _ in g) / n
    actual = k / n
    lo, hi = wilson(k, n)
    gross = actual - ap
    fee = 0.07 * ap * (1 - ap)
    net = gross - fee
    net_ask = gross - fee - 0.01          # pay one tick above last trade
    sig = "yes" if (lo - ap) > 0 else ("no" if (hi - ap) > 0 else "negative")
    print(f"{b*10:>3}-{b*10+10:<3}c {n:>7,} {gross:>+8.4f} {fee:>7.4f} "
          f"{net:>+8.4f} {net/ap*100:>7.2f}% {net_ask:>+14.4f} {sig:>13}")

print()
print("Same, as a MAKER (fee = 25% of taker, and you earn the spread rather")
print("than pay it - but only get filled when someone crosses to you):")
print()
print(f"{'band':>10} {'n':>7} {'gross':>8} {'fee':>7} {'net':>8} {'net/$1':>8}")
for b in sorted(bands):
    g = bands[b]
    n = len(g)
    k = sum(y for _, y in g)
    ap = sum(p for p, _ in g) / n
    gross = k / n - ap
    fee = 0.25 * 0.07 * ap * (1 - ap)
    net = gross - fee
    print(f"{b*10:>3}-{b*10+10:<3}c {n:>7,} {gross:>+8.4f} {fee:>7.4f} "
          f"{net:>+8.4f} {net/ap*100:>7.2f}%")
