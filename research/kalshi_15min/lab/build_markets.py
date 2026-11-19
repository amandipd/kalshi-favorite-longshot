"""One compact file of every settled 15-minute market, for the strategy-lab backtests (lab/markets.npz).

Reads the four minute files the way history.py does (the first file a market is in wins) and keeps, per market:
ticker, series, group (from universe.json, "other" if unlisted), open_ts (UTC unix seconds the window opens),
yes (1 if YES won), and YES's bid, ask and last trade at the end of minutes 1..15 as float32 [N, 15]
(column k-1 is minute k, NaN where missing). About 40 MB in memory instead of the CSVs' several hundred.

    python lab/build_markets.py      (from research/kalshi_15min)
"""
import csv
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import history  # noqa: E402


def main():
    groups = history.groups()
    n_max = sum(sum(1 for _ in open(p)) - 1 for p in history.FILES if os.path.exists(p))
    ticker = np.empty(n_max, dtype="U40")
    series = np.empty(n_max, dtype="U16")
    group = np.empty(n_max, dtype="U12")
    open_ts = np.zeros(n_max, dtype=np.int64)
    yes = np.zeros(n_max, dtype=np.int8)
    q = {k: np.full((n_max, 15), np.nan, dtype=np.float32) for k in ("bid", "ask", "last")}
    cols = {"bid": [f"b{k}" for k in range(1, 16)], "ask": [f"a{k}" for k in range(1, 16)],
            "last": [f"p{k}" for k in range(1, 16)]}
    seen, i = set(), 0
    for path in history.FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen:
                    continue
                seen.add(r["ticker"])
                ticker[i], series[i] = r["ticker"], r["series"]
                group[i] = groups.get(r["series"], "other")
                open_ts[i] = int(datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")).timestamp())
                yes[i] = r["resolved_yes"] == "1"
                for k, names in cols.items():
                    q[k][i] = [float(r[c]) if r[c] != "" else np.nan for c in names]
                i += 1
    order = np.argsort(open_ts[:i], kind="stable")
    out = {"ticker": ticker[:i][order], "series": series[:i][order], "group": group[:i][order],
           "open_ts": open_ts[:i][order], "yes": yes[:i][order], **{k: v[:i][order] for k, v in q.items()}}
    np.savez_compressed(os.path.join(HERE, "markets.npz"), **out)
    first, last = (datetime.fromtimestamp(int(out["open_ts"][j]), timezone.utc) for j in (0, -1))
    print(f"{i} markets, {first:%Y-%m-%d} to {last:%Y-%m-%d}")
    for g in np.unique(out["group"]):
        print(f"  {g:<12} {int((out['group'] == g).sum()):7d}")


if __name__ == "__main__":
    main()
