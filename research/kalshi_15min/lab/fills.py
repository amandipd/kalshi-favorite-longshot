"""Unfilled contracts: would a higher limit on the live bot's order have bought more, and were the extra contracts worth it?

The live bot sends one immediate-or-cancel order about 2 s after minute 8 (SEND), limited at the favourite's ask it saw.
Its fills are modelled from Kalshi's trade tape the way liquidity.py and "The live bot · real liquidity" do:
  nothing if the first trade on its side after SEND came within FRESH s and above the limit (the price ran away),
  otherwise min(wanted, max(seen, QUIET)) contracts, seen = contracts others bought on its side at the limit or better
  in the DEPTH s after SEND.
Here the limit is raised by X (capped at 99.9c). Contracts at the old limit or better are charged the old limit (as the
real-liquidity replay does); the extra ones are charged the tape's own prices between the old and new limit, cheapest
first (a quiet book's QUIET contracts where the book was: the old limit, or the first trade's price if it had
already moved). An immediate-or-cancel order takes the book at once, so the
dearer trades count only within W s of the order: 30 s (as the old-limit ones), 10, 5 and 2. Kalshi's fee is charged
exactly (0.07 x C x P x (1 - P), no rounding up to the cent: the bot's fills show Kalshi charges members that way).

Every live-rule bet from Dec 10 to Oct 8 (data/liquidity_tape.jsonl: the trades on the favourite's side, minutes 7:50-10),
at three order sizes: $10, $30 (3% of about $1,000, the bot today) and $100.

    python lab/fills.py
"""
import json
import os
from collections import defaultdict

import numpy as np

import common as C

HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "data", "liquidity_tape.jsonl"))
SEND, DEPTH, FRESH, QUIET = 482, 30, 10, 3
CHASE = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05)
SIZES = (10.0, 30.0, 100.0)
WINDOWS = (30, 10, 5, 2)


def fill(trades, top, want, x, w=DEPTH):
    """(contracts, cost) of an IOC for `want` contracts limited at top + x, from the tape after SEND. Trades at the old
    limit or better count over DEPTH s, as the real-liquidity replay's do; dearer ones only over the first w s."""
    lim = min(top + x, 0.999)
    after = [t for t in trades if t[0] > SEND]
    first = after[0][1] if after and after[0][0] <= SEND + FRESH else None   # where the book was just after the order
    if first is not None and first > lim + 1e-9:
        return 0.0, 0.0
    quiet = max(top, first) if first is not None else top
    pool = sorted((px, c) for dt, px, c in after
                  if px <= lim + 1e-9 and dt <= SEND + (DEPTH if px <= top + 1e-9 else w))
    k = min(want, max(sum(c for _, c in pool), QUIET))
    got = cost = 0.0
    for px, c in pool:
        take = min(c, k - got)
        if take <= 0:
            break
        cost += take * max(px, top)   # at the old limit or better: charged the old limit
        got += take
    if got < k:                       # a quiet book: its QUIET contracts where the book was (the old limit, or the
        cost += (k - got) * quiet     # first trade's dearer price if the price had already moved)
        got = k
    return got, cost


def pnl_of(k, cost, won):
    if not k:
        return 0.0
    p = cost / k
    return (k if won else 0.0) - cost - 0.07 * k * p * (1 - p)


def main():
    d = C.load()
    m, side_yes, top = C.live_rule(d)
    wins = C.won(d, side_yes)
    idx = {str(d["ticker"][i]): int(i) for i in np.flatnonzero(m)}
    per = C.period_of(d["open_ts"])
    acc = defaultdict(lambda: defaultdict(float))     # (size, window, raise) -> totals
    seen = 0
    with open(TAPE, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            i = idx.get(r["t"])
            if i is None:
                continue
            seen += 1
            t, won, half = float(top[i]), bool(wins[i]), "pre" if per[i] == "pre" else "post"
            for s in SIZES:
                want = float(np.floor(s / t + 1e-9))
                for w in WINDOWS:
                    k0, c0 = fill(r["tr"], t, want, 0.0, w)
                    p0 = pnl_of(k0, c0, won)
                    for x in CHASE:
                        k, cost = (k0, c0) if x == 0 else fill(r["tr"], t, want, x, w)
                        p = p0 if x == 0 else pnl_of(k, cost, won)
                        a = acc[(s, w, x)]
                        a["orders"] += 1
                        a["any"] += k > 0
                        a["want"] += want
                        a["got"] += k
                        a["cost"] += cost
                        a["pnl"] += p
                        a[half + "Pnl"] += p
                        a[half + "Cost"] += cost
                        if x and k > k0 + 1e-9:
                            a["xOrders"] += 1
                            a["xN"] += k - k0
                            a["xCost"] += cost - c0
                            a["xPnl"] += p - p0
                            a["xWon"] += (k - k0) if won else 0.0
                            a["x" + half + "Pnl"] += p - p0
                            a["x" + half + "Cost"] += cost - c0
    print(f"{seen} of {len(idx)} live-rule bets have tape\n")
    rows = []
    div = lambda a, b, k=1.0: a / b * k if b else None   # noqa: E731
    for s in SIZES:
        for w in WINDOWS:
            print(f"ORDER ${s:.0f}, dearer trades within {w} s: raise  orders filled  contracts  c/$10   $ pnl"
                  f"  | extra contracts: n, avg price, won, c/$10 (pre | post)")
            for x in CHASE:
                a = acc[(s, w, x)]
                row = {"size": s, "window": w, "raise": x, "orders": a["orders"], "filledAny": div(a["any"], a["orders"]),
                       "filledContracts": div(a["got"], a["want"]), "avgPaid": div(a["cost"], a["got"]),
                       "perTen": div(a["pnl"], a["cost"], 1000), "pnl": round(a["pnl"], 2),
                       "pre": div(a["prePnl"], a["preCost"], 1000), "post": div(a["postPnl"], a["postCost"], 1000)}
                line = (f"   +{x * 100:3.1f}c  {row['filledAny']:6.1%}  {row['filledContracts']:6.1%}  "
                        f"{row['perTen']:+6.2f}  {a['pnl']:+9,.0f}")
                if x:
                    row["extra"] = {"orders": a["xOrders"], "contracts": round(a["xN"], 2), "avgPrice": div(a["xCost"], a["xN"]),
                                    "won": div(a["xWon"], a["xN"]), "perTen": div(a["xPnl"], a["xCost"], 1000),
                                    "pnl": round(a["xPnl"], 2), "pre": div(a["xprePnl"], a["xpreCost"], 1000),
                                    "post": div(a["xpostPnl"], a["xpostCost"], 1000)}
                    q = row["extra"]
                    if q["contracts"]:
                        line += (f"  | {q['contracts']:9,.0f} at {q['avgPrice']:.4f}, won {q['won']:.2%}, {q['perTen']:+5.1f}c"
                                 f" ({q['pre']:+.1f} | {q['post']:+.1f})")
                print(line)
                rows.append(row)
            print()
    with open(os.path.join(HERE, "fills.json"), "w", encoding="utf-8") as fh:
        json.dump({"bets": seen, "send": SEND, "depth": DEPTH, "fresh": FRESH, "quiet": QUIET, "rows": rows}, fh, indent=1)


if __name__ == "__main__":
    main()
