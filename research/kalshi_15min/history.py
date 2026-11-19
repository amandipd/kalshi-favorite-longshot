"""Every 15-minute market Kalshi has settled, from the first ones (Dec 10, 2025) to the last full day fetched.

The four minute files together hold every market, each once: minutes_30d.csv (Aug 24 - Sep 23),
minutes_new.csv (the series that launched later), minutes_ext.csv (everything else from Jul 18, kept up to
date by fetch_history.py) and minutes_pre.csv (the crypto markets before Jul 18, from fetch_pre.py). The
backtests read their markets through here, so each one covers all the data there is rather than one
stretch of it.

The history used to begin on Jul 18 because the first three files were listed from Kalshi's live endpoint,
whose live/historical cutoff sat there when they were built. BTC and ETH have run since Dec 10, 2025, SOL
since Jan 9, XRP since Feb 11, BNB since Mar 7, DOGE and HYPE since Mar 18, NEAR and ZEC since Jun 30;
metals and energy began on Jul 31.

Run it to write snapshots_all.csv, the minute-8 view of every market in the groups the strategy bets
(crypto, metals, energy): the same columns the older scripts read from snapshots_8min.csv,
snapshots_30d.csv and quotes_30d.csv, for the whole history.

    python fetch_history.py     (brings the minute files up to the last full day)
    python history.py           (then this)
"""
import csv
import json
import os
from datetime import datetime, timedelta

# The first file a market is in wins; fetch_pre.py skips any market already in the other three.
FILES = ("minutes_30d.csv", "minutes_new.csv", "minutes_ext.csv", "minutes_pre.csv")
FIRST = "2025-12-10T00:00:00Z"                 # the day of the first 15-minute markets (BTC and ETH)
JUL18 = "2026-07-18T00:00:00Z"                 # where the first three files begin; minutes_pre.csv holds what came before
EDGE_GROUPS = ("crypto", "metals", "energy")   # the groups the strategy bets in
SNAPSHOTS = "snapshots_all.csv"


def groups():
    """{series: group} from Kalshi's catalog (fetch_all15.py)."""
    with open("universe.json", encoding="utf-8") as fh:
        return {u["ticker"]: u["group"] for u in json.load(fh)["series"]}


def each(only=EDGE_GROUPS):
    """Every settled market once, as the minute files' rows, in the given groups (None: every group)."""
    g, seen = groups(), set()
    for path in FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen or (only and g.get(r["series"]) not in only):
                    continue
                seen.add(r["ticker"])
                yield r


def end():
    """Midnight (UTC) after the last day in the data, as ISO text: where every backtest ends."""
    last = max(r["open_time"] for r in each(None))
    return (datetime.fromisoformat(last[:10]) + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")


def strategy(doc):
    """Print the "Strategy:" paragraph of a script's docstring, so every run says what exactly it tests."""
    para = next((p for p in doc.split("\n\n") if p.lstrip().startswith("Strategy:")), None)
    if para:
        print(" ".join(para.split()), end="\n\n", flush=True)


def write_snapshots():
    """snapshots_all.csv: each market's last trade, bid and ask at minute 8 (and last trade at minute 7) with its result."""
    n, first, last = 0, None, None
    with open(SNAPSHOTS, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "ticker", "open_time", "price_8min", "yes_bid", "yes_ask", "price_7", "resolved_yes"])
        for r in sorted(each(), key=lambda r: (r["open_time"], r["series"])):
            if r["p8"] == "":   # no trade by minute 8: the snapshot studies price each market by its last trade
                continue
            w.writerow([r["series"], r["ticker"], r["open_time"], r["p8"], r["b8"], r["a8"], r["p7"], r["resolved_yes"]])
            n += 1
            first, last = first or r["open_time"], r["open_time"]
    print(f"{SNAPSHOTS}: {n} markets in {', '.join(EDGE_GROUPS)}, {first[:10]} to {last[:10]}")


if __name__ == "__main__":
    write_snapshots()
