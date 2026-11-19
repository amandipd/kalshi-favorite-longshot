"""Where in the 15-minute window is the edge biggest? Every crypto, metals and energy market since Dec 10, 2025.

Strategy: for each entry minute k = 1..15, the favourite is the side with the higher ask at
the end of minute k (YES ask vs 1 - YES bid). Each bet is $10, filled at that
real ask, taker fee rounded up to the cent, held to settlement.

Per minute: the 90c+ strategy (win rate, profit per bet with a 95% range
clustered by window, halves of the history, $240 bankroll) at crypto fee
multipliers 1x/1.5x/2x; a minute x price-bin grid; and an out-of-sample check
that picks the best minute on the first half and scores it on the second.

Run directly to print the tables.
"""
import contextlib
import csv
import math
from collections import defaultdict
from statistics import stdev

import history
from history import strategy

CRYPTO = {"KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M",
          "KXHYPE15M", "KXNEAR15M", "KXDOGE15M", "KXZEC15M"}
STAKE, START = 10.0, 240.0
MINUTES = range(1, 16)
MULTS = (1.0, 1.5, 2.0)
BANDS = [(0.50, 0.60, "50–60"), (0.60, 0.70, "60–70"), (0.70, 0.80, "70–80"),
         (0.80, 0.90, "80–90"), (0.90, 0.9991, "90+")]
Z = 1.96


def load(path=None):
    """Per minute, each market's favourite side: (window, series, fill at ask, won). Every crypto, metals and energy
    market since Dec 10 (history.py), or one minute file's markets."""
    num = lambda x: float(x) if x != "" else None
    fav = {k: [] for k in MINUTES}
    with open(path) if path else contextlib.nullcontext() as fh:
        for r in (csv.DictReader(fh) if path else history.each()):
            yes = r["resolved_yes"] == "1"
            for k in MINUTES:
                a, b = num(r[f"a{k}"]), num(r[f"b{k}"])
                if a is None or b is None or abs(a - (1 - b)) < 1e-9:
                    continue
                fill, won = (a, yes) if a > 1 - b else (1 - b, not yes)
                fav[k].append((r["open_time"], r["series"], fill, won))
    return fav


def fee(contracts, price, series, m):
    k = m if series in CRYPTO else 1.0
    return math.ceil(k * 0.07 * contracts * price * (1 - price) * 100 - 1e-9) / 100


def bets_at(fav, k, lo, hi, m=1.0):
    out = []
    for t, series, fill, won in fav[k]:
        if not (lo <= fill < hi) or fill >= 1.0:
            continue
        c = STAKE / fill
        fe = fee(c, fill, series, m)
        out.append({"t": t, "fill": fill, "won": won, "fee": fe,
                    "pnl": (c if won else 0.0) - STAKE - fe, "need": (STAKE + fe) / c})
    return out


def clustered(groups):
    """Mean per bet with a 95% range clustered by window; None under 30 bets."""
    groups = [g for g in groups if g]
    n = sum(len(g) for g in groups)
    if n < 30 or len(groups) < 2:
        return None, None, None
    mu = sum(sum(g) for g in groups) / n
    resid = [sum(g) - mu * len(g) for g in groups]
    se = stdev(resid) / ((n / len(groups)) * math.sqrt(len(groups)))
    return mu, mu - Z * se, mu + Z * se


def summarise(bs, mid):
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b["pnl"] / STAKE)
    mu, lo, hi = clustered(list(by_w.values()))
    n = len(bs)
    avg = lambda f: sum(f(b) for b in bs) / n if n else None
    return {"n": n, "price": avg(lambda b: b["fill"]), "win": avg(lambda b: b["won"]),
            "need": avg(lambda b: b["need"]), "mu": mu, "lo": lo, "hi": hi,
            "h1": clustered([v for t, v in by_w.items() if t < mid])[0],
            "h2": clustered([v for t, v in by_w.items() if t >= mid])[0]}


def bankroll(bs):
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b)
    bal, peak, dd, worst, broke = START, START, 0.0, 0.0, None
    for t in sorted(by_w):
        avail, pnl = bal, 0.0
        for b in by_w[t]:
            if avail < STAKE + b["fee"]:
                continue
            avail -= STAKE + b["fee"]
            pnl += b["pnl"]
        bal += pnl
        worst = min(worst, pnl)
        peak = max(peak, bal)
        dd = max(dd, 1 - bal / peak)
        if bal < STAKE:
            broke = t
            break
    return {"final": bal, "dd": dd, "worst": worst, "broke": broke}


def analyse(fav):
    """Profit figures are per $1 staked (x10 for a $10 bet)."""
    windows = sorted({t for k in MINUTES for t, *_ in fav[k]})
    mid = windows[len(windows) // 2]
    by_mult = {}
    for m in MULTS:
        by_mult[f"{m:.1f}"] = []
        for k in MINUTES:
            bs = bets_at(fav, k, 0.90, 0.9991, m)
            by_mult[f"{m:.1f}"].append({"k": k, **summarise(bs, mid), **bankroll(bs)})
    grid = {f"{k}|{lbl}": summarise(bets_at(fav, k, lo, hi), mid) for k in MINUTES for lo, hi, lbl in BANDS}
    base = by_mult["1.0"]
    best_k = max((x["h1"], x["k"]) for x in base if x["h1"] is not None)[1]
    return {"bands": [lbl for *_, lbl in BANDS], "byMult": by_mult, "grid": grid,
            "oos": {"split": mid, "bestK": best_k, "best": base[best_k - 1], "m8": base[7]}}


def report(res):
    c = lambda v: "   —   " if v is None else f"{v*1000:+6.1f}¢"
    pct = lambda v: "  —  " if v is None else f"{v*100:5.1f}%"
    print("90¢+ FAVORITES, $10 per bet at the real ask, taker fee (crypto multiplier 1×)")
    print(f"{'min':>3} {'bets':>6} {'avg ask':>8} {'won':>6} {'needed':>7} {'profit/bet':>11} {'95% range':>19}"
          f" {'1st half':>9} {'2nd half':>9} {'$240 ->':>10} {'worst drop':>10}")
    for s in res["byMult"]["1.0"]:
        rng = "" if s["lo"] is None else f"{s['lo']*1000:+.1f} to {s['hi']*1000:+.1f}¢"
        flag = " *" if s["lo"] is not None and s["lo"] > 0 else "  "
        end = "broke" if s["broke"] else f"${s['final']:,.0f}"
        print(f"{s['k']:>3} {s['n']:>6,} {s['price']*100:>7.1f}¢ {pct(s['win'])} {pct(s['need']):>7} {c(s['mu']):>11}{flag}"
              f"{rng:>18} {c(s['h1']):>9} {c(s['h2']):>9} {end:>10} {s['dd']*100:>9.0f}%")
    print("  * = 95% range above zero\n")
    print("PROFIT PER $10 BET BY ENTRY MINUTE × FAVORITE'S PRICE")
    print(f"{'min':>3} " + "".join(f"{lbl:>11}" for lbl in res["bands"]))
    for k in MINUTES:
        cells = []
        for lbl in res["bands"]:
            s = res["grid"][f"{k}|{lbl}"]
            mark = "*" if s["lo"] is not None and s["lo"] > 0 else ("-" if s["hi"] is not None and s["hi"] < 0 else " ")
            cells.append(f"{c(s['mu'])}{mark}" if s["mu"] is not None else f"{'n/a':>8} ")
        print(f"{k:>3} " + "".join(f"{x:>11}" for x in cells))
    o = res["oos"]
    print(f"\nFAIR TEST: best minute on the first half = {o['bestK']} ({c(o['best']['h1']).strip()}),"
          f" second half {c(o['best']['h2']).strip()}; minute 8: {c(o['m8']['h1']).strip()} -> {c(o['m8']['h2']).strip()}")


if __name__ == "__main__":
    strategy(__doc__)
    report(analyse(load()))
