"""Per-period breakdown of the tape-fill sizing grid (read-only; mirrors local_backtest_grid.py)."""
import os, sys
from collections import Counter
from pathlib import Path
R = str(Path(__file__).resolve().parents[3] / "research" / "kalshi_15min")
os.chdir(R); sys.path.insert(0, R)
import strategies_backtest as sb
windows, first, last = sb.load()
hours = int((last + 900 - first) // 3600) + 1
base = next(s for s in sb.MINE if s["id"] == "mine4")
memo = {}
print("PERIODS:", [(k, lab) for k, lab, a, b in sb.PERIODS])
for liq in (True, False):
    for pct, cap in ((0.01, 0.20), (0.015, 0.20), (0.02, 0.20), (0.03, 0.20), (0.02, 0.10), (0.015, 0.10)):
        sb.WINDOW_CAP = cap
        s = {**base, "id": "g", "pct": pct, "liquidity": liq}
        r = sb.run(s, windows, 0.004, first, hours, None, memo)
        tag = "tape" if liq else "full"
        L = r.get("liquidity")
        fillshare = (L["got"] / L["asked"]) if L and L["asked"] else None
        print(f"\n{tag} {pct:.1%}/{cap:.0%}: final ${r['final']:,.0f} maxDD {r['maxDD']:.0%} worst24h {r['worst24hPct']:+.1%} "
              f"bets {r['bets']} perBet(c/$10) {r['perBet']:+.1f} fillshare {fillshare if fillshare is None else f'{fillshare:.0%}'}")
        for k, q in r["periods"].items():
            if not q:
                continue
            lo = f"{q['lo']:+.1f}" if q['lo'] is not None else "-"
            hi = f"{q['hi']:+.1f}" if q['hi'] is not None else "-"
            print(f"   {k:7s} bets {q['bets']:5d} ret {q['ret']:+7.1%} maxDD {q['maxDD']:4.0%} per$10 {q['mu']:+6.1f}c [{lo},{hi}]")
# cluster sizes: bets chosen per window (before sizing), for windows with >=1 bet
sizes = Counter(len(v[0]) for v in memo.values() if v[0])
tot = sum(k * v for k, v in sizes.items())
nw = sum(sizes.values())
print("\nwindows with bets:", nw, "bets:", tot, "mean per active window:", round(tot / nw, 2))
print("cluster size distribution:", sorted(sizes.items()))
# design effect with phi=0.33: sum n_i(1+(n_i-1)phi)/sum n_i
for phi in (0.2, 0.33):
    de = sum(v * k * (1 + (k - 1) * phi) for k, v in sizes.items()) / tot
    print(f"design effect at phi={phi}: {de:.2f}")
