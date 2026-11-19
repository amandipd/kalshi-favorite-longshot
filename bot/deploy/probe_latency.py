"""How long Kalshi takes to answer from this machine, at each of its two prod addresses.

    python deploy/probe_latency.py          # 20 requests to each address
    python deploy/probe_latency.py -n 50

It sends N sequential GETs of /exchange/status (public: no key, no ledger) to each address on one reused connection
(a requests.Session), GAP s apart to stay well under Kalshi's read rate limit. The first request is the cold one (DNS,
TCP and TLS) and is shown apart; the rest are what a warm request pays: their median, p90 (nearest rank) and max, in ms.
"""
import argparse
import math
import statistics
import time
from collections import Counter
from urllib.parse import urlparse

import requests

HOSTS = ("https://external-api.kalshi.com/trade-api/v2",     # Kalshi's recommended address (load balancer in Ohio)
         "https://api.elections.kalshi.com/trade-api/v2")    # the older one
PATH = "/exchange/status"
TIMEOUT = 10      # seconds
GAP = 0.1         # seconds between requests: 10 a second


def probe(base, n, session, clock=time.perf_counter, sleep=time.sleep, gap=GAP):
    """n GETs in a row on one session: (ms, HTTP status) for each, or (None, the error's kind) for one that failed."""
    out = []
    for i in range(n):
        if i:
            sleep(gap)
        start = clock()
        try:
            status = session.get(base + PATH, timeout=TIMEOUT).status_code
        except requests.RequestException as e:
            out.append((None, type(e).__name__))
            continue
        out.append(((clock() - start) * 1000, status))
    return out


def nearest_rank(xs, q):
    """The q-quantile by nearest rank: the smallest value with at least q of them at or below it."""
    s = sorted(xs)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def summary(base, results):
    """One line: the cold request, then the warm ones' median, p90 and max, then anything that wasn't a 200."""
    cold = results[0][0]
    warm = [ms for ms, _ in results[1:] if ms is not None]
    line = f"{urlparse(base).hostname:<26} cold {'failed' if cold is None else f'{cold:.1f} ms'}"
    if warm:
        line += (f" · warm ({len(warm)}): median {statistics.median(warm):.1f}, p90 {nearest_rank(warm, 0.9):.1f},"
                 f" max {max(warm):.1f} ms")
    else:
        line += " · no warm answers"
    bad = Counter(str(st) for _, st in results if st != 200)
    if bad:
        line += " · not 200: " + ", ".join(f"{k} x{v}" for k, v in bad.items())
    return line


def main(argv=None, session=requests.Session, clock=time.perf_counter, sleep=time.sleep):
    a = argparse.ArgumentParser(description="Time Kalshi's public /exchange/status at each prod address.")
    a.add_argument("-n", type=int, default=20, help="requests to each address (default 20)")
    args = a.parse_args(argv)
    if args.n < 1:
        a.error("-n must be at least 1")
    print(f"{args.n} GETs of {PATH} to each address, one reused connection each, {GAP:.1f} s apart")
    for base in HOSTS:
        with session() as s:
            print(summary(base, probe(base, args.n, s, clock, sleep)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
