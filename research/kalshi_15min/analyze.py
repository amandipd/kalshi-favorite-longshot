"""
Analyse every market since Dec 10, 2025 (snapshots_all.csv, from history.py) at minute 8: calibration across all price bands, plus
the 70c strategy's edge before and after fees.

Strategy: at minute 8 of each 15-minute window, buy YES in every crypto, metals and energy market
whose last trade is 65-75c, and hold it to settlement. (The calibration table tests no strategy: it
sets each 10c price band against how often those contracts won.)

Kalshi taker fee per contract = M * 0.07 * P * (1-P); maker = 25% of that.
M is a per-market multiplier (1.0 for standard categories, higher for crypto),
so the net-EV table sweeps a range of M rather than assuming one value.

load_rows() and calibration() are importable, so other scripts read the same table this prints.
"""
import csv
import math
from collections import defaultdict
from history import strategy

CSV = "snapshots_all.csv"
Z = 1.96  # 95%


def wilson(k, n):
    """Wilson score interval - well-behaved for proportions near 0/1."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + Z**2 / n
    centre = (p + Z**2 / (2 * n)) / denom
    half = (Z / denom) * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2))
    return (centre - half, centre + half)


def load_rows(path=CSV):
    """Every market at minute 8: its series, last trade and result."""
    with open(path) as fh:
        return [{"series": r["series"], "price": float(r["price_8min"]), "yes": int(r["resolved_yes"])}
                for r in csv.DictReader(fh)]


def calibration(rows):
    """Each 10c band: markets, average price, how often YES won, the gap and a 95% Wilson interval on the win rate."""
    bands = defaultdict(list)
    for r in rows:
        bands[min(int(r["price"] * 10), 9)].append(r)
    out = []
    for b in sorted(bands):
        g = bands[b]
        n = len(g)
        k = sum(x["yes"] for x in g)
        avg_p = sum(x["price"] for x in g) / n
        lo, hi = wilson(k, n)
        out.append({"band": b, "low": b / 10, "high": (b + 1) / 10, "n": n, "price": avg_p, "actual": k / n,
                    "diff": k / n - avg_p, "lo": lo, "hi": hi})
    return out


def main():
    strategy(__doc__)
    rows = load_rows()
    print(f"Snapshots loaded: {len(rows):,}\n")

    # ---------------------------------------------------------------- calibration
    print("=" * 72)
    print("CALIBRATION AT THE 8-MINUTE MARK (all price bands)")
    print("=" * 72)
    print(f"{'band':>12} {'n':>7} {'avg price':>10} {'actual YES':>11} "
          f"{'diff':>8} {'95% CI on actual':>22}")
    for c in calibration(rows):
        b = c["band"]
        print(f"{b*10:>4}-{b*10+10:<3}c {c['n']:>7,} {c['price']:>10.4f} {c['actual']:>11.4f} "
              f"{c['diff']:>+8.4f} {f'[{c["lo"]:.4f}, {c["hi"]:.4f}]':>22}")

    # ------------------------------------------------------------ the 70c stategy
    print()
    print("=" * 72)
    print("THE STRATEGY: buy YES at 65-75c, 8 minutes in, hold to settlement")
    print("=" * 72)

    sel = [r for r in rows if 0.65 <= r["price"] <= 0.75]
    n = len(sel)
    k = sum(r["yes"] for r in sel)
    avg_p = sum(r["price"] for r in sel) / n
    win = k / n
    lo, hi = wilson(k, n)

    print(f"Trades in band          : {n:,}")
    print(f"Average entry price     : {avg_p:.4f}")
    print(f"Actual YES rate         : {win:.4f}  ({k:,}/{n:,})")
    print(f"95% CI on YES rate      : [{lo:.4f}, {hi:.4f}]")
    print(f"Break-even needs        : {avg_p:.4f}")
    print(f"Gross edge per contract : {win-avg_p:+.4f}  ({(win-avg_p)*100:+.2f} cents)")
    gross_per_dollar = (win - avg_p) / avg_p
    print(f"Gross EV per $1 staked  : {gross_per_dollar:+.4f}  ({gross_per_dollar*100:+.2f}%)")

    verdict = ("EDGE (CI clears break-even)" if lo > avg_p
               else "NO PROVEN EDGE (CI straddles break-even)" if hi > avg_p
               else "NEGATIVE EDGE")
    print(f"Statistical verdict     : {verdict}")

    # ------------------------------------------------------------------ with fees
    print()
    print("-" * 72)
    print("NET EV AFTER FEES   fee/contract = M * 0.07 * P * (1-P), maker = 25% of taker")
    print("-" * 72)
    print(f"{'multiplier M':>13} {'role':>7} {'fee/contract':>14} "
          f"{'net/contract':>14} {'net per $1':>12}")

    for M in (1.0, 1.5, 2.0, 3.0):
        for role, mult in (("taker", 1.0), ("maker", 0.25)):
            fee = M * 0.07 * avg_p * (1 - avg_p) * mult
            net = (win - avg_p) - fee
            print(f"{M:>13.1f} {role:>7} {fee:>14.4f} {net:>+14.4f} "
                  f"{net/avg_p*100:>11.2f}%")

    # fee level at which the gross edge is exactly eaten (taker)
    break_M = (win - avg_p) / (0.07 * avg_p * (1 - avg_p))
    print(f"\nEdge is fully eaten at taker multiplier M = {break_M:.2f} "
          f"(maker: M = {break_M*4:.2f})")

    # ---------------------------------------------------------------- by series
    print()
    print("-" * 72)
    print("BY SERIES (65-75c band)")
    print("-" * 72)
    print(f"{'series':>16} {'n':>6} {'avg price':>10} {'actual':>8} {'diff':>8} "
          f"{'95% CI':>22}")
    by = defaultdict(list)
    for r in sel:
        by[r["series"]].append(r)
    for s, g in sorted(by.items(), key=lambda x: -len(x[1])):
        nn = len(g)
        kk = sum(x["yes"] for x in g)
        ap = sum(x["price"] for x in g) / nn
        ac = kk / nn
        l, h = wilson(kk, nn)
        print(f"{s:>16} {nn:>6,} {ap:>10.4f} {ac:>8.4f} {ac-ap:>+8.4f} "
              f"{f'[{l:.3f}, {h:.3f}]':>22}")


if __name__ == "__main__":
    main()
