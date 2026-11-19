"""Does the edge hold month by month? The minute-8 favourites rule over every month since Dec 10, 2025.

Strategy: at the end of minute 8 of each 15-minute window, buy the favourite - the side with the higher ask - of each
crypto, metals and energy market when that ask is 90-99.9c, $10 a bet, filled 0.4c a contract worse than the recorded
ask, with the taker fee, and hold it to settlement. Two versions: the plain rule, and the live bot's
(strategies_backtest.LIVE[0]: the same, skipping both warning signs and the Fed decisions' windows).

The history before Jul 18 (minutes_pre.csv: crypto only, Dec 10 - Jul 17) was never used to choose any rule, so it is
the longest fair test there is. For each version, each part of the history (Dec 10 - Jul 17, Jul 18 - Aug 23, Aug 24
on) and each month, this reports:

  bets, and the share that won
  cost      what a bet must win to break even: the fill plus the fee, a contract
  per $10   profit per $10 bet in cents, with a 95% range clustered by window (bets in a window win and lose together)
  kelly     the one-bet Kelly fraction, f* = (won - cost) / (1 - cost): the growth-maximising bet if each bet stood alone
  spread    the favourites' average gap between bid and ask at minute 8: how thin the books were. The minute files
            record no volume, so this stands in for it.

and, for Dec 10 - Jul 17, the same by market. Writes by_month.json.

    python by_month.py
"""
import json
import math
from collections import defaultdict
from datetime import datetime, timezone

import history
import strategies_backtest as sb
from history import strategy

SLIP = 0.004                                   # live-like fills
STAKE = 10.0
PARTS = [("pre", "Dec 10 – Jul 17", history.FIRST, history.JUL18),
         ("before", "Jul 18 – Aug 23", history.JUL18, "2026-08-24T00:00:00Z"),
         ("after", "Aug 24 on", "2026-08-24T00:00:00Z", None)]


def bets():
    """Every minute-8 favourite at 90-99.9c in the edge groups: when, which market, the fill, $10 P&L and whether the
    live bot would have bought it too."""
    live = sb.LIVE[0]
    windows, _, _ = sb.load()
    out = []
    for t, ms in sorted(windows.items()):
        blackout = any(t < z and t + 900 > a for a, z in live["blackouts"])
        for m in ms:
            if m["group"] not in sb.EDGE_GROUPS:
                continue
            side, top = sb.favourite(*m["q"][8])
            if not side or not sb.LO <= top <= sb.HI:
                continue
            price = min(top + SLIP, 0.999)
            c = STAKE / price
            f = sb.fee(c, price)
            won = (side == "yes") == m["yes"]
            bid, ask = m["q"][8]
            out.append({"t": t, "series": m["series"], "won": won, "cost": price + f / c,
                        "pnl": (c if won else 0.0) - STAKE - f, "spread": round(ask - bid, 4),
                        "live": not blackout and not sb.skipped(live, m, side)})
    return out


def stats(bs):
    """Bets, win rate, all-in cost, cents per $10 bet with a 95% range clustered by window, Kelly and spread."""
    n = len(bs)
    if not n:
        return None
    won = sum(b["won"] for b in bs) / n
    cost = sum(b["cost"] for b in bs) / n
    mu = sum(b["pnl"] for b in bs) / n * 100
    by_w = defaultdict(list)
    for b in bs:
        by_w[b["t"]].append(b["pnl"] * 100)
    k = len(by_w)
    lo = hi = None
    if k > 1:
        resid = [sum(v) - mu * len(v) for v in by_w.values()]
        se = (sum(x * x for x in resid) / (k - 1)) ** 0.5 / ((n / k) * math.sqrt(k))
        lo, hi = mu - 1.96 * se, mu + 1.96 * se
    return {"bets": n, "windows": k, "won": round(won, 5), "cost": round(cost, 5), "perBet": round(mu, 2),
            "lo": None if lo is None else round(lo, 2), "hi": None if hi is None else round(hi, 2),
            "kelly": round((won - cost) / (1 - cost), 4), "spread": round(sum(b["spread"] for b in bs) / n, 4),
            "pnl": round(sum(b["pnl"] for b in bs), 2)}


def month(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")


def table(bs):
    """stats() for each part of the history, each month, and each market in the first part."""
    def within(a, z):
        lo, hi = sb.ts(a), sb.ts(z) if z else math.inf
        return [b for b in bs if lo <= b["t"] < hi]
    months = defaultdict(list)
    for b in bs:
        months[month(b["t"])].append(b)
    pre = within(PARTS[0][2], PARTS[0][3])
    series = defaultdict(list)
    for b in pre:
        series[b["series"]].append(b)
    return {"all": stats(bs), "parts": {k: stats(within(a, z)) for k, _, a, z in PARTS},
            "months": {m: stats(v) for m, v in sorted(months.items())},
            "preBySeries": {s: stats(v) for s, v in sorted(series.items())}}


def show(name, t):
    def row(label, s):
        if not s:
            return f"  {label:<18} {'no bets':>8}"
        rng = f"({s['lo']:+5.1f} to {s['hi']:+5.1f})" if s["lo"] is not None else ""
        return (f"  {label:<18} {s['bets']:7,d} {s['won']:7.2%} {s['cost']:7.2%} {s['perBet']:+7.1f}c {rng:<17}"
                f" {s['kelly']:+7.1%} {s['spread'] * 100:6.2f}c  ${s['pnl']:+10,.2f}")
    print(f"\n{name}")
    print(f"  {'':<18} {'bets':>7} {'won':>7} {'cost':>7} {'per $10':>8} {'95% range':<17} {'kelly':>7} {'spread':>7}  {'profit':>11}")
    print(row("all", t["all"]))
    for k, label, _, _ in PARTS:
        print(row(label, t["parts"][k]))
    print("  by month")
    for m, s in t["months"].items():
        print(row(m, s))
    print("  Dec 10 – Jul 17, by market")
    for s, v in t["preBySeries"].items():
        print(row(s.replace("KX", "").replace("15M", ""), v))


def main():
    strategy(__doc__)
    bs = bets()
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "slip": SLIP,
           "parts": [{"key": k, "label": label, "from": a, "to": z} for k, label, a, z in PARTS],
           "plain": table(bs), "live": table([b for b in bs if b["live"]])}
    show("THE PLAIN RULE: every 90-99.9c favourite at minute 8, crypto, metals and energy", out["plain"])
    show("THE LIVE BOT'S RULE: the same, skipping both warning signs and the Fed decisions' windows", out["live"])
    with open("by_month.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("\nby_month.json written")


if __name__ == "__main__":
    main()
