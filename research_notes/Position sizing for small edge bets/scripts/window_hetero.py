"""Heterogeneous-edge window: 10 contracts at 93c, true win prob 0.935..0.96.
One-factor Gaussian copula, latent rho ~0.66 (P(lose|other lost) ~0.36 at q=5%).
Exact enumeration of 2^10 loss patterns per factor node.
Compare: correlated Kelly, independent Kelly, equal 2% (20%/n), and the
growth-optimal allocation subject to each<=3%, sum<=20%.
"""
import itertools
import numpy as np
from scipy import stats, optimize

c = 0.93
p = np.array([0.960, 0.958, 0.955, 0.953, 0.950, 0.948, 0.945, 0.943, 0.940, 0.935])
n = len(p)
q = 1 - p
b = (1 - c) / c
rho = 0.663

pats = np.array(list(itertools.product([0, 1], repeat=n)))  # 1 = lost
R = np.where(pats == 1, -1.0, b)  # return per $ for each pattern, each bet
z, w = np.polynomial.hermite_e.hermegauss(120)
w = w / w.sum()
t = stats.norm.ppf(q)
prob = np.zeros(len(pats))
for zi, wi in zip(z, w):
    qz = stats.norm.cdf((t - np.sqrt(rho) * zi) / np.sqrt(1 - rho))
    pp = np.prod(np.where(pats == 1, qz, 1 - qz), axis=1)
    prob += wi * pp
prob /= prob.sum()

# independent joint for comparison
prob_ind = np.prod(np.where(pats == 1, q, 1 - q), axis=1)


def g(f, pr):
    W = 1 + R @ f
    if np.any(W <= 0):
        return -1e9
    return float(pr @ np.log(W))


def grad(f, pr):
    W = 1 + R @ f
    return (pr / W) @ R


def solve(pr, ub, total):
    cons = [{"type": "ineq", "fun": lambda f: total - f.sum(), "jac": lambda f: -np.ones(n)}]
    res = optimize.minimize(lambda f: -g(f, pr), x0=np.full(n, min(ub, total / n) * 0.5),
                            jac=lambda f: -grad(f, pr), bounds=[(0, ub)] * n, constraints=cons,
                            method="SLSQP", options={"ftol": 1e-12, "maxiter": 500})
    return res.x


single = (p - c) / (1 - c)
fk_corr = solve(prob, 1.0, 0.999)
fk_ind = solve(prob_ind, 1.0, 0.999)
f_cap = solve(prob, 0.03, 0.20)
f_eq = np.full(n, 0.02)
f_half = fk_corr / 2

np.set_printoptions(precision=4, suppress=True)
print("edge (c):          ", (p - c) * 100)
print("single-bet Kelly:  ", single)
print("indep joint Kelly: ", fk_ind, " total", fk_ind.sum().round(3))
print("corr joint Kelly:  ", fk_corr, " total", fk_corr.sum().round(3))
print("cap-opt (3%/20%):  ", f_cap, " total", f_cap.sum().round(3))
for name, f in [("corr Kelly", fk_corr), ("half corr Kelly", f_half), ("equal 2% (20%/n)", f_eq),
                ("cap-optimal", f_cap), ("3% each (30%)", np.full(n, 0.03)),
                ("Kelly-proportional scaled to 20%", single / single.sum() * 0.20)]:
    W = 1 + R @ f
    print(f"{name:34s} growth/window={g(f, prob)*1e4:7.2f}e-4  total={f.sum():.3f}  "
          f"P(window loss>=10%)={prob[W <= 0.90].sum():.4f}  P(>=15%)={prob[W <= 0.85].sum():.4f}  worst={W.min()-1:.3f}")
