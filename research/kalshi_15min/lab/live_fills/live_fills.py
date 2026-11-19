"""The live bot's real orders against Kalshi's public trade tape: what filled, what didn't, and what would have.

The bot sends one immediate-or-cancel (IOC) buy per bet, about 2 s after minute 8 of a window ends, limited at the
favourite's ask it saw (90-99.9c). This reads its orders from bot/state/live-prod.db (read-only), fetches the public
trades in window seconds 470-600 of every market it sent an order to (tape.jsonl, both taker sides) and each market's
result (markets.json), then:

  1. live fill stats: contracts asked vs filled, fully / partly / not filled, price improvement, by order size, series
     and day, and how often the markets of unfilled orders won anyway;
  2. checks liquidity.py's fill model (strategies_backtest.available) on these real orders;
  3. what-ifs: the limit raised 0.5, 1, 2 and 3c on our side (capped at 99.9c), and a second IOC 5 or 10 s later.

Prices are always on the side the bot bought ("our side"). A YES buy is sent as a bid at the YES price. A NO buy is sent
as a sell of YES ("ask") at 1 - the NO price, and Kalshi reports that order's average_fill_price in YES terms too, so
the NO price paid is 1 - average_fill_price. A trade on the tape is "on our side" when its taker bought our side; its
price on our side is its yes_price for a YES bet and its no_price for a NO bet. Fees are Kalshi's 0.07 x C x P x (1-P)
per order, not rounded up.

The bot's own fills are on the tape too, stamped with the order's own ts_ms. The model check takes them out, so the
model sees what everyone else did (the tape the backtest sees for a market the bot didn't trade); it is also run on
the raw tape, which is what liquidity.json holds for the markets the bot traded. The extra contracts in the what-ifs
are taken earliest first after the order (an IOC meets only the book of that instant) and priced at their trades.

Results and caveats in plain words: live_fills.md.

    python research/kalshi_15min/lab/live_fills/live_fills.py fetch   # tape + results: resumable, a few minutes
    python research/kalshi_15min/lab/live_fills/live_fills.py         # writes live_fills.json, prints a summary

Run it from the repo root. API etiquette: at most RATE requests a second, and none started from 7:35 to 9:25 into
any quarter hour (the live bot orders from 7:50 to 9:20).
"""
import json
import math
import os
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime

sys.dont_write_bytecode = True   # leave no caches next to the research scripts it imports
HERE = os.path.dirname(os.path.abspath(__file__))
K15 = os.path.dirname(os.path.dirname(HERE))   # research/kalshi_15min
ROOT = os.path.dirname(os.path.dirname(K15))   # the repo
TAPE = os.path.join(HERE, "tape.jsonl")
MARKETS = os.path.join(HERE, "markets.json")
OUT = os.path.join(HERE, "live_fills.json")

UPTO = 476                  # the orders on file when this was run (the last at Oct 12, 03:38 UTC); the bot keeps adding more
RATE = 5.0                  # requests a second (the limit is 8)
QUIET_ZONE = (455, 565)     # seconds into each quarter hour when no request is started (the bot orders at 470-560)
WINDOW = (470, 600)         # window seconds of tape kept, as liquidity.py
BUMPS = (0.005, 0.01, 0.02, 0.03)
CAP = 0.999                 # the highest limit the bot may use (99.9c)
RETRY = (5, 10)             # a second IOC this many seconds after the first
BUCKETS = (("<=10", 1, 10), ("11-20", 11, 20), ("21-30", 21, 30), ("31+", 31, 10 ** 9))
SEND_BUCKETS = (("<481.5", 0, 481.5), ("481.5-482.5", 481.5, 482.5), ("482.5-483.5", 482.5, 483.5),
                ("483.5-486", 483.5, 486), ("486+", 486, 10 ** 9))   # Kalshi's time for the order, s after the open
EPS = 1e-9


# ------------------------------------------------------------------ inputs
def read_orders():
    """The bot's orders, from one quick read-only look at its live database (relative path: run from the repo root)."""
    os.chdir(ROOT)
    con = sqlite3.connect("file:bot/state/live-prod.db?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT id, ts, ticker, request, http_status, response FROM orders WHERE id <= ? ORDER BY id",
                           (UPTO,)).fetchall()
        bets = {r[0]: r for r in con.execute(
            "SELECT ticker, window_open, side, price, contracts, cost, fee, status, result, pnl FROM bets")}
    finally:
        con.close()
    out = []
    for oid, ts, ticker, req, status, resp in rows:
        q = json.loads(req)
        if "cancel" in q:   # a cancel the bot logged, not an order
            continue
        a = json.loads(resp) if resp else None
        side = {"bid": "yes", "ask": "no"}[q["side"]]
        yes_limit = float(q["price"])
        o = math.floor(ts / 900) * 900   # orders go out ~482 s into the window
        rec = {"id": oid, "ts": ts, "ticker": ticker, "series": ticker.split("-")[0], "open": o, "side": side,
               "want": int(q["count"]), "limit": round(yes_limit if side == "yes" else 1 - yes_limit, 4),
               "status": status, "accepted": status in (200, 201) and isinstance(a, dict)}
        if rec["accepted"]:
            filled = float(a.get("fill_count") or 0)
            avg = a.get("average_fill_price")
            rec["filled"] = filled
            # average_fill_price is in YES terms for both sides: the NO price paid is 1 - it
            rec["avg"] = None if not filled or avg is None else round(float(avg) if side == "yes" else 1 - float(avg), 6)
            rec["send"] = a["ts_ms"] / 1000 - o   # Kalshi's own time for the order, seconds after the open
        b = bets.get(ticker)
        if b:
            rec["bet"] = {"side": b[2], "price": b[3], "contracts": b[4], "cost": b[5], "fee": b[6], "status": b[7],
                          "pnl": b[9]}
        out.append(rec)
    return out


def lib():
    """liquidity.py (and through it strategies_backtest.py), imported from their folder: they read files relative to it."""
    os.chdir(K15)
    if K15 not in sys.path:
        sys.path.insert(0, K15)
    import liquidity
    liquidity.pace = pace   # its requests go at this script's slower pace, with the wider quiet zone
    return liquidity


_last = [0.0]


def pace():
    while True:
        s = time.time() % 900
        if QUIET_ZONE[0] <= s <= QUIET_ZONE[1]:
            time.sleep(QUIET_ZONE[1] + 1 - s)
            continue
        wait = _last[0] + 1 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
            continue   # look at the clock again after any sleep
        _last[0] = time.time()
        return


def fetch_tape(lq, ticker, o):
    """Every trade in window seconds 470-600, both taker sides: [seconds after the open, 'y'/'n' (the side the taker
    bought), YES price, contracts]. liquidity.tape's endpoints and cutoff logic, but nothing dropped."""
    paths = ["/historical/trades", "/markets/trades"] if o + 600 < lq.CUTOFF else ["/markets/trades", "/historical/trades"]
    trades = []
    for path in paths:
        cur = None
        while True:
            p = {"ticker": ticker, "min_ts": o + WINDOW[0], "max_ts": o + WINDOW[1], "limit": 1000, **({"cursor": cur} if cur else {})}
            d = lq.get(path, p)
            trades += d.get("trades") or []
            cur = d.get("cursor")
            if not cur:
                break
        if trades:
            break
    return sorted([round(datetime.fromisoformat(x["created_time"].replace("Z", "+00:00")).timestamp() - o, 6),
                   x["taker_side"][0], float(x["yes_price_dollars"]), float(x["count_fp"])] for x in trades)


def fetch_results(lq, tickers):
    """{ticker: {result, status, open, close}} from /markets, 50 tickers a request; /markets/{ticker} for any missed."""
    out = {}

    def keep(m):
        out[m["ticker"]] = {"result": m.get("result"), "status": m.get("status"), "open": m.get("open_time"),
                            "close": m.get("close_time")}
    for i in range(0, len(tickers), 50):
        for m in lq.get("/markets", {"tickers": ",".join(tickers[i:i + 50]), "limit": 100}).get("markets") or []:
            keep(m)
    for t in tickers:
        if t not in out:
            keep(lq.get(f"/markets/{t}", {})["market"])
    return out


def fetch():
    accepted = [o for o in read_orders() if o["accepted"]]
    lq = lib()
    done = set()
    if os.path.exists(TAPE):
        with open(TAPE) as fh:
            done = {json.loads(line)["t"] for line in fh}
    todo = [o for o in accepted if o["ticker"] not in done]
    print(f"{len(accepted)} accepted orders: {len(done)} tapes on file, {len(todo)} to fetch", flush=True)
    for n, o in enumerate(todo, 1):
        rec = {"t": o["ticker"], "o": o["open"], "tr": fetch_tape(lq, o["ticker"], o["open"])}
        with open(TAPE, "a") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        if n % 50 == 0:
            print(f"{n}/{len(todo)}", flush=True)
    res = fetch_results(lq, sorted({o["ticker"] for o in accepted}))
    with open(MARKETS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, separators=(",", ":"))
    print(f"tape for {len(done) + len(todo)} markets, results for {len(res)}", flush=True)


# ------------------------------------------------------------------ helpers
def fee(c, p):
    """Kalshi's taker fee for c contracts at p, exact (not rounded up to the cent)."""
    return 0.07 * c * p * (1 - p)


def pnl(c, p, won):
    """Profit after the fee on c contracts bought at p that won (paid $1 each) or lost."""
    return c * ((1 - p) if won else -p) - fee(c, p)


def our_side(tr, side):
    """The trades whose taker bought our side: [seconds after the open, price on our side, contracts], timed to the ms
    and sorted as liquidity.tape does it (one sweep's trades share a time: cheapest on our side first)."""
    k = side[0]
    return sorted([round(t, 3), px if side == "yes" else round(1 - px, 4), c] for t, s, px, c in tr if s == k)


def split_own(trades, o, tol=0.003):
    """(the tape without the order's own fills, the fills found): its fills are the trades on our side at its limit or
    better stamped within `tol` s of its ts_ms, up to the count Kalshi reported."""
    need, own, rest = o["filled"], [], []
    for x in trades:
        if need > 1e-9 and abs(x[0] - o["send"]) <= tol and x[1] <= o["limit"] + EPS:
            take = min(need, x[2])
            own.append([x[0], x[1], take])
            if x[2] - take > 1e-9:
                rest.append([x[0], x[1], x[2] - take])
            need -= take
        else:
            rest.append(x)
    return rest, own


def take_first(trades, n):
    """Up to n contracts from these trades, earliest first: (got, average price). The earliest trades after an order
    are the nearest thing on the tape to the book it met (an IOC sees only that instant); cheapest-first over the
    whole window would borrow prices that turned up later."""
    got = cost = 0.0
    for _, px, c in trades:
        if got >= n - 1e-9:
            break
        k = min(c, n - got)
        got, cost = got + k, cost + k * px
    return got, (cost / got if got > 1e-9 else None)


def spread(xs):
    """The standard error of a total of independent per-order amounts: sd * sqrt(n)."""
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) * n)


def tally(picks):
    """Totals over (order, contracts, average price) picks: orders, wins, contracts, price, fees, P&L and its noise."""
    picks = [p for p in picks if p[1] > 1e-9]
    c = sum(p[1] for p in picks)
    per = [pnl(k, px, o["won"]) for o, k, px in picks]
    return {"orders": len(picks), "orders_won": sum(bool(o["won"]) for o, _, _ in picks), "contracts": r2(c),
            "contracts_won": r2(sum(k for o, k, _ in picks if o["won"])),
            "vwap": r2(sum(k * px for _, k, px in picks) / c, 4) if c else None,
            "fees": r2(sum(fee(k, px) for _, k, px in picks)), "pnl": r2(sum(per)), "pnl_se": r2(spread(per)),
            "pnl_per_contract_cents": r2(100 * sum(per) / c, 2) if c else None,
            "contract_win_rate": share(sum(k for o, k, _ in picks if o["won"]), c)}


def predict(lq, ticker, trades, top, want, send):
    """liquidity.py's model for one order: reduce()'s [first, price, seen] for this tape, then
    strategies_backtest.available() itself (no fill if the first trade on our side after `send` came within FRESH s
    above `top`; else min(want, max(seen, QUIET)), seen = contracts bought on our side at <= top in DEPTH s)."""
    after = [x for x in trades if x[0] > send]
    seen = sum(c for dt, px, c in after if dt <= send + lq.DEPTH and px <= top + EPS)
    lq.sb.LIQUIDITY = {ticker: [round(after[0][0] - send, 3), after[0][1], round(seen, 2)] if after
                       else [None, None, round(seen, 2)]}
    return lq.sb.available({"ticker": ticker}, top, want)


def r2(x, k=2):
    return None if x is None else round(x, k)


def share(a, b):
    return round(a / b, 4) if b else None


def bucket(want):
    return next(name for name, lo, hi in BUCKETS if lo <= want <= hi)


def fill_table(rows, key):
    """Orders, contracts asked and filled, and how many filled fully / partly / not at all, per key(row)."""
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    out = []
    for k in sorted(g):
        rs = g[k]
        asked, got = sum(r["want"] for r in rs), sum(r["filled"] for r in rs)
        out.append({"key": k, "orders": len(rs), "asked": asked, "filled": r2(got), "fill_share": share(got, asked),
                    "full": sum(r["state"] == "full" for r in rs), "partial": sum(r["state"] == "partial" for r in rs),
                    "none": sum(r["state"] == "none" for r in rs), "mean_size": r2(asked / len(rs), 1)})
    return out


def check(rows, key):
    """Model vs reality over these orders: contracts, and the orders that got nothing."""
    pred = [r["pred"][key] for r in rows]
    real = [r["filled"] for r in rows]
    n = len(rows)
    both0 = sum(p == 0 and x == 0 for p, x in zip(pred, real))
    p0 = sum(p == 0 for p in pred)
    x0 = sum(x == 0 for x in real)
    return {"orders": n, "asked": sum(r["want"] for r in rows), "real": r2(sum(real)), "predicted": r2(sum(pred)),
            "mean_abs_error": r2(sum(abs(p - x) for p, x in zip(pred, real)) / n), "real_zero": x0, "predicted_zero": p0,
            "zero_caught": both0, "zero_missed": x0 - both0, "false_zero": p0 - both0,
            "exact": sum(abs(p - x) < 1e-6 for p, x in zip(pred, real))}


# ------------------------------------------------------------------ the analysis
def analyse():
    allo = read_orders()
    acc = [o for o in allo if o["accepted"]]
    tapes = {}
    with open(TAPE) as fh:
        for line in fh:
            r = json.loads(line)
            tapes[r["t"]] = r["tr"]
    with open(MARKETS, encoding="utf-8") as fh:
        results = json.load(fh)
    missing = [o["ticker"] for o in acc if o["ticker"] not in tapes or o["ticker"] not in results]
    if missing:
        raise SystemExit(f"no tape or result yet for {len(missing)} orders (run fetch): {missing[:5]}")
    lq = lib()
    fresh, quiet, depth, send0 = lq.sb.FRESH, lq.sb.QUIET, lq.DEPTH, lq.SEND

    # ---- each order: state, result, the tape on our side, its own fills found on it
    own_bad = []
    for o in acc:
        o["state"] = "none" if o["filled"] <= 1e-9 else "full" if o["filled"] >= o["want"] - 1e-9 else "partial"
        res = (results.get(o["ticker"]) or {}).get("result")
        o["won"] = None if res not in ("yes", "no") else res == o["side"]
        if o.get("bet") and o["bet"]["status"] in ("won", "lost") and (o["bet"]["status"] == "won") != o["won"]:
            raise SystemExit(f"result mismatch on {o['ticker']}")
        o["day"] = datetime.fromtimestamp(o["ts"]).strftime("%Y-%m-%d")   # the machine's local clock
        o["mine"] = our_side(tapes[o["ticker"]], o["side"])
        o["clean"], own = split_own(o["mine"], o)
        got = sum(c for _, _, c in own)
        if abs(got - o["filled"]) > 1e-6 or (got and abs(sum(c * p for _, p, c in own) / got - o["avg"]) > 6e-4):
            own_bad.append(o["ticker"])
    unsettled = [o["ticker"] for o in acc if o["won"] is None]

    # ---- 1. live fill stats
    asked, got = sum(o["want"] for o in acc), sum(o["filled"] for o in acc)
    filled = [o for o in acc if o["filled"] > 1e-9]
    imp = [(o["limit"] - o["avg"], o["filled"], o) for o in filled]
    imp_c = sum(c for _, c, _ in imp)
    big = [o for d, _, o in imp if d >= 0.01 - 1e-9]
    stats = {
        "orders_sent": len(allo), "accepted": len(acc),
        "rejected": [{"id": o["id"], "ticker": o["ticker"], "status": o["status"]} for o in allo if not o["accepted"]],
        "first": datetime.fromtimestamp(acc[0]["ts"]).isoformat(timespec="minutes"),
        "last": datetime.fromtimestamp(acc[-1]["ts"]).isoformat(timespec="minutes"),
        "asked": asked, "filled": r2(got), "fill_share": share(got, asked),
        "full": sum(o["state"] == "full" for o in acc), "partial": sum(o["state"] == "partial" for o in acc),
        "none": sum(o["state"] == "none" for o in acc),
        "send_seconds": {"median": r2(sorted(o["send"] for o in acc)[len(acc) // 2], 1),
                         "p90": r2(sorted(o["send"] for o in acc)[int(len(acc) * 0.9)], 1)},
        "price_improvement": {
            "note": "limit minus average fill price, both on our side (the price of the side bought); positive = paid less",
            "orders_filled": len(filled), "orders_improved": sum(d > 1e-6 for d, _, _ in imp),
            "cents_per_contract": r2(100 * sum(d * c for d, c, _ in imp) / imp_c, 3),
            "dollars_saved": r2(sum(d * c for d, c, _ in imp), 2),
            "orders_1c_or_more": len(big), "of_those_won": sum(bool(o["won"]) for o in big),
            "largest": sorted(([o["ticker"], o["side"], o["limit"], o["avg"], o["filled"], o["won"]] for o in big),
                              key=lambda x: x[3] - x[2])[:5]},
        "by_size": fill_table(acc, lambda o: [b[0] for b in BUCKETS].index(bucket(o["want"]))),
        # the same, Oct 10-11 only (no order cap since Oct 10), so the period doesn't stand in for the size
        "by_size_oct10_11": fill_table([o for o in acc if o["day"] >= "2026-10-10"],
                                       lambda o: [b[0] for b in BUCKETS].index(bucket(o["want"]))),
        "by_series": fill_table(acc, lambda o: o["series"]),
        "by_day": fill_table(acc, lambda o: o["day"]),
    }
    stats["by_send_time"] = fill_table(acc, lambda o: next(i for i, (_, lo, hi) in enumerate(SEND_BUCKETS) if lo <= o["send"] < hi))
    for k, names in (("by_size", BUCKETS), ("by_size_oct10_11", BUCKETS), ("by_send_time", SEND_BUCKETS)):
        for row in stats[k]:
            row["key"] = names[row["key"]][0]
    # the minute-8 rush: contracts others bought on our side, per second, over all these markets, and the part at or
    # under each order's limit
    vol, under = defaultdict(float), defaultdict(float)
    for o in acc:
        for t, px, c in o["clean"]:
            vol[int(t)] += c
            under[int(t)] += c if px <= o["limit"] + EPS else 0
    stats["volume_by_second"] = {
        "note": "contracts others bought on our side in each second after the open, all markets together; "
                "[all, at or under the order's limit]",
        **{str(s): [round(vol[s]), round(under[s])] for s in range(474, 492)},
        "500-599 per second": [round(sum(vol[s] for s in range(500, 600)) / 100),
                               round(sum(under[s] for s in range(500, 600)) / 100)]}
    # the markets of the orders that didn't fill in full, and what their missing contracts would have made at the limit
    missed = {}
    for state in ("full", "partial", "none"):
        rs = [o for o in acc if o["state"] == state]
        lost = [(o["want"] - o["filled"], o) for o in rs if o["want"] - o["filled"] > 1e-9]
        missed[state] = {"orders": len(rs), "won": sum(bool(o["won"]) for o in rs),
                         "win_rate": share(sum(bool(o["won"]) for o in rs), len(rs)),
                         "mean_limit": r2(sum(o["limit"] for o in rs) / len(rs), 4) if rs else None,
                         "missing_contracts": r2(sum(c for c, _ in lost)),
                         "missing_contracts_won": r2(sum(c for c, o in lost if o["won"])),
                         "missing_contracts_mean_limit": r2(sum(c * o["limit"] for c, o in lost) / sum(c for c, _ in lost), 4)
                         if lost else None,
                         "pnl_if_missing_filled_at_limit": r2(sum(pnl(c, o["limit"], o["won"]) for c, o in lost)),
                         "pnl_se": r2(spread([pnl(c, o["limit"], o["won"]) for c, o in lost]))}
    stats["by_fill_state"] = missed
    stats["real_pnl"] = r2(sum(o["bet"]["pnl"] or 0 for o in acc if o.get("bet")))
    # how far the price had run when an order got nothing: the first trade on our side by anyone else after it
    runs = []
    for o in acc:
        if o["state"] != "none":
            continue
        after = [x for x in o["clean"] if x[0] > o["send"]]
        runs.append(None if not after else (after[0][1] - o["limit"], after[0][0] - o["send"]))
    within = [r for r in runs if r is not None and r[1] <= fresh]
    stats["zero_fill_runaway"] = {
        "orders": len(runs), "next_trade_within_10s": len(within),
        "of_those_above_limit": sum(d > EPS for d, _ in within),
        "above_by": {f"<={int(b * 1000) / 10:g}c": sum(EPS < d <= b + EPS for d, _ in within) for b in BUMPS},
        "above_by_more_than_3c": sum(d > 0.03 + EPS for d, _ in within),
        "no_trade_within_10s": len(runs) - len(within)}

    # ---- 3. the model on the real orders
    for o in acc:
        o["pred"] = {"clean": predict(lq, o["ticker"], o["clean"], o["limit"], o["want"], send0),
                     "raw": predict(lq, o["ticker"], o["mine"], o["limit"], o["want"], send0),
                     "clean_at_send": predict(lq, o["ticker"], o["clean"], o["limit"], o["want"], o["send"]),
                     "raw_at_send": predict(lq, o["ticker"], o["mine"], o["limit"], o["want"], o["send"])}
    model = {k: check(acc, k) for k in ("clean", "raw", "clean_at_send")}
    # liquidity.py's docstring check on the first 76 orders said 126 predicted vs 130 real, 10 of 17 zero fills caught.
    # liquidity.json's [first, price] for those markets equal this tape's; its `seen` is measured at the backtest's
    # minute-8 candle ask, not the bot's real limit, which is what is used here.
    model["first76_raw"] = check(acc[:76], "raw")
    model["first76_raw_at_send"] = check(acc[:76], "raw_at_send")
    model["clean_by_size"] = {b[0]: check([o for o in acc if bucket(o["want"]) == b[0]], "clean") for b in BUCKETS}

    # what each would have booked on these orders: the real fills at their prices, and the model's contracts at the
    # limit, as the backtest books them (exact fees, each order won or lost as its market did)
    def book(count, price):
        per = [pnl(count(o), price(o), o["won"]) for o in acc if count(o) > 1e-9]
        return {"contracts": r2(sum(count(o) for o in acc)), "pnl": r2(sum(per)), "pnl_se": r2(spread(per))}
    model["pnl"] = {"real": book(lambda o: o["filled"], lambda o: o["avg"] or o["limit"]),
                    "real_fills_at_limit": book(lambda o: o["filled"], lambda o: o["limit"]),
                    **{f"model_{k}": book(lambda o, k=k: o["pred"][k], lambda o: o["limit"])
                       for k in ("clean", "raw", "clean_at_send")},
                    "every_order_in_full_at_limit": book(lambda o: o["want"], lambda o: o["limit"])}
    # one send time for every order, as the backtest assumes: which reproduces the real fills and P&L best?
    sweep = {}
    for s0 in (481.0, 482.0, 482.5, 483.0, 483.5, 484.0):
        for o in acc:
            o["pred"]["sweep"] = predict(lq, o["ticker"], o["clean"], o["limit"], o["want"], s0)
        c = check(acc, "sweep")
        sweep[f"{s0:g}"] = {k: c[k] for k in ("predicted", "zero_caught", "false_zero", "mean_abs_error")} | \
            {"pnl_at_limit": book(lambda o: o["pred"]["sweep"], lambda o: o["limit"])["pnl"],
             "losing_markets_contracts": r2(sum(o["pred"]["sweep"] for o in acc if not o["won"]))}
    for o in acc:
        del o["pred"]["sweep"]
    model["send_sweep"] = {"note": "the tape without the bot's own fills; real: 3576 contracts, P&L at the limit "
                                   f"{model['pnl']['real_fills_at_limit']['pnl']}, "
                                   f"{r2(sum(o['filled'] for o in acc if not o['won']))} contracts in losing markets",
                           **sweep}
    model["note"] = ("clean: the tape without the bot's own fills, SEND = 482 s (the model as the backtest uses it); "
                     "raw: with them, as liquidity.json has these markets; *_at_send: each order's real send time "
                     "(Kalshi's ts_ms) instead of 482 s")

    # ---- 4. the limit raised. For each order that didn't fill in full: the contracts others bought on our side at
    # prices above its limit and up to the new one, in the 30 s after it (5 s as a stricter check), earliest first, up
    # to what it still wanted; nothing if the first trade on our side within FRESH s was above even the new limit (the
    # model's no-fill rule at the new limit). Priced at those trades' prices; won or lost with the market.
    what_if = []
    for b in BUMPS:
        row = {"bump_cents": round(b * 100, 1)}
        for label, horizon in (("30s", depth), ("5s", 5)):
            picks, ran_past, tape_vol = [], 0, 0.0
            for o in acc:
                left = o["want"] - o["filled"]
                new = min(round(o["limit"] + b, 4), CAP)
                if left <= 1e-9 or new <= o["limit"] + EPS:
                    continue
                after = [x for x in o["clean"] if x[0] > o["send"]]
                if after and after[0][0] - o["send"] <= fresh and after[0][1] > new + EPS:
                    ran_past += 1
                    continue
                band = [x for x in after if x[0] <= o["send"] + horizon and o["limit"] + EPS < x[1] <= new + EPS]
                tape_vol += sum(x[2] for x in band)
                c, px = take_first(band, left)
                picks.append((o, c, px))
            row[label] = {**tally(picks), "ran_past_new_limit": ran_past, "tape_contracts_in_band": r2(tape_vol),
                          "by_fill_state": {s: tally([p for p in picks if p[0]["state"] == s]) for s in ("none", "partial")}}
        # the model itself with the higher limit (SEND = 482, the tape without the bot's own fills): its extra
        # contracts over its own prediction at the real limit, priced at the new limit as the backtest would
        picks = []
        for o in acc:
            new = min(round(o["limit"] + b, 4), CAP)
            extra = predict(lq, o["ticker"], o["clean"], new, o["want"], send0) - o["pred"]["clean"]
            picks.append((o, extra, new))
        row["model"] = tally(picks)
        what_if.append(row)

    # ---- 5. a second IOC for what's left, 5 or 10 s after the first, limited at the then-current tape price (the last
    # price paid on our side by anyone else by then) if <= 99.9c. The same rules: nothing if the first trade after it
    # within FRESH s was above that price, else up to what others bought on our side at or under it in the next 30 s,
    # earliest first, at their prices.
    retry = []
    for d in RETRY:
        picks, tried, ran, ups = [], 0, 0, []
        for o in acc:
            left = o["want"] - o["filled"]
            if left <= 1e-9:
                continue
            t2 = o["send"] + d
            before = [x for x in o["clean"] if x[0] <= t2]
            if not before or before[-1][1] > CAP + EPS:
                continue
            l2 = before[-1][1]
            tried += 1
            ups.append(l2 - o["limit"])
            after = [x for x in o["clean"] if x[0] > t2]
            if after and after[0][0] - t2 <= fresh and after[0][1] > l2 + EPS:
                ran += 1
                continue
            c, px = take_first([x for x in after if x[0] <= t2 + depth and x[1] <= l2 + EPS], left)
            picks.append((o, c, px, l2 > o["limit"] + EPS))
        retry.append({"delay_s": d, "orders_tried": tried, "ran_away_again": ran,
                      "new_limit_vs_old_cents": {"mean": r2(100 * sum(ups) / len(ups), 2) if ups else None,
                                                 "higher": sum(u > EPS for u in ups), "same": sum(abs(u) <= EPS for u in ups),
                                                 "lower": sum(u < -EPS for u in ups)},
                      **tally([p[:3] for p in picks]),
                      "limit_higher_than_first": tally([p[:3] for p in picks if p[3]]),
                      "limit_same_or_lower": tally([p[:3] for p in picks if not p[3]])})

    per_order = [{"id": o["id"], "ticker": o["ticker"], "side": o["side"], "want": o["want"], "limit": o["limit"],
                  "filled": o["filled"], "avg": o["avg"], "send_s": r2(o["send"], 3), "won": o["won"],
                  "pred_clean": r2(o["pred"]["clean"]), "pred_raw": r2(o["pred"]["raw"]),
                  "pred_at_send": r2(o["pred"]["clean_at_send"])} for o in acc]
    out = {"generated": datetime.now().isoformat(timespec="seconds"),
           "prices": "every price is on our side, the side bought (NO orders: 1 - the YES price Kalshi reports)",
           "fee": "0.07 x C x P x (1-P) per order, exact", "send": send0, "depth": depth, "fresh": fresh, "quiet": quiet,
           "own_fills_not_found": own_bad, "unsettled": unsettled,
           "stats": stats, "model_check": model, "what_if_limit": what_if, "second_ioc": retry, "orders": per_order}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    show(out)


def show(out):
    s = out["stats"]
    print(f"{s['orders_sent']} orders ({s['accepted']} accepted), {s['first']} - {s['last']}; asked {s['asked']}, "
          f"filled {s['filled']} ({s['fill_share']:.1%}); full {s['full']}, partial {s['partial']}, none {s['none']}")
    print("own fills not found on the tape:", out["own_fills_not_found"], "| unsettled:", out["unsettled"])
    print("price improvement:", json.dumps(s["price_improvement"]))
    print("volume by second:", json.dumps(s["volume_by_second"]))
    for k in ("by_size", "by_size_oct10_11", "by_send_time", "by_day", "by_series"):
        print(k)
        for r in s[k]:
            print("  ", json.dumps(r))
    print("by fill state:", json.dumps(s["by_fill_state"], indent=1))
    print("zero-fill runaway:", json.dumps(s["zero_fill_runaway"]))
    print("real pnl", s["real_pnl"])
    for k, v in out["model_check"].items():
        print("model", k, json.dumps(v))
    keys = ("orders", "orders_won", "contracts", "contract_win_rate", "vwap", "fees", "pnl", "pnl_se", "pnl_per_contract_cents")
    pick = lambda d: {k: d.get(k) for k in keys}
    for r in out["what_if_limit"]:
        print(f"what-if +{r['bump_cents']}c")
        for h in ("30s", "5s"):
            print(f"   {h}", json.dumps(pick(r[h])), "ran past:", r[h]["ran_past_new_limit"], "tape in band:",
                  r[h]["tape_contracts_in_band"])
            for s, v in r[h]["by_fill_state"].items():
                print(f"      {s}", json.dumps(pick(v)))
        print("   model", json.dumps(pick(r["model"])))
    for r in out["second_ioc"]:
        print(f"retry {r['delay_s']}s: tried {r['orders_tried']}, ran away again {r['ran_away_again']},",
              json.dumps(r["new_limit_vs_old_cents"]))
        print("   all", json.dumps(pick(r)))
        print("   higher limit", json.dumps(pick(r["limit_higher_than_first"])))
        print("   same/lower", json.dumps(pick(r["limit_same_or_lower"])))


if __name__ == "__main__":
    if sys.argv[1:2] == ["fetch"]:
        fetch()
    else:
        analyse()
