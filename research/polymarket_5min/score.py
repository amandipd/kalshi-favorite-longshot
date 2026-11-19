"""Score the bot's rule on Polymarket US 5-minute markets, as fixed in PREREG.md.

Reads markets.jsonl (fetch.py). Each market's price history becomes the Yes bid and ask at the end of minutes 1-5
(quotes), then the research's own Kalshi rule (research/kalshi_15min/lab/common.py: favourite, spread_sign,
late_sign) picks the bets at minute 3. Bets are $10 at the recorded ask in fractional contracts, with Polymarket US's
taker fee rounded to the nearest cent. Writes score.json and prints the reading.

    python score.py [offset]      # offset: seconds a history point lags the book it shows (default 60)
"""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kalshi_15min", "lab"))
import common as C  # noqa: E402

MINUTES = 5
NEAR = 5                     # a history point counts for a stamp within this many seconds
LO, HI = 0.92, 0.99
THETA = 0.085                # main fee coefficient (tier 2)
TIERS = (0.0695, 0.075, 0.085, 0.095)
STAKE = 10.0
SPLIT = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()   # train: before; test: from
FED = [tuple(datetime.fromisoformat(f"2026-10-28T{hm}").replace(tzinfo=C.ET).timestamp() for hm in ("14:00", "15:30"))]
CENT = Decimal("0.01")


# ------------------------------------------------------------------ reading the data


def quotes(points, offset=60):
    """(bid, ask): the Yes bid and ask at the end of minutes 1-5, NaN where missing. The book at the end of minute k is
    the point stamped k*60 - offset (within NEAR s). longPrice is the Yes ask, shortPrice the No ask (1 - Yes bid);
    a value outside (0, 1) is no quote."""
    bid, ask = np.full(MINUTES, np.nan), np.full(MINUTES, np.nan)
    at = {}
    for t, lp, sp in points:
        at.setdefault(t, (lp, sp))
    for k in range(1, MINUTES + 1):
        want = k * 60 - offset
        hit = min((t for t in at if abs(t - want) <= NEAR), key=lambda t: abs(t - want), default=None)
        if hit is None:
            continue
        lp, sp = at[hit]
        if lp is not None and 0 < lp < 1:
            ask[k - 1] = round(lp, 4)
        if sp is not None and 0 < sp < 1:
            bid[k - 1] = round(1 - sp, 4)
    return bid, ask


def build(records, offset=60):
    """(d, counts): the resolved markets as arrays in lab/common.py's layout (bid, ask: n x 5; yes; open_ts; coin),
    and how many were kept, missing (no market listed) and unresolved."""
    counts = {"markets": 0, "missing": 0, "unresolved": 0}
    rows = []
    for r in records:
        if r.get("missing"):
            counts["missing"] += 1
            continue
        if r.get("yes") is None:
            counts["unresolved"] += 1
            continue
        counts["markets"] += 1
        rows.append((quotes(r.get("h") or [], offset), r))
    n = len(rows)
    d = {"bid": np.full((n, MINUTES), np.nan), "ask": np.full((n, MINUTES), np.nan),
         "yes": np.array([int(r["yes"]) for _, r in rows], dtype=int),
         "open_ts": np.array([r["start"] for _, r in rows], dtype=np.int64),
         "coin": np.array([r["coin"] for _, r in rows], dtype="U4")}
    for i, ((bid, ask), _) in enumerate(rows):
        d["bid"][i], d["ask"][i] = bid, ask
    return d, counts


def load(path=os.path.join(HERE, "markets.jsonl")):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# ------------------------------------------------------------------ the rule


def won(d, side_yes):
    return C.won(d, side_yes)


def blackout(d):
    t = d["open_ts"]
    return np.any([(t < z) & (t + 300 > a) for a, z in FED], axis=0)


def rule(d, M=3, lo=LO, hi=HI, signs=True, late="kalshi", fed=True):
    """(mask, side_yes, top): the bets at the end of minute M. late: "kalshi" (mid 50c or under at M-1 or M-2, or up
    10c in minute M: lab/common.py's own late_sign), "m1" (the same with M-1 only), None (no late sign)."""
    side_yes, top = C.favourite(d, M)
    m = (top >= lo - 1e-9) & (top <= hi + 1e-9)
    if signs:
        m &= ~C.spread_sign(d, side_yes, M)
    if late == "kalshi":
        m &= ~C.late_sign(d, side_yes, M)
    elif late == "m1":
        mid = lambda k: np.mean(C.own(d, side_yes, k), axis=0)
        now, before = mid(M), mid(M - 1)
        m &= ~(((now - before) >= 0.10) | (before <= 0.5))
    if fed:
        m &= ~blackout(d)
    return m & ~np.isnan(top), side_yes, top


# ------------------------------------------------------------------ money


def fee(c, p, theta):
    """Polymarket US taker fee on one order: theta x contracts x p x (1 - p), to the nearest cent, half to even."""
    raw = Decimal(repr(round(float(theta * c * p * (1 - p)), 9)))
    return float(raw.quantize(CENT, rounding=ROUND_HALF_EVEN))


def bet(top, wins, theta=THETA, slip=0.0, stake=STAKE):
    """(pnl, cost, contracts) of a stake-sized taker order at the ask plus slip (at most 99c), fractional contracts
    floored to a hundredth, held to the result."""
    price = np.minimum(np.round(top + slip, 4), 0.99)
    c = np.floor(stake / price * 100 + 1e-9) / 100
    cost = c * price
    f = np.array([fee(ci, pi, theta) for ci, pi in zip(c, price)])
    pnl = np.where(wins, c, 0.0) - cost - f
    return pnl, cost, c


# ------------------------------------------------------------------ reading the numbers


def stats(pnl, cost, window):
    """Bets, cents for every dollar bet, and its 95% range clustered by window (lab/common.py summary, per $1)."""
    s = C.summary(pnl, cost, window)
    per = lambda x: None if x is None else round(x / 10, 3)
    return {"bets": s["bets"], "c_per_1": per(s["perBet"]), "lo": per(s["lo"]), "hi": per(s["hi"]),
            "pnl": s["pnl"]}


def day_of(ts):
    return np.array([datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d") for t in ts])


def leave_one_out(pnl, cost, keys):
    """The biggest earner among keys and cents for every dollar bet without it."""
    tot = defaultdict(float)
    for k, p in zip(keys, pnl):
        tot[k] += p
    if not tot:
        return None, None
    top = max(tot, key=tot.get)
    keep = keys != top
    return str(top), (round(float(pnl[keep].sum() / cost[keep].sum() * 100), 3) if keep.any() else None)


def verdict(s, loo_coin, loo_day):
    if not s["bets"] or s["c_per_1"] is None:
        return "UNCLEAR"
    if s["c_per_1"] <= 0 or (s["hi"] is not None and s["hi"] < 0.5):
        return "FAIL"
    if (s["c_per_1"] > 0.5 and s["lo"] is not None and s["lo"] > 0 and loo_coin is not None and loo_coin > 0
            and loo_day is not None and loo_day > 0):
        return "PASS"
    return "UNCLEAR"


def score(d, m, side_yes, top, theta=THETA, slip=0.0):
    w = won(d, side_yes)[m]
    pnl, cost, c = bet(top[m], w, theta=theta, slip=slip)
    s = stats(pnl, cost, d["open_ts"][m])
    s["lost"] = int((~w).sum())
    s["implied"] = round(float((1 - top[m]).sum()), 1)
    s["edge_per_contract_c"] = round(float(pnl.sum() / c.sum() * 100), 3) if c.sum() else None
    return s, pnl, cost


def calibration(d, m, side_yes, top):
    out = []
    for a, b in ((0.92, 0.93), (0.94, 0.95), (0.96, 0.97), (0.98, 0.99)):
        s = m & (top >= a - 1e-9) & (top <= b + 1e-9)
        if s.any():
            out.append({"band": f"{a * 100:.0f}-{b * 100:.0f}c", "bets": int(s.sum()),
                        "won_share": round(float(won(d, side_yes)[s].mean()), 4),
                        "avg_price": round(float(top[s].mean()), 4)})
    return out


def main(offset=60):
    recs = load()
    d, counts = build(recs, offset=offset)
    out = {"offset": offset, "counts": counts, "first": int(d["open_ts"].min()), "last": int(d["open_ts"].max())}
    days = (d["open_ts"].max() - d["open_ts"].min() + 300) / 86400

    m, side_yes, top = rule(d)
    s, pnl, cost = score(d, m, side_yes, top)
    coin_out, loo_coin = leave_one_out(pnl, cost, d["coin"][m])
    day_out, loo_day = leave_one_out(pnl, cost, day_of(d["open_ts"][m]))
    s.update({"loo_coin": [coin_out, loo_coin], "loo_day": [day_out, loo_day],
              "bets_a_day": round(s["bets"] / days, 1), "no_quote_at_entry": int(np.isnan(d["ask"][:, 2]).sum())})
    out["main"] = s
    out["verdict"] = verdict(s, loo_coin, loo_day)

    out["fee_tiers"] = {str(t): score(d, m, side_yes, top, theta=t)[0] for t in TIERS}
    out["one_tick_worse"] = score(d, m, side_yes, top, slip=0.01)[0]
    out["calibration"] = calibration(d, m, side_yes, top)
    out["by_coin"] = {c: score(d, m & (d["coin"] == c), side_yes, top)[0] for c in ("btc", "eth", "sol", "xrp")}
    out["by_side"] = {"yes": score(d, m & side_yes, side_yes, top)[0], "no": score(d, m & ~side_yes, side_yes, top)[0]}
    out["by_half"] = {"oct22_31": score(d, m & (d["open_ts"] < SPLIT), side_yes, top)[0],
                      "nov1_on": score(d, m & (d["open_ts"] >= SPLIT), side_yes, top)[0]}

    pm, ps, pt = rule(d, signs=False, late=None, fed=False)
    out["plain"] = score(d, pm, ps, pt)[0]
    out["plain_calibration"] = calibration(d, pm, ps, pt)
    out["variants"] = {
        "minute 2": score(d, *rule(d, M=2))[0],
        "minute 4": score(d, *rule(d, M=4))[0],
        "90c floor": score(d, *rule(d, lo=0.90))[0],
        "late sign at M-1 only": score(d, *rule(d, late="m1"))[0],
    }

    if out["verdict"] != "PASS":
        train, test = d["open_ts"] < SPLIT, d["open_ts"] >= SPLIT
        grid = []
        for M in (2, 3, 4):
            for name, kw in (("as Kalshi", {}), ("late at M-1 only", {"late": "m1"}),
                             ("no signs", {"signs": False, "late": None})):
                for lo in (0.90, 0.92, 0.95):
                    gm, gs, gt = rule(d, M=M, lo=lo, **kw)
                    tr = score(d, gm & train, gs, gt)[0]
                    grid.append({"M": M, "signs": name, "floor": lo, "train": tr, "_mask": (gm, gs, gt)})
        ok = [g for g in grid if g["train"]["bets"] >= 100]
        best = max(ok, key=lambda g: g["train"]["c_per_1"]) if ok else None
        out["grid_train"] = [{k: v for k, v in g.items() if k != "_mask"} for g in grid]
        if best:
            gm, gs, gt = best["_mask"]
            ts, tp, tc = score(d, gm & test, gs, gt)
            lc = leave_one_out(tp, tc, d["coin"][gm & test])
            ld = leave_one_out(tp, tc, day_of(d["open_ts"][gm & test]))
            ts.update({"loo_coin": list(lc), "loo_day": list(ld)})
            out["grid_pick"] = {"M": best["M"], "signs": best["signs"], "floor": best["floor"],
                                "train": best["train"], "test": ts, "verdict": verdict(ts, lc[1], ld[1])}

    with open(os.path.join(HERE, "score.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in ("counts", "verdict", "main")}, indent=1))
    return out


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
