"""The favourites rule on Kalshi's other markets: hourly, daily and weekly series, Jul 18 to the last full day.

Strategy: the 15-minute rule moved to other markets. At a fixed time before a market closes (5 to 45 minutes for an
hourly series, 1 to 12 hours for a daily or weekly one), buy the favourite - the side with the higher ask - when that
ask is 90-99.9c, and hold it to settlement. $10 a bet, taker fee with the series' own fee multiplier, filled 0.4c a
contract worse than the recorded ask, as live fills are for the 15-minute markets.

Reads other_markets.json and other_hours.csv (fetch_other.py). Reports profit per $10 bet by category and frequency
at each checkpoint, with a 95% range clustered by close time (markets that close together move together: an event's
brackets, or every crypto series at the same hour), the two halves of the history apart (Jul 18 - Aug 31 to choose
rules on, Sep 1 on to test them once: PLAN_OTHER_MARKETS.md),
and the same with a liquidity screen (the favourite's own bid within 3c of its ask).

Then the plan's pass test, on the liquid bets: groups (category, frequency, checkpoint) are chosen from the first half
alone, and only those are read on the second half, once.

The unscreened sports rows (about -400c a bet) are Counter-Strike map markets, whose books sit at placeholder quotes
such as 3c bid / 95c ask before a map starts. Both sides then look like 95c+ favourites, and those "favourites" win
about half the time. The settlements are sound (each map has one YES and one NO); the liquidity screen drops them.

    python other_markets.py
"""
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from history import strategy

LO, HI = 0.90, 0.999
SLIP = 0.004
SPLIT = datetime.fromisoformat("2026-09-01T00:00:00+00:00").timestamp()   # choose on Jul 18 - Aug 31, test on Sep 1 on
CHECKS = {"min": (45, 30, 20, 10, 5), "hour": (12, 6, 3, 2, 1)}
UNIT = {"min": "min", "hour": "h"}
ET = ZoneInfo("America/New_York")
BANK = 240                      # the worst day is a share of this
EDGE = 0.02                     # the plan's pass: at least +2c a $10 bet in both halves,
MIN_TEST = 1000                 # 1,000+ test-half bets,
MIN_SERIES, MIN_DAYS = 5, 20    # from 5+ series or 20+ days,
WORST = 0.30                    # and a worst day under 30% of $240
MIN_CHOOSE = 200                # bets a group needs in the first half to be chosen


def num(x):
    return float(x) if x not in ("", None) else None


def fee(c, p, mult):
    return math.ceil(mult * 0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def load():
    meta = {s["series"]: s for s in json.load(open("other_markets.json"))}
    with open("other_hours.csv") as fh:
        for r in csv.DictReader(fh):
            s = meta.get(r["series"])
            if s:
                yield r, s


def bets():
    """(category, frequency, series, checkpoint, close ts, pnl on $10, spread ok) for every bet the rule makes."""
    out = []
    for r, s in load():
        close = datetime.fromisoformat(r["close"].replace("Z", "+00:00")).timestamp()
        mult = float(s.get("fee_multiplier") if s.get("fee_multiplier") is not None else 1)
        for k in CHECKS[r["unit"]]:
            b, a = num(r.get(f"b{k}")), num(r.get(f"a{k}"))
            if b is None or a is None or b <= 0 or a >= 1:
                continue
            yes, no = a, round(1 - b, 4)
            if abs(yes - no) < 1e-9:
                continue
            side, price = ("yes", yes) if yes > no else ("no", no)
            if not LO <= price <= HI:
                continue
            p = min(price + SLIP, 0.999)
            c = 10 / p
            won = (side == "yes") == (r["result"] == "yes")
            spread = a - b   # the same for both sides
            out.append((s["category"], s["frequency"], r["series"], f"{k}{UNIT[r['unit']]}", close,
                        (c if won else 0.0) - 10 - fee(c, p, mult), spread <= 0.03))
    return out


def clustered(rows):
    """Mean profit per bet and its standard error, clustered by close time (nan with one close time)."""
    n = len(rows)
    mu = sum(x[5] for x in rows) / n
    by = defaultdict(float)
    for x in rows:
        by[x[4]] += x[5] - mu
    g = len(by)
    se = math.sqrt(sum(v * v for v in by.values()) * g / (g - 1)) / n if g > 1 else float("nan")
    return mu, se


def summary(rows):
    n = len(rows)
    mu, se = clustered(rows)
    half = lambda ok: [x[5] for x in rows if ok(x[4])]
    b, a = half(lambda t: t < SPLIT), half(lambda t: t >= SPLIT)
    c = lambda xs: f"{sum(xs) / len(xs) * 100:+6.1f}c" if xs else "      -"
    return mu, se, f"{n:>7,} {mu * 100:>+7.1f}c ({(mu - 1.96 * se) * 100:+6.1f} to {(mu + 1.96 * se) * 100:+6.1f})  {c(b)} {c(a)}  ${sum(x[5] for x in rows):>+9,.0f}"


def table(rows, key, title, min_n=200):
    print(f"\n{title}")
    print(f"   {'':<44} {'bets':>7} {'per $10':>8} {'95% range':<18} {'Jul-Aug31':>8} {'Sep1 on':>8}  {'total':>10}")
    groups = defaultdict(list)
    for x in rows:
        groups[key(x)].append(x)
    for k, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(rs) >= min_n:
            print(f"   {' · '.join(map(str, k)):<44} {summary(rs)[2]}")


def stats(rows):
    """What the pass test reads off a set of bets; None for none. worst: the worst New York day's loss at $10 a bet,
    as a share of BANK (0.0 if no day lost)."""
    if not rows:
        return None
    mu, se = clustered(rows)
    days = defaultdict(float)
    for x in rows:
        days[datetime.fromtimestamp(x[4], ET).date()] += x[5]
    return {"bets": len(rows), "mu": mu, "lo": mu - 1.96 * se, "hi": mu + 1.96 * se, "series": len({x[2] for x in rows}),
            "days": len(days), "worst": max(0.0, -min(days.values())) / BANK}


def groups(rows):
    """The liquid bets by (category, frequency, checkpoint)."""
    out = defaultdict(list)
    for x in rows:
        if x[6]:
            out[(x[0], x[1], x[3])].append(x)
    return out


def candidates(rows):
    """The groups the plan picks from the first half alone (closes before SPLIT): MIN_CHOOSE+ liquid bets there, at
    least +2c a $10 bet and a 95% range above zero. Nothing from Sep 1 on is read."""
    return sorted(k for k, rs in groups([x for x in rows if x[4] < SPLIT]).items()
                  if (s := stats(rs))["bets"] >= MIN_CHOOSE and s["mu"] >= EDGE and s["lo"] > 0)


def verdict(choose, test):
    """The pass conditions a candidate fails (PLAN_OTHER_MARKETS.md, "What counts as a pass"); [] is a pass."""
    if test is None:
        return ["no test-half bets"]
    return [why for bad, why in ((choose["mu"] < EDGE, "choosing half under +2c"),
                                 (test["mu"] < EDGE, "test half under +2c"),
                                 (not test["lo"] > 0, "test range not above zero"),
                                 (test["bets"] < MIN_TEST, "under 1,000 test bets"),
                                 (test["series"] < MIN_SERIES and test["days"] < MIN_DAYS, "under 5 series and under 20 days"),
                                 (test["worst"] >= WORST, "worst day 30%+")) if bad]


def pass_test(rows):
    """Choose on the first half, then read the second half once: (key, first-half stats, second-half stats, the
    conditions failed) for each candidate."""
    every = groups(rows)
    keys = candidates(rows)
    print(f"\nThe plan's pass test, liquid bets only. Chosen before Sep 1: {MIN_CHOOSE}+ bets, +{EDGE * 100:.0f}c or more a $10"
          f" bet and a 95% range above zero ({len(keys)} of {len(every)} groups). Then Sep 1 on, read once.")
    if not keys:
        print("No group qualified on the choosing half.")
        return []
    print(f"   {'':<44} {'before Sep 1':>15}   {'Sep 1 on':<8}")
    print(f"   {'':<44} {'bets':>6} {'per $10':>8}   {'bets':>6} {'per $10':>8} {'95% range':<18} {'series':>6} {'days':>5}"
          f" {'worst day':>9}")
    out = []
    for key in keys:
        choose = stats([x for x in every[key] if x[4] < SPLIT])
        test = stats([x for x in every[key] if x[4] >= SPLIT])
        why = verdict(choose, test)
        t = (f"{test['bets']:>6,} {test['mu'] * 100:>+7.1f}c ({test['lo'] * 100:+6.1f} to {test['hi'] * 100:+6.1f}) "
             f"{test['series']:>6} {test['days']:>5} {test['worst']:>9.0%}") if test else " " * 64
        print(f"   {' · '.join(key):<44} {choose['bets']:>6,} {choose['mu'] * 100:>+7.1f}c   {t}  {'; '.join(why) or 'PASS'}")
        out.append((key, choose, test, why))
    print(f"{sum(not why for *_, why in out)} of {len(out)} candidates passed.")
    return out


def main():
    strategy(__doc__)
    rows = bets()
    print(f"{len(rows):,} bets across {len({x[2] for x in rows})} series")
    table(rows, lambda x: (x[0], x[1], x[3]), "By category, frequency and time before close (every bet):")
    table([x for x in rows if x[6]], lambda x: (x[0], x[1], x[3]), "The same, only where the bid was within 3c of the ask:")
    liquid = [x for x in rows if x[6]]
    table(liquid, lambda x: (x[2], x[3]), "By series and checkpoint, liquid only (200+ bets):", min_n=200)
    pass_test(rows)


if __name__ == "__main__":
    main()
