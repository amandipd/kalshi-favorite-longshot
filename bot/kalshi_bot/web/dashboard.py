"""A dashboard for the bot: your account, its bets and its decisions, from its own records.

    python dashboard.py           then open http://localhost:8080
    python dashboard.py --lan     also reachable from your phone on your home network

It reads the bot's records in state/. While a paper ledger exists (dry-prod) only paper modes get a
tab and your real account is never shown: the page tracks the paper bot, led by the simulated $1,000
account from the research backtest (strategies.json). For a live mode with a key set up it reads your
real account from Kalshi (read only): its value now, re-read every 10 seconds, and its value over
time, rebuilt from Kalshi's own deposit, withdrawal and settlement records. Open bets are valued at what you could sell
them for now. It can halt the bot but never resume it: resuming stays a command you run
(python bot.py --resume), and only its own page can press the halt button, not a page from another site. The live 15-minute markets stream from Kalshi's WebSocket when websocket-client is
installed and .env has a prod key, and are polled once a second otherwise.
"""
import argparse
import glob
import importlib
import importlib.util
import ipaddress
import json
import math
import os
import pathlib
import re
import sqlite3
import statistics
import threading
import time
from collections import deque
from time import time as pc_clock   # this PC's own clock, as the paper +1¢'s date (SHADOW_UNTIL) is read
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from kalshi_bot import bot, fast_entry
from kalshi_bot.kalshi import ORDER_TIMEOUT, Kalshi, sign
from kalshi_bot.web import latency

# websocket-client (pip install websocket-client): Kalshi's live prices as they change. Without it, the feed polls.
WS = importlib.import_module("websocket") if importlib.util.find_spec("websocket") else None

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")   # the pages and the files they load
PAGE = os.path.join(STATIC, "dashboard.html")
ASSETS = {"/live_research.js": ("live_research.js", "text/javascript; charset=utf-8"),   # the Live Research tab
          "/live_research.css": ("live_research.css", "text/css; charset=utf-8"),
          "/latency.js": ("latency.js", "text/javascript; charset=utf-8"),               # the Latency tab
          "/latency.css": ("latency.css", "text/css; charset=utf-8"),
          "/backtest.js": ("backtest.js", "text/javascript; charset=utf-8"),       # the Backtest tab
          "/backtest.css": ("backtest.css", "text/css; charset=utf-8"),
          "/exchange.css": ("exchange.css", "text/css; charset=utf-8"),   # the Live tab's exchange skin
          "/tape_fmt.js": ("tape_fmt.js", "text/javascript; charset=utf-8"),       # the Tape page (SPEC_TAPE.md)
          "/tape_panels.js": ("tape_panels.js", "text/javascript; charset=utf-8"),
          "/tape.js": ("tape.js", "text/javascript; charset=utf-8"),
          "/tape.css": ("tape.css", "text/css; charset=utf-8"),
          "/tape_panels.css": ("tape_panels.css", "text/css; charset=utf-8")}
TAPE = os.path.join(STATIC, "tape.html")   # the Tape page, at /tape beside the classic page at /
RESEARCH = os.path.normpath(os.path.join(bot.HERE, "..", "research", "kalshi_15min"))   # the study the bot trades
# The research outputs /api/research serves (study()); /api/research/stamp moves when one of these files changes.
STUDY_FILES = ("strategies.json", "findings.json", "key_stats.json", "all_markets.json", "sizing.json", "price_floor.json",
               "live_losses.json", os.path.join("dashboard", "src", "generated", "dashboard.json"))
ACCOUNT_EVERY = 10   # seconds between reads of your Kalshi balance (the page refreshes every second: Kalshi is asked at most this often)
BALANCE_EVERY = 0.5  # ... and of the navbar's balance: under its 1-second poll, as a reading is stamped when Kalshi answers,
                     # so every poll reads it fresh; tabs polling together share a read (two calls a second at most)
HISTORY_EVERY = 30   # ... and of the records its value over time is rebuilt from
RESEARCH_EVERY = 0.2 # ... and of the research folder and the live board: under the board's 250 ms poll, so every poll reads it fresh
REPLAY_STEP = 6      # hours between the points of each account's replay from Jul 18
_cache, _lock = {}, threading.Lock()

# The page shows real time, not this PC's clock (about 0.15 s behind on Oct 11): internet time servers are asked
# (fast_entry.ntp_offset: Microsoft's, Google's and Cloudflare's at once, the median) on a thread of their own, at most
# every CLOCK_EVERY s, and the page's own one-second tick carries the offset in between. Only the "now" sent to the page
# moves to real time: everything compared with the ledger stays on the PC's clock, which wrote it.
CLOCK_EVERY = 60
_clock = {"offset": None, "checked": None, "attempt": None, "busy": False}
_clock_lock = threading.Lock()


def _check_clock(now):
    """One check of internet time, on the "internet-clock" thread: a good answer becomes the offset, and one that fails
    (None, or an exception) keeps the last good one. It never raises: the thread has no one to raise to."""
    try:
        offset = fast_entry.ntp_offset()
    except Exception:
        offset = None
    with _clock_lock:
        if offset is not None:
            _clock["offset"], _clock["checked"] = offset, now
        _clock["busy"] = False


def clock(now=None):
    """How far real time is ahead of this PC's clock: {"offset": seconds or None before the first good answer, "synced",
    "checked": PC time of that answer}. It never waits: when a check is due (none yet, or CLOCK_EVERY s since the last
    attempt, good or not) and none is running, it starts one on a daemon thread and answers with what it has."""
    now = time.time() if now is None else now
    with _clock_lock:
        last = _clock.get("attempt")
        due = not _clock.get("busy") and (last is None or now - last >= CLOCK_EVERY)
        if due:
            _clock["busy"], _clock["attempt"] = True, now
        offset, checked = _clock.get("offset"), _clock.get("checked")
    if due:
        threading.Thread(target=_check_clock, args=(now,), daemon=True, name="internet-clock").start()
    return {"offset": offset, "synced": offset is not None, "checked": checked}


def real_now():
    """Real time: this PC's clock plus the internet-time offset (none yet: the PC's own)."""
    return time.time() + (clock()["offset"] or 0.0)


def cached(key, ttl, fn):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def modes():
    """The modes the page offers. While a paper ledger exists (dry-prod: python bot.py, no --live) only paper modes
    get a tab, and the real Kalshi account stays off the page. A dated experiment copy (dry-prod-500-nov3) and a --paper account keep their records in
    state/ but get no tab. With no paper ledger yet, the old live modes (live-prod, live-demo), real money first,
    so old data still renders."""
    names = [os.path.basename(p)[:-3] for p in glob.glob(os.path.join(bot.STATE, "*.db"))]
    dry = sorted((n for n in names if re.fullmatch(r"dry-[a-z]+", n)), key=lambda n: (n != "dry-prod", n))
    return dry or sorted((n for n in names if not n.startswith(("paper", "dry"))),
                         key=lambda n: (n != "live-prod", not n.startswith("live"), n))


def num(v):
    return float(v) if v not in (None, "") else None


def marks(env, tickers):
    """What each open market's YES trades at now: {ticker: (bid, ask)}, from Kalshi's public prices."""
    d = Kalshi(env).markets(tickers=",".join(tickers), limit=100)
    return {m["ticker"]: (num(m.get("yes_bid_dollars")), num(m.get("yes_ask_dollars"))) for m in (d or {}).get("markets", [])}


def client(env):
    """A signed Kalshi client for env, or why there isn't one: the key in .env must be for this environment."""
    cfg = bot.load_env()
    if not (cfg.get("KALSHI_API_KEY_ID") and cfg.get("KALSHI_PRIVATE_KEY_PATH")):
        return "no API key in .env"
    if cfg.get("KALSHI_ENV", "demo") != env:
        return f"the key in .env is for {cfg.get('KALSHI_ENV', 'demo')}, not {env}"
    return Kalshi(env, cfg["KALSHI_API_KEY_ID"], cfg["KALSHI_PRIVATE_KEY_PATH"])


def cash_of(b):
    """All the cash in the account, every section, to the fraction of a cent."""
    return float(b.get("balance_dollars") or b["balance"] / 100)


def account(env):
    """Your real Kalshi account (read only): cash in every section, the part in Crypto & Commodities (the only
    cash the bot can bet), and open positions at what Kalshi values them now."""
    k = client(env)
    if isinstance(k, str):
        return {"error": k}
    b = k.balance()
    if not b or "balance" not in b:
        return {"error": k.last_error or "couldn't read the balance"}
    pos = k.positions(count_filter="position")
    total, held = cash_of(b), (b.get("portfolio_value") or 0) / 100
    return {"total": total, "crypto": bot.usable_cash(b, bot.crypto_section(k.exchange_status())),
            "positions": len((pos or {}).get("market_positions") or []), "held": held, "value": total + held,
            "updated": b.get("updated_ts")}


def paper_balance(mode):
    """The navbar's balance for a paper mode, with no Kalshi call: the simulated account's value and its change since
    its start, marked "paper" so the page says so. While there's no sim (the backtest or the run is missing), the dry
    ledger's own bankroll. `updated` is when the research outputs last changed: the sim only moves when they do."""
    s = sim()
    if s and s.get("value") is not None:
        start, value, updated = s.get("start") or 0.0, s["value"], stamp() or None
    else:
        db = sqlite3.connect(os.path.join(bot.STATE, mode + ".db"))
        start = float(bot.get_meta(db, "start") or 0)
        value = start + sum(r[0] or 0.0 for r in db.execute("SELECT pnl FROM bets WHERE status != 'open'"))
        db.close()
        updated = None
    return {"value": round(value, 4), "gain": round(value - start, 4), "pct": (value - start) / start if start else None,
            "paper": True, "now": real_now(), "updated": updated}


def balance_now(mode):
    """The navbar's balance, in the one Kalshi call it can afford every second: cash plus what Kalshi values the open
    positions at, and the change since the bot's start in dollars and as a share of it. The start already takes in money
    moved in or out (bot.rebase), so a deposit never shows as a gain. A paper mode never asks Kalshi (paper_balance)."""
    if mode.startswith("dry"):
        return paper_balance(mode)
    k = client(mode.split("-", 1)[1])
    if isinstance(k, str):
        return {"error": k}
    b = k.balance()
    if not b or "balance" not in b:
        return {"error": k.last_error or "couldn't read the balance"}
    db = sqlite3.connect(os.path.join(bot.STATE, mode + ".db"))
    start = float(bot.get_meta(db, "start") or 0)
    db.close()
    value = cash_of(b) + (b.get("portfolio_value") or 0) / 100
    return {"value": round(value, 4), "gain": round(value - start, 4), "pct": (value - start) / start if start else None,
            "now": real_now(), "updated": b.get("updated_ts")}


def pages(k, path, key, **params):
    """Every row of one of Kalshi's paged portfolio lists, or None if a page can't be read."""
    rows, cursor = [], None
    for _ in range(50):
        d = k.get(path, {**params, "limit": 200, **({"cursor": cursor} if cursor else {})}, auth=True)
        if d is None:
            return None
        rows += d.get(key) or []
        cursor = d.get("cursor")
        if not cursor:
            return rows
    return rows


def history(env, since):
    """The account's value since `since`, rebuilt from Kalshi's records (read only): [[ts, value, money in or
    out, what happened]]. It walks back from today's cash plus open positions at cost, undoing each deposit and
    withdrawal, each settlement (revenue less cost and fees) and the fees already paid on open positions.
    Events in the same minute are one point. None if anything can't be read."""
    k = client(env)
    if isinstance(k, str):
        return None
    b, pos = k.balance(), k.positions(count_filter="position")
    moves = {kind: pages(k, f"/portfolio/{kind}", kind) for kind in ("deposits", "withdrawals")}
    settled = pages(k, "/portfolio/settlements", "settlements", min_ts=int(since))
    if not b or "balance" not in b or pos is None or None in moves.values() or settled is None:
        return None
    events = []  # (ts, change in value, money in or out, what)
    for kind, sign in (("deposits", 1), ("withdrawals", -1)):
        for x in moves[kind]:
            t = x.get("finalized_ts") or x["created_ts"]
            if x.get("status") == "applied" and t > since:
                events.append((t, sign * x["amount_cents"] / 100, sign * x["amount_cents"] / 100, kind[:-1]))
    for s in settled:
        t = bot.ts(s["settled_time"])
        if t > since:
            cost = float(s.get("yes_total_cost_dollars") or 0) + float(s.get("no_total_cost_dollars") or 0)
            events.append((t, s["revenue"] / 100 - cost - float(s.get("fee_cost") or 0), 0, "won" if s["revenue"] else "lost"))
    open_ = pos.get("market_positions") or []
    for p in open_:
        if float(p.get("fees_paid_dollars") or 0) and bot.ts(p["last_updated_ts"]) > since:
            events.append((bot.ts(p["last_updated_ts"]), -float(p["fees_paid_dollars"]), 0, "bet"))
    points = {}
    for t, dv, money, what in sorted(events):
        pt = points.setdefault((int(t // 60), money != 0), [t, 0.0, 0.0, {}])
        pt[0], pt[1], pt[2] = t, pt[1] + dv, pt[2] + money
        pt[3][what] = pt[3].get(what, 0) + 1
    value = cash_of(b) + sum(float(p.get("market_exposure_dollars") or 0) for p in open_)
    out = []
    for t, dv, money, whats in (points[key] for key in sorted(points, reverse=True)):
        out.append([t, round(value, 4), round(money, 2), " · ".join(
            f"{n} {w}" if w in ("won", "lost") else f"{n} bet{'s' if n > 1 else ''} placed" if w == "bet" else w
            for w, n in whats.items())])
        value -= dv
    return [[since, round(value, 4), 0, "start"]] + out[::-1]


# ------------------------------------------------------------------ the research the bot trades
def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ the live 15-minute markets, straight from Kalshi
QUOTES_EVERY = 1       # seconds between reads of every live market's prices (one request), while the Live tab's board is open and the stream is down
CANDLES_EVERY = 20     # ... of their minute-by-minute prices, each market's price path (one request)
BOOK_EVERY = 1         # ... of the order book of the market being looked at
SERIES_EVERY = 3600    # ... of Kalshi's list of 15-minute series
RELIST_EVERY = 15      # ... of the series with no market yet this window: a window's markets don't all open at once
RELIST_FOR = 300       # ... for this long into each window (well before the bot's minute 8)
WATCHED_FOR = 30       # nobody has looked for this long: it stops reading Kalshi
FEED_TICK = 0.5        # how often the feed wakes to see what's due
GROUP_ORDER = ("crypto", "metals", "energy", "coin race", "fx", "stock index", "rates")
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"   # Kalshi's WebSocket, prod (docs.kalshi.com)
WS_PATH = "/trade-api/ws/v2"   # the handshake signs timestamp + "GET" + this path
STREAM_TIMEOUT = 10    # seconds to open the socket
STREAM_QUIET = 20      # a subscribed socket silent this long is dead: reconnect, and poll meanwhile
STREAM_RETRY = (1, 2, 5, 10, 30)   # seconds before each reconnect after a failure, then every 30 s
TRADES_KEPT = 40       # recent trades kept per market, for the trade tape


def label_of(ticker, series, group):
    """Short display name: BTC, GOLD, EURUSD, or Race·SOL for a Coin Race market."""
    return "Race·" + ticker.rsplit("-", 1)[-1] if group == "coin race" else series.replace("KX", "").replace("15M", "")


def quotes(raw):
    """A market's prices from GET /markets: the YES bid and ask, the last trade, sizes, volume and open interest."""
    return {"status": raw.get("status"), "yes_bid": num(raw.get("yes_bid_dollars")), "yes_ask": num(raw.get("yes_ask_dollars")),
            "last": num(raw.get("last_price_dollars")), "bid_size": num(raw.get("yes_bid_size_fp")),
            "ask_size": num(raw.get("yes_ask_size_fp")), "volume": num(raw.get("volume_fp")), "oi": num(raw.get("open_interest_fp"))}


def book_levels(book):
    """bot.parse_book's YES and NO bids -> the YES side's best ten bids and asks (a YES ask is a NO bid from the other side)."""
    if not book:
        return None
    return {"bids": [[p, q] for p, q in book["yes"][:10]], "asks": [[round(1 - p, 4), q] for p, q in book["no"][:10]]}


def ticker_quotes(msg):
    """A market's prices from a WebSocket "ticker" message: quotes()'s fields, named a little differently there."""
    return {"yes_bid": num(msg.get("yes_bid_dollars")), "yes_ask": num(msg.get("yes_ask_dollars")),
            "last": num(msg.get("price_dollars")), "bid_size": num(msg.get("yes_bid_size_fp")),
            "ask_size": num(msg.get("yes_ask_size_fp")), "volume": num(msg.get("volume_fp")), "oi": num(msg.get("open_interest_fp"))}


class StreamDown(Exception):
    """Why there's no live stream. The feed polls instead, and the page says why."""


def open_stream():
    """A signed, read-only connection to Kalshi's WebSocket with the prod key in .env; StreamDown if there can't be one."""
    if WS is None:
        raise StreamDown("websocket-client isn't installed (pip install websocket-client)")
    k = client("prod")
    if isinstance(k, str):
        raise StreamDown(k)
    stamp = str(int(time.time() * 1000))
    headers = {"KALSHI-ACCESS-KEY": k.key_id, "KALSHI-ACCESS-TIMESTAMP": stamp,
               "KALSHI-ACCESS-SIGNATURE": sign(k.key, stamp + "GET" + WS_PATH)}
    ws = WS.create_connection(WS_URL, header=headers, timeout=STREAM_TIMEOUT)
    ws.settimeout(1)   # recv() comes back every second, so the stream can follow a new window or see it went quiet
    return ws


class Feed:
    """Kalshi's public market data for this window's 15-minute markets, read in the background only while someone has
    the Live tab's market board open: the 15-minute series (hourly), this window's markets
    (as the window opens, then every RELIST_EVERY s for any series still without one, for RELIST_FOR s), their
    minute-by-minute prices (CANDLES_EVERY s), and the order book of the market being looked at (at most every
    BOOK_EVERY s). Every market's prices and trades stream from Kalshi's WebSocket as they change (stream_step); while
    the stream is down they're polled instead, one request every QUOTES_EVERY s. Read only: no orders. The stream signs
    in with the prod key in .env, because Kalshi's WebSocket needs a key even for public market data."""

    def __init__(self, k=None, connect=None):
        self.k = k or Kalshi("prod")
        # A feed on Kalshi itself streams through open_stream. One given its own exchange (a test's) streams only through
        # the connect it's also given, so a test can never open a real socket with the real key.
        self.connect = connect if connect is not None else (None if k else open_stream)
        self.trades = {}         # ticker -> its latest trades, newest first: [time, taker side, price on that side, contracts]
        self.ws = None           # the open socket, if any
        self.sub = frozenset()   # the markets it's subscribed to
        self.sids = set()        # Kalshi's ids for those subscriptions
        self.cmd = 0             # the last command id sent
        self.tries = 0           # failed connects in a row
        self.stream_at = 0.0     # when the socket last said anything
        self.stream_why = None   # why it isn't streaming, for the page
        self.stream_thread = None
        self.lock = threading.Lock()
        self.series = {}         # series ticker -> group
        self.window = None       # the window whose markets are listed
        self.markets = {}        # ticker -> market
        self.paths = {}          # ticker -> [[minute, yes_bid, yes_ask]]
        self.books = {}          # ticker -> (read at, levels)
        self.heartbeat = None    # when its prices were last read
        self.due = {"series": 0.0, "list": 0.0, "quotes": 0.0, "candles": 0.0}
        self.watched = 0.0       # when someone last asked
        self.thread = None

    def list_window(self, window, only=None):
        """{ticker: market} for this window's markets in every 15-minute series (or just `only`); {} if none could be listed.

        Asked for by close time, the way bot.Bot.listed asks and for the same reason: `status=open` matched nothing
        for about seven hours on Oct 24, answering 200 with an empty list. A window's market is the one closing at
        its end, so the close time finds it whether or not that filter is working."""
        series = sorted(self.series if only is None else only)
        close = int(window) + 900
        with ThreadPoolExecutor(max_workers=8) as pool:
            listed = list(pool.map(lambda s: self.k.markets(series_ticker=s, min_close_ts=close - 1,
                                                            max_close_ts=close + 1, limit=50), series))
        out = {}
        for s, d in zip(series, listed):
            for raw in (d or {}).get("markets") or []:
                if abs(bot.ts(raw["open_time"]) - window) < 1:
                    out[raw["ticker"]] = {"ticker": raw["ticker"], "series": s, "group": self.series[s],
                                          "label": label_of(raw["ticker"], s, self.series[s]), "open": raw["open_time"],
                                          "close": raw["close_time"], "strike": num(raw.get("floor_strike")), **quotes(raw)}
        return out

    def step(self, now):
        """One pass: whatever is due."""
        if now - self.due["series"] >= SERIES_EVERY:
            d = self.k.series()
            if d:
                self.series = {s["ticker"]: bot.group_of(s["ticker"], s.get("category") or "") for s in d.get("series") or []
                               if s.get("frequency") == "fifteen_min" and not s["ticker"].endswith("TEST")}
                self.due["series"] = now
        window = now - now % 900
        if window != self.window and self.series:
            listed = self.list_window(window)
            if listed:   # nothing listed (a window not up yet, or Kalshi unreachable): try again next pass
                with self.lock:
                    self.window, self.markets, self.paths, self.books, self.trades = window, listed, {}, {}, {}
                self.due["quotes"] = self.due["candles"] = 0.0
                self.due["list"] = now
        elif window == self.window and now - window < RELIST_FOR and now - self.due["list"] >= RELIST_EVERY:
            self.due["list"] = now
            missing = set(self.series) - {m["series"] for m in self.markets.values()}
            more = self.list_window(window, missing) if missing else {}
            if more:   # markets that opened after the window was first listed
                with self.lock:
                    self.markets.update({t: m for t, m in more.items() if t not in self.markets})
                self.due["quotes"] = self.due["candles"] = 0.0
        tickers = sorted(self.markets)
        if tickers and not self.streaming(now) and now - self.due["quotes"] >= QUOTES_EVERY:   # the stream is fresher
            self.due["quotes"] = now
            got = [self.k.markets(tickers=",".join(tickers[i:i + 50]), limit=100) for i in range(0, len(tickers), 50)]
            with self.lock:
                for d in got:
                    for raw in (d or {}).get("markets") or []:
                        if raw.get("ticker") in self.markets:
                            self.markets[raw["ticker"]].update(quotes(raw))
                if any(d is not None for d in got):
                    self.heartbeat = now
        if tickers and now - self.due["candles"] >= CANDLES_EVERY:
            self.due["candles"] = now
            history = bot.minute_quotes(self.k.candlesticks(tickers, self.window, min(now, self.window + 900)), self.window)
            if history is not None:
                with self.lock:
                    self.paths = {t: [[k, b, a] for k, (b, a) in sorted(q.items())] for t, q in history.items()}

    def book(self, ticker, now):
        """The order book of one of this window's markets, read at most every BOOK_EVERY s (the last good one if a read
        fails); None for any other ticker, which is never looked up."""
        if ticker not in self.markets:
            return None
        at, old = self.books.get(ticker, (None, None))
        if at is not None and now - at < BOOK_EVERY:
            return old
        levels = book_levels(bot.parse_book(self.k.orderbook(ticker))) or old
        with self.lock:
            self.books[ticker] = (now, levels)
        return levels

    def snapshot(self, now, book=None):
        """The live markets as /api/research/live sends them (the Live tab's board), with the order book of `book` (a ticker) if it's one of them.
        Asking keeps the feed running. None until its first prices are in."""
        self.watched = now
        self.start()
        levels = self.book(book, now) if book else None
        with self.lock:
            if self.heartbeat is None:
                return None
            live = self.streaming(now)
            beat = max(self.heartbeat, self.stream_at) if live else self.heartbeat   # a live socket is up to date
            order = lambda m: (GROUP_ORDER.index(m["group"]) if m["group"] in GROUP_ORDER else len(GROUP_ORDER), m["label"])
            ms = []
            for m in sorted(self.markets.values(), key=order):
                side, price = bot.favourite(m.get("yes_bid"), m.get("yes_ask"))
                shown = m["ticker"] == book
                ms.append({**m, "favSide": side, "favPrice": price, "path": self.paths.get(m["ticker"], []),
                           "book": levels if shown else None, "trades": list(self.trades.get(m["ticker"], ())) if shown else None})
            return {"heartbeat": bot.iso(beat), "source": "stream" if live else "poll", "streamWhy": None if live else self.stream_why,
                    "band": [bot.LO, bot.HI],
                    "groups": sorted({m["group"] for m in ms}, key=lambda g: GROUP_ORDER.index(g) if g in GROUP_ORDER else 99),
                    "markets": ms}

    # ------------------------------------------------------------------ the live stream
    def streaming(self, now):
        """The socket is up, subscribed, and has said something within STREAM_QUIET s."""
        return self.ws is not None and bool(self.sids) and now - self.stream_at < STREAM_QUIET

    def stream_step(self, now):
        """One turn of the live stream: connect while someone is watching, keep it subscribed to this window's markets'
        prices and trades, and take one message. Returns the seconds to wait before the next turn (0: go straight on)."""
        if now - self.watched >= WATCHED_FOR or not self.markets:
            self.drop(None)   # nobody looking, or nothing to look at: no socket
            return FEED_TICK
        if self.ws is None:
            try:
                ws = self.connect()
            except Exception as e:
                self.tries += 1
                self.stream_why = f"no live stream ({e}), polling instead"
                return STREAM_RETRY[min(self.tries, len(STREAM_RETRY)) - 1]
            self.ws, self.tries, self.stream_at, self.sub, self.sids = ws, 0, now, frozenset(), set()
        try:
            self.sync()
            raw = self.ws.recv()
        except Exception as e:
            if WS is not None and isinstance(e, WS.WebSocketTimeoutException):   # nothing this second
                if now - self.stream_at < STREAM_QUIET:
                    return 0
                self.drop("Kalshi's stream went quiet: reconnecting, polling meanwhile")
            else:
                self.drop(f"Kalshi's stream dropped ({e!r}): reconnecting, polling meanwhile")
            return STREAM_RETRY[0]
        self.on_message(raw, time.time())
        return 0

    def command(self, cmd, params):
        self.cmd += 1
        self.ws.send(json.dumps({"id": self.cmd, "cmd": cmd, "params": params}))

    def sync(self):
        """Subscribe to this window's markets' ticker and trade channels, swapping out the last window's."""
        want = frozenset(self.markets)
        if want == self.sub:
            return
        if self.sids:
            self.command("unsubscribe", {"sids": sorted(self.sids)})
            self.sids = set()
        self.command("subscribe", {"channels": ["ticker", "trade"], "market_tickers": sorted(want)})
        self.sub = want

    def on_message(self, raw, now):
        """A ticker message updates its market's prices; a trade goes on its market's tape. Anything else that isn't
        an acknowledgement or an error is ignored, as are markets that aren't this window's."""
        try:
            m = json.loads(raw)
        except ValueError:
            return
        if not isinstance(m, dict):
            return
        self.stream_at = now
        kind, body = m.get("type"), m.get("msg") or {}
        if kind == "subscribed":
            self.sids.add(body.get("sid"))
            self.stream_why = None
        elif kind == "error":
            self.stream_why = f"Kalshi's stream said: {body.get('msg') or body}"
        elif kind in ("ticker", "trade"):
            t = body.get("market_ticker")
            with self.lock:
                if t not in self.markets:
                    return
                if kind == "ticker":
                    self.markets[t].update({k: v for k, v in ticker_quotes(body).items() if v is not None})
                    self.heartbeat = now
                else:
                    side = body.get("taker_side")
                    self.trades.setdefault(t, deque(maxlen=TRADES_KEPT)).appendleft(
                        [(body.get("ts_ms") or now * 1000) / 1000, side, num(body.get(f"{side}_price_dollars")), num(body.get("count_fp"))])

    def drop(self, why):
        """Close the socket, if there is one, and say why the feed isn't streaming (None: nobody's watching)."""
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws, self.sub, self.sids, self.stream_why = None, frozenset(), set(), why

    def stream_run(self, passes=float("inf")):
        """The stream's thread: one stream_step after another, waiting when it says to. An error is printed, the socket
        dropped, and the next turn reconnects. passes: how many turns (forever, unless a test says otherwise)."""
        while passes > 0:
            passes -= 1
            try:
                wait = self.stream_step(time.time())
            except Exception as e:
                print(f"{bot.iso(time.time())} live stream: {e!r}", flush=True)
                self.drop(f"live stream error ({e!r}): reconnecting, polling meanwhile")
                wait = STREAM_RETRY[0]
            if wait:
                time.sleep(wait)

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.run, daemon=True, name="kalshi-feed")
            self.thread.start()
        if self.stream_thread is None and self.connect is not None:
            self.stream_thread = threading.Thread(target=self.stream_run, daemon=True, name="kalshi-stream")
            self.stream_thread.start()

    def run(self, passes=float("inf")):
        """Wake every FEED_TICK s and step while someone has looked within WATCHED_FOR s. A bad answer from Kalshi is
        printed and the feed carries on. passes: how many wakes (forever, unless a test says otherwise)."""
        while passes > 0:
            passes -= 1
            now = time.time()
            if now - self.watched < WATCHED_FOR:
                try:
                    self.step(now)
                except Exception as e:
                    print(f"{bot.iso(now)} live feed: {e!r}", flush=True)
            time.sleep(FEED_TICK)


FEED = Feed()


def live(book=None):
    """The live 15-minute markets from Kalshi, with `book`'s order book; None until the feed has prices."""
    return FEED.snapshot(time.time(), book)


RUN_STATS = ("start", "final", "ret", "broke", "bets", "wins", "winRate", "need", "perBet", "maxDD", "worstWindow", "worstWindowPct", "worstDay",
             "losingDays", "days", "byGroup", "byBand", "bySeries", "periods", "exit", "liquidity", "liveFit",
             "worst24h", "worst24hPct", "worst24hAt", "floorHit")   # floorHit: when the $700 stop would have fired


def has_runs(d):
    return isinstance(d, dict) and isinstance((d.get("scenarios") or {}).get("live"), dict)


def thin(curve):
    return (curve or [])[::REPLAY_STEP]


def runs(d):
    """{fills: {start: {id: run}}}: every account under each fill assumption ("live", "backtest"), started Jul 18, and
    again Dec 10 and Aug 24 where the backtest has those starts, with its stats, its bets split by group, price and market,
    and its bankroll every REPLAY_STEP hours (None before its start and once it's broke)."""
    starts = d.get("starts") or {}
    full = lambda r: {**{k: r.get(k) for k in RUN_STATS}, "curve": thin(r.get("curve"))}
    out = {}
    for fills, rows in d["scenarios"].items():
        out[fills] = {"jul18": {sid: full(r) for sid, r in rows.items() if isinstance(r, dict)}}
        for start in ("dec10", "aug24"):
            if start == "aug24" or isinstance(starts.get(start), dict):
                out[fills][start] = {sid: full(r) for sid, r in ((starts.get(start) or {}).get(fills) or {}).items() if isinstance(r, dict)}
    return out


def replay():
    """Every account replayed from the first 15-minute market, Dec 10, 2025, to the end of the history (strategies.json, from
    strategies_backtest.py), trading every window with no pauses: its rules and periods, its runs (runs()), and each
    rule's edge. None if the backtest hasn't been run."""
    d = read_json(os.path.join(RESEARCH, "strategies.json"))
    if not has_runs(d):
        return None
    return {"t0": d.get("t0"), "hours": d.get("hours"), "step": REPLAY_STEP, "start": d.get("start"), "periods": d.get("periods"),
            "strategies": [x for x in d.get("strategies") or [] if isinstance(x, dict) and x.get("id") in d["scenarios"]["live"]],
            "runs": runs(d),
            # each rule alone at $10 a bet, never broke, under both fill assumptions: its running profit every REPLAY_STEP hours
            "edge": {sc: {sid: {**e, "curve": thin(e.get("curve"))} for sid, e in rows.items()}
                     for sc, rows in (d.get("edge") or {}).items()} or None}


def stamp():
    """When the research outputs last changed: /api/research/stamp, so a reader fetches the study again only when this moves."""
    return max((os.path.getmtime(os.path.join(RESEARCH, f)) for f in STUDY_FILES if os.path.exists(os.path.join(RESEARCH, f))), default=0)


def study():
    """Everything /api/research serves, which changes only when the research is run again: each strategy replayed from
    Jul 18 and each rule's edge (strategies.json), the calibration and Kelly table (key_stats.json), halts, selling early,
    warning signs and loss clusters (findings.json), every market group (all_markets.json), bet sizing (sizing.json),
    the price-floor test: the live rule with its lowest price at 90-95c (price_floor.json), and how the live bot's losses
    happened with the skip rule they suggested, backtested (live_losses.json)."""
    key = read_json(os.path.join(RESEARCH, "key_stats.json")) or {}
    built = read_json(os.path.join(RESEARCH, "dashboard", "src", "generated", "dashboard.json")) or {}
    groups = read_json(os.path.join(RESEARCH, "all_markets.json")) or {}
    return {"stamp": stamp(), "replay": replay(), "findings": read_json(os.path.join(RESEARCH, "findings.json")), "key": key or None,
            "calibration": key.get("calibration") or built.get("calibration"),
            "groups": {k: groups.get(k) for k in ("groups", "calibration", "rules", "coLosses", "spreads", "slip")} if groups else None,
            "sizing": read_json(os.path.join(RESEARCH, "sizing.json")), "floor": read_json(os.path.join(RESEARCH, "price_floor.json")),
            "losses": read_json(os.path.join(RESEARCH, "live_losses.json"))}


def research_live(book=None):
    """The live markets, with `book`'s order book, and the study's stamp so the page knows when to fetch the study again."""
    return {"now": real_now(), "stamp": stamp(), "live": live(book)}


SIM_RUN = "mine4liq1k"   # the simulated $1,000 account: replayed from Dec 10, 2025 on real prices and real book depth


def sim():
    """The simulated account a paper mode's page leads with: the SIM_RUN account out of the study's replay (the same
    cached read /api/research serves), started Dec 10, 2025. Its start and value now, the stats the page may show, and
    its bankroll every `step` hours from the replay's t0 (the curve runs() already thinned, None before its start).
    None while the backtest, or that run, is missing."""
    d = cached(("study", stamp()), 3600, study)
    rep = (d or {}).get("replay")
    run = ((((rep or {}).get("runs") or {}).get("live") or {}).get("dec10") or {}).get(SIM_RUN)
    if not isinstance(run, dict):
        return None
    # winRate and need come straight from the replay: the page cannot work out a break-even from bets and wins,
    # because it is the average cost of a contract.
    return {"start": run.get("start"), "value": run.get("final"), "ret": run.get("ret"), "bets": run.get("bets"),
            "wins": run.get("wins"), "maxDD": run.get("maxDD"), "curve": run.get("curve"),
            "winRate": run.get("winRate"), "need": run.get("need"),
            "t0": rep.get("t0"), "hours": rep.get("hours"), "step": rep.get("step"),
            # when each asset class and each market had its first bet, for the Tape page's long chart (Nov 8)
            "groups": first_bets(run.get("byGroup")), "markets": first_bets(run.get("bySeries"))}


def first_bets(rows):
    """[{key, first}] for each row of a run's byGroup or bySeries that names itself and has a first bet, oldest first."""
    return sorted(({"key": r["key"], "first": r["first"]} for r in rows or [] if isinstance(r, dict)
                   and isinstance(r.get("key"), str) and isinstance(r.get("first"), str) and r["first"]),
                  key=lambda r: r["first"])


ORDERS_SHOWN = 30      # the latest buy orders the Live tab lists, each with what it asked for and what filled
BUY_ORDERS = "request LIKE '%\"count\"%'"   # the orders table also holds cancels, whose request is {"cancel": order id}
# The bands of the price paid, in whole cents, the live bets are split by to sit beside the price-floor test:
# the same as research/kalshi_15min/price_floor.py's BANDS.
PRICE_BANDS = ((90, 91), (92, 94), (95, 97), (98, 99))


def order_row(r):
    """One buy order as the Live tab lists it: the favorite it bought (a bid buys YES at its price; an ask sells YES,
    which buys NO at 1 minus it), the contracts asked for and filled, and why it failed if it did. filled is None when
    Kalshi refused the order or its answer never came back."""
    req, status = json.loads(r["request"]), r["http_status"]
    try:
        resp = json.loads(r["response"])
    except (TypeError, ValueError):
        resp = None
    side, price = {"bid": "yes", "ask": "no"}.get(req.get("side")), num(req.get("price"))
    ok = status is not None and 200 <= status < 300 and isinstance(resp, dict)
    err = resp.get("error") if isinstance(resp, dict) else None
    why = None if ok else "no answer from Kalshi" if status is None else (err.get("message") if isinstance(err, dict) else f"HTTP {status}")
    return {"ts": r["ts"], "ticker": r["ticker"], "series": r["ticker"].split("-")[0], "side": side,
            "price": round(price if side == "yes" else 1 - price, 4) if side and price is not None else None,
            "asked": num(req.get("count")), "filled": (num(resp.get("fill_count")) or 0.0) if ok else None, "error": why}


def fill_counts(orders):
    """Buy orders' contracts asked for and filled, and how many got none (refused, unanswered or nothing filled)."""
    return {"orders": len(orders), "asked": sum(o["asked"] or 0 for o in orders), "filled": sum(o["filled"] or 0 for o in orders),
            "none": sum(not o["filled"] for o in orders)}


# The Live tab's fill-rate chart: is live fast entry filling more than before it? The time the bot wasn't trading is
# left out of it (fill_off).
FAST_LIVE = 1792011600   # the first window with live fast entry: Oct 14, 2026, 21:00 UTC (the bot restarted at 21:04 UTC)
FILL_CHART_DAYS = 7      # how far back the chart reaches
FILL_BEFORE_DAYS = 4     # the span of its "before fast entry" figures


def fill_windows(orders):
    """Buy orders by their 15-minute window (ts - ts % 900), oldest first, only the windows with an order:
    [window, orders, asked, filled, none], each window's counted as fill_counts counts them."""
    by = {}
    for o in orders:
        by.setdefault(o["ts"] - o["ts"] % 900, []).append(o)
    out = []
    for w in sorted(by):
        c = fill_counts(by[w])
        out.append([w, c["orders"], c["asked"], c["filled"], c["none"]])
    return out


def fill_off(rows, decisions):
    """The stretches the fill-rate chart leaves out: between each two of fill_windows' rows, the
    windows the bot wasn't trading in, those it logged no decision in (it wasn't running, or Kalshi listed nothing) or a
    'halted' one. One [from, to, kind] a gap with any, oldest first: the first such window's start to the last one's end
    (quiet windows between them inside it), "halted" if a halt was logged in it, else "off". decisions: (ts, action)."""
    halted = {}   # window -> whether a 'halted' decision was logged in it
    for ts, action in decisions:
        w = ts - ts % 900
        halted[w] = halted.get(w, False) or action == "halted"
    out = []
    for (a, *_), (b, *_) in zip(rows, rows[1:]):
        off = [w for w in range(int(a) + 900, int(b), 900) if halted.get(w, True)]
        if off:
            out.append([off[0], off[-1] + 900, "halted" if any(halted.get(w) for w in off) else "off"])
    return out


# Order sizes, by the top of each bucket in contracts asked for: 1-5, 6-15, ... 51-100, then 101+.
SIZE_EDGES = (5, 15, 25, 35, 50, 100)


def fill_sizes(orders):
    """fill_counts by order size, smallest first, for the buckets that have an order: whether bigger orders fill less,
    which is the sign the bot is outgrowing what the books offer at 90-99c. Orders Kalshi refused or never answered
    (filled None) say nothing about the book, so they're left out, as is an order with no size."""
    buckets = {}
    for o in orders:
        if o["filled"] is None or not o["asked"]:
            continue
        i = next((i for i, hi in enumerate(SIZE_EDGES) if o["asked"] <= hi), len(SIZE_EDGES))
        buckets.setdefault(i, []).append(o)
    out = []
    for i in sorted(buckets):
        lo, hi = (SIZE_EDGES[i - 1] + 1 if i else 1), (SIZE_EDGES[i] if i < len(SIZE_EDGES) else None)
        out.append({"label": f"{lo}–{hi}" if hi else f"{lo}+", "lo": lo, "hi": hi, **fill_counts(buckets[i])})
    return out


def by_price(settled, seen=None):
    """The settled bets by price band, low to high, and only the bands with a bet: under 90c first, then each of
    PRICE_BANDS. A bet's price is the ask it saw when it decided (seen: ticker -> the decision's price), as the backtest
    bands each bet by the ask at minute 8; an order often fills below it, so the price paid would move bets down a band.
    Without a decision for it, the price paid. Each band's bets, wins, profit and cost, as bySeries counts them."""
    seen = seen or {}
    bands = [("under-90", "under 90¢", 0, 89)] + [(f"{lo}-{hi}", f"{lo}–{hi}¢", lo, hi) for lo, hi in PRICE_BANDS]
    rows = {key: {"key": key, "label": label, "n": 0, "wins": 0, "pnl": 0.0, "staked": 0.0} for key, label, _, _ in bands}
    for b in settled:
        cents = int((seen.get(b["ticker"]) or b["price"]) * 100 + 1e-6)   # whole cents: 0.9199999999 is 92c, 0.9075 is 90c
        key = next((key for key, _, lo, hi in bands if lo <= cents <= hi), None)
        if key:   # a price past every band (shouldn't happen) is left out
            r = rows[key]
            r["n"] += 1
            r["wins"] += b["status"] == "won"
            r["pnl"] += b["pnl"]
            r["staked"] += b["cost"]
    return [r for r in rows.values() if r["n"]]


def state(mode):
    live, env = mode.startswith("live"), mode.split("-", 1)[1]
    db = sqlite3.connect(os.path.join(bot.STATE, mode + ".db"))
    db.row_factory = sqlite3.Row
    start = float(bot.get_meta(db, "start") or 0)
    bets = [dict(r) for r in db.execute("SELECT * FROM bets ORDER BY placed_ts")]
    settled = sorted((b for b in bets if b["status"] != "open"), key=lambda b: b["settled_ts"])
    open_ = [b for b in bets if b["status"] == "open"]

    bankroll = start + sum(b["pnl"] for b in settled)
    quotes = cached(("marks", env, tuple(b["ticker"] for b in open_)), 10,
                    lambda: marks(env, [b["ticker"] for b in open_])) if open_ else {}
    unrealized = 0.0
    for b in open_:
        bid, ask = quotes.get(b["ticker"], (None, None))
        b["mark"] = bid if b["side"] == "yes" else (None if ask is None else round(1 - ask, 4))
        b["unrealized"] = None if b["mark"] is None else b["contracts"] * b["mark"] - b["cost"] - b["fee"]
        unrealized += b["unrealized"] or 0.0

    curve, bal, peak, drop = [], start, start, 0.0
    if bets:
        curve.append([bets[0]["placed_ts"], start])
    for b in settled:
        bal += b["pnl"]
        peak, drop = max(peak, bal), max(drop, 1 - bal / peak if peak else 0.0)
        curve.append([b["settled_ts"], round(bal, 2)])

    wins = sum(b["status"] == "won" for b in settled)
    by_series = {}
    for b in settled:
        s = by_series.setdefault(b["series"], {"series": b["series"], "n": 0, "wins": 0, "pnl": 0.0, "staked": 0.0})
        s["n"] += 1
        s["wins"] += b["status"] == "won"
        s["pnl"] += b["pnl"]
        s["staked"] += b["cost"]
    now = time.time()
    day_ago = now - 86400
    hour_ago = time.time() - 3600
    order_q = f"SELECT ts, ticker, request, http_status, response FROM orders WHERE {BUY_ORDERS}"
    orders = [order_row(r) for r in db.execute(order_q + " ORDER BY ts DESC, id DESC LIMIT ?", (ORDERS_SHOWN,))]
    bet_of = {b["ticker"]: b for b in bets}
    # what the book offered each listed order at minute 8, from its market's shadow rows (one a kind and market): the
    # 'fast' row's extra is the contracts at its price, the 'limitup' row's those within 1¢ over it; none before the
    # book reads began, nor in a ledger from before the shadow table
    reads = {(r["kind"], r["ticker"]): r["extra"] for r in db.execute(
        f"SELECT kind, ticker, extra FROM shadow WHERE kind IN ('fast', 'limitup') AND ticker IN ({', '.join('?' * len(orders))})",
        [o["ticker"] for o in orders])} if has_table(db, "shadow") else {}
    for o in orders:   # how its contracts did: the bet it made, by market (one buy order per market); none if nothing filled
        b = bet_of.get(o["ticker"]) or {}
        o.update(result=b.get("status"), pnl=b.get("pnl"), close_ts=b.get("close_ts"),
                 atAsk=reads.get(("fast", o["ticker"])), plusOne=reads.get(("limitup", o["ticker"])))
    every = [order_row(r) for r in db.execute(order_q + " ORDER BY ts")]   # every buy order, oldest first
    today = [o for o in every if o["ts"] >= day_ago]
    this_hour = [o for o in every if o["ts"] >= hour_ago]   # all of them, not only the ORDERS_SHOWN listed
    week = now - FILL_CHART_DAYS * 86400   # the fill-rate chart's reach: its windows, and the decisions it's off by
    windows = fill_windows([o for o in every if o["ts"] >= week])
    heartbeat = bot.get_meta(db, "heartbeat")
    kalshi = cached(("account", env), ACCOUNT_EVERY, lambda: account(env)) if live else None
    since = bets[0]["placed_ts"] - 60 if bets else None   # the real account's chart starts with the bot's first bet
    kalshi_curve = cached(("history", env, since), HISTORY_EVERY, lambda: history(env, since)) if live and since else None
    ck = clock()   # one reading for both, so "now" and the clock the page is told about agree
    out = {
        "mode": mode, "modes": modes(), "live": live, "env": env, "now": time.time() + (ck["offset"] or 0.0), "clock": ck,
        "heartbeat": float(heartbeat) if heartbeat else None,
        # the real-money ledger as the bot from before Oct 12 left it (no shadow table yet): the Live tab asks for a restart
        "restartBot": mode == "live-prod" and not has_table(db, "shadow"),
        "halt": bot.halt_info(),
        "blackout": next(({"what": w, "from": bot.ts(a), "to": bot.ts(b), "active": bot.ts(a) <= time.time() < bot.ts(b)}
                          for a, b, w in bot.BLACKOUTS if bot.ts(b) > time.time()), None),
        "start": start, "bankroll": bankroll, "unrealized": unrealized,
        "haltBase": float(bot.get_meta(db, "halt_base") or start),  # the half-the-start floor is half of this
        "limits": {"betPct": bot.CAP_PCT, "windowPct": bot.WINDOW_CAP,
                   "ordersPerWindow": bot.MAX_ORDERS_PER_WINDOW, "ordersPerDay": bot.MAX_ORDERS_PER_DAY,
                   "minCash": bot.MIN_BET / bot.CAP_PCT, "dayDrop": bot.HALT_DAY_DROP, "halfStart": bot.HALT_DEPOSIT,
                   "windowLosses": bot.HALT_WINDOW_LOSSES, "settleLag": bot.HALT_SETTLE_LAG, "persist": bot.HALT_PERSIST,
                   "orderErrors": bot.MAX_ORDER_ERRORS,
                   # the strategy itself, for the Live tab's "How it trades"
                   "minute": bot.MINUTE, "lo": bot.LO, "hi": bot.HI, "limitUp": bot.LIMIT_UP, "shadowUp": bot.SHADOW_UP,
                   "grace": bot.GRACE,
                   "spreadMax": bot.SPREAD_MAX,
                   "lateMid": bot.LATE_MID, "jump": bot.JUMP, "orderDeadline": bot.ORDER_DEADLINE,
                   "bookMaxAge": bot.BOOK_MAX_AGE, "restingEvery": bot.RESTING_EVERY,
                   "orderConnect": ORDER_TIMEOUT[0], "orderAnswer": ORDER_TIMEOUT[1]},
        "groups": list(bot.EDGE_GROUPS),
        "openCost": sum(b["cost"] + b["fee"] for b in open_),
        "wins": wins, "losses": len(settled) - wins,
        "need": sum(b["cost"] + b["fee"] for b in settled) / sum(b["contracts"] for b in settled) if settled else None,
        # ... and the share of settled contracts that won: per contract too, so the two compare (a per-bet rate doesn't)
        "winShare": sum(b["contracts"] for b in settled if b["status"] == "won") / sum(b["contracts"] for b in settled) if settled else None,
        "fees": sum(b["fee"] for b in bets), "maxDrop": drop,
        "day": sum(b["pnl"] for b in settled if b["settled_ts"] >= day_ago),
        "dayBets": sum(b["placed_ts"] >= day_ago for b in bets),
        # what the bets cost (price x contracts; the fees are apart): every one, the last 24 hours', and the settled
        # ones with what they made, so the page can say the profit per $1 staked
        "staked": {"all": round(sum(b["cost"] for b in bets), 2), "bets": len(bets),
                   "since": min((b["placed_ts"] for b in bets), default=None),
                   "day": round(sum(b["cost"] for b in bets if b["placed_ts"] >= day_ago), 2),
                   "settled": round(sum(b["cost"] for b in settled), 2), "profit": round(sum(b["pnl"] for b in settled), 2)},
        "nextBet": bot.stake_for(bankroll, 1),
        "curve": curve,
        "openBets": open_,
        "recentBets": settled[::-1][:150],
        "bySeries": sorted(by_series.values(), key=lambda s: s["pnl"]),
        "byPrice": by_price(settled, dict(db.execute("SELECT ticker, fav_price FROM decisions WHERE action='bet'"))),   # beside the price-floor test
        "decisions": [dict(r) for r in db.execute("SELECT ts, ticker, series, fav_side, fav_price, action, reason"
                                                  " FROM decisions ORDER BY ts DESC, id DESC LIMIT 200")],
        "orders": orders,
        # the last 24 hours' buy orders: contracts asked for and filled, and how many orders got none; then every one, since the first
        "fills": fill_counts(today),
        "fillsAll": {**fill_counts(every), "since": every[0]["ts"] if every else None},
        "fillsHour": fill_counts(this_hour),   # ... and the last hour's, the same way
        "fillsBySize": fill_sizes(every),   # ... and every one by its size: do bigger orders fill less?
        # the fill-rate chart: the last FILL_CHART_DAYS of buy orders by window, the stretches between them the bot wasn't
        # trading in (from the same days' decisions), and fast entry's go-live with the FILL_BEFORE_DAYS before it and
        # everything since, each counted as fill_counts counts them
        "fillWindows": windows,
        "fillOff": fill_off(windows, db.execute("SELECT ts, action FROM decisions WHERE ts >= ?", (week,))),
        "fillsFast": {"live": FAST_LIVE, "before": fill_counts([o for o in every if FAST_LIVE - FILL_BEFORE_DAYS * 86400 <= o["ts"] < FAST_LIVE]),
                      "after": fill_counts([o for o in every if o["ts"] >= FAST_LIVE])},
        "errors": [dict(r) for r in db.execute("SELECT ts, ticker, http_status, response FROM orders"
                                               " WHERE http_status IS NULL OR http_status NOT IN (200, 201)"
                                               " ORDER BY ts DESC LIMIT 30")],
        "kalshi": kalshi,
        # Your real account's value over time, ending at its value now; the page draws this instead of the bot's own curve.
        "kalshiCurve": kalshi_curve + [[time.time(), round(kalshi["value"], 4), 0, "now"]] if kalshi_curve and "value" in kalshi else None,
    }
    if mode.startswith("dry"):   # a paper mode: the real wallet stays off the page, the simulated account stands in
        del out["kalshi"], out["kalshiCurve"]
        out["sim"] = sim()
    return out


# ------------------------------------------------------------------ the Live Research tab: the +1¢ limit, live and on paper
LIVE_RESEARCH_EVERY = 2       # seconds between reads of the ledger for the Live Research tab (the page polls every 2)
LATENCY_EVERY = 10            # ... and for the Latency tab (it polls every 15 s; new orders come once a window)
LIVE_RESEARCH_TARGET = 1000   # buy orders with the live +1¢ limit before it says whether the extra cent pays
# Nov 27, 2026, 08:00 UTC: 6 weeks from the server go-live (Oct 16, 05:13:55 UTC), the planned length of the live test
# (its clock restarted at the move to the server). The paper +1¢'s verdict waits until then, however many orders it
# has measured (paper_verdict()).
SHADOW_UNTIL = 1795766400
FAST_SHADOW_TARGET = 300      # real orders paired with the paper fast entry before it says which fills more (~2 days, ~140 a day)
LIVE_ORDERS_SHOWN = 50        # the experiment's latest buy orders it lists (and the paper ones' latest rows)
# What reading a research file of another shape than expected raises: a key missing, a list for a dict, no such row.
SHAPE_ERRORS = (AttributeError, LookupError, TypeError, ValueError, StopIteration)


def read_only(mode):
    """A mode's ledger, opened so SQLite can't write to it: nothing in or beside it is ever created or changed (no
    -journal, -wal or -shm file), however often the tab reads it while the bot is writing to it."""
    path = os.path.abspath(os.path.join(bot.STATE, mode + ".db"))
    db = sqlite3.connect(pathlib.Path(path).as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def has_table(db, name):
    """Whether a ledger has the table yet: the bot adds its newer ones (fills, shadow) when it next starts."""
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def accepted_orders(db):
    """Every buy order Kalshi accepted, oldest first, as order_row reads it (its price is the limit on the side it
    bought), with Kalshi's ID for it, which its fills carry. Orders Kalshi refused, or whose answer never came back, are
    left out of everything: what they did isn't known."""
    out, q = [], f"SELECT ts, ticker, request, http_status, response FROM orders WHERE {BUY_ORDERS} ORDER BY ts, id"
    for r in db.execute(q):
        o = order_row(r)
        if o["filled"] is not None:
            out.append({**o, "orderId": json.loads(r["response"]).get("order_id")})
    return out


def returns(settled):
    """P&L and money staked over settled (window, P&L, staked) items, as ¢ per $10 staked with its standard error
    clustered by window: the bets in one 15-minute window share their luck (the coins move together), so each window
    counts as one draw. With each window's sums P_w and S_w and R = ΣP/ΣS, se = 1000·sqrt(G/(G−1)·Σ(P_w − R·S_w)²)/ΣS
    over the G windows. perTen is None with nothing staked, se with fewer than two settled windows."""
    windows = {}
    for w, pnl, staked in settled:
        p, s = windows.get(w, (0.0, 0.0))
        windows[w] = (p + pnl, s + staked)
    P, S, G = sum(p for p, _ in windows.values()), sum(s for _, s in windows.values()), len(windows)
    se = None
    if S and G > 1:
        R = P / S
        se = 1000 * math.sqrt(G / (G - 1) * sum((p - R * s) ** 2 for p, s in windows.values())) / S
    return {"pnl": P, "staked": S, "perTen": 1000 * P / S if S else None, "se": se}


def arm(orders, seen, bets):
    """One arm of the experiment, the buy orders before the +1¢ limit or with it: the contracts asked for and filled,
    the orders that got none, some or all of theirs, the average ask it saw (seen: ticker -> the decision's price) and
    price it paid, and how their settled bets did (staked: what the contracts cost, fees aside)."""
    asked, filled = sum(o["asked"] or 0 for o in orders), sum(o["filled"] for o in orders)
    none = sum(not o["filled"] for o in orders)
    full = sum(o["filled"] > 0 and o["filled"] + 1e-9 >= (o["asked"] or 0) for o in orders)
    sees = [seen[o["ticker"]] for o in orders if seen.get(o["ticker"]) is not None]
    # the bets their contracts made, one a market
    made = {o["ticker"]: bets[o["ticker"]] for o in orders if o["filled"] and o["ticker"] in bets}.values()
    settled = [b for b in made if b["status"] in ("won", "lost")]
    return {"orders": len(orders), "asked": asked, "filled": filled, "fillShare": filled / asked if asked else None,
            "none": none, "partial": len(orders) - none - full, "full": full,
            "avgSeen": sum(sees) / len(sees) if sees else None,
            "avgPaid": sum(b["cost"] for b in made) / sum(b["contracts"] for b in made) if made else None,
            "settled": sum(b["contracts"] for b in settled),
            "won": sum(b["contracts"] for b in settled if b["status"] == "won"),
            **returns((b["window_open"], b["pnl"], b["cost"]) for b in settled)}


def group(fills):
    """One side of the split, the during orders' fills at or under the ask it saw ("base") or over it ("extra"): the
    orders with any contracts in it, the contracts, their average price and fees, the break-even (the price plus the
    fee per contract: a contract pays $1 if it wins, so that's the win rate it needs), the win rate, and how the
    settled fills did, each by its own price and fee: won, count·(1 − price) − fee; lost, −count·price − fee. The paper
    +1¢'s extra contracts are a group too (shadow(): one "fill" a row)."""
    n, fee = sum(f["count"] for f in fills), sum(f["fee"] for f in fills)
    price = sum(f["count"] * f["price"] for f in fills) / n if n else None
    settled = [f for f in fills if f["status"] in ("won", "lost")]
    done, won = sum(f["count"] for f in settled), sum(f["count"] for f in settled if f["status"] == "won")
    pnl = lambda f: (f["count"] if f["status"] == "won" else 0) - f["count"] * f["price"] - f["fee"]   # payout - cost - fee
    return {"orders": len({f["order"] for f in fills if f["count"]}), "contracts": n, "avgPrice": price, "fee": fee,
            "breakEven": price + fee / n if n else None, "settled": done, "won": won,
            "winRate": won / done if done else None,
            **returns((f["window"], pnl(f), f["count"] * f["price"]) for f in settled),
            "windows": len({f["window"] for f in settled})}


def history_prediction():
    """What the backtest of a higher limit predicted at $30 a bet, 3% of about $1,000 like the bot today
    (research/kalshi_15min/lab/fills.py): the share of contracts filled and ¢ per $10 with the limit at the ask it saw
    (raise 0) and 1¢ over it, the latter a [min, max] over the windows of dearer trades it counted (30, 10, 5 and 2 s
    after the order), and the extra contracts' own ¢ per $10 likewise. None if the file or a number is missing."""
    try:
        rows = [r for r in read_json(os.path.join(RESEARCH, "lab", "fills.json"))["rows"] if r.get("size") == 30.0]
        before, during = next(r for r in rows if r.get("raise") == 0), [r for r in rows if r.get("raise") == 0.01]
        span = lambda key: [min(map(key, during)), max(map(key, during))]
        return {"source": "research/kalshi_15min/lab/fills.json", "size": 30, "fillBefore": before["filledContracts"],
                "fillDuring": span(lambda r: r["filledContracts"]), "perTenBefore": before["perTen"],
                "perTenDuring": span(lambda r: r["perTen"]), "extraPerTen": span(lambda r: r["extra"]["perTen"])}
    except SHAPE_ERRORS:
        return None


def live_prediction():
    """What replaying the bot's own orders against Kalshi's trade tape predicted for a limit 1¢ higher
    (research/kalshi_15min/lab/live_fills/live_fills.py): the share of asked contracts its orders filled at the old
    limit, and the extra contracts the higher limit would have bought from the trades in the 30 s after each order that
    didn't fill in full, their P&L with its standard error, P&L per contract and win rate. None if the file or a
    number is missing."""
    try:
        d = read_json(os.path.join(RESEARCH, "lab", "live_fills", "live_fills.json"))
        b = next(w for w in d["what_if_limit"] if w.get("bump_cents") == 1.0)["30s"]
        return {"source": "research/kalshi_15min/lab/live_fills/live_fills.json", "fillBefore": d["stats"]["fill_share"],
                "orders": b["orders"], "contracts": b["contracts"], "pnl": b["pnl"], "pnlSe": b["pnl_se"],
                "perContractCents": b["pnl_per_contract_cents"], "winRate": b["contract_win_rate"]}
    except SHAPE_ERRORS:
        return None


# What each verdict says, by its state: the +1¢ limit on real orders, and on paper (the shadow table)
LIVE_SAYS = {
    "off": "Off: real orders go at the ask the bot saw. The paper +1¢ above measures the extra cent without real money.",
    "waiting": "Not started: the bot sends +1¢ limits from its next restart.",
    "too-early": "Too early to tell: {n} of {target} orders with the +1¢ limit so far.",
    "helping": "The extra cent is paying: the extra contracts made money, and their 95% range is above zero.",
    "hurting": "The extra cent is losing money: the extra contracts' 95% range is below zero.",
    "no-difference": "No clear difference: the extra contracts' 95% range includes zero."}
PAPER_SAYS = {
    "waiting": "Not recording yet: the bot measures the paper +1¢ from its next restart.",
    "too-early": "Too early to tell: {n} orders measured on paper so far. The verdict comes on Nov 27, after 6 weeks.",
    "thin": "Not enough extra contracts to tell yet: {n} orders measured on paper.",
    "helping": "On paper the extra cent pays: the extra contracts made money, and their 95% range is above zero.",
    "hurting": "On paper the extra cent loses money: the extra contracts' 95% range is below zero.",
    "no-difference": "No clear difference on paper: the extra contracts' 95% range includes zero."}
# ... and the fast entry on paper (the shadow table's 'fast' rows), whose verdict is on the fills rather than the money
FAST_SAYS = {
    "waiting": "Not recording yet: the bot reads the order books at minute 8 exactly from its next restart.",
    "too-early": "Too early to tell: {n} of {target} orders paired on paper so far.",
    "faster-fills-more": "Orders sent at minute 8 exactly would fill more: the difference's 95% range is above zero.",
    "faster-fills-less": "Orders sent at minute 8 exactly would fill less: the difference's 95% range is below zero.",
    "no-difference": "No clear difference in fills: the difference's 95% range includes zero."}


def verdict(started, n, extra, target, says, idle="waiting"):
    """A card's answer to "does the extra cent pay?", from the extra contracts' ¢ per $10 and its 95% range (1.96
    standard errors either side), given only once `target` orders have the +1¢ limit and that range can be worked out.
    Before it started, `idle`: "waiting" for it, or "off" when there is nothing to wait for. says: the text of each state."""
    if started is None:
        state = idle
    elif n < target or extra["se"] is None:
        state = "too-early"
    else:
        state = ranged(extra)
    return {"state": state, "text": says[state].format(n=n, target=target), "orders": n, "target": target}


def ranged(extra):
    """What the extra contracts' 95% range (1.96 standard errors either side of their ¢ per $10) says: above zero,
    below it, or across it. Their standard error must be known."""
    if extra["perTen"] - 1.96 * extra["se"] > 0:
        return "helping"
    if extra["perTen"] + 1.96 * extra["se"] < 0:
        return "hurting"
    return "no-difference"


def paper_verdict(started, n, extra):
    """The paper +1¢'s answer, which waits for a date rather than an order count: "waiting" before it started, "too
    early" until SHADOW_UNTIL on this PC's clock however many orders are measured, then what the extra contracts' 95%
    range says, or "thin" when it can't be worked out (settled extra contracts in fewer than two windows)."""
    if started is None:
        state = "waiting"
    elif pc_clock() < SHADOW_UNTIL:
        state = "too-early"
    elif extra["se"] is None:
        state = "thin"
    else:
        state = ranged(extra)
    return {"state": state, "text": PAPER_SAYS[state].format(n=n), "orders": n, "until": SHADOW_UNTIL}


def shadow(rows):
    """The +1¢ limit on paper, from the ledger's shadow table (its kind 'limitup' rows, oldest first). Real orders go at
    the ask the bot saw; right after each one the bot reads the order book and notes the "extra" contracts a limit
    bot.SHADOW_UP higher would have bought on top of the real fill, what they'd have cost and their fee, then settles
    them with the market like a bet. No money moves. The real fill share (contracts filled / asked for) against the share
    with the extra cent, the share of the contracts left unfilled that the cent would have caught, the median lag (how
    many seconds after minute 8 the book was read), the extra contracts as a group of the split, the date it runs until
    (SHADOW_UNTIL), a verdict (paper_verdict()), and the latest rows. A book that couldn't be read ("unread") measured
    nothing: it counts as unread, and as the start."""
    measured = [r for r in rows if r["status"] != "unread"]
    asked, filled = sum(r["asked"] for r in measured), sum(r["filled"] for r in measured)
    extra, remaining = sum(r["extra"] for r in measured), sum(max(r["asked"] - r["filled"], 0) for r in measured)
    lags = [r["lag"] for r in measured if r["lag"] is not None]
    # how it ended: its side against the market's result, even with nothing extra bought
    result = lambda r: "open" if r["status"] != "settled" else "won" if r["side"] == r["result"] else "lost"
    # its extra contracts as group() reads fills: one "fill" a row, at their average price
    bought = [{"order": r["id"], "window": r["window_open"], "count": r["extra"], "price": r["cost"] / r["extra"],
               "fee": r["fee"], "status": result(r)} for r in measured if r["extra"] > 0]
    started, extras = rows[0]["ts"] if rows else None, group(bought)
    return {"limitUp": bot.SHADOW_UP, "started": started, "until": SHADOW_UNTIL, "orders": len(measured),
            "unread": len(rows) - len(measured), "asked": asked, "filled": filled, "extra": extra,
            "fillShare": filled / asked if asked else None, "fillShareWith": (filled + extra) / asked if asked else None,
            "remaining": remaining, "extraShare": extra / remaining if remaining else None,
            "ordersWithExtra": len(bought), "lag": statistics.median(lags) if lags else None, "group": extras,
            "verdict": paper_verdict(started, len(measured), extras),
            "rows": [{"ts": r["ts"], "ticker": r["ticker"], "side": r["side"], "seen": r["seen"], "limit": r["limit_price"],
                      "asked": r["asked"], "filled": r["filled"], "extra": r["extra"],
                      "avgPrice": r["cost"] / r["extra"] if r["extra"] else None, "lag": r["lag"], "result": result(r)}
                     for r in measured[::-1][:LIVE_ORDERS_SHOWN]]}


def fast_shadow(rows, bets, seen):
    """The fast entry on paper, from the ledger's shadow table (its kind 'fast' rows, oldest first). Real orders keep
    their timing, landing about 2.4 s after minute 8 starts; in the background the bot reads every order book at minute
    8 exactly (480.0 s into the window on Kalshi's clock, "the mark") and pairs each real order with a paper twin: the
    contracts an order sent at that instant with the same limit rule would have bought from that book (its "extra", here
    the twin's whole fill), what they'd have cost and their fee, settled with the market like a bet. No money moves.
    The real fill share (contracts filled / asked for) against the mark's, their difference with its standard error
    clustered by window, the share of the real orders' misses the mark's book had ("caught"), the ask each saw and the
    price each paid (seen: ticker -> the decision's price; bets: ticker -> the real bet), how many seconds after minute 8
    the mark's book answered ("lag"), the settled pairs' P&L on paper and for real, a verdict, and the latest pairs. A
    book that couldn't be read ("unread") measured nothing: it counts as unread, and as the start."""
    measured = [r for r in rows if r["status"] != "unread"]
    asked, filled = sum(r["asked"] for r in measured), sum(r["filled"] for r in measured)
    extra, n = sum(r["extra"] for r in measured), len(measured)
    # the mark's share less the real one, Σ(extra − filled) / Σasked, with its standard error clustered by window: the
    # orders in one 15-minute window share their luck, so each window counts as one draw
    diff, diff_se = fast_entry.ratio_se(fast_entry.by_window((r["window_open"], r["extra"] - r["filled"], r["asked"])
                                                             for r in measured))
    # the contracts the real orders missed, and how many of them the twins bought (a twin that bought less adds nothing)
    missed = sum(max(r["asked"] - r["filled"], 0) for r in measured)
    caught = sum(max(r["extra"] - r["filled"], 0) for r in measured)
    real_seen = [seen[r["ticker"]] for r in measured if seen.get(r["ticker"]) is not None]
    fast_seen = [r["seen"] for r in measured if r["seen"] is not None]   # none: nobody was selling on its side at the mark
    # the real bets the orders made, one a market (an order that got nothing made none, or one of no contracts)
    made = [bets[r["ticker"]] for r in measured if bets.get(r["ticker"], {}).get("contracts")]
    lags = sorted(r["lag"] for r in measured if r["lag"] is not None)
    settled = [r for r in measured if r["status"] == "settled"]
    # how it ended: its side against the market's result, even with nothing bought
    result = lambda r: "open" if r["status"] != "settled" else "won" if r["side"] == r["result"] else "lost"
    started, target = rows[0]["ts"] if rows else None, FAST_SHADOW_TARGET
    # the verdict, from the difference's 95% range (1.96 standard errors either side) once `target` orders are paired
    if not rows:
        state = "waiting"
    elif n < target or diff_se is None:
        state = "too-early"
    elif diff - 1.96 * diff_se > 0:
        state = "faster-fills-more"
    elif diff + 1.96 * diff_se < 0:
        state = "faster-fills-less"
    else:
        state = "no-difference"
    return {"started": started, "target": target, "orders": n, "unread": len(rows) - n,
            "asked": asked, "filled": filled, "extra": extra,
            "realShare": filled / asked if asked else None, "fastShare": extra / asked if asked else None,
            "diff": diff, "diffSe": diff_se, "caught": caught / missed if missed else None,
            "realSeen": sum(real_seen) / len(real_seen) if real_seen else None,
            "fastSeen": sum(fast_seen) / len(fast_seen) if fast_seen else None,
            "realAvg": sum(b["cost"] for b in made) / sum(b["contracts"] for b in made) if made else None,
            "fastAvg": sum(r["cost"] for r in measured) / extra if extra else None,
            "lag": {"median": fast_entry.quantile(lags, 0.5), "p90": fast_entry.quantile(lags, 0.9)},
            # on paper, the settled twins that bought something; for real, those markets' settled bets
            "pnl": {"settled": len(settled),
                    "paper": returns((r["window_open"], r["pnl"], r["cost"]) for r in settled if r["cost"] > 0),
                    "real": returns((b["window_open"], b["pnl"], b["cost"]) for b in
                                    (bets.get(r["ticker"], {}) for r in settled) if b.get("status") in ("won", "lost"))},
            "verdict": {"state": state, "text": FAST_SAYS[state].format(n=n, target=target), "orders": n, "target": target},
            "rows": [{"ts": r["ts"], "ticker": r["ticker"], "side": r["side"], "seenReal": seen.get(r["ticker"]),
                      "seen": r["seen"], "limit": r["limit_price"], "asked": r["asked"], "filled": r["filled"],
                      "extra": r["extra"], "avgPrice": r["cost"] / r["extra"] if r["extra"] else None, "lag": r["lag"],
                      "pnl": r["pnl"], "result": result(r)}
                     for r in measured[::-1][:LIVE_ORDERS_SHOWN]]}


def live_research(mode):
    """The +1¢ limit experiment in a mode's own records, for the Live Research tab. From its restart with bot.LIMIT_UP
    the bot's immediate-or-cancel limit sits 1¢ over the ask it saw: the experiment started with the first accepted buy
    order whose limit is over the ask it saw (the decision's price, whatever the decision then was), and each buy order
    is in the arm "before" it or "during" it. The during orders' fills split into "base" contracts, at or under the ask
    it saw (the old limit would have bought them too), and "extra" ones over it, which only the new limit buys; a filled
    order whose fills weren't recorded (a ledger from before the restart has no fills table) is "unknown". Then a
    verdict on the extra contracts, what the research predicted, and the experiment's latest orders. While bot.LIMIT_UP
    is 0 and no order ever had a limit over the ask it saw, the verdict is "off": the +1¢ runs on paper instead, the
    reply's "shadow" (None for a ledger from before the bot made the shadow table). The fast entry runs on paper too:
    each real order paired with what an order sent at minute 8 exactly would have bought, the reply's "fastShadow"
    (fast_shadow(); None likewise). The ledger is opened read-only and never changed."""
    db = read_only(mode)
    try:
        seen = dict(db.execute("SELECT ticker, fav_price FROM decisions"))
        bets = {b["ticker"]: dict(b) for b in db.execute("SELECT * FROM bets")}
        orders = accepted_orders(db)
        recorded = has_table(db, "fills")
        fills = {}   # order ID -> its fills
        if recorded:
            for f in db.execute("SELECT order_id, price, count, fee FROM fills WHERE order_id IS NOT NULL ORDER BY id"):
                fills.setdefault(f["order_id"], []).append(f)
        paper = None   # the paper +1¢'s rows, oldest first: the table also holds other paper experiments', each its own kind
        fast = None    # ... and the paper fast entry's
        if has_table(db, "shadow"):
            paper = [dict(r) for r in db.execute("SELECT * FROM shadow WHERE kind = 'limitup' ORDER BY ts, id")]
            fast = [dict(r) for r in db.execute("SELECT * FROM shadow WHERE kind = 'fast' ORDER BY ts, id")]
    finally:
        db.close()
    started = next((o["ts"] for o in orders if o["price"] is not None and seen.get(o["ticker"]) is not None
                    and o["price"] > seen[o["ticker"]] + 1e-9), None)
    before = [o for o in orders if started is None or o["ts"] < started]
    during = [o for o in orders if started is not None and o["ts"] >= started]
    split, unknown, rows = {"base": [], "extra": []}, {"orders": 0, "contracts": 0}, []
    for o in during:
        s = seen.get(o["ticker"])
        bet = bets.get(o["ticker"], {}) if o["filled"] else {}
        got = {"base": 0, "extra": 0}   # its contracts at or under the ask it saw, and over it
        if o["filled"] and (s is None or o["orderId"] not in fills):   # it filled, but which price bought what isn't known
            got = {"base": None, "extra": None}
            unknown["orders"] += 1
            unknown["contracts"] += o["filled"]
        elif o["filled"]:
            for f in fills[o["orderId"]]:
                kind = "base" if f["price"] <= s + 1e-9 else "extra"
                got[kind] += f["count"]
                split[kind].append({"order": o["orderId"], "window": bet.get("window_open"), "price": f["price"],
                                    "count": f["count"], "fee": f["fee"], "status": bet.get("status")})
        rows.append({"ts": o["ts"], "ticker": o["ticker"], "side": o["side"], "seen": s, "limit": o["price"],
                     "asked": o["asked"], "filled": o["filled"], **got, "avgPaid": bet.get("price"),
                     "result": bet.get("status")})
    extra, target = group(split["extra"]), LIVE_RESEARCH_TARGET
    return {"mode": mode, "now": real_now(), "limitUp": bot.LIMIT_UP, "target": target, "started": started,
            "fillsRecorded": recorded,
            "arms": {"before": arm(before, seen, bets), "during": arm(during, seen, bets)},
            "split": {"base": group(split["base"]), "extra": extra, "unknown": unknown},
            "verdict": verdict(started, len(during), extra, target, LIVE_SAYS, "off" if bot.LIMIT_UP == 0 else "waiting"),
            "predictions": {"history": history_prediction(), "live": live_prediction()},
            "orders": rows[::-1][:LIVE_ORDERS_SHOWN],
            "shadowUp": bot.SHADOW_UP, "shadow": None if paper is None else shadow(paper),
            "fastShadow": None if fast is None else fast_shadow(fast, bets, seen)}


def latency_view(mode):
    """The Latency tab's reply for a mode: latency.report() of its ledger, opened read-only (latency.py)."""
    db = read_only(mode)
    try:
        return {"mode": mode, "now": real_now(), **latency.report(db)}
    finally:
        db.close()


def own_address(host):
    """Whether a Host header names this computer by number or as localhost, not by a site's name: a site that points
    its own name at 127.0.0.1 (DNS rebinding) mustn't pass for this dashboard's own page."""
    name = urlparse("//" + host).hostname or ""
    if name == "localhost":
        return True
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(PAGE, "rb") as fh:
                return self.send(200, fh.read(), "text/html; charset=utf-8")
        if u.path == "/tape":
            with open(TAPE, "rb") as fh:
                return self.send(200, fh.read(), "text/html; charset=utf-8")
        if u.path == "/api/state":
            ms = modes()
            if not ms:
                return self.send(200, {"modes": [], "halt": bot.halt_info()})
            want = parse_qs(u.query).get("mode", [None])[0]
            return self.send(200, state(want if want in ms else ms[0]))  # only modes that exist: no paths from outside
        if u.path == "/api/balance":   # the navbar's: Kalshi is asked at most once a second, however many tabs poll
            ms = modes()
            if not ms:
                return self.send(200, {"error": "no live account yet"})
            want = parse_qs(u.query).get("mode", [None])[0]
            m = want if want in ms else ms[0]   # only modes that exist: no paths from outside
            return self.send(200, cached(("balance", m), BALANCE_EVERY, lambda: balance_now(m)))
        if u.path == "/api/research":
            return self.send(200, cached(("study", stamp()), 3600, study))
        if u.path == "/api/research/stamp":   # cheap to ask now and then: then /api/research only when it moved
            return self.send(200, {"stamp": stamp()})
        if u.path == "/api/research/live":   # ?book=TICKER: that market's order book too
            book = parse_qs(u.query).get("book", [None])[0]
            return self.send(200, cached(("live", book), RESEARCH_EVERY, lambda: research_live(book)))
        if u.path == "/api/live-research":
            ms = modes()
            if not ms:
                return self.send(200, {"error": "no live records yet"})
            want = parse_qs(u.query).get("mode", [None])[0]
            m = want if want in ms else ms[0]   # only modes that exist: no paths from outside
            return self.send(200, cached(("liveresearch", m), LIVE_RESEARCH_EVERY, lambda: live_research(m)))
        if u.path == "/api/latency":
            ms = modes()
            if not ms:
                return self.send(200, {"error": "no live records yet"})
            want = parse_qs(u.query).get("mode", [None])[0]
            m = want if want in ms else ms[0]   # only modes that exist: no paths from outside
            return self.send(200, cached(("latency", m), LATENCY_EVERY, lambda: latency_view(m)))
        if u.path in ASSETS:
            name, kind = ASSETS[u.path]
            with open(os.path.join(STATIC, name), "rb") as fh:
                return self.send(200, fh.read(), kind)
        self.send(404, {"error": "not found"})

    def own_page(self):
        """Whether a POST came from this dashboard's own page. A browser names the page a request came from (Origin),
        and any web page can POST to localhost; a program on this computer (curl) sends no Origin at all."""
        origin, host = self.headers.get("Origin"), self.headers.get("Host") or ""
        return origin is None or (urlparse(origin).netloc == host and own_address(host))

    def do_POST(self):
        if urlparse(self.path).path == "/api/halt":  # it can stop the bot, never start it
            if not self.own_page():
                return self.send(403, {"error": "only the dashboard's own page can halt the bot"})
            bot.set_halt(time.time(), "halted from the dashboard", "you")
            return self.send(200, {"halt": bot.halt_info()})
        self.send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--lan", action="store_true", help="listen on the home network too (for your phone), not just this computer")
    ap.add_argument("--state", help=argparse.SUPPRESS)  # another state folder, for testing
    a = ap.parse_args()
    if a.state:
        bot.STATE = a.state
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    print(f"dashboard on http://localhost:{a.port}" + (" (and this computer's address on your network)" if a.lan else ""), flush=True)
    ThreadingHTTPServer((host, a.port), Handler).serve_forever()


def cli():
    """The command line (python dashboard.py, python -m kalshi_bot.web): main(), stopped quietly by Ctrl+C."""
    try:
        main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
