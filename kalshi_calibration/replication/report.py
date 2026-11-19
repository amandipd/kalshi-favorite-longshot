"""`make replicate`: the replication's findings, printed and written to reports/replication.json.

Reads the markets `make replicate-data` fetched (data/replication/) and the settings in config.yaml's
`replication` section; the fee coefficient is the main study's. The findings dashboard reads the
JSON, so the page and this printout come from the same numbers.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kalshi_calibration.config import Config, get_config
from kalshi_calibration.replication.dataset import Market, load_markets
from kalshi_calibration.replication.stats import calibration, favourites, kelly_table, regime, stop_table

REPORT_PATH = Path("reports/replication.json")


def build(markets: list[Market], config: Config) -> dict:
    """Every number the write-up and dashboard quote from the replication."""
    s = config.replication
    coefficient = config.strategy.fee_coefficient
    bets = favourites(markets, s)
    table = calibration(markets, s.entry_minute)
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": s.start.isoformat(), "end": (s.end - timedelta(days=1)).isoformat(),
                   "split": s.split.isoformat()},
        "settings": {"groups": s.groups, "entry_minute": s.entry_minute, "favourite_low": s.favourite_low,
                     "favourite_high": s.favourite_high, "stake": s.stake, "slippage": s.slippage,
                     "fee_coefficient": coefficient},
        "markets": sum(row["n"] for row in table),
        "favourites": len(bets),
        "calibration": table,
        "kelly": kelly_table(bets, s, coefficient),
        "regime": regime(bets, s, coefficient),
        "stops": stop_table(bets, s, coefficient),
    }


def print_report(r: dict) -> None:
    w = r["window"]
    print(f"{r['markets']:,} markets priced at minute {r['settings']['entry_minute']}, {w['start']} to {w['end']}\n")
    print(f"{'band':>9} {'n':>7} {'price':>7} {'won':>7} {'gap':>8} {'95% Wilson interval':>22}")
    for c in r["calibration"]:
        interval = "[{:.4f}, {:.4f}]".format(c["lo"], c["hi"])
        print(f"{c['low']:.1f}-{c['high']:.1f}".rjust(9) + f" {c['n']:>7,} {c['price']:>7.4f} {c['actual']:>7.4f} "
              f"{c['gap']:>+8.4f} {interval:>22}")
    lo, hi = r["settings"]["favourite_low"], r["settings"]["favourite_high"]
    print(f"\nFavourites at {lo * 100:g}-{hi * 100:g}c: {r['favourites']:,}. One-bet Kelly, f* = (q - c) / (1 - c):")
    for k in r["kelly"]:
        print(f"  {k['label']:<28} q {k['win']:.4f}  c {k['cost']:.4f}  f* {k['kelly']:+.2%}")
    print(f"\nProfit per ${r['settings']['stake']:g} bet with live-like fills, either side of {w['split']}:")
    for name, p in r["regime"].items():
        print(f"  {name:<7} {p['bets']:>6,} bets, {p['lost']:.2%} lost, {p['per_bet_cents']:+.1f}c a bet, "
              f"${p['total']:+,.2f} in all")
    print("\nSelling at the first bid at or under each level, against holding to settlement:")
    for row in r["stops"]:
        parts = []
        for name in ("before", "after"):
            x = row[name]
            parts.append(f"{name} ${x['delta']:+,.0f} ({x['sold']:,} sold, {x['sold_won']:,} would have won)")
        print(f"  {row['level'] * 100:>3.0f}c  " + "   ".join(parts))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = get_config()
    report = build(load_markets(config.replication), config)
    print_report(report)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=1, allow_nan=False), encoding="utf-8")
    print(f"\nwrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
