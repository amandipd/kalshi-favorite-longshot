"""The eight candidate entry filters of FILTER_SEARCH_PREREG.md, and the search that scores them.

The live bot's edge is not in its price floor -- the 92c floor alone returns -0.15c per $1 on the bot's own
markets. It is in the two warning signs it skips on (`strategies_backtest.skipped`), which between them read
six numbers out of the sixteen available at the entry minute. This module computes richer features of the
same quote path, fits a threshold for each on the first half of the history, and scores the best two once on
the second half against the two filters the bot uses today.

Every feature reads the entry minute and earlier only. Nothing here may look at minute 9, the settlement, or
anything else the live bot could not know when it sizes an order; tests/test_filter_search.py builds markets
whose later minutes contradict their earlier ones to hold that line.

    python filter_search.py
"""
import json
import statistics as st

import strategies_backtest as sb

# Which direction of each feature is the warning sign, as written down before any score was read.
# "high": large values are the suspicious ones, so a threshold skips bets above it. "low": the reverse.
FEATURES = {
    "mean_spread_5_8": {"worse": "high", "about": "mean own spread over the four minutes to entry"},
    "rel_spread": {"worse": "high", "about": "entry spread over that series' median entry spread"},
    "spread_trend": {"worse": "high", "about": "entry spread minus the spread three minutes earlier"},
    "fav_minutes": {"worse": "low", "about": "minutes of 1-8 this side led"},
    "travel": {"worse": "high", "about": "total absolute mid movement to entry"},
    "worst_dip": {"worse": "high", "about": "entry mid minus the lowest mid before it"},
    "since_coinflip": {"worse": "low", "about": "minutes since the mid was last 50c or under"},
    "staleness": {"worse": "high", "about": "consecutive unchanged quotes ending at entry"},
}
BACK = 3          # how far back the spread features look: minute 8 against minute 5
COINFLIP = 0.50   # "a coin flip": the mid at or under this
OUT = "filter_search.json"


# ------------------------------------------------------------------ reading the favourite's own path


def own(m, side, k):
    """The favourite side's own (bid, ask) at the end of minute k, or None without both. For the NO side the
    YES quote turns round, exactly as strategies_backtest.own_quote does it."""
    q = m["q"].get(k)
    if not q or q[0] is None or q[1] is None:
        return None
    bid, ask = q
    return (bid, ask) if side == "yes" else (round(1 - ask, 4), round(1 - bid, 4))


def mid(m, side, k):
    q = own(m, side, k)
    return None if q is None else (q[0] + q[1]) / 2


def spread(m, side, k):
    q = own(m, side, k)
    return None if q is None else q[1] - q[0]


def leads(m, side, k):
    """Whether this side was the favourite at minute k: its own price above the other side's. A dead heat is
    neither side leading, as favourite() has it."""
    q = m["q"].get(k)
    if not q or q[0] is None or q[1] is None:
        return False
    yes, no = q[1], round(1 - q[0], 4)
    return yes > no if side == "yes" else no > yes


def path(m, side, minute):
    """(minute, mid) for every quoted minute up to and including the entry minute, in order."""
    return [(k, mid(m, side, k)) for k in range(1, minute + 1) if mid(m, side, k) is not None]


# ------------------------------------------------------------------ the eight features


def mean_spread_5_8(m, side, minute):
    xs = [spread(m, side, k) for k in range(minute - BACK, minute + 1)]
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


def spread_trend(m, side, minute):
    now, before = spread(m, side, minute), spread(m, side, minute - BACK)
    return None if now is None or before is None else now - before


def rel_spread(m, side, minute, medians):
    """The entry spread against this series' own normal. `medians` is fitted on the train half and reused."""
    now, med = spread(m, side, minute), medians.get(m["series"])
    return None if now is None or not med else now / med


def fav_minutes(m, side, minute):
    if not path(m, side, minute):
        return None
    return sum(leads(m, side, k) for k in range(1, minute + 1))


def travel(m, side, minute):
    p = path(m, side, minute)
    if len(p) < 2:
        return None
    return sum(abs(p[i][1] - p[i - 1][1]) for i in range(1, len(p)))


def worst_dip(m, side, minute):
    p = path(m, side, minute)
    if not p:
        return None
    return mid(m, side, minute) - min(x for _, x in p)


def since_coinflip(m, side, minute):
    p = path(m, side, minute)
    if not p:
        return None
    flips = [k for k, x in p if x <= COINFLIP]
    return minute - max(flips) if flips else minute


def staleness(m, side, minute):
    q = own(m, side, minute)
    if q is None:
        return None
    n = 1
    for k in range(minute - 1, 0, -1):
        if own(m, side, k) != q:
            break
        n += 1
    return n


def value(name, m, side, minute, medians):
    """One feature by name. rel_spread is the only one needing the fitted medians."""
    if name == "rel_spread":
        return rel_spread(m, side, minute, medians)
    return globals()[name](m, side, minute)


def series_medians(bets):
    """Each series' median entry spread, from the train half only (FILTER_SEARCH_PREREG.md step 2)."""
    by = {}
    for b in bets:
        if b["spread"] is not None:
            by.setdefault(b["series"], []).append(b["spread"])
    return {s: st.median(v) for s, v in by.items() if v}


# ------------------------------------------------------------------ collecting candidate bets

LIVE = {**sb.LIVE[0], "sizing": "flat"}   # the bot's rule: 92c floor, both warning signs, minute 8
SLIP = sb.SCENARIOS["live"]               # 0.4c over the ask, where live fills land
STAKE = 10.0


def outcome(m, side, top):
    """$10 flat on this favourite at the live fill gap: (cents per $1 staked, won)."""
    price = min(top + SLIP, sb.HI)
    c = STAKE / price
    won = (side == "yes") == m["yes"]
    pnl = (c if won else 0.0) - c * price - sb.fee(c, price)
    return pnl / (c * price) * 100, won


def collect(windows, medians):
    """Every bet the 92c floor alone would take, with its eight features, its outcome, and whether the two
    warning signs the bot uses today would have skipped it. The floor-only and bot-kept sets come from
    choose(), so the selection is the project's own tested code rather than a second copy of it."""
    out = []
    for t in sorted(windows):
        ms = windows[t]
        every, _ = sb.choose({**LIVE, "skip": ()}, ms)
        kept, _ = sb.choose({**LIVE, "skip": ("spread", "late")}, ms)
        now = {(m["ticker"], side) for m, side, _ in kept}
        for m, side, top in every:
            cents, won = outcome(m, side, top)
            row = {"window": t, "series": m["series"], "side": side, "top": top, "won": won,
                   "cents": cents, "keptNow": (m["ticker"], side) in now,
                   "spread": spread(m, side, LIVE["minute"])}
            for name in FEATURES:
                row[name] = value(name, m, side, LIVE["minute"], medians)
            out.append(row)
    return out


def score(rows):
    """Cents per $1 over these bets, with a 95% interval clustered by window: bets in one window move
    together, so each window counts once, not once per bet."""
    if not rows:
        return {"bets": 0, "cents": None, "lo": None, "hi": None, "losses": 0}
    by = {}
    for r in rows:
        by.setdefault(r["window"], []).append(r["cents"])
    means = [st.mean(v) for v in by.values()]
    mu = st.mean([r["cents"] for r in rows])
    n = len(means)
    se = (st.stdev(means) / (n ** 0.5)) if n > 1 else None
    return {"bets": len(rows), "windows": n, "losses": sum(not r["won"] for r in rows),
            "cents": round(mu, 3),
            "lo": round(mu - 1.96 * se, 3) if se else None,
            "hi": round(mu + 1.96 * se, 3) if se else None}


def passes(rows, name, cut):
    """The bets a single candidate filter keeps: its warning side is the one named in FEATURES."""
    worse = FEATURES[name]["worse"]
    out = []
    for r in rows:
        v = r[name]
        if v is None:
            out.append(r)            # no reading is not a warning sign; the bot bets when it cannot tell
        elif (v < cut) if worse == "high" else (v > cut):
            out.append(r)
    return out


def fit(rows, baseline_bets):
    """On the TRAIN half only: for each feature, the threshold with the best cents per $1 among those keeping
    at least as many bets as the bot's own filters keep. Returns the table and the count of thresholds tried."""
    table, tried = [], 0
    for name in FEATURES:
        vals = sorted(r[name] for r in rows if r[name] is not None)
        if len(vals) < 100:
            table.append({"feature": name, "note": "too few readings"})
            continue
        best = None
        for pct in range(5, 100, 5):
            cut = vals[int(len(vals) * pct / 100)]
            tried += 1
            kept = passes(rows, name, cut)
            if len(kept) < baseline_bets:
                continue
            s = score(kept)
            if s["cents"] is not None and (best is None or s["cents"] > best["cents"]):
                best = {**s, "cut": cut, "pct": pct}
        table.append({"feature": name, **(best or {"note": "no threshold kept enough bets"})})
    return table, tried


def main():
    print(__doc__)
    windows, first, last = sb.load()
    mid_ts = first + (last - first) // 2
    train_w = {t: ms for t, ms in windows.items() if t < mid_ts}
    test_w = {t: ms for t, ms in windows.items() if t >= mid_ts}
    when = sb.datetime.fromtimestamp(mid_ts, sb.timezone.utc)
    print(f"train {len(train_w)} windows, test {len(test_w)} windows, split at {when:%b %d %Y}\n")

    # the per-series medians rel_spread needs come from the train half alone, then are reused unchanged
    pre = collect(train_w, {})
    medians = series_medians(pre)
    train = collect(train_w, medians)
    base_train = score([r for r in train if r["keptNow"]])
    print(f"TRAIN: {len(train)} bets pass the 92c floor; the bot's two signs keep {base_train['bets']}")
    print(f"  floor alone        {score(train)['cents']:+.3f}c/$1   {score(train)['bets']:>6} bets")
    print(f"  the bot's 2 signs  {base_train['cents']:+.3f}c/$1   {base_train['bets']:>6} bets"
          f"   [{base_train['lo']:+.2f}, {base_train['hi']:+.2f}]\n")

    table, tried = fit(train, base_train["bets"])
    print(f"best threshold per feature on the TRAIN half, keeping at least {base_train['bets']} bets"
          f" ({tried} thresholds tried):")
    for row in sorted(table, key=lambda r: -(r.get("cents") or -99)):
        if "cents" not in row:
            print(f"  {row['feature']:<17} {row['note']}")
        else:
            print(f"  {row['feature']:<17} {row['cents']:+.3f}c/$1  {row['bets']:>6} bets"
                  f"  cut {row['cut']:.4g} at p{row['pct']}")

    picks = [r for r in sorted(table, key=lambda r: -(r.get("cents") or -99))
             if "cents" in r and r["cents"] > base_train["cents"]][:2]
    print(f"\npicked on the train half: {[p['feature'] for p in picks] or 'nothing beat the bot'}")

    test = collect(test_w, medians)
    base_test = score([r for r in test if r["keptNow"]])
    print(f"\nTEST half, scored once. {when:%b %d} on:\n")
    print(f"  {'variant':<30}{'bets':>8}{'c/$1':>9}{'95% interval':>20}{'losses':>8}")
    results = {"bot": base_test}
    print(f"  {'the bot (both signs)':<30}{base_test['bets']:>8}{base_test['cents']:>+9.3f}"
          f"   [{base_test['lo']:+.2f}, {base_test['hi']:+.2f}]{base_test['losses']:>8}")
    s = score(test)
    print(f"  {'the 92c floor alone':<30}{s['bets']:>8}{s['cents']:>+9.3f}"
          f"   [{s['lo']:+.2f}, {s['hi']:+.2f}]{s['losses']:>8}")
    results["floorOnly"] = s
    for p in picks:
        kept = passes(test, p["feature"], p["cut"])
        s = score(kept)
        results[p["feature"]] = {**s, "cut": p["cut"]}
        verdict = ("BEATS the bot" if s["bets"] >= base_test["bets"] and s["cents"] > base_test["cents"]
                   else "no")
        print(f"  {p['feature'] + ' (replaces)':<30}{s['bets']:>8}{s['cents']:>+9.3f}"
              f"   [{s['lo']:+.2f}, {s['hi']:+.2f}]{s['losses']:>8}   {verdict}")
    json.dump({"split": when.isoformat(), "thresholdsTried": tried, "train": table,
               "picked": [p["feature"] for p in picks], "test": results},
              open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
