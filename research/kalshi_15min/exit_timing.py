"""When, if ever, to sell a minute-8 favorite that has turned against you: the test the theory asks for.

Strategy: the bot's. At the end of minute 8, buy the favourite - the side with the higher ask - of each
crypto, metals or energy market when that ask is 90-99.9c, and hold it to settlement. This script asks
whether selling it at the bid later in the window would have done better, minute by minute.

The theory (see the README's "Selling early" notes): if the price is a fair win probability (a martingale),
no selling rule changes the expected payout, so every sale only pays the spread and the fee; holding is
optimal. Selling helps only where the market overprices the side you hold, the "Yogi Berra" pattern of
collapsed favourites trading above their chance late in a game. So the test is a calibration table: for
every position still open at the end of minute m, bucket the bid it could be sold for and compare that
with how often it went on to win. Selling pays only in a cell where

    win rate  <  bid - the taker fee per contract

and holding pays everywhere else. Two more checks of the fair-price assumption:

  - The crossing law. For a fair price starting at p, the chance it ever falls to x before the end is
    (1 - p) / (1 - x) (optional stopping). Falling there more often than that means the price overreacts
    and tends to bounce, which favours holding; less often means it underreacts, which favours selling.
  - Each simple rule (sell the first time the bid is at or under x, from minute m on), against holding.
  - The mirror image: if a dip is underpriced, buying another $10 at the ask (0.4c worse, as live fills
    are) the first time it trades at or under x should pay.

Standard errors are clustered by window, since a window's markets move together.

    python exit_timing.py
"""
import math
from collections import defaultdict
from datetime import datetime

import history
from history import strategy

LO, HI = 0.90, 0.999
ENTRY = 8
LATER = range(9, 15)   # minutes 9-14: minute 15's quote is the close, when the result is all but known
JUL18 = datetime.fromisoformat(history.JUL18.replace("Z", "+00:00")).timestamp()
SPLIT = datetime.fromisoformat("2026-08-24T00:00:00+00:00").timestamp()
BUCKETS = [(0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9),
           (0.9, 0.95), (0.95, 1.0)]


def num(x):
    return float(x) if x not in ("", None) else None


def fee(price):
    """The taker fee per contract on a 100-contract order, rounded up to the cent: 0.07 p (1 - p)."""
    return math.ceil(0.07 * 100 * price * (1 - price) * 100 - 1e-9) / 100 / 100


def part(t):
    """Which part of the history a window opening at t is in: before Jul 18, Jul 18 - Aug 23, or Aug 24 on."""
    return "pre" if t < JUL18 else "before" if t < SPLIT else "after"


def positions():
    """Every minute-8 favourite the strategy buys: when, which side, what it paid, the side's (bid, ask) each minute, won."""
    out = []
    for r in history.each():
        q = {k: (num(r[f"b{k}"]), num(r[f"a{k}"])) for k in range(1, 16)}
        bid, ask = q[ENTRY]
        if bid is None or ask is None:
            continue
        yes, no = ask, round(1 - bid, 4)
        if abs(yes - no) < 1e-9:
            continue
        side, price = ("yes", yes) if yes > no else ("no", no)
        if not LO <= price <= HI:
            continue
        mine = {k: (b, a) if side == "yes" else (None if a is None else round(1 - a, 4), None if b is None else round(1 - b, 4))
                for k, (b, a) in q.items()}
        t = datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")).timestamp()
        out.append({"t": t, "price": price, "q": mine, "won": (r["resolved_yes"] == "1") == (side == "yes")})
    return out


def clustered(rows):
    """Mean of x and its window-clustered standard error, from (window, x) pairs."""
    n = len(rows)
    if n < 2:
        return (rows[0][1] if rows else None), None
    mu = sum(x for _, x in rows) / n
    by = defaultdict(float)
    for w, x in rows:
        by[w] += x - mu
    g = len(by)
    if g < 2:
        return mu, None
    return mu, math.sqrt(sum(v * v for v in by.values()) * g / (g - 1)) / n


def calibration(ps):
    print("\nSell or hold: positions still open at the end of each minute, by the bid they could be sold for.")
    print("edge = win rate - (bid - fee): positive means holding beat selling (95% range in brackets).")
    for m in LATER:
        print(f"\n minute {m}")
        print(f"   {'bid':<9} {'positions':>9} {'mean bid':>9} {'won':>7} {'edge':>8}  {'95% range':<17} verdict")
        for lo, hi in BUCKETS:
            rows = [(p["t"], p) for p in ps if p["q"][m][0] is not None and lo <= p["q"][m][0] < hi]
            if len(rows) < 20:
                continue
            bid = sum(p["q"][m][0] for _, p in rows) / len(rows)
            won = sum(p["won"] for _, p in rows) / len(rows)
            mu, se = clustered([(w, p["won"] - (p["q"][m][0] - fee(p["q"][m][0]))) for w, p in rows])
            rng = f"({mu - 1.96 * se:+.3f} to {mu + 1.96 * se:+.3f})" if se else ""
            verdict = "sell" if se and mu + 1.96 * se < 0 else "hold" if se and mu - 1.96 * se > 0 else "no difference"
            print(f"   {lo * 100:>3.0f}-{hi * 100:<3.0f}c {len(rows):>9,} {bid * 100:>8.1f}c {won:>7.1%} {mu:>+8.3f}  {rng:<17} {verdict}")


def crossings(ps):
    print("\nThe crossing law: how often the side's mid fell to x by minute 14, against (1 - p) / (1 - x) for a fair price.")
    print(f"   {'x':<5} {'fell there':>11} {'fair price says':>16} {'then won':>9}  (a fair price wins about x of these)")
    for x in (0.8, 0.7, 0.5, 0.3, 0.1):
        hit = expect = 0
        won = []
        for p in ps:
            b, a = p["q"][ENTRY]
            if b is None or a is None:
                continue
            mid0 = (b + a) / 2
            if mid0 <= x:
                continue
            expect += (1 - mid0) / (1 - x)
            mids = [(p["q"][m][0] + p["q"][m][1]) / 2 for m in LATER if p["q"][m][0] is not None and p["q"][m][1] is not None]
            if any(v <= x for v in mids):
                hit += 1
                won.append(p["won"])
        n = sum(1 for p in ps if None not in p["q"][ENTRY])
        print(f"   {x * 100:>3.0f}c {hit / n:>11.2%} {expect / n:>16.2%} {sum(won) / max(1, len(won)):>9.1%}")


def rules(ps):
    print("\nEvery simple rule on $10 bets: sell the first time the bid is at or under x, from minute m to 14, at the bid less the fee.")
    print("Profit against holding (positive: the rule did better), all history (Dec 10 - Jul 17 · Jul 18 - Aug 23 · Aug 24 on).")
    best = None
    for m0 in (9, 11, 12, 13, 14):
        cells = []
        for x in (0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05):
            diff = {"all": 0.0, "pre": 0.0, "before": 0.0, "after": 0.0}
            for p in ps:
                contracts = 10 / p["price"]
                for m in range(m0, 15):
                    b = p["q"][m][0]
                    if b is not None and b <= x:
                        gain = contracts * (b - fee(b)) - (contracts if p["won"] else 0.0)
                        for k in ("all", part(p["t"])):
                            diff[k] += gain
                        break
            cells.append(f"{x * 100:.0f}c {diff['all']:+,.0f} ({diff['pre']:+,.0f} · {diff['before']:+,.0f} · {diff['after']:+,.0f})")
            if best is None or diff["all"] > best[0]:
                best = (diff["all"], m0, x)
        print(f"   from minute {m0:<2}  " + "   ".join(cells[:4]))
        print(f"                  " + "   ".join(cells[4:]))
    print(f"\nBest rule: sell under {best[2] * 100:.0f}c from minute {best[1]}: {best[0]:+,.0f} against holding.")


def dips(ps, slip=0.004):
    print("\nBuying the dip: another $10 of the same side at the ask (+0.4c) the first time it's at or under x, minutes 9-13.")
    print(f"   {'x':<5} {'from':<6} {'bets':>6} {'won':>7} {'mean ask':>9} {'per $10':>9}  {'95% range':<20} {'Dec 10-Jul 17':>13}"
          f" {'Jul 18-Aug 23':>13} {'Aug 24 on':>10}")
    for x in (0.8, 0.7, 0.6, 0.5, 0.4, 0.3):
        for m0 in (9, 11):
            rows, asks, parts = [], [], {"pre": [], "before": [], "after": []}
            for p in ps:
                for m in range(m0, 14):
                    a = p["q"][m][1]
                    if a is not None and a <= x:
                        price = min(a + slip, 0.999)
                        c = 10 / price
                        pnl = (c if p["won"] else 0.0) - 10 - c * fee(price)
                        rows.append((p["t"], pnl * 100))   # cents per $10
                        asks.append(a)
                        parts[part(p["t"])].append(pnl * 100)
                        break
            if len(rows) < 30:
                continue
            mu, se = clustered(rows)
            won = sum(1 for _, v in rows if v > 0) / len(rows)
            avg = lambda xs: f"{sum(xs) / len(xs):+.0f}c ({len(xs)})" if xs else "-"
            print(f"   {x * 100:>3.0f}c  {m0:<6} {len(rows):>6,} {won:>7.1%} {sum(asks) / len(asks) * 100:>8.1f}c {mu:>+8.0f}c  "
                  f"({mu - 1.96 * se:+.0f}c to {mu + 1.96 * se:+.0f}c){'':<4} {avg(parts['pre']):>13} {avg(parts['before']):>13}"
                  f" {avg(parts['after']):>10}")


def main():
    strategy(__doc__)
    ps = positions()
    print(f"{len(ps):,} minute-8 favourites at {LO * 100:.0f}-{HI * 100:.1f}c, {sum(p['won'] for p in ps) / len(ps):.2%} won")
    calibration(ps)
    crossings(ps)
    rules(ps)
    dips(ps)


if __name__ == "__main__":
    main()
