"""The maker shadow recorder: Kalshi's order book and trade tape for the bot's 16 markets, written down raw for a month.

Why: the live bot is a taker. At minute 8 of each 15-minute window it buys the favourite at the ask and pays the
taker fee. Makers, whose resting orders wait in the book, are said to collect what takers lose. The Oct 11 lab test
could only see minute-close prices, so it saw a resting order fill only when the price itself fell to it; it could
not see a seller hitting a resting bid while the price stayed put. This records what it couldn't see: every change to
the order book and every trade in the bot's 16 markets, straight from Kalshi's WebSocket. maker_replay.py then replays
them with a pretend resting order at minute 8: how often it would fill, at what price, how fast, and what the price
did next. Spec: SPEC.md, "maker_shadow.py: the recorder".

It cannot trade. There is no order code here at all. The REST client is used for two public reads only: listing a
window's markets (markets()) and reading a market's result (get()). The WebSocket is subscribed to two public
channels only, orderbook_delta and trade. Kalshi's socket wants a key even for public data, so it signs in with the
bot's key, which it only reads. It makes no REST call in seconds 420-600 of a window, when the bot gets ready and
buys. It shares nothing with the bot but that .env and key, opens no port, and writes only inside --out.

What it writes, all in --out:
- ws-YYYYMMDDTHH.txt.gz: every WebSocket message exactly as it came, one a line: "<receive time> <message>". One gzip
  stream per UTC hour, flushed every FLUSH_EVERY s (so a crash loses at most that much) and closed as the hour ends
  (a complete gzip, ready for the laptop to copy). A name already taken, after a restart within the hour, gets the
  next number: ws-YYYYMMDDTHH.1.txt.gz, .2, ... A file is never appended to or overwritten.
- markets.jsonl: each window's markets as Kalshi listed them, with window_open added.
- results.jsonl: each market's result, once it has one.
- events.jsonl: starts, connects, drops, gaps in Kalshi's message numbers, subscribes, failed listings, series still
  unlisted when listing stops (not_listed), REST calls over REST_SLOW s (rest_slow), refused sign-ins (auth_failed),
  Kalshi's errors, low-space pauses.
- status.json: what it is doing, rewritten every STATUS_EVERY s. pull.py reads "writing", the hour file still open.
- recorder.lock: locked while it runs (the OS lets go when the process ends), so a second recorder on the same folder
  exits 3 at once, having changed nothing.

How it keeps out of the bot's way on a 2-CPU server: the feed is about 3,300 messages a second, and each one is only
peeked at (three small regexes find its type, sid and seq) and written; only the rare control messages are parsed.
One REST call at a time, REST_GAP s apart at least, with timeouts short enough that even one that keeps retrying is
over before the bot's busy part. A refused sign-in waits AUTH_WAIT s before the next try. It stops recording when the
shared disk has less than MIN_FREE_GB free, and starts again once there is room. Every failure (a dropped socket, a
failed listing, a bad answer, even a bug in a step) is logged and recovered from, not crashed on. Its timers run on
the monotonic clock, so a wall clock stepped back or forward can't freeze or rush them; the wall clock is used only for
the times it writes down and for the window, hour, results and --until.

    python maker_shadow.py record --out data --until 2026-11-28
"""
import argparse
import gzip
import json
import math
import os
import re
import shutil
import signal
import sys
import time
import traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.normpath(os.path.join(HERE, "..", "..", "bot", "kalshi_bot")), HERE):   # its own folder first, then the bot's
    while _path in sys.path:
        sys.path.remove(_path)
    sys.path.insert(0, _path)

from kalshi import Kalshi, load_key, sign  # noqa: E402  (a kalshi.py beside it on the server, the bot's in the repo)

try:
    import websocket   # websocket-client
except ImportError:   # pragma: no cover  (the CLI says what to install)
    websocket = None

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M", "KXNEAR15M",
          "KXZEC15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXCOPPER15M", "KXWTI15M",
          "KXNATGAS15M")   # the bot's 16 markets
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"   # Kalshi's WebSocket, prod
WS_PATH = "/trade-api/ws/v2"   # the handshake signs timestamp + "GET" + this path
WINDOW = 900           # seconds in a window; each series has one market a window, open for all of it
QUIET = (420, 600)     # seconds into a window with no REST calls at all: the bot preps at 450 s, enters at 480 s
LIST_AT = 15           # first try at listing a window's markets, seconds into it; series still missing are asked
LIST_RETRY = 30        #   again this long after each round ends, until all have a market or REST calls stop
RESULTS_AFTER = 120    # ask for a market's result once it closed this long ago ...
RESULTS_GIVE_UP = 6 * 3600   # ... and stop asking this long after it closed
RESULTS_RETRY = 60     # ... asking one that has no result yet again at most this often
REST_GAP = 0.5         # at least this many seconds between REST calls
REST_CONNECT = 0.5     # seconds a REST call may spend connecting to one address (the server is under 1 ms from Kalshi)
REST_TIMEOUT = 3       #   and waiting for each read of Kalshi's answer. requests applies the connect timeout to each
                       #   of the host's 8 addresses in turn, and kalshi.Kalshi.get tries 4 times, sleeping 1-4 s
REST_STOP = 60         #   between, so one call can last 4 x (8 x 0.5 + 3) + 10 = 38 s: none starts this long before
                       #   QUIET[0]
REST_SLOW = 1          # a REST call that took longer than this many seconds is logged (rest_slow)
QUIET_SOCKET = 30      # a subscribed socket that has said nothing this long is dead: reconnect
RETRY = (1, 2, 5, 10, 30)    # seconds before each reconnect after a failure in a row, then 30 s each time
HEALTHY = 60           # a socket that stays up this long starts the waits over from RETRY[0]
AUTH_WAIT = 900        # Kalshi refused the socket's sign-in (HTTP 401 or 403): wait this long, not RETRY, to try
                       #   again, so a bad key can't hammer Kalshi from the bot's IP with the bot's key
RESUB_MIN = 10         # at least this long between resubscribes after gaps, so a storm of gaps can't spam Kalshi
STATUS_EVERY = 30      # seconds between rewrites of status.json
GZIP_LEVEL = 3         # light compression: cheap on the CPU, still about 10x smaller
FLUSH_EVERY = 5        # seconds between flushes of the hour file, at most: what a crash can lose
SPACE_EVERY = 60       # seconds between reads of the disk's free space
MIN_FREE_GB = 15       # below this many GiB free it stops recording; it starts again above MIN_FREE_GB + 2
STEP_MAX = 0.2         # a step reads messages for at most this long, so REST calls and housekeeping get their turn
CONTROL = frozenset(("subscribed", "unsubscribed", "ok", "error"))   # the only messages parsed in full
MARKETS, RESULTS, EVENTS, STATUS = "markets.jsonl", "results.jsonl", "events.jsonl", "status.json"
LOCK = "recorder.lock"   # held by the recorder writing in the folder; the OS lets go of it when that process ends
DEFAULT_ENV = "~/kalshi/bot/.env"
GIB = 2 ** 30
HOUR_NAME = re.compile(r"^(ws-\d{8}T\d{2})(?:\.(\d+))?\.txt\.gz$")

# peek's regexes: a message's top-level "type", "sid" and "seq" come first in Kalshi's messages, so each search
# stops a few dozen characters in. They match whole keys only ("market_type" is not "type").
_TYPE = re.compile(r'"type"\s*:\s*"([^"]*)"')
_SID = re.compile(r'"sid"\s*:\s*(\d+)')
_SEQ = re.compile(r'"seq"\s*:\s*(\d+)')
_SIGN_IN_REFUSED = re.compile(r"\b40[13]\b")


# ------------------------------------------------------------------ pure helpers


def window_of(t):
    """The start of the window holding t: t rounded down to a multiple of WINDOW (UTC epoch seconds)."""
    return int(t // WINDOW) * WINDOW


def quiet(t):
    """True in the part of a window with no REST calls: QUIET[0] <= seconds into it < QUIET[1]."""
    return QUIET[0] <= t - window_of(t) < QUIET[1]


def rest_ok(t):
    """True when a REST call may start: not in QUIET, nor in the REST_STOP s before it, so even a call that keeps
    retrying is over before the bot preps."""
    return not QUIET[0] - REST_STOP <= t - window_of(t) < QUIET[1]


def hour_file(t):
    """The hour file's name for the UTC hour holding t: ws-YYYYMMDDTHH.txt.gz."""
    return datetime.fromtimestamp(t, timezone.utc).strftime("ws-%Y%m%dT%H.txt.gz")


def peek(text):
    """(type, sid, seq) of a raw message, read with regexes instead of parsing the JSON; None for any that's absent."""
    kind, sid, seq = _TYPE.search(text), _SID.search(text), _SEQ.search(text)
    return (kind.group(1) if kind else None, int(sid.group(1)) if sid else None, int(seq.group(1)) if seq else None)


def read_env(path):
    """{KEY: VALUE} from a .env file's KEY=VALUE lines. Blank lines, # comments and lines without "=" are skipped;
    spaces and quotes around a value are stripped. A missing file gives {}."""
    env = {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return env
    for raw in lines:
        raw = raw.strip()
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            env[key.strip()] = value.strip().strip("\"'")
    return env


def ws_headers(key_id, key, now_ms):
    """The WebSocket handshake's three signed headers, for a timestamp in milliseconds."""
    stamp = str(now_ms)
    return {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-TIMESTAMP": stamp,
            "KALSHI-ACCESS-SIGNATURE": sign(key, stamp + "GET" + WS_PATH)}


def epoch(iso):
    """Epoch seconds of an ISO time, "Z" or "+00:00", with or without fractions (UTC if it names no zone)."""
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def window_markets(listing, series, window_open):
    """The markets in one GET /markets answer ({"markets": [...]}, or None) that opened within 1 s of window_open, as
    {"ticker", "series", "open", "close", "raw"}: open and close in epoch seconds, raw the market as Kalshi sent it
    (tick size, fee fields and all). A market without a ticker, or whose open or close time is missing or won't
    parse, is skipped: the run is unattended."""
    markets = listing.get("markets") if isinstance(listing, dict) else None
    out = []
    for raw in markets if isinstance(markets, list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            ticker, opened, closes = raw["ticker"], epoch(raw["open_time"]), epoch(raw["close_time"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if isinstance(ticker, str) and ticker and abs(opened - window_open) <= 1:
            out.append({"ticker": ticker, "series": series, "open": opened, "close": closes, "raw": raw})
    return out


def settled(market):
    """(result, status) once a GET /markets/{ticker} answer's market has its result, "yes" or "no"; else None.
    Takes the whole answer ({"market": {...}}) or the market itself."""
    m = market.get("market") if isinstance(market, dict) and "market" in market else market
    if not isinstance(m, dict) or m.get("result") not in ("yes", "no"):
        return None
    return m["result"], m.get("status")


def refused_sign_in(e):
    """True when a connect failed because Kalshi refused the handshake's sign-in, HTTP 401 or 403. websocket-client
    raises WebSocketBadStatusException with the code in .status_code; an error without one counts when its message
    has a 401 or 403 in it."""
    code = getattr(e, "status_code", None)
    if code is not None:
        return str(code).strip() in ("401", "403")
    return bool(_SIGN_IN_REFUSED.search(str(e)))


def say(text):
    """Print a line for the service's log; a closed stdout is no reason to stop recording."""
    try:
        print(text, flush=True)
    except (OSError, ValueError):
        pass


# ------------------------------------------------------------------ the recorder


class Recorder:
    """Lists each window's markets, keeps the socket subscribed to them, writes every message, and asks for results.

    out: the folder for everything it writes (made if missing); it writes nowhere else. client: a kalshi.Kalshi, or
    a fake, used only for markets(**params) and get(path). connect(): an open socket with send(text), recv() (one
    message, or TimeoutError / websocket-client's timeout after about a second with nothing) and close(); any other
    error from them means the socket is dead. now: the wall clock, for receive times, the window, the hour, results
    and until. mono: a monotonic clock, for every timer (reconnect waits, flushes, status.json, space checks,
    REST_GAP, QUIET_SOCKET, RESUB_MIN, HEALTHY, STEP_MAX). sleep: sleeps. until: run() returns once now() >= until
    (None: never). free_bytes(path): the free bytes on out's disk (shutil.disk_usage by default).

    step() is one turn: housekeeping (free space, the hour file, the window, at most one REST call, status.json),
    then the socket (connect when due, subscribe when the markets changed, read messages for up to STEP_MAX s)."""

    def __init__(self, out, client, connect, now=time.time, mono=time.monotonic, sleep=time.sleep, until=None,
                 free_bytes=None):
        self.out = os.path.abspath(out)
        self.client, self.connect, self.now, self.sleep, self.until = client, connect, now, sleep, until
        self.mono = mono             # the timers' clock (the fields marked "mono" below)
        self.free_bytes = free_bytes or (lambda path: shutil.disk_usage(path).free)
        self.timeouts = (TimeoutError,) + ((websocket.WebSocketTimeoutException,) if websocket else ())
        self.started = self.stopping = self.paused = False
        # the socket
        self.ws = None
        self.cmd = 0                 # the last command id sent on this socket
        self.sids = set()            # Kalshi's ids for the subscriptions it holds
        self.sub_ids = set()         # this socket's subscribe command ids ...
        self.sub_id = None           # ... and the one in force
        self.subscribed = ()         # the tickers that subscribe asked for
        self.seqs = {}               # sid -> the last seq seen on it
        self.want_sub = False        # subscribe at the next turn: the window's markets changed, or a new socket
        self.want_resub = False      # ... after a gap: not before last_sub + RESUB_MIN
        self.last_sub = -math.inf    # mono
        self.heard = 0.0             # mono: when the socket last said anything (or was subscribed)
        self.connected_at = 0.0      # mono
        self.fails = 0               # failures in a row: they set the wait before the next connect
        self.retry_at = -math.inf    # mono: no connect before then
        # the window and its markets
        self.window = None
        self.markets = {}            # ticker -> series, this window's
        self.carry = {}              # this window's markets, read back from markets.jsonl at the start
        self.queue = []              # series left to ask in this listing round
        self.round_at = 0.0          # when the next round may start
        self.round_found = False     # this round found a market
        self.rounds = 0              # rounds started this window (0 again once the missing series are logged)
        self.rest_free = -math.inf   # mono: no REST call before then
        # results
        self.pending = {}            # ticker -> close, for markets with no result yet
        self.asked = {}              # ticker -> when it was last asked
        self.results_at = 0.0        # nothing is due before then
        # the hour file
        self.fh = None
        self.fh_name = None
        self.fh_end = 0.0            # the end of its hour
        self.flush_at = 0.0          # mono
        self.dirty = False           # written since the last flush
        # housekeeping
        self.status_at = self.space_at = -math.inf   # mono
        self.free_gb = None
        self.messages = self.drops = self.gaps = 0
        self.last_rt = None
        self.tails = set()           # the .jsonl files checked for a last line a crash cut short

    # -------------------------------------------------------------- the loop

    def run(self):
        """step() until now() >= until or stop(). A step that raises is logged, the socket dropped and the hour file
        closed (so the next one starts clean), and the loop carries on. Leaves the hour file complete either way."""
        done = False
        try:
            if not self.started:
                self.begin(self.now())
            while not self.stopping and (self.until is None or self.now() < self.until):
                try:
                    self.step()
                except Exception as e:
                    t = self.now()
                    traceback.print_exc()
                    self.close_file()
                    self.close_socket()
                    self.failed(t, "exception", why=repr(e)[:500])
                    self.sleep(1.0)
            done = True
        finally:
            self.finish("stopped" if self.stopping else "until" if done else "interrupted")

    def stop(self):
        """Ask run() to return after this step (the CLI's SIGTERM)."""
        self.stopping = True

    def step(self):
        t, m = self.now(), self.mono()       # t: what is written down, the window, the hour; m: the timers
        if not self.started:
            self.begin(t)
        if m >= self.space_at:
            self.check_space(t, m)
        if self.fh is not None:
            if t >= self.fh_end:
                self.close_file()            # the hour is over: a complete gzip, even with nothing more to write
                self.write_status(t)         # and pull.py may copy it now
            elif self.dirty and m >= self.flush_at:
                self.flush(m)
        self.follow_window(t)
        if not self.paused:
            self.rest(t, m)
        if m >= self.status_at:
            self.status_at = m + STATUS_EVERY
            self.write_status(t)
        if self.paused:
            self.sleep(1.0)
            return
        if self.ws is None:
            if m < self.retry_at:
                self.sleep(min(1.0, self.retry_at - m))   # in pieces, so listing, results and status carry on
                return
            self.open_socket()
            if self.ws is None:
                return
        m = self.mono()
        if self.fails and m - self.connected_at >= HEALTHY:
            self.fails = 0
        if self.sub_due(m):
            self.subscribe()
        if self.ws is not None:
            self.read(m)

    def begin(self, t):
        """Read back what an earlier run wrote: this window's markets (so they aren't listed again) and the markets
        still waiting for a result (so a result is never asked twice)."""
        self.started = True
        os.makedirs(self.out, exist_ok=True)
        w = window_of(t)
        done = {r.get("ticker") for r in self.read_back(RESULTS)}
        for m in self.read_back(MARKETS):
            try:
                ticker, series, close, opened = m["ticker"], m["series"], float(m["close"]), m["window_open"]
            except (KeyError, TypeError, ValueError):
                continue
            if opened == w:
                self.carry[ticker] = series
            if ticker not in done and t - close < RESULTS_GIVE_UP:
                self.pending[ticker] = close
        self.log(t, "start", until=self.until, window_open=w, carried=sorted(self.carry), pending=len(self.pending))

    def finish(self, why):
        t = self.now()
        self.close_socket()
        self.close_file()
        self.log(t, "stop", why=why)
        self.write_status(t)

    # -------------------------------------------------------------- listing and results (REST)

    def follow_window(self, t):
        """A new window: its markets start empty (or as read back at the start), and get listed from LIST_AT s in."""
        w = window_of(t)
        if w == self.window:
            return
        self.window = w
        self.markets, self.carry = dict(self.carry), {}
        self.queue, self.round_found, self.round_at, self.rounds = [], False, w + LIST_AT, 0
        self.want_sub = True         # the last window's markets closed with it: unsubscribe them

    def rest(self, t, m):
        """At most one REST call: the next series of a listing round, else the result most due. None in QUIET, nor
        in the REST_STOP s before it (rest_ok)."""
        listing = self.round(t)
        if m < self.rest_free or not rest_ok(t):
            return
        if listing:
            self.list_next()
        else:
            self.ask_result(t)

    def round(self, t):
        """Keep the listing round going; True when a series waits to be asked. From LIST_AT s into the window, a round
        asks each series still without a market; the next round starts LIST_RETRY s after one ends. At
        QUIET[0] - REST_STOP, when no more REST calls may start, it gives up on the rest for this window, and if it
        asked at all, logs the series still without a market (not_listed), once."""
        into = t - self.window
        if into < LIST_AT or into >= QUIET[0] - REST_STOP:
            if self.queue:
                self.queue = []
                self.end_round()
            if self.rounds and into >= QUIET[0] - REST_STOP:
                rounds, self.rounds = self.rounds, 0
                have = set(self.markets.values())
                missing = [s for s in SERIES if s not in have]
                if missing:
                    self.log(t, "not_listed", window_open=self.window, series=missing, rounds=rounds)
            return False
        if not self.queue and t >= self.round_at:
            have = set(self.markets.values())
            self.queue = [s for s in SERIES if s not in have]
            self.round_found = False
            if self.queue:
                self.rounds += 1
            else:
                self.round_at = math.inf     # every series has its market
        return bool(self.queue)

    def list_next(self):
        s, w = self.queue.pop(0), self.window
        why = "no answer"
        began = self.mono()
        try:
            got = self.client.markets(series_ticker=s, min_close_ts=int(w + WINDOW - 1),
                                      max_close_ts=int(w + WINDOW + 1), limit=50)
        except Exception as e:
            got, why = None, repr(e)
        t = self.now()
        self.called(t, began, series=s)
        if got is None:
            self.log(t, "list_failed", series=s, why=why)
        for m in window_markets(got, s, w):
            if m["ticker"] not in self.markets:
                self.append(MARKETS, {**m, "window_open": w})
                self.markets[m["ticker"]] = s
                self.pending[m["ticker"]] = m["close"]
                self.results_at = min(self.results_at, m["close"] + RESULTS_AFTER)
                self.round_found = True
        if not self.queue:
            self.end_round()

    def end_round(self):
        self.round_at = self.now() + LIST_RETRY
        if self.round_found:
            self.want_sub = True     # subscribe once a round ends, not after each market it found
        self.round_found = False

    def ask_result(self, t):
        """Ask for the result of the market most due: closed RESULTS_AFTER s ago or more, not asked in the last
        RESULTS_RETRY s, the one asked longest ago first. Markets closed RESULTS_GIVE_UP s ago are given up on."""
        if t < self.results_at:
            return
        best, wake = None, math.inf
        for ticker, close in list(self.pending.items()):
            if t - close >= RESULTS_GIVE_UP:
                del self.pending[ticker]
                self.asked.pop(ticker, None)
                continue
            last = self.asked.get(ticker)
            due = close + RESULTS_AFTER if last is None else max(close + RESULTS_AFTER, last + RESULTS_RETRY)
            if due > t:
                wake = min(wake, due)
                continue
            key = (-math.inf if last is None else last, close)
            if best is None or key < best[0]:
                best = (key, ticker)
        if best is None:
            self.results_at = wake
            return
        self.results_at = 0.0            # others may be due too: look again next time
        ticker = best[1]
        self.asked[ticker] = t
        began = self.mono()
        try:
            got = self.client.get(f"/markets/{ticker}")
        except Exception:
            got = None
        rt = self.now()
        self.called(rt, began, ticker=ticker)
        result = settled(got)
        if result:
            self.append(RESULTS, {"ticker": ticker, "result": result[0], "status": result[1], "rt": round(rt, 3)})
            del self.pending[ticker]
            self.asked.pop(ticker, None)

    def called(self, t, began, **what):
        """A REST call that began at mono time `began` just ended: the next waits REST_GAP s, and one that took over
        REST_SLOW s is logged with the series or ticker it asked about."""
        m = self.mono()
        self.rest_free = m + REST_GAP
        if m - began > REST_SLOW:
            self.log(t, "rest_slow", **what, seconds=round(m - began, 2))

    # -------------------------------------------------------------- the socket

    def open_socket(self):
        try:
            ws = self.connect()
        except Exception as e:
            if refused_sign_in(e):
                self.failed(self.now(), "auth_failed", wait=AUTH_WAIT, why=repr(e)[:500])
            else:
                self.failed(self.now(), "connect_failed", why=repr(e)[:500])
            return
        self.ws, self.cmd = ws, 0
        self.sids, self.sub_ids, self.sub_id, self.subscribed, self.seqs = set(), set(), None, (), {}
        self.connected_at = self.heard = self.mono()
        self.want_sub, self.want_resub = True, False
        self.log(self.now(), "connect")

    def sub_due(self, m):
        return self.want_sub or (self.want_resub and m >= self.last_sub + RESUB_MIN)

    def subscribe(self):
        """Unsubscribe every sid it holds, then subscribe this window's markets' book and trades (if it has any:
        a subscribe with no markets would mean every market on Kalshi). Kalshi answers with fresh snapshots."""
        self.want_sub = self.want_resub = False
        try:
            if self.sids:
                old = sorted(self.sids)
                self.sids = set()
                for sid in old:
                    self.seqs.pop(sid, None)
                self.command("unsubscribe", {"sids": old})
            tickers = sorted(self.markets)
            self.subscribed, self.sub_id = tuple(tickers), None
            if tickers:
                self.sub_id = self.command("subscribe", {"channels": ["orderbook_delta", "trade"],
                                                         "market_tickers": tickers})
                self.sub_ids.add(self.sub_id)
                self.heard = self.last_sub = self.mono()   # the quiet clock starts here
                self.log(self.now(), "subscribe", tickers=tickers)
        except Exception as e:
            self.drop(self.now(), f"send failed: {e!r}")

    def command(self, cmd, params):
        self.cmd += 1
        self.ws.send(json.dumps({"id": self.cmd, "cmd": cmd, "params": params}))
        return self.cmd

    def read(self, m0):
        """Take messages until recv has nothing for a second, a subscribe is due, or STEP_MAX s have gone by."""
        ws = self.ws
        while True:
            try:
                text = ws.recv()
            except self.timeouts:
                m = self.mono()
                if self.subscribed and m - self.heard >= QUIET_SOCKET:
                    self.drop(self.now(), f"quiet: nothing for {m - self.heard:.0f} s")
                return
            except Exception as e:
                self.drop(self.now(), f"recv failed: {e!r}")
                return
            rt, m = self.now(), self.mono()
            if not text:                 # websocket-client's answer to a close frame
                self.drop(rt, "closed by Kalshi")
                return
            self.heard = m
            self.on_message(text, rt)
            if self.ws is not ws or self.sub_due(m) or m - m0 >= STEP_MAX:
                return

    def on_message(self, text, rt):
        """Write the message as it came, then peek at it: control messages are parsed, the rest only seq-checked."""
        if not isinstance(text, str):
            text = text.decode("utf-8", "replace")    # a binary frame (Kalshi sends text)
        if "\n" in text or "\r" in text:
            text = text.replace("\r", " ").replace("\n", " ")   # never seen: JSON doesn't need them; a line is a message
        if self.fh is None or rt >= self.fh_end:
            self.roll(rt)
        self.fh.write(f"{rt:.3f} {text}\n")
        self.dirty = True
        self.messages += 1
        self.last_rt = rt
        kind, sid, seq = peek(text)
        if kind in CONTROL:
            self.control(kind, text, rt)
        elif sid is not None and seq is not None:
            last = self.seqs.get(sid)
            self.seqs[sid] = seq
            if last is not None and seq != last + 1:
                self.gap(rt, sid, last + 1, seq)

    def control(self, kind, text, rt):
        try:
            m = json.loads(text)
        except ValueError:
            return
        if not isinstance(m, dict):
            return
        body = m.get("msg") if isinstance(m.get("msg"), dict) else {}
        if kind == "subscribed":
            sid, cid = body.get("sid"), m.get("id")
            if not isinstance(sid, int):
                return
            if isinstance(cid, int) and cid in self.sub_ids and cid != self.sub_id:
                # the answer to a subscribe that was replaced before Kalshi answered it: two subscriptions would
                # send every delta twice
                try:
                    self.command("unsubscribe", {"sids": [sid]})
                except Exception as e:
                    self.drop(rt, f"send failed: {e!r}")
            else:
                self.sids.add(sid)
        elif kind == "error":
            self.log(rt, "error", msg=body.get("msg"), code=body.get("code"), id=m.get("id"))

    def gap(self, rt, sid, expected, got):
        """Messages were lost on a sid: log it, and resubscribe (fresh snapshots) if it's one of this window's."""
        self.gaps += 1
        self.log(rt, "gap", sid=sid, expected=expected, got=got)
        if sid in self.sids:
            self.want_resub = True

    def close_socket(self):
        ws, self.ws = self.ws, None
        self.sids, self.sub_ids, self.sub_id, self.subscribed, self.seqs = set(), set(), None, (), {}
        self.want_sub, self.want_resub = True, False
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def drop(self, t, why):
        self.close_socket()
        self.drops += 1
        self.failed(t, "drop", why=why)

    def failed(self, t, event, wait=None, **fields):
        """Log a failure; the next connect waits `wait` s, or by default RETRY[k - 1] s after the k-th failure in a
        row."""
        self.fails += 1
        if wait is None:
            wait = RETRY[min(self.fails, len(RETRY)) - 1]
        self.retry_at = self.mono() + wait
        self.log(t, event, **fields)

    # -------------------------------------------------------------- files

    def roll(self, rt):
        """Close the hour file and open the one for rt's hour, numbered after any already there for that hour."""
        self.close_file()
        base = hour_file(rt)[:-len(".txt.gz")]
        taken = [int(m.group(2) or 0) for m in map(HOUR_NAME.match, os.listdir(self.out)) if m and m.group(1) == base]
        n = max(taken) + 1 if taken else 0
        while True:
            name = f"{base}.{n}.txt.gz" if n else f"{base}.txt.gz"
            try:
                fh = gzip.open(os.path.join(self.out, name), "xt", compresslevel=GZIP_LEVEL, encoding="utf-8",
                               newline="")
                break
            except FileExistsError:      # pragma: no cover  (another writer between listdir and open)
                n += 1
        self.fh, self.fh_name, self.dirty = fh, name, False
        self.fh_end = (math.floor(rt / 3600) + 1) * 3600
        self.flush_at = self.mono() + FLUSH_EVERY
        self.write_status(rt)            # status.json names the open file at once: pull.py must not take it

    def flush(self, m):
        """A sync flush: everything written so far can be read back, even if the process dies next."""
        self.flush_at, self.dirty = m + FLUSH_EVERY, False
        self.fh.flush()

    def close_file(self):
        fh, self.fh, self.fh_name, self.dirty = self.fh, None, None, False
        if fh is not None:
            try:
                fh.close()
            except Exception as e:
                say(f"closing the hour file: {e!r}")

    def read_back(self, name):
        """The JSON objects in one of its .jsonl files, a line each; lines that don't parse (a crash's) skipped."""
        try:
            fh = open(os.path.join(self.out, name), encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return
        with fh:
            for raw in fh:
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    yield rec

    def append(self, name, rec):
        """One JSON line onto a .jsonl file in out. The first time, a last line a crash cut short is ended first."""
        path = os.path.join(self.out, name)
        text = json.dumps(rec, separators=(",", ":")) + "\n"
        if name not in self.tails:
            self.tails.add(name)
            try:
                with open(path, "rb") as fh:
                    fh.seek(max(fh.seek(0, os.SEEK_END) - 1, 0))
                    if fh.read(1) not in (b"", b"\n"):
                        text = "\n" + text
            except FileNotFoundError:
                pass
        with open(path, "a", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def log(self, t, event, **fields):
        rec = {"rt": round(t, 3), "event": event, **fields}
        try:
            self.append(EVENTS, rec)
        except OSError as e:
            say(f"{EVENTS}: {e!r}")
        say(json.dumps(rec))

    def write_status(self, t):
        """status.json, rewritten atomically: a temp file in out, then os.replace."""
        st = {"rt": round(t, 3), "connected": self.ws is not None, "messages": self.messages,
              "last_message_rt": None if self.last_rt is None else round(self.last_rt, 3),
              "window_open": self.window, "markets": sorted(self.markets), "sids": sorted(self.sids),
              "drops": self.drops, "gaps": self.gaps, "writing": self.fh_name, "free_gb": self.free_gb,
              "paused": self.paused}
        path = os.path.join(self.out, STATUS)
        try:
            with open(path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(st, fh)
            os.replace(path + ".tmp", path)
        except OSError as e:
            say(f"{STATUS}: {e!r}")

    def check_space(self, t, m):
        """Below MIN_FREE_GB free: close the socket and the hour file and record nothing (the bot shares this disk).
        Above MIN_FREE_GB + 2 again: carry on. Free space it can't read leaves things as they are."""
        self.space_at = m + SPACE_EVERY
        try:
            free = self.free_bytes(self.out) / GIB
        except Exception as e:
            self.free_gb = None
            say(f"free space: {e!r}")
            return
        self.free_gb = round(free, 2)
        if not self.paused and free < MIN_FREE_GB:
            self.paused = True
            self.close_socket()
            self.close_file()
            self.log(t, "low_space", free_gb=self.free_gb)
        elif self.paused and free > MIN_FREE_GB + 2:
            self.paused = False
            self.fails, self.retry_at = 0, -math.inf
            self.log(t, "resume", free_gb=self.free_gb)


# ------------------------------------------------------------------ main


def lock_posix(fd):
    """An exclusive flock on fd, or OSError (BlockingIOError) at once if another open file holds one."""
    import fcntl
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def lock_windows(fd):
    """An exclusive lock on fd's first byte, or OSError at once if another handle holds it. msvcrt locks from the
    file's position, so it goes to byte 0 first."""
    import msvcrt
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)


def lock_out(out, lock=None):
    """Lock <out>/recorder.lock (out is made if missing), so two recorders can never write in one folder. Returns the
    open lock file, which holds the lock until it is closed or the process ends however it ends (the OS lets go of
    it), with this process's pid written in it; None, with the file as it was, when another process holds it.
    lock(fd) takes the OS's lock or raises OSError: lock_posix (flock) by default, lock_windows on Windows."""
    lock = lock or (lock_windows if os.name == "nt" else lock_posix)
    os.makedirs(out, exist_ok=True)
    fh = open(os.path.join(out, LOCK), "a+", encoding="utf-8")   # a+: opening never empties it
    try:
        lock(fh.fileno())
    except OSError:
        fh.close()
        return None
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    return fh


def lock_holder(out):
    """The pid written in <out>/recorder.lock, or None if there is none or it can't be read (on Windows the lock
    itself stops another process reading it)."""
    try:
        with open(os.path.join(out, LOCK), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def midnight(day):
    """Epoch seconds of midnight UTC as the day YYYY-MM-DD starts."""
    try:
        return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        raise argparse.ArgumentTypeError(f"{day!r} isn't a date like 2026-11-28") from None


def make_connect(key_id, key):
    """connect() for the Recorder: a signed, read-only socket on Kalshi's WebSocket, with a 1 s recv timeout.
    websocket-client's UTF-8 check is skipped: in pure Python it costs about 40 us a message, some 14% of a CPU at
    3,300 messages a second; the text is still decoded as UTF-8, and a bad frame drops the socket."""
    def connect():
        ws = websocket.create_connection(WS_URL, header=ws_headers(key_id, key, int(time.time() * 1000)), timeout=10,
                                         skip_utf8_validation=True)
        ws.settimeout(1)
        return ws
    return connect


def main(argv=None):
    p = argparse.ArgumentParser(prog="maker_shadow.py",
                                description="Record Kalshi's order book and trades for the bot's 16 markets. Read only.")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("record", help="record until --until, or forever")
    r.add_argument("--out", required=True, help="the folder it writes in, and the only one")
    r.add_argument("--env-file", default=DEFAULT_ENV,
                   help="the bot's .env, for KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH (default: %(default)s)")
    r.add_argument("--until", type=midnight, help="YYYY-MM-DD: stop at midnight UTC as that day starts")
    a = p.parse_args(argv)

    env_path = os.path.expanduser(a.env_file)
    cfg = read_env(env_path)
    key_id, key_path = cfg.get("KALSHI_API_KEY_ID"), cfg.get("KALSHI_PRIVATE_KEY_PATH")
    if not key_id or not key_path:
        print(f"{env_path} needs KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH: Kalshi's WebSocket wants a key even "
              "for public market data", file=sys.stderr)
        return 2
    if websocket is None:
        print("websocket-client isn't installed (pip install websocket-client)", file=sys.stderr)
        return 2
    key_path = os.path.join(os.path.dirname(os.path.abspath(env_path)), os.path.expanduser(key_path))
    try:
        key = load_key(key_path)
    except Exception as e:
        print(f"can't read the key {key_path}: {e!r}", file=sys.stderr)
        return 2
    lock = lock_out(a.out)
    if lock is None:                     # exit 3, having changed nothing: the other recorder's files are its own
        pid = lock_holder(a.out)
        held = os.path.join(os.path.abspath(a.out), LOCK)
        print(f"another recorder is already writing in {os.path.abspath(a.out)}: it holds {held}"
              f"{f' (pid {pid})' if pid else ''}. Not starting a second one.", file=sys.stderr)
        return 3
    try:
        client = Kalshi("prod", timeout=(REST_CONNECT, REST_TIMEOUT))   # REST: public GETs, no key
        rec = Recorder(a.out, client, make_connect(key_id, key), until=a.until)
        signal.signal(signal.SIGTERM, lambda signum, frame: rec.stop())   # systemd's stop: close the hour file cleanly
        rec.run()
    finally:
        lock.close()
    return 0


if __name__ == "__main__":   # pragma: no cover
    sys.exit(main())
