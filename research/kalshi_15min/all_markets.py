"""Every 15-minute market, one analysis: does the edge hold outside the original 16, and how do
the groups move together?

Data: every 15-minute market in every group since Dec 10, 2025 (history.py): crypto from Dec 10, metals and
energy as they launched, Coin Race since Aug 20, FX since Sep 23.

Strategy: the same rule as everywhere else - at the end of the entry minute the favourite is the side
with the higher ask; bet $10 when that ask is 90-99.9c; realistic fills (+0.4c a contract, the
live-vs-candle gap) and the taker fee, rounded up per order; held to settlement.

  1. Bias check per group: how often favourites won vs what they cost, by price bin.
  2. The 90c+ rule per group at minutes 8 and 5: win rate, profit per bet with a 95% range
     clustered by window, halves of the sample, worst window.
  3. Co-losses: when one bet loses, how often another in the same window does, by group pair.
  4. Group caps on every window: no cap, max 1 crypto,
     max 1 per group, and crypto + Coin Race as one group.

Writes all_markets.json.

    python all_markets.py
"""
import json
import math
from collections import defaultdict
from datetime import datetime
from statistics import NormalDist

from fetch_all15 import group_of
from minutes import clustered, fee, load
import os
import history
from history import strategy

SLIP = 0.004
LO, HI = 0.90, 0.9991
GROUPS = ["crypto", "coin race", "metals", "energy", "fx", "stock index", "rates"]
ELIGIBLE = {"crypto", "metals", "energy"}  # groups where the favourite-longshot bias holds (section 2)
Z = NormalDist().inv_cdf(0.975)


def bets_for(fav, minute):
    out = []
    for t, series, ask, won in fav[minute]:
        if LO <= ask < HI:
            price = min(ask + SLIP, 0.999)
            c = 10 / price
            out.append({"t": t, "series": series, "group": group_of(series, "Crypto" if series in CRYPTO_SERIES else ""),
                        "ask": ask, "won": won, "pnl": (c if won else 0) - 10 - fee(c, price, series, 1.0),
                        "need": (10 + fee(c, price, series, 1.0)) / c})
    return out


CRYPTO_SERIES = {"KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M", "KXHYPE15M", "KXNEAR15M", "KXDOGE15M", "KXZEC15M"}


def summary(bs):
    if not bs:
        return None
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b["pnl"] * 100)  # cents per $10 bet
    mu, lo, hi = clustered(list(by_w.values()))
    ws = sorted(by_w)
    mid = ws[len(ws) // 2]
    half = lambda cond: clustered([v for w, v in by_w.items() if cond(w)])[0]
    days = len({b["t"][:10] for b in bs})
    return {"n": len(bs), "days": days, "perDay": len(bs) / days, "win": sum(b["won"] for b in bs) / len(bs),
            "need": sum(b["need"] for b in bs) / len(bs), "mu": mu, "lo": lo, "hi": hi,
            "h1": half(lambda w: w < mid), "h2": half(lambda w: w >= mid),
            "total": sum(b["pnl"] for b in bs), "worstWindow": min(sum(v) for v in by_w.values()) / 100,
            "first": ws[0], "last": ws[-1]}


def calibration(fav, minute, group):
    bins = defaultdict(lambda: [0, 0, 0.0])
    for t, series, ask, won in fav[minute]:
        if group_of(series, "Crypto" if series in CRYPTO_SERIES else "") != group or not 0.5 <= ask < 1:
            continue
        b = bins[min(int(ask * 10), 9)]
        b[0] += 1
        b[1] += won
        b[2] += ask
    return [{"bin": f"{k * 10}–{k * 10 + 10}", "n": v[0], "priced": v[2] / v[0], "won": v[1] / v[0]}
            for k, v in sorted(bins.items()) if v[0] >= 30]


def co_losses(bs):
    out = {}
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b)
    base = {g: sum(not b["won"] for b in bs if b["group"] == g) / max(1, sum(b["group"] == g for b in bs)) for g in GROUPS}
    for a in GROUPS:
        for c in GROUPS:
            pairs = hits = 0
            for xs in by_w.values():
                for x in xs:
                    if x["group"] != a or x["won"]:
                        continue
                    for y in xs:
                        if y is not x and y["group"] == c:
                            pairs += 1
                            hits += not y["won"]
            if pairs >= 20 and base[c]:
                out[f"{a}|{c}"] = {"p": hits / pairs, "base": base[c], "lift": hits / pairs / base[c], "n": pairs}
    return out


def rule(bs, cap_groups, one_of=None):
    """Replay with at most one bet a window in each capped group (the highest-priced favourite).
    one_of merges groups that count as one for the cap."""
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b)
    merge = lambda g: "crypto-driven" if one_of and g in one_of else g
    windows = sorted(by_w)
    pnl_w, n = {}, 0
    for w in windows:
        taken, chosen = set(), []
        for b in sorted(by_w[w], key=lambda b: -b["ask"]):
            g = merge(b["group"])
            if g in cap_groups or (one_of and g == "crypto-driven"):
                if g in taken:
                    continue
                taken.add(g)
            chosen.append(b)
        pnl_w[w] = sum(b["pnl"] for b in chosen)
        n += len(chosen)
    bal = peak = 240.0
    dd, broke = 0.0, None
    for w in windows:
        bal += pnl_w[w]
        peak = max(peak, bal)
        dd = min(1.0, max(dd, 1 - bal / peak))
        if bal < 10 and broke is None:
            broke = w
    tt = [datetime.fromisoformat(w.replace("Z", "+00:00")).timestamp() for w in windows]
    worst12, j, acc = 0.0, 0, 0.0
    for i in range(len(windows)):
        while j < len(windows) and tt[j] < tt[i] + 43200:
            acc += pnl_w[windows[j]]
            j += 1
        worst12 = min(worst12, acc)
        acc -= pnl_w[windows[i]]
    mid = windows[len(windows) // 2]
    total = sum(pnl_w.values())
    return {"n": n, "total": total, "perBet": total / n * 100, "worstWindow": min(pnl_w.values()), "worst12h": worst12,
            "maxDrop": dd, "broke": broke, "h1": sum(v for w, v in pnl_w.items() if w < mid), "h2": sum(v for w, v in pnl_w.items() if w >= mid)}


def main():
    strategy(__doc__)
    parts = [load(p) for p in history.FILES if os.path.exists(p)]
    fav = {k: [b for part in parts for b in part[k]] for k in parts[0]}
    out = {"slip": SLIP, "groups": {}, "calibration": {}, "rules": {}}

    print("1. BIAS CHECK, minute 8: favourites' price vs how often they won")
    for g in GROUPS:
        cal = calibration(fav, 8, g)
        if cal:
            out["calibration"][g] = cal
            print(f"   {g:<10} " + "  ".join(f"{c['bin']}: {c['priced']:.1%}->{c['won']:.1%}" for c in cal[-3:]))

    print("\n2. THE 90c+ RULE BY GROUP ($10 a bet, realistic fills)")
    for minute in (8, 5):
        bs = bets_for(fav, minute)
        for g in GROUPS:
            s = summary([b for b in bs if b["group"] == g])
            if s:
                out["groups"].setdefault(g, {})[f"m{minute}"] = s
                c = lambda v: "  n/a" if v is None else f"{v:+5.1f}"  # too few bets for a clustered range
                print(f"   m{minute} {g:<10} {s['n']:6d} bets / {s['days']:2d} days  win {s['win']:.2%} need {s['need']:.2%}"
                      f"  per bet {c(s['mu'])}c ({c(s['lo'])} to {c(s['hi'])})  halves {c(s['h1'])}/{c(s['h2'])}"
                      f"  worst window {s['worstWindow']:+7.2f}")

    overlap = bets_for(fav, 8)
    print("\n3. CO-LOSSES, minute 8, every window (one loss -> another loss in the same window)")
    out["coLosses"] = co_losses(overlap)
    for k, v in out["coLosses"].items():
        a, c = k.split("|")
        print(f"   {a:>9} lost -> {c:<9} loses {v['p']:5.1%} (normal {v['base']:.1%}, {v['lift']:4.1f}x, n={v['n']})")

    print("\n4. GROUP CAPS, minute 8, every window, everything that traded ($10 a bet, realistic fills)")
    rules = [("all", "every market, no cap", set(), None),
             ("orig16", "original 16 only, no cap", None, None),
             ("max1crypto", "max 1 crypto a window", {"crypto"}, None),
             ("max1group", "max 1 per group a window", {"crypto", "coin race", "metals", "energy", "fx"}, None),
             ("max1cryptodriven", "crypto + Coin Race count as one", {"metals", "energy", "fx"}, {"crypto", "coin race"}),
             ("elig_max1crypto", "edge groups only, max 1 crypto", {"crypto"}, "eligible"),
             ("elig_max1group", "edge groups only, max 1 per group", {"crypto", "metals", "energy"}, "eligible")]
    for key, label, caps, one_of in rules:
        if one_of == "eligible":
            bs, one_of = [b for b in overlap if b["group"] in ELIGIBLE], None
        else:
            bs = [b for b in overlap if b["group"] != "coin race"] if caps is None else overlap
        r = rule(bs, caps or set(), one_of)
        out["rules"][key] = {"label": label, **r}
        print(f"   {label:<34} {r['n']:6d} bets {r['total']:+8.2f}  per bet {r['perBet']:+5.1f}c  halves {r['h1']:+7.2f}/{r['h2']:+7.2f}"
              f"  worst window {r['worstWindow']:+7.2f}  worst 12h {r['worst12h']:+8.2f}  max drop {r['maxDrop']:.0%}"
              + (f"  BROKE {r['broke'][:10]}" if r["broke"] else ""))

    print("\n5. COIN RACE THE OTHER WAY: buy the cheaper side at minute 8 ($10 a bet, realistic fills)")
    import csv
    under = defaultdict(list)
    if True:
        for r in history.each(None):
            if r["series"] != "KXCRYPTOLEAD15M" or r["a8"] == "" or r["b8"] == "":
                continue
            a, b, yes = float(r["a8"]), float(r["b8"]), r["resolved_yes"] == "1"
            price, won = (a, yes) if a < 1 - b else (round(1 - b, 4), not yes)  # the cheaper side's ask
            if not 0.01 <= price < 0.5:
                continue
            p = min(price + SLIP, 0.999)
            c = 10 / p
            under[min(int(price * 10), 4)].append((c if won else 0) - 10 - fee(c, p, "KXCRYPTOLEAD15M", 1.0))
    out["coinRaceUnderdog"] = []
    for k in sorted(under):
        xs = under[k]
        mu = sum(xs) / len(xs) * 100
        se = (sum((x * 100 - mu) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 / len(xs) ** 0.5
        out["coinRaceUnderdog"].append({"bin": f"{k * 10}–{k * 10 + 10}", "n": len(xs), "mu": mu, "lo": mu - Z * se, "hi": mu + Z * se})
        print(f"   underdog at {k * 10:2d}–{k * 10 + 10:2d}c  {len(xs):5d} bets  per $10 bet {mu:+6.1f}c ({mu - Z * se:+6.1f} to {mu + Z * se:+6.1f})")

    print("\n6. WHY COIN RACE AND FX LOSE: spreads at minute 8, and 90%+ favourites priced at the mid instead of the ask")
    spread = defaultdict(lambda: {"n": 0, "sum": 0.0, "wide": 0, "fav": 0, "priced": 0.0, "won": 0})
    if True:
        if True:
            for r in history.each(None):
                if r["a8"] == "" or r["b8"] == "":
                    continue
                a, b = float(r["a8"]), float(r["b8"])
                s = spread[group_of(r["series"], "Crypto" if r["series"] in CRYPTO_SERIES else "")]
                s["n"] += 1
                s["sum"] += a - b
                s["wide"] += a - b >= 0.05
                mid = (a + b) / 2
                fav, won = (mid, r["resolved_yes"] == "1") if mid >= 0.5 else (1 - mid, r["resolved_yes"] != "1")
                if fav >= 0.9:
                    s["fav"] += 1
                    s["priced"] += fav
                    s["won"] += won
    out["spreads"] = {}
    for g in GROUPS:
        s = spread.get(g)
        if not s:
            continue
        out["spreads"][g] = {"n": s["n"], "spread": s["sum"] / s["n"], "wide": s["wide"] / s["n"], "favN": s["fav"],
                             "midPriced": s["priced"] / s["fav"], "won": s["won"] / s["fav"]}
        print(f"   {g:<10} {s['n']:6d} markets  average spread {s['sum'] / s['n'] * 100:4.1f}c  5c+ in {s['wide'] / s['n']:5.1%}"
              f"  | 90%+ favourites at the mid: priced {s['priced'] / s['fav']:.1%}, won {s['won'] / s['fav']:.1%}")

    with open("all_markets.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
