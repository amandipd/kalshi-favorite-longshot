"""The replication's key numbers in one file, key_stats.json, for the bot dashboard's Research tab (bot/dashboard.py).

Calibration: every market at minute 8 (snapshots_all.csv) in 10c bands, the same table analyze.py prints.
Kelly: the one-bet Kelly fraction for minute-8 favourites at 90-99.9c, f* = (q - c) / (1 - c), under each of
sizing.py's fill scenarios. sizing.py prints it but does not save it.
Regime, stops and selling under 90c: copied from findings.json and strategies.json, so run findings.py and
strategies_backtest.py first.
Real fills: the live bot's rule with every order filled in full, against the same rule filled only as far as Kalshi's
trade tape says the book had (strategies.json's "live" and "liveliq" accounts, liquidity.py), from each start.
Book depth: how much traded at the live bot's price in the seconds after each of its orders (liquidity.json), per
market group and per market, to say how much size the book takes now that the bot has no order cap.

    python key_stats.py
"""
import json
from datetime import datetime, timezone

import analyze
import sizing

OUT = "key_stats.json"
DEPTH_DOLLARS = (10, 25, 50, 100)   # order sizes the book is tested against
DEPTH_PRICE = 0.95                  # dollars a contract, the middle of the 90-99.9c band: turns contracts into dollars


def kelly_table(days):
    """q, all-in cost and f* per scenario: as recorded, +0.4c fills, and +0.4c with a 2x crypto fee."""
    out = []
    for name, (slip, mult) in sizing.SCENARIOS.items():
        q, cost, k = sizing.kelly_single(days, slip, mult)
        out.append({"scenario": name, "slip": slip, "feeMult": mult, "win": q, "cost": cost, "kelly": k})
    return out


def exit_rules(strategies, start="aug24"):
    """Each sell-under-90c strategy against the same strategy held to settlement, from `start`."""
    runs = strategies["starts"][start]["backtest"]
    names = {s["id"]: s["name"] for s in strategies["strategies"]}
    out = []
    for s in strategies["strategies"]:
        if not s.get("base"):
            continue
        sold, held = runs[s["id"]], runs[s["base"]]
        out.append({"name": s["name"], "base": names[s["base"]], "start": sold["start"],
                    "final": sold["final"], "broke": sold["broke"],
                    "baseFinal": held["final"], "baseBroke": held["broke"], "exit": sold["exit"]})
    return out


def real_fills(strategies):
    """Per start: how much of the live bot's orders the book had, and what filling only that did to its profit a bet, its
    end and its one-bet Kelly fraction, against the same rule filled in full. Both at the recorded ask ("backtest"
    fills), so how much fills is the only difference. None if the backtest has no real-liquidity account."""
    def side(r):
        kelly = (r["winRate"] - r["need"]) / (1 - r["need"]) if r["bets"] else None
        return {**{k: r[k] for k in ("start", "final", "broke", "bets", "winRate", "need", "perBet", "maxDD")}, "kelly": kelly}
    out = {}
    for start, by_fills in (strategies.get("starts") or {}).items():
        runs = by_fills.get("backtest") or {}
        full, real = runs.get("live"), runs.get("liveliq")
        if full and real and real.get("liquidity"):
            out[start] = {**real["liquidity"], "full": side(full), "real": side(real)}
    return out or None


def book_depth(liquidity, groups):
    """How much size the book took at the live bot's price: for each of its orders, the contracts other traders bought
    at the minute-8 ask or better in the `depth` seconds after it would have gone in (liquidity.json's `seen`). For
    every order, each market group and each market: the orders, the median in dollars, the share where nothing traded,
    and the share where at least each of DEPTH_DOLLARS did (contracts at DEPTH_PRICE). Markets deepest first, by the
    share with $50 or more. None without liquidity.json or with no markets in it."""
    if not liquidity or not liquidity.get("markets"):
        return None

    def stats(vals):
        vals, n = sorted(vals), len(vals)
        return {"orders": n, "median": vals[n // 2] * DEPTH_PRICE, "none": sum(v == 0 for v in vals) / n,
                "atLeast": {str(d): sum(v * DEPTH_PRICE >= d for v in vals) / n for d in DEPTH_DOLLARS}}
    by_group, by_series = {}, {}
    for ticker, (_, _, seen) in liquidity["markets"].items():
        series = ticker.split("-")[0]
        by_group.setdefault(groups.get(series, "other"), []).append(seen)
        by_series.setdefault(series, []).append(seen)
    return {"depth": liquidity.get("depth"), "price": DEPTH_PRICE, "dollars": list(DEPTH_DOLLARS),
            "all": stats([v for vals in by_series.values() for v in vals]),
            "groups": {g: stats(v) for g, v in sorted(by_group.items())},
            "markets": sorted(({"series": s, "group": groups.get(s, "other"), **stats(v)} for s, v in by_series.items()),
                              key=lambda m: (-m["atLeast"]["50"], m["series"]))}


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def main():
    rows = analyze.load_rows()
    with open("findings.json", encoding="utf-8") as fh:
        findings = json.load(fh)
    with open("strategies.json", encoding="utf-8") as fh:
        strategies = json.load(fh)
    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "markets": len(rows),
        "from": findings["from"], "split": findings["split"], "to": findings["to"],
        "calibration": analyze.calibration(rows),
        "kelly": kelly_table(sizing.days_of_windows()),
        "regime": findings["periods"],
        "stops": findings["exits"]["stops"],
        "forwardBets": findings["forwardBets"],
        "exits": exit_rules(strategies),
        "realFills": real_fills(strategies),
        "bookDepth": book_depth(read_json("liquidity.json"),
                                {u["ticker"]: u["group"] for u in (read_json("universe.json") or {}).get("series", [])}),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    k = {r["scenario"]: r["kelly"] for r in out["kelly"]}
    print(f"{OUT}: {out['markets']:,} markets; one-bet Kelly {k['backtest']:+.1%} as recorded, "
          f"{k['realistic']:+.1%} with live-like fills, {k['stress']:+.1%} under stress")
    for start, q in (out["realFills"] or {}).items():
        if q["asked"] and q["full"]["bets"] and q["real"]["bets"]:
            print(f"  real fills from {start}: {q['got'] / q['asked']:.0%} of contracts, {q['missed']:,} of {q['orders']:,} orders"
                  f" got nothing; per $10 {q['full']['perBet']:+.1f}c in full, {q['real']['perBet']:+.1f}c real")
    if out["bookDepth"]:
        a = out["bookDepth"]["all"]
        print(f"  book depth: median ${a['median']:.0f} at the bot's price within {out['bookDepth']['depth']} s; "
              f"$50 or more in {a['atLeast']['50']:.0%} of orders, nothing in {a['none']:.0%}")


if __name__ == "__main__":
    main()
