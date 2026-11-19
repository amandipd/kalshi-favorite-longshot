"""Sell the other coins when one turns (PREREG.md, fixed 28 Oct 2026 22:37 UTC before any result).

For each window where the live bot's rule holds 2+ crypto favourites, at the first minute m (9-14) where at least K
held coins' own bids are at or below T, sell every other held coin on the same side whose bid is still above T, at
its minute-m bid less the taker fee. Score = sale proceeds minus what holding paid. Positive = selling beat holding.

    python contagion_exit.py      -> prints every cell, writes contagion_exit.json
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kalshi_15min", "lab"))
import common as C  # noqa: E402

MAIN = [(1, 0.70), (1, 0.50), (2, 0.70), (2, 0.50)]
EXTRA = [(1, 0.80), (2, 0.80), (1, 0.30), (2, 0.30)]
MINUTES = range(9, 15)


def held_bets():
    """The rule's crypto bets: window, side, contracts, won, and the own bid at the end of minutes 9-14."""
    d = C.load(("crypto",))
    m, side_yes, top = C.live_rule(d, lo=0.92)
    idx = np.flatnonzero(m)
    price = np.minimum(top[idx] + C.SLIP, 0.999)
    c = np.floor(10.0 / price + 1e-9)
    bids = np.stack([C.own(d, side_yes, k)[0][idx] for k in MINUTES], axis=1)
    return {"t": d["open_ts"][idx], "yes": side_yes[idx], "c": c, "price": price,
            "won": C.won(d, side_yes)[idx], "bids": bids, "series": d["series"][idx]}


def events(B, K, T):
    """One row per sold position: (window, minute, contracts, bid, won, delta $)."""
    out = []
    order = np.argsort(B["t"], kind="stable")
    t = B["t"][order]
    starts = np.flatnonzero(np.r_[True, t[1:] != t[:-1]])
    ends = np.r_[starts[1:], len(t)]
    for a, b in zip(starts, ends):
        if b - a < 2:
            continue
        ix = order[a:b]
        for j, minute in enumerate(MINUTES):
            bid = B["bids"][ix, j]
            turned = bid <= T + 1e-9            # NaN compares False: a missing quote is not a turn
            if turned.sum() < K:
                continue
            sides = set(B["yes"][ix][turned].tolist())
            sell = ~turned & np.isin(B["yes"][ix], list(sides)) & ~np.isnan(bid)
            for i in ix[sell]:
                p = float(B["bids"][i, j])
                c = float(B["c"][i])
                proceeds = p * c - float(C.fee(np.array([c]), np.array([p]))[0])
                hold = c if B["won"][i] else 0.0
                out.append((float(B["t"][i]), minute, c, p, bool(B["won"][i]), proceeds - hold))
            break
    return out


def score(rows):
    """Total $, t clustered on the window, events, positions; plus the halves and the drop-best-day check."""
    if not rows:
        return {"windows": 0, "positions": 0, "total": 0.0, "t": None}
    w = {}
    for t, *_, delta in rows:
        w[t] = w.get(t, 0.0) + delta
    v = np.array(list(w.values()))
    n = len(v)
    t_stat = float(v.mean() / (v.std(ddof=1) / math.sqrt(n))) if n > 1 and v.std(ddof=1) > 0 else None
    return {"windows": n, "positions": len(rows), "total": round(float(v.sum()), 2),
            "perWindow": round(float(v.mean()), 3), "t": t_stat,
            "soldBid": round(float(np.mean([r[3] for r in rows])), 4),
            "soldWon": round(float(np.mean([r[4] for r in rows])), 4)}


def by_day(rows):
    days = {}
    for r in rows:
        k = datetime.fromtimestamp(r[0], timezone.utc).strftime("%Y-%m-%d")
        days[k] = days.get(k, 0.0) + r[5]
    return days


def cell(B, K, T, mid, post):
    rows = events(B, K, T)
    out = {"K": K, "T": T, "all": score(rows),
           "older": score([r for r in rows if r[0] < mid]), "newer": score([r for r in rows if r[0] >= mid]),
           "julyOn": score([r for r in rows if r[0] >= post])}
    days = by_day(rows)
    if days:
        best = max(days, key=days.get)
        out["bestDay"] = {"day": best, "total": round(days[best], 2)}
        out["withoutBestDay"] = score([r for r in rows
                                       if datetime.fromtimestamp(r[0], timezone.utc).strftime("%Y-%m-%d") != best])
    return out


def verdict(c):
    a = c["all"]
    if not a["windows"] or a["total"] <= 0 or a["t"] is None or a["t"] < 1:
        return "fail"
    ok = (a["t"] > 2 and c["older"]["total"] > 0 and c["newer"]["total"] > 0
          and c.get("withoutBestDay", {}).get("total", 0) > 0)
    return "pass" if ok else "in between"


def main():
    B = held_bets()
    lo, hi = B["t"].min(), B["t"].max()
    d0 = datetime.fromtimestamp(lo, timezone.utc).date()
    d1 = datetime.fromtimestamp(hi, timezone.utc).date()
    mid = datetime.combine(d0 + (d1 - d0) / 2, datetime.min.time(), timezone.utc).timestamp()
    post = C.PERIODS[1][2]
    win = np.unique(B["t"], return_counts=True)[1]
    print(f"crypto bets {len(B['t'])}, windows {len(win)}, with 2+ bets {(win >= 2).sum()}; {d0} .. {d1}; "
          f"halves split at {datetime.fromtimestamp(mid, timezone.utc).date()}")
    res = {"main": [], "extra": []}
    for key, cells in (("main", MAIN), ("extra", EXTRA)):
        for K, T in cells:
            c = cell(B, K, T, mid, post)
            c["verdict"] = verdict(c) if key == "main" else None
            res[key].append(c)
            a = c["all"]
            ts = f"{a['t']:+.2f}" if a["t"] is not None else "n/a"
            print(f"{key:<5} K={K} T={T:.2f}: windows {a['windows']:>4} sold {a['positions']:>4}  sell-minus-hold "
                  f"${a['total']:>+9.2f}  t {ts}  older ${c['older']['total']:+.2f}  newer ${c['newer']['total']:+.2f}  "
                  f"w/o best day ${c.get('withoutBestDay', {}).get('total', 0):+.2f}  Jul18+ ${c['julyOn']['total']:+.2f}  "
                  f"sold at avg bid {a.get('soldBid', 0):.3f}, won {a.get('soldWon', 0):.1%}  -> {c['verdict']}")
    base_won = B["won"].astype(float) * B["c"] - B["c"] * B["price"] - C.fee(B["c"], B["price"])
    res["ruleProfit"] = round(float(base_won.sum()), 2)
    res["halfSplit"] = str(datetime.fromtimestamp(mid, timezone.utc).date())
    print(f"the rule's own crypto profit over the same bets at $10: ${res['ruleProfit']:+.2f}")
    with open(os.path.join(HERE, "contagion_exit.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)


if __name__ == "__main__":
    main()
