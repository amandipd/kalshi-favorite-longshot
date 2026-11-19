"""Correlated window Kelly at the bot's actual edge (1-1.5 pt), reusing window_kelly.py's copula model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from window_kelly import gauss_rho, loss_count_pmf_gauss, kelly_per_bet, growth, tail

for c in (0.93, 0.95, 0.97):
    for edge in (0.010, 0.015):
        p = c + edge
        q = 1 - p
        f1 = edge / (1 - c)
        rho = gauss_rho(q)
        print(f"\n== c={c} edge={edge*100:.1f}pt  lone Kelly={f1:.3f}  latent rho={rho:.3f}")
        print(" n | Kelly/bet | Kelly total | rule3/20 tot | x Kelly | rule2/20 x | rule1.5 x | g(3/20)/g* | g(2/20)/g* | g(1.5/12)/g* | g(1/..)/g*")
        for n in (1, 2, 3, 5, 8, 10):
            pmf = loss_count_pmf_gauss(n, q, rho)
            fk, gk = kelly_per_bet(n, pmf, c)
            r3 = min(0.03, 0.20 / n)
            r2 = min(0.02, 0.20 / n)
            r15 = min(0.015, 0.12 / n)
            r1 = min(0.01, 0.20 / n)
            out = [growth(x, n, pmf, c) / gk for x in (r3, r2, r15, r1)]
            print(f"{n:2d} | {fk:.4f} | {fk*n:.3f} | {r3*n:.3f} | {r3/fk:.2f} | {r2/fk:.2f} | {r15/fk:.2f} | "
                  + " | ".join(f"{o:.2f}" for o in out))
