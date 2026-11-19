"""Fair value from the underlying: does a coin's own spot price say which 15-minute crypto favourites to skip, or which
side to buy?

Settlement (Kalshi's rules_primary, checked against every market's strike in spot/strikes.npz): YES wins when the simple
average of the 60 seconds of CF Benchmarks' index (BRTI and the like) before the close is at least the same average
before the open; the strike (floor_strike) is that opening average, which is also the previous window's settlement value.

The model, at the end of minute m (6, 8, 10, 12):
    x    = ln(S / K): S the Coinbase close of the minute that ends at the decision, K the opening average - either
           Coinbase's own average of the minute before the open ("cb", which cancels any steady gap between Coinbase and
           the index) or Kalshi's strike ("strike")
    sig  = per-minute volatility from Coinbase 1-minute log returns that closed by the decision (last 30/60/240 minutes,
           or an EWMA with a 30/120-minute half-life), floored at 1 bp
    tau  = (14 - m) + 1/3 minutes: to the start of minute 15, plus a third of a minute for averaging over it
    P(YES) = Phi(x / (k sig sqrt(tau))), or a Student-t CDF in place of Phi; the K source, sig recipe, scale k and tails
             are picked on the train half only, by log loss over every crypto market (no drift)

Then, on each split (pick on Dec 10 - Jul 17, test on Jul 18 - Oct 8; then the reverse):
    calibration  Brier and log loss of the market's mid, the model, and both together (a logistic fit on the train half)
    edge buckets the live rule's crypto bets by P_model(favourite) - its ask, and what each bucket earned
    (a) the live rule (common.live_rule: 90-99.9c favourite, skip spread and late signs, Fed blackouts), crypto bets
    (b) (a), skipping a bet when P_model(favourite) < ask + margin (margin picked on the train half by $ profit)
    (b2) the same with the market and model together (the calibration's logistic fit) in place of P_model
    (c) model only: every crypto market, buy the side the model says is X or more under its ask, at any price
$10 a bet in whole contracts at the ask + 0.4c, Kalshi's taker fee, held to settlement (common.bet); cents per $10 with a
95% range clustered by window (common.summary).

    python fair_value.py           -> fair_value.json (and the printout)
"""
import json
import math
import os
import sys

import numpy as np
from scipy.signal import lfilter
from scipy.special import ndtr, stdtr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

SPOT = os.path.join(HERE, "spot")
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "HYPE", "NEAR", "ZEC"]
MINUTES = (6, 8, 10, 12)
SIG_FLOOR = 1e-4
SPECS = (("rv", 30), ("rv", 60), ("rv", 240), ("ewma", 30), ("ewma", 120))
KS = np.round(np.arange(0.5, 2.51, 0.05), 2)
NUS = (None, 20, 10, 6, 4, 3)    # tails: normal, then Student-t with these degrees of freedom
MARGINS = (-0.20, -0.15, -0.10, -0.07, -0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02)
XS = (0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20)
BUCKETS = (-1.0, -0.20, -0.10, -0.05, -0.02, 0.0, 0.02, 1.0)
SPLIT = C.PERIODS[1][2]          # Jul 18
END = C.PERIODS[-1][3]           # Oct 9 (the last window opens Oct 8)


# ---- the model's pieces -------------------------------------------------------------------------------------------

def tau_eff(m):
    """Minutes of variance left at the end of minute m: to the closing average over minute 15, which adds a third."""
    return (14 - m) + 1 / 3


def p_yes(x, sig, m, k=1.0, nu=None):
    """P(YES): the scaled move through a normal CDF, or a Student-t one with nu degrees of freedom (fatter tails)."""
    z = x / (k * np.maximum(sig, SIG_FLOOR) * math.sqrt(tau_eff(m)))
    return ndtr(z) if nu is None else stdtr(nu, z)


def _returns(logc):
    r = np.diff(logc)
    return np.where(np.isnan(r), 0.0, r)


def realized_sigma(logc, L):
    """Per-minute RMS log return over the L minutes ending at each index (returns into minutes i-L+1..i), NaN before
    L minutes of history. Nothing after index i enters."""
    r2 = _returns(logc) ** 2
    cum = np.concatenate([[0.0], np.cumsum(r2)])        # cum[j] = sum of r2[0:j], r2[j] the move into minute j+1
    out = np.full(len(logc), np.nan)
    i = np.arange(L, len(logc))
    out[i] = np.sqrt((cum[i] - cum[i - L]) / L)
    out[np.isnan(logc)] = np.nan
    return out


def ewma_sigma(logc, hl):
    """EWMA per-minute volatility with a half-life of hl minutes, using moves up to and including the one into minute i."""
    lam = 0.5 ** (1 / hl)
    v = lfilter([1 - lam], [1, -lam], _returns(logc) ** 2)
    out = np.full(len(logc), np.nan)
    out[1:] = np.sqrt(v)
    out[: int(3 * hl)] = np.nan
    out[np.isnan(logc)] = np.nan
    return out


def sigma(logc, spec):
    kind, n = spec
    return realized_sigma(logc, n) if kind == "rv" else ewma_sigma(logc, n)


def _take(arr, i):
    ok = (i >= 0) & (i < len(arr))
    return np.where(ok, arr[np.clip(i, 0, len(arr) - 1)], np.nan)


def spot_features(grid, opens, m, lag=0):
    """S: the close of the minute candle ending at open + m min (lag: that many minutes earlier); K: Coinbase's average
    over the minute before the open; F: its average over minute 15 (the settlement minute). iS: S's grid index."""
    t0 = int(grid["t0"])
    iS = (opens + 60 * (m - 1 - lag) - t0) // 60
    iK = (opens - 60 - t0) // 60
    iF = (opens + 840 - t0) // 60
    return {"S": _take(grid["close"], iS), "K": _take(grid["avg"], iK), "F": _take(grid["avg"], iF), "iS": iS}


def fav_keep(p_fav, top, margin):
    """(b)'s filter: keep a live-rule bet unless the model prices the favourite under its ask + margin. No model: keep."""
    return np.isnan(p_fav) | (p_fav >= top + margin - 1e-12)


def model_pick(p, ask, bid, X):
    """(c): (bet, side_yes, price, edge) - the side whose model value beats its ask by more, bought if by X or more."""
    ask_no = np.round(1 - bid, 4)
    e_yes, e_no = p - ask, (1 - p) - ask_no
    side_yes = e_yes >= e_no
    edge = np.where(side_yes, e_yes, e_no)
    price = np.where(side_yes, ask, ask_no)
    with np.errstate(invalid="ignore"):
        bet = (edge >= X - 1e-12) & (price >= 0.01) & (price <= 0.999)
    return bet, side_yes, price, edge


def logit_fit(X, y, iters=50, ridge=1e-6):
    """Logistic regression with an intercept by Newton's method: [b0, b1, ...]."""
    A = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-A @ b))
        g = A.T @ (y - p) - ridge * b
        H = (A * (p * (1 - p))[:, None]).T @ A + ridge * np.eye(len(b))
        step = np.linalg.solve(H, g)
        b += step
        if np.abs(step).max() < 1e-10:
            break
    return b


def pick(train):
    """The option with the most train-half profit (dict order breaks ties, so "none" first wins them)."""
    return max(train, key=lambda k: train[k])


# ---- the analysis -------------------------------------------------------------------------------------------------

def load_spot(coin):
    path = os.path.join(SPOT, f"{coin}.npz")
    if not os.path.exists(path):
        return None
    z = np.load(path)
    return {"t0": int(z["t0"]), "close": z["close"], "avg": z["avg"], "have": z["have"]}


def logloss(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(np.where(y, np.log(p), np.log(1 - p))))


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def build(d, minutes, lags=(0,)):
    """Per-market spot features at each (minute, lag): S, K (Coinbase), F, every sig recipe; NaN without spot."""
    n = len(d["ticker"])
    coin = np.array([s[2:-3] for s in d["series"]])
    nan = lambda: np.full(n, np.nan)
    out = {(m, lag): {"S": nan(), "K": nan(), "F": nan(), **{s: nan() for s in SPECS}} for m in minutes for lag in lags}
    for c in COINS:
        g = load_spot(c)
        sel = np.where(coin == c)[0]
        if g is None or not len(sel):
            continue
        logc = np.log(g["close"])
        sigs = {s: sigma(logc, s) for s in SPECS}
        for (m, lag), o in out.items():
            f = spot_features(g, d["open_ts"][sel], m, lag)
            for key in ("S", "K", "F"):
                o[key][sel] = f[key]
            for s, arr in sigs.items():
                o[s][sel] = _take(arr, f["iS"])
        del logc, sigs
    return out, coin


def strikes_for(d):
    z = np.load(os.path.join(SPOT, "strikes.npz"))
    look = dict(zip(z["ticker"].tolist(), zip(z["strike"].tolist(), z["settle"].tolist(), z["yes"].tolist())))
    got = [look.get(t, (np.nan, np.nan, -1)) for t in d["ticker"].tolist()]
    return np.array([g[0] for g in got]), np.array([g[1] for g in got]), np.array([g[2] for g in got])


def mismatch(d, feats, coin, strike, settle, kyes):
    """How far Coinbase sits from the index: its opening-minute average vs the strike, and whether its own version of
    the settlement (minute-15 average >= opening average) calls the market the way Kalshi did."""
    f = feats[(8, 0)]
    out = {"rule": {}, "byCoin": {}}
    has = ~np.isnan(strike) & ~np.isnan(settle)
    out["rule"] = {"markets": int(has.sum()),
                   "settle>=strike matches result": float(np.mean((settle[has] >= strike[has]) == (kyes[has] == 1))),
                   "result in markets.npz matches listing": float(np.mean(kyes[has] == d["yes"][has]))}
    prev = {}
    for c in COINS:
        s = (coin == c)
        ok = s & has & ~np.isnan(f["K"])
        if not ok.any():
            continue
        bps = 1e4 * np.log(f["K"][ok] / strike[ok])
        cb_call = f["F"][ok] >= f["K"][ok]
        prev[c] = {"markets": int(ok.sum()), "gapBpsMedian": float(np.median(bps)),
                   "absGapBpsMedian": float(np.median(np.abs(bps))), "absGapBps95": float(np.percentile(np.abs(bps), 95)),
                   "coinbaseCallsResult": float(np.mean(cb_call == (d["yes"][ok] == 1))),
                   "absMoveBpsMedian": float(np.median(np.abs(1e4 * np.log(settle[ok] / strike[ok]))))}
    out["byCoin"] = prev
    return out


def fit_model(y, mid, xs, sigs, m, mask):
    """The K source, sig recipe and scale k with the lowest log loss over `mask` (the train half)."""
    common = mask & ~np.isnan(mid)
    for x in xs.values():
        common &= ~np.isnan(x)
    for s in sigs.values():
        common &= ~np.isnan(s)
    best = None
    for src, x in xs.items():          # the K source and sig recipe, with normal tails
        for spec, sg in sigs.items():
            for k in KS:
                ll = logloss(p_yes(x[common], sg[common], m, k), y[common])
                if best is None or ll < best[0]:
                    best = (ll, src, spec, float(k), None)
    src, spec = best[1], best[2]
    x, sg = xs[src][common], sigs[spec][common]
    for nu in NUS[1:]:                 # then the tails, refitting the scale with each
        for k in KS:
            ll = logloss(p_yes(x, sg, m, k, nu), y[common])
            if ll < best[0]:
                best = (ll, src, spec, float(k), nu)
    return {"src": src, "spec": spec, "k": best[3], "nu": best[4], "trainLogLoss": best[0], "fitMarkets": int(common.sum())}


def split_masks(t):
    pre = t < SPLIT
    post = (t >= SPLIT) & (t < END)
    return pre, post


def stats(pnl, cost, t):
    s = C.summary(pnl, cost, t)
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()}


def analyse_minute(d, feats, coin, strike, m, train, test, lag_check=False):
    f = feats[(m, 0)]
    y = d["yes"] == 1
    t = d["open_ts"]
    crypto = d["group"] == "crypto"
    bid, ask = d["bid"][:, m - 1], d["ask"][:, m - 1]
    mid = np.where(np.isnan(bid) | np.isnan(ask), np.nan, (bid + ask) / 2)
    xs = {"cb": np.log(f["S"] / f["K"]), "strike": np.log(f["S"] / strike)}
    sigs = {f"{a}{b}": f[(a, b)] for a, b in SPECS}
    fit = fit_model(y, mid, xs, sigs, m, crypto & train)
    P = p_yes(xs[fit["src"]], sigs[fit["spec"]], m, fit["k"], fit["nu"])
    P[np.isnan(xs[fit["src"]]) | np.isnan(sigs[fit["spec"]])] = np.nan
    res = {"model": fit}

    # calibration over every crypto market with a model value and a quote
    ok = crypto & ~np.isnan(P) & ~np.isnan(mid)
    beta = logit_fit(np.column_stack([logit(mid[ok & train]), logit(P[ok & train])]), y[ok & train])
    both = 1 / (1 + np.exp(-(beta[0] + beta[1] * logit(mid) + beta[2] * logit(P))))
    res["calibration"] = {"combinedFit": [round(float(b), 3) for b in beta]}
    for name, s in (("train", ok & train), ("test", ok & test)):
        res["calibration"][name] = {"markets": int(s.sum()), **{
            src: {"brier": round(brier(p[s], y[s]), 5), "logloss": round(logloss(p[s], y[s]), 5)}
            for src, p in (("market mid", mid), ("model", P), ("both", both))}}

    # the live rule's crypto bets, and the model's view of each favourite
    lm, side_yes, top = C.live_rule(d, M=m)
    lm &= crypto
    wins = C.won(d, side_yes)
    p_fav = np.where(side_yes, P, 1 - P)
    gap = p_fav - top
    res["liveCryptoBets"] = {"all": int(lm.sum()), "withModel": int((lm & ~np.isnan(P)).sum())}

    def run_mask(mask, price=top, w=wins):
        pnl, cost = C.bet(price[mask], w[mask])
        return pnl, cost, t[mask]

    def both_halves(mask, price=top, w=wins):
        return {name: stats(*run_mask(mask & s, price, w)) for name, s in (("train", train), ("test", test))}

    res["edgeBuckets"] = []
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        b = lm & (gap > lo) & (gap <= hi)
        res["edgeBuckets"].append({"gap": f"{lo:+.2f} to {hi:+.2f}", **both_halves(b)})

    res["a_live"] = both_halves(lm)
    tab = {"none": both_halves(lm)}
    for mg in MARGINS:
        tab[mg] = both_halves(lm & fav_keep(p_fav, top, mg))
    choice = pick({k: v["train"]["pnl"] for k, v in tab.items()})
    res["b_filter"] = {"chosenMargin": choice, "chosen": tab[choice],
                       "table": [{"margin": k, "trainBets": v["train"]["bets"], "trainPerBet": v["train"]["perBet"],
                                  "trainPnl": v["train"]["pnl"], "testBets": v["test"]["bets"],
                                  "testPerBet": v["test"]["perBet"], "testPnl": v["test"]["pnl"]} for k, v in tab.items()]}

    tabc = {}
    for X in XS:
        bet_m, sy, price, _ = model_pick(P, ask, bid, X)
        bet_m &= crypto & ~C.blackout(d)
        tabc[X] = both_halves(bet_m, price, C.won(d, sy))
    # (b2) the same filter on the market and model together (the train half's logistic fit) instead of the model alone
    pb_fav = np.where(side_yes, both, 1 - both)
    pb_fav[np.isnan(P)] = np.nan
    tab2 = {"none": tab["none"], **{mg: both_halves(lm & fav_keep(pb_fav, top, mg)) for mg in MARGINS}}
    c2 = pick({k: v["train"]["pnl"] for k, v in tab2.items()})
    res["b2_filterBoth"] = {"chosenMargin": c2, "chosen": tab2[c2],
                            "table": [{"margin": k, "trainBets": v["train"]["bets"], "trainPnl": v["train"]["pnl"],
                                       "testBets": v["test"]["bets"], "testPnl": v["test"]["pnl"]} for k, v in tab2.items()]}
    cx = pick({k: v["train"]["pnl"] for k, v in tabc.items()})
    bet_m, sy, price, _ = model_pick(P, ask, bid, cx)
    bet_m &= crypto & ~C.blackout(d)
    by_price = [{"price": f"{lo:.2f}-{hi:.2f}", **both_halves(bet_m & (price >= lo) & (price < hi), price, C.won(d, sy))}
                for lo, hi in ((0, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 1.0))]
    res["c_modelOnly"] = {"chosenX": cx, "chosen": tabc[cx], "byPrice": by_price,
                          "table": [{"X": k, "trainBets": v["train"]["bets"], "trainPerBet": v["train"]["perBet"],
                                     "trainPnl": v["train"]["pnl"], "testBets": v["test"]["bets"],
                                     "testPerBet": v["test"]["perBet"], "testPnl": v["test"]["pnl"]} for k, v in tabc.items()]}

    if lag_check and (m, 1) in feats:   # spot one minute stale: the same fitted model, on a minute-old price
        g1 = feats[(m, 1)]
        x1 = np.log(g1["S"] / (g1["K"] if fit["src"] == "cb" else strike))
        P1 = p_yes(x1, g1[tuple(_spec(fit["spec"]))], m, fit["k"], fit["nu"])
        P1[np.isnan(x1)] = np.nan
        pf1 = np.where(side_yes, P1, 1 - P1)
        out = {}
        if choice != "none":
            out["b"] = both_halves(lm & fav_keep(pf1, top, choice))
        bet_m, sy, price, _ = model_pick(P1, ask, bid, cx)
        out["c"] = both_halves(bet_m & crypto & ~C.blackout(d), price, C.won(d, sy))
        res["staleSpot1min"] = out
    return res


def _spec(name):
    kind = "ewma" if name.startswith("ewma") else "rv"
    return kind, int(name[len(kind):])


def main():
    d = C.load()
    feats, coin = build(d, MINUTES, lags=(0,))
    feats.update(build(d, (8, 12), lags=(1,))[0])
    strike, settle, kyes = strikes_for(d)
    pre, post = split_masks(d["open_ts"])
    out = {"settlement": "YES iff the 60-second average of CF Benchmarks' index before the close >= the same average "
                         "before the open (floor_strike = the opening average = the previous window's settlement value)",
           "spotCoverage": {}, "mismatch": mismatch(d, feats, coin, strike, settle, kyes), "splits": {}}
    for c in COINS:
        s = coin == c
        if s.any():
            out["spotCoverage"][c] = {"markets": int(s.sum()), "withSpot": int((s & ~np.isnan(feats[(8, 0)]["S"])).sum())}
    # every group at minute 8, for context: the crypto change is the whole change, metals and energy stay as they are
    lm, side_yes, top = C.live_rule(d, M=8)
    pnl, cost = C.bet(top[lm], C.won(d, side_yes)[lm])
    out["liveAllGroups"] = {k: {x: (round(v, 3) if isinstance(v, float) else v) for x, v in s.items()}
                            for k, s in C.by_period(pnl, cost, d["open_ts"][lm]).items() if k in ("all", "pre", "post")}
    for name, (train, test) in (("pickPre_testPost", (pre, post)), ("pickPost_testPre", (post, pre))):
        out["splits"][name] = {m: analyse_minute(d, feats, coin, strike, m, train, test, lag_check=(m in (8, 12)))
                               for m in MINUTES}
        print(name, flush=True)
    with open(os.path.join(HERE, "fair_value.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=lambda o: o if not isinstance(o, np.generic) else o.item())
    report(out)


def report(out):
    print("mismatch:", json.dumps(out["mismatch"]["rule"]))
    for c, v in out["mismatch"]["byCoin"].items():
        print(f"  {c:5} gap med {v['gapBpsMedian']:+.1f}bp |gap| med {v['absGapBpsMedian']:.1f} p95 {v['absGapBps95']:.1f}"
              f"  coinbase calls result {v['coinbaseCallsResult']:.3f}  |move| med {v['absMoveBpsMedian']:.1f}bp")
    for name, by_m in out["splits"].items():
        print("\n==", name)
        for m, r in by_m.items():
            cal = r["calibration"]["test"]
            print(f" m{m} model {r['model']['src']}/{r['model']['spec']}/k={r['model']['k']}/nu={r['model']['nu']}  test logloss mid "
                  f"{cal['market mid']['logloss']:.4f} model {cal['model']['logloss']:.4f} both {cal['both']['logloss']:.4f}"
                  f"  (n={cal['markets']})")
            a = r["a_live"]
            b = r["b_filter"]
            c = r["c_modelOnly"]
            fm = lambda s: f"{s['bets']:6d} {s['perBet'] if s['perBet'] is not None else float('nan'):+6.2f}c " \
                           f"[{s['lo'] if s['lo'] is not None else float('nan'):+.1f},{s['hi'] if s['hi'] is not None else float('nan'):+.1f}] ${s['pnl']:.0f}"
            print(f"   a live      train {fm(a['train'])} | test {fm(a['test'])}")
            print(f"   b margin {b['chosenMargin']!s:5} train {fm(b['chosen']['train'])} | test {fm(b['chosen']['test'])}")
            b2 = r["b2_filterBoth"]
            print(f"   b2 margin {b2['chosenMargin']!s:5} train {fm(b2['chosen']['train'])} | test {fm(b2['chosen']['test'])}")
            print(f"   c X={c['chosenX']!s:5}   train {fm(c['chosen']['train'])} | test {fm(c['chosen']['test'])}")
            for e in c["byPrice"]:
                print(f"     c price {e['price']}: train {fm(e['train'])} | test {fm(e['test'])}")
            for k, v in (r.get("staleSpot1min") or {}).items():
                print(f"   stale 1min {k}: train {fm(v['train'])} | test {fm(v['test'])}")
            if m == 8:
                for e in r["edgeBuckets"]:
                    print(f"     gap {e['gap']}: train {fm(e['train'])} | test {fm(e['test'])}")


if __name__ == "__main__":
    main()
