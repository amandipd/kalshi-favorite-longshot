"""Does the backtest's minute-4 price peek past 4:00?

The history point stamped 3:00 holds the book at the end of minute 4, but live polling (live.py) shows it keeps
updating until about 4:08. A bot buying at 4:00 sees only what the point said by then. This compares, for every point
stamped 3:00 that live.py watched across 4:00, the value visible at 4:00 with its final value, and counts the markets
where the 90-99c favourite bet (side or price) would differ. Prices only.

    python peek.py
"""
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def bet(lp, sp):
    if lp is None or sp is None:
        return None
    top = max(lp, sp)
    return ("yes" if lp > sp else "no", top) if 0.90 <= top <= 0.99 else None


def main():
    obs = defaultdict(list)
    for fn in ("live_timing.jsonl", "live.jsonl"):
        with open(os.path.join(HERE, fn)) as f:
            for line in f:
                r = json.loads(line)
                if r["k"] == "h":
                    for t, lp, sp in r["pts"]:
                        obs[(r["slug"], t)].append((r["w"], lp, sp))
    watched = changed = either = differs = 0
    for (slug, t), v in obs.items():
        v.sort()
        seen, late = [x for x in v if x[0] <= 240], [x for x in v if x[0] > 240]
        if t != 180 or not seen or not late:
            continue
        a, z = seen[-1][1:], late[-1][1:]
        watched += 1
        changed += a != z
        if bet(*a) or bet(*z):
            either += 1
            differs += bet(*a) != bet(*z)
    out = {"points_watched_across_4_00": watched, "changed_after_4_00": changed,
           "markets_with_a_90_99c_favourite": either, "bet_or_price_differs": differs}
    print(out)
    with open(os.path.join(HERE, "peek.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
