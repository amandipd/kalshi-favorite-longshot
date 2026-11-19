import numpy as np
from math import log
from scipy.optimize import brentq

def G(f, p, q):
    """Expected log growth per bet: stake fraction f of bankroll on a contract
    bought at price p (pays 1), true win prob q."""
    return q * np.log1p(f * (1 - p) / p) + (1 - q) * np.log1p(-f)

def kelly(p, q):
    return (q - p) / (1 - p)

print("=== 1. Kelly fraction, growth, overbet zero point ===")
print("p      q      f*     G*/bet      G(1/2)/G*  G(1/4)/G*  zero-growth f / f*   loss-ratio")
for p in [0.92, 0.95, 0.98, 0.99]:
    for d in [0.01, 0.015]:
        q = p + d
        if q >= 1:
            continue
        fs = kelly(p, q)
        g = G(fs, p, q)
        r2 = G(fs / 2, p, q) / g
        r4 = G(fs / 4, p, q) / g
        if fs < 1:
            hi = 1 - 1e-12
            if G(hi, p, q) < 0:
                f0 = brentq(lambda f: G(f, p, q), fs * 1.0001, hi)
                z = f0 / fs
            else:
                z = float('nan')
        else:
            z = float('nan')
        print(f"{p:.3f}  {q:.3f}  {fs:.4f}  {g:.3e}  {r2:.3f}      {r4:.3f}      {z:.3f}    {(1-q)/(1-p):.3f}")

print()
print("=== 2. Sensitivity: df*/dq = 1/(1-p) ===")
for p in [0.92, 0.95, 0.98, 0.99, 0.995, 0.999]:
    print(f"p={p}: 1pp error in q moves f* by {0.01/(1-p)*100:.1f} pp of bankroll")

print()
print("=== 3. Misestimated edge: sized for q_est = p+0.01, truth differs ===")
print("p     true q    c(frac of est. Kelly)  stake   G/bet (true)   G*/bet if truth known")
for p in [0.92, 0.95, 0.98]:
    fe = kelly(p, p + 0.01)
    for dq in [0.01, 0.005, 0.0, -0.005]:
        qt = p + dq
        for c in [1.0, 0.5, 0.25]:
            f = c * fe
            gt = G(f, p, qt)
            gstar = G(kelly(p, qt), p, qt) if qt > p else 0.0
            print(f"{p:.2f}  {qt:.3f}    {c:.2f}                  {f:.4f}  {gt:+.3e}     {gstar:.3e}")
    print()

print("=== 4. Monte Carlo drawdowns (true q = p+0.01) ===")
rng = np.random.default_rng(12345)
def mc(p, q, f, nbets, npaths=20000, chunk=2000):
    up = log(1 + f * (1 - p) / p)
    dn = log(1 - f)
    hit_init = 0
    hit_peak = 0
    finals = []
    for s in range(0, npaths, chunk):
        m = min(chunk, npaths - s)
        wins = rng.random((m, nbets)) < q
        inc = np.where(wins, up, dn)
        lw = np.cumsum(inc, axis=1)
        lw0 = np.concatenate([np.zeros((m, 1)), lw], axis=1)
        hit_init += np.sum(lw0.min(axis=1) <= log(0.5))
        peak = np.maximum.accumulate(lw0, axis=1)
        dd = (lw0 - peak).min(axis=1)
        hit_peak += np.sum(dd <= log(0.5))
        finals.append(lw[:, -1])
    finals = np.concatenate(finals)
    return hit_init / npaths, hit_peak / npaths, np.exp(np.median(finals)), np.mean(finals <= 0)

for nb in [1000, 5000]:
    print(f"-- {nb} bets --")
    print("p     c     stake   P(ever <=50% of start)  Thorp x^(2/c-1)  P(50% peak-to-trough DD)  median final W  P(final<=start)")
    for p in [0.92, 0.95, 0.98]:
        q = p + 0.01
        fs = kelly(p, q)
        for c in [1.0, 0.5, 0.25]:
            a, b, med, pl = mc(p, q, c * fs, nb)
            th = 0.5 ** (2 / c - 1)
            print(f"{p:.2f}  {c:.2f}  {c*fs:.4f}  {a:.4f}                  {th:.4f}           {b:.4f}                    {med:.3g}          {pl:.4f}")

print()
print("=== 5. Sample size needed to estimate a 1pp edge ===")
for p in [0.92, 0.95, 0.98]:
    q = p + 0.01
    var = q * (1 - q)
    for N in [500, 1000, 2000, 5000]:
        se = (var / N) ** 0.5
        print(f"p={p} q={q:.2f} N={N}: SE of win rate = {se*100:.2f}pp; edge/SE = {0.01/se:.2f}; edge^2/(edge^2+SE^2) = {0.0001/(0.0001+se*se):.2f}")
    print(f"   N for edge = 2 SE: {4*var/0.0001:.0f}; for 3 SE: {9*var/0.0001:.0f}")

print()
print("=== 6. Baker-McHale-style frequentist shrinkage: plug-in Kelly from N-bet win-rate sample ===")
print("Truth q=p+0.01. Estimate q_hat = wins/N. Bet k*max(0,(q_hat-p)/(1-p)) capped at 0.99. Find k maximising E[G_true].")
ks = np.linspace(0.02, 1.5, 149)
for p in [0.92, 0.95, 0.98]:
    q = p + 0.01
    for N in [500, 1000, 2000, 5000, 20000]:
        wins = rng.binomial(N, q, size=200000)
        qh = wins / N
        fh = np.clip((qh - p) / (1 - p), 0, 0.99)
        best = None
        for k in ks:
            f = np.clip(k * fh, 0, 0.99)
            eg = np.mean(G(f, p, q))
            if best is None or eg > best[1]:
                best = (k, eg)
        eg_full = np.mean(G(np.clip(fh, 0, 0.99), p, q))
        eg_half = np.mean(G(np.clip(0.5 * fh, 0, 0.99), p, q))
        gstar = G(kelly(p, q), p, q)
        print(f"p={p} N={N:6d}: best k={best[0]:.2f}  E[G] at best={best[1]/gstar:+.2f} G*  full plug-in={eg_full/gstar:+.2f} G*  half={eg_half/gstar:+.2f} G*")
