"""Shared helpers for the strategy-lab backtests: lab/markets.npz with the research's own conventions
(strategies_backtest.py): the favourite, Kalshi's taker fee, live-like fills, the live rule's warning signs, the Fed
blackouts, the four periods and a 95% range clustered by window. Vectorised with numpy, so a whole-history run takes
a second and a few tens of MB.

    import common as C
    d = C.load()                                  # crypto, metals and energy; C.load(None) for every group
    m, side_yes, top = C.live_rule(d)             # the live bot's bets at $10 a bet
    pnl, cost = C.bet(top[m], C.won(d, side_yes)[m])
    print(C.summary(pnl, cost, d["open_ts"][m]))  # matches strategies.json's edge["live"]["live"]: 35,793 bets, +4.47c
"""
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE_GROUPS = ("crypto", "metals", "energy")
LO, HI = 0.90, 0.999
SLIP = 0.004   # live-like fills: 0.4c a contract worse than the recorded ask
ET = ZoneInfo("America/New_York")
FED_DAYS = ["2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16"]
FED_WINDOWS = [tuple(datetime.fromisoformat(f"{d}T{hm}").replace(tzinfo=ET).timestamp() for hm in ("14:00", "15:30"))
               for d in FED_DAYS]
_iso = lambda s: datetime.fromisoformat(s + "T00:00:00+00:00").timestamp()
PERIODS = [("pre", "Dec 10 - Jul 17 (untouched)", _iso("2025-12-10"), _iso("2026-07-18")),
           ("before", "Jul 18 - Aug 23 (untouched)", _iso("2026-07-18"), _iso("2026-08-24")),
           ("build", "Aug 24 - Sep 23 (rules built here)", _iso("2026-08-24"), _iso("2026-09-24")),
           ("paper", "Sep 24 - Oct 8", _iso("2026-09-24"), _iso("2026-10-09"))]


def load(groups=EDGE_GROUPS, path=os.path.join(HERE, "markets.npz")):
    """The markets as a dict of arrays, prices as float64 rounded to 4 places (so 0.90 compares as 0.90)."""
    z = np.load(path)
    keep = np.isin(z["group"], groups) if groups else np.ones(len(z["group"]), bool)
    d = {k: z[k][keep] for k in ("ticker", "series", "group", "open_ts", "yes")}
    for k in ("bid", "ask", "last"):
        d[k] = np.round(z[k][keep].astype(np.float64), 4)
    return d


def own(d, side_yes, k):
    """The given side's own (bid, ask) at the end of minute k (1-15), NaN where either quote is missing."""
    if k < 1 or k > 15:
        n = len(side_yes)
        return np.full(n, np.nan), np.full(n, np.nan)
    b, a = d["bid"][:, k - 1], d["ask"][:, k - 1]
    bid = np.where(side_yes, b, np.round(1 - a, 4))
    ask = np.where(side_yes, a, np.round(1 - b, 4))
    bad = np.isnan(a) | np.isnan(b)
    return np.where(bad, np.nan, bid), np.where(bad, np.nan, ask)


def favourite(d, k):
    """(side_yes, top): the favourite at the end of minute k - the side whose ask is higher - and its ask. top is NaN
    where a quote is missing or the two asks tie."""
    b, a = d["bid"][:, k - 1], d["ask"][:, k - 1]
    no = np.round(1 - b, 4)
    side_yes = a > no
    top = np.where(side_yes, a, no)
    top[np.isnan(a) | np.isnan(b) | (np.abs(a - no) < 1e-9)] = np.nan
    return side_yes, top


def won(d, side_yes):
    return (d["yes"] == 1) == side_yes


def spread_sign(d, side_yes, M):
    """The favourite's ask 2c or more over its bid at minute M."""
    bid, ask = own(d, side_yes, M)
    return (ask - bid) >= 0.02 - 1e-9


def late_sign(d, side_yes, M):
    """Its mid 50c or under at M-2 or M-1, or up 10c or more in minute M."""
    mid = lambda k: np.mean(own(d, side_yes, k), axis=0)
    now, before, earlier = mid(M), mid(M - 1), mid(M - 2)
    return ((now - before) >= 0.10) | (before <= 0.5) | (earlier <= 0.5)


def blackout(d):
    t = d["open_ts"]
    return np.any([(t < z) & (t + 900 > a) for a, z in FED_WINDOWS], axis=0)


def live_rule(d, M=8, lo=LO, hi=HI, skip=("spread", "late"), fed=True):
    """(mask, side_yes, top): the markets the live bot's rule bets at minute M, with its price band, warning signs and
    Fed blackouts. Pass skip=() and fed=False for the plain rule."""
    side_yes, top = favourite(d, M)
    m = (top >= lo) & (top <= hi)
    if "spread" in skip:
        m &= ~spread_sign(d, side_yes, M)
    if "late" in skip:
        m &= ~late_sign(d, side_yes, M)
    if fed:
        m &= ~blackout(d)
    return m, side_yes, top


def fee(c, p):
    """Kalshi's taker fee per order, rounded up to the cent."""
    return np.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def bet(top, wins, slip=SLIP, stake=10.0, whole=True, fees=True):
    """(pnl, cost) in $ of a stake-sized taker order at the ask plus slip, held to settlement. whole: whole contracts
    (the live bot), else fractional (the old paper accounts)."""
    price = np.minimum(top + slip, 0.999)
    c = np.floor(stake / price + 1e-9) if whole else stake / price
    cost = c * price
    f = fee(c, price) if fees else 0.0
    pnl = np.where(wins, c, 0.0) - cost - f
    ok = c > 0
    return pnl[ok], cost[ok]


def summary(pnl, cost, window, min_n=30):
    """Bets, cents per $10 staked (total pnl / total staked), the mean per-bet cents and its 95% range clustered by
    window (strategies_backtest.period_stats), and $ pnl at the given stake."""
    n = len(pnl)
    if n == 0:
        return {"bets": 0, "perBet": None, "mu": None, "lo": None, "hi": None, "pnl": 0.0}
    vals = pnl / cost * 1000
    mu = float(vals.mean())
    lo = hi = None
    _, inv = np.unique(window, return_inverse=True)
    g = inv.max() + 1
    if g > 1 and n >= min_n:
        resid = np.bincount(inv, weights=vals) - mu * np.bincount(inv)
        se = math.sqrt((resid ** 2).sum() / (g - 1)) / ((n / g) * math.sqrt(g))
        lo, hi = mu - 1.96 * se, mu + 1.96 * se
    return {"bets": int(n), "perBet": float(pnl.sum() / cost.sum() * 1000), "mu": mu, "lo": lo, "hi": hi,
            "pnl": round(float(pnl.sum()), 2)}


def period_of(ts):
    """Each timestamp's period key ("pre", "before", "build", "paper"), "" outside them."""
    out = np.full(len(ts), "", dtype="U6")
    for k, _, a, b in PERIODS:
        out[(ts >= a) & (ts < b)] = k
    return out


def by_period(pnl, cost, window, extra=(("post", ("before", "build", "paper")),)):
    """summary() over the whole history, each period, and "post" = Jul 18 on."""
    p = period_of(window)
    out = {"all": summary(pnl, cost, window)}
    for k, *_ in PERIODS:
        s = p == k
        out[k] = summary(pnl[s], cost[s], window[s])
    for name, keys in extra:
        s = np.isin(p, keys)
        out[name] = summary(pnl[s], cost[s], window[s])
    return out


def fmt(s):
    if not s or not s["bets"]:
        return "      -"
    rng = f" ({s['lo']:+.1f} to {s['hi']:+.1f})" if s["lo"] is not None else ""
    return f"{s['bets']:6d} bets {s['perBet']:+6.2f}c{rng}"


if __name__ == "__main__":
    d = load()
    m, side_yes, top = live_rule(d)
    pnl, cost = bet(top[m], won(d, side_yes)[m])
    for k, s in by_period(pnl, cost, d["open_ts"][m]).items():
        print(f"live rule  {k:<7} {fmt(s)}")
    m, side_yes, top = live_rule(d, skip=(), fed=False)
    pnl, cost = bet(top[m], won(d, side_yes)[m], whole=False)
    for k, s in by_period(pnl, cost, d["open_ts"][m]).items():
        print(f"plain rule {k:<7} {fmt(s)}")
