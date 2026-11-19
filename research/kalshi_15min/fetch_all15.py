"""Every 15-minute series on Kalshi, and per-minute history for the ones outside the original 16.

Kalshi's series catalog marks each series' frequency; 31 are "fifteen_min". The original research
used 16 of them (minutes_30d.csv). This writes universe.json (every 15-minute series, its group,
and whether it's live, paused or not launched yet) and fetches every minute 1-15 of every market in
the other series that have ever traded, with the same code as fetch_minutes.py, into
minutes_new.csv (same columns). Coin Race windows hold five markets, one per coin.

    python fetch_all15.py
"""
import csv
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from backtest_large import BASE, get
from fetch_minutes import FIELDS, fetch_window

ORIGINAL = {"KXBTC15M", "KXETH15M", "KXSOL15M", "KXBNB15M", "KXXRP15M", "KXHYPE15M", "KXNEAR15M", "KXDOGE15M",
            "KXZEC15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXCOPPER15M", "KXPALLADIUM15M",
            "KXNATGAS15M", "KXWTI15M"}
OUT_CSV = "minutes_new.csv"
UNIVERSE = "universe.json"


def group_of(ticker, category=""):
    """Markets that move together share a group; the same mapping lives in bot/bot.py and kalshi_calibration/replication/fetch.py."""
    t = ticker.upper()
    if "CRYPTOLEAD" in t or "CRYPTOCOMP" in t:
        return "coin race"
    if any(x in t for x in ("GOLD", "SILVER", "PLATINUM", "PALLADIUM", "COPPER")):
        return "metals"
    if any(x in t for x in ("WTI", "BRENT", "NATGAS", "OIL")):
        return "energy"
    if any(x in t for x in ("EURUSD", "GBPUSD", "USDJPY")):
        return "fx"
    if "RATE" in t:
        return "rates"
    if "INX" in t or "NDQ" in t:
        return "stock index"
    return "crypto" if category == "Crypto" else category.lower() or "other"


def all_markets(series):
    out, cursor = [], None
    while True:
        params = {"series_ticker": series, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get(f"{BASE}/markets", params=params)
        if not d:
            return out
        out += d.get("markets", [])
        cursor = d.get("cursor")
        if not cursor:
            return out


def main():
    catalog = [s for s in get(f"{BASE}/series")["series"]
               if s.get("frequency") == "fifteen_min" and not s["ticker"].endswith("TEST")]
    universe, new_markets = [], []
    for s in sorted(catalog, key=lambda s: s["ticker"]):
        ms = all_markets(s["ticker"])
        live = any(m.get("status") in ("active", "open") for m in ms)
        opens = sorted(m["open_time"] for m in ms)
        universe.append({"ticker": s["ticker"], "title": s.get("title"), "group": group_of(s["ticker"], s.get("category", "")),
                         "status": "live" if live else ("paused" if ms else "not launched"), "markets": len(ms),
                         "first": opens[0] if opens else None, "last": opens[-1] if opens else None,
                         "feeMultiplier": s.get("fee_multiplier"), "inOriginal": s["ticker"] in ORIGINAL})
        if s["ticker"] not in ORIGINAL:
            new_markets += [{"ticker": m["ticker"], "series": s["ticker"], "open_time": m["open_time"],
                             "resolved_yes": "1" if m.get("result") == "yes" else "0"}
                            for m in ms if m.get("result") in ("yes", "no")]
    with open(UNIVERSE, "w", encoding="utf-8") as fh:
        json.dump({"fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "series": universe}, fh, indent=1)
    for u in universe:
        print(f"  {u['ticker']:<18} {u['group']:<12} {u['status']:<13} {u['markets']:>6} markets"
              f"  fee x{u['feeMultiplier']}{'  (original 16)' if u['inOriginal'] else ''}")

    windows = defaultdict(list)
    for m in new_markets:
        windows[m["open_time"]].append(m)
    print(f"\nfetching minutes for {len(new_markets)} settled markets outside the original 16, {len(windows)} windows")
    started = time.time()
    with open(OUT_CSV, "w", newline="") as fh, ThreadPoolExecutor(max_workers=3) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        rows = 0
        for got in pool.map(lambda o: fetch_window(o, windows[o]), sorted(windows)):
            w.writerows(got)
            rows += len(got)
    print(f"wrote {rows} markets to {OUT_CSV} in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
