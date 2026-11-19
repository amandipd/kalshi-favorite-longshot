"""Do Polymarket US 5-minute markets settle on the same numbers as Kalshi's 15-minute markets?

At every 15-minute mark T, Kalshi's 15-minute market closing at T has a final value (the 60-second index average
before T), and the Polymarket 5-minute window ending at T has its own close value, which by its rules is the same
average. Likewise the Polymarket window opening at T - 900 has an open value equal to Kalshi's strike for that market.
Reads markets.jsonl; Kalshi's results come from its public API (research/settle_average/last_minute.py helpers).
Writes settle.json.

    python settle.py
"""
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "settle_average"))
import last_minute as L  # noqa: E402

SERIES = {"btc": "KXBTC15M", "eth": "KXETH15M", "sol": "KXSOL15M", "xrp": "KXXRP15M"}


def close_enough(a, b):
    """Equal to within half a unit of the coarser of the two values' rounding: 2 decimals for BTC, ETH and SOL; for
    XRP Polymarket keeps 5 decimals and Kalshi 4, so half of 0.0001."""
    return abs(a - b) <= (0.005 if abs(a) > 50 else 0.00005) + 1e-9


def main():
    pm = {}
    with open(os.path.join(HERE, "markets.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            if not r.get("missing") and r.get("yes") is not None:
                pm[(r["coin"], r["start"])] = r
    lo = min(t for _, t in pm) + 300
    hi = max(t for _, t in pm) + 300
    cutoff = L.ts(L.get("/historical/cutoff")["market_settled_ts"])
    out = {}
    for coin, series in SERIES.items():
        ks = L.markets_between([series], lo, hi, cutoff)
        tally = defaultdict(int)
        diffs = []
        for k in ks:
            T = k["c"]
            ending, opening = pm.get((coin, T - 300)), pm.get((coin, T - 900))
            if ending and ending.get("close") is not None and not math.isnan(k["v"]):
                tally["close_pairs"] += 1
                same = close_enough(ending["close"], k["v"])
                tally["close_same"] += same
                diffs.append(abs(ending["close"] - k["v"]) / k["v"])
                if not same and len(tally) < 40:
                    tally[f"diff {T} pm {ending['close']} kalshi {k['v']}"] = 1
            if opening and opening.get("open") is not None and not math.isnan(k["k"]):
                tally["open_pairs"] += 1
                tally["open_same"] += close_enough(opening["open"], k["k"])
        diffs.sort()
        tally["median_rel_diff"] = diffs[len(diffs) // 2] if diffs else None
        tally["kalshi_markets"] = len(ks)
        out[coin] = dict(tally)
        print(coin, dict(tally), flush=True)
    with open(os.path.join(HERE, "settle.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
