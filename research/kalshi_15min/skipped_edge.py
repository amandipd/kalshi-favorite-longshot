"""The live entry rule replayed on the 15-minute series the bot skips.

The bot trades crypto, metals and energy (bot.py's EDGE_GROUPS). Kalshi runs 35 fifteen-minute
series; the other 16 -- Coin Race, FX, Treasury yields, the stock indices and Brent -- have never
been tested on their own data. This replays the live rule on them: at the end of minute 8 buy the
favourite (the dearer of YES at its ask and NO at 1 - the YES bid) when that price is 92-99.9c,
$10 flat, hold to settlement, paying Kalshi's taker fee rounded up to the cent.

$10 flat from a bankroll that can't run out is strategies_backtest.py's edge() measure: it compares
rules on what they earn a bet, apart from sizing and from going broke. The headline is cents per
dollar staked, with its t-stat, so these series line up against the live bot's own +1.39c/$1.

Reads minutes_skipped.csv (fetch_skipped.py) and the four minute files the rest of the research
reads, each market once. Writes skipped_edge.json.

    python fetch_skipped.py     (the minute history for the skipped series)
    python skipped_edge.py      (then this)
"""
import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone

from fetch_all15 import group_of

# minutes_skipped.csv first: it is the fresh pull, and the older files stop earlier.
FILES = ("minutes_skipped.csv", "minutes_30d.csv", "minutes_new.csv", "minutes_ext.csv", "minutes_pre.csv")
MINUTE = 8          # the live bot's entry minute
LO, HI = 0.92, 0.999  # the live price floor (raised to 92c on Oct 14) and Kalshi's dearest quote
STAKE = 10.0
SLIP = 0.004   # live fills landed this much over the candle ask (live_fills.py); 0 buys at the ask
SKIPS = ("spread", "late")   # the warning signs the live bot skips on; most of its edge is here, not in the floor
# The control: the series the bot does trade, so the same rule on the same code gives the number to beat.
TRADED = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M", "KXHYPE15M", "KXNEAR15M", "KXDOGE15M",
          "KXZEC15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXCOPPER15M", "KXPALLADIUM15M",
          "KXNATGAS15M", "KXWTI15M")
OUT = "skipped_edge.json"


def num(v):
    return float(v) if v not in (None, "") else None


def favourite(bid, ask):
    """The side the rule buys and what it pays: the dearer of YES at its ask and NO at 1 - the YES bid."""
    if bid is None or ask is None:
        return None, None
    yes, no = ask, round(1 - bid, 4)
    if abs(yes - no) < 1e-9:
        return None, None
    return ("yes", yes) if yes > no else ("no", no)


def fee(contracts, price):
    """Kalshi's taker fee, rounded up to the cent per order (bot.py's taker_fee at fee multiplier 1)."""
    return math.ceil(0.07 * contracts * price * (1 - price) * 100 - 1e-9) / 100


def own_quote(m, side, k):
    """The favourite side's own (bid, ask) at the end of minute k, or None without both: for NO, the YES quote
    turned round. Same as strategies_backtest.py's."""
    bid, ask = num(m.get(f"b{k}")), num(m.get(f"a{k}"))
    if bid is None or ask is None:
        return None
    return (bid, ask) if side == "yes" else (round(1 - ask, 4), round(1 - bid, 4))


def warned(m, side, minute, signs):
    """findings.py's warning signs at the entry minute, the two the live bot skips on: "spread", the favourite's ask
    2c or more over its bid; "late", its mid 50c or under a minute or two before, or up 10c or more in the entry
    minute. strategies_backtest.py's skipped(), market by market."""
    def mid(k):
        q = own_quote(m, side, k)
        return None if q is None else (q[0] + q[1]) / 2

    for sign in signs or ():
        if sign == "spread":
            q = own_quote(m, side, minute)
            if q and q[1] - q[0] >= 0.02 - 1e-9:
                return True
        elif sign == "late":
            now, before = mid(minute), mid(minute - 1)
            if (now is not None and before is not None and now - before >= 0.10) or                     any(x is not None and x <= 0.5 for x in (mid(minute - 2), before)):
                return True
    return False


def band(price):
    """The 2c price band a bet falls in, as the rest of the research labels them."""
    lo = int(price * 100) // 2 * 2
    return f"{lo}-{lo + 2}"


def markets(series):
    """Every settled market once, for these series, as the minute files' rows."""
    want, seen = set(series), set()
    for path in FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["series"] in want and r["ticker"] not in seen:
                    seen.add(r["ticker"])
                    yield r


def stats(each):
    """The mean of per-bet cents per $1 staked and its t-stat; (None, None) with nothing to average."""
    n = len(each)
    if not n:
        return None, None
    mu = sum(each) / n
    if n < 2:
        return mu, None
    sd = math.sqrt(sum((x - mu) ** 2 for x in each) / (n - 1))
    return mu, (mu / (sd / math.sqrt(n)) if sd else None)


def replay(series, minute=MINUTE, lo=LO, hi=HI, stake=STAKE, slip=0.0, skip=()):
    """The rule's bets on these series: the totals, and the same split by series, group, band, side and half.

    The floor and ceiling are judged on the quote the bot sees; `slip` is what the fill then costs over it,
    never past the ceiling, as strategies_backtest.py's "live" scenario charges it. `skip` is the warning signs
    to pass over -- the live bot skips both ("spread", "late")."""
    bets = []
    for m in markets(series):
        bid, ask = num(m.get(f"b{minute}")), num(m.get(f"a{minute}"))
        side, top = favourite(bid, ask)
        if top is None or not (lo <= top <= hi):
            continue
        if warned(m, side, minute, skip):
            continue
        price = min(top + slip, hi)
        c = stake / price
        f = fee(c, price)
        won = (side == "yes") == (m["resolved_yes"] == "1")
        pnl = (c if won else 0.0) - c * price - f
        bets.append({"series": m["series"], "group": group_of(m["series"]), "open": m["open_time"], "side": side,
                     "quote": top, "price": price, "band": band(top), "spread": (ask - bid) * 100,
                     "contracts": c, "fee": f, "won": won, "pnl": pnl,
                     "cents": pnl / (c * price) * 100})
    return report(bets, series, minute, lo, hi, stake, slip, skip)


def report(bets, series, minute, lo, hi, stake, slip, skip):
    def windows(rows):
        """How a window's bets land together: Coin Race runs five markets a window and exactly one settles YES,
        so its bets are one bet on which coin leads, not five independent ones."""
        per = defaultdict(float)
        for b in rows:
            per[b["open"]] += b["pnl"]
        return len(per), (round(min(per.values()), 2) if per else None)

    def summarize(rows):
        mu, t = stats([b["cents"] for b in rows])
        n, worst = windows(rows)
        return {"bets": len(rows), "windows": n, "betsPerWindow": round(len(rows) / n, 2) if n else None,
                "worstWindow": worst,
                "spread": round(sum(b["spread"] for b in rows) / len(rows), 2) if rows else None,
                "wins": sum(b["won"] for b in rows), "losses": sum(not b["won"] for b in rows),
                "staked": round(sum(b["contracts"] * b["price"] for b in rows), 2),
                "fees": round(sum(b["fee"] for b in rows), 2), "pnl": round(sum(b["pnl"] for b in rows), 2),
                "centsPerDollar": mu if mu is None else round(mu, 3), "t": t if t is None else round(t, 2)}

    def split(key):
        out = defaultdict(list)
        for b in bets:
            out[b[key]].append(b)
        return {k: summarize(v) for k, v in sorted(out.items())}

    mu, t = stats([b["cents"] for b in bets])
    n_windows, worst_window = windows(bets)
    opens = sorted(b["open"] for b in bets)
    halves = {}
    if bets:
        mid = opens[len(opens) // 2]
        halves = {"first": summarize([b for b in bets if b["open"] < mid]),
                  "second": summarize([b for b in bets if b["open"] >= mid])}
    return {"series": list(series), "minute": minute, "floor": lo, "ceiling": hi, "stake": stake, "slip": slip,
            "skip": list(skip),
            "bets": len(bets), "windows": n_windows,
            "betsPerWindow": round(len(bets) / n_windows, 2) if n_windows else None, "worstWindow": worst_window,
            "wins": sum(b["won"] for b in bets), "losses": sum(not b["won"] for b in bets),
            "spread": round(sum(b["spread"] for b in bets) / len(bets), 2) if bets else None,
            "contracts": sum(b["contracts"] for b in bets),
            "staked": round(sum(b["contracts"] * b["price"] for b in bets), 2),
            "fees": round(sum(b["fee"] for b in bets), 2), "pnl": round(sum(b["pnl"] for b in bets), 2),
            "centsPerDollar": mu if mu is None else round(mu, 3), "t": t if t is None else round(t, 2),
            "from": opens[0] if opens else None, "to": opens[-1] if opens else None,
            "bySeries": split("series"), "byGroup": split("group"), "byBand": split("band"),
            "bySide": split("side"), "halves": halves}


def line(name, r):
    cpd = "     -" if r["centsPerDollar"] is None else f"{r['centsPerDollar']:+6.2f}"
    t = "    -" if r.get("t") is None else f"{r['t']:+5.2f}"
    per = "   -" if r.get("betsPerWindow") is None else f"{r['betsPerWindow']:4.1f}"
    worst = "        -" if r.get("worstWindow") is None else f"{r['worstWindow']:+9.2f}"
    sp = "    -" if r.get("spread") is None else f"{r['spread']:5.2f}"
    return (f"  {name:<20}{r['bets']:>7} bets{r['losses']:>6} lost   {cpd}c/$1  t={t}"
            f"   ${r['pnl']:>9.2f} on ${r['staked']:>10.2f}  {per}/window  worst {worst}  spread {sp}c")


def ci(r):
    """The 95% interval around cents per $1, from the mean's own t: the range the edge could really be in."""
    if not r["t"] or r["centsPerDollar"] is None:
        return None
    se = abs(r["centsPerDollar"] / r["t"])
    return [round(r["centsPerDollar"] - 1.96 * se, 2), round(r["centsPerDollar"] + 1.96 * se, 2)]


def main():
    print(__doc__)
    from fetch_skipped import scanned
    series = [s["ticker"] for s in scanned() if s["settled"]]
    print(f"{len(series)} skipped series with settled markets.")
    print(f"The control, the series the bot does trade under the same rule, is the last line of each block.\n")
    out = {}
    for name, slip, skip in (("floor", 0.0, ()), ("floorlive", SLIP, ()),
                             ("rule", 0.0, SKIPS), ("rulelive", SLIP, SKIPS)):
        r = replay(series, slip=slip, skip=skip)
        out[name] = r
        head = ("the 92c floor alone" if not skip else "the full live rule, both warning signs skipped")
        head += ", at the candle ask" if not slip else f", {slip * 100:.1f}c over the ask, where live fills landed"
        print(f"=== {head} ===\n\nby series:")
        for k, row in sorted(r["bySeries"].items(), key=lambda kv: -kv[1]["bets"]):
            print(line(k, row), " 95% CI", ci(row))
        print("\nby group:")
        for k, row in sorted(r["byGroup"].items(), key=lambda kv: -kv[1]["bets"]):
            print(line(k, row), " 95% CI", ci(row))
        print("\nby price band:")
        for k, row in r["byBand"].items():
            print(line(k, row))
        print("\nby half (the second half is the holdout):")
        for k, row in r["halves"].items():
            print(line(k, row))
        print("\n" + line("all skipped", r), " 95% CI", ci(r))
        control = replay(TRADED, slip=slip, skip=skip)
        out[name + "Control"] = control
        print(line("what the bot trades", control), " 95% CI", ci(control), "\n")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
