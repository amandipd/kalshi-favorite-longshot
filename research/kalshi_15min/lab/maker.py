"""Maker instead of taker: rest a limit order for the favourite at minute 8 instead of buying its ask.

The live rule picks the market (minute 8, favourite's ask 90-99.9c, skip 2c+ spreads and late favourites, Fed
blackouts). Instead of paying the ask (plus the 0.4c live-like slip and the taker fee), it rests a buy for the
favourite at a limit L and holds whatever fills to settlement. L is the favourite's own bid at minute 8 ("join"),
a cent over it ("improve", only if that's still under the ask), or a tenth of a cent under the ask ("tick").

The minute files only hold each minute's closing quotes, so fills are judged from them:
  conservative  filled the first later minute (9-14) whose closing ask on the favourite's side is at or under L:
                someone offered at L or less, which would have crossed the resting order
  optimistic    also filled when a later closing bid on its side is under L (the level was taken out, or just
                pulled) - an upper bound
Filled orders pay L, plus a maker fee (Kalshi charges none on most markets; "fee" runs Kalshi's 0.0175 rate as
the worst case). The question is adverse selection: orders fill when the price comes down to them, so filled bets
should win less often than the taker's.

    python lab/maker.py
"""
import json
import os

import numpy as np

import common as C

HERE = os.path.dirname(os.path.abspath(__file__))


def maker_fee(c, p):
    return np.ceil(0.0175 * c * p * (1 - p) * 100 - 1e-9) / 100


def run(d, how="join", fill="conservative", fee_rate=0.0, until=14):
    m, side_yes, top = C.live_rule(d)
    bid8, ask8 = C.own(d, side_yes, 8)
    if how == "join":
        L = bid8
    elif how == "improve":
        L = np.where(bid8 + 0.01 < ask8 - 1e-9, bid8 + 0.01, bid8)
    elif how == "tick":
        L = np.maximum(ask8 - 0.001, bid8)
    else:
        raise ValueError(how)
    L = np.round(L, 4)
    filled = np.zeros(len(L), bool)
    for k in range(9, until + 1):
        b, a = C.own(d, side_yes, k)
        hit = a <= L + 1e-9
        if fill == "optimistic":
            hit |= b < L - 1e-9
        filled |= np.nan_to_num(hit, nan=0).astype(bool)
    wins = C.won(d, side_yes)
    sel = m & filled & (L > 0)
    c = np.floor(10.0 / L[sel] + 1e-9)
    cost = c * L[sel]
    f = maker_fee(c, L[sel]) if fee_rate else 0.0
    pnl = np.where(wins[sel], c, 0.0) - cost - f
    ok = c > 0
    unf = m & ~filled
    return {"orders": int(m.sum()), "filled": int(sel.sum()), "fillRate": float(sel.sum() / m.sum()),
            "winFilled": float(wins[sel].mean()), "winUnfilled": float(wins[unf].mean()), "winAll": float(wins[m].mean()),
            "avgL": float(L[sel].mean()), "avgAsk": float(top[sel].mean()),
            "byPeriod": C.by_period(pnl[ok], cost[ok], d["open_ts"][sel][ok])}


def main():
    d = C.load()
    m, side_yes, top = C.live_rule(d)
    pnl, cost = C.bet(top[m], C.won(d, side_yes)[m])
    out = {"taker": {"orders": int(m.sum()), "winAll": float(C.won(d, side_yes)[m].mean()),
                     "byPeriod": C.by_period(pnl, cost, d["open_ts"][m])}}
    print("TAKER (the live rule): ", C.fmt(out["taker"]["byPeriod"]["all"]),
          f" $ {out['taker']['byPeriod']['all']['pnl']:+,.0f}")
    for how in ("join", "improve", "tick"):
        for fill in ("conservative", "optimistic"):
            for fee_rate in (0.0, 0.0175):
                if fee_rate and fill == "optimistic":
                    continue
                key = f"{how}-{fill}" + ("-fee" if fee_rate else "")
                r = run(d, how, fill, fee_rate)
                out[key] = r
                a = r["byPeriod"]
                print(f"\n{key}: filled {r['filled']}/{r['orders']} ({r['fillRate']:.0%}) at avg {r['avgL']:.4f} vs ask {r['avgAsk']:.4f};"
                      f" win filled {r['winFilled']:.4f}, unfilled {r['winUnfilled']:.4f}, taker {r['winAll']:.4f}")
                for p in ("all", "pre", "post", "paper"):
                    print(f"   {p:<6} {C.fmt(a[p])}  $ {a[p]['pnl']:+,.0f}")
    with open(os.path.join(HERE, "maker.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
