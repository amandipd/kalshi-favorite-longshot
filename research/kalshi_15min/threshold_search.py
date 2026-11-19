"""Are the two warning signs set at the right thresholds? THRESHOLD_SEARCH_PREREG.md, scored.

Three numbers carry the live bot's entire edge: a 2c spread cut, a 10c jump cut and a 50c coin-flip cut. Each
was chosen once in October and never scored against an alternative. This searches each on the first half of
the history with the other two held at today's value, picks by total profit at a flat $10 stake, then scores
the chosen combination once on the second half against today's settings.

Total profit, not cents per $1, because cents per $1 alone always favours the pickiest threshold -- it rises
by shrinking the business. Bet count is printed beside every number so the trade-off stays visible.

    python threshold_search.py
"""
import json

import strategies_backtest as sb

BASE = {**sb.LIVE[0], "sizing": "flat", "start": sb.EDGE_BANK}
NOW = {"spreadCut": sb.SPREAD_CUT, "jumpCut": sb.JUMP_CUT, "flipCut": sb.FLIP_CUT}
GRID = {
    "spreadCut": [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, None],
    "jumpCut": [0.05, 0.075, 0.10, 0.125, 0.15, 0.20, None],
    "flipCut": [0.40, 0.45, 0.50, 0.55, 0.60, None],
}
OUT = "threshold_search.json"


def score(strat, windows, t0, hours):
    r = sb.run(strat, windows, sb.SCENARIOS["live"], t0, hours)
    staked = sum(g["staked"] for g in r["byBand"])
    return {"bets": r["bets"], "pnl": round(r["final"] - sb.EDGE_BANK, 2),
            "cents": round((r["final"] - sb.EDGE_BANK) / staked * 100, 3) if staked else None,
            "staked": round(staked, 2), "maxDD": r["maxDD"]}


def show(name, s):
    return (f"  {name:<22}{s['bets']:>7} bets   {s['cents']:+.3f}c/$1   ${s['pnl']:>9,.2f}"
            f"   deepest fall {s['maxDD']*100:>5.1f}%")


def main():
    print(__doc__)
    windows, first, last = sb.load()
    mid = first + (last - first) // 2
    train = {t: ms for t, ms in windows.items() if t < mid}
    test = {t: ms for t, ms in windows.items() if t >= mid}
    hrs = lambda a, b: int((b + 900 - a) // sb.HOUR) + 1
    when = sb.datetime.fromtimestamp(mid, sb.timezone.utc)
    print(f"train {len(train)} windows, test {len(test)} windows, split {when:%b %d %Y}\n")

    base_train = score({**BASE, **NOW}, train, first, hrs(first, mid))
    print("TRAIN half. today's settings first, then each number on its own:\n")
    print(show("today (2c/10c/50c)", base_train))
    picked, tried, table = dict(NOW), 0, {}
    for key, vals in GRID.items():
        print(f"\n  {key}:")
        rows = []
        for v in vals:
            tried += 1
            s = score({**BASE, **NOW, key: v}, train, first, hrs(first, mid))
            rows.append((v, s))
            flag = "  <- today" if v == NOW[key] else ""
            print(show(f"    {'off' if v is None else v}", s) + flag)
        best = max(rows, key=lambda r: r[1]["pnl"])
        table[key] = [{"value": v, **s} for v, s in rows]
        picked[key] = best[0]
        if best[0] != NOW[key]:
            print(f"    -> train prefers {'off' if best[0] is None else best[0]}"
                  f" (${best[1]['pnl']:,.2f} vs ${base_train['pnl']:,.2f})")
        else:
            print(f"    -> train keeps today's value")

    print(f"\n{tried} values tried. train picked: "
          f"{ {k: ('off' if v is None else v) for k, v in picked.items()} }")

    print(f"\nTEST half, scored once. {when:%b %d} on:\n")
    a = score({**BASE, **NOW}, test, mid, hrs(mid, last))
    b = score({**BASE, **picked}, test, mid, hrs(mid, last))
    print(show("today (2c/10c/50c)", a))
    print(show("what train picked", b))
    better = b["pnl"] > a["pnl"]
    print(f"\n  verdict: {'the new settings win' if better else 'TODAY STANDS - no change'}"
          f"  ({b['pnl'] - a['pnl']:+,.2f} on the test half)")
    json.dump({"split": when.isoformat(), "tried": tried, "today": NOW, "picked": picked,
               "train": table, "trainBase": base_train, "test": {"today": a, "picked": b}},
              open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
