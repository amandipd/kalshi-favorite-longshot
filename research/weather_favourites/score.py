"""The frozen favourite rule of PREREG.md, scored on daily rain (KXRAIN) and the 24 daily-high series.

At 6 hours (primary) and 2 hours before each market's close, buy the favourite - the dearer side, YES at the ask or
NO at 1 - bid - when it costs 90c to 99.9c and the ask is within 3c of the bid, and only if the market is still
quoting after that moment (a rain market closes early once rain falls). $10 a bet, filled 0.4c worse, taker fee
rounded up to the cent, held to Kalshi's result.

Reads data/markets.jsonl (fetch.py). Reports each family by part: older and recent are the test data, seen is the
training half that was already scored on Oct 18 and never counts. The verdict is PREREG.md's, read once.

    python score.py
"""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
MARKETS = os.path.join(HERE, "data", "markets.jsonl")

LO, HI = 0.90, 0.999
SPREAD = 0.03
SLIP = 0.004
STAKE = 10.0
CHECKS = (6, 2)              # hours before close: primary first
H = 3600
MONTHS = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
OLDER = (date(2025, 7, 18), date(2026, 7, 17))
SEEN = (date(2026, 7, 18), date(2026, 9, 29))
BANDS = (("90-95", 0.95), ("95-97", 0.97), ("97-99", 0.99), ("99-99.9", 1.0))
EDGE = 0.02                  # +2c a $10 bet
MIN_BETS, MIN_DATES = 1000, 20
BANK, WORST = 240, 0.30
BIG3 = ("KXHIGHMIA", "KXHIGHNY", "KXHIGHLAX")


def fee(c, p, mult=1.0):
    return math.ceil(mult * 0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def band(price):
    return next(name for name, top in BANDS if price < top - 1e-9)


def climate_date(event):
    """The date in an event ticker: KXHIGHNY-26OCT24 -> 2026-10-24."""
    s = event.rsplit("-", 1)[1]
    return date(2000 + int(s[:2]), MONTHS[s[2:5]], int(s[5:7]))


def part(day):
    if OLDER[0] <= day <= OLDER[1]:
        return "older"
    if SEEN[0] <= day <= SEEN[1]:
        return "seen"
    return "recent" if day > SEEN[1] else None


def quote_at(cs, t):
    """(bid, ask) of the last candle ending at or before t; None if there is none."""
    before = [c for c in cs if c[0] <= t]
    return (before[-1][1], before[-1][2]) if before else None


def open_after(cs, t):
    return any(c[0] > t for c in cs)


def city(m):
    return m["series"] + "-" + m["ticker"].rsplit("-", 1)[1] if m["series"] == "KXRAIN" else m["series"]


def bet(m, hours):
    """The rule's bet on market m at hours before its close, or None."""
    cs = sorted(m["candles"])
    t = m["close"] - hours * H
    q = quote_at(cs, t)
    if q is None or not open_after(cs, t):
        return None
    b, a = q
    if b is None or a is None or b <= 0 or a >= 1:
        return None
    yes, no = a, round(1 - b, 4)
    if abs(yes - no) < 1e-9 or round(a - b, 4) > SPREAD:
        return None
    side, price = ("yes", yes) if yes > no else ("no", no)
    if not LO - 1e-9 <= price <= HI + 1e-9:
        return None
    p = min(price + SLIP, HI)
    c = STAKE / p
    won = side == m["result"]
    return {"ticker": m["ticker"], "city": city(m), "date": climate_date(m["event"]), "side": side, "price": price,
            "band": band(price), "won": won, "pnl": (c if won else 0.0) - STAKE - fee(c, p)}


def clustered(rows):
    """Mean profit per bet and its standard error, clustered by climate date (nan with one date)."""
    n = len(rows)
    mu = sum(r["pnl"] for r in rows) / n
    by = defaultdict(float)
    for r in rows:
        by[r["date"]] += r["pnl"] - mu
    g = len(by)
    se = math.sqrt(sum(v * v for v in by.values()) * g / (g - 1)) / n if g > 1 else float("nan")
    return mu, se


def stats(rows):
    if not rows:
        return None
    mu, se = clustered(rows)
    days = defaultdict(float)
    for r in rows:
        days[r["date"]] += r["pnl"]
    implied = sum(1 - r["price"] for r in rows)
    return {"bets": len(rows), "dates": len(days), "mu": mu, "lo": mu - 1.96 * se, "hi": mu + 1.96 * se,
            "lost": sum(not r["won"] for r in rows), "implied": implied, "total": sum(r["pnl"] for r in rows),
            "worst": max(0.0, -min(days.values())) / BANK, "staked": STAKE * len(rows)}


def biggest(rows, key):
    """The key value (city, month) whose bets made the most money."""
    by = defaultdict(float)
    for r in rows:
        by[key(r)] += r["pnl"]
    return max(by, key=by.get)


def month(r):
    return (r["date"].year, r["date"].month)


def verdict(rows, parts=None):
    """PREREG.md's verdict on the test bets: {'verdict': 'pass' | 'fail' | 'not enough data yet', 'why': [...]}.
    parts: {'older': rows, 'recent': rows} for the both-parts check (skipped when None)."""
    s = stats(rows) or {"bets": 0, "dates": 0}
    if s["bets"] < MIN_BETS or s["dates"] < MIN_DATES:
        return {"verdict": "not enough data yet", "why": [f"{s['bets']:,} bets on {s['dates']} dates"], "stats": s}
    why = []
    if s["mu"] < EDGE:
        why.append("under +2c a $10 bet")
    if not s["lo"] > 0:
        why.append("95% range not above zero")
    for name, _ in BANDS:
        rest = stats([r for r in rows if r["band"] != name])
        if rest is None or rest["mu"] <= 0 or not rest["lo"] > 0:
            why.append(f"fails without the {name}c band")
    for label, key in (("city", lambda r: r["city"]), ("month", month)):
        top = biggest(rows, key)
        rest = stats([r for r in rows if key(r) != top])
        if rest is None or rest["mu"] <= 0:
            why.append(f"not positive without its best {label} ({top})")
    for name, rs in (parts or {}).items():
        st = stats(rs)
        if st is None or st["mu"] <= 0:
            why.append(f"{name} part not positive")
    if s["worst"] >= WORST:
        why.append("worst day 30%+ of $240")
    return {"verdict": "fail" if why else "pass", "why": why, "stats": s}


def load(path=MARKETS):
    with open(path) as fh:
        for line in fh:
            yield json.loads(line)


def family(m):
    return "rain" if m["series"] == "KXRAIN" else "highs"


def line(label, s):
    if s is None:
        return f"   {label:<34} {'-':>7}"
    return (f"   {label:<34} {s['bets']:>7,} {s['dates']:>6} {s['lost']:>6} {s['implied']:>8.1f} "
            f"{s['mu'] * 100:>+7.1f}c ({s['lo'] * 100:+6.1f} to {s['hi'] * 100:+6.1f})  ${s['total']:>+8,.0f}")


HEAD = (f"   {'':<34} {'bets':>7} {'dates':>6} {'lost':>6} {'implied':>8} {'per $10':>8} {'95% range':<18}  {'total':>9}")


def report(ms):
    by = defaultdict(list)      # (family, hours, part) -> bets
    counts = defaultdict(lambda: defaultdict(int))
    for m in ms:
        f, p = family(m), part(climate_date(m["event"]))
        counts[f][p or "outside"] += 1
        if p is None:
            continue
        for hours in CHECKS:
            b = bet(m, hours)
            if b:
                by[(f, hours, p)].append(b)
    print("Markets by family and part (before the rule):")
    for f in ("rain", "highs"):
        print(f"   {f}: " + ", ".join(f"{k} {v:,}" for k, v in sorted(counts[f].items())))
    out = {}
    for f in ("rain", "highs"):
        for hours in CHECKS:
            test = by[(f, hours, "older")] + by[(f, hours, "recent")]
            print(f"\n{f.upper()}, {hours} hours before close{' (PRIMARY)' if hours == CHECKS[0] else ''}")
            print(HEAD)
            for p in ("older", "recent", "seen"):
                print(line(p + (" (seen: never counts)" if p == "seen" else ""), stats(by[(f, hours, p)])))
            print(line("TEST = older + recent", stats(test)))
            if f == "highs":
                print(line("test, Miami + NYC + LA only", stats([r for r in test if r["city"] in BIG3])))
            print("   by price band (test):")
            for name, top in BANDS:
                rs = [r for r in test if r["band"] == name]
                s = stats(rs)
                if s:
                    p_mid = sum(r["price"] for r in rs) / len(rs)
                    be = 1 - (p_mid + SLIP)        # the loss rate that would just break even, ignoring the fee
                    print(line(f"  {name}c (loss rate {s['lost'] / s['bets']:.2%}, break-even ~{be:.2%})", s))
            v = verdict(test, {"older": by[(f, hours, "older")], "recent": by[(f, hours, "recent")]})
            print(f"   VERDICT: {v['verdict'].upper()}" + (f" - {'; '.join(v['why'])}" if v["why"] else ""))
            out[f"{f}_{hours}h"] = {"verdict": v["verdict"], "why": v["why"],
                                    "test": stats(test), **{p: stats(by[(f, hours, p)]) for p in ("older", "recent", "seen")}}
    return out


def main():
    print(__doc__.split("\n\n")[0])
    out = report(load())
    json.dump(out, open(os.path.join(HERE, "data", "result.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    sys.exit(main())
