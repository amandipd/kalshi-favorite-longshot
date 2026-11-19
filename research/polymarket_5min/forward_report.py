"""Score the forward paper test (PREREG_FORWARD.md) once it is done.

    python forward_report.py --health   # counts and coverage only: no results are read
    python forward_report.py            # fetch every recorded market's result, score, write forward_score.json

The full run reads each recorded market's result and final price history with fetch.one (public GETs, about 8 a
second), cached in forward_results.jsonl. It scores the bets the recorder made from what it saw before 3:58 (the
reading), and, for the peek effect, the bets the backtest would have made on the same windows from the history's
final values.
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402
import forward as F  # noqa: E402
import score as S  # noqa: E402

RESULTS = "forward_results.jsonl"


def verdict(s):
    if not s.get("bets") or s.get("c_per_1") is None:
        return "UNCLEAR"
    if s["c_per_1"] <= 0 or (s["hi"] is not None and s["hi"] < 0.5):
        return "FAIL"
    if s["c_per_1"] > 0.5 and s["lo"] is not None and s["lo"] > 0:
        return "PASS"
    return "UNCLEAR"


def load():
    with open(F.path(F.OUT)) as f:
        return [json.loads(line) for line in f if line.strip()]


def health(recs):
    starts = sorted({r["start"] for r in recs})
    span = (starts[-1] - starts[0]) // 300 + 1 if starts else 0
    why = Counter(r["decision"]["why"] for r in recs)
    seen = [r["seen_sw"] for r in recs if r.get("seen_sw") is not None]
    out = {"records": len(recs), "windows": len(starts), "windows_passed": int(span),
           "coverage": round(len(starts) / span, 3) if span else None, "bets": why.get("bet", 0), "why": dict(why),
           "seen_at_s_median": float(np.median(seen)) if seen else None,
           "seen_at_s_max": max(seen) if seen else None,
           "books_with_offers": sum(1 for r in recs if (r.get("book") or {}).get("offers")),
           "done": os.path.exists(F.path(F.DONE))}
    print(json.dumps(out, indent=1))
    return out


def results(recs):
    """{slug: fetch.one record}, fetching what isn't cached yet."""
    have = {}
    p = F.path(RESULTS)
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                r = json.loads(line)
                have[r["slug"]] = r
    todo = [(r["coin"], r["start"]) for r in recs if r["slug"] not in have]
    with open(p, "a") as f, ThreadPoolExecutor(6) as pool:
        for r in pool.map(lambda ct: fetch.one(*ct), todo):
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
            have[r["slug"]] = r
    return have


def bets_from(rows):
    """Arrays (top, wins, start, coin, side_yes) for rows of (decision, result) with a bet and a result."""
    rows = [(d, r) for d, r in rows if d["bet"] and r.get("yes") is not None]
    top = np.array([d["top"] for d, _ in rows], dtype=float)
    side = np.array([d["side"] == "yes" for d, _ in rows], dtype=bool)
    yes = np.array([bool(r["yes"]) for _, r in rows], dtype=bool)
    return top, side == yes, np.array([r["start"] for _, r in rows]), np.array([r["coin"] for _, r in rows]), side


def scored(top, wins, start, coin):
    if not len(top):
        return {"bets": 0, "c_per_1": None, "lo": None, "hi": None}
    pnl, cost, c = S.bet(top, wins)
    s = S.stats(pnl, cost, start)
    s.update({"lost": int((~wins).sum()), "implied": round(float((1 - top).sum()), 1)})
    lc = S.leave_one_out(pnl, cost, coin)
    ld = S.leave_one_out(pnl, cost, S.day_of(start))
    s.update({"loo_coin": list(lc), "loo_day": list(ld)})
    return s


def depth(rec, dec):
    b = rec.get("book") or {}
    if dec["side"] == "yes" and b.get("offers"):
        lv = [q for p, q in b["offers"] if abs(p - dec["top"]) < 1e-9]
    elif dec["side"] == "no" and b.get("bids"):
        lv = [q for p, q in b["bids"] if abs(round(1 - p, 4) - dec["top"]) < 1e-9]
    else:
        return None
    return round(sum(lv) * dec["top"], 2)


def main():
    recs = load()
    h = health(recs)
    res = results(recs)
    fwd = [(r["decision"], res[r["slug"]]) for r in recs]
    peek = [(F.decide(res[r["slug"]].get("h") or []), res[r["slug"]]) for r in recs]
    out = {"health": h}
    top, wins, start, coin, side = bets_from(fwd)
    out["reading"] = scored(top, wins, start, coin)
    out["verdict"] = verdict(out["reading"])
    out["by_coin"] = {c: scored(top[coin == c], wins[coin == c], start[coin == c], coin[coin == c])
                      for c in F.PRE}
    out["by_side"] = {k: scored(top[m], wins[m], start[m], coin[m]) for k, m in (("yes", side), ("no", ~side))}
    at99 = np.isclose(top, 0.99)
    out["at_99c"] = scored(top[at99], wins[at99], start[at99], coin[at99])
    pt, pw, ps_, pc, _ = bets_from(peek)
    out["peek_view_same_windows"] = scored(pt, pw, ps_, pc)
    dep = [x for x in (depth(r, r["decision"]) for r in recs if r["decision"]["bet"]) if x is not None]
    out["depth_dollars_at_ask"] = {"books": len(dep), "median": float(np.median(dep)) if dep else None,
                                   "p10": float(np.percentile(dep, 10)) if dep else None}
    with open(F.path("forward_score.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in ("verdict", "reading", "peek_view_same_windows")}, indent=1))


if __name__ == "__main__":
    if "--health" in sys.argv:
        health(load())
    else:
        main()
