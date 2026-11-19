"""Which of the 15-minute series the bot skips have ever settled a market.

The bot trades crypto, metals and energy (bot.py's EDGE_GROUPS); Kalshi lists 35 fifteen-minute series.
This writes skipped_scan.json: every other series, its group, how many markets it has listed and settled,
and the span they cover, so fetch_skipped.py knows what history there is to pull.

    python scan_skipped.py
"""
import json
import time

from backtest_large import BASE, get
from fetch_all15 import group_of

EDGE_GROUPS = ("crypto", "metals", "energy")
OUT = "skipped_scan.json"


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
    skipped = [s for s in catalog if group_of(s["ticker"], s.get("category") or "") not in EDGE_GROUPS]
    print(f"{len(catalog)} fifteen-minute series, {len(skipped)} outside the groups the bot trades\n")
    out = []
    for s in sorted(skipped, key=lambda s: s["ticker"]):
        ms = all_markets(s["ticker"])
        settled = [m for m in ms if m.get("result") in ("yes", "no")]
        opens = sorted(m["open_time"] for m in settled)
        out.append({"ticker": s["ticker"], "title": s.get("title"),
                    "group": group_of(s["ticker"], s.get("category") or ""), "category": s.get("category"),
                    "markets": len(ms), "settled": len(settled), "fee": s.get("fee_multiplier"),
                    "first": opens[0] if opens else None, "last": opens[-1] if opens else None})
        r = out[-1]
        print(f"  {r['ticker']:<18}{r['group']:<12}{r['markets']:>7} listed{r['settled']:>8} settled"
              f"   {str(r['first'])[:16]} -> {str(r['last'])[:16]}")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "series": out}, fh, indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
