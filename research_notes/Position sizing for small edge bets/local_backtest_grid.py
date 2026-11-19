"""Sizing grid for the live rule (version 4: 92c floor) from $2,000: % a bet x % a window, full fills (live-like) and
fills limited by Kalshi's trade tape. Read-only on the research data; writes nothing to the repo."""
import os, sys, time
from pathlib import Path
R = str(Path(__file__).resolve().parents[2] / "research" / "kalshi_15min")
os.chdir(R); sys.path.insert(0, R)
import strategies_backtest as sb
windows, first, last = sb.load()
hours = int((last + 900 - first) // 3600) + 1
base = next(s for s in sb.MINE if s["id"] == "mine4")
jul18 = sb.ts(sb.PERIODS[1][2])
memo = {}
print(f"{'fills':5} {'bet':>4} {'window':>6} | {'end from $2k (Dec 10)':>22} {'max drop':>8} {'worst 24h':>9} {'worst 15m':>9} | {'Dec10-Jul17':>11} {'Jul18-on':>9}")
for liq in (False, True):
    for pct in (0.01, 0.02, 0.03, 0.04, 0.05):
        for cap in (0.10, 0.15, 0.20, 0.30):
            if cap < pct: continue
            sb.WINDOW_CAP = cap
            s = {**base, "id": "g", "pct": pct, "liquidity": liq}
            r = sb.run(s, windows, 0.004, first, hours, None, memo)
            p = r["periods"]
            pre = p["pre"]["ret"] if p.get("pre") else None
            post_start = p["before"]["start"] if p.get("before") else None
            post = (r["final"] / post_start - 1) if post_start else None
            end = "broke " + r["broke"][:10] if r["broke"] else f"${r['final']:,.0f}"
            print(f"{'tape' if liq else 'full':5} {pct:4.0%} {cap:6.0%} | {end:>22} {r['maxDD']:8.0%} {r['worst24hPct']:+9.1%} {r['worstWindowPct']:+9.1%} | {pre if pre is None else f'{pre:+.0%}':>11} {post if post is None else f'{post:+.0%}':>9}")
