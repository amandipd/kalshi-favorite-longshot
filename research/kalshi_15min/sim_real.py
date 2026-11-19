"""Heavy-favourite strategy ($240, $10 per trade) filled at the real ask, every market since Jul 18 (snapshots_all.csv, from history.py).

Strategy: at minute 8, buy the favourite of every crypto, metals and energy market for $10 when it
costs 90-99.9c, paying the real ask rather than the last trade, taker fee rounded up to the cent, and
hold it to settlement. V1 picks the bets by their last trade, V2 by the ask itself.

Favoured-side ask: YES ask for YES, (1 - YES bid) for NO.
  V1: same bets as the last-trade simulation, filled at the real ask.
  V2: bet chosen by the ask itself (what a live trader sees) in [0.90, 0.999].
"""
import csv
import math
from collections import defaultdict
from datetime import datetime
from statistics import mean, median, stdev
from history import strategy

strategy(__doc__)

CRYPTO = {"KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M",
          "KXHYPE15M", "KXNEAR15M", "KXDOGE15M", "KXZEC15M"}
START, STAKE = 240.0, 10.0
LO, HI = 0.90, 0.999

rows = []
with open("snapshots_all.csv") as fh:
    for r in csv.DictReader(fh):
        f = lambda k: float(r[k]) if r[k] != "" else None
        rows.append({"t": datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")),
                     "series": r["series"], "last": float(r["price_8min"]),
                     "bid": f("yes_bid"), "ask": f("yes_ask"),
                     "yes": r["resolved_yes"] == "1"})


def v1(r):
    """Selected on last trade, filled at the favoured side's ask."""
    if r["last"] >= 0.5:
        fav, won, fill = r["last"], r["yes"], r["ask"]
    else:
        fav, won = 1 - r["last"], not r["yes"]
        fill = None if r["bid"] is None else 1 - r["bid"]
    if not (LO <= fav <= HI and fav < 1.0):
        return None
    return ("ok", fill, won, fav)


def v2(r):
    """Selected and filled on the ask."""
    ay = r["ask"]
    an = None if r["bid"] is None else 1 - r["bid"]
    yes_ok = ay is not None and LO <= ay <= HI
    no_ok = an is not None and LO <= an <= HI
    if yes_ok == no_ok:
        return None
    return ("ok", ay, r["yes"], ay) if yes_ok else ("ok", an, not r["yes"], an)


def bets(rule):
    out = defaultdict(list)
    unfillable = 0
    for r in rows:
        b = rule(r)
        if b is None:
            continue
        _, fill, won, ref = b
        if fill is None or fill >= 1.0 or fill <= 0:
            unfillable += 1
            continue
        out[r["t"]].append((r["series"], fill, won, ref))
    return out, unfillable


def simulate(windows, m_crypto=1.0):
    b, peak, max_dd, low = START, START, 0.0, START
    n = wins = 0
    fees = 0.0
    per_window, per_day = [], defaultdict(float)
    order = sorted(windows)
    mid = order[len(order) // 2]
    halves = [0.0, 0.0]
    broke = None
    for t in order:
        avail, pnl, k = b, 0.0, 0
        for s, fill, won, _ in windows[t]:
            c = STAKE / fill
            m = m_crypto if s in CRYPTO else 1.0
            fee = math.ceil(m * 0.07 * c * fill * (1 - fill) * 100 - 1e-9) / 100
            if avail < STAKE + fee:
                continue
            avail -= STAKE + fee
            fees += fee
            pnl += (c if won else 0.0) - STAKE - fee
            n += 1
            k += 1
            wins += won
        if k:
            b += pnl
            per_window.append((pnl, k))
            per_day[t.date()] += pnl
            halves[t >= mid] += pnl
            peak = max(peak, b)
            low = min(low, b)
            max_dd = max(max_dd, 1 - b / peak)
        if b < STAKE:
            broke = t
            break
    mu = sum(x for x, _ in per_window) / n
    resid = [x - mu * k for x, k in per_window]
    se = stdev(resid) / ((n / len(per_window)) * math.sqrt(len(per_window)))
    return {"final": b, "n": n, "win": wins / n, "fees": fees, "dd": max_dd, "low": low,
            "broke": broke, "mu": mu, "lo": mu - 1.96 * se, "hi": mu + 1.96 * se,
            "halves": halves, "losing_days": sum(v < 0 for v in per_day.values()),
            "days": len(per_day), "worst_window": min(x for x, _ in per_window)}


# --------------------------------------------------------------- spread check
w1, unf1 = bets(v1)
cost = [fill - ref for ws in w1.values() for _, fill, _, ref in ws]
print("HOW MUCH WORSE IS THE REAL ASK THAN THE LAST TRADE? (V1 bets)")
print(f"  bets with a fillable ask : {len(cost):,}   (no usable ask: {unf1})")
print(f"  ask minus last trade     : mean {mean(cost)*100:+.2f}c, median {median(cost)*100:+.2f}c")
print(f"  ask <= last trade        : {sum(c <= 1e-9 for c in cost)/len(cost)*100:.1f}%")
print(f"  ask 0-1c above           : {sum(1e-9 < c <= 0.01 + 1e-9 for c in cost)/len(cost)*100:.1f}%")
print(f"  ask more than 1c above   : {sum(c > 0.01 + 1e-9 for c in cost)/len(cost)*100:.1f}%")
print()

w2, unf2 = bets(v2)
print(f"{'variant':<44}{'final $':>10}{'bets':>7}{'win%':>7}{'fees $':>9}{'max DD':>8}"
      f"{'profit/bet':>12}{'95% CI':>20}{'1st half':>10}{'2nd half':>10}{'lose days':>11}"
      f"{'worst 15m':>11}")
for label, ws, m in (("V1 same bets, real ask", w1, 1.0),
                     ("V1 ... crypto fee M=1.5", w1, 1.5),
                     ("V1 ... crypto fee M=2.0", w1, 2.0),
                     ("V2 chosen by ask", w2, 1.0),
                     ("V2 ... crypto fee M=1.5", w2, 1.5),
                     ("V2 ... crypto fee M=2.0", w2, 2.0)):
    r = simulate(ws, m)
    tag = " BROKE" if r["broke"] else ""
    print(f"{label:<44}{r['final']:>10,.2f}{r['n']:>7,}{r['win']*100:>6.1f}%{r['fees']:>9,.2f}"
          f"{r['dd']*100:>7.1f}%{r['mu']*100:>+10.1f}c"
          f"{f'[{r['lo']*100:+.1f}c, {r['hi']*100:+.1f}c]':>20}"
          f"{r['halves'][0]:>+10,.0f}{r['halves'][1]:>+10,.0f}"
          f"{f'{r['losing_days']}/{r['days']}':>11}{r['worst_window']:>+11,.2f}{tag}")
print("\nfor reference: simulate2.py runs the same bets at the last trade price ((a+b) 90c+, $240, $10 per trade)")
