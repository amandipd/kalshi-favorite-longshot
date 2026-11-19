"""Tape-fill check: 1.5% with a 12% window cap, and correlation-scaled stakes pct/(1+(n-1)*phi)
(read-only; mirrors local_backtest_grid.py)."""
import os, sys, math
from pathlib import Path
R = str(Path(__file__).resolve().parents[3] / "research" / "kalshi_15min")
os.chdir(R); sys.path.insert(0, R)
import strategies_backtest as sb
windows, first, last = sb.load()
hours = int((last + 900 - first) // 3600) + 1
base = next(s for s in sb.MINE if s["id"] == "mine4")
memo = {}
orig = sb.stake_for


def show(tag, r):
    per = "  ".join(f"{k} {q['ret']:+.1%}" for k, q in r["periods"].items() if q)
    print(f"{tag:28s}: final ${r['final']:,.0f} maxDD {r['maxDD']:.0%} worst24h {r['worst24hPct']:+.1%} "
          f"worst15m {r['worstWindowPct']:+.1%} perBet {r['perBet']:+.1f}c | {per}")


for pct, cap in ((0.015, 0.12), (0.015, 0.10), (0.01, 0.10)):
    sb.WINDOW_CAP = cap
    show(f"tape {pct:.1%}/{cap:.0%}", sb.run({**base, "id": "g", "pct": pct, "liquidity": True}, windows, 0.004, first, hours, None, memo))

PHI = 0.33


def corr_stake(strat, bal, n=1):
    raw = bal * strat["pct"] / (1 + (max(n, 1) - 1) * PHI)
    return min(math.floor(raw * 100 + 1e-6) / 100, strat.get("maxOrder", math.inf))


sb.stake_for = corr_stake
for pct in (0.02, 0.03, 0.04):
    show(f"tape corr-scaled {pct:.0%}/(1+(n-1)0.33)", sb.run({**base, "id": "g", "pct": pct, "liquidity": True}, windows, 0.004, first, hours, None, memo))
sb.stake_for = orig
