"""Tape-fill window-cap check at 2% a bet (read-only; mirrors local_backtest_grid.py)."""
import os, sys
from pathlib import Path
R = str(Path(__file__).resolve().parents[3] / "research" / "kalshi_15min")
os.chdir(R); sys.path.insert(0, R)
import strategies_backtest as sb
windows, first, last = sb.load()
hours = int((last + 900 - first) // 3600) + 1
base = next(s for s in sb.MINE if s["id"] == "mine4")
memo = {}
for pct, cap in ((0.02, 0.12), (0.02, 0.15), (0.015, 0.15), (0.025, 0.15)):
    sb.WINDOW_CAP = cap
    s = {**base, "id": "g", "pct": pct, "liquidity": True}
    r = sb.run(s, windows, 0.004, first, hours, None, memo)
    per = "  ".join(f"{k} {q['ret']:+.1%}" for k, q in r["periods"].items() if q)
    print(f"tape {pct:.1%}/{cap:.0%}: final ${r['final']:,.0f} maxDD {r['maxDD']:.0%} worst24h {r['worst24hPct']:+.1%} "
          f"worst15m {r['worstWindowPct']:+.1%} perBet {r['perBet']:+.1f}c | {per}")
