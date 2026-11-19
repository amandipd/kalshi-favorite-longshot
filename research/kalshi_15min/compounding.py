"""
Is the ~3% edge per trade or per day, and what does it compound to? (every market since Jul 18 (snapshots_all.csv, from history.py))

Strategy: the 70c strategy - at minute 8, buy YES in every crypto, metals and energy market whose
last trade is 65-75c, and hold it to settlement. This measures how often those bets come up, what
each returns, the Kelly bet size, and whether bets in the same window are independent.

Also tests the assumption the whole 'split across N markets' idea rests on:
are simultaneous trades across different series actually independent?
"""
import csv
import math
from collections import defaultdict
from history import strategy

strategy(__doc__)

rows = []
with open("snapshots_all.csv") as fh:
    for r in csv.DictReader(fh):
        rows.append({
            "series": r["series"],
            "open": r["open_time"],
            "price": float(r["price_8min"]),
            "yes": int(r["resolved_yes"]),
        })

sel = [r for r in rows if 0.65 <= r["price"] <= 0.75]
n, k = len(sel), sum(r["yes"] for r in sel)
P = sum(r["price"] for r in sel) / n
W = k / n

# ---------------------------------------------------------- opportunity rate
windows = sorted({r["open"] for r in rows})
span_days = len(windows) / 96.0          # 96 fifteen-minute windows per day
per_day = n / span_days
print(f"Sample span              : {span_days:.1f} days ({len(windows):,} distinct windows)")
print(f"Qualifying trades        : {n:,}  ->  {per_day:.1f} per day")
print(f"                           {n/len(windows):.2f} simultaneous opportunities per window")
print()

edge_gross = W - P
fee = 0.07 * P * (1 - P)                  # taker, standard multiplier M=1.0
edge_net = edge_gross - fee
r_gross = edge_gross / P
r_net = edge_net / P
print(f"Per-trade return (gross) : {r_gross*100:+.2f}%")
print(f"Per-trade return (net)   : {r_net*100:+.2f}%")
print()

# ------------------------------------------------------- naive compounding
print("NAIVE COMPOUNDING (full bankroll every cycle, 96 cycles/day):")
for label, r in (("gross", r_gross), ("net of fees", r_net)):
    daily = (1 + r) ** 96 - 1
    log10_yr = 96 * 365 * math.log10(1 + r)
    print(f"  {label:>12}: {daily*100:,.0f}% per day"
          f"   -> 10^{log10_yr:,.0f}x per year")
print("  ^ obviously impossible. The assumptions below are what break.")
print()

# ------------------------------------------------------------------- Kelly
def kelly(win, price):
    b = (1 - price) / price               # net odds
    return (b * win - (1 - win)) / b

def growth(win, price, f):
    b = (1 - price) / price
    return win * math.log(1 + b * f) + (1 - win) * math.log(1 - f)

P_eff = P + fee                            # fee folded into effective cost
f_g, f_n = kelly(W, P), kelly(W, P_eff)
print(f"Kelly fraction (gross)   : {f_g*100:.2f}% of bankroll per bet")
print(f"Kelly fraction (net)     : {f_n*100:.2f}% of bankroll per bet")
print()

print("GROWTH AT KELLY SIZING (net of fees), per day:")
for name, frac in (("full Kelly", f_n), ("half Kelly", f_n / 2), ("quarter Kelly", f_n / 4)):
    g = growth(W, P_eff, frac)
    print(f"  {name:>14} (f={frac*100:5.2f}%): {(math.exp(g*per_day)-1)*100:+7.2f}% per day")
print("  (still assumes every trade is an independent bet - tested next)")
print()

# ------------------------------------------------- are the series independent?
by_window = defaultdict(list)
for r in sel:
    by_window[r["open"]].append(r["yes"])

agree = total = 0
for outcomes in by_window.values():
    m = len(outcomes)
    if m < 2:
        continue
    for i in range(m):
        for j in range(i + 1, m):
            total += 1
            agree += (outcomes[i] == outcomes[j])

obs = agree / total
exp = W**2 + (1 - W)**2                   # expected agreement if independent
# phi / intraclass correlation implied by the excess agreement
rho = (obs - exp) / (1 - exp)
print("INDEPENDENCE CHECK (pairs of trades in the SAME 15-minute window):")
print(f"  pairs compared         : {total:,}")
print(f"  agreement if independent: {exp*100:.2f}%")
print(f"  agreement observed      : {obs*100:.2f}%")
print(f"  implied correlation     : {rho:+.3f}")
eff = 1 / (1 + rho * (n / len(by_window) - 1)) if rho > 0 else 1.0
print(f"  -> {n/len(by_window):.2f} concurrent bets behave like "
      f"{(n/len(by_window))*eff:.2f} independent ones")
