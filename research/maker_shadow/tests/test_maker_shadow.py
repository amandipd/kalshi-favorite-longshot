"""maker_shadow.py, the recorder: Kalshi's order book and trade tape for the bot's 16 markets, written raw.

The maker shadow test (SPEC.md, "Why") replays the real book with a pretend resting order at minute 8. This file
tests the half that runs on the server for a month: it lists each window's markets, subscribes to their
orderbook_delta and trade channels, writes every WebSocket message as it came into hourly gzip files, asks for the
results, and keeps status.json and events.jsonl. Spec: SPEC.md, "maker_shadow.py: the recorder".

Everything is offline. The socket, the REST client, the clock, sleep and the free-space reading are all fakes; the
clock moves only when a fake moves it (recv waits up to 1 s, sleep sleeps). The REST client is strict: touching
anything on it but markets(**params) and get(path) raises a BaseException, so the recorder's own `except Exception`
can't hide it. conftest.py's guard makes any real socket connection fail. Every test writes only in its tmp_path.

Readings of the spec (the contract where it leaves a choice):

- One REST call per step at most, so the socket is read between calls (REST_GAP apart means a step never sleeps
  between calls). The "at most 40 result calls per step" cap therefore always holds.
- A step reads messages until recv has nothing for a second, or for STEP_MAX s at most, so a busy feed can't starve
  the listing, results, status or flushes.
- A listing round asks each missing series once, REST_GAP apart. The socket is resubscribed when a round that found
  new markets ends, not after each market (16 resubscribes a window would be 16 bursts of snapshots). A round starts
  LIST_RETRY s after the last one started.
- A subscribe is never sent with an empty market list: Kalshi reads no market_tickers as every market.
- seq is tracked on every message with a sid and a seq except the four control types (subscribed, unsubscribed, ok,
  error), which are parsed in full instead. A gap on a sid the recorder holds resubscribes; a gap on any other sid (a
  late message from one it already unsubscribed) is only logged. Resubscribes after gaps are at least RESUB_MIN s
  apart, so a storm of gaps can't spam Kalshi with commands from the bot's own IP and key.
- A `subscribed` answering one of this socket's subscribe commands that has since been replaced is unsubscribed at
  once: otherwise two subscriptions would send every delta twice, and the replay would apply each twice.
- "While subscribed" means a subscribe for a non-empty market list was sent on this socket. The QUIET_SOCKET clock
  starts at the later of that subscribe and the last message, and is checked only when recv has nothing.
- Reconnect waits: RETRY[k - 1] after the k-th failure in a row (drops and failed connects both count), 30 s after
  the fifth. A socket that stays up HEALTHY s resets the count, so a socket Kalshi accepts and then closes at once
  backs off instead of reconnecting every second. Waits are slept in pieces of at most 1 s, so listing, results and
  status carry on meanwhile.
- recv returning "" (websocket-client's answer to a close frame) is a dead socket.
- Hour files: when the hour's name is taken, the next n after the highest one there for that hour, opened with
  exclusive create. So a later file always sorts later, even after pull.py has moved the earlier ones away.
- status.json is rewritten every STATUS_EVERY s and also the moment an hour file opens or closes, so "writing" is
  never stale when pull.py looks.
- A message with a raw newline in it (never seen from Kalshi; JSON can't need one) has it replaced by a space, so a
  line is always one message.
- free_gb is in GiB (2**30 bytes), the stricter reading. free_bytes(path) is given the out folder. While paused
  there are no REST calls either (nothing is recorded); status.json is still rewritten.
- A market not yet settled is asked again at most every RESULTS_RETRY s (otherwise one market that never settles
  would be asked twice a second for 6 hours).
- settled() accepts the whole GET /markets/{ticker} answer ({"market": {...}}) or the market itself.
- window_markets(): "within 1 s" is inclusive; a market without a ticker, or with a time that doesn't parse, is
  skipped like one missing a time.
- read_env(): a line without "=" is skipped, a UTF-8 BOM is ignored, the value is everything after the first "=".
- Two events beyond the spec's list: "stop" (why) when run() returns, and "exception" (why) when a step raised and
  run() recovered (the socket is dropped and the hour file closed, so the next file starts clean).
- The CLI: connect passes skip_utf8_validation=True as well (websocket-client's pure-Python UTF-8 check costs about
  40 us a message, some 14% of a CPU at 3,300 messages a second; decoding still fails on bad UTF-8, which drops the
  socket). A relative KALSHI_PRIVATE_KEY_PATH is read from the env file's folder. SIGTERM ends run() cleanly, so the
  hour file is closed complete. A missing key, key file or websocket-client returns 2 with a message.
- Two clocks (added in review): every timer runs on mono (reconnect waits, flushes, status.json, space checks,
  REST_GAP, QUIET_SOCKET, RESUB_MIN, HEALTHY, STEP_MAX); receive times, the window, the hour, results and until stay
  on now(). The fake Clock's mono() starts far from now(), so a mix-up of the two breaks tests.
- rest_slow: a REST call's time is measured on mono from just before the call to just after it, failed or not, and
  logged when over REST_SLOW s, with "series" (a listing) or "ticker" (a result) and "seconds" (to 0.01).
- not_listed: logged when listing stops for a window (QUIET[0] - REST_STOP), only if a round was started in it: a
  recorder that joined after that, or was paused all along, asked nothing, so says nothing. Fields: window_open,
  series (in SERIES order) and rounds (rounds started in that window).
- auth_failed: a handshake refused with 401 or 403 (the exception's status_code when it has one, which wins; else a
  whole "401" or "403" in its message). It still counts as a failure in a row for the RETRY waits that follow. A
  failed connect's "why" is cut to 500 characters, since a refused handshake's message carries Kalshi's headers.
- recorder.lock is taken by the CLI after the .env and key checks, before the Recorder is made, and holds the pid.
  Held by another process: exit 3 with a message on stderr, the lock file opened but unchanged and nothing else
  touched. The Recorder itself takes no lock, so the tests' many recorders don't need one.

    python -m pytest research/maker_shadow/tests/test_maker_shadow.py -q
"""

from __future__ import annotations

import base64
import bisect
import gzip
import importlib
import inspect
import json
import os
import posixpath
import signal
import subprocess
import sys
import time
import zlib
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

UTC = timezone.utc
H0 = 1_793_037_600          # 2026-10-26T18:00:00Z: an hour start, so a window start too
SPEC_SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M", "KXNEAR15M",
               "KXZEC15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXCOPPER15M", "KXWTI15M",
               "KXNATGAS15M")
F18 = "ws-20261026T18.txt.gz"
F19 = "ws-20261026T19.txt.gz"
_loads = json.loads          # the fakes' own, untouched when a test counts the recorder's json.loads


@pytest.fixture(scope="module")
def ms():
    """maker_shadow, imported in the fixture so a missing module fails each test cleanly."""
    return importlib.import_module("maker_shadow")


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


# ------------------------------------------------------------------ Kalshi, faked


def iso(t, frac=False):
    d = datetime.fromtimestamp(t, UTC)
    return d.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" if frac else d.strftime("%Y-%m-%dT%H:%M:%SZ")


def ticker_of(series, window):
    return f"{series}-{int(window)}"


def close_of(ticker):
    return int(ticker.rsplit("-", 1)[1]) + 900


def market_raw(series, window):
    """A market as GET /markets lists it (a few of Kalshi's fields: the recorder keeps them all as `raw`)."""
    return {"ticker": ticker_of(series, window), "event_ticker": f"{series}-E{int(window)}", "status": "active",
            "open_time": iso(window), "close_time": iso(window + 900), "tick_size": 1,
            "price_level_structure": "linear_cent", "yes_bid_dollars": "0.9500", "fee_waiver_expiration_time": None}


def market_line(series, window):
    """A markets.jsonl line as the recorder writes it (for restart tests)."""
    return {"ticker": ticker_of(series, window), "series": series, "open": float(window),
            "close": float(window + 900), "raw": market_raw(series, window), "window_open": window}


class Clock:
    """The recorder's now(), mono() and sleep(): time moves only when a fake moves it. now() is the wall clock. mono()
    is the monotonic one: it moves with now(), starts far from it (so code that mixes the two up breaks tests), and
    ignores jump()."""

    def __init__(self, t):
        self.t = float(t)
        self.skew = self.t - 1000.0   # mono() = t - skew: 1000.0 at the start
        self.sleeps = []          # (when, seconds)
        self.on_sleep = None

    def now(self):
        return self.t

    def mono(self):
        return self.t - self.skew

    def jump(self, s):
        """The wall clock steps by s (NTP correcting it, say); the monotonic clock doesn't move."""
        self.t += s
        self.skew += s

    def sleep(self, s):
        assert 0 <= s <= 30, f"slept {s} s"
        self.sleeps.append((self.t, s))
        self.t += s
        if self.on_sleep:
            self.on_sleep(self.t)


Call = namedtuple("Call", "t kind arg")


class Exchange:
    """What Kalshi's REST API knows: each window's market in each series, and when their results are out."""

    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.absent = set()        # series that list nothing
        self.late = {}             # series -> seconds into a window before its market lists
        self.fail_once = {}        # series -> "none" | "raise": how its next listing fails
        self.settle_after = 30     # a market's result is out this long after it closes; None: never
        self.result = "yes"

    def listing(self, params):
        s = params["series_ticker"]
        w = params["min_close_ts"] - 899
        how = self.fail_once.pop(s, None)
        if how == "none":
            return None
        if how == "raise":
            raise ConnectionError("Kalshi didn't answer")
        if s in self.absent or self.clock.t - w < self.late.get(s, 0):
            return {"markets": [], "cursor": ""}
        return {"markets": [market_raw(s, w)], "cursor": ""}

    def market(self, path):
        assert path.startswith("/markets/"), path
        ticker = path[len("/markets/"):]
        if self.settle_after is not None and self.clock.t >= close_of(ticker) + self.settle_after:
            return {"market": {"ticker": ticker, "status": "finalized", "result": self.result}}
        return {"market": {"ticker": ticker, "status": "closed", "result": ""}}

    def of(self, kind):
        return [c for c in self.calls if c.kind == kind]


class Forbidden(BaseException):
    """The recorder touched the client outside markets(**params) and get(path). A BaseException, so the
    recorder's `except Exception` (which keeps it alive after a bad answer) can't swallow it."""


class Rest:
    """A strict kalshi.Kalshi: markets(**params) and get(path), nothing else, not even reading an attribute."""

    def __init__(self, ex):
        self.__dict__["ex"] = ex

    def markets(self, **params):
        ex = self.ex
        ex.calls.append(Call(ex.clock.t, "markets", params))
        return ex.listing(params)

    def get(self, path, *args, **kwargs):
        ex = self.ex
        if args or kwargs:
            raise Forbidden(f"client.get({path!r}, {args}, {kwargs}): only a plain public GET of the path")
        ex.calls.append(Call(ex.clock.t, "get", path))
        return ex.market(path)

    def __getattr__(self, name):
        raise Forbidden(f"the recorder used client.{name}")

    def __setattr__(self, name, value):
        raise Forbidden(f"the recorder set client.{name}")


BOOK = {"yes_dollars_fp": [["0.9200", "150.00"], ["0.9100", "20.00"]], "no_dollars_fp": [["0.0500", "40.00"]]}
DELTA = {"price_dollars": "0.9300", "delta_fp": "-25.00", "side": "yes", "ts_ms": 1793037680123}
TRADE = {"trade_id": "t-1", "yes_price_dollars": "0.9300", "no_price_dollars": "0.0700", "count_fp": "12.00",
         "taker_side": "no", "ts_ms": 1793037681456}
BODIES = {"orderbook_snapshot": BOOK, "orderbook_delta": DELTA, "trade": TRADE}


class Net:
    """connect(): a new FakeSocket each time, or the next exception in `refuse`."""

    def __init__(self, clock):
        self.clock = clock
        self.sockets = []
        self.connects = []
        self.refuse = []
        self.ack = True            # answer subscribe and unsubscribe the way Kalshi does
        self.snapshots = True      # and send a snapshot of each market after subscribing
        self.timeout = TimeoutError
        self.last_sid = 0

    def __call__(self):
        self.connects.append(self.clock.t)
        if self.refuse:
            raise self.refuse.pop(0)
        s = FakeSocket(self)
        self.sockets.append(s)
        return s

    def next_sid(self):
        self.last_sid += 1
        return self.last_sid

    def commands(self, kind=None):
        return [c for s in self.sockets for c in s.commands(kind)]


class FakeSocket:
    """Kalshi's WebSocket as websocket-client shows it: send(text), recv() (one message, or a timeout after up to a
    second with nothing), close(). Messages wait in `inbox` with the time they arrive."""

    def __init__(self, net):
        self.net, self.clock = net, net.clock
        self.sent = []             # (when, command dict)
        self.inbox = []            # (arrives at, text or exception)
        self.delivered = []        # (when, text): what recv returned
        self.closed = False
        self.seq = {}
        self.channel = {}          # sid -> channel, for the subscriptions this socket acknowledged
        self.recvs = 0
        self.fail_send = None
        self.fail_close = None

    def send(self, text):
        if self.closed:
            raise ConnectionError("send on a closed socket")
        if self.fail_send:
            raise self.fail_send
        cmd = _loads(text)
        self.sent.append((self.clock.t, cmd))
        p = cmd.get("params") or {}
        if cmd.get("cmd") == "subscribe" and self.net.ack:
            book = None
            for ch in p["channels"]:
                sid = self.net.next_sid()
                self.channel[sid] = ch
                book = sid if ch == "orderbook_delta" else book
                self.push(json.dumps({"id": cmd["id"], "type": "subscribed", "msg": {"channel": ch, "sid": sid}}))
            if self.net.snapshots and book is not None:
                for t in p["market_tickers"]:
                    self.emit("orderbook_snapshot", book, t)
        elif cmd.get("cmd") == "unsubscribe" and self.net.ack:
            for sid in p["sids"]:
                self.channel.pop(sid, None)
                # Kalshi's answer carries a seq of its own: a control message, never counted as a gap
                self.push(json.dumps({"id": cmd["id"], "sid": sid, "seq": 999, "type": "unsubscribed"}))

    def push(self, item, at=None):
        at = self.clock.t if at is None else at
        keys = [a for a, _ in self.inbox]
        self.inbox.insert(bisect.bisect_right(keys, at), (at, item))

    def emit(self, kind, sid, ticker, at=None, seq=None, **body):
        seq = self.seq.get(sid, 0) + 1 if seq is None else seq
        self.seq[sid] = seq
        text = json.dumps({"type": kind, "sid": sid, "seq": seq,
                           "msg": {"market_ticker": ticker, **(body or BODIES.get(kind, {}))}})
        self.push(text, at)
        return text

    def recv(self):
        if self.closed:
            raise ConnectionError("recv on a closed socket")
        self.recvs += 1
        if self.inbox and self.inbox[0][0] <= self.clock.t + 1.0:
            at, item = self.inbox.pop(0)
            self.clock.t = max(self.clock.t, at)
            if isinstance(item, BaseException):
                raise item
            self.delivered.append((self.clock.t, item))
            return item
        self.clock.t += 1.0
        raise self.net.timeout("nothing this second")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise self.fail_close

    def sids(self, channel):
        return [s for s, ch in self.channel.items() if ch == channel]

    @property
    def book_sid(self):
        return self.sids("orderbook_delta")[-1]

    def commands(self, kind=None):
        return [c for _, c in self.sent if kind is None or c["cmd"] == kind]


class World:
    """A recorder wired to the fakes, writing into tmp_path/out."""

    def __init__(self, ms, tmp_path, t0=H0, until=None, free_gb=100.0, out=None):
        self.ms = ms
        self.clock = Clock(t0)
        self.ex = Exchange(self.clock)
        self.client = Rest(self.ex)
        self.net = Net(self.clock)
        self.free_gb = free_gb
        self.space_error = None
        self.space_reads = []
        self.out = Path(out) if out else Path(tmp_path) / "out"
        self.rec = ms.Recorder(str(self.out), self.client, self.net, now=self.clock.now, mono=self.clock.mono,
                               sleep=self.clock.sleep, until=until, free_bytes=self.free_bytes)

    def free_bytes(self, path):
        self.space_reads.append((self.clock.t, path))
        if self.space_error:
            raise self.space_error
        return self.free_gb * 2 ** 30

    def run_to(self, t, limit=100_000):
        for _ in range(limit):
            if self.clock.t >= t:
                return
            self.rec.step()
        raise AssertionError("the recorder stopped moving time forward")

    @property
    def sock(self):
        return self.net.sockets[-1]

    def events(self, kind=None):
        return [e for e in jsonl(self.out / "events.jsonl") if kind is None or e["event"] == kind]

    def status(self):
        return json.loads((self.out / "status.json").read_text(encoding="utf-8"))

    def tickers(self, window=H0, series=SPEC_SERIES):
        return sorted(ticker_of(s, window) for s in series)


@pytest.fixture
def world(ms, tmp_path, monkeypatch):
    """World(...) maker. The fake feed is far quieter than Kalshi's (which sends deltas all the time), so the
    QUIET_SOCKET rule is turned off unless a test asks for it with quiet_socket=True."""
    def make(quiet_socket=False, **kwargs):
        if not quiet_socket:
            monkeypatch.setattr(ms, "QUIET_SOCKET", 10 ** 9)
        return World(ms, tmp_path, **kwargs)
    return make


def jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def partial_lines(path):
    """The lines of a gzip stream that may still be open: everything up to its last flush."""
    data = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(Path(path).read_bytes())
    return data.decode("utf-8").split("\n")[:-1]


def full_lines(path):
    """The lines of a complete gzip file: raises if it was never closed."""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert text.endswith("\n") or text == ""
    return text.split("\n")[:-1]


def line(rt, text):
    return f"{rt:.3f} {text}"


def assert_rest_spaced(ms, calls):
    times = [c.t for c in calls]
    assert all(b - a >= ms.REST_GAP - 1e-9 for a, b in zip(times, times[1:])), times


def assert_never_quiet(ms, calls):
    bad = [(c.kind, c.t - ms.window_of(c.t)) for c in calls if ms.quiet(c.t) or not ms.rest_ok(c.t)]
    assert bad == [], f"REST calls inside QUIET or the REST_STOP s before it (seconds into the window): {bad}"


# ------------------------------------------------------------------ constants, and nothing that trades


def test_constants_are_the_specs(ms):
    assert ms.SERIES == SPEC_SERIES
    assert ms.WS_URL == "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
    assert ms.WS_PATH == "/trade-api/ws/v2"
    assert (ms.WINDOW, tuple(ms.QUIET), ms.LIST_AT, ms.LIST_RETRY) == (900, (420, 600), 15, 30)
    assert (ms.RESULTS_AFTER, ms.RESULTS_GIVE_UP, ms.REST_GAP) == (120, 6 * 3600, 0.5)
    assert (ms.REST_CONNECT, ms.REST_TIMEOUT, ms.REST_STOP, ms.REST_SLOW) == (0.5, 3, 60, 1)
    assert (ms.QUIET_SOCKET, tuple(ms.RETRY), ms.STATUS_EVERY, ms.AUTH_WAIT) == (30, (1, 2, 5, 10, 30), 30, 900)
    assert (ms.GZIP_LEVEL, ms.FLUSH_EVERY, ms.SPACE_EVERY, ms.MIN_FREE_GB) == (3, 5, 60, 15)


def test_the_module_has_no_way_to_trade(ms):
    """No order, cancel, POST or DELETE anywhere in the source: the strict client catches calls, this the intent."""
    src = inspect.getsource(ms)
    for word in (".post(", ".delete(", "create_order", "cancel_order", "transfer(", "batch_cancel", "amend"):
        assert word not in src, word


# ------------------------------------------------------------------ pure helpers


def test_window_of_rounds_down_to_the_window(ms):
    assert ms.window_of(H0) == H0
    assert ms.window_of(H0 + 0.001) == H0
    assert ms.window_of(H0 + 899.999) == H0
    assert ms.window_of(H0 + 900) == H0 + 900
    assert ms.window_of(H0 - 0.5) == H0 - 900


def test_quiet_is_seconds_420_to_600_of_each_window(ms):
    assert not ms.quiet(H0 + 419.999)
    assert ms.quiet(H0 + 420)
    assert ms.quiet(H0 + 599.999)
    assert not ms.quiet(H0 + 600)
    assert not ms.quiet(H0)
    assert ms.quiet(H0 + 900 + 500)
    assert not ms.quiet(H0 + 900 + 15)


def test_hour_file_names_the_utc_hour(ms):
    assert ms.hour_file(H0) == F18
    assert ms.hour_file(H0 + 3599.999) == F18
    assert ms.hour_file(H0 + 3600) == F19
    assert ms.hour_file(H0 + 6 * 3600) == "ws-20261027T00.txt.gz"
    assert ms.hour_file(H0 + 6 * 3600 - 0.001) == "ws-20261026T23.txt.gz"


def test_peek_reads_type_sid_and_seq_without_parsing(ms):
    delta = '{"type": "orderbook_delta", "sid": 7, "seq": 2, "msg": {"market_ticker": "T", "price_dollars": "0.9300"}}'
    assert ms.peek(delta) == ("orderbook_delta", 7, 2)
    assert ms.peek('{"type":"trade","sid":8,"seq":5,"msg":{"trade_id":"x","market_ticker":"T"}}') == ("trade", 8, 5)
    snap = json.dumps({"type": "orderbook_snapshot", "sid": 123456, "seq": 98765432,
                       "msg": {"market_ticker": "T", "yes_dollars_fp": [["0.%04d" % i, "1.00"] for i in range(2000)]}})
    assert ms.peek(snap) == ("orderbook_snapshot", 123456, 98765432)
    assert ms.peek('{ "type" : "trade" , "sid" : 3 , "msg": {} }') == ("trade", 3, None)        # no seq
    sub = ms.peek('{"id": 1, "type": "subscribed", "msg": {"channel": "trade", "sid": 8}}')
    assert sub[0] == "subscribed" and sub[2] is None
    assert ms.peek('{"id": 4, "type": "error", "msg": {"code": 6, "msg": "Already subscribed"}}') == ("error", None, None)
    assert ms.peek('{"msg": {"market_ticker": "T"}, "seq": 9, "sid": 2, "type": "orderbook_delta"}') == (
        "orderbook_delta", 2, 9)                                                   # any key order
    assert ms.peek('{"market_type": "binary"}') == (None, None, None)               # "type" is a whole key
    assert ms.peek("not json at all") == (None, None, None)
    assert ms.peek("") == (None, None, None)


def test_read_env_reads_key_value_lines(ms, tmp_path):
    env = tmp_path / ".env"
    env.write_text("﻿# the bot's settings\n"
                   "KALSHI_ENV=prod\n"
                   "\n"
                   "KALSHI_API_KEY_ID = abc-123  \n"
                   'KALSHI_PRIVATE_KEY_PATH="/home/kalshi/kalshi/bot/keys/prod.pem"\n'
                   "   # an indented comment\n"
                   "  SPACED  =  'a quoted value'  \n"
                   "EMPTY=\n"
                   "NO_EQUALS_SIGN\n"
                   "URL=https://example.com/x?a=b\n", encoding="utf-8")
    assert ms.read_env(str(env)) == {"KALSHI_ENV": "prod", "KALSHI_API_KEY_ID": "abc-123",
                                     "KALSHI_PRIVATE_KEY_PATH": "/home/kalshi/kalshi/bot/keys/prod.pem",
                                     "SPACED": "a quoted value", "EMPTY": "", "URL": "https://example.com/x?a=b"}
    assert ms.read_env(str(tmp_path / "missing.env")) == {}


def test_ws_headers_sign_timestamp_get_and_the_ws_path(ms, rsa_key):
    h = ms.ws_headers("key-id", rsa_key, 1793037600123)
    assert set(h) == {"KALSHI-ACCESS-KEY", "KALSHI-ACCESS-TIMESTAMP", "KALSHI-ACCESS-SIGNATURE"}
    assert h["KALSHI-ACCESS-KEY"] == "key-id"
    assert h["KALSHI-ACCESS-TIMESTAMP"] == "1793037600123"
    rsa_key.public_key().verify(base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"]),
                                b"1793037600123GET/trade-api/ws/v2",
                                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                                hashes.SHA256())
    ed = ed25519.Ed25519PrivateKey.generate()
    h = ms.ws_headers("k2", ed, 5)
    ed.public_key().verify(base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"]), b"5GET/trade-api/ws/v2")


def test_window_markets_keeps_this_windows_markets_with_their_raw_fields(ms):
    w = H0 + 900
    exact = market_raw("KXBTC15M", w)
    half = {**market_raw("KXBTC15M", w), "ticker": "HALF",
            "open_time": datetime.fromtimestamp(w + 0.5, UTC).isoformat(timespec="milliseconds"),
            "close_time": datetime.fromtimestamp(w + 900, UTC).isoformat()}           # "+00:00" forms
    milli = {**market_raw("KXBTC15M", w), "ticker": "MILLI", "open_time": iso(w, frac=True)}
    nxt = {**market_raw("KXBTC15M", w + 900), "ticker": "NEXT"}
    early = {**market_raw("KXBTC15M", w), "ticker": "EARLY", "open_time": iso(w - 2)}
    no_open = {k: v for k, v in market_raw("KXBTC15M", w).items() if k != "open_time"}
    no_close = {k: v for k, v in market_raw("KXBTC15M", w).items() if k != "close_time"}
    no_ticker = {k: v for k, v in market_raw("KXBTC15M", w).items() if k != "ticker"}
    junk = {**market_raw("KXBTC15M", w), "ticker": "JUNK", "close_time": "soon"}
    got = ms.window_markets({"markets": [exact, half, milli, nxt, early, no_open, no_close, no_ticker, junk, "x"]},
                            "KXBTC15M", w)
    assert [m["ticker"] for m in got] == [exact["ticker"], "HALF", "MILLI"]
    for m in got:
        assert set(m) == {"ticker", "series", "open", "close", "raw"}
        assert m["series"] == "KXBTC15M"
        assert m["close"] == pytest.approx(w + 900)
        assert isinstance(m["open"], float) and isinstance(m["close"], float)
    assert got[0]["open"] == w and got[1]["open"] == pytest.approx(w + 0.5)
    assert got[0]["raw"] == exact and got[1]["raw"] == half
    assert ms.window_markets(None, "KXBTC15M", w) == []
    assert ms.window_markets({}, "KXBTC15M", w) == []
    assert ms.window_markets({"markets": None}, "KXBTC15M", w) == []
    assert ms.window_markets(["not", "a", "dict"], "KXBTC15M", w) == []


def test_settled_gives_the_result_once_it_is_yes_or_no(ms):
    assert ms.settled({"market": {"ticker": "T", "result": "yes", "status": "finalized"}}) == ("yes", "finalized")
    assert ms.settled({"market": {"ticker": "T", "result": "no", "status": "settled"}}) == ("no", "settled")
    assert ms.settled({"market": {"ticker": "T", "result": "", "status": "closed"}}) is None
    assert ms.settled({"market": {"ticker": "T", "status": "active"}}) is None
    assert ms.settled({"market": {"ticker": "T", "result": "void", "status": "finalized"}}) is None
    assert ms.settled({"market": None}) is None
    assert ms.settled(None) is None
    assert ms.settled({"result": "yes", "status": "determined"}) == ("yes", "determined")     # the market itself


# ------------------------------------------------------------------ listing


def test_listing_waits_for_LIST_AT_then_asks_every_series_once(ms, world):
    w = world()
    w.run_to(H0 + ms.LIST_AT - 0.01)
    assert w.ex.of("markets") == []
    w.run_to(H0 + 60)
    calls = w.ex.of("markets")
    assert sorted(c.arg["series_ticker"] for c in calls) == sorted(SPEC_SERIES)
    assert H0 + ms.LIST_AT <= calls[0].t < H0 + ms.LIST_AT + 1.5
    for c in calls:
        assert c.arg == {"series_ticker": c.arg["series_ticker"], "min_close_ts": H0 + 899, "max_close_ts": H0 + 901,
                         "limit": 50}
        assert all(isinstance(c.arg[k], int) for k in ("min_close_ts", "max_close_ts", "limit"))
    assert_rest_spaced(ms, calls)
    lines = jsonl(w.out / "markets.jsonl")
    assert sorted(m["ticker"] for m in lines) == w.tickers()
    for m in lines:
        assert set(m) == {"ticker", "series", "open", "close", "raw", "window_open"}
        assert m["window_open"] == H0 and m["open"] == H0 and m["close"] == H0 + 900
        assert m["raw"] == market_raw(m["series"], H0)


def test_listing_retries_missing_series_every_LIST_RETRY_until_QUIET_then_gives_up(ms, world):
    w = world()
    w.ex.late = {"KXGOLD15M": 100}
    w.ex.absent = {"KXNATGAS15M"}
    w.run_to(H0 + 900)
    calls = w.ex.of("markets")
    offsets = [c.t - H0 for c in calls]
    assert all(ms.LIST_AT <= o < ms.QUIET[0] - ms.REST_STOP for o in offsets), offsets
    gas = [c.t - H0 for c in calls if c.arg["series_ticker"] == "KXNATGAS15M"]
    gold = [c.t - H0 for c in calls if c.arg["series_ticker"] == "KXGOLD15M"]
    assert gas[0] < ms.LIST_AT + 17 and gas[-1] >= ms.QUIET[0] - ms.REST_STOP - ms.LIST_RETRY - 3
    assert all(ms.LIST_RETRY <= b - a <= ms.LIST_RETRY + 2 for a, b in zip(gas, gas[1:])), gas
    assert gold[-2] < 100 <= gold[-1] and len(gold) == 4                # found on the fourth round
    others = [c for c in calls if c.arg["series_ticker"] not in ("KXGOLD15M", "KXNATGAS15M")]
    assert len(others) == 14                                            # each found on its first try
    lines = jsonl(w.out / "markets.jsonl")
    assert sorted(m["ticker"] for m in lines) == w.tickers(series=[s for s in SPEC_SERIES if s != "KXNATGAS15M"])
    (gave_up,) = w.events("not_listed")                                 # the one series never found, said once
    assert (gave_up["window_open"], gave_up["series"]) == (H0, ["KXNATGAS15M"]) and gave_up["rounds"] >= 10
    assert H0 + ms.QUIET[0] - ms.REST_STOP <= gave_up["rt"] < H0 + ms.QUIET[0] - ms.REST_STOP + 1.5
    w.run_to(H0 + 900 + 60)                                             # the next window lists afresh
    nxt = [c for c in w.ex.of("markets") if c.t >= H0 + 900]
    assert sorted(c.arg["series_ticker"] for c in nxt) == sorted(SPEC_SERIES)
    assert all(c.arg["min_close_ts"] == H0 + 1799 for c in nxt)
    assert all(c.t >= H0 + 900 + ms.LIST_AT for c in nxt)
    assert len(w.events("not_listed")) == 1


def test_every_series_still_missing_is_named_once_a_window(ms, world):
    w = world()
    w.ex.absent = {"KXNATGAS15M", "KXBTC15M"}
    w.run_to(H0 + 2 * 900)
    ev = w.events("not_listed")
    assert [(e["window_open"], e["series"]) for e in ev] == [(H0, ["KXBTC15M", "KXNATGAS15M"]),
                                                              (H0 + 900, ["KXBTC15M", "KXNATGAS15M"])]


def test_no_not_listed_when_every_series_is_found_or_listing_never_began(ms, world, tmp_path):
    w = world()
    w.run_to(H0 + 900)                                   # all 16 found in the first round
    assert w.events("not_listed") == []
    late = world(t0=H0 + ms.QUIET[0] - ms.REST_STOP + 1, out=tmp_path / "late")   # joined after listing stopped
    late.run_to(H0 + 900 + ms.QUIET[0])
    assert late.ex.of("markets") and late.events("not_listed") == []


def test_rest_ok_stops_new_calls_REST_STOP_seconds_before_QUIET(ms):
    w = 1793037600
    for into, ok in [(0, True), (ms.QUIET[0] - ms.REST_STOP - 0.01, True), (ms.QUIET[0] - ms.REST_STOP, False),
                     (ms.QUIET[0], False), (ms.QUIET[1] - 0.01, False), (ms.QUIET[1], True), (899.99, True)]:
        assert ms.rest_ok(w + into) is ok, into


KALSHI_ADDRESSES = 8         # what Kalshi's REST host resolves to; requests' connect timeout applies to each in turn


def test_a_REST_call_that_keeps_retrying_still_ends_before_QUIET(ms, monkeypatch):
    """The worst case, from the real kalshi.Kalshi.get with Kalshi unreachable: each try may spend the connect
    timeout on every one of the host's addresses, then the read timeout; it sleeps after each failed try. Today:
    4 x (8 x 0.5 + 3) + (1 + 2 + 3 + 4) = 38 s, inside REST_STOP, so a call started just before it ends before QUIET."""
    kalshi = sys.modules[ms.Kalshi.__module__]         # the kalshi.py the recorder imported
    tries, sleeps = [], []

    class Unreachable:
        def get(self, url, params=None, timeout=None, headers=None):
            tries.append(timeout)
            raise requests.ConnectionError("Kalshi is unreachable")

    monkeypatch.setattr(kalshi, "time", SimpleNamespace(sleep=sleeps.append, time=time.time))
    client = kalshi.Kalshi("prod", timeout=(ms.REST_CONNECT, ms.REST_TIMEOUT))
    client.http = Unreachable()
    assert client.get("/markets", {"series_ticker": "KXBTC15M"}) is None
    assert tries and all(t == (ms.REST_CONNECT, ms.REST_TIMEOUT) for t in tries)
    worst = len(tries) * (KALSHI_ADDRESSES * ms.REST_CONNECT + ms.REST_TIMEOUT) + sum(sleeps)
    assert worst < ms.REST_STOP, worst
    assert ms.REST_CONNECT <= 0.5 and ms.REST_TIMEOUT <= 5


def test_results_wait_out_the_minute_before_QUIET_too(ms, world):
    w = world()
    w.run_to(H0 + 900 + ms.QUIET[0] - ms.REST_STOP - 5)        # last window's results are due from 120 s in
    w.run_to(H0 + 900 + ms.QUIET[1] + 60)
    gets = [c.t - (H0 + 900) for c in w.ex.of("get")]
    assert gets, "no results were asked"
    assert not [o for o in gets if ms.QUIET[0] - ms.REST_STOP <= o < ms.QUIET[1]], gets


def test_a_failed_listing_is_logged_and_retried(ms, world):
    w = world()
    w.ex.fail_once = {"KXBTC15M": "none", "KXETH15M": "raise"}
    w.run_to(H0 + 80)
    failed = w.events("list_failed")
    assert sorted(e["series"] for e in failed) == ["KXBTC15M", "KXETH15M"]
    asked = [c.arg["series_ticker"] for c in w.ex.of("markets")]
    assert asked.count("KXBTC15M") == 2 and asked.count("KXETH15M") == 2
    assert sorted(m["ticker"] for m in jsonl(w.out / "markets.jsonl")) == w.tickers()


def test_a_round_cut_short_at_QUIET_subscribes_what_it_found_at_once(ms, world):
    stop = ms.QUIET[0] - ms.REST_STOP                     # the last moment a REST call may start
    w = world(t0=H0 + stop - 7)                           # 7 s left: room for 7 of the 16 series
    w.run_to(H0 + stop + 5)
    calls = w.ex.of("markets")
    assert 5 <= len(calls) <= 8 and all(c.t < H0 + stop for c in calls)
    found = sorted(ticker_of(c.arg["series_ticker"], H0) for c in calls)
    # the new socket subscribed the first market it knew; the cut-short round's end subscribes them all
    assert w.sock.commands("subscribe")[-1]["params"]["market_tickers"] == found
    assert H0 + stop <= w.sock.sent[-1][0] < H0 + stop + 1.5   # when calls stop, not a minute later at QUIET
    w.run_to(H0 + 900)
    assert len(w.ex.of("markets")) == len(calls)          # and none of the rest asked this window
    (gave_up,) = w.events("not_listed")                   # the ones never reached are named
    asked = {c.arg["series_ticker"] for c in calls}
    assert gave_up["series"] == [s for s in SPEC_SERIES if s not in asked] and gave_up["rounds"] == 1


def test_a_market_listed_twice_is_written_once(ms, world):
    w = world()
    real = w.ex.listing
    w.ex.listing = lambda params: (lambda d: d and {"markets": d["markets"] * 2})(real(params))
    w.run_to(H0 + 40)
    assert sorted(m["ticker"] for m in jsonl(w.out / "markets.jsonl")) == w.tickers()


def test_no_listing_in_a_window_it_joins_inside_QUIET(ms, world):
    w = world(t0=H0 + 430)
    w.ex.settle_after = None
    w.run_to(H0 + 3 * 900)
    assert_never_quiet(ms, w.ex.calls)
    assert [c for c in w.ex.of("markets") if c.arg["min_close_ts"] == H0 + 899] == []
    assert w.ex.of("get"), "the next windows' markets were asked for their results"
    assert_rest_spaced(ms, w.ex.calls)


def test_REST_calls_stay_REST_GAP_apart_and_on_time_while_the_feed_is_busy(ms, world):
    w = world()
    w.run_to(H0 + 10)
    for i in range(4000):                               # 100 messages a second for 40 s, on a sid it doesn't hold
        w.sock.emit("trade", 777, "X", at=H0 + 10 + i * 0.01)
    w.run_to(H0 + 50)
    calls = w.ex.of("markets")
    assert len(calls) == 16
    assert_rest_spaced(ms, calls)
    assert calls[-1].t - calls[0].t <= 15 * (ms.REST_GAP + 0.5)   # the busy socket didn't starve the listing
    assert w.events("gap") == []


# ------------------------------------------------------------------ subscribing


def test_it_subscribes_the_windows_markets_when_the_listing_round_ends(ms, world):
    w = world()
    w.run_to(H0 + 70)
    sock = w.sock
    assert sock.commands() == [{"id": 1, "cmd": "subscribe",
                                "params": {"channels": ["orderbook_delta", "trade"], "market_tickers": w.tickers()}}]
    last_listing = w.ex.of("markets")[-1].t
    assert last_listing <= sock.sent[0][0] < last_listing + 1.5
    ev = w.events("subscribe")
    assert len(ev) == 1 and ev[0]["tickers"] == w.tickers()
    st = w.status()
    assert st["sids"] == sorted(sock.channel) and len(st["sids"]) == 2
    assert st["markets"] == w.tickers() and st["window_open"] == H0


def test_new_markets_resubscribe_with_ids_counting_up(ms, world):
    w = world()
    w.ex.late = {"KXGOLD15M": 100}
    w.run_to(H0 + 140)
    sock = w.sock
    fifteen = w.tickers(series=[s for s in SPEC_SERIES if s != "KXGOLD15M"])
    assert sock.commands() == [
        {"id": 1, "cmd": "subscribe", "params": {"channels": ["orderbook_delta", "trade"], "market_tickers": fifteen}},
        {"id": 2, "cmd": "unsubscribe", "params": {"sids": [1, 2]}},
        {"id": 3, "cmd": "subscribe", "params": {"channels": ["orderbook_delta", "trade"],
                                                 "market_tickers": w.tickers()}}]
    assert sock.sent[1][0] >= H0 + 100


def test_a_new_window_unsubscribes_and_never_subscribes_an_empty_list(ms, world):
    w = world()
    w.run_to(H0 + 900 + 80)
    sock = w.sock
    cmds = sock.commands()
    assert [c["cmd"] for c in cmds] == ["subscribe", "unsubscribe", "subscribe"]
    unsub_at = sock.sent[1][0]
    assert H0 + 900 <= unsub_at < H0 + 901.5
    assert cmds[1]["params"] == {"sids": [1, 2]}
    assert cmds[2]["params"]["market_tickers"] == w.tickers(window=H0 + 900)
    assert sock.sent[2][0] >= H0 + 900 + ms.LIST_AT
    assert all(c["params"]["market_tickers"] for c in w.net.commands("subscribe"))


def test_an_empty_window_sends_no_subscribe(ms, world):
    w = world()
    w.ex.absent = set(SPEC_SERIES)
    w.run_to(H0 + 900 + 100)
    assert w.net.commands() == []
    assert len(w.net.connects) == 1 and w.events("drop") == []      # an idle socket isn't a dead one


def test_a_subscribed_answering_a_replaced_subscribe_is_unsubscribed(ms, world):
    w = world()
    w.net.ack = False                                    # Kalshi slow to answer the first subscribe
    w.ex.late = {"KXGOLD15M": 100}
    w.run_to(H0 + 130)
    sock = w.sock
    assert [c["cmd"] for c in sock.commands()] == ["subscribe", "subscribe"]     # no sids held: nothing to drop
    sock.push(json.dumps({"id": 1, "type": "subscribed", "msg": {"channel": "orderbook_delta", "sid": 50}}))
    sock.push(json.dumps({"id": 2, "type": "subscribed", "msg": {"channel": "orderbook_delta", "sid": 51}}))
    sock.push(json.dumps({"id": 2, "type": "subscribed", "msg": {"channel": "trade", "sid": 52}}))
    w.run_to(H0 + 170)
    assert sock.commands()[2:] == [{"id": 3, "cmd": "unsubscribe", "params": {"sids": [50]}}]
    assert w.status()["sids"] == [51, 52]


def test_odd_control_messages_are_recorded_and_otherwise_ignored(ms, world):
    w = world()
    w.run_to(H0 + 40)
    sock = w.sock
    odd = ['{"type": "subscribed", "msg": {"sid": 9',                         # cut short
           '["a list", {"type": "subscribed"}]',                             # not an object
           '{"type": "subscribed", "msg": {"channel": "trade", "sid": "9"}}',  # sid not a number
           '{"type": "subscribed", "msg": "no body"}',
           '{"type": "ok", "id": 3}']
    for i, text in enumerate(odd):
        sock.push(text, at=H0 + 41 + i * 0.1)
    w.run_to(H0 + 41 + ms.FLUSH_EVERY + 2)
    assert partial_lines(w.out / F18)[-5:] == [line(H0 + 41 + i * 0.1, t) for i, t in enumerate(odd)]
    assert len(sock.commands()) == 1 and w.events("drop") == []
    w.run_to(H0 + 92)
    assert w.status()["sids"] == [1, 2]


def test_an_unsubscribe_that_cannot_be_sent_drops_the_socket(ms, world):
    w = world()
    w.net.ack = False
    w.ex.late = {"KXGOLD15M": 100}
    w.run_to(H0 + 130)                                   # subscribes 1 and 2 sent, neither answered
    w.sock.fail_send = BrokenPipeError("pipe closed")
    w.sock.push(json.dumps({"id": 1, "type": "subscribed", "msg": {"channel": "trade", "sid": 50}}))
    w.run_to(H0 + 133)
    drops = w.events("drop")
    assert len(drops) == 1 and "pipe closed" in drops[0]["why"]


def test_an_error_from_kalshi_is_logged(ms, world):
    w = world()
    w.run_to(H0 + 5)
    w.sock.push(json.dumps({"id": 1, "type": "error", "msg": {"code": 16, "msg": "Market not found"}}))
    w.run_to(H0 + 8)
    ev = w.events("error")
    assert len(ev) == 1 and ev[0]["msg"] == "Market not found"


# ------------------------------------------------------------------ recording


def test_every_message_is_written_as_received_with_its_receive_time(ms, world):
    w = world()
    w.run_to(H0 + 40)
    texts = ['{"type": "orderbook_delta", "sid": 1, "seq": 17, "msg": {"market_ticker": "Ü\\u00e9", "x": 1}}',
             '{"type":"trade","sid":2,"msg":{"trade_id":"a","count_fp":"0.03","yes_price_dollars":"0.9840"}}',
             '{"type": "something_new", "list": [1, 2.5, "three"]}',
             '  {"type": "orderbook_delta", "sid": 1, "seq": 18}  ',
             "not json, kept anyway"]
    for i, t in enumerate(texts):
        w.sock.push(t, at=H0 + 41 + i * 0.25)
    w.run_to(H0 + 41 + ms.FLUSH_EVERY + 2)
    lines = partial_lines(w.out / F18)
    assert lines == [line(rt, text) for rt, text in w.sock.delivered]
    assert lines[-5:] == [line(H0 + 41 + i * 0.25, t) for i, t in enumerate(texts)]
    w.run_to(H0 + 2 * ms.STATUS_EVERY + 2)              # past a status write with the file open
    assert w.status()["writing"] == F18


def test_the_gzip_stream_is_readable_after_each_flush(ms, world):
    w = world(t0=H0 + 3000)
    w.ex.absent = set(SPEC_SERIES)                 # nothing listed: only the messages pushed here
    w.run_to(H0 + 3005)
    for k in range(3):
        text = json.dumps({"type": "trade", "sid": 9, "n": k})
        w.sock.push(text, at=w.clock.t + 0.5)
        w.run_to(w.clock.t + ms.FLUSH_EVERY + 1.5)
        assert partial_lines(w.out / F18)[-1] == line(w.sock.delivered[-1][0], text)
    with pytest.raises(EOFError):                     # still open: no gzip end yet
        full_lines(w.out / F18)


def test_the_hour_file_is_closed_complete_when_the_hour_rolls(ms, world):
    w = world(t0=H0 + 3500)
    w.run_to(H0 + 3510)
    a, b = '{"type": "trade", "sid": 9, "a": 1}', '{"type": "trade", "sid": 9, "b": 2}'
    w.sock.push(a, at=H0 + 3599.5)
    w.sock.push(b, at=H0 + 3600.25)
    w.run_to(H0 + 3600 + ms.FLUSH_EVERY + 2)
    assert full_lines(w.out / F18) == [line(H0 + 3599.5, a)]
    assert partial_lines(w.out / F19)[0] == line(H0 + 3600.25, b)
    assert w.status()["writing"] == F19 and w.status()["rt"] == H0 + 3600.25   # rewritten as the file opened
    w.run_to(H0 + 3600 + ms.STATUS_EVERY + 5)
    assert w.status()["writing"] == F19


def test_the_hour_file_closes_at_the_hour_even_with_nothing_more_to_write(ms, world):
    w = world(t0=H0 + 3500)
    w.ex.absent = set(SPEC_SERIES)
    w.run_to(H0 + 3510)
    a = '{"type": "trade", "sid": 9, "a": 1}'
    w.sock.push(a, at=H0 + 3550)
    w.run_to(H0 + 3601.5)
    assert full_lines(w.out / F18) == [line(H0 + 3550, a)]
    assert w.status()["writing"] is None and H0 + 3600 <= w.status()["rt"] < H0 + 3601.5   # rewritten as it closed
    w.run_to(H0 + 3600 + ms.STATUS_EVERY + 5)
    assert w.status()["writing"] is None
    assert not (w.out / F19).exists()


def test_a_taken_name_is_never_overwritten(ms, tmp_path, world):
    out = tmp_path / "out"
    out.mkdir()
    (out / F18).write_bytes(b"an earlier run's file")
    w = world()
    w.run_to(H0 + 60)
    assert (out / F18).read_bytes() == b"an earlier run's file"
    assert partial_lines(out / "ws-20261026T18.1.txt.gz")[0].endswith(w.sock.delivered[0][1])
    w.run_to(H0 + 95)
    assert w.status()["writing"] == "ws-20261026T18.1.txt.gz"


def test_numbering_carries_on_after_the_highest_file_of_the_hour(ms, tmp_path, world):
    out = tmp_path / "out"
    out.mkdir()
    for name in ("ws-20261026T18.1.txt.gz", "ws-20261026T18.3.txt.gz", "ws-20261026T17.7.txt.gz"):
        (out / name).write_bytes(b"old")
    w = world()
    w.run_to(H0 + 60)
    assert (out / "ws-20261026T18.4.txt.gz").exists()
    assert not (out / F18).exists() and not (out / "ws-20261026T18.2.txt.gz").exists()


def test_a_newline_inside_a_message_cannot_split_its_line(ms, world):
    w = world(t0=H0 + 3000)
    w.ex.absent = set(SPEC_SERIES)
    w.run_to(H0 + 3002)
    w.sock.push('{"type": "trade",\n "sid": 9,\r\n "x": 1}', at=H0 + 3003)
    w.run_to(H0 + 3003 + ms.FLUSH_EVERY + 2)
    assert partial_lines(w.out / F18) == [line(H0 + 3003, '{"type": "trade",  "sid": 9,   "x": 1}')]


def test_deltas_and_trades_are_only_peeked_never_parsed(ms, monkeypatch, world):
    parsed = []
    real = json.loads

    def counting(s, *a, **k):
        if isinstance(s, str) and ('"orderbook_delta"' in s or '"trade"' in s or '"orderbook_snapshot"' in s):
            parsed.append(s)
        return real(s, *a, **k)

    w = world()
    w.run_to(H0 + 40)
    monkeypatch.setattr(ms.json, "loads", counting)
    sid = w.sock.book_sid
    for i in range(50):
        w.sock.emit("orderbook_delta", sid, w.tickers()[0], at=H0 + 41 + i * 0.01)
        w.sock.emit("trade", sid + 1, w.tickers()[0], at=H0 + 41 + i * 0.01)
    w.run_to(H0 + 45)
    monkeypatch.setattr(ms.json, "loads", real)
    assert len(w.sock.delivered) >= 100 + 18
    assert parsed == []


# ------------------------------------------------------------------ sequence gaps


def test_a_seq_gap_is_logged_and_the_markets_resubscribed(ms, world):
    w = world()
    w.run_to(H0 + 40)
    sock = w.sock
    a, b = sorted(sock.channel)
    t1 = w.clock.t
    sock.emit("orderbook_delta", a, w.tickers()[0], at=t1 + 0.1)           # seq 17, after 16 snapshots
    sock.emit("orderbook_delta", a, w.tickers()[0], at=t1 + 0.2, seq=20)
    w.run_to(t1 + 3)
    gaps = w.events("gap")
    assert len(gaps) == 1
    assert {k: gaps[0][k] for k in ("sid", "expected", "got")} == {"sid": a, "expected": 18, "got": 20}
    cmds = sock.commands()
    assert cmds[1:] == [{"id": 2, "cmd": "unsubscribe", "params": {"sids": [a, b]}},
                        {"id": 3, "cmd": "subscribe", "params": {"channels": ["orderbook_delta", "trade"],
                                                                 "market_tickers": w.tickers()}}]
    w.run_to(t1 + ms.STATUS_EVERY + 2)
    st = w.status()
    assert st["gaps"] == 1 and st["sids"] == sorted(sock.channel) and a not in st["sids"]
    assert len(w.events("gap")) == 1           # the new sids' snapshots start their own count; unsubscribed isn't one


def test_the_first_message_of_a_sid_sets_its_seq_and_messages_without_one_dont_count(ms, world):
    w = world()
    w.run_to(H0 + 40)
    sock = w.sock
    a = sock.book_sid
    t1 = w.clock.t
    sock.emit("trade", 300, "X", at=t1 + 0.1, seq=41)
    sock.emit("trade", 300, "X", at=t1 + 0.2)                                    # 42
    sock.push('{"type": "trade", "sid": 300, "msg": {"market_ticker": "X"}}', at=t1 + 0.3)   # no seq
    sock.emit("trade", 300, "X", at=t1 + 0.4)                                    # 43
    sock.push(json.dumps({"id": 9, "type": "ok", "sid": a, "seq": 5000}), at=t1 + 0.5)   # control: not counted
    sock.emit("orderbook_delta", a, w.tickers()[0], at=t1 + 0.6)                 # 17
    w.run_to(t1 + 3)
    assert w.events("gap") == []
    assert len(sock.commands()) == 1


def test_a_gap_on_a_sid_it_does_not_hold_is_only_logged(ms, world):
    w = world()
    w.run_to(H0 + 40)
    t1 = w.clock.t
    w.sock.emit("trade", 300, "X", at=t1 + 0.1, seq=1)
    w.sock.emit("trade", 300, "X", at=t1 + 0.2, seq=5)
    w.run_to(t1 + 3)
    assert [(e["sid"], e["expected"], e["got"]) for e in w.events("gap")] == [(300, 2, 5)]
    assert len(w.sock.commands()) == 1


def test_resubscribes_after_gaps_are_RESUB_MIN_apart(ms, world):
    w = world()
    w.run_to(H0 + 50)
    sock = w.sock
    t1 = w.clock.t
    sock.emit("orderbook_delta", sock.book_sid, w.tickers()[0], at=t1 + 0.1, seq=30)
    w.run_to(t1 + 1.5)
    assert [c["cmd"] for c in sock.commands()] == ["subscribe", "unsubscribe", "subscribe"]
    first_resub = sock.sent[-1][0]
    new = sock.book_sid
    sock.emit("orderbook_delta", new, w.tickers()[0], at=w.clock.t + 0.1, seq=40)   # a second gap at once
    w.run_to(first_resub + ms.RESUB_MIN - 0.5)
    assert len(sock.commands()) == 3 and len(w.events("gap")) == 2
    w.run_to(first_resub + ms.RESUB_MIN + 2)
    assert [c["cmd"] for c in sock.commands()] == ["subscribe", "unsubscribe", "subscribe", "unsubscribe", "subscribe"]
    assert sock.sent[-1][0] >= first_resub + ms.RESUB_MIN


# ------------------------------------------------------------------ dead sockets


def test_a_recv_error_drops_the_socket_waits_and_resubscribes(ms, world):
    w = world()
    w.run_to(H0 + 40)
    s1 = w.sock
    s1.fail_close = OSError("close failed too")                     # ignored
    s1.push(ConnectionResetError("reset by peer"), at=H0 + 41)
    w.run_to(H0 + 60)
    drops = w.events("drop")
    assert len(drops) == 1 and "reset by peer" in drops[0]["why"]
    assert s1.closed
    assert len(w.net.connects) == 2
    assert w.net.connects[1] - drops[0]["rt"] == pytest.approx(ms.RETRY[0], abs=0.01)
    slept = sum(s for t, s in w.clock.sleeps if drops[0]["rt"] - 0.01 <= t < w.net.connects[1])
    assert slept == pytest.approx(ms.RETRY[0], abs=0.01)
    s2 = w.sock
    assert s2.commands()[0] == {"id": 1, "cmd": "subscribe",
                                "params": {"channels": ["orderbook_delta", "trade"], "market_tickers": w.tickers()}}
    assert len(w.events("connect")) == 2
    w.run_to(H0 + 100)
    assert w.status()["drops"] == 1 and w.status()["connected"] is True


def test_a_silent_subscribed_socket_is_dropped_after_QUIET_SOCKET(ms, world):
    w = world(quiet_socket=True)
    w.run_to(H0 + 40)
    heard = w.sock.delivered[-1][0]
    w.run_to(heard + ms.QUIET_SOCKET - 1)
    assert w.events("drop") == []
    w.run_to(heard + ms.QUIET_SOCKET + 5)
    drops = w.events("drop")
    assert len(drops) == 1 and "quiet" in drops[0]["why"].lower()
    assert ms.QUIET_SOCKET <= drops[0]["rt"] - heard < ms.QUIET_SOCKET + 1.5
    assert len(w.net.sockets) == 2 and w.sock.commands()[0]["cmd"] == "subscribe"


def test_connect_failures_back_off_by_RETRY_then_every_30_s(ms, world):
    w = world()
    w.net.refuse = [OSError(f"refused {i}") for i in range(7)]
    w.run_to(H0 + 140)
    c = w.net.connects
    assert c[0] == H0
    assert [round(b - a, 3) for a, b in zip(c, c[1:])] == [1, 2, 5, 10, 30, 30, 30]
    failed = w.events("connect_failed")
    assert len(failed) == 7 and all(f"refused {i}" in e["why"] for i, e in enumerate(failed))
    assert len(w.events("connect")) == 1
    assert w.sock.commands()[0]["params"]["market_tickers"] == w.tickers()   # subscribed once it got through
    assert len(w.ex.of("markets")) == 16                                     # listing carried on meanwhile
    assert w.status()["rt"] >= H0 + 110                                      # and status.json


class BadStatus(Exception):
    """websocket-client's WebSocketBadStatusException, as far as the recorder may rely on it: a message and a
    status_code."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def test_refused_sign_in_reads_the_status_code_or_else_the_message(ms):
    assert ms.refused_sign_in(BadStatus("Handshake status 401 Unauthorized -+-+- {} -+-+- None", 401))
    assert ms.refused_sign_in(BadStatus("Handshake status", "403"))
    assert not ms.refused_sign_in(BadStatus("Handshake status 500 -+-+- {'x-id': '401'} -+-+- None", 500))  # code wins
    assert ms.refused_sign_in(OSError("Handshake status 403 Forbidden -+-+- {} -+-+- None"))      # no code: the text
    assert not ms.refused_sign_in(OSError("[Errno 111] Connection refused"))
    assert not ms.refused_sign_in(OSError("timed out after 4010 ms on port 14030"))
    websocket = pytest.importorskip("websocket")
    assert ms.refused_sign_in(websocket.WebSocketBadStatusException("Handshake status 401 Unauthorized", 401))
    assert not ms.refused_sign_in(websocket.WebSocketBadStatusException("Handshake status 502 Bad Gateway", 502))


def test_a_refused_sign_in_waits_AUTH_WAIT_before_the_next_connect(ms, world):
    w = world()
    w.net.refuse = [BadStatus("Handshake status 401 Unauthorized -+-+- {} -+-+- None", 401),
                    OSError("Handshake status 403 Forbidden"),
                    BadStatus("Handshake status 503 Service Unavailable", 503)]   # not a sign-in: the usual wait
    w.run_to(H0 + 2 * ms.AUTH_WAIT + 10)
    c = w.net.connects
    assert [round(b - a, 3) for a, b in zip(c, c[1:])] == [ms.AUTH_WAIT, ms.AUTH_WAIT, ms.RETRY[2]]
    ev = w.events("auth_failed")
    assert len(ev) == 2 and "401" in ev[0]["why"] and "403" in ev[1]["why"]
    assert len(w.events("connect_failed")) == 1 and len(w.events("connect")) == 1
    assert len(w.ex.of("markets")) >= 16 and w.ex.of("get")       # listing and results carried on meanwhile
    assert all(s <= 1.0 for _, s in w.clock.sleeps)                # waited in pieces


def test_a_socket_that_stays_up_resets_the_waits(ms, world):
    w = world()
    w.net.refuse = [OSError("refused")] * 3                  # waits of 1, 2 and 5 s
    w.run_to(H0 + 9)
    assert len(w.net.sockets) == 1
    up = w.net.connects[-1]
    w.sock.push(ConnectionResetError("short-lived"), at=up + 3)         # down again within seconds
    w.run_to(up + 3 + ms.RETRY[3] + 2)
    assert round(w.net.connects[-1] - (up + 3), 3) == ms.RETRY[3]       # the fourth failure in a row
    up = w.net.connects[-1]
    w.sock.push(ConnectionResetError("after a good run"), at=up + ms.HEALTHY + 5)
    w.run_to(up + ms.HEALTHY + 5 + ms.RETRY[0] + 1)
    assert round(w.net.connects[-1] - (up + ms.HEALTHY + 5), 3) == ms.RETRY[0]


def test_a_send_error_drops_the_socket(ms, world):
    w = world()
    w.run_to(H0 + 10)
    w.sock.fail_send = BrokenPipeError("pipe closed")
    w.run_to(H0 + 50)
    drops = w.events("drop")
    assert len(drops) == 1 and "pipe closed" in drops[0]["why"]
    assert len(w.net.sockets) == 2
    assert w.sock.commands()[0]["params"]["market_tickers"] == w.tickers()


def test_websocket_clients_timeout_means_nothing_this_second(ms, world):
    websocket = pytest.importorskip("websocket")
    w = world()
    w.net.timeout = websocket.WebSocketTimeoutException
    w.ex.absent = set(SPEC_SERIES)
    w.run_to(H0 + 20)
    assert w.events("drop") == [] and len(w.net.connects) == 1


def test_an_empty_frame_means_kalshi_closed_the_socket(ms, world):
    w = world()
    w.run_to(H0 + 40)
    w.sock.push("", at=H0 + 41)
    w.run_to(H0 + 41 + ms.FLUSH_EVERY + 3)
    assert len(w.events("drop")) == 1 and len(w.net.sockets) == 2
    lines = partial_lines(w.out / F18)
    assert len(lines) == sum(1 for s in w.net.sockets for _, text in s.delivered if text)
    assert not any(ln.endswith(" ") for ln in lines)


# ------------------------------------------------------------------ results


def test_results_are_asked_once_after_RESULTS_AFTER_and_written_once(ms, world):
    w = world()
    w.ex.settle_after = 30
    w.run_to(H0 + 900 + 700)
    gets = w.ex.of("get")
    assert sorted(c.arg for c in gets) == sorted(f"/markets/{t}" for t in w.tickers())    # once each
    assert all(c.t >= H0 + 900 + ms.RESULTS_AFTER for c in gets)
    assert_never_quiet(ms, w.ex.calls)
    assert_rest_spaced(ms, w.ex.calls)
    res = jsonl(w.out / "results.jsonl")
    assert sorted(r["ticker"] for r in res) == w.tickers()
    for r in res:
        assert set(r) == {"ticker", "result", "status", "rt"}
        assert (r["result"], r["status"]) == ("yes", "finalized") and r["rt"] >= H0 + 900 + ms.RESULTS_AFTER


def test_an_unsettled_market_is_asked_again_until_RESULTS_GIVE_UP(ms, monkeypatch, world):
    monkeypatch.setattr(ms, "RESULTS_GIVE_UP", 1800)
    w = world()
    w.ex.settle_after = None
    w.run_to(H0 + 900 + 2000)
    btc = ticker_of("KXBTC15M", H0)
    asks = [c.t for c in w.ex.of("get") if c.arg == f"/markets/{btc}"]
    assert asks[0] >= H0 + 900 + ms.RESULTS_AFTER
    assert all(b - a >= ms.RESULTS_RETRY - 1e-9 for a, b in zip(asks, asks[1:]))
    assert H0 + 900 + 1800 - ms.RESULTS_RETRY - 20 <= asks[-1] < H0 + 900 + 1800
    assert len(asks) >= 10
    assert_never_quiet(ms, w.ex.calls)
    assert jsonl(w.out / "results.jsonl") == []


def test_results_calls_are_capped_at_40_a_step_and_spaced(ms, tmp_path, world):
    out = tmp_path / "out"
    out.mkdir()
    old = H0 - 1800
    with open(out / "markets.jsonl", "w", encoding="utf-8") as fh:
        for i in range(100):
            m = market_line("KXBTC15M", old)
            m["ticker"] = f"KXBTC15M-{old}-{i:03d}"
            fh.write(json.dumps(m) + "\n")
    w = world(t0=H0 + 700)
    w.ex.settle_after = None
    before = len(w.ex.of("get"))
    w.rec.step()
    assert len(w.ex.of("get")) - before <= 40
    w.run_to(H0 + 900)
    assert len({c.arg for c in w.ex.of("get")}) == 100
    assert_rest_spaced(ms, w.ex.calls)


def test_a_failed_results_call_is_just_asked_again(ms, world):
    w = world()
    w.run_to(H0 + 900 + 100)
    real = w.ex.market
    calls = []

    def flaky(path):
        calls.append(path)
        if len(calls) <= 2:
            raise ConnectionError("Kalshi didn't answer")
        if len(calls) <= 4:
            return None
        return real(path)

    w.ex.market = flaky
    w.run_to(H0 + 900 + 400)
    assert sorted(r["ticker"] for r in jsonl(w.out / "results.jsonl")) == w.tickers()


def test_a_REST_call_over_REST_SLOW_is_logged_with_what_it_asked(ms, world):
    w = world()
    eth = ticker_of("KXETH15M", H0)
    took = {"KXETH15M": 2.5, "KXSOL15M": 0.9, "KXXRP15M": 3.0, f"/markets/{eth}": 1.5}   # each call's first time only
    listing, market = w.ex.listing, w.ex.market

    def slow_listing(params):
        w.clock.t += took.pop(params["series_ticker"], 0)
        return listing(params)

    def slow_market(path):
        w.clock.t += took.pop(path, 0)
        return market(path)

    w.ex.listing, w.ex.market = slow_listing, slow_market
    w.ex.fail_once = {"KXXRP15M": "raise"}                 # slow, and then it fails
    w.run_to(H0 + 900 + 400)
    slow = [{k: v for k, v in e.items() if k != "rt"} for e in w.events("rest_slow")]
    assert slow == [{"event": "rest_slow", "series": "KXETH15M", "seconds": 2.5},
                    {"event": "rest_slow", "series": "KXXRP15M", "seconds": 3.0},
                    {"event": "rest_slow", "ticker": eth, "seconds": 1.5}]
    assert [e["series"] for e in w.events("list_failed")] == ["KXXRP15M"]
    assert_rest_spaced(ms, w.ex.calls)


# ------------------------------------------------------------------ restart


def test_a_restart_reads_markets_and_results_back(ms, tmp_path, world):
    out = tmp_path / "out"
    out.mkdir()
    w1 = H0 + 900
    lines = [market_line(s, H0) for s in SPEC_SERIES] + [market_line(s, w1) for s in SPEC_SERIES]
    lines += [market_line("KXBTC15M", H0 - 7 * 3600)]                         # too old to ask
    (out / "markets.jsonl").write_text("".join(json.dumps(m) + "\n" for m in lines), encoding="utf-8")
    done = [ticker_of(s, H0) for s in SPEC_SERIES[:10]]
    (out / "results.jsonl").write_text("".join(json.dumps({"ticker": t, "result": "no", "status": "finalized",
                                                           "rt": H0 + 1000.0}) + "\n" for t in done),
                                       encoding="utf-8")
    w = world(t0=w1 + 100)
    w.ex.settle_after = 0
    w.rec.step()
    assert w.sock.commands() == [{"id": 1, "cmd": "subscribe", "params": {
        "channels": ["orderbook_delta", "trade"], "market_tickers": w.tickers(window=w1)}}]
    w.run_to(w1 + 400)
    assert w.ex.of("markets") == []                                           # nothing re-listed
    assert sorted(c.arg for c in w.ex.of("get")) == sorted(f"/markets/{ticker_of(s, H0)}" for s in SPEC_SERIES[10:])
    res = jsonl(out / "results.jsonl")
    assert sorted(r["ticker"] for r in res) == w.tickers()                    # each once
    assert len(jsonl(out / "markets.jsonl")) == len(lines)
    start = w.events("start")
    assert len(start) == 1


def test_a_restart_lists_only_the_series_still_missing(ms, tmp_path, world):
    out = tmp_path / "out"
    out.mkdir()
    known = SPEC_SERIES[:10]
    with open(out / "markets.jsonl", "w", encoding="utf-8") as fh:
        for s in known:
            fh.write(json.dumps(market_line(s, H0)) + "\n")
        fh.write('{"ticker": "KXSILVER15M-1793037600", "series": "KXSIL')            # a crash cut this one short
    w = world(t0=H0 + 50)
    w.run_to(H0 + 70)
    assert sorted(c.arg["series_ticker"] for c in w.ex.of("markets")) == sorted(SPEC_SERIES[10:])
    good = []
    for ln in (out / "markets.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            good.append(json.loads(ln))
        except ValueError:
            pass
    assert sorted(m["ticker"] for m in good) == w.tickers()                   # appended on lines of their own
    assert w.sock.commands()[-1]["params"]["market_tickers"] == w.tickers()


def test_a_restart_skips_lines_it_cannot_use(ms, tmp_path, world):
    out = tmp_path / "out"
    out.mkdir()
    good = market_line("KXBTC15M", H0)
    (out / "markets.jsonl").write_text("\n".join([
        "[1, 2]", "7", json.dumps({"ticker": "NO-CLOSE", "series": "KXBTC15M", "window_open": H0}),
        json.dumps({**market_line("KXETH15M", H0), "close": "soon"}), json.dumps(good)]) + "\n", encoding="utf-8")
    (out / "results.jsonl").write_text('"just a string"\n{"no": "ticker"}\n', encoding="utf-8")
    w = world(t0=H0 + 50)
    w.run_to(H0 + 70)
    assert "KXBTC15M" not in [c.arg["series_ticker"] for c in w.ex.of("markets")]
    assert "KXETH15M" in [c.arg["series_ticker"] for c in w.ex.of("markets")]
    assert w.events("start")[0]["carried"] == [good["ticker"]]


# ------------------------------------------------------------------ files it can't write


def test_events_and_status_it_cannot_write_dont_stop_it(ms, tmp_path, world, capsys):
    out = tmp_path / "out"
    (out / "events.jsonl").mkdir(parents=True)          # a folder where the file should be
    (out / "status.json.tmp").mkdir()
    w = world()
    w.run_to(H0 + 100)
    assert len(w.sock.commands("subscribe")) == 1
    assert partial_lines(out / F18)
    said = capsys.readouterr().out
    assert "events.jsonl" in said and "status.json" in said
    assert not (out / "status.json").exists()


def test_a_broken_stdout_is_no_reason_to_stop(ms, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("stdout is gone")

    monkeypatch.setattr("builtins.print", broken)
    ms.say("still here")


def test_an_hour_file_that_fails_to_close_is_left_and_the_next_one_opened(ms, world, monkeypatch, capsys):
    real = gzip.open

    class Brittle:
        def __init__(self, fh):
            self.fh = fh

        def write(self, text):
            return self.fh.write(text)

        def flush(self):
            return self.fh.flush()

        def close(self):
            self.fh.close()
            raise OSError("no space left on device")

    monkeypatch.setattr(ms.gzip, "open", lambda *a, **k: Brittle(real(*a, **k)))
    w = world(t0=H0 + 3500)
    w.run_to(H0 + 3510)
    w.sock.push('{"type": "trade", "sid": 9, "a": 1}', at=H0 + 3599.5)
    w.sock.push('{"type": "trade", "sid": 9, "b": 2}', at=H0 + 3600.5)
    w.run_to(H0 + 3600 + ms.FLUSH_EVERY + 2)
    monkeypatch.setattr(ms.gzip, "open", real)
    assert "no space left on device" in capsys.readouterr().out
    assert partial_lines(w.out / F19)[0].endswith('"b": 2}')


# ------------------------------------------------------------------ status


def test_status_is_rewritten_atomically_every_STATUS_EVERY(ms, monkeypatch, world):
    replaced = []
    real = os.replace

    def spy(src, dst, *a, **k):
        replaced.append((Path(src), Path(dst)))
        return real(src, dst, *a, **k)

    monkeypatch.setattr(ms.os, "replace", spy)
    w = world()
    w.rec.step()
    first = w.status()
    assert first["rt"] == H0
    w.run_to(H0 + 100)
    st = w.status()
    assert H0 + 100 - ms.STATUS_EVERY - 1.5 <= st["rt"] <= H0 + 100
    writes = [r for r in replaced if r[1].name == "status.json"]
    assert 3 <= len(writes) <= 5
    assert all(src.parent == w.out and dst.parent == w.out and src.name != "status.json" for src, dst in writes)
    assert set(st) == {"rt", "connected", "messages", "last_message_rt", "window_open", "markets", "sids", "drops",
                       "gaps", "writing", "free_gb", "paused"}
    assert st["connected"] is True and st["paused"] is False
    assert st["messages"] == len(w.sock.delivered) == 18                  # 2 acks and 16 snapshots, all at H0 + 30
    assert st["last_message_rt"] == pytest.approx(w.sock.delivered[-1][0])
    assert st["window_open"] == H0 and st["markets"] == w.tickers()
    assert st["sids"] == [1, 2] and st["drops"] == 0 and st["gaps"] == 0
    assert st["writing"] == F18 and st["free_gb"] == pytest.approx(100.0, abs=0.01)
    assert sorted(p.name for p in w.out.iterdir()) == sorted(["events.jsonl", "markets.jsonl", "status.json", F18])


def test_status_before_any_message(ms, world):
    w = world()
    w.net.refuse = [OSError("no network")]
    w.rec.step()
    st = w.status()
    assert st["connected"] is False and st["messages"] == 0 and st["last_message_rt"] is None
    assert st["writing"] is None and st["markets"] == [] and st["sids"] == []


# ------------------------------------------------------------------ low space


def test_low_space_pauses_everything_until_there_is_room_again(ms, world):
    w = world()
    w.run_to(H0 + 40)
    s1 = w.sock
    w.free_gb = ms.MIN_FREE_GB - 0.1
    w.run_to(H0 + 40 + ms.SPACE_EVERY + 2)
    ev = w.events("low_space")
    assert len(ev) == 1
    assert s1.closed
    assert full_lines(w.out / F18)                                       # closed: a complete gzip
    paused_at = ev[0]["rt"]
    connects, recvs, calls = len(w.net.connects), s1.recvs, len(w.ex.calls)
    w.free_gb = ms.MIN_FREE_GB + 1.5                                     # back above MIN, not above MIN + 2
    w.run_to(paused_at + 3 * ms.SPACE_EVERY)
    assert len(w.net.connects) == connects and s1.recvs == recvs and len(w.ex.calls) == calls
    assert w.events("resume") == [] and w.status()["paused"] is True
    w.free_gb = ms.MIN_FREE_GB + 2.5
    w.run_to(paused_at + 4 * ms.SPACE_EVERY + 5)
    resume = w.events("resume")
    assert len(resume) == 1
    assert len(w.net.sockets) == 2 and w.sock.commands()[0]["params"]["market_tickers"] == w.tickers()
    assert w.net.connects[-1] - resume[0]["rt"] < 1.5
    assert (w.out / "ws-20261026T18.1.txt.gz").exists()                  # recording again, in a new file
    reads = [t for t, _ in w.space_reads]
    assert all(b - a >= ms.SPACE_EVERY - 1e-9 for a, b in zip(reads, reads[1:]))
    assert all(Path(p) == w.out for _, p in w.space_reads)
    w.run_to(w.clock.t + ms.STATUS_EVERY + 2)
    assert w.status()["paused"] is False


def test_unreadable_free_space_keeps_recording(ms, world):
    w = world()
    w.space_error = OSError("statvfs failed")
    w.run_to(H0 + 100)
    assert w.events("low_space") == [] and w.status()["free_gb"] is None and w.status()["paused"] is False


# ------------------------------------------------------------------ the wall clock jumping


def test_a_wall_clock_jumping_back_does_not_freeze_flushes_space_checks_or_status(ms, world):
    w = world(t0=H0 + 3000)
    w.ex.absent = set(SPEC_SERIES)                 # nothing listed: only the messages pushed here
    w.run_to(H0 + 3005)
    a, b = '{"type": "trade", "sid": 9, "a": 1}', '{"type": "trade", "sid": 9, "b": 2}'
    w.sock.push(a, at=H0 + 3006)
    w.run_to(H0 + 3006 + ms.FLUSH_EVERY + 2)
    assert partial_lines(w.out / F18)[-1] == line(H0 + 3006, a)
    reads = len(w.space_reads)
    w.clock.jump(-300)                             # NTP steps the wall clock back 5 minutes (same hour, same window)
    back = w.clock.t
    w.sock.push(b, at=back + 0.5)
    w.run_to(back + 0.5 + ms.FLUSH_EVERY + 2)
    assert partial_lines(w.out / F18)[-1] == line(back + 0.5, b)     # flushed on time, not 5 minutes late
    w.run_to(back + ms.SPACE_EVERY + 2)
    assert len(w.space_reads) == reads + 1                           # the space check carried on
    assert w.status()["rt"] >= back                                  # and so did status.json
    assert w.events("drop") == [] and len(w.net.sockets) == 1


def test_a_wall_clock_jumping_back_does_not_freeze_a_reconnect(ms, world):
    w = world(t0=H0 + 3000)
    w.ex.absent = set(SPEC_SERIES)
    w.run_to(H0 + 3002)
    w.sock.push(ConnectionResetError("reset by peer"), at=H0 + 3003)
    for _ in range(10):
        w.rec.step()
        if w.rec.ws is None:
            break
    assert len(w.events("drop")) == 1
    w.clock.jump(-300)                             # while it waits RETRY[0] s to reconnect
    w.run_to(w.clock.t + ms.RETRY[0] + 1.5)
    assert len(w.net.sockets) == 2


def test_a_wall_clock_jumping_forward_does_not_drop_a_live_socket_as_quiet(ms, world):
    w = world(quiet_socket=True)
    w.run_to(H0 + 40)                              # subscribed; the snapshots came at H0 + 30
    w.clock.jump(120)                              # same window, same hour
    w.run_to(w.clock.t + 5)
    assert w.events("drop") == [] and len(w.net.sockets) == 1


# ------------------------------------------------------------------ run, until and stopping


def test_run_returns_at_until_with_the_hour_file_complete(ms, world):
    w = world(until=H0 + 100)
    w.rec.run()
    assert w.clock.t >= H0 + 100
    assert w.clock.t < H0 + 103
    assert w.sock.closed
    assert full_lines(w.out / F18) == [line(rt, text) for rt, text in w.sock.delivered]
    st = w.status()
    assert st["connected"] is False and st["writing"] is None
    kinds = [e["event"] for e in w.events()]
    assert kinds[0] == "start" and kinds[-1] == "stop"


def test_run_returns_at_once_when_until_has_passed(ms, world):
    w = world(until=H0 - 1)
    w.rec.run()
    assert w.net.connects == [] and w.ex.calls == []


def test_stop_ends_run_cleanly(ms, world):
    w = world()
    w.net.refuse = [OSError("refused")] * 100

    def at(t):
        if t >= H0 + 30:
            w.rec.stop()

    w.clock.on_sleep = at
    w.rec.run()
    assert H0 + 30 <= w.clock.t < H0 + 32
    assert w.events()[-1]["event"] == "stop"


def test_run_recovers_from_an_unexpected_error(ms, world):
    w = world(until=H0 + 120)
    w.run_to(H0 + 40)
    w.sock.push(42, at=H0 + 41)                     # not text: the recorder chokes on it
    w.rec.run()
    assert len(w.events("exception")) == 1
    assert len(w.net.sockets) == 2 and w.sock.commands()[0]["cmd"] == "subscribe"
    assert w.clock.t >= H0 + 120
    for f in w.out.glob("ws-*.txt.gz"):
        full_lines(f)                               # every file it wrote is complete


# ------------------------------------------------------------------ never outside out, never more than markets/get


def test_it_writes_only_inside_out_and_uses_only_markets_and_get(ms, tmp_path, monkeypatch, world):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    w = world(quiet_socket=True, until=H0 + 3600 + 1200)
    w.ex.late = {"KXGOLD15M": 100}
    w.ex.fail_once = {"KXBTC15M": "raise"}
    w.rec.run()
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files and all(w.out in p.parents for p in files), [str(p) for p in files if w.out not in p.parents]
    assert list(cwd.iterdir()) == []
    assert {c.kind for c in w.ex.calls} == {"markets", "get"}
    assert all(set(c.arg) == {"series_ticker", "min_close_ts", "max_close_ts", "limit"}
               for c in w.ex.of("markets"))
    assert all(c.arg.startswith("/markets/KX") and c.arg.count("/") == 2 for c in w.ex.of("get"))
    assert {p.name for p in w.out.glob("ws-*.txt.gz")} == {F18, F19}
    assert_never_quiet(ms, w.ex.calls)


# ------------------------------------------------------------------ one recorder per folder


def test_a_second_lock_on_the_folder_is_refused_until_the_first_lets_go(ms, tmp_path):
    out = tmp_path / "out"                         # made if missing
    first = ms.lock_out(str(out))
    assert first is not None and (out / "recorder.lock").exists()
    assert ms.lock_out(str(out)) is None
    assert ms.lock_holder(str(out)) in (None, str(os.getpid()))    # Windows won't let another handle read it
    first.close()
    again = ms.lock_out(str(out))
    assert again is not None
    again.close()


def test_the_lock_goes_when_the_process_holding_it_dies(ms, tmp_path):
    out = tmp_path / "out"
    child = ("import sys, time\n"
             "sys.path.insert(0, sys.argv[1])\n"
             "import maker_shadow\n"
             "lock = maker_shadow.lock_out(sys.argv[2])\n"
             "print('locked' if lock else 'held', flush=True)\n"
             "time.sleep(60)\n")
    p = subprocess.Popen([sys.executable, "-c", child, os.path.dirname(ms.__file__), str(out)],
                         stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "locked"
        assert ms.lock_out(str(out)) is None
        p.kill()                                   # no clean exit and no close: the OS has to let go
        p.wait(timeout=10)
        lock = None
        for _ in range(50):
            lock = ms.lock_out(str(out))
            if lock is not None:
                break
            time.sleep(0.1)
        assert lock is not None
        lock.close()
    finally:
        if p.poll() is None:
            p.kill()
        p.stdout.close()


def test_on_linux_the_lock_is_an_exclusive_non_blocking_flock(ms, tmp_path, monkeypatch):
    held, calls = set(), []

    def flock(fd, flags):
        calls.append(flags)
        if held:
            raise BlockingIOError(11, "Resource temporarily unavailable")
        held.add(fd)

    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=flock))
    out = tmp_path / "out"
    first = ms.lock_out(str(out), lock=ms.lock_posix)
    assert first is not None and calls == [2 | 4]
    assert ms.lock_out(str(out), lock=ms.lock_posix) is None
    assert ms.lock_holder(str(out)) == str(os.getpid())          # the holder's pid, for the message
    first.close()


def test_on_windows_the_lock_is_msvcrts_non_blocking_lock_on_the_first_byte(ms, tmp_path, monkeypatch):
    held, calls = set(), []

    def locking(fd, mode, nbytes):
        calls.append((mode, nbytes, os.lseek(fd, 0, os.SEEK_CUR)))
        if held:
            raise PermissionError(13, "Permission denied")
        held.add(fd)

    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=2, locking=locking))
    out = tmp_path / "out"
    out.mkdir()
    (out / "recorder.lock").write_text("12345\n", encoding="utf-8")     # a dead recorder's pid
    first = ms.lock_out(str(out), lock=ms.lock_windows)
    assert first is not None and calls == [(2, 1, 0)]              # byte 0, though the file opens at its end
    assert (out / "recorder.lock").read_text(encoding="utf-8") == f"{os.getpid()}\n"
    assert ms.lock_out(str(out), lock=ms.lock_windows) is None
    assert (out / "recorder.lock").read_text(encoding="utf-8") == f"{os.getpid()}\n"   # a refused one changes nothing
    first.close()
    assert ms.lock_holder(str(tmp_path / "nowhere")) is None


# ------------------------------------------------------------------ the systemd unit


def test_the_unit_hides_the_bots_state_folder_and_reads_nothing_inside_it(ms):
    unit = Path(ms.__file__).parent / "deploy" / "kalshi-maker-shadow.service"
    settings = {}
    for raw in unit.read_text(encoding="utf-8").splitlines():
        if "=" in raw and not raw.lstrip().startswith(("#", ";")):
            key, value = raw.split("=", 1)
            settings.setdefault(key.strip(), []).append(value.strip())
    state = "/home/kalshi/kalshi/bot/state"
    assert settings["InaccessiblePaths"] == [state]
    assert settings["ReadWritePaths"] == ["/home/kalshi/kalshi/maker-shadow"]
    work = settings["WorkingDirectory"][0]
    command = settings["ExecStart"][0].split()
    used = [work, command[0],                                        # its folder (and kalshi.py in it), the venv
            posixpath.join(work, command[command.index("--out") + 1]),
            ms.DEFAULT_ENV.replace("~", "/home/kalshi", 1),          # the bot's .env, which names the key file
            "/home/kalshi/kalshi/bot/keys/kalshi.pem"]               # the key, as the server's .env names it
    used += [v.split(":", 1)[1] for k in ("StandardOutput", "StandardError") for v in settings[k]]
    assert "--env-file" not in command
    for path in used:
        path = posixpath.normpath(path)
        assert path != state and not path.startswith(state + "/"), path


# ------------------------------------------------------------------ the CLI


class FakeRecorder:
    made = []
    on_run = None                  # called with the recorder while it "runs"

    def __init__(self, out, client, connect, now=None, mono=None, sleep=None, until=None, free_bytes=None):
        self.out, self.client, self.connect, self.until = out, client, connect, until
        self.ran = self.stopped = False
        FakeRecorder.made.append(self)

    def run(self):
        self.ran = True
        if FakeRecorder.on_run:
            FakeRecorder.on_run(self)

    def stop(self):
        self.stopped = True


class FakeWebSocketModule:
    """websocket-client's create_connection, recorded."""

    class WebSocketTimeoutException(Exception):
        pass

    def __init__(self):
        self.calls = []

    def create_connection(self, url, **kwargs):
        ws = FakeWS()
        self.calls.append((url, kwargs, ws))
        return ws


class FakeWS:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, t):
        self.timeouts.append(t)


@pytest.fixture
def cli(ms, monkeypatch, tmp_path, rsa_key):
    FakeRecorder.made = []
    monkeypatch.setattr(FakeRecorder, "on_run", None)
    monkeypatch.setattr(ms, "Recorder", FakeRecorder)
    wsmod = FakeWebSocketModule()
    monkeypatch.setattr(ms, "websocket", wsmod)
    handlers = {}
    monkeypatch.setattr(ms.signal, "signal", lambda sig, h: handlers.__setitem__(sig, h))
    bot = tmp_path / "bot"
    (bot / "keys").mkdir(parents=True)
    pem = rsa_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    (bot / "keys" / "test.pem").write_bytes(pem)
    env = bot / ".env"
    env.write_text("KALSHI_ENV=prod\nKALSHI_API_KEY_ID=test-key-id\nKALSHI_PRIVATE_KEY_PATH=keys/test.pem\n",
                   encoding="utf-8")
    return {"env": env, "ws": wsmod, "handlers": handlers, "bot": bot}


def test_cli_record_builds_a_public_client_and_a_signed_connect(ms, cli, tmp_path, rsa_key):
    out = tmp_path / "data"
    assert ms.main(["record", "--out", str(out), "--env-file", str(cli["env"]), "--until", "2026-11-28"]) == 0
    (rec,) = FakeRecorder.made
    assert rec.ran and rec.out == str(out)
    assert rec.until == datetime(2026, 11, 28, tzinfo=UTC).timestamp()
    from kalshi import Kalshi
    assert isinstance(rec.client, Kalshi) and rec.client.env == "prod" and not rec.client.authed
    assert rec.client.timeout == (ms.REST_CONNECT, ms.REST_TIMEOUT)      # requests: (connect, read)
    ws = rec.connect()
    ((url, kwargs, made),) = cli["ws"].calls
    assert ws is made and url == ms.WS_URL
    assert kwargs["timeout"] == 10 and kwargs.get("skip_utf8_validation") is True
    assert made.timeouts == [1]
    h = kwargs["header"]
    assert h["KALSHI-ACCESS-KEY"] == "test-key-id"
    rsa_key.public_key().verify(base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"]),
                                (h["KALSHI-ACCESS-TIMESTAMP"] + "GET" + ms.WS_PATH).encode(),
                                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                                hashes.SHA256())
    cli["handlers"][signal.SIGTERM](signal.SIGTERM, None)
    assert rec.stopped


def test_cli_without_until_records_forever_and_reads_the_default_env(ms, cli, tmp_path, monkeypatch):
    seen = []
    real = ms.read_env

    def spy(path):
        seen.append(path)
        return real(str(cli["env"]))

    monkeypatch.setattr(ms, "read_env", spy)
    key_abs = str(cli["bot"] / "keys" / "test.pem")
    cli["env"].write_text(f"KALSHI_API_KEY_ID=k\nKALSHI_PRIVATE_KEY_PATH={key_abs}\n", encoding="utf-8")
    assert ms.main(["record", "--out", str(tmp_path / "d")]) == 0
    assert FakeRecorder.made[0].until is None
    assert len(seen) == 1 and Path(seen[0]) == Path(os.path.expanduser("~/kalshi/bot/.env"))


def test_cli_refuses_without_a_key(ms, cli, tmp_path, capsys):
    cli["env"].write_text("KALSHI_ENV=prod\n", encoding="utf-8")
    assert ms.main(["record", "--out", str(tmp_path / "d"), "--env-file", str(cli["env"])]) == 2
    assert "KALSHI_API_KEY_ID" in capsys.readouterr().err
    cli["env"].write_text("KALSHI_API_KEY_ID=k\nKALSHI_PRIVATE_KEY_PATH=keys/missing.pem\n", encoding="utf-8")
    assert ms.main(["record", "--out", str(tmp_path / "d"), "--env-file", str(cli["env"])]) == 2
    assert "missing.pem" in capsys.readouterr().err
    assert FakeRecorder.made == []


def test_cli_refuses_without_websocket_client(ms, cli, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ms, "websocket", None)
    assert ms.main(["record", "--out", str(tmp_path / "d"), "--env-file", str(cli["env"])]) == 2
    assert "websocket-client" in capsys.readouterr().err
    assert FakeRecorder.made == []


def test_cli_holds_the_folders_lock_while_it_records_and_lets_go_after(ms, cli, tmp_path):
    out = tmp_path / "data"
    during = []
    FakeRecorder.on_run = lambda rec: during.append(ms.lock_out(rec.out))
    assert ms.main(["record", "--out", str(out), "--env-file", str(cli["env"])]) == 0
    assert during == [None]                              # held while it ran
    after = ms.lock_out(str(out))
    assert after is not None                             # and let go once it returned
    after.close()


def test_cli_exits_3_when_another_recorder_holds_the_folder(ms, cli, tmp_path, capsys):
    out = tmp_path / "data"
    other = ms.lock_out(str(out))
    (out / "events.jsonl").write_text("the other recorder's\n", encoding="utf-8")
    try:
        assert ms.main(["record", "--out", str(out), "--env-file", str(cli["env"])]) == 3
    finally:
        other.close()
    err = capsys.readouterr().err
    assert "another recorder" in err and "recorder.lock" in err
    assert FakeRecorder.made == []
    assert sorted(p.name for p in out.iterdir()) == ["events.jsonl", "recorder.lock"]   # nothing else touched
    assert (out / "events.jsonl").read_text(encoding="utf-8") == "the other recorder's\n"


def test_cli_usage_errors(ms, cli):
    for argv in ([], ["replay"], ["record"], ["record", "--out", "x", "--until", "28/11/2026"]):
        with pytest.raises(SystemExit) as e:
            ms.main(argv)
        assert e.value.code == 2
    assert FakeRecorder.made == []
