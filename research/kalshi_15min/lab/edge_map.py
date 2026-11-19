"""Where the edge lives: entry minute x price, time of day, and how a window's crypto bets lose together.

Strategy: the live bot's rule (common.live_rule) - at the end of minute M buy the favourite of every crypto, metals and
energy market whose ask is in the band, skipping 2c+ spreads and late favourites, no bets in a Fed decision's windows,
held to settlement - with one thing changed at a time: the entry minute (4-14), the price band (80-99.9c in seven
bands), the side (the underdog instead), the hour or kind of window, or at most K crypto bets a window.

Per bet: $10, whole contracts, the recorded ask plus 0.4c and the taker fee (common.bet), cents per $10 staked with a
95% range clustered by window. "pre" is Dec 10 - Jul 17, which no rule was chosen on; "post" is Jul 18 - Oct 8, and
"clean" is post without Aug 24 - Sep 23, the month the live rule's filters were chosen on. Every rule change is chosen
on one half and scored on the other, both ways round.

  1. Edge map: minute 4-14 x band, with and without the live filters, by group: bets, won vs priced, cents per $10.
  2. The underdog in the same markets at its own ask: the longshot half of the bias.
  3. Timing on the live rule: ET hour, weekday vs weekend, the windows around the 8:30 and 10:00 ET releases.
  4. Concentration: how a window's crypto favourites lose together, and "at most K crypto bets a window" (K = 1-3,
     keeping the dearest or the tightest) at the bot's own sizing from $500: 3% a bet, 20% a window, whole contracts.

    python edge_map.py      -> edge_map.json (about a minute, under 300 MB)
"""
import json
import math
import os
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = os.path.join(C.HERE, "edge_map.json")
MINUTES = tuple(range(4, 15))
BANDS = ((0.80, 0.85), (0.85, 0.90), (0.90, 0.92), (0.92, 0.94), (0.94, 0.96), (0.96, 0.98), (0.98, 0.999))
LIVE = ("spread", "late")
SPLITS = {"post": ("before", "build", "paper"), "clean": ("before", "paper")}
KEYS = ("all", "pre", "post", "clean", "build")
START = 500.0
CAP_PCT, WINDOW_CAP, MIN_BET, FEE_ROOM = 0.015, 0.10, 1.0, 0.10   # strategies_backtest's live bot (1.5%/10%, Oct 15)
CAPS, PICKS = (1, 2, 3), ("price", "spread")
# Weekday windows by their ET opening time: the two that touch each release (the one closing on it, the one opening on
# it), and the 9:30 stock-market open. Not every weekday has a release at these times, so these are the slots, not a
# calendar of releases.
SLOTS = {"8:15 (closes on the 8:30 release)": (8, 15), "8:30 (opens on it)": (8, 30), "9:30 (stocks open)": (9, 30),
         "9:45 (closes on the 10:00 release)": (9, 45), "10:00 (opens on it)": (10, 0)}


def band_label(lo, hi):
    return f"{lo * 100:g}-{hi * 100:g}"


def cells():
    """(label, lo, hi inclusive) of each band, then the live rule's whole 90-99.9c band. A band stops just under the
    next one's floor; prices are whole tenths of a cent, so nothing falls between."""
    out = [(band_label(lo, hi), lo, hi if hi == 0.999 else hi - 1e-6) for lo, hi in BANDS]
    return out + [(band_label(C.LO, C.HI), C.LO, C.HI)]


def band_of(top):
    """Each price's band label ("" outside 80-99.9c)."""
    out = np.full(len(top), "", dtype="U8")
    for label, lo, hi in cells()[:-1]:
        out[(top >= lo) & (top <= hi)] = label
    return out


def masks(t):
    """{key: bool mask} of the periods in KEYS over window open times t."""
    p = C.period_of(t)
    out = {"all": np.ones(len(t), bool), "pre": p == "pre", "build": p == "build"}
    out.update({k: np.isin(p, v) for k, v in SPLITS.items()})
    return out


def stats(pnl, cost, t, wins=None, price=None):
    """common.summary() over each period in KEYS, with the share won and the average price paid when given."""
    out = {}
    for k, s in masks(t).items():
        r = C.summary(pnl[s], cost[s], t[s])
        if wins is not None and s.any():
            r["win"], r["price"] = float(wins[s].mean()), float(price[s].mean())
        out[k] = r
    return out


def spread(d, side_yes, M):
    """The side's own ask minus its bid at minute M, to 4 places, so float noise can't break a tie (0.94 - 0.93 and
    0.96 - 0.95 are both 1c)."""
    bid, ask = C.own(d, side_yes, M)
    return np.round(ask - bid, 4)


def underdog_ask(d, side_yes, M):
    """The other side's own ask at the end of minute M: 1 minus the favourite's own bid."""
    return C.own(d, ~side_yes, M)[1]


def run_bets(d, mask, top, wins, slip=C.SLIP):
    """$10 bets on mask: (pnl, cost, open times, wins, price), every bet kept (whole contracts at 99.9c are still 10)."""
    pnl, cost = C.bet(top[mask], wins[mask], slip=slip)
    assert len(pnl) == mask.sum()
    return pnl, cost, d["open_ts"][mask], wins[mask], top[mask]


def cap_mask(d, mask, top, sprd, cap, pick):
    """mask with at most `cap` crypto bets a window: the dearest (pick "price", ties to the first listed, as
    strategies_backtest's one-per-window account) or the tightest spread (then the dearest). Other groups untouched."""
    out = mask.copy()
    if cap is None:
        return out
    idx = np.flatnonzero(mask & (d["group"] == "crypto"))
    t = d["open_ts"][idx]
    keys = (idx, -top[idx], t) if pick == "price" else (idx, -top[idx], sprd[idx], t)
    s = idx[np.lexsort(keys)]
    ts = d["open_ts"][s]
    first = np.r_[True, ts[1:] != ts[:-1]]
    rank = np.arange(len(s)) - np.maximum.accumulate(np.where(first, np.arange(len(s)), 0))
    out[s[rank >= cap]] = False
    return out


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def floor_cents(x):
    return math.floor(x * 100 + 1e-6) / 100


def replay(d, mask, top, wins, start=START, slip=C.SLIP, window_cap=WINDOW_CAP):
    """The live bot's sizing on the bets in mask, window by window (strategies_backtest.run's capped, whole-contract
    account): 1.5% of the bankroll a bet, a window's bets together at most 10% of it, the order skipped if the cash
    isn't there, broke when 1.5% is under $1 or the bankroll under it plus $0.10. Sized on the bets the window places.
    window_cap: swaps that 10% for another."""
    idx = np.flatnonzero(mask)
    idx = idx[np.argsort(d["open_ts"][idx], kind="stable")]
    t = d["open_ts"][idx]
    bal = peak = start
    dd = worst = worst_pct = 0.0
    n = 0
    broke = None
    for g in np.split(idx, np.flatnonzero(np.diff(t)) + 1) if len(idx) else ():
        first = floor_cents(min(bal * CAP_PCT, bal * window_cap))
        if first < MIN_BET or bal < first + FEE_ROOM:
            broke = int(d["open_ts"][g[0]])
            break
        stake = floor_cents(min(bal * CAP_PCT, bal * window_cap / max(len(g), 1)))
        cash, wp = bal, 0.0
        if stake >= MIN_BET:
            for i in g:
                price = min(float(top[i]) + slip, 0.999)
                c = math.floor(stake / price + 1e-9)
                if c <= 0:
                    continue
                cost, f = c * price, fee(c, price)
                if cash < cost + f:
                    continue
                cash -= cost + f
                wp += (c if wins[i] else 0.0) - cost - f
                n += 1
        worst_pct = min(worst_pct, wp / bal)
        bal += wp
        worst = min(worst, wp)
        peak = max(peak, bal)
        dd = max(dd, 1 - bal / peak)
    return {"start": start, "final": 0.0 if broke else round(bal, 2), "bets": n, "maxDD": 1.0 if broke else dd,
            "worstWindow": round(worst, 2), "worstWindowPct": worst_pct,
            "broke": broke and datetime.fromtimestamp(broke, C.ET).strftime("%Y-%m-%d")}


def slot_mask(d, h, mi):
    """The weekday windows opening at h:mi ET."""
    uniq, inv = np.unique(d["open_ts"], return_inverse=True)
    et = [datetime.fromtimestamp(int(x), C.ET) for x in uniq]
    return np.array([e.weekday() < 5 and (e.hour, e.minute) == (h, mi) for e in et], bool)[inv]


def holdout(seg, pnl, cost, t, a, b):
    """Choose on period a the segments to skip (those whose edge there is below zero), score on b: the edge on b of all
    bets, of the ones kept and of the ones skipped. A skip rule holds up when the skipped bets' range on b is below 0."""
    ma, mb = masks(t)[a], masks(t)[b]
    drop = []
    for s in np.unique(seg):
        x = C.summary(pnl[ma & (seg == s)], cost[ma & (seg == s)], t[ma & (seg == s)])
        if x["bets"] and x["mu"] < 0:
            drop.append(s)
    out_ = np.isin(seg, drop)
    part = lambda m: C.summary(pnl[mb & m], cost[mb & m], t[mb & m])
    return {"chosenOn": a, "scoredOn": b, "skip": [str(s) for s in drop], "all": part(np.ones(len(seg), bool)),
            "kept": part(~out_), "skipped": part(out_)}


def edge_map(d):
    """1 and 2: every minute x band, with and without the live filters, by group, for the favourite and the underdog."""
    groups = ("all",) + C.EDGE_GROUPS
    rows = []
    for M in MINUTES:
        for live in (True, False):
            for label, lo, hi in cells():
                m, sy, top = C.live_rule(d, M, lo, hi, skip=LIVE if live else (), fed=live)
                w = C.won(d, sy)
                bid, ask = C.own(d, sy, M)
                dog = underdog_ask(d, sy, M)
                for g in groups:
                    mg = m if g == "all" else m & (d["group"] == g)
                    if not mg.any():
                        continue
                    pnl, cost, t, wins, price = run_bets(d, mg, top, w)
                    fav = stats(pnl, cost, t, wins, price)
                    fav["all"]["mid"] = float(np.nanmean((bid + ask)[mg] / 2))
                    md = mg & (dog > 0)
                    lose = ~w
                    dpnl, dcost, dt, dwins, dprice = run_bets(d, md, dog, lose)
                    rows.append({"minute": M, "live": live, "band": label, "group": g,
                                 "fav": fav, "dog": stats(dpnl, dcost, dt, dwins, dprice)})
    return rows


def timing(d):
    """3: the live rule (minute 8, 90-99.9c) by ET hour, weekday vs weekend and release slot, each chosen on one half."""
    m, sy, top = C.live_rule(d)
    pnl, cost, t, wins, price = run_bets(d, m, top, C.won(d, sy))
    uniq, inv = np.unique(t, return_inverse=True)
    et = [datetime.fromtimestamp(int(x), C.ET) for x in uniq]
    hour = np.array([e.hour for e in et])[inv]
    weekend = np.array([e.weekday() >= 5 for e in et])[inv]
    hm = np.array([(e.hour, e.minute) for e in et])[inv]
    by_hour = {str(h): stats(pnl[hour == h], cost[hour == h], t[hour == h]) for h in range(24)}
    week = {"weekday": stats(pnl[~weekend], cost[~weekend], t[~weekend]),
            "weekend": stats(pnl[weekend], cost[weekend], t[weekend])}
    slots = {}
    for name, (h, mi) in SLOTS.items():
        s = ~weekend & (hm[:, 0] == h) & (hm[:, 1] == mi)
        slots[name] = stats(pnl[s], cost[s], t[s])
    rel = ~weekend & np.isin(hm[:, 0] * 60 + hm[:, 1], [8 * 60 + 15, 8 * 60 + 30, 9 * 60 + 45, 10 * 60])
    slots["all four release windows"] = stats(pnl[rel], cost[rel], t[rel])
    slots["every other window"] = stats(pnl[~rel], cost[~rel], t[~rel])
    seg_rel = np.where(rel, "release", "other")
    return {"base": stats(pnl, cost, t), "byHour": by_hour, "week": week, "slots": slots,
            "holdout": {"hour": [holdout(hour, pnl, cost, t, a, b) for a, b in (("pre", "post"), ("post", "pre"))],
                        "weekend": [holdout(np.where(weekend, "weekend", "weekday"), pnl, cost, t, a, b)
                                    for a, b in (("pre", "post"), ("post", "pre"))],
                        "release": [holdout(seg_rel, pnl, cost, t, a, b) for a, b in (("pre", "post"), ("post", "pre"))]}}


def together(d):
    """4a: how a window's crypto bets under the live rule lose together, against independent bets losing at the same rate."""
    m, sy, _ = C.live_rule(d)
    cr = m & (d["group"] == "crypto")
    lost = ~C.won(d, sy)[cr]
    _, inv = np.unique(d["open_ts"][cr], return_inverse=True)
    n = np.bincount(inv)
    L = np.bincount(inv, weights=lost).astype(int)
    p = float(lost.mean())
    multi = n >= 2
    exp2 = float((1 - (1 - p) ** n - n * p * (1 - p) ** (n - 1))[multi].sum())
    return {"windows": int(len(n)), "bets": int(cr.sum()), "lossRate": p, "windowsWith2plus": int(multi.sum()),
            "betsPerWindow": float(n.mean()), "lose2plus": int((L >= 2).sum()), "lose2plusIfIndependent": exp2,
            # if one crypto favourite in a window loses, the chance another one there does too
            "otherLosesGivenOneLoses": float((L * (L - 1)).sum() / (L * (n - 1)).sum()),
            "lossesInMultiLossWindows": float(L[L >= 2].sum() / L.sum()), "mostLostInOneWindow": int(L.max()),
            "lossHistogram": {str(k): int((L == k).sum()) for k in range(0, 6)} | {"6+": int((L >= 6).sum())}}


def caps(d):
    """4b: at most K crypto bets a window, at $10 a bet by period and at the bot's sizing from $500 (from Dec 10, over pre
    alone and over post alone), with the edge of the bets each cap drops. The best cap on one half is scored on the other."""
    m, sy, top = C.live_rule(d)
    w = C.won(d, sy)
    sp = spread(d, sy, 8)
    t = d["open_ts"]
    pre = t < C.PERIODS[1][2]
    out = []
    for cap in (None,) + CAPS:
        for pick in (PICKS if cap else ("price",)):
            mk = cap_mask(d, m, top, sp, cap, pick)
            pnl, cost, tt, _, _ = run_bets(d, mk, top, w)
            dropped = m & ~mk
            dp, dc, dt, _, _ = run_bets(d, dropped, top, w)
            out.append({"cap": cap, "pick": pick, "edge": stats(pnl, cost, tt), "dropped": stats(dp, dc, dt),
                        "sized": {"dec10": replay(d, mk, top, w), "pre": replay(d, mk & pre, top, w),
                                  "post": replay(d, mk & ~pre, top, w)}})
    score = lambda r, k: r["sized"][k]["final"] / START / max(r["sized"][k]["maxDD"], 1e-9) if r["cap"] else None
    picks = {}
    for a, b in (("pre", "post"), ("post", "pre")):
        best = max((r for r in out if r["cap"]), key=lambda r: score(r, a))
        picks[f"{a}->{b}"] = {"cap": best["cap"], "pick": best["pick"], "criterion": "final / start / deepest fall",
                              "chosen": best["sized"][a], "scored": best["sized"][b], "baseline": out[0]["sized"][b]}
    return {"rows": out, "holdout": picks}


def rule_changes(d, rows):
    """One change to the live rule at a time, chosen on one half and scored on the other: the entry minute (the one with
    the best edge on the choosing half), and skipping the 2c bands whose edge was below zero on the choosing half."""
    whole = band_label(C.LO, C.HI)
    by_min = {r["minute"]: r["fav"] for r in rows if r["live"] and r["group"] == "all" and r["band"] == whole}
    out = {}
    for a, b in (("pre", "post"), ("post", "pre")):
        best = max(MINUTES, key=lambda M: by_min[M][a]["mu"])
        out[f"minute {a}->{b}"] = {"best": best, "chosen": by_min[best][a], "scored": by_min[best][b],
                                   "minute8": by_min[8][b]}
    m, sy, top = C.live_rule(d)
    pnl, cost, t, _, price = run_bets(d, m, top, C.won(d, sy))
    out["bands"] = [holdout(band_of(price), pnl, cost, t, a, b) for a, b in (("pre", "post"), ("post", "pre"))]
    return out


def candidates(d):
    """The changes that held up, each alone and then together, against the live rule: $10 a bet by period, and the bot's
    sizing from $500 from Dec 10, over pre alone and over post alone. A smaller window cap (9%, 6%) is the plain sizing
    alternative to dropping crypto bets: it shrinks every bet in a crowded window instead. The caps were picked against
    the 20% the bot ran until Oct 15; it is on 10% now, so the rows below compare against that."""
    m, sy, top = C.live_rule(d)
    w = C.won(d, sy)
    pre = d["open_ts"] < C.PERIODS[1][2]
    open930 = slot_mask(d, 9, 30)
    cap3 = lambda mk: cap_mask(d, mk, top, spread(d, sy, 8), 3, "spread")
    rules = [("live rule", m, WINDOW_CAP), ("skip the weekday 9:30 ET window", m & ~open930, WINDOW_CAP),
             ("at most 3 crypto bets a window, tightest spreads", cap3(m), WINDOW_CAP),
             ("window cap 9% instead of 10%", m, 0.09), ("window cap 6% instead of 10%", m, 0.06),
             ("skip 9:30 and at most 3 crypto bets", cap3(m & ~open930), WINDOW_CAP)]
    out = []
    for name, mk, wc in rules:
        pnl, cost, t, _, _ = run_bets(d, mk, top, w)
        out.append({"rule": name, "windowCap": wc, "edge": stats(pnl, cost, t),
                    "sized": {k: replay(d, mk & sel, top, w, window_cap=wc)
                              for k, sel in (("dec10", np.ones(len(pre), bool)), ("pre", pre), ("post", ~pre))}})
    return out


def main():
    print(" ".join(next(p for p in __doc__.split("\n\n") if p.startswith("Strategy:")).split()), end="\n\n")
    d = C.load()
    m, sy, top = C.live_rule(d)
    pnl, cost, t, _, _ = run_bets(d, m, top, C.won(d, sy))
    check = stats(pnl, cost, t)["all"]
    base = replay(d, m, top, C.won(d, sy))
    print(f"check: live rule {check['bets']} bets {check['perBet']:+.2f}c (strategies.json: 35,793, +4.47c); "
          f"from $500 on Dec 10 ${base['final']:,.2f}, deepest fall {base['maxDD']:.1%}, worst 15m ${base['worstWindow']:,.2f}"
          " (strategies.json live500: $25,131.63, 59.7%, -$2,794.48)")
    rows = edge_map(d)
    out = {"bands": [c[0] for c in cells()], "minutes": list(MINUTES), "slip": C.SLIP, "start": START,
           "periods": {"pre": "Dec 10 - Jul 17", "post": "Jul 18 - Oct 8", "clean": "Jul 18 - Aug 23 and Sep 24 - Oct 8",
                       "build": "Aug 24 - Sep 23 (live filters chosen here)"},
           "check": {"liveRule": check, "live500": base}, "edgeMap": rows, "ruleChanges": rule_changes(d, rows),
           "timing": timing(d), "together": together(d), "caps": caps(d), "candidates": candidates(d)}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
