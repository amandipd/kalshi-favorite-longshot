"""Score PREREG.md once: the bot's rule (and plain favourites) on Oct 9 - 29 2026 against the past (lab/markets.npz),
then the reported-only splits and the execution check against the live ledger pull.

    python score.py [live_bets.json]      -> prints everything, writes score.json
"""
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kalshi_15min", "lab"))
import common as C  # noqa: E402

C.FED_WINDOWS.append(tuple(datetime.fromisoformat(f"2026-10-28T{hm}").replace(tzinfo=C.ET).timestamp()
                           for hm in ("14:00", "15:30")))
GROUPS = {s: "crypto" for s in ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M", "KXHYPE15M",
                                 "KXNEAR15M", "KXDOGE15M", "KXZEC15M")}
GROUPS.update({s: "metals" for s in ("KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXCOPPER15M", "KXPALLADIUM15M")})
GROUPS.update({"KXNATGAS15M": "energy", "KXWTI15M": "energy"})
BASE_ALL, BASE_RECENT = 0.80, 1.16
SPLIT = datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()
GO = 1792127635  # the live test's start (Oct 16 05:13:55 UTC)


def load_recent():
    rows = list(csv.DictReader(open(os.path.join(HERE, "recent_minutes.csv"))))
    num = lambda v: float(v) if v != "" else np.nan
    d = {"ticker": np.array([r["ticker"] for r in rows]), "series": np.array([r["series"] for r in rows]),
         "group": np.array([GROUPS[r["series"]] for r in rows]),
         "open_ts": np.array([int(datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")).timestamp())
                              for r in rows]),
         "yes": np.array([r["resolved_yes"] == "1" for r in rows], dtype=np.int8)}
    for k, p in (("bid", "b"), ("ask", "a"), ("last", "p")):
        d[k] = np.round(np.array([[num(r[f"{p}{m}"]) for m in range(1, 16)] for r in rows], dtype=np.float64), 4)
    return d


def bets(d, plain=False):
    """(pnl, cost, window, price, won, side_yes, group, ticker) of the rule's $10 bets at the recorded ask."""
    m, sy, top = C.live_rule(d, lo=0.92, skip=() if plain else ("spread", "late"), fed=not plain)
    idx = np.flatnonzero(m)
    price = np.minimum(top[idx], 0.999)
    c = np.floor(10.0 / price + 1e-9)
    won = C.won(d, sy)[idx]
    cost = c * price + C.fee(c, price)
    pnl = np.where(won, c, 0.0) - cost
    return {"pnl": pnl, "cost": cost, "t": d["open_ts"][idx], "price": price, "won": won, "yes": sy[idx],
            "group": d["group"][idx], "ticker": d["ticker"][idx]}


def stat(b, sel=None):
    sel = np.ones(len(b["pnl"]), bool) if sel is None else sel
    p, s, t = b["pnl"][sel], b["cost"][sel], b["t"][sel]
    if len(p) < 30:
        return {"bets": int(len(p))}
    c = p.sum() / s.sum()
    _, inv = np.unique(t, return_inverse=True)
    g = inv.max() + 1
    r = np.bincount(inv, weights=p) - c * np.bincount(inv, weights=s)
    se = math.sqrt((r ** 2).sum() * g / (g - 1)) / s.sum()
    lost = int((~b["won"][sel]).sum())
    pred = float((1 - b["price"][sel]).sum())
    return {"bets": int(len(p)), "cents": round(c * 100, 3), "lo": round((c - 1.96 * se) * 100, 3),
            "hi": round((c + 1.96 * se) * 100, 3), "t": round(c / se, 2), "lost": lost, "pred": round(pred, 1),
            "ratio": round(lost / pred, 3), "pnl": round(float(p.sum()), 2)}


def show(label, s):
    if "cents" not in s:
        print(f"  {label:<40} {s['bets']} bets (too few)")
        return
    print(f"  {label:<40} bets {s['bets']:>6}  {s['cents']:+6.2f}c/$1 (range {s['lo']:+.2f} to {s['hi']:+.2f}, "
          f"t {s['t']:+.2f})  lost {s['lost']:>4} vs {s['pred']:7.1f} pred ({s['ratio']:.2f}x)  ${s['pnl']:+.2f}")


def flips(b, days):
    cr = b["group"] == "crypto"
    t, l = b["t"][cr], ~b["won"][cr]
    u, inv = np.unique(t, return_inverse=True)
    nl = np.bincount(inv, weights=l.astype(float))
    return {"5plus": int((nl >= 5).sum()), "3plus": int((nl >= 3).sum()), "days": round(days, 1),
            "perWeek5": round((nl >= 5).sum() / days * 7, 2), "perWeek3": round((nl >= 3).sum() / days * 7, 2)}


def main():
    out = {}
    past = C.load()
    pb = bets(past)
    out["baseline"] = {"all": stat(pb), "aug24on": stat(pb, pb["t"] >= C.PERIODS[2][2])}
    print("PAST (lab/markets.npz) at the recorded ask:")
    show("rule, whole history", out["baseline"]["all"])
    show("rule, Aug 24 - Oct 8", out["baseline"]["aug24on"])
    ppl = bets(past, plain=True)
    show("plain favourites, whole history", stat(ppl))
    show("plain favourites, Aug 24 - Oct 8", stat(ppl, ppl["t"] >= C.PERIODS[2][2]))

    d = load_recent()
    print(f"\nRECENT: {len(d['ticker'])} markets, {datetime.fromtimestamp(d['open_ts'].min(), timezone.utc):%b %d} .. "
          f"{datetime.fromtimestamp(d['open_ts'].max(), timezone.utc):%b %d %H:%M} UTC")
    rb = bets(d)
    prim = stat(rb)
    out["primary"] = prim
    show("RULE (primary)", prim)
    faded, there = prim["hi"] < BASE_ALL, prim["lo"] > 0
    reading = ("smaller but still there" if faded and there else "faded" if faded else
               "still there" if there else "unclear")
    out["reading"] = reading
    print(f"  READING: {reading}  (faded = range below +{BASE_ALL}c: {faded}; still there = range above 0: {there})")

    print("\nReported, not part of the reading:")
    rp = bets(d, plain=True)
    out["plain"] = stat(rp)
    show("plain favourites (no warning signs)", out["plain"])
    for lab, sel in (("rule Oct 9-19", rb["t"] < SPLIT), ("rule Oct 20-29", rb["t"] >= SPLIT),
                     ("rule crypto", rb["group"] == "crypto"), ("rule metals+energy", rb["group"] != "crypto"),
                     ("rule Yes side", rb["yes"]), ("rule No side", ~rb["yes"])):
        out[lab] = stat(rb, sel)
        show(lab, out[lab])
    for lab, sel in (("plain Oct 9-19", rp["t"] < SPLIT), ("plain Oct 20-29", rp["t"] >= SPLIT)):
        out[lab] = stat(rp, sel)
        show(lab, out[lab])
    days_recent = (d["open_ts"].max() + 900 - d["open_ts"].min()) / 86400
    days_past = (pb["t"].max() + 900 - C.PERIODS[2][2]) / 86400
    out["flipsRecent"] = flips(rb, days_recent)
    sel = pb["t"] >= C.PERIODS[2][2]
    out["flipsPast"] = flips({k: v[sel] for k, v in pb.items()}, days_past)
    print(f"  crypto windows with 5+ / 3+ losses: recent {out['flipsRecent']}; past Aug 24 on {out['flipsPast']}")

    if len(sys.argv) > 1:   # execution check against the live ledger pull
        live = [b for b in json.load(open(sys.argv[1]))["bets"] if b["status"] in ("won", "lost")]
        end = d["open_ts"].max() + 900
        lv = [b for b in live if b["window_open"] >= GO - 900 and b["window_open"] + 900 <= end]
        lw = {b["window_open"] for b in lv}
        sel = (rb["t"] >= GO - 900) & (rb["t"] + 900 <= end)
        rule_same = stat(rb, sel)
        lp = np.array([b["pnl"] for b in lv]); ls = np.array([b["cost"] + b["fee"] for b in lv])
        lwin = np.array([b["window_open"] for b in lv]); lwon = np.array([b["status"] == "won" for b in lv])
        lprice = np.array([b["price"] for b in lv])
        live_s = stat({"pnl": lp, "cost": ls, "t": lwin, "won": lwon, "price": lprice})
        print(f"\nEXECUTION CHECK, Oct 16 05:15 UTC to {datetime.fromtimestamp(end, timezone.utc):%b %d %H:%M} UTC:")
        show("rule on Kalshi's candles", rule_same)
        show("the live bot", live_s)
        rt = {t: i for i, t in enumerate(rb["ticker"])}
        both = [b for b in lv if b["ticker"] in rt]
        only_live = [b for b in lv if b["ticker"] not in rt]
        lt = {b["ticker"] for b in lv}
        only_rule = np.array([t not in lt for t in rb["ticker"]]) & sel
        print(f"  markets both bet {len(both)}; live only {len(only_live)}; rule only {int(only_rule.sum())}")
        if both:
            gap = np.mean([b["price"] - rb["price"][rt[b['ticker']]] for b in both]) * 100
            agree = np.mean([(b["status"] == "won") == bool(rb["won"][rt[b["ticker"]]]) for b in both])
            print(f"  on the shared markets: live paid {gap:+.2f}c more on average; same result {agree:.1%}")
            show("  shared markets, live", stat({"pnl": np.array([b["pnl"] for b in both]),
                                                  "cost": np.array([b["cost"] + b["fee"] for b in both]),
                                                  "t": np.array([b["window_open"] for b in both]),
                                                  "won": np.array([b["status"] == "won" for b in both]),
                                                  "price": np.array([b["price"] for b in both])}))
            ix = np.array([rt[b["ticker"]] for b in both])
            show("  shared markets, rule at the candle ask", stat({k: v[ix] for k, v in rb.items()}))
        if only_live:
            show("  live-only markets", stat({"pnl": np.array([b["pnl"] for b in only_live]),
                                              "cost": np.array([b["cost"] + b["fee"] for b in only_live]),
                                              "t": np.array([b["window_open"] for b in only_live]),
                                              "won": np.array([b["status"] == "won" for b in only_live]),
                                              "price": np.array([b["price"] for b in only_live])}))
        show("  rule-only markets", stat(rb, only_rule))
        out["execution"] = {"rule": rule_same, "live": live_s, "both": len(both), "liveOnly": len(only_live),
                            "ruleOnly": int(only_rule.sum()), "windowsLive": len(lw)}
    with open(os.path.join(HERE, "score.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
