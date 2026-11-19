"""Correlated window Kelly if the true edge is the out-of-sample 0.3-0.5 pt at ~96c."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from window_kelly import gauss_rho, loss_count_pmf_gauss, kelly_per_bet, growth

for c in (0.93, 0.96):
    for edge in (0.003, 0.005, 0.012):
        p = c + edge
        q = 1 - p
        rho = gauss_rho(q)
        print(f"\n== c={c} edge={edge*100:.1f}pt lone Kelly={edge/(1-c):.3f}")
        for n in (1, 3, 5, 10):
            pmf = loss_count_pmf_gauss(n, q, rho)
            fk, gk = kelly_per_bet(n, pmf, c)
            r3 = min(0.03, 0.20 / n); r2 = min(0.02, 0.20 / n); r1 = min(0.01, 0.10 / n)
            print(f" n={n:2d} Kelly/bet {fk:.4f} total {fk*n:.3f} | 3%/20% = {r3/fk:.2f}xK g/g*={growth(r3,n,pmf,c)/gk:+.2f} | "
                  f"2%/20% = {r2/fk:.2f}xK g/g*={growth(r2,n,pmf,c)/gk:+.2f} | 1%/10% = {r1/fk:.2f}xK g/g*={growth(r1,n,pmf,c)/gk:+.2f}")
