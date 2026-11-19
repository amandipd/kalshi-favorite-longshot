"""Quick checks on the live rule that the other lab scripts don't cover, each at $10 a bet with live-like fills:

  series   the live rule market by market, Dec 10 - Jul 17 against Jul 18 on: does any market lose in both?
  second   a second chance: a market that didn't qualify at minute 8 bets the first later minute (9-12) it does
  choppy   skip a favourite whose mid swung a lot over minutes 1-8 (high minus low), threshold picked on one half
           and tested on the other

    python lab/extras.py
"""
import json
import os

import numpy as np

import common as C

HERE = os.path.dirname(os.path.abspath(__file__))


def stats(d, m, side_yes, top):
    pnl, cost = C.bet(top[m], C.won(d, side_yes)[m])
    return C.by_period(pnl, cost, d["open_ts"][m])


def series(d):
    m, side_yes, top = C.live_rule(d)
    out = {}
    for s in np.unique(d["series"][m]):
        k = m & (d["series"] == s)
        out[s] = stats(d, k, side_yes, top)
    return out


def second(d, last=12):
    """Bets at minute 8 as the live rule does; a market that didn't qualify then bets at the first minute 9..last that
    it does (same band, warning signs taken at that minute)."""
    m8, sy8, top8 = C.live_rule(d, M=8)
    taken = m8.copy()
    extra = []
    for M in range(9, last + 1):
        m, sy, top = C.live_rule(d, M=M)
        new = m & ~taken
        extra.append((M, new, sy, top))
        taken |= new
    rows = {"minute 8": stats(d, m8, sy8, top8)}
    allp, allc, allw = [], [], []
    for M, new, sy, top in extra:
        pnl, cost = C.bet(top[new], C.won(d, sy)[new])
        rows[f"first at minute {M}"] = C.by_period(pnl, cost, d["open_ts"][new])
        allp.append(pnl); allc.append(cost); allw.append(d["open_ts"][new])
    pnl, cost = C.bet(top8[m8], C.won(d, sy8)[m8])
    allp.append(pnl); allc.append(cost); allw.append(d["open_ts"][m8])
    rows["minute 8 + second chance"] = C.by_period(np.concatenate(allp), np.concatenate(allc), np.concatenate(allw))
    return rows


def choppy(d):
    m, side_yes, top = C.live_rule(d)
    mids = np.stack([np.mean(C.own(d, side_yes, k), axis=0) for k in range(1, 9)], axis=1)
    rng = np.nanmax(mids, axis=1) - np.nanmin(mids, axis=1)
    out = {}
    for x in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        keep = m & ~(rng > x)
        out[f"skip swing > {x:.1f}"] = {"skipped": int((m & (rng > x)).sum()), **stats(d, keep, side_yes, top)}
        cut = m & (rng > x)
        out[f"only swing > {x:.1f}"] = stats(d, cut, side_yes, top)
    return out


def main():
    d = C.load()
    out = {"series": series(d), "second": second(d), "choppy": choppy(d)}
    print("LIVE RULE BY MARKET (pre = Dec 10-Jul 17, post = Jul 18 on)")
    for s, r in sorted(out["series"].items(), key=lambda kv: kv[1]["all"]["perBet"] or 0):
        print(f"  {s:<16} pre {C.fmt(r['pre'])}   post {C.fmt(r['post'])}")
    print("\nSECOND CHANCE")
    for k, r in out["second"].items():
        print(f"  {k:<26} all {C.fmt(r['all'])}  pre {C.fmt(r['pre'])}  post {C.fmt(r['post'])}")
    print("\nCHOPPY (mid's high-low over minutes 1-8)")
    for k, r in out["choppy"].items():
        print(f"  {k:<18} all {C.fmt(r['all'])}  pre {C.fmt(r['pre'])}  post {C.fmt(r['post'])}")
    with open(os.path.join(HERE, "extras.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
