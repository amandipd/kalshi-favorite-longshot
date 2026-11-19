"""Does weighting bets by price beat flat sizing? Weights fitted on the first half, scored on the second.

The measured edge falls as the favourite gets dearer, but so does the loss rate, so Kelly sizing (bet in
proportion to edge divided by risk) says the opposite of what edge-per-dollar alone suggests. This fits the
band weights on the first half of the history and scores them once on the second, against flat sizing, on
profit, deepest fall and worst window.

    python band_weight_test.py
"""
import json
import statistics as st

import strategies_backtest as sb

BASE = {**sb.LIVE[0], "start": 2000.0}      # the live bot's rule, from $2,000
BANDS = (92, 94, 96, 98)


def edges(windows, t0, hours, lo, hi):
    """Per-band cents per $1 and mean quote, from a flat $10 replay over these windows."""
    r = sb.run({**BASE, "sizing": "flat", "start": sb.EDGE_BANK}, windows, sb.SCENARIOS["live"], t0, hours)
    out = {}
    for g in r["byBand"]:
        b = int(g["key"].split("–")[0])
        if g["staked"] > 0:
            out[b] = {"cents": g["pnl"] / g["staked"] * 100, "n": g["n"],
                      "lossRate": 1 - g["wins"] / g["n"], "staked": g["staked"]}
    return out


def kelly(e):
    """Kelly weight for a band: edge x price / (1 - price), normalised to mean 1 over the bands present.
    p is taken as the band's midpoint, so 92-94c -> 0.93."""
    raw = {}
    for b in BANDS:
        if b not in e:
            continue
        p = (b + 1) / 100
        raw[b] = max(0.0, e[b]["cents"] / 100) * p / (1 - p)
    m = st.mean(raw.values()) if raw else 0
    return {b: (v / m if m else 1.0) for b, v in raw.items()}


def main():
    windows, first, last = sb.load()
    mid = first + (last - first) // 2
    train = {t: ms for t, ms in windows.items() if t < mid}
    test = {t: ms for t, ms in windows.items() if t >= mid}
    hrs = lambda a, b: int((b + 900 - a) // sb.HOUR) + 1
    print(f"train {len(train)} windows, test {len(test)} windows "
          f"(split at {sb.datetime.fromtimestamp(mid, sb.timezone.utc):%b %d})\n")

    e = edges(train, first, hrs(first, mid), BASE.get("lo", sb.LO), sb.HI)
    print("TRAIN half, per band (this is all the weights may use):")
    for b in BANDS:
        if b in e:
            print(f"  {b}-{b+2}c  {e[b]['n']:>6} bets  loses {e[b]['lossRate']*100:5.2f}%  {e[b]['cents']:+.3f}c/$1")

    kw = kelly(e)
    half = {b: (1 + w) / 2 for b, w in kw.items()}
    dear = {92: 1.0, 94: 1.0, 96: 1.0, 98: 0.5}
    print("\nweights fitted on the train half:")
    print("  kelly     ", {b: round(w, 3) for b, w in kw.items()})
    print("  half kelly", {b: round(w, 3) for b, w in half.items()})
    print("  cap dear  ", dear)

    print(f"\nTEST half, scored once. {sb.datetime.fromtimestamp(mid, sb.timezone.utc):%b %d} on, "
          f"from ${BASE['start']:.0f}, live-like fills:\n")
    print(f"  {'variant':<14}{'bets':>7}{'final $':>11}{'profit $':>11}{'deepest fall':>14}"
          f"{'worst window':>14}{'staked $':>12}")
    out = {}
    for name, strat in (("flat (now)", BASE),
                        ("kelly", {**BASE, "bandWeights": kw}),
                        ("half kelly", {**BASE, "bandWeights": half}),
                        ("cap dear 50%", {**BASE, "bandWeights": dear})):
        r = sb.run(strat, test, sb.SCENARIOS["live"], mid, hrs(mid, last))
        staked = sum(g["staked"] for g in r["byBand"])
        out[name] = {"bets": r["bets"], "final": r["final"], "maxDD": r["maxDD"],
                     "worstWindow": r["worstWindow"], "staked": round(staked, 2)}
        print(f"  {name:<14}{r['bets']:>7}{r['final']:>11,.2f}{r['final']-BASE['start']:>11,.2f}"
              f"{r['maxDD']*100:>13.1f}%{r['worstWindow']:>14,.2f}{staked:>12,.0f}")
    json.dump({"trainEdges": e, "weights": {"kelly": kw, "half": half, "capDear": dear}, "test": out},
              open("band_weight_test.json", "w"), indent=1)
    print("\nwrote band_weight_test.json")


if __name__ == "__main__":
    main()
