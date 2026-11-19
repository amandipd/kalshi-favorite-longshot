"""How many contracts the live bot could really have bought: Kalshi's public trade tape around each of its bets.

The backtests fill every order in full at the ask recorded at the end of minute 8. The live bot instead sends an
immediate-or-cancel order at that ask about 2 s later (SEND), and gets only what is still on the book: on its first 76
real orders (Sep 28 - Oct 10) it got 70% of the contracts it asked for, nothing at all on 17 of them, because other
traders had already bought the ask away and the price had moved up.

For every bet the live rule makes from Jul 18 (strategies_backtest.LIVE: the minute-8 favourite at 90-99.9c in crypto, metals and
energy, both warning signs skipped, no bets in the Fed blackouts) this fetches the trades in minutes 7:50 to 10 and
keeps those whose taker bought the favourite's side. liquidity.json then holds, per market:

    [first, price, seen]   first: seconds after SEND of the first trade on our side after it (None if none by
                           minute 10); price: its price on our side; seen: contracts bought on our side at the
                           minute-8 ask or better in the DEPTH seconds after SEND

strategies_backtest.py reads it for "The live bot · real liquidity" (fill() there): no fill when the first trade
after the order came within FRESH seconds and above our price (the price ran away), and otherwise at most the larger of
`seen` and QUIET contracts. Checked against the bot's 76 real orders, that predicts 126 contracts filled against 130
real, catching 10 of the 17 orders that got nothing (and calling 8 of the 59 that filled misses).

Trades before Aug 10 are at /historical/trades, later ones at /markets/trades (/historical/cutoff). The fetch is gentle
(4 workers, 8 requests a second, waiting out minutes 7:50-9:20 of every quarter hour, when the live bot orders) and
resumable; the raw tape (~110 MB) stays out of the repo.

    python liquidity.py fetch TAPE.jsonl     # ~1 hour for ~20,000 bets
    python liquidity.py reduce TAPE.jsonl    # writes liquidity.json

    python liquidity.py fetch TAPE.jsonl 2025-12-10    # the bets from Dec 10 too: the pre-July history
    python liquidity.py reduce TAPE.jsonl 2025-12-10   # liquidity.json for all of them
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

import strategies_backtest as sb

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CUTOFF = sb.ts("2026-08-10T00:00:00Z")
SEND, DEPTH = 482, 30
RATE, WORKERS = 8.0, 4


def bets(since=None):
    """Every market the live rule bets on from `since` (a date, 2025-12-10; Jul 18 unless given): (ticker, window open,
    favourite side, its minute-8 ask). The history reaches back to Dec 10 (minutes_pre.csv); the tape was first fetched
    from Jul 18 only, and an earlier `since` extends it."""
    live = sb.LIVE[0]
    windows, _, _ = sb.load()
    since = sb.ts(f"{since}T00:00:00Z" if since else sb.history.JUL18)
    out = []
    for t, ms in sorted(windows.items()):
        if t < since or any(t < z and t + 900 > a for a, z in live["blackouts"]):
            continue
        for m in ms:
            if m["group"] not in live["groups"]:
                continue
            side, top = sb.favourite(*m["q"][live["minute"]])
            if side and sb.LO <= top <= sb.HI and not sb.skipped(live, m, side):
                out.append((m["ticker"], t, side, top))
    return out


lock, last, local = threading.Lock(), [0.0], threading.local()


def pace():
    while 470 <= time.time() % 900 <= 560:   # the live bot's entry: stay off the API
        time.sleep(561 - time.time() % 900)
    with lock:
        wait = last[0] + 1 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        last[0] = time.time()


def get(path, params):
    if not hasattr(local, "s"):
        local.s = requests.Session()
    for i in range(6):
        pace()
        try:
            r = local.s.get(BASE + path, params=params, timeout=15)
        except requests.RequestException:
            time.sleep(1 + i)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 + 2 * i)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path} {params}")


def tape(ticker, t, side):
    """The trades in minutes 7:50-10 whose taker bought `side`: [seconds after the window opened, price, contracts]."""
    o = int(t)
    paths = ["/historical/trades", "/markets/trades"] if o + 600 < CUTOFF else ["/markets/trades", "/historical/trades"]
    trades = []
    for path in paths:
        cur = None
        while True:
            p = {"ticker": ticker, "min_ts": o + 470, "max_ts": o + 600, "limit": 1000, **({"cursor": cur} if cur else {})}
            d = get(path, p)
            trades += d.get("trades") or []
            cur = d.get("cursor")
            if not cur:
                break
        if trades:
            break
    mine = [[round(datetime.fromisoformat(x["created_time"].replace("Z", "+00:00")).timestamp() - t, 3),
             float(x["yes_price_dollars"] if side == "yes" else x["no_price_dollars"]), float(x["count_fp"])]
            for x in trades if x["taker_side"] == side]
    return sorted(mine)


def fetch(path, since=None):
    done = set()
    try:
        with open(path) as fh:
            done = {json.loads(line)["t"] for line in fh}
    except FileNotFoundError:
        pass
    todo = [b for b in (bets(since) if since else bets()) if b[0] not in done]
    print(f"{len(done)} done, {len(todo)} to fetch", flush=True)
    wlock = threading.Lock()

    def work(b):
        rec = {"t": b[0], "tr": tape(b[0], b[1], b[2])}
        with wlock, open(path, "a") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for n, _ in enumerate(pool.map(work, todo), 1):
            if n % 1000 == 0:
                print(f"{n}/{len(todo)} · ~{(len(todo) - n) * (time.time() - t0) / n / 60:.0f} min left", flush=True)


def reduce(path, since=None):
    tops = {b[0]: b[3] for b in (bets(since) if since else bets())}
    out = {}
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            top = tops.get(r["t"])
            if top is None:
                continue
            after = [x for x in r["tr"] if x[0] > SEND]
            seen = sum(c for dt, px, c in after if dt <= SEND + DEPTH and px <= top + 1e-9)
            out[r["t"]] = [round(after[0][0] - SEND, 3), after[0][1], round(seen, 2)] if after else [None, None, round(seen, 2)]
    with open("liquidity.json", "w", encoding="utf-8") as fh:
        json.dump({"send": SEND, "depth": DEPTH, "markets": out}, fh, separators=(",", ":"))
    print(f"liquidity.json: {len(out)} of {len(tops)} bets")


if __name__ == "__main__":
    {"fetch": fetch, "reduce": reduce}[sys.argv[1]](*sys.argv[2:4])
