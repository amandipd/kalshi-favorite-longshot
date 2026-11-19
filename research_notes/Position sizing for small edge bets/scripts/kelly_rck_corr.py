import numpy as np
from math import log
from itertools import product
from scipy.optimize import brentq, minimize_scalar

def kelly(p, q):
    return (q - p) / (1 - p)

print("=== RCK (Busseti-Ryu-Boyd 2016) for binary contract: max f s.t. q*(1+f(1-p)/p)^-lam + (1-q)*(1-f)^-lam <= 1 ===")
print("lam = log(beta)/log(alpha); guarantees Prob(wealth ever < alpha * start) < beta")
cases = [(0.5, 0.10), (0.5, 0.05), (0.7, 0.10), (0.8, 0.10)]
for p in [0.92, 0.95, 0.98]:
    for d in [0.01, 0.015]:
        q = p + d
        fs = kelly(p, q)
        out = []
        for a, b in cases:
            lam = log(b) / log(a)
            h = lambda f: q * (1 + f * (1 - p) / p) ** (-lam) + (1 - q) * (1 - f) ** (-lam) - 1
            if h(fs) <= 0:
                fr = fs
            else:
                fr = brentq(h, 1e-9, fs)
            out.append(f"a={a},b={b}(lam={lam:.2f}): f={fr:.4f} ({fr/fs:.2f}xKelly)")
        print(f"p={p} q={q:.3f} f*={fs:.4f} | " + " | ".join(out))

print()
print("=== Simultaneous bets in one window: 3 contracts each p=0.95, marginal q=0.96 ===")
p = 0.95
b = (1 - p) / p
def growth_equal(f, outcomes):
    # f = stake per contract (fraction of bankroll); outcomes: list of (prob, n_losses)
    g = 0.0
    for pr, nl in outcomes:
        nw = 3 - nl
        w = 1 + f * (nw * b - nl)
        if w <= 0:
            return -1e9
        g += pr * np.log(w)
    return g

def outcomes_common(pi, marg_loss=0.04):
    # with prob pi all three lose together (common shock); else independent losses w.p. l
    l = 1 - (1 - marg_loss) / (1 - pi)
    res = {}
    for combo in product([0, 1], repeat=3):
        pr = (1 - pi) * np.prod([l if c else 1 - l for c in combo])
        nl = sum(combo)
        res[nl] = res.get(nl, 0) + pr
    res[3] = res.get(3, 0) + pi
    return [(v, k) for k, v in res.items()], l

for pi in [0.0, 0.01, 0.02, 0.03, 0.04]:
    outs, l = outcomes_common(pi)
    r = minimize_scalar(lambda f: -growth_equal(f, outs), bounds=(0, 0.33), method="bounded")
    fper = r.x
    print(f"common-shock prob={pi:.2f} (idio loss {l:.4f}): optimal stake per contract={fper:.4f}, total={3*fper:.4f}  (single-bet Kelly={kelly(p,0.96):.4f})")
