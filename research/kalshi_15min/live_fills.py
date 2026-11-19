"""The live bot's real orders against the research: what they got, and the backtests' accounts that fill the same way.

The bot sends one immediate-or-cancel order per bet, about 2 s after minute 8, limited at the favourite's ask it saw,
and gets only what the book still has: on its first 488 orders (Sep 28 - Oct 12) 54% of the contracts it asked for,
nothing at all on 29% of them. Every backtest but the real-liquidity ones fills each order in full. This reads the
live bot's ledger (bot/state/live-prod.db, opened read-only and copied into memory at once, so the bot is never held
up) and sets each order against the research data (the minute files, liquidity.json):

  summary      orders filled in full, in part, not at all; contracts asked for and got; the gap between the prices
               paid, the order's limit and the minute-8 candle ask, in cents a contract; how often the filled and
               the missed orders' markets won; the fees paid against Kalshi's exact formula and sb.fee's rounding up
  by...        the same by price band (the order's limit), size (contracts asked), market and group
  tape         liquidity.py's fill model against the real fills. For a market the bot traded, the tape it reads
               holds the bot's own fills too (lab/live_fills/ takes them out)
  depth        the fill table strategies_backtest's "live fills" accounts use (below)
  replay       the backtest's live rule against the bot, market by market, over the windows the bot traded
  candidates   the live bets each of the Oct 11 lab's changes would have dropped, and what they made

The fill table: how many contracts were waiting at the bot's price. An order that filled in part shows it exactly
(the book had what it got), one that got nothing shows none, and one that filled in full only that there were at least
that many (a censored count). Kaplan-Meier, the survival estimate made for counts like that, gives survival[k], the
chance the book had more than k, for k up to the largest order (or until no order says more); an order for c then
expects survival[0] + ... + survival[c-1] (strategies_backtest.expected_fill). A market with MIN_ORDERS live orders
has its own table, one with fewer its group's, and a group with fewer the table from every order. It's today's book
applied to the whole history: the trade-tape replays use each market's own trades instead.

Writes live_fills.json, which strategies_backtest.py reads at import (rerun it afterwards), and prints a report.

    python live_fills.py              # the real-money bot's ledger
    python live_fills.py LEDGER.db    # any other ledger
"""
import errno
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import history
import strategies_backtest as sb

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.normpath(os.path.join(HERE, "..", "..", "bot", "state", "live-prod.db"))
OUT = "live_fills.json"
MIN_ORDERS = sb.MIN_ORDERS
BANDS = [(0.90, 0.92, "90–91"), (0.92, 0.95, "92–94"), (0.95, 1.0, "95+")]           # by the order's limit
SIZES = [(1, 5, "1–5"), (6, 15, "6–15"), (16, 30, "16–30"), (31, None, "31+")]      # by contracts asked for
expected_fill, pick = sb.expected_fill, sb.pick


# ------------------------------------------------------------------ the ledger
def read_ledger(path):
    """(orders, bets, decisions) from a ledger, never writing to it: opened read-only and copied into memory, the file
    closed at once. Orders are the ones Kalshi took (HTTP 200 or 201, with a JSON answer), by row id, each with its
    side, limit, contracts asked for and got, and average price on its own side (a NO buy goes to Kalshi as a sell of
    YES at 1 - the NO price, and its average comes back in YES terms too)."""
    path = str(path)
    if not os.path.exists(path):
        raise FileNotFoundError(errno.ENOENT, "no ledger", path)
    src = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
    db = sqlite3.connect(":memory:")
    try:
        src.backup(db)
    finally:
        src.close()
    db.row_factory = sqlite3.Row
    try:
        orders = [o for o in map(order, db.execute("SELECT * FROM orders ORDER BY id")) if o]
        bets = {r["ticker"]: dict(r) for r in db.execute("SELECT * FROM bets")}
        decisions = {r["ticker"]: dict(r) for r in db.execute("SELECT * FROM decisions")}
    finally:
        db.close()
    return orders, bets, decisions


def order(row):
    """An orders row as read_ledger gives it, or None for one Kalshi didn't take (or a cancel, which isn't an order)."""
    if row["http_status"] not in (200, 201):
        return None
    try:
        req, res = json.loads(row["request"]), json.loads(row["response"])
    except (TypeError, ValueError):
        return None
    if not (isinstance(req, dict) and isinstance(res, dict) and req.get("side") in ("bid", "ask") and "count" in req):
        return None
    yes = req["side"] == "bid"
    own = lambda p: float(p) if yes else round(1 - float(p), 4)  # noqa: E731
    got = float(res.get("fill_count") or 0)
    avg = res.get("average_fill_price")
    return {"id": row["id"], "ticker": row["ticker"], "series": row["ticker"].split("-")[0], "ts": row["ts"],
            "side": "yes" if yes else "no", "limit": own(req["price"]), "want": float(req["count"]), "got": got,
            "price": own(avg) if got and avg is not None else None,
            "fee": float(res.get("average_fee_paid") or 0) * got}


def outcome(o, bets, m):
    """Would the order's side win? Its settled bet says, else the research data (market m), else nobody knows yet."""
    b = bets.get(o["ticker"])
    if b and b.get("status") in ("won", "lost"):
        return b["status"] == "won"
    return None if m is None else (o["side"] == "yes") == m["yes"]


# ------------------------------------------------------------------ the fill table
def depth_model(orders):
    """The fill tables: one from every order, one per group and one per market (series)."""
    groups = history.groups()
    by_group, by_series = defaultdict(list), defaultdict(list)
    for o in orders:
        by_group[groups.get(o["series"], "other")].append(o)
        by_series[o["series"]].append(o)
    return {"all": table(orders), "groups": {g: table(os_) for g, os_ in by_group.items()},
            "series": {s: table(os_) for s, os_ in by_series.items()}}


def table(orders):
    """Kaplan-Meier over whole contracts: at each k, the orders still in question are those whose book had k or more
    for certain (filled in part or not at all, with D = got >= k) or might have (filled in full, with want > k); the
    share of them whose book had exactly k is that step's drop."""
    obs = [(o["got"], o["got"] < o["want"], o["want"]) for o in orders]   # (D or its lower bound, exact?, want)
    top = int(max(w for _, _, w in obs))
    survival, s = [], 1.0
    for k in range(top):
        risk = sum(1 for d, exact, w in obs if (d >= k if exact else w > k))
        if not risk:
            break
        s *= 1 - sum(1 for d, exact, _ in obs if exact and d == k) / risk
        survival.append(round(s, 6))
    return {"orders": len(orders), "maxWant": top, "survival": survival}


# ------------------------------------------------------------------ each order against the data
def markets(windows):
    """{ticker: (window open, market)} over the data."""
    return {m["ticker"]: (t, m) for t, ms in windows.items() for m in ms}


def compare(orders, bets, decisions, windows):
    """Each order's group, minute-8 ask on its own side, outcome and trade-tape model fill (added to the orders), with
    the summary, the breakdowns and the tape check."""
    where, groups = markets(windows), history.groups()
    for o in orders:
        m = where.get(o["ticker"], (None, None))[1]
        q = sb.own_quote(m, o["side"], 8) if m else None
        o["group"] = m["group"] if m else groups.get(o["series"], "other")
        o["ask"] = q[1] if q else None
        o["won"] = outcome(o, bets, m)
        o["tape"] = (sb.available(m, o["ask"], o["want"])
                     if sb.LIQUIDITY and o["ticker"] in sb.LIQUIDITY and o["ask"] is not None else None)
    stamp = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()  # noqa: E731
    filled = [o for o in orders if o["got"] > 0 and o["price"] is not None]

    def gap(rows, a, b):   # cents a contract, weighted by contracts got
        w = sum(o["got"] for o in rows)
        return sum((o[a] - o[b]) * o["got"] for o in rows) / w * 100 if w else None
    asked = [o for o in orders if o["ask"] is not None]
    both = [o for o in filled if o["ask"] is not None]
    known = [o for o in orders if o["won"] is not None]
    paid = [bets[o["ticker"]] for o in orders if o["got"] > 0 and o["ticker"] in bets]
    summary = {
        "orders": len(orders), "none": sum(o["got"] == 0 for o in orders),
        "partial": sum(0 < o["got"] < o["want"] for o in orders), "full": sum(o["got"] >= o["want"] for o in orders),
        "asked": sum(o["want"] for o in orders), "got": sum(o["got"] for o in orders),
        "fillRate": rate(orders), "from": stamp(min(o["ts"] for o in orders)) if orders else None,
        "to": stamp(max(o["ts"] for o in orders)) if orders else None, "dataEnd": history.end(),
        "gap": {"fillVsLimit": gap(filled, "price", "limit"),
                "limitVsAsk": sum(o["limit"] - o["ask"] for o in asked) / len(asked) * 100 if asked else None,
                "fillVsAsk": gap(both, "price", "ask"), "n": len(both)},
        "won": {"filled": [sum(o["won"] for o in known if o["got"] > 0), sum(o["got"] > 0 for o in known)],
                "missed": [sum(o["won"] for o in known if o["got"] == 0), sum(o["got"] == 0 for o in known)]},
        "fee": {"paid": sum(b["fee"] for b in paid),
                "exact": sum(0.07 * b["contracts"] * b["price"] * (1 - b["price"]) for b in paid),
                "rounded": sum(sb.fee(b["contracts"], b["price"]) for b in paid)},
    }
    band = lambda o: next((k for lo, hi, k in BANDS if lo <= o["limit"] < hi), None)  # noqa: E731
    size = lambda o: next((k for lo, hi, k in SIZES if lo <= o["want"] and (hi is None or o["want"] <= hi)), None)  # noqa: E731
    series = defaultdict(list)
    for o in orders:
        series[o["series"]].append(o)
    group = defaultdict(list)
    for o in orders:
        group[o["group"]].append(o)
    tape = [o for o in orders if o["tape"] is not None]
    cell = lambda o: f"model {'some' if o['tape'] > 0 else 'none'}/real {'some' if o['got'] > 0 else 'none'}"  # noqa: E731
    return {"orders": orders, "summary": summary,
            "byBand": [row(k, [o for o in orders if band(o) == k]) for _, _, k in BANDS],
            "bySize": [row(k, [o for o in orders if size(o) == k]) for _, _, k in SIZES],
            "bySeries": sorted((row(k, v) for k, v in series.items()), key=lambda r: -r["orders"]),
            "byGroup": sorted((row(k, v) for k, v in group.items()), key=lambda r: -r["orders"]),
            "tape": {"orders": len(tape), "predicted": sum(o["tape"] for o in tape), "real": sum(o["got"] for o in tape),
                     "table": {k: sum(cell(o) == k for o in tape) for k in
                               ("model none/real none", "model none/real some", "model some/real none", "model some/real some")}}}


def rate(orders):
    asked = sum(o["want"] for o in orders)
    return sum(o["got"] for o in orders) / asked if asked else None


def row(key, orders):
    known = [o for o in orders if o["won"] is not None]
    return {"key": key, "orders": len(orders), "none": sum(o["got"] == 0 for o in orders),
            "asked": sum(o["want"] for o in orders), "got": sum(o["got"] for o in orders), "fillRate": rate(orders),
            "filledWon": sum(o["won"] for o in known if o["got"] > 0), "filledN": sum(o["got"] > 0 for o in known),
            "missedWon": sum(o["won"] for o in known if o["got"] == 0), "missedN": sum(o["got"] == 0 for o in known)}


# ------------------------------------------------------------------ the backtest's rule against the bot
def picks(t, ms):
    """The live rule's picks in window t, as sb.run makes them for the live bot: {ticker: (side, top)}."""
    live = sb.LIVE[0]
    if blackout(t):
        return {}
    out = {}
    for m in ms:
        side, top = sb.favourite(*m["q"][live["minute"]])
        if m["group"] in live["groups"] and side and sb.LO <= top <= sb.HI and not sb.skipped(live, m, side):
            out[m["ticker"]] = (side, top)
    return out


def blackout(t):
    return any(t < z and t + 900 > a for a, z in sb.LIVE[0]["blackouts"])


def replay(orders, decisions, windows):
    """Market by market, over the data's windows from the bot's first order on that the bot was running in (it logs a
    decision for every market it looks at, so a window with none it didn't see): the markets both bought (and on the
    same side?), the ones only the backtest did (and the bot's reason) and only the bot did (and why the backtest
    didn't), and each side's profit in cents per $10 staked at $10 a bet: the backtest filled in full at the candle ask
    with sb.fee, the bot at its real prices and fees, every bet scaled to $10 so each weighs the same. "same" sets the
    two side by side on the markets both bought, so its gap is the fills alone, not which markets each picked."""
    live, where = sb.LIVE[0], markets(windows)
    w0 = min((o["ts"] // 900 * 900 for o in orders), default=math.inf)
    on = {d["ts"] // 900 * 900 for d in decisions.values()}
    covered = sorted(t for t in windows if t >= w0 and t in on)
    chosen = {}
    for t in covered:
        for ticker, p in picks(t, windows[t]).items():
            chosen[ticker] = (t, *p)
    sent = {o["ticker"]: o for o in orders}
    both = [k for k in chosen if k in sent]
    why_b = dict.fromkeys(("halted", "warning sign", "outside the band", "other skip", "no decision"), 0)
    for k in chosen:
        if k in sent:
            continue
        d = decisions.get(k)
        reason = (d or {}).get("reason") or ""
        why_b["no decision" if d is None else "halted" if d["action"] == "halted" else "warning sign"
              if reason.startswith("warning sign") else "outside the band" if "outside" in reason else "other skip"] += 1
    why_l = dict.fromkeys(("not in the data", "outside the band at the candle", "warning sign at the candle", "blackout",
                           "other"), 0)
    for k, o in sent.items():
        if k in chosen:
            continue
        t, m = where.get(k, (None, None))
        side, top = sb.favourite(*m["q"][live["minute"]]) if m else (None, None)
        why_l["not in the data" if m is None else "blackout" if blackout(t) else "other"
              if m["group"] not in live["groups"] else "outside the band at the candle"
              if not side or not sb.LO <= top <= sb.HI else "warning sign at the candle"
              if sb.skipped(live, m, side) else "other"] += 1
    bt = {}
    for k, (t, side, top) in chosen.items():
        m, c = where[k][1], 10 / top
        bt[k] = ((c if (side == "yes") == m["yes"] else 0.0) - 10 - sb.fee(c, top)) / 10
    real = {}
    for o in orders:
        m = where.get(o["ticker"], (None, None))[1]
        if o["got"] > 0 and o["price"] is not None and m is not None:
            cost = o["got"] * o["price"]
            real[o["ticker"]] = ((o["got"] if (o["side"] == "yes") == m["yes"] else 0.0) - cost - o["fee"]) / cost
    mean = lambda xs: sum(xs) / len(xs) * 1000 if xs else None  # noqa: E731
    same = [k for k in both if k in real]
    return {"windows": len(covered), "both": {"n": len(both), "sameSide": sum(sent[k]["side"] == chosen[k][1] for k in both)},
            "backtestOnly": {"n": len(chosen) - len(both), "why": why_b},
            "liveOnly": {"n": len(sent) - len(both), "why": why_l},
            "perBet": {"backtest": mean(list(bt.values())), "live": mean(list(real.values())), "backtestBets": len(bt),
                       "liveBets": len(real), "same": {"n": len(same), "backtest": mean([bt[k] for k in same]),
                                                       "live": mean([real[k] for k in same])}}}


# ------------------------------------------------------------------ the lab's changes on the live bets
def candidates(orders, bets, decisions):
    """For each of the lab's candidate accounts (not their real-liquidity or live-fills copies, which run the same
    rule), the live bets it would have dropped: their count, wins and real profit (a positive one is profit it would
    have given up), and the dropped orders that got nothing anyway. skipSeries and skipSlots go first, then maxPer
    keeps a window's k orders in a group with the tightest spread the bot saw, then the dearest, then the first sent."""
    groups = history.groups()
    windows = defaultdict(list)
    for o in orders:
        windows[o["ts"] // 900 * 900].append(o)
    out = {}
    for s in sb.LIVE:
        if s.get("role") != "candidate" or s.get("liquidity") or s.get("liveFit") \
                or not any(s.get(k) for k in ("skipSeries", "skipSlots", "maxPer")):
            continue
        dropped = []
        for t, os_ in windows.items():
            keep = []
            for o in os_:
                if o["series"] in (s.get("skipSeries") or ()) or (s.get("skipSlots") and sb.slot(t) in s["skipSlots"]):
                    dropped.append(o)
                else:
                    keep.append(o)
            for g, k in (s.get("maxPer") or {}).items():
                mine = sorted((o for o in keep if groups.get(o["series"], "other") == g), key=lambda o: (spread(decisions.get(o["ticker"])), -o["limit"], o["id"]))
                dropped += mine[k:]
        fills = [bets[o["ticker"]] for o in dropped if o["got"] > 0 and o["ticker"] in bets]
        out[s["id"]] = {"name": s["name"], "dropped": len(fills), "wins": sum(b["status"] == "won" for b in fills),
                        "pnl": round(sum(b["pnl"] or 0.0 for b in fills), 2), "missed": sum(o["got"] == 0 for o in dropped)}
    return out


def spread(d):
    """The YES ask over the YES bid the bot saw (the same on either side), to 4 places; none known ranks last."""
    if not d or d.get("yes_bid") is None or d.get("yes_ask") is None:
        return math.inf
    return round(d["yes_ask"] - d["yes_bid"], 4)


# ------------------------------------------------------------------ the command line
def report(out):
    s, g = out["summary"], out["summary"]["gap"]
    c = lambda x: "—" if x is None else f"{x:+.2f}c"  # noqa: E731
    pc = lambda w, n: f"{w} of {n} ({w / n:.1%})" if n else "none known"  # noqa: E731
    print(f"{s['orders']} orders, {(s['from'] or '')[:10]} to {(s['to'] or '')[:10]} (the data ends {s['dataEnd'][:10]})")
    print(f"  filled in full {s['full']}, in part {s['partial']}, not at all {s['none']}; "
          f"contracts {s['got']:,.0f} of {s['asked']:,.0f} asked for"
          + (f" ({s['fillRate']:.1%} fill rate)" if s["fillRate"] is not None else ""))
    print(f"  price paid vs the limit {c(g['fillVsLimit'])}, the limit vs the minute-8 ask {c(g['limitVsAsk'])}, "
          f"paid vs the ask {c(g['fillVsAsk'])} ({g['n']} orders)")
    print(f"  won: filled {pc(*s['won']['filled'])}, missed {pc(*s['won']['missed'])}")
    f = s["fee"]
    print(f"  fees paid ${f['paid']:.2f}, exact formula ${f['exact']:.2f}, rounded up per order ${f['rounded']:.2f}")
    for kind in ("byBand", "bySize", "byGroup", "bySeries"):
        print(f"  {kind[2:].lower()}: " + ", ".join(
            f"{r['key']} {r['orders']} ({'—' if r['fillRate'] is None else f'{r['fillRate']:.0%}'})" for r in out[kind]))
    t = out["tape"]
    if t and t["orders"]:
        print(f"  trade-tape model on {t['orders']} orders: {t['predicted']:,.0f} contracts predicted, {t['real']:,.0f} real; "
              + ", ".join(f"{k} {v}" for k, v in t["table"].items()))
    r = out["replay"]
    print(f"replay over {r['windows']} windows: both {r['both']['n']} ({r['both']['sameSide']} on the same side), "
          f"backtest only {r['backtestOnly']['n']} {r['backtestOnly']['why']}, live only {r['liveOnly']['n']} {r['liveOnly']['why']}")
    p = r["perBet"]
    print(f"  per $10: backtest {c(p['backtest'])} over {p['backtestBets']} bets, live {c(p['live'])} over {p['liveBets']}; "
          f"on the {p['same']['n']} markets both bought, backtest {c(p['same']['backtest'])}, live {c(p['same']['live'])}")
    for sid, x in out["candidates"].items():
        print(f"  {x['name']}: drops {x['dropped']} filled bets ({x['wins']} won, ${x['pnl']:+.2f} real profit), "
              f"{x['missed']} that got nothing")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    path = args[0] if args else LEDGER
    try:
        orders, bets, decisions = read_ledger(path)
    except FileNotFoundError:
        print(f"No ledger at {path}: the live bot writes it when it runs (or name another one).")
        return 1
    windows = sb.load()[0]
    out = {"ledger": os.path.basename(path), "depth": depth_model(orders), "replay": replay(orders, decisions, windows),
           "candidates": candidates(orders, bets, decisions)}
    c = compare(orders, bets, decisions, windows)
    out.update({k: c[k] for k in ("summary", "byBand", "bySize", "bySeries", "byGroup", "tape", "orders")})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    report(out)
    print(f"wrote {OUT}: rerun strategies_backtest.py for the live-fills accounts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
