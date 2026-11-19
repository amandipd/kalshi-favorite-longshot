"""Illustrative multi-bet Kelly for n exchangeable correlated binary contracts.

Each contract: buy at price c, pays 1 if it wins (prob p), 0 otherwise.
Per $ staked: win -> +b = (1-c)/c, lose -> -1.
Correlation pinned by P(B loses | A loses) = cond (0.36).
Two dependence models with the same marginals and same pairwise stats:
  - Gaussian copula (one-factor latent threshold)
  - Beta-binomial (loss prob Q ~ Beta), heavier joint-loss tail
"""
import numpy as np
from scipy import stats, optimize, integrate
from scipy.special import comb, betaln

COND = 0.36


def gauss_rho(q, cond=COND):
    t = stats.norm.ppf(q)
    def f(r):
        p2 = stats.multivariate_normal.cdf([t, t], mean=[0, 0], cov=[[1, r], [r, 1]])
        return p2 / q - cond
    return optimize.brentq(f, 1e-6, 0.999)


def loss_count_pmf_gauss(n, q, rho, nodes=200):
    t = stats.norm.ppf(q)
    z, w = np.polynomial.hermite_e.hermegauss(nodes)
    w = w / w.sum()
    qz = stats.norm.cdf((t - np.sqrt(rho) * z) / np.sqrt(1 - rho))
    k = np.arange(n + 1)
    pmf = np.zeros(n + 1)
    for qi, wi in zip(qz, w):
        pmf += wi * comb(n, k) * qi**k * (1 - qi) ** (n - k)
    return pmf / pmf.sum()


def loss_count_pmf_beta(n, q, cond=COND):
    s = (1 - cond) / (cond - q)
    a, b = q * s, (1 - q) * s
    k = np.arange(n + 1)
    logp = np.log(comb(n, k)) + betaln(k + a, n - k + b) - betaln(a, b)
    pmf = np.exp(logp)
    return pmf / pmf.sum()


def loss_count_pmf_indep(n, q):
    k = np.arange(n + 1)
    return comb(n, k) * q**k * (1 - q) ** (n - k)


def growth(f, n, pmf, c):
    """E log wealth after one window, equal stake f on each of n contracts."""
    b = (1 - c) / c
    k = np.arange(n + 1)
    w = 1 + f * ((n - k) * b - k)
    if np.any(w <= 0):
        return -np.inf
    return float(np.sum(pmf * np.log(w)))


def kelly_per_bet(n, pmf, c):
    hi = 1.0 / n - 1e-9
    res = optimize.minimize_scalar(lambda f: -growth(f, n, pmf, c), bounds=(0, hi), method="bounded",
                                   options={"xatol": 1e-7})
    return res.x, -res.fun


def tail(f, n, pmf, c, thresh):
    b = (1 - c) / c
    k = np.arange(n + 1)
    ret = f * ((n - k) * b - k)
    return float(pmf[ret <= -thresh].sum())


def main():
    c = 0.93
    for p in (0.95, 0.96):
        q = 1 - p
        f1 = (p - c) / (1 - c)
        rho = gauss_rho(q)
        phi = (COND * q - q * q) / (q * (1 - q))
        print(f"\n=== price c={c}, true win p={p}  (edge {p-c:.3f}/contract, single-bet Kelly f1={f1:.3f}) ===")
        print(f"latent Gaussian rho for P(lose|other lost)={COND}: {rho:.3f}; binary (phi) corr: {phi:.3f}")
        print("n | model | Kelly/bet | Kelly total | g*(1e-4/window) | g@3%/bet | g@min(3%,20%/n) | g@20%/n | P(lose>=10%) @min(3%,20%/n) | @Kelly | @half Kelly")
        for n in (1, 2, 3, 5, 8, 10):
            meff = n / (1 + (n - 1) * phi)
            for name, pmf in (("indep", loss_count_pmf_indep(n, q)),
                              ("gauss", loss_count_pmf_gauss(n, q, rho)),
                              ("beta", loss_count_pmf_beta(n, q))):
                fk, gk = kelly_per_bet(n, pmf, c)
                g3 = growth(0.03, n, pmf, c)
                fcap = min(0.03, 0.20 / n)
                gcap = growth(fcap, n, pmf, c)
                g20 = growth(0.20 / n, n, pmf, c)
                print(f"{n:2d} | {name:5s} | {fk:.4f} | {fk*n:.3f} | {gk*1e4:8.1f} | {g3*1e4:7.1f} | {gcap*1e4:7.1f} | {g20*1e4:7.1f} | "
                      f"{tail(fcap,n,pmf,c,0.10):.2e} | {tail(fk,n,pmf,c,0.10):.2e} | {tail(fk/2,n,pmf,c,0.10):.2e}  (m_eff={meff:.2f})")
        # loss-count distribution for n=10
        n = 10
        print("P(k losses of 10):")
        for name, pmf in (("indep", loss_count_pmf_indep(n, q)), ("gauss", loss_count_pmf_gauss(n, q, rho)), ("beta", loss_count_pmf_beta(n, q))):
            print(f"  {name:5s}", " ".join(f"{x:.2e}" for x in pmf[:6]), " P(>=5)=", f"{pmf[5:].sum():.2e}")


if __name__ == "__main__":
    main()
