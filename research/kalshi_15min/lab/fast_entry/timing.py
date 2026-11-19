"""Fast entry, the research: when within second 480 the minute-8 rush comes, how fills change with the time an order
lands, where the live bot's ~2.4 s go, and how long the experiment needs. It only reads; it writes timing.json here.

  1. The rush at 100 ms. Contracts bought on the bot's side from 478.0 to 486.0 s into the window, in 100 ms buckets:
     - the historical tape (data/liquidity_tape.jsonl, streamed): every live-rule bet Dec 10 - Oct 8, the trades whose
       taker bought the favourite, timed to the ms; the bot's own fills (Sep 28 on) are taken out;
     - the live tape (lab/live_fills/tape.jsonl): every market the bot ordered in up to Oct 11 20:38, both sides, timed
       to the microsecond; the side the bot bought, its own fills taken out (live_fills.split_own).
     The limit is the minute-8 ask (historical) or the order's own limit (live).
  2. Fills against landing time, historical tape. fills.py's immediate-or-cancel (IOC) model with the landing time as a
     parameter: nothing if the first trade on our side within FRESH s after landing is above the limit (the price ran
     away); otherwise min(want, max(V, QUIET)) contracts, V = what others bought on our side at or under the limit in
     the DEPTH s after landing. Contracts at the old limit or better are charged the old limit; dearer ones (with the
     +1c limit) their own price, cheapest first. $30 orders (want = floor(30 / top)), two limits (top, top + 1c capped
     at 99.9c), landing 480.0-484.0 s, and four variants:
       tape        DEPTH 30 s, all of each trade (fills.py)
       book1s      DEPTH 1 s: an IOC meets only the book of its instant; volume that trades 1-30 s later is mostly
                   liquidity added after it
       split       DEPTH 30 s, half of each trade: we race the taker who took it, and win half the time
       book1s_split  both
     Each is checked on the live orders at their real landing times (live tape, own fills out).
  3. The live breakdown (bot/state/live-prod.db, read-only): step lag (orders.ts - open - 480, the PC's clock), landing
     (ts_ms / 1000 - open - 480, Kalshi's clock), send delay = landing - step lag, rank in the window and the gap to the
     order before; fill share by rank and landing time, and fixed-effects regressions for the natural experiment.
  4. Power: window-level fill share, windows a day, and the windows per arm (and days) to detect +10 and +15 points.

    python research/kalshi_15min/lab/fast_entry/timing.py      # ~2 minutes, a few hundred MB at most
"""
import json
import math
import os
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime

sys.dont_write_bytecode = True   # leave no caches next to the research scripts it imports
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(LAB)))
for _p in (os.path.join(LAB, "live_fills"), LAB):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import common as C  # noqa: E402
import live_fills as LF  # noqa: E402   (our_side, split_own)

TAPE_H = os.path.join(ROOT, "data", "liquidity_tape.jsonl")
TAPE_L = os.path.join(LAB, "live_fills", "tape.jsonl")
DB = os.path.join(ROOT, "bot", "state", "live-prod.db")
OUT = os.path.join(HERE, "timing.json")

MARK = 480.0                 # minute 8 ends
CLOCK = 0.155                # this PC runs ~0.155 s behind Kalshi (SNTP, 4 servers, Oct 11): Kalshi ~ PC + 0.155
R0, R1, BW = 478000, 486000, 100   # the rush, in ms after the open, and the bucket width in ms
NB = (R1 - R0) // BW
GONE = (480.2, 480.5, 481.0, 482.0, 482.4)
SENDS = np.round(np.array(sorted({*np.arange(480.0, 481.0001, 0.1), *np.arange(481.25, 484.0001, 0.25), 482.4})), 3)
TODAY = 482.4                # the live bot's median landing: the baseline the sweep is compared with
STAKE = 30.0
FRESH, DEPTH, QUIET = 10, 30, 3
RAISE, CAP = 0.01, 0.999
VARIANTS = (("tape", 30.0, 1.0), ("book1s", 1.0, 1.0), ("split", 30.0, 0.5), ("book1s_split", 1.0, 0.5))
LIMITS = ("top", "top+1c")
LIVE_SENDS = [None, 480.2, 480.5, TODAY]   # the live orders: their real landing, then fixed landings
LIVE_KEYS = ("atLanding", "at480.2", "at480.5", "at482.4")
EPS = 1e-9
Z_SIG, Z_POW = 2.0, 0.8416   # "2 standard errors", 80% power


# ------------------------------------------------------------------ inputs
def read_orders():
    """Every buy order the live bot sent, from one read-only look at its database. Rank: its place among the window's
    accepted orders (the 3 rejected on Sep 28 came back at once and are left out of the breakdown)."""
    con = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT id, ts, ticker, request, http_status, response FROM orders ORDER BY id").fetchall()
    finally:
        con.close()
    out, rank = [], defaultdict(int)
    for oid, ts, ticker, req, status, resp in rows:
        q = json.loads(req)
        if "count" not in q:   # a cancel the bot logged
            continue
        a = json.loads(resp) if resp else None
        wo = ts - ts % 900
        side = {"bid": "yes", "ask": "no"}[q["side"]]
        yp = float(q["price"])
        o = {"id": oid, "ts": ts, "ticker": ticker, "series": ticker.split("-")[0], "wo": wo, "side": side,
             "want": int(q["count"]), "limit": round(yp if side == "yes" else 1 - yp, 4), "lag": ts - wo - MARK,
             "accepted": status in (200, 201) and isinstance(a, dict) and "ts_ms" in a}
        if o["accepted"]:
            rank[wo] += 1
            o["rank"] = rank[wo]
            o["filled"] = float(a.get("fill_count") or 0)
            o["send"] = a["ts_ms"] / 1000 - wo           # Kalshi's time, s after the open (live_fills' "send")
            o["landing"] = o["send"] - MARK
            o["delay"] = o["landing"] - o["lag"]         # raw: Kalshi's clock minus the PC's
        out.append(o)
    return out


# ------------------------------------------------------------------ 1. the rush
class Rush:
    """Contracts others bought on the bot's side, per 100 ms bucket from 478.0 to 486.0 s, and per ms near the mark."""

    def __init__(self):
        self.markets = 0
        self.vol, self.under = np.zeros(NB), np.zeros(NB)       # all contracts; those at or under the limit
        self.trades, self.sweeps = np.zeros(NB), np.zeros(NB)   # trades; distinct timestamps (one taker order each)
        self.active = [[] for _ in range(NB)]                   # contracts per market, markets with a trade there
        self.ms_n, self.ms_c = np.zeros(3000), np.zeros(3000)   # per ms from 479.000 to 481.999: trades, contracts
        self.period = defaultdict(lambda: np.zeros(NB))         # contracts per bucket, by period
        self.gone = defaultdict(float)                          # (kind, X) -> contracts in [480, X); X 486 / 510 = base
        self.mgone = defaultdict(float)                         # market-weighted: sum of shares, and markets
        self.last_digit = defaultdict(lambda: np.zeros(10))     # ms % 10 of every trade time, by period
        self.round_sec = defaultdict(float)                     # trades at .000 vs all, 470-600 s

    def add(self, trades, limit, period="all"):
        """trades: [[s after the open (ms-rounded), price on our side, contracts], ...], everyone but the bot."""
        self.markets += 1
        per = np.zeros(NB)
        stamps = [set() for _ in range(NB)]
        u = defaultdict(float)
        for t, px, c in trades:
            m = int(round(t * 1000))
            self.last_digit[period][m % 10] += 1
            self.round_sec["all"] += 1
            self.round_sec["at000"] += m % 1000 == 0
            cheap = px <= limit + EPS
            if 479000 <= m < 482000:
                self.ms_n[m - 479000] += 1
                self.ms_c[m - 479000] += c
            if R0 <= m < R1:
                b = (m - R0) // BW
                per[b] += c
                self.trades[b] += 1
                self.under[b] += c if cheap else 0.0
                stamps[b].add(m)
            if 480000 <= m < 510000:
                for x in (*GONE, 486.0, 510.0):
                    if m < round(x * 1000):
                        u[("all", x)] += c
                        if cheap:
                            u[("under", x)] += c
        self.vol += per
        self.period[period] += per
        for b in range(NB):
            self.sweeps[b] += len(stamps[b])
            if per[b] > 0:
                self.active[b].append(per[b])
        for k, v in u.items():
            self.gone[k] += v
        for kind in ("all", "under"):
            base = u.get((kind, 510.0), 0.0)
            if base > 0:
                self.mgone[(kind, "n")] += 1
                for x in GONE + (486.0,):
                    self.mgone[(kind, x)] += u.get((kind, x), 0.0) / base

    def report(self):
        n = self.markets
        rows = []
        for b in range(NB):
            act = sorted(self.active[b])
            na = len(act)
            med_all = 0.0 if na < n / 2 else float(np.median(np.concatenate([np.zeros(n - na), act])))
            rows.append({"from": round((R0 + b * BW) / 1000, 1), "contracts": round(float(self.vol[b]), 1),
                         "underLimit": round(float(self.under[b]), 1), "trades": int(self.trades[b]),
                         "takerOrders": int(self.sweeps[b]), "marketsTrading": na,
                         "medianPerMarket": med_all,
                         "medianPerTradingMarket": round(float(np.median(act)), 2) if na else None,
                         "meanPerMarket": round(float(self.vol[b]) / n, 3)})
        s480 = self.vol[20:30].sum()
        share480 = [round(float(v / s480), 4) for v in self.vol[20:30]]
        by_period = {}
        for k, v in self.period.items():
            tot = v[20:30].sum()
            by_period[k] = {"second480": round(float(tot)), "shares": [round(float(x / tot), 4) for x in v[20:30]]
                            if tot else None, "perSecond478to486": [round(float(v[i:i + 10].sum())) for i in range(0, NB, 10)]}
        base = {(k, x): self.gone[(k, x)] for k in ("all", "under") for x in (486.0, 510.0)}
        gone = {}
        for kind in ("under", "all"):
            gone[kind] = {f"{x:g}": {"of480to486": share(self.gone[(kind, x)], base[(kind, 486.0)]),
                                     "of480to510": share(self.gone[(kind, x)], base[(kind, 510.0)]),
                                     "marketMeanOf480to510": share(self.mgone[(kind, x)], self.mgone[(kind, "n")])}
                          for x in GONE + (486.0,)}
            gone[kind]["contracts480to486"] = round(base[(kind, 486.0)])
            gone[kind]["contracts480to510"] = round(base[(kind, 510.0)])
        # near the mark: 10 ms bins from 479.90 to 480.50, and each ms from 479.990 to 480.020
        ten = [{"from": round(479.9 + i * 0.01, 2), "trades": int(self.ms_n[900 + 10 * i: 910 + 10 * i].sum()),
                "contracts": round(float(self.ms_c[900 + 10 * i: 910 + 10 * i].sum()), 1)} for i in range(60)]
        one = [{"ms": round(479.99 + i * 0.001, 3), "trades": int(self.ms_n[990 + i]),
                "contracts": round(float(self.ms_c[990 + i]), 1)} for i in range(31)]
        # a spike at exactly 480.000: that ms against the average ms around it (479.900-480.100, itself left out)
        around = np.r_[self.ms_n[900:1000], self.ms_n[1001:1100]]
        aroundc = np.r_[self.ms_c[900:1000], self.ms_c[1001:1100]]
        spike = {"trades480000": int(self.ms_n[1000]), "meanTradesPerMs479.9to480.1": round(float(around.mean()), 2),
                 "contracts480000": round(float(self.ms_c[1000]), 1),
                 "meanContractsPerMs479.9to480.1": round(float(aroundc.mean()), 2),
                 "trades481000": int(self.ms_n[2000]), "meanTradesPerMs480.9to481.1":
                     round(float(np.r_[self.ms_n[1900:2000], self.ms_n[2001:2100]].mean()), 2),
                 "trades479000": int(self.ms_n[0]), "meanTradesPerMs479.0to479.1": round(float(self.ms_n[1:100].mean()), 2)}
        res = {k: {"tradeTimes": int(v.sum()), "lastMsDigitShares": [round(float(x / v.sum()), 4) for x in v]}
               for k, v in self.last_digit.items()}
        res["atWholeSecond"] = {"trades": int(self.round_sec["at000"]), "of": int(self.round_sec["all"]),
                                "share": share(self.round_sec["at000"], self.round_sec["all"], 5), "expected": 0.001}
        return {"markets": n, "buckets": rows, "second480Shares": share480, "second480Contracts": round(float(s480)),
                "byPeriod": by_period, "goneBy": gone, "nearMark10ms": ten, "nearMark1ms": one, "spike": spike,
                "resolution": res}


# ------------------------------------------------------------------ 2. the fill model
def model(T, P, Cn, top, want, sends, lims):
    """(got, cost), each shaped (variant, limit, send): the IOC model above for one market. T, P, Cn: the trades
    others made on our side (s after the open, sorted; price on our side; contracts)."""
    nv, nl, ns = len(VARIANTS), len(lims), len(sends)
    got, cost = np.zeros((nv, nl, ns)), np.zeros((nv, nl, ns))
    n = len(T)
    if n == 0:                                   # no trades at all: a quiet book, QUIET contracts at the ask
        k = min(want, QUIET)
        got[:], cost[:] = k, k * top
        return got, cost
    i0 = np.searchsorted(T, sends + EPS, side="right")   # the first trade after landing
    fi = np.minimum(i0, n - 1)
    first_ok = (i0 < n) & (T[fi] <= sends + FRESH + EPS)
    first_px = np.where(first_ok, P[fi], 0.0)
    for li, lim in enumerate(lims):
        ran = first_ok & (first_px > lim + EPS)          # the price ran away before the order: nothing
        quiet = np.where(first_ok, np.maximum(top, first_px), top)
        le = P <= top + EPS
        band = ~le & (P <= lim + EPS)
        cs1 = np.concatenate(([0.0], np.cumsum(np.where(le, Cn, 0.0))))
        cs2 = np.concatenate(([0.0], np.cumsum(np.where(band, Cn, 0.0))))
        cs2v = np.concatenate(([0.0], np.cumsum(np.where(band, Cn * P, 0.0))))
        for vi, (_, depth, frac) in enumerate(VARIANTS):
            i1 = np.searchsorted(T, sends + depth + EPS, side="right")
            v1 = frac * (cs1[i1] - cs1[i0])
            v2 = frac * (cs2[i1] - cs2[i0])
            v2v = frac * (cs2v[i1] - cs2v[i0])
            k = np.minimum(want, np.maximum(v1 + v2, QUIET))
            a = np.minimum(k, v1)                        # at the old limit or better: charged the old limit
            b = np.minimum(k - a, v2)                    # dearer, cheapest first, at their own prices
            c = a * top + np.where(b > 1e-9, v2v, 0.0)
            for j in np.flatnonzero((b > 1e-9) & (b < v2 - 1e-9)):   # only part of the dearer volume is needed
                seg = sorted((P[x], Cn[x] * frac) for x in range(i0[j], i1[j]) if band[x])
                need, cc = b[j], 0.0
                for px, q in seg:
                    t = min(q, need)
                    cc += t * px
                    need -= t
                    if need <= 1e-12:
                        break
                c[j] = a[j] * top + cc
            c = c + (k - a - b) * quiet                  # a quiet book: QUIET contracts where the book was
            got[vi, li] = np.where(ran, 0.0, k)
            cost[vi, li] = np.where(ran, 0.0, c)
    return got, cost


def pnl_of(k, cost, won):
    """Profit after Kalshi's exact fee (0.07 x C x P x (1 - P)) of k contracts that cost `cost` in all."""
    p = np.where(k > 0, cost / np.maximum(k, 1e-12), 0.0)
    return np.where(k > 0, (k if won else 0.0) - cost - 0.07 * k * p * (1 - p), 0.0)


def own_fills(orders):
    """{ticker: order} for the bot's accepted orders, to take its own fills out of the tapes."""
    return {o["ticker"]: o for o in orders if o["accepted"]}


def historical(orders):
    """One pass over the historical tape: the rush (part 1) and the landing-time sweep (part 2)."""
    d = C.load()
    m, side_yes, top = C.live_rule(d)
    wins = C.won(d, side_yes)
    idx = {str(d["ticker"][i]): int(i) for i in np.flatnonzero(m)}
    per = C.period_of(d["open_ts"])
    mine = own_fills(orders)
    rush = Rush()
    ns, nl, nv = len(SENDS), len(LIMITS), len(VARIANTS)
    shape = (nv, nl, ns)
    tot = defaultdict(lambda: np.zeros(shape))
    win = {}                                           # window -> [got, pnl] per config, for clustered SEs
    seen = own_out = 0
    with open(TAPE_H, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            i = idx.get(r["t"])
            if i is None:
                continue
            seen += 1
            tr = r["tr"]
            o = mine.get(r["t"])
            if o and o["filled"] > 0 and (o["side"] == "yes") == bool(side_yes[i]):
                tr, own = LF.split_own(tr, o)
                own_out += 1 if own else 0
            t0 = float(top[i])
            half = "pre" if per[i] == "pre" else "post"
            rush.add(tr, t0, period=per[i] or "other")
            want = float(np.floor(STAKE / t0 + 1e-9))
            T = np.array([x[0] for x in tr], dtype=float)
            P = np.array([x[1] for x in tr], dtype=float)
            Cn = np.array([x[2] for x in tr], dtype=float)
            got, cost = model(T, P, Cn, t0, want, SENDS, (t0, min(round(t0 + RAISE, 4), CAP)))
            pnl = pnl_of(got, cost, bool(wins[i]))
            for k, v in (("got", got), ("cost", cost), ("pnl", pnl), ("any", (got > 0).astype(float))):
                tot[k] += v
                tot[half + k] += v
            tot["want"] += want
            tot[half + "want"] += want
            w = float(d["open_ts"][i])
            if w not in win:
                win[w] = [np.zeros(shape), np.zeros(shape), 0.0]
            win[w][0] += got
            win[w][1] += pnl
            win[w][2] += want
    print(f"historical tape: {seen} of {len(idx)} live-rule bets, the bot's own fills taken out of {own_out}", flush=True)
    return rush.report(), sweep_report(tot, win, seen)


def sweep_report(tot, win, seen):
    base = int(np.flatnonzero(np.isclose(SENDS, TODAY))[0])
    G = np.stack([v[0] for v in win.values()])         # windows x configs
    PN = np.stack([v[1] for v in win.values()])
    WA = np.array([v[2] for v in win.values()])
    J = len(WA)
    rows = []
    for vi, (vname, depth, frac) in enumerate(VARIANTS):
        for li, lname in enumerate(LIMITS):
            for si, s in enumerate(SENDS):
                g = lambda k: float(tot[k][vi, li, si])   # noqa: E731
                dg = G[:, vi, li, si] - G[:, vi, li, base]
                dp = PN[:, vi, li, si] - PN[:, vi, li, base]
                se_total = lambda x: math.sqrt(J / (J - 1) * ((x - x.mean()) ** 2).sum())   # noqa: E731
                rows.append({
                    "variant": vname, "limit": lname, "landing": float(s),
                    "fillShare": share(g("got"), float(tot["want"][0, 0, 0])),
                    "fillSharePre": share(g("pregot"), float(tot["prewant"][0, 0, 0])),
                    "fillSharePost": share(g("postgot"), float(tot["postwant"][0, 0, 0])),
                    "anyFill": share(g("any"), seen),
                    "perTen": r2(g("pnl") / g("cost") * 1000) if g("cost") else None,
                    "perTenPre": r2(g("prepnl") / g("precost") * 1000) if g("precost") else None,
                    "perTenPost": r2(g("postpnl") / g("postcost") * 1000) if g("postcost") else None,
                    "avgPaid": r2(g("cost") / g("got"), 4) if g("got") else None,
                    "pnl": r2(g("pnl")), "pnlPre": r2(g("prepnl")), "pnlPost": r2(g("postpnl")),
                    "dFillVsToday": share(float(dg.sum()), float(WA.sum())),
                    "dFillVsTodaySe": share(se_total(dg), float(WA.sum())),
                    "dPnlVsToday": r2(float(dp.sum())), "dPnlVsTodaySe": r2(se_total(dp))})
    return {"bets": seen, "windows": J, "stake": STAKE, "fresh": FRESH, "depth": DEPTH, "quiet": QUIET,
            "variants": {v: {"depth_s": dpt, "shareOfEachTrade": f} for v, dpt, f in VARIANTS},
            "today": TODAY, "rows": rows,
            "note": "landing: s after the open on Kalshi's clock; fillShare: contracts filled / wanted; anyFill: orders "
                    "with any fill; perTen: P&L in c per $10 paid; dFill/dPnl: this landing minus 482.4 s, same variant "
                    "and limit, with standard errors clustered by window"}


# ------------------------------------------------------------------ 1 (live) and the model check on live orders
def live_tape(orders):
    acc = {o["ticker"]: o for o in orders if o["accepted"]}
    rush = Rush()
    us_digit = np.zeros(10)
    us_exact_ms = us_n = 0
    calib = defaultdict(float)
    calib_rows = []
    with open(TAPE_L, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            o = acc.get(r["t"])
            if o is None:
                continue
            for t, s, px, c in r["tr"]:
                us = int(round(t * 1e6))
                us_digit[us % 10] += 1
                us_exact_ms += us % 1000 == 0
                us_n += 1
            mine = LF.our_side(r["tr"], o["side"])
            clean, own = LF.split_own(mine, o)
            rush.add(clean, o["limit"])
            T = np.array([x[0] for x in clean], dtype=float)
            P = np.array([x[1] for x in clean], dtype=float)
            Cn = np.array([x[2] for x in clean], dtype=float)
            got, _ = model(T, P, Cn, o["limit"], float(o["want"]), np.array([o["send"]] + LIVE_SENDS[1:]),
                           (o["limit"], min(round(o["limit"] + RAISE, 4), CAP)))
            calib["orders"] += 1
            calib["want"] += o["want"]
            calib["real"] += o["filled"]
            calib["realAny"] += o["filled"] > 0
            row = {"id": o["id"], "landing": r2(o["landing"], 3), "want": o["want"], "filled": o["filled"]}
            for vi, (vname, _, _) in enumerate(VARIANTS):
                for li, lname in enumerate(LIMITS):
                    for si, key in enumerate(LIVE_KEYS):
                        k = f"{vname}|{lname}|{key}"
                        calib[k] += got[vi, li, si]
                        calib[k + "|any"] += got[vi, li, si] > 0
                        calib[k + "|zeroBoth"] += got[vi, li, si] == 0 and o["filled"] == 0
                row[vname] = r2(float(got[vi, 0, 0]))
            row["tape1c"], row["tape1c_480.2"] = r2(float(got[0, 1, 0])), r2(float(got[0, 1, 1]))
            row["tape_480.2"], row["window"] = r2(float(got[0, 0, 1])), int(o["wo"])
            calib_rows.append(row)
    rep = rush.report()
    rep["resolution"]["microseconds"] = {"tradeTimes": us_n, "lastUsDigitShares": [round(float(x / us_n), 4) for x in us_digit],
                                         "exactWholeMs": us_exact_ms, "exactWholeMsShare": share(us_exact_ms, us_n, 5),
                                         "expected": 0.001}
    n = calib["orders"]
    check = {"orders": int(n), "wanted": calib["want"], "realFilled": calib["real"],
             "realFillShare": share(calib["real"], calib["want"]), "realAnyFill": share(calib["realAny"], n),
             "realZero": int(n - calib["realAny"])}
    for vname, _, _ in VARIANTS:
        for lname in LIMITS:
            for key in LIVE_KEYS:
                k = f"{vname}|{lname}|{key}"
                check[f"{vname} {lname} {key}"] = {"filled": r2(calib[k]), "fillShare": share(calib[k], calib["want"]),
                                                   "anyFill": share(calib[k + "|any"], n),
                                                   **({"zeroCaught": int(calib[k + "|zeroBoth"])}
                                                      if lname == "top" and key == "atLanding" else {})}
    check["note"] = ("the model on the bot's own orders (its limit, its size, the live tape without its fills): "
                     "atLanding = each order's real landing (compare with realFillShare); at480.2 / at480.5 / at482.4 "
                     "= every order landing then, the limit unchanged (in a fast window it would be read off a book "
                     "~2 s fresher)")
    return rep, check, calib_rows


# ------------------------------------------------------------------ 3. the live breakdown
def pct(xs):
    xs = np.asarray(xs, dtype=float)
    if not len(xs):
        return None
    return {"n": int(len(xs)), "p10": r2(float(np.percentile(xs, 10)), 3), "median": r2(float(np.median(xs)), 3),
            "p90": r2(float(np.percentile(xs, 90)), 3), "mean": r2(float(xs.mean()), 3)}


def fill_row(rs):
    asked, got = sum(o["want"] for o in rs), sum(o["filled"] for o in rs)
    return {"orders": len(rs), "windows": len({o["wo"] for o in rs}), "asked": asked, "filled": r2(got),
            "fillShare": share(got, asked), "none": sum(o["filled"] <= 0 for o in rs),
            "fillShareSe": cluster_ratio_se([(o["wo"], o["filled"], o["want"]) for o in rs])}


def cluster_ratio_se(items):
    """The standard error of sum(num) / sum(den), clustered by the first element (fast_entry.ratio_se's formula)."""
    g = defaultdict(lambda: [0.0, 0.0])
    for k, a, b in items:
        g[k][0] += a
        g[k][1] += b
    num = np.array([v[0] for v in g.values()])
    den = np.array([v[1] for v in g.values()])
    J = len(num)
    if J < 2 or den.sum() <= 0:
        return None
    R = num.sum() / den.sum()
    return r2(float(math.sqrt(J / (J - 1) * ((num - R * den) ** 2).sum()) / den.sum()), 4)


def rank_key(k):
    return str(k) if k <= 5 else "6-7" if k <= 7 else "8+"


LAND_BUCKETS = ((None, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 3.5), (3.5, 4.5), (4.5, None))


def fe_ols(y, X, w, groups, fes):
    """Weighted least squares of y on X (named columns) plus fixed effects (lists of category labels), with standard
    errors clustered by `groups` (CR1: G / (G - 1)). Returns {name: (beta, se)} for X's columns."""
    cols = [np.asarray(c, dtype=float) for c in X.values()]
    for fe in fes:
        cats = sorted(set(fe))
        cols += [np.array([f == c for f in fe], dtype=float) for c in cats]
    A = np.column_stack(cols)
    y, w = np.asarray(y, float), np.asarray(w, float)
    sw = np.sqrt(w)
    Aw, yw = A * sw[:, None], y * sw
    XtX_inv = np.linalg.pinv(Aw.T @ Aw)
    beta = XtX_inv @ Aw.T @ yw
    e = y - A @ beta
    meat = np.zeros((A.shape[1], A.shape[1]))
    gidx = defaultdict(list)
    for i, g in enumerate(groups):
        gidx[g].append(i)
    for ii in gidx.values():
        s = (A[ii] * (w[ii] * e[ii])[:, None]).sum(axis=0)
        meat += np.outer(s, s)
    G = len(gidx)
    V = XtX_inv @ meat @ XtX_inv * G / (G - 1)
    return {k: (r2(float(beta[j]), 4), r2(float(math.sqrt(max(V[j, j], 0))), 4)) for j, k in enumerate(X)}, \
        {"orders": len(y), "clusters": G}


def breakdown(orders):
    acc = [o for o in orders if o["accepted"]]
    byw = defaultdict(list)
    for o in acc:
        byw[o["wo"]].append(o)
    for rs in byw.values():
        rs.sort(key=lambda o: o["id"])
        first = rs[0]
        for j, o in enumerate(rs):
            o["gap"] = None if j == 0 else o["landing"] - rs[j - 1]["landing"]
            o["prevFilled"] = None if j == 0 else rs[j - 1]["filled"] > 0
            o["first_delay"] = first["delay"]
            o["since_first"] = o["landing"] - first["landing"]
            o["n_in_window"] = len(rs)
    late = {o["wo"] for o in acc if o["lag"] > 3.2}   # steps that began late (a restart): 2 windows
    norm = [o for o in acc if o["wo"] not in late]
    out = {"orders": len(acc), "windows": len(byw), "rejected": sum(not o["accepted"] for o in orders),
           "lateStepWindows": sorted(datetime.fromtimestamp(w).isoformat(timespec="minutes") for w in late),
           "clockNote": f"step lag and send delay raw (PC clock vs Kalshi's); *Kalshi = the PC's lag + {CLOCK} s"}
    out["overall"] = {"stepLag": pct([o["lag"] for o in acc]), "landing": pct([o["landing"] for o in acc]),
                      "sendDelay": pct([o["delay"] for o in acc]),
                      "sendDelayKalshi": pct([o["delay"] - CLOCK for o in acc]),
                      "gap": pct([o["gap"] for o in acc if o["gap"] is not None]),
                      "rank": pct([o["rank"] for o in acc]),
                      "excludingLateSteps": {"stepLag": pct([o["lag"] for o in norm]),
                                             "landing": pct([o["landing"] for o in norm])}}
    ranks = sorted({rank_key(o["rank"]) for o in acc}, key=lambda k: int(k.split("-")[0].rstrip("+")))
    out["byRank"] = {k: {"stepLag": pct([o["lag"] for o in acc if rank_key(o["rank"]) == k]),
                         "landing": pct([o["landing"] for o in acc if rank_key(o["rank"]) == k]),
                         "sendDelay": pct([o["delay"] for o in acc if rank_key(o["rank"]) == k]),
                         "gap": pct([o["gap"] for o in acc if rank_key(o["rank"]) == k and o["gap"] is not None]),
                         **fill_row([o for o in acc if rank_key(o["rank"]) == k])} for k in ranks}
    out["gapByPreviousFill"] = {"previousFilled": pct([o["gap"] for o in acc if o["prevFilled"] is True]),
                                "previousGotNothing": pct([o["gap"] for o in acc if o["prevFilled"] is False])}
    out["byLanding"] = {}
    for lo, hi in LAND_BUCKETS:
        rs = [o for o in acc if (lo is None or o["landing"] >= lo) and (hi is None or o["landing"] < hi)]
        out["byLanding"][f"{lo if lo is not None else ''}-{hi if hi is not None else ''}"] = {
            **fill_row(rs), "rank1": sum(o["rank"] == 1 for o in rs)}
    out["rank1ByLanding"] = {}
    for lo, hi in ((None, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, None)):
        rs = [o for o in acc if o["rank"] == 1 and (lo is None or o["landing"] >= lo) and (hi is None or o["landing"] < hi)]
        out["rank1ByLanding"][f"{lo if lo is not None else ''}-{hi if hi is not None else ''}"] = fill_row(rs)
    # the mean landing, split exactly: step lag (PC) + the clock + the first order's delay (Kalshi) + the gaps before it
    out["meanDecomposition"] = {
        "orders": len(norm),
        "stepLagPc": r2(float(np.mean([o["lag"] for o in norm])), 3), "clock": CLOCK,
        "firstOrderDelayKalshi": r2(float(np.mean([o["first_delay"] - CLOCK for o in norm])), 3),
        "gapsBeforeIt": r2(float(np.mean([o["since_first"] for o in norm])), 3),
        "landing": r2(float(np.mean([o["landing"] for o in norm])), 3),
        "rank1Only": {"stepLagPc": pct([o["lag"] for o in norm if o["rank"] == 1]),
                      "firstOrderDelayKalshi": pct([o["delay"] - CLOCK for o in norm if o["rank"] == 1]),
                      "landing": pct([o["landing"] for o in norm if o["rank"] == 1])}}
    # is the PC's clock steady? The first order's raw delay (Kalshi's clock minus the PC's) by half day, against the
    # gaps between orders (Kalshi's clock only). A drifting PC clock moves the first, not the second.
    half = lambda o: datetime.fromtimestamp(o["wo"]).strftime("%m-%d ") + ("am" if datetime.fromtimestamp(o["wo"]).hour < 12 else "pm")  # noqa: E731
    out["clockCheck"] = {
        "note": "rank-1 raw send delay = ts_ms - orders.ts (Kalshi minus PC); gaps use Kalshi's clock alone. A raw delay "
                "under ~0.1 s is impossible for the work before the first order, so the PC clock was ahead of Kalshi then",
        "byHalfDay": {k: {"rank1RawDelay": pct([o["delay"] for o in norm if o["rank"] == 1 and half(o) == k]),
                          "gapAfterFill": pct([o["gap"] for o in norm if half(o) == k and o["prevFilled"] is True]),
                          "gapAfterNothing": pct([o["gap"] for o in norm if half(o) == k and o["prevFilled"] is False])}
                      for k in sorted({half(o) for o in norm})}}
    # natural experiments: fill share (filled / asked per order) weighted by contracts asked, SEs clustered by window
    y = [o["filled"] / o["want"] for o in norm]
    w = [o["want"] for o in norm]
    g = [o["wo"] for o in norm]
    ser = [o["series"] for o in norm]
    reg = {}
    b, info = fe_ols(y, {"landing_s": [o["landing"] for o in norm]}, w, g, [g, ser])
    reg["withinWindow_landing"] = {"coef": b, **info, "fe": "window + series",
                                   "meaning": "fill share per extra second of landing, same window and series. Biased "
                                              "down: the gap after an order is longer when it filled (fills_for), so a "
                                              "later landing partly means 'the order before filled'"}
    rnk = [min(o["rank"], 8) for o in norm]
    b, info = fe_ols(y, {"rank": rnk}, w, g, [g, ser])
    fs, _ = fe_ols([o["landing"] for o in norm], {"rank": rnk}, w, g, [g])
    reg["withinWindow_rankLinear"] = {
        "coef": b, **info, "fe": "window + series", "secondsPerRank": fs["rank"],
        "perSecond": r2(b["rank"][0] / fs["rank"][0], 3), "perSecondSe": r2(b["rank"][1] / fs["rank"][0], 3),
        "meaning": "fill share per place later in the window's queue (rank capped at 8), same window and series; "
                   "perSecond = that / the seconds each place adds (a Wald / IV estimate, landing instrumented by rank)"}
    rk = {f"rank{k}": [float(rank_key(o["rank"]) == k) for o in norm] for k in ranks if k != "1"}
    b, info = fe_ols(y, rk, w, g, [g, ser])
    reg["withinWindow_rank"] = {"coef": b, **info, "fe": "window + series", "meaning": "vs rank 1"}
    b, info = fe_ols(y, {"landing_s": [o["landing"] for o in norm]}, w, g, [ser])
    reg["acrossWindows_landing_seriesFE"] = {"coef": b, **info, "fe": "series"}
    r1 = [o for o in norm if o["rank"] == 1]
    b, info = fe_ols([o["filled"] / o["want"] for o in r1], {"stepLag_s": [o["lag"] for o in r1]},
                     [o["want"] for o in r1], [o["wo"] for o in r1], [[o["series"] for o in r1]])
    reg["rank1_stepLag_seriesFE"] = {"coef": b, **info, "fe": "series",
                                     "meaning": "first orders only: fill share per extra second of step lag (where the "
                                                "3 s loop happened to wake), same series"}
    b, info = fe_ols(y, {"stepLag_s": [o["lag"] for o in norm]}, w, g,
                     [ser, [rank_key(o["rank"]) for o in norm]])
    reg["all_stepLag_seriesRankFE"] = {"coef": b, **info, "fe": "series + rank"}
    days = [datetime.fromtimestamp(o["wo"]).strftime("%Y-%m-%d") for o in norm]
    b, info = fe_ols(y, {"stepLag_s": [o["lag"] for o in norm]}, w, g,
                     [ser, [rank_key(o["rank"]) for o in norm], days])
    reg["all_stepLag_seriesRankDayFE"] = {"coef": b, **info, "fe": "series + rank + day"}
    # within window, the simple version: rank 1's fill share minus the later orders', windows with 2+ orders
    diffs = []
    for rs in byw.values():
        if rs[0]["wo"] in late or len(rs) < 2:
            continue
        f1 = rs[0]["filled"] / rs[0]["want"]
        later = sum(o["filled"] for o in rs[1:]) / sum(o["want"] for o in rs[1:])
        diffs.append(f1 - later)
    diffs = np.array(diffs)
    reg["rank1MinusLater_sameWindow"] = {"windows": len(diffs), "mean": r2(float(diffs.mean()), 4),
                                         "se": r2(float(diffs.std(ddof=1) / math.sqrt(len(diffs))), 4),
                                         "note": "not controlled for series: the bot sends in Kalshi's series order"}
    out["regressions"] = reg
    first_series = defaultdict(int)
    for rs in byw.values():
        first_series[rs[0]["series"]] += 1
    out["firstOrderSeries"] = dict(sorted(first_series.items(), key=lambda kv: -kv[1]))
    out["bySeries"] = {s: fill_row([o for o in acc if o["series"] == s]) | {"meanRank": r2(float(np.mean(
        [o["rank"] for o in acc if o["series"] == s])), 2)} for s in sorted({o["series"] for o in acc})}
    out["perOrder"] = [{"id": o["id"], "window": int(o["wo"]), "series": o["series"], "rank": o["rank"],
                        "stepLag": r2(o["lag"], 3), "landing": r2(o["landing"], 3), "sendDelay": r2(o["delay"], 3),
                        "gap": r2(o["gap"], 3), "want": o["want"], "filled": o["filled"]} for o in acc]
    return out


# ------------------------------------------------------------------ 4. power
def power(orders, rows=None):
    acc = [o for o in orders if o["accepted"]]
    end = max(o["ts"] for o in acc)
    res = {}
    # series-adjusted: each order's contracts asked x its series' fill share, subtracted (a regression adjustment)
    ss = defaultdict(lambda: [0.0, 0.0])
    for o in acc:
        ss[o["series"]][0] += o["filled"]
        ss[o["series"]][1] += o["want"]
    for label, rs in (("all", acc), ("last3days", [o for o in acc if o["ts"] > end - 3 * 86400])):
        g = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
        for o in rs:
            v = g[o["wo"]]
            v[0] += o["filled"]
            v[1] += o["want"]
            v[2] += o["want"] * ss[o["series"]][0] / ss[o["series"]][1]
            v[3] += 1
        num = np.array([v[0] for v in g.values()])
        den = np.array([v[1] for v in g.values()])
        exp = np.array([v[2] for v in g.values()])
        J = len(num)
        R = num.sum() / den.sum()
        F = num / den
        sig = float(np.sqrt(((num - R * den) ** 2).sum() / (J - 1)) / den.mean())   # per window, ratio-weighted
        Ra = (num - exp).sum() / den.sum()
        sig_adj = float(np.sqrt((((num - exp) - Ra * den) ** 2).sum() / (J - 1)) / den.mean())
        days = (end - min(o["ts"] for o in rs)) / 86400 if label == "all" else 3.0
        wpd = J / days
        need = {}
        for dlt in (0.05, 0.10, 0.15):
            for name, s in (("plain", sig), ("seriesAdjusted", sig_adj)):
                n = math.ceil(2 * (Z_SIG + Z_POW) ** 2 * s ** 2 / dlt ** 2)
                need[f"+{round(dlt * 100)}pts {name}"] = {"windowsPerArm": n, "windowsTotal": 2 * n,
                                                          "days": r2(2 * n / wpd, 1)}
        res[label] = {"windows": J, "orders": len(rs), "days": r2(days, 2), "windowsPerDay": r2(wpd, 1),
                      "ordersPerDay": r2(len(rs) / days, 1), "pooledFillShare": r2(float(R), 4),
                      "windowFillShare": {"mean": r2(float(F.mean()), 4), "median": r2(float(np.median(F)), 4),
                                          "sd": r2(float(F.std(ddof=1)), 4), "p10": r2(float(np.percentile(F, 10)), 4),
                                          "p90": r2(float(np.percentile(F, 90)), 4)},
                      "sdPerWindowRatioWeighted": r2(sig, 4), "sdPerWindowSeriesAdjusted": r2(sig_adj, 4),
                      "ordersPerWindow": r2(float(np.mean([v[3] for v in g.values()])), 2), "need": need,
                      "detectableAt50PerArm": r2((Z_SIG + Z_POW) * sig * math.sqrt(2 / 50), 4)}
        # the other design: a coin per market within each window (half sent fast, half at the usual time). Its noise
        # is the order-to-order spread within a window, not the window-to-window one. Windows with 2+ orders only.
        multi = [o for o in rs if g[o["wo"]][3] >= 2]
        byw = defaultdict(list)
        for o in multi:
            byw[o["wo"]].append(o["filled"] / o["want"])
        resid = [x - np.mean(v) for v in byw.values() for x in v]
        sig_e = math.sqrt(sum(e * e for e in resid) / (len(resid) - len(byw)))
        opd = len(multi) / days
        res[label]["withinWindowDesign"] = {
            "orders": len(multi), "ordersPerDay": r2(opd, 1), "sdOrderWithinWindow": r2(sig_e, 4),
            "sdOrderOverall": r2(float(np.std([o["filled"] / o["want"] for o in rs], ddof=1)), 4),
            "need": {f"+{round(dlt * 100)}pts": {"ordersPerArm": (n := math.ceil(2 * (Z_SIG + Z_POW) ** 2 * sig_e ** 2 / dlt ** 2)),
                                                 "days": r2(2 * n / opd, 1)} for dlt in (0.05, 0.10, 0.15)}}
    # with the +1c limit in both arms: the tape model's fills for the live orders (their own sizes and tape) give a
    # rough window spread and the fast-entry effect to plan for (model-based, not measured)
    if rows:
        def spread_of(key):
            g = defaultdict(lambda: [0.0, 0.0])
            for r in rows:
                g[r["window"]][0] += r[key]
                g[r["window"]][1] += r["want"]
            num = np.array([v[0] for v in g.values()])
            den = np.array([v[1] for v in g.values()])
            R = num.sum() / den.sum()
            return float(R), float(np.sqrt(((num - R * den) ** 2).sum() / (len(num) - 1)) / den.mean()), len(num)
        out = {}
        for label, now_key, fast_key in (("limitTop", "tape", "tape_480.2"), ("limitTop+1c", "tape1c", "tape1c_480.2")):
            R0_, s0, J = spread_of(now_key)
            R1_, s1, _ = spread_of(fast_key)
            dlt = R1_ - R0_
            s = max(s0, s1)
            n = math.ceil(2 * (Z_SIG + Z_POW) ** 2 * s ** 2 / dlt ** 2) if dlt > 0 else None
            wpd = res["last3days"]["windowsPerDay"]
            out[label] = {"windows": J, "modelFillShareNow": r2(R0_, 4), "modelFillShareAt480.2": r2(R1_, 4),
                          "effect": r2(dlt, 4), "sdNow": r2(s0, 4), "sdAt480.2": r2(s1, 4), "windowsPerArm": n,
                          "days": r2(2 * n / wpd, 1) if n else None}
        res["modelBased"] = {**out, "note": "the tape model on the live orders at their real landing vs all at 480.2, "
                                            "same limit; sd = the larger of the two; days at the last 3 days' pace"}
    res["formula"] = ("windows per arm n = 2 (z_sig + z_pow)^2 sd^2 / delta^2, z_sig = 2 (a 2-standard-error test), "
                      "z_pow = 0.8416 (80% power); sd = the per-window spread of the ratio filled / asked, "
                      "sqrt(sum (num_j - R den_j)^2 / (J - 1)) / mean(den), clustered by window; both arms share "
                      "the days, so days = 2n / windows a day")
    return res


# ------------------------------------------------------------------ helpers, main
def r2(x, k=2):
    return None if x is None else round(x, k)


def share(a, b, k=4):
    return round(a / b, k) if b else None


def main():
    t0 = time.time()
    orders = read_orders()
    print(f"{len(orders)} buy orders, {sum(o['accepted'] for o in orders)} accepted", flush=True)
    live_rush, check, calib_rows = live_tape(orders)
    print(f"live tape: {live_rush['markets']} markets ({time.time() - t0:.0f}s)", flush=True)
    hist_rush, sweep = historical(orders)
    print(f"historical done ({time.time() - t0:.0f}s)", flush=True)
    out = {"generated": datetime.now().isoformat(timespec="seconds"),
           "notes": {"time": "seconds after the window opened (on Kalshi's clock for trades and ts_ms)",
                     "side": "the bot's side: the favourite (historical) or the side it bought (live); the bot's own "
                             "fills taken out of both tapes",
                     "clock": f"Kalshi ~ PC + {CLOCK} s (SNTP, 4 servers, Oct 11)",
                     "orders": f"{len(orders)} buy orders in live-prod.db through "
                               f"{datetime.fromtimestamp(orders[-1]['ts']).isoformat(timespec='minutes')}; the live "
                               "tape covers the first 473 accepted"},
           "rush": {"historical": hist_rush, "live": live_rush},
           "sweep": sweep, "modelCheckLive": check, "breakdown": breakdown(orders), "power": power(orders, calib_rows),
           "modelCheckLiveOrders": calib_rows}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    show(out)
    print(f"wrote {OUT} ({time.time() - t0:.0f}s)")


def show(out):
    for k in ("historical", "live"):
        r = out["rush"][k]
        print(f"\n== rush, {k}: {r['markets']} markets; second 480 = {r['second480Contracts']} contracts")
        print("   second-480 shares by 100 ms:", r["second480Shares"])
        print("   gone by (under limit):", json.dumps(r["goneBy"]["under"]))
        print("   spike:", json.dumps(r["spike"]))
        print("   resolution:", json.dumps(r["resolution"]))
        for b in r["buckets"]:
            if 479.0 <= b["from"] < 483.0:
                print("   ", json.dumps(b))
        print("   near the mark (10 ms):", [(x["from"], x["trades"], x["contracts"]) for x in r["nearMark10ms"][:30]])
    print("\n== sweep (tape / book1s / split), limit top")
    for row in out["sweep"]["rows"]:
        if row["landing"] in (480.0, 480.2, 480.5, 481.0, 481.5, 482.0, 482.4, 483.0, 484.0):
            print("  ", json.dumps({k: row[k] for k in ("variant", "limit", "landing", "fillShare", "anyFill", "perTen",
                                                         "perTenPre", "perTenPost", "pnl", "dFillVsToday",
                                                         "dFillVsTodaySe", "dPnlVsToday", "dPnlVsTodaySe")}))
    print("\n== model check on live orders:", json.dumps(out["modelCheckLive"], indent=1))
    b = out["breakdown"]
    print("\n== breakdown overall:", json.dumps(b["overall"], indent=1))
    print("mean decomposition:", json.dumps(b["meanDecomposition"], indent=1))
    for k, v in b["byRank"].items():
        print("  rank", k, json.dumps(v))
    print("gap by previous fill:", json.dumps(b["gapByPreviousFill"]))
    for k, v in b["byLanding"].items():
        print("  landing", k, json.dumps(v))
    for k, v in b["rank1ByLanding"].items():
        print("  rank1 landing", k, json.dumps(v))
    print("regressions:", json.dumps(b["regressions"], indent=1))
    print("first-order series:", json.dumps(b["firstOrderSeries"]))
    print("\n== power:", json.dumps(out["power"], indent=1))


if __name__ == "__main__":
    main()
