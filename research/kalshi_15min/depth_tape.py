"""The depth check's historical half: did $10 really trade at the backtest's price? Kalshi's public trade tape says.

other_markets.py's pass test found four liquid groups that paid in both halves (other_markets_findings.md): hourly
temperature 30 and 10 minutes before the close, and the daily gas, SOFR and ERCOT markets 2 and 1 hours before it.
Its backtest fills a full $10 at the recorded ask plus 0.4c, every time. The tape (who bought what, at what price,
when) shows whether takers really bought our side at that price or better in the minutes after the checkpoint, and
what the bets make if each buys only what demonstrably traded there.

Strategy: other_markets.py's favourites rule on the four groups that passed (hourly temperature 30 and 10 minutes
before the close; daily gas, SOFR and ERCOT 2 and 1 hours before). At the checkpoint, buy the favourite (the side
with the higher ask) when its ask is 90-99.9c and its own bid is within 3c of it, $10 a bet, paying up to the ask
plus 0.4c, taker fee with the series' multiplier, and hold it to settlement.

For every such bet from Jul 18 (the same bets as other_markets.bets(), read from other_markets.json and
other_hours.csv) it reads the takers who bought our side from the checkpoint on:

    soon, window   contracts and dollars bought at the ask + 0.4c or better in the first WINDOW seconds (hourly:
                   1 and 5 minutes; daily: 10 and 30 minutes)
    any trade      any taker on our side in the window, at any price
    full $10       $10 or more traded at our price in the window
    capped         profit when the bet buys at most what traded at our price in the window (up to $10 worth)

The report gives these per group, for the two halves apart (Jul 18 - Aug 31, Sep 1 on) and together, with the
backtest's profit per $10 bet over all bets, over only the full-$10 ones, and capped.

fetch: the tape of every bet's market, from SPAN before the close (35 minutes hourly, 150 minutes daily) to a minute
after it, into depth_tape.jsonl, a line a market: {"t": ticker, "tr": [[unix ts, YES price, contracts, taker side],
...]} oldest first. Markets that closed before Kalshi's cutoff (/historical/cutoff) are asked of /historical/trades
first, the rest of /markets/trades, and the other endpoint when the first has nothing. Gentle (depth_books.get: public
GETs, 4 a second, none in seconds 470-560 of a quarter hour, when the live bot orders) and resumable.

    python depth_tape.py fetch     # ~10,000 markets, about an hour
    python depth_tape.py           # the report; no requests
"""
import json
import os
import statistics
import sys
from datetime import datetime

from depth_books import get
from history import strategy
from other_markets import CHECKS, HI, LO, SLIP, SPLIT, UNIT, fee, load, num

PASSED = (("Climate and Weather", "hourly", "30min"), ("Climate and Weather", "hourly", "10min"),
          ("Economics", "daily", "2h"), ("Economics", "daily", "1h"))
WINDOW = {"min": (60, 300), "hour": (600, 1800)}   # seconds after the checkpoint: "soon" and the whole window
SPAN = {"min": 35 * 60, "hour": 150 * 60}           # the tape fetched: this long before the close to a minute after
SECONDS = {"min": 60, "hour": 3600}
STAKE = 10
TAPE = "depth_tape.jsonl"
HALVES = ("before", "after", "all")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


# ------------------------------------------------------------------ the bets


def bets_from(pairs):
    """The liquid bets of the PASSED groups among (row, series) pairs as other_markets.load() yields them, by
    other_markets.bets()'s rule: {"ticker", "series", "key", "cp" (the checkpoint, unix seconds), "close", "side",
    "ask" (the favourite's cost), "won", "mult", "unit"}."""
    out = []
    for r, s in pairs:
        unit = r["unit"]
        close = ts(r["close"])
        mult = float(s.get("fee_multiplier") if s.get("fee_multiplier") is not None else 1)
        for k in CHECKS[unit]:
            key = (s["category"], s["frequency"], f"{k}{UNIT[unit]}")
            if key not in PASSED:
                continue
            b, a = num(r.get(f"b{k}")), num(r.get(f"a{k}"))
            if b is None or a is None or b <= 0 or a >= 1:
                continue
            yes, no = a, round(1 - b, 4)
            if abs(yes - no) < 1e-9:
                continue
            side, price = ("yes", yes) if yes > no else ("no", no)
            if not LO <= price <= HI or not a - b <= 0.03:   # the band, and other_markets' own spread screen
                continue
            out.append({"ticker": r["ticker"], "series": r["series"], "key": key, "cp": close - k * SECONDS[unit],
                        "close": close, "side": side, "ask": price, "won": (side == "yes") == (r["result"] == "yes"),
                        "mult": mult, "unit": unit})
    return out


def tape_bets():
    """bets_from() other_markets.json and other_hours.csv in the working directory."""
    return bets_from(load())


# ------------------------------------------------------------------ the tape, from our side


def ours(trades, side):
    """[(ts, price on our side, contracts)] of the tape rows whose taker bought `side`, in tape order."""
    return [(t, p if side == "yes" else round(1 - p, 4), c) for t, p, c, taker in trades if taker == side]


def seen(trades, side, limit, t0, t1):
    """(contracts, dollars) takers bought on our side at our price `limit` or better, t0 <= ts < t1."""
    c = d = 0.0
    for t, p, n in ours(trades, side):
        if t0 <= t < t1 and p <= limit + 1e-9:
            c += n
            d += p * n
    return c, d


def first(trades, side, t0):
    """(seconds after t0, our price) of the first taker on our side at or after t0, at any price; None if none."""
    after = [(t, p) for t, p, _ in ours(trades, side) if t >= t0]
    if not after:
        return None
    t, p = min(after, key=lambda x: x[0])
    return t - t0, p


def check(bet, trades):
    """The bet with what the tape says about it: soon and win (contracts, dollars) at the ask + SLIP or better in the
    two windows; any_win (anyone bought our side in the window at all); first (the first buyer of our side from the
    checkpoint on); full10 ($10 or more traded in the window); the backtest's profit (the full $10 at the ask + SLIP,
    99.9c at most) and the capped one (only the contracts that traded, up to $10 worth)."""
    cp, side, unit = bet["cp"], bet["side"], bet["unit"]
    soon = seen(trades, side, bet["ask"] + SLIP, cp, cp + WINDOW[unit][0])
    win = seen(trades, side, bet["ask"] + SLIP, cp, cp + WINDOW[unit][1])
    p = min(bet["ask"] + SLIP, 0.999)
    c = STAKE / p
    backtest = (c if bet["won"] else 0.0) - STAKE - fee(c, p, bet["mult"])
    c = min(c, win[0])
    capped = (c if bet["won"] else 0.0) - c * p - fee(c, p, bet["mult"]) if c > 0 else 0.0
    return {**bet, "soon": soon, "win": win,
            "any_win": any(cp <= t < cp + WINDOW[unit][1] for t, _, _ in ours(trades, side)),
            "first": first(trades, side, cp), "full10": win[1] >= STAKE - 1e-9,
            "pnl_backtest": backtest, "pnl_capped": capped}


def summarise(checked):
    """{(key, half): what the report prints} over check()'s dicts, half "before" (closes before SPLIT), "after" or
    "all". Shares are fractions of the bets; profits are means per bet, pnl_full10_only over the full-$10 bets
    only (None if none)."""
    groups = {}
    for x in checked:
        for half in ("before" if x["close"] < SPLIT else "after", "all"):
            groups.setdefault((x["key"], half), []).append(x)
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    out = {}
    for key, half in sorted(groups, key=lambda kh: (PASSED.index(kh[0]) if kh[0] in PASSED else len(PASSED), kh[0],
                                                     HALVES.index(kh[1]))):
        xs = groups[(key, half)]
        out[(key, half)] = {"bets": len(xs),
                            "any_win": mean([x["any_win"] for x in xs]),
                            "soon10": mean([x["soon"][1] >= STAKE - 1e-9 for x in xs]),
                            "full10": mean([x["full10"] for x in xs]),
                            "median_win_dollars": statistics.median(x["win"][1] for x in xs),
                            "pnl_backtest": mean([x["pnl_backtest"] for x in xs]),
                            "pnl_full10_only": mean([x["pnl_backtest"] for x in xs if x["full10"]]),
                            "pnl_capped": mean([x["pnl_capped"] for x in xs]),
                            "capped_total": sum(x["pnl_capped"] for x in xs)}
    return out


def report(summary):
    pct = lambda x: f"{x:.0%}"
    cents = lambda x: "-" if x is None else f"{x * 100:+.1f}c"
    dollars = lambda x: f"{'-' if x < 0 else '+'}${abs(x):,.0f}"
    label = {"before": "Jul 18-Aug 31", "after": "Sep 1 on", "all": "all"}
    print(f"\n   {'':<38} {'':<13} {'':>6} {'any':>6} {'$10 at our price':^15} {'median $':>9}"
          f"   {'per $10 bet':^29} {'capped':>9}")
    print(f"   {'':<38} {'':<13} {'bets':>6} {'trade':>6} {'soon':>7} {'window':>7} {'in window':>9}"
          f"   {'backtest':>9} {'full $10':>9} {'capped':>9} {'total':>9}")
    for (key, half), v in summary.items():
        print(f"   {' · '.join(key):<38} {label[half]:<13} {v['bets']:>6,} {pct(v['any_win']):>6} {pct(v['soon10']):>7}"
              f" {pct(v['full10']):>7} {'$' + format(v['median_win_dollars'], ',.0f'):>9}   {cents(v['pnl_backtest']):>9}"
              f" {cents(v['pnl_full10_only']):>9} {cents(v['pnl_capped']):>9} {dollars(v['capped_total']):>9}")
    print("\nWindow: from the checkpoint, 5 minutes for an hourly market (soon: the first minute), 30 minutes for a"
          " daily one (soon: the first 10). Any trade: some taker bought our side in the window, at any price."
          " $10 at our price: takers bought $10 or more of our side at the ask + 0.4c or better. Median $: dollars"
          " bought there in the window. Per $10 bet: the backtest's profit (the full $10 at the ask + 0.4c, as"
          " other_markets.py has it) over every bet, over only the bets where $10 traded, and capped (each bet buys"
          " only the contracts that traded at our price in the window, up to $10 worth); capped total in dollars.")


# ------------------------------------------------------------------ Kalshi


def trades_of(ticker, close, unit, cutoff):
    """The ticker's tape from SPAN[unit] before the close to a minute after, oldest first: the historical store
    first for a market that closed before the cutoff, the live one first otherwise, the other when it has none."""
    lo, hi = int(close) - SPAN[unit], int(close) + 60
    paths = ["/historical/trades", "/markets/trades"] if close < cutoff else ["/markets/trades", "/historical/trades"]
    got = []
    for path in paths:
        cursor = None
        while True:
            params = {"ticker": ticker, "min_ts": lo, "max_ts": hi, "limit": 1000, **({"cursor": cursor} if cursor else {})}
            d = get(path, params)
            if d is None:   # a 404: nothing here
                break
            got += d.get("trades") or []
            cursor = d.get("cursor")
            if not cursor:
                break
        if got:
            break
    return sorted([round(ts(x["created_time"]), 3), float(x["yes_price_dollars"]), float(x["count_fp"]), x["taker_side"]]
                  for x in got)


def fetch(path=TAPE):
    """A line in `path` for every tape_bets() market not already there, its tape or [] when it had no trades."""
    done, ends = set(), True
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["t"])
                except ValueError:   # a line cut short by a stopped run: that market is fetched again
                    pass
                ends = line.endswith("\n")
    todo = {}
    for b in tape_bets():
        if b["ticker"] not in done:
            todo.setdefault(b["ticker"], (b["close"], b["unit"]))
    print(f"{len(done):,} markets already in {path}, {len(todo):,} to fetch", flush=True)
    if not todo:
        return
    cutoff = ts(get("/historical/cutoff")["market_settled_ts"])
    with open(path, "a", encoding="utf-8") as fh:
        if not ends:
            fh.write("\n")
        for n, (t, (close, unit)) in enumerate(todo.items(), 1):
            fh.write(json.dumps({"t": t, "tr": trades_of(t, close, unit, cutoff)}, separators=(",", ":")) + "\n")
            fh.flush()
            if n % 500 == 0:
                print(f"{n:,}/{len(todo):,}", flush=True)
    print("=== all done", flush=True)


def main():
    what = sys.argv[1:]
    if what == ["fetch"]:
        fetch()
        return
    if what:
        sys.exit("python depth_tape.py [fetch]")
    strategy(__doc__)
    bets = tape_bets()
    want = {b["ticker"] for b in bets}
    tape = {}
    with open(TAPE, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d["t"] in want:
                tape[d["t"]] = d["tr"]
    checked = [check(b, tape[b["ticker"]]) for b in bets if b["ticker"] in tape]
    missing = [b for b in bets if b["ticker"] not in tape]
    quiet = sum(1 for b in bets if tape.get(b["ticker"]) == [])
    print(f"{len(bets):,} bets on {len(want):,} markets; {len(checked):,} checked against {TAPE}"
          f" ({quiet:,} of them on markets with no trade at all in the span fetched)")
    print(f"{len(missing):,} bets ({len({b['ticker'] for b in missing}):,} markets) have no line in the tape and are"
          f" left out")
    report(summarise(checked))


if __name__ == "__main__":
    main()
