"""What the live bot's research found about halts, selling early and the warning signs before buying, in one run:
findings.json.

Strategy: at minute 8 of each 15-minute window, buy the favourite - the side with the higher ask - of
every crypto, metals and energy market when its ask is 90-99.9c, filled 0.4c worse than the recorded
ask with the taker fee, and hold it to settlement; the halts, exit rules and warning signs below are
tested on top of it.

Every minute-8 favourite since Dec 10, 2025 (90-99.9c, crypto/metals/energy), bought at the recorded ask + 0.4c with
Kalshi's taker fee, is replayed four ways:

  halts     the live bot's own sizing (3% a bet, 20% a window, whole contracts, from $100) under each set of halts
  exits     what losing bets' prices did, and every rule for selling a position before it settles
  signs     what, before buying, marks the bets that go on to lose
  clusters  how losses bunch into windows

Each is checked on three parts of the history: "pre" (Dec 10 - Jul 17, the crypto markets before the first three minute
files began, never used to choose a rule), "before" (Jul 18 - Aug 23, when the edge was about zero) and "after" (Aug 24
on, about +4c a $10 bet); and, where the paper trader recorded minute bars, on its forward days from Sep 24, which no
rule here was chosen on.

    python findings.py        (about a minute)
"""
import csv
import json
import math
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone

import history
from strategies_backtest import FED_WINDOWS, favourite, fee, ts
from history import strategy

SLIP = 0.004                                   # live-like fills: 0.4c worse than the recorded ask
FIRST, JUL18, SPLIT, LAST = ts(history.FIRST), ts(history.JUL18), ts("2026-08-24T00:00:00Z"), ts(history.end()) - 900
FED = FED_WINDOWS                              # the Fed decisions' 2:00-3:30 pm ET windows, which the live bot skips
LATER = range(9, 15)                           # the minutes after entry at which a position could be sold
EDGE_MONITOR = (0.003, 15.0, 3.0)              # allowance a bet, threshold, most one window can add


def fav_quotes(side, bid, ask):
    """The favourite's own (bid, ask) from the YES bid and ask."""
    if bid is None or ask is None:
        return None
    return (bid, ask) if side == "yes" else (round(1 - ask, 4), round(1 - bid, 4))


def load():
    """Every minute-8 favourite: when, which market, what it cost, whether it won and its quotes in minutes 1-14."""
    with open("universe.json", encoding="utf-8") as fh:
        groups = {u["ticker"]: u["group"] for u in json.load(fh)["series"]}
    num = lambda x: float(x) if x != "" else None
    bets, seen = [], set()
    for path in history.FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen:
                    continue
                seen.add(r["ticker"])
                t = ts(r["open_time"])
                if not FIRST <= t <= LAST or groups.get(r["series"]) not in ("crypto", "metals", "energy") or "" in (r["b8"], r["a8"]):
                    continue
                side, top = favourite(float(r["b8"]), float(r["a8"]))
                if side and 0.90 <= top <= 0.999:
                    bets.append({"t": t, "series": r["series"], "group": groups[r["series"]], "entry": min(top + SLIP, 0.999),
                                 "won": (side == "yes") == (r["resolved_yes"] == "1"),
                                 "q": {m: fav_quotes(side, num(r[f"b{m}"]), num(r[f"a{m}"])) for m in range(1, 15)}})
    return bets


def forward():
    """The paper trader's $10 account (Sep 24 on) where it recorded every minute's quotes."""
    if not os.path.exists("paper/paper.db"):
        return []
    db = sqlite3.connect("file:paper/paper.db?mode=ro", uri=True)
    bars = defaultdict(dict)
    for t, m, yb, ya in db.execute("SELECT ticker, minute, yes_bid, yes_ask FROM minute_bars"):
        bars[t][m] = (yb, ya)
    out = []
    for t, series, side, fill, won, opened in db.execute(
            "SELECT ticker, series, side, fill, status='won', window_open FROM bets WHERE strategy='m8' AND status IN ('won','lost')"):
        if 8 in bars.get(t, {}):
            out.append({"t": opened, "series": series, "entry": fill, "won": bool(won),
                        "q": {m: fav_quotes(side, *bars[t][m]) if m in bars[t] else None for m in range(1, 15)}})
    return out


# ------------------------------------------------------------------ money
def held(b, c=None):
    """P&L of holding a $10 bet (or c contracts) to settlement."""
    c = c or 10 / b["entry"]
    return (c if b["won"] else 0.0) - c * b["entry"] - fee(c, b["entry"])


def sold(b, px, c=None):
    """P&L of selling it at px instead, paying the taker fee again."""
    c = c or 10 / b["entry"]
    return c * px - (fee(c, px) if px > 0 else 0) - c * b["entry"] - fee(c, b["entry"])


def total(bs):
    return sum(held(b) for b in bs)


def cents(x):
    return round(x * 100, 1)


def halves(bets):
    """The history in three parts: before Jul 18, Jul 18 - Aug 23, and Aug 24 on."""
    return {"pre": [b for b in bets if b["t"] < JUL18], "before": [b for b in bets if JUL18 <= b["t"] < SPLIT],
            "after": [b for b in bets if b["t"] >= SPLIT]}


def part(t):
    return "pre" if t < JUL18 else "before" if t < SPLIT else "after"


def summary(bs):
    return {"bets": len(bs), "lost": round(sum(not b["won"] for b in bs) / max(1, len(bs)), 4),
            "total": round(total(bs), 2), "perBet": cents(total(bs) / len(bs)) if bs else None}   # cents a $10 bet


# ------------------------------------------------------------------ the warning signs, before buying
mid = lambda b, m: None if b["q"].get(m) is None else (b["q"][m][0] + b["q"][m][1]) / 2
SIGNS = {
    "spread": ("The favorite's ask was 2¢ or more above its bid at minute 8",
               lambda b: b["q"][8][1] - b["q"][8][0] >= 0.02 - 1e-9),
    "late": ("It was 50¢ or under at minute 6 or 7, or rose 10¢ or more in minute 8",
             lambda b: (mid(b, 7) is not None and mid(b, 8) - mid(b, 7) >= 0.10) or any(mid(b, m) is not None and mid(b, m) <= 0.5 for m in (6, 7))),
    "slow": ("It was still under 70¢ at minute 5, three minutes before the bet", lambda b: mid(b, 5) is not None and mid(b, 5) < 0.70),
}


def signs(bets, fwd):
    combos = [["spread"], ["late"], ["slow"], ["spread", "late"], ["spread", "late", "slow"]]
    out = {"signs": {k: v[0] for k, v in SIGNS.items()}, "rows": []}
    parts = dict(halves(bets), forward=fwd)
    out["base"] = {k: summary(v) for k, v in parts.items()}
    for ks in combos:
        row = {"skip": ks}
        for k, bs in parts.items():
            keep = [b for b in bs if not any(SIGNS[s][1](b) for s in ks)]
            row[k] = dict(summary(keep), skipped=round(1 - len(keep) / max(1, len(bs)), 4))
        out["rows"].append(row)
    return out


# ------------------------------------------------------------------ selling a position before it settles
def first_bid(b, x, above=False, start=9):
    """The first bid in minutes start-14 at or under x (or at or over it)."""
    return next((b["q"][m][0] for m in LATER if m >= start and b["q"][m] and (b["q"][m][0] >= x if above else b["q"][m][0] <= x)), None)


def rule_delta(bs, x, above=False, at_mid=False):
    d = 0.0
    for b in bs:
        m = next((m for m in LATER if b["q"][m] and (b["q"][m][0] >= x if above else b["q"][m][0] <= x)), None)
        if m is None:
            continue
        if at_mid:   # the most any rule could get: no spread, no fee
            c = 10 / b["entry"]
            d += c * sum(b["q"][m]) / 2 - c * b["entry"] - fee(c, b["entry"]) - held(b)
        else:
            d += sold(b, b["q"][m][0]) - held(b)
    return round(d, 2)


def shape(b):
    p = [b["q"][m][0] if b["q"][m] else None for m in LATER]
    if None in p:
        return None
    if p[3] >= 0.80 and p[5] < 0.50:
        return "late crash"
    if min(p[:2]) < 0.80:
        return "early break"
    if min(p[:4]) < 0.70 and max(p[p.index(min(p[:4])):]) >= 0.90:
        return "whipsaw"
    if all(x >= y - 0.02 for x, y in zip(p, p[1:])):
        return "steady slide"
    return "other"


def exits(bets, fwd):
    losers, winners = [b for b in bets if not b["won"]], [b for b in bets if b["won"]]
    out = {"losers": len(losers), "bets": len(bets), "byMinute": [], "under50": [], "shapes": [], "bounce": []}
    for m in LATER:
        bids = sorted(b["q"][m][0] for b in losers if b["q"][m])
        wb = [b["q"][m][0] for b in winners if b["q"][m]]
        out["byMinute"].append({"minute": m, "median": bids[len(bids) // 2], "still80": round(sum(x >= .8 for x in bids) / len(bids), 4),
                                "winnersUnder80": round(sum(x < .8 for x in wb) / len(wb), 4)})
        hit = [b for b in bets if b["q"][m] and b["q"][m][0] < 0.50]
        lo = [b for b in hit if not b["won"]]
        wi = [b for b in hit if b["won"]]
        rescued = sum(sold(b, b["q"][m][0]) - held(b) for b in lo)
        thrown = sum(held(b) - sold(b, b["q"][m][0]) for b in wi)
        out["under50"].append({"minute": m, "losers": len(lo), "rescued": round(rescued, 2), "winners": len(wi),
                               "thrown": round(thrown, 2), "net": round(rescued - thrown, 2)})
    kinds = Counter(shape(b) for b in losers)
    wkinds = Counter(shape(b) for b in winners)
    for k in ("early break", "late crash", "steady slide", "whipsaw", "other"):
        out["shapes"].append({"shape": k, "losers": kinds[k], "winners": wkinds[k]})
    for lo_, hi_ in ((0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 1.0)):
        nxt, won, bid = [], 0, 0.0
        for b in bets:
            for m in range(9, 14):
                a, c, d = mid(b, m - 1), mid(b, m), mid(b, m + 1)
                if None not in (a, c, d) and lo_ <= a - c < hi_:
                    nxt.append(d - c); won += b["won"]; bid += b["q"][m][0]
                    break
        nxt.sort()
        out["bounce"].append({"drop": [lo_, hi_], "n": len(nxt), "nextMedian": nxt[len(nxt) // 2],
                              "fellFurther": round(sum(x < -0.005 for x in nxt) / len(nxt), 4),
                              "bid": round(bid / len(nxt), 4), "won": round(won / len(nxt), 4)})
    parts = dict(halves(bets), forward=fwd)
    out["stops"] = [{"under": x, **{k: rule_delta(bs, x) for k, bs in parts.items()}} for x in (0.90, 0.80, 0.50, 0.30, 0.10)]
    out["stopAtMid"] = {k: rule_delta(bs, 0.50, at_mid=True) for k, bs in halves(bets).items()}
    out["takeProfit"] = [{"at": x, **{k: rule_delta(bs, x, above=True) for k, bs in parts.items()}} for x in (0.97, 0.98, 0.99)]
    out["hindsight"] = round(sum(sold(b, b["q"][9][0]) - held(b) for b in losers if b["q"][9]), 2)
    # contagion: when one crypto favourite in a window falls to 30c, sell the window's other crypto favourites
    by_w = defaultdict(list)
    for b in bets:
        if b["group"] == "crypto":
            by_w[b["t"]].append(b)
    cont = {"pre": 0.0, "before": 0.0, "after": 0.0}
    for w, bs in by_w.items():
        for trig in bs:
            m = next((m for m in LATER if trig["q"][m] and trig["q"][m][0] <= 0.30), None)
            if m is None:
                continue
            for sib in bs:
                if sib is not trig and sib["q"][m]:
                    cont[part(w)] += sold(sib, sib["q"][m][0]) - held(sib)
            break
    out["contagion"] = {k: round(v, 2) for k, v in cont.items()}
    return out


# ------------------------------------------------------------------ halts, at the live bot's own sizing
def halts(bets):
    windows = defaultdict(list)
    for b in bets:
        if not any(b["t"] < z and b["t"] + 900 > a for a, z in FED):   # the bot skips Fed decision windows
            windows[b["t"]].append(b)
    order = sorted(windows)

    def run(start, spread=False, rules=(), day_drop=0.20, monitor=None):
        bal, hist, s = 100.0, [], 0.0
        for t in order:
            if t < start:
                continue
            bs = [b for b in windows[t] if not (spread and SIGNS["spread"][1](b))]
            if not bs:
                continue
            stake = min(math.floor(min(bal * 0.03, bal * 0.20 / len(bs)) * 100) / 100, 10.0)
            if stake < 1:
                return bal, t, "broke"
            pnl, losses, y = 0.0, 0, 0.0
            for b in bs:
                c = math.floor(stake / b["entry"] + 1e-9)
                if c < 1:
                    continue
                f = fee(c, b["entry"])
                pnl += held(b, c); losses += not b["won"]
                y += b["entry"] + f / c - b["won"] - (monitor[0] if monitor else 0)
            bal += pnl
            hist.append((t, bal))
            if monitor:
                s = max(0.0, s + min(y, monitor[2]))
            if "half" in rules and bal <= 50:
                return bal, t, "half the start"
            if "window" in rules and losses >= 8:
                return bal, t, "8+ losses in a window"
            if "day" in rules:
                recent = [v for u, v in hist if u > t - 86400] + [next((v for u, v in reversed(hist) if u <= t - 86400), 100.0)]
                if bal <= max(recent) * (1 - day_drop):
                    return bal, t, f"{day_drop:.0%} down in 24 hours"
            if monitor and s >= monitor[1]:
                return bal, t, "edge monitor"
        return bal, None, None

    today = ("half", "window", "day")
    sets = [("Today's halts", {"rules": today}),
            ("No halts", {}),
            ("24-hour rule loosened to 35%", {"rules": today, "day_drop": 0.35}),
            ("Half the start, 8 losses, edge monitor", {"rules": ("half", "window"), "monitor": EDGE_MONITOR}),
            ("Spread filter and today's halts", {"spread": True, "rules": today}),
            ("Spread filter, half the start, 8 losses, edge monitor", {"spread": True, "rules": ("half", "window"), "monitor": EDGE_MONITOR})]
    out = []
    for name, kw in sets:
        row = {"rule": name}
        for key, start in (("fromDec10", FIRST), ("fromJul18", JUL18), ("fromAug24", SPLIT)):
            end, t, why = run(start, **kw)
            row[key] = {"end": round(end, 2), "stopped": t and datetime.fromtimestamp(t, timezone.utc).strftime("%b %d"), "why": why}
        out.append(row)
    return out


def clusters(bets):
    by_w = Counter()
    for b in bets:
        by_w[b["t"]] += not b["won"]
    dist = Counter(v for v in by_w.values() if v)
    lost = sum(k * v for k, v in dist.items())
    return {"windows": {str(k): v for k, v in sorted(dist.items())}, "shareIn3Plus": round(sum(k * v for k, v in dist.items() if k >= 3) / lost, 4)}


def main():
    strategy(__doc__)
    bets, fwd = load(), forward()
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "from": history.FIRST[:10], "jul18": history.JUL18[:10], "split": "2026-08-24",
           "to": datetime.fromtimestamp(LAST, timezone.utc).strftime("%Y-%m-%d"), "periods": {k: summary(v) for k, v in halves(bets).items()}, "forwardBets": len(fwd),
           "halts": halts(bets), "exits": exits(bets, fwd), "signs": signs(bets, fwd), "clusters": clusters(bets)}
    with open("findings.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    p = out["periods"]
    c = lambda k: f"{p[k]['perBet']:+}c" if p[k]["perBet"] is not None else "no bets"  # noqa: E731
    print(f"findings.json: {len(bets)} bets ({c('pre')} a $10 bet before Jul 18, {c('before')} Jul 18 - Aug 23, {c('after')} after), "
          f"{len(fwd)} forward")


if __name__ == "__main__":
    main()
