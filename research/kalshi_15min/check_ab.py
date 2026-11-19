"""Robustness checks for the 90c+ / $10-per-trade strategy, every market since Jul 18 (snapshots_all.csv, from history.py).

Strategy: at minute 8 of each window, buy the favourite (YES if its last trade is 50c or more, else NO)
of every crypto, metals and energy market when it costs 90-99.9c: $10 a bet at the last trade price
plus the slippage being tested, taker fee rounded up to the cent, held to settlement.

- Per-bet profit with a 95% CI clustered by 15-minute window (same-window
  bets are correlated, so treating them as independent overstates certainty).
- First half vs second half of the history.
- Worst single window and worst day.
- Higher fee multiplier on the crypto series, whose exact M is unknown.
"""
import csv
import math
from collections import defaultdict
from datetime import datetime
from statistics import mean, stdev
from history import strategy

strategy(__doc__)

CRYPTO = {"KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M",
          "KXHYPE15M", "KXNEAR15M", "KXDOGE15M", "KXZEC15M"}
STAKE = 10.0

windows = defaultdict(list)
with open("snapshots_all.csv") as fh:
    for r in csv.DictReader(fh):
        t = datetime.fromisoformat(r["open_time"].replace("Z", "+00:00"))
        p, y = float(r["price_8min"]), int(r["resolved_yes"])
        fav, won = (p, y == 1) if p >= 0.5 else (1 - p, y == 0)
        if 0.90 <= fav < 1.0:
            windows[t].append((r["series"], fav, won))
order = sorted(windows)
mid = order[len(order) // 2]


def pnl(series, price, won, slip, m_crypto):
    fill = price + slip
    if fill >= 1.0:
        return None
    c = STAKE / fill
    m = m_crypto if series in CRYPTO else 1.0
    fee = math.ceil(m * 0.07 * c * fill * (1 - fill) * 100 - 1e-9) / 100
    return (c if won else 0.0) - STAKE - fee


for label, slip, m in (("B taker fees", 0.0, 1.0),
                       ("C fees + 1c worse fill", 0.01, 1.0),
                       ("C with crypto fee M=1.5", 0.01, 1.5),
                       ("C with crypto fee M=2.0", 0.01, 2.0)):
    per_window, per_day, bets = [], defaultdict(float), []
    halves = [0.0, 0.0]
    for t in order:
        w = [x for x in (pnl(s, p, won, slip, m) for s, p, won in windows[t]) if x is not None]
        if not w:
            continue
        tot = sum(w)
        per_window.append((tot, len(w)))
        per_day[t.date()] += tot
        halves[t >= mid] += tot
        bets.extend(w)
    n_bets = len(bets)
    # ratio estimator: mean profit per bet, SE clustered by window
    mu = sum(x for x, _ in per_window) / n_bets
    resid = [x - mu * k for x, k in per_window]
    kbar = n_bets / len(per_window)
    se = stdev(resid) / (kbar * math.sqrt(len(per_window)))
    print(f"{label}")
    print(f"  profit per $10 bet : {mu:+.4f}  95% CI [{mu-1.96*se:+.4f}, {mu+1.96*se:+.4f}]"
          f"  ({'significant' if mu - 1.96*se > 0 else 'NOT significant'})")
    print(f"  total P&L          : {sum(bets):+,.2f}  (1st half {halves[0]:+,.2f}, "
          f"2nd half {halves[1]:+,.2f})")
    print(f"  worst 15 min       : {min(x for x, _ in per_window):+,.2f}   "
          f"worst day: {min(per_day.values()):+,.2f}   "
          f"losing days: {sum(v < 0 for v in per_day.values())}/{len(per_day)}")
    print()
