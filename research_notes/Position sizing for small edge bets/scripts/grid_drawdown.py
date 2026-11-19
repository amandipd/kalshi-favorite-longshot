"""Tape-fill backtest of drawdown step-down rules (read-only; mirrors local_backtest_grid.py).
Wraps stake_for so the per-bet % shrinks with the drawdown from the running peak."""
import os, sys
from pathlib import Path
R = str(Path(__file__).resolve().parents[3] / "research" / "kalshi_15min")
os.chdir(R); sys.path.insert(0, R)
import strategies_backtest as sb
windows, first, last = sb.load()
hours = int((last + 900 - first) // 3600) + 1
base = next(s for s in sb.MINE if s["id"] == "mine4")
memo = {}
orig = sb.stake_for
state = {"peak": 0.0}


def make(rule):
    def stake_for(strat, bal, n=1):
        state["peak"] = max(state["peak"], bal)
        dd = 1 - bal / state["peak"]
        m = rule(dd)
        s = {**strat, "pct": strat["pct"] * m}
        raw = min(bal * s["pct"], bal * sb.WINDOW_CAP * m / max(n, 1))
        import math
        return min(math.floor(raw * 100 + 1e-6) / 100, strat.get("maxOrder", math.inf))
    return stake_for


def episodes(curve, thresh):
    """Count 24h falls from a high >= thresh (hourly curve), counting a new episode only after 24h clear."""
    c = [x for x in curve if x is not None]
    cnt, last = 0, -10**9
    for i in range(len(c)):
        hi = max(c[max(0, i - 24):i + 1])
        if hi > 0 and 1 - c[i] / hi >= thresh and i - last > 24:
            cnt += 1
            last = i
    return cnt


rules = {
    "flat": lambda dd: 1.0,
    "halve@15": lambda dd: 0.5 if dd >= 0.15 else 1.0,
    "halve@10,quarter@20": lambda dd: 0.25 if dd >= 0.20 else (0.5 if dd >= 0.10 else 1.0),
    "GZ cushion 35%": lambda dd: max(0.0, (0.35 - dd) / 0.35) / (1 - dd) if dd < 0.35 else 0.0,
}
sb.WINDOW_CAP = 0.20
for pct in (0.02, 0.03):
    for name, rule in rules.items():
        state["peak"] = 0.0
        sb.stake_for = make(rule)
        s = {**base, "id": "g", "pct": pct, "liquidity": True}
        r = sb.run(s, windows, 0.004, first, hours, None, memo)
        pre = r["periods"]["pre"]
        print(f"tape {pct:.0%}/20% {name:22s}: final ${r['final']:,.0f} maxDD {r['maxDD']:.0%} worst24h {r['worst24hPct']:+.1%} "
              f"pre {pre['ret']:+.1%} | 24h falls>=7.5%: {episodes(r['curve'], 0.075)}  >=10%: {episodes(r['curve'], 0.10)}  >=15%: {episodes(r['curve'], 0.15)}")
sb.stake_for = orig
