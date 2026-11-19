"""Maker shadow: the replay and report. Offline and pure: it reads a data folder written by maker_shadow.py.

The live bot is a taker: at minute 8 it buys the favourite at the ask and pays the taker fee. This replays Kalshi's
recorded order book and trade tape with pretend resting orders placed at the mark. It measures how often a waiting
order (a maker) would have filled, at what price, how fast, and what the price did right after: the picked-off
check. Nothing here trades or uses the network.

    python maker_replay.py report --data DIR [--out report.json] [--workers N] [--size 15]

SPEC.md ("maker_replay.py: the replay and report") is the contract. Where it is silent, the choices made are listed
at the top of tests/test_maker_replay.py ("Readings of the spec"). Each one can only remove fills, never add one.

It streams the hour files one line at a time. Per-market state (a book and three pretend orders) lives only from a
market's first message to its close, so memory stays flat however many weeks are replayed. One process reads about
150,000 messages a second (a day of recording is ~280 million), so the report splits the hours across processes.
"""
import argparse
import calendar
import concurrent.futures
import gzip
import heapq
import json
import math
import os
import re
import statistics
import sys
import time
import zlib

LO, HI = 0.92, 0.999       # the bot's band: the favourite's ask
MARK = 480                 # seconds into the window when the pretend orders go in (minute 8)
LAND = 0.124               # ... and how long after that they reach Kalshi: the bot's median from the Ohio server
                           # (Oct 2026). Nothing before then can fill them, and the join order queues behind every
                           # order at its price when it lands, not when the bot looked
SIZE = 15                  # contracts: the bot's median order since the Ohio move
CHECKS = (5, 30, 60)       # seconds after a first fill when the price is read again
TAKE_AFTER = 60            # the hybrid's wait before it buys the rest at the ask
TAKER_RATE = 0.07
STALE = 30                 # a feed silent longer than this was down: every book is unknown until its next snapshot
PAIR = 0.5                 # a trade at L this close (s) to a delta that cut the queue at L is that delta's own trade
KINDS = ("join", "tick", "cent")
EPS = 1e-9
TOL = 1e-6
WS_NAME = re.compile(r"^ws-(\d{8}T\d{2})(?:\.(\d+))?\.txt\.gz$")
BOOK_TYPES = ("orderbook_delta", "trade", "orderbook_snapshot")


# ---------------------------------------------------------------- reading files

_scan = json.JSONDecoder().scan_once     # the C scanner behind json.loads, without its per-call wrappers


def _raw_lines(path):
    """Text lines of a plain or gzip file. A missing file gives nothing; a damaged or truncated gzip (a crash)
    gives everything before the damage, then stops without raising."""
    kw = {"encoding": "utf-8", "errors": "replace", "newline": "\n"}
    try:
        with (gzip.open(path, "rt", **kw) if path.endswith(".gz") else open(path, "r", **kw)) as fh:
            for line in fh:
                yield line
    except (EOFError, OSError, zlib.error):     # gzip.BadGzipFile is an OSError
        return


def read_lines(path):
    """The JSON objects in a .jsonl or .jsonl.gz file, one per line. Bad lines are skipped."""
    for line in _raw_lines(path):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            yield obj


def ws_files(folder):
    """The recorder's hour files in time order: by the hour in the name, then the restart number (none first)."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = []
    for name in names:
        m = WS_NAME.match(name)
        if m:
            found.append((m.group(1), int(m.group(2) or 0), name))
    return [os.path.join(folder, name) for _, _, name in sorted(found)]


def _parse(line):
    """(rt, message) from one "<rt> <json>" line, or None if it can't be read."""
    i = line.find(" ")
    if i <= 0:
        return None
    try:
        rt = float(line[:i])
        msg, end = _scan(line, i + 1)
    except (ValueError, StopIteration):
        return None
    if type(msg) is not dict or not math.isfinite(rt) or line[end:].strip():
        return None
    return rt, msg


def messages(folder):
    """(rt, message) from every hour file in the folder, in time order. Bad lines are skipped."""
    for path in ws_files(folder):
        for line in _raw_lines(path):
            got = _parse(line)
            if got is not None:
                yield got


# ---------------------------------------------------------------- the book

def _levels(rows):
    out = {}
    for row in rows or ():
        try:
            p, c = round(float(row[0]), 4), float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if c > EPS:
            out[p] = out.get(p, 0.0) + c
    return out


class Book:
    """One market's book: bids for YES and bids for NO, price (rounded to 4 dp) -> contracts."""
    __slots__ = ("yes", "no", "ok")

    def __init__(self):
        self.yes = {}
        self.no = {}
        self.ok = False

    def snapshot(self, body):
        self.yes = _levels(body.get("yes_dollars_fp"))
        self.no = _levels(body.get("no_dollars_fp"))
        self.ok = True

    def delta(self, body):
        """Add delta_fp to `side` at price_dollars; a level at or under 1e-9 is gone. False if it can't be read."""
        side = body.get("side")
        try:
            p = round(float(body["price_dollars"]), 4)
            d = float(body["delta_fp"])
        except (KeyError, TypeError, ValueError):
            return False
        if side == "yes":
            lv = self.yes
        elif side == "no":
            lv = self.no
        else:
            return False
        new = lv.get(p, 0.0) + d
        if new <= EPS:
            lv.pop(p, None)
        else:
            lv[p] = new
        return True

    def bid(self, side):
        lv = self.yes if side == "yes" else self.no
        return max(lv) if lv else None

    def ask(self, side):
        b = self.bid("no" if side == "yes" else "yes")
        return None if b is None else round(1.0 - b, 4)

    def size(self, side, price):
        return (self.yes if side == "yes" else self.no).get(round(price, 4), 0.0)

    def mid(self, side):
        b, a = self.bid(side), self.ask(side)
        return None if b is None or a is None else (b + a) / 2

    def invalidate(self):
        self.ok = False


def favourite(book):
    """"yes" when the YES mid is 0.5 or more, else "no"; None when there is no YES mid."""
    m = book.mid("yes")
    if m is None:
        return None
    return "yes" if m >= 0.5 - 1e-12 else "no"


def taker_fee(contracts, price):
    """Kalshi's taker fee for one order, rounded up to the next $0.0001."""
    return math.ceil(TAKER_RATE * contracts * price * (1 - price) * 10000 - 1e-9) / 10000


def tick_at(raw, side, bid):
    """The price step just above `bid` on `side`, from the market's REST fields: price_ranges (the real grid, read on
    the YES grid for a NO bid), then tick_size (cents), then a tapered_deci_cent structure, then 1 cent."""
    raw = raw or {}
    y = bid if side == "yes" else 1.0 - bid          # where this bid sits on the YES grid
    for r in raw.get("price_ranges") or ():
        try:
            lo, hi, step = float(r["start"]), float(r["end"]), float(r["step"])
        except (KeyError, TypeError, ValueError):
            continue
        # a YES bid moves up from y; a NO bid moving up is a YES ask moving down from y
        inside = (lo - EPS <= y < hi - EPS) if side == "yes" else (lo + EPS < y <= hi + EPS)
        if inside and step > 0:
            return step
    ts = raw.get("tick_size")
    if isinstance(ts, (int, float)) and not isinstance(ts, bool) and ts > 0:
        return ts / 100
    if raw.get("price_level_structure") == "tapered_deci_cent":
        fine = (y < 0.1 - EPS or y >= 0.9 - EPS) if side == "yes" else (y <= 0.1 + EPS or y > 0.9 + EPS)
        return 0.001 if fine else 0.01
    return 0.01


# ---------------------------------------------------------------- a pretend order

def _side_price(body, side):
    key, other = ("yes_price_dollars", "no_price_dollars") if side == "yes" else ("no_price_dollars",
                                                                                  "yes_price_dollars")
    try:
        if body.get(key) is not None:
            return float(body[key])
        return 1.0 - float(body[other])
    except (TypeError, ValueError):
        return None


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class Order:
    """A pretend resting buy of `side` at limit L for `size` contracts, posted at t0 with `ahead` contracts queued
    before it at that price. `filled` (contracts so far), `fills` (list of (rt, contracts)), `done`."""

    def __init__(self, side, L, size, t0=None, ahead=0.0):
        self.side = side
        self.L = round(float(L), 4)
        self.size = float(size)
        self.t0 = t0
        self.ahead = max(0.0, float(ahead))
        self.filled = 0.0
        self.fills = []
        self.done = self.size <= EPS
        self._cuts = []    # (ts_ms, rt, contracts): queue cuts at L seen in deltas, which a trade may repeat

    def _when(self, body, rt):
        if rt is None and _num(body.get("ts_ms")):
            rt = body["ts_ms"] / 1000.0
        return rt

    def _before(self, body, rt):
        """True when the event came before the order was posted: received before t0, or stamped by Kalshi before
        t0 (a message can arrive a few ms after the event it reports). Such an event can't have filled it."""
        if self.t0 is None:
            return False
        if rt is not None and rt < self.t0:
            return True
        ts = body.get("ts_ms")
        return _num(ts) and ts / 1000.0 < self.t0

    def _fill(self, n, rt):
        n = min(n, self.size - self.filled)
        if n <= EPS:
            return 0.0
        self.filled += n
        if self.size - self.filled <= EPS:
            self.filled = self.size
            self.done = True
        self.fills.append((rt, n))
        return n

    def on_trade(self, body, rt=None):
        """A trade: only a taker who bought the other side (a seller of ours) can fill this order. Returns the
        contracts filled."""
        if self.done:
            return 0.0
        taker = body.get("taker_side")
        if taker not in ("yes", "no") or taker == self.side or body.get("is_block_trade") is True:
            return 0.0                  # a block trade is arranged off the book: it shows no seller hitting bids
        rt = self._when(body, rt)
        if self._before(body, rt):
            return 0.0
        p = _side_price(body, self.side)
        try:
            count = float(body.get("count_fp"))
        except (TypeError, ValueError):
            return 0.0
        if p is None or not count > EPS:
            return 0.0
        if p < self.L - TOL:            # the seller went through our price: we were hit first
            return self._fill(count, rt)
        if p > self.L + TOL:
            return 0.0
        count -= self._paired(body.get("ts_ms"), rt, count)     # already out of the queue via its own delta
        eat = min(self.ahead, count)
        self.ahead -= eat
        count -= eat
        return self._fill(count, rt) if count > EPS else 0.0

    def on_delta(self, body, book, rt=None):
        """A book delta, after `book` has applied it. Returns the contracts filled."""
        if self.done:
            return 0.0
        rt = self._when(body, rt)
        if self.t0 is not None and rt is not None and rt < self.t0:
            return 0.0
        side = body.get("side")
        try:
            q = float(body.get("price_dollars"))
            d = float(body.get("delta_fp"))
        except (TypeError, ValueError):
            return 0.0
        if side == self.side:
            if abs(q - self.L) <= TOL:  # orders ahead that left are gone; new ones at L join behind us
                self._cut(book.size(self.side, self.L), body.get("ts_ms"), rt)
            return 0.0
        if side in ("yes", "no") and d > EPS and 1.0 - q <= self.L + TOL and not self._before(body, rt):
            eat = min(self.ahead, d)    # a new sell of our side at L or better: it trades with the line at L
            self.ahead -= eat
            return self._fill(d - eat, rt)
        return 0.0

    def on_book(self, book, rt=None):
        """After a fresh snapshot: the queue ahead can't be longer than what is bid at L now."""
        if not self.done:
            self._cut(book.size(self.side, self.L), None, rt)

    def _cut(self, level, ts, rt):
        if level < self.ahead - EPS:
            self._cuts.append((ts, rt, self.ahead - level))
            self.ahead = level
            if len(self._cuts) > 64:
                del self._cuts[:-64]

    def _paired(self, ts, rt, count):
        """Contracts of this trade already taken out of the queue by its own delta (Kalshi usually sends the delta
        first). They must not move the queue a second time."""
        used = 0.0
        keep = []
        for cts, crt, n in self._cuts:
            if _num(cts) and _num(ts):
                gap = (ts - cts) / 1000.0
            elif crt is not None and rt is not None:
                gap = rt - crt
            else:
                gap = 0.0               # no way to tell: assume it is the same event (fewer fills)
            if used < count - EPS and abs(gap) <= PAIR:
                take = min(n, count - used)
                used += take
                n -= take
            if n > EPS and gap <= 10 * PAIR:
                keep.append((cts, crt, n))
        self._cuts = keep
        return used


# ---------------------------------------------------------------- the replay

class _Market:
    def __init__(self, ticker, meta):
        self.ticker = ticker
        self.meta = meta
        self.open = meta["open"]
        self.close = meta["close"]
        self.mark = self.open + MARK
        self.book = Book()
        self.book_sid = None
        self.trade_sid = None
        self.y6 = self.y7 = None
        self.row = None
        self.side = None
        self.orders = {}
        self.live = ()
        self.first_mid = {}
        self.after = {}
        self.taker = None
        self.hybrid = None

    def broken(self):
        """Data was lost after the mark: fills may be missing."""
        if self.row is not None:
            self.row["complete"] = False

    def mid(self):
        return self.book.mid(self.side) if self.book.ok else None


def _r(x):
    return round(x, 6)


def _rm(x):
    return None if x is None else round(x, 6)


def _order_out(o, first_mid, after, mid_close):
    if o is None:
        return None
    return {"L": o.L, "filled": _r(o.filled), "first_fill_rt": o.fills[0][0] if o.fills else None,
            "fills": [(t, _r(n)) for t, n in o.fills], "mid_at_fill": _rm(first_mid),
            "mid_after": {k: _rm(after.get(k)) for k in CHECKS}, "mid_close": _rm(mid_close)}


def _hour(t):
    return int(t // 3600)


def _file_hour(path):
    """The UTC hour (epoch hours) an hour file covers, from its name."""
    stamp = WS_NAME.match(os.path.basename(path)).group(1)
    return calendar.timegm(time.strptime(stamp, "%Y%m%dT%H")) // 3600


def log_files(folder, stem):
    """Every <stem>*.jsonl in the folder: <stem>.jsonl first, then the rest, reset numbers in order. pull.py keeps a
    reset server's log beside the laptop's as <stem>.reset<n>.jsonl, so all of them hold markets or results."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = []
    for name in names:
        if name.startswith(stem) and name.endswith(".jsonl"):
            m = re.fullmatch(re.escape(stem) + r"\.reset(\d+)\.jsonl", name)
            found.append((name != stem + ".jsonl", int(m.group(1)) if m else 0, name))
    return [os.path.join(folder, name) for _, _, name in sorted(found)]


def load_markets(folder):
    """ticker -> market line from every markets*.jsonl (first line per ticker; lines without open or close skipped)."""
    out = {}
    for path in log_files(folder, "markets"):
        for m in read_lines(path):
            t = m.get("ticker")
            try:
                o, c = float(m["open"]), float(m["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if isinstance(t, str) and t not in out and c > o:
                out[t] = dict(m, open=o, close=c)
    return out


def load_results(folder):
    """ticker -> "yes" / "no" from every results*.jsonl (first line per ticker)."""
    out = {}
    for path in log_files(folder, "results"):
        for r in read_lines(path):
            if isinstance(r.get("ticker"), str) and r.get("result") in ("yes", "no"):
                out.setdefault(r["ticker"], r["result"])
    return out


class Replay:
    """One pass over a data folder. `run()` returns the rows; `stats` counts what the data looked like.

    With `hours` (a set of epoch hours), only the markets opening in those hours are replayed: it reads the files from
    the first of those hours on, and stops once the last of its markets has closed. Each 15-minute window sits inside
    one hour and gets fresh subscriptions, so hours can be replayed apart (in parallel) with the same rows."""

    def __init__(self, folder, size=SIZE, markets=None, results=None, hours=None):
        self.folder = folder
        self.size = size
        self.markets = load_markets(folder) if markets is None else dict(markets)
        self.results = load_results(folder) if results is None else dict(results)
        self.hours = None if hours is None else set(hours)
        if self.hours is not None:
            self.markets = {t: m for t, m in self.markets.items() if _hour(m["open"]) in self.hours}
        self.active = {}
        self.finished = set()
        self.events = []
        self.n = 0
        self.seqs = {}
        self.last_rt = None
        self.rows = []
        self.stats = {"files": 0, "messages": 0, "bad_lines": 0, "gaps": 0, "holes": 0, "foreign_deltas": 0,
                      "bad_deltas": 0, "crossed": 0, "markets_listed": len(self.markets)}

    def run(self):
        # The hot loop: ~3,300 messages a second of recording, so the common path is kept short and inline.
        stats, seqs, events, apply_ = self.stats, self.seqs, self.events, self._apply
        last_rt = self.last_rt
        files = ws_files(self.folder)
        stop = None
        if self.hours is not None:
            if not self.markets:
                files = []
            else:
                lo = min(self.hours)
                files = [p for p in files if _file_hour(p) >= lo]
                stop = max(m["close"] for m in self.markets.values())
        done = False
        for path in files:
            own = self.hours is None or _file_hour(path) in self.hours
            stats["files"] += own
            restart = WS_NAME.match(os.path.basename(path)).group(2) is not None
            first = True
            n = bad = 0
            for line in _raw_lines(path):
                got = _parse(line)
                if got is None:
                    if line.strip():
                        bad += 1
                    continue
                rt, msg = got
                if last_rt is not None and ((first and restart) or self._silent(last_rt, rt)):
                    self._hole(True)
                first = False
                n += 1
                seq = msg.get("seq")
                if seq is not None:
                    sid = msg.get("sid")
                    try:
                        last = seqs.get(sid)
                        seqs[sid] = seq
                        jumped = last is not None and seq != last + 1
                    except TypeError:          # a sid or seq of the wrong type: not a stream we can check
                        jumped = False
                    if jumped:
                        self._gap(sid)
                if events and events[0][0] <= rt:
                    self._until(rt)
                if stop is not None and rt >= stop and not own:    # every market of these hours has closed
                    done = True
                    break
                typ = msg.get("type")
                if typ in BOOK_TYPES:
                    apply_(rt, typ, msg)
                if last_rt is None or rt > last_rt:
                    last_rt = rt
            if own:
                stats["messages"] += n
                stats["bad_lines"] += bad
            if done:
                break
        self.last_rt = last_rt
        if self.active:
            self._hole(False)          # after the last message nothing is known
        self._until(math.inf)
        self.rows.sort(key=lambda r: (r["mark"], r["ticker"]))
        return self.rows

    # -- data health

    def _gap(self, sid):
        """Messages on this sid were lost: books from it are unknown until their next snapshot, and trades from it
        may be missing."""
        self.stats["gaps"] += 1
        for mk in self.active.values():
            if mk.book_sid == sid:
                mk.book.invalidate()
                mk.broken()
            if mk.trade_sid == sid:
                mk.broken()

    def _silent(self, last_rt, rt):
        """True when the feed said nothing for over STALE s while a market it was following was still open. The quiet
        start of each window (the last window's markets closed, the new ones not yet subscribed) doesn't count."""
        return rt - last_rt > STALE and any(min(rt, mk.close) - last_rt > STALE for mk in self.active.values())

    def _hole(self, count):
        if count:
            self.stats["holes"] += 1
        for mk in self.active.values():
            mk.book.invalidate()
            mk.broken()

    # -- time

    def _push(self, when, ticker, kind, arg=None):
        self.n += 1
        heapq.heappush(self.events, (when, self.n, ticker, kind, arg))

    def _until(self, t):
        ev = self.events
        while ev and ev[0][0] <= t:
            when, _, ticker, kind, arg = heapq.heappop(ev)
            mk = self.active.get(ticker)
            if mk is None:
                continue
            if kind == "check":
                name, k = arg
                mk.after[name][k] = mk.mid()
            elif kind == "m6":
                mk.y6 = mk.book.mid("yes") if mk.book.ok else None
            elif kind == "m7":
                mk.y7 = mk.book.mid("yes") if mk.book.ok else None
            elif kind == "mark":
                self._mark(mk)
            elif kind == "land":
                self._land(mk)
            elif kind == "take":
                self._take(mk, when)
            elif kind == "close":
                self._close(mk)

    # -- messages

    def _activate(self, ticker, rt):
        meta = self.markets.get(ticker)
        if meta is None or ticker in self.finished or rt >= meta["close"]:
            return None
        mk = _Market(ticker, meta)
        self.active[ticker] = mk
        for when, kind in ((mk.open + 360, "m6"), (mk.open + 420, "m7"), (mk.mark, "mark")):
            if when > rt:              # an earlier time had no data for this market: unknown
                self._push(when, ticker, kind)
        self._push(mk.close, ticker, "close")
        return mk

    def _apply(self, rt, typ, msg):
        body = msg.get("msg")
        if not isinstance(body, dict):
            return
        ticker = body.get("market_ticker")
        mk = self.active.get(ticker)
        if mk is None:
            mk = self._activate(ticker, rt)
            if mk is None:
                return
        sid = msg.get("sid")
        if typ == "orderbook_delta":
            if sid != mk.book_sid:
                if mk.book_sid is not None:
                    self.stats["foreign_deltas"] += 1
                return
            if not mk.book.delta(body):
                self.stats["bad_deltas"] += 1
                mk.book.invalidate()
                mk.broken()
                return
            if mk.live and mk.book.ok:
                for name, o in mk.live:
                    if not o.done and o.on_delta(body, mk.book, rt) > 0 and len(o.fills) == 1:
                        self._first_fill(mk, name, rt)
        elif typ == "trade":
            mk.trade_sid = sid
            for name, o in mk.live:
                if not o.done and o.on_trade(body, rt) > 0 and len(o.fills) == 1:
                    self._first_fill(mk, name, rt)
        else:
            mk.book.snapshot(body)
            mk.book_sid = sid
            for name, o in mk.live:
                o.on_book(mk.book, rt)

    def _land(self, mk):
        """The orders reach Kalshi: the join order queues behind everything bid at its price by then (orders that
        joined since the mark are ahead of it too). An unknown book keeps the mark's queue."""
        o = (mk.orders or {}).get("join")
        if o is not None and not o.done and mk.book.ok:
            o.ahead = mk.book.size(o.side, o.L)

    def _first_fill(self, mk, name, rt):
        mk.first_mid[name] = mk.mid()
        for k in CHECKS:
            if rt + k < mk.close:
                self._push(rt + k, mk.ticker, "check", (name, k))

    # -- the mark, the hybrid's switch, the close

    def _mark(self, mk):
        b = mk.book
        if not b.ok:
            return
        side = favourite(b)
        if side is None:
            return
        bid, ask = b.bid(side), b.ask(side)
        if bid is None or ask is None:
            return
        if ask <= bid + TOL:           # a crossed or locked book can't be real
            self.stats["crossed"] += 1
            return
        meta = mk.meta
        res = self.results.get(mk.ticker)
        fav = (lambda y: y) if side == "yes" else (lambda y: 1.0 - y)
        in_band = LO - EPS <= ask <= HI + EPS
        mk.side = side
        mk.row = {"ticker": mk.ticker, "series": meta.get("series"), "window_open": meta.get("window_open", mk.open),
                  "open": mk.open, "close": mk.close, "mark": mk.mark, "size": self.size, "side": side,
                  "bid": bid, "ask": ask, "spread": round(ask - bid, 4), "in_band": in_band, "result": res,
                  "won": None if res is None else res == side,
                  "mid_6": None if mk.y6 is None else _rm(fav(mk.y6)),
                  "mid_7": None if mk.y7 is None else _rm(fav(mk.y7)),
                  "orders": None, "taker": None, "hybrid": None, "complete": True}
        if not in_band:
            return
        tick = round(bid + tick_at(meta.get("raw"), side, bid), 4)
        cent = round(bid + 0.01, 4)
        landed = mk.mark + LAND
        mk.orders = {"join": Order(side, bid, self.size, landed, b.size(side, bid)),
                     "tick": Order(side, tick, self.size, landed) if tick < ask - TOL else None,
                     "cent": Order(side, cent, self.size, landed) if cent < ask - TOL else None}
        mk.live = [(n, o) for n, o in mk.orders.items() if o is not None]
        self._push(landed, mk.ticker, "land")
        mk.after = {n: {} for n in KINDS + ("taker",)}
        mk.taker = {"price": ask, "fee": taker_fee(self.size, ask), "mid_at_fill": _rm(b.mid(side))}
        for k in CHECKS:
            if mk.mark + k < mk.close:
                self._push(mk.mark + k, mk.ticker, "check", ("taker", k))
        if mk.mark + TAKE_AFTER < mk.close:
            self._push(mk.mark + TAKE_AFTER, mk.ticker, "take")

    def _take(self, mk, when):
        """The hybrid at mark + TAKE_AFTER: the join's fills so far are its maker part; the rest is bought at the ask
        now if that ask is known and in band. The join's later fills are not the hybrid's."""
        join = mk.orders["join"]
        maker = join.filled
        left = self.size - maker
        ask = mk.book.ask(mk.side) if mk.book.ok else None
        first = join.fills[0][0] if join.fills else None
        if left > EPS and ask is not None and LO - EPS <= ask <= HI + EPS:
            mk.hybrid = {"maker_filled": _r(maker), "taker_filled": _r(left), "taker_price": ask,
                         "fee": taker_fee(left, ask), "first_fill_rt": when if first is None else first}
        else:
            mk.hybrid = {"maker_filled": _r(maker), "taker_filled": 0.0, "taker_price": None, "fee": 0.0,
                         "first_fill_rt": first}

    def _close(self, mk):
        del self.active[mk.ticker]
        self.finished.add(mk.ticker)
        row = mk.row
        if row is None:
            return
        if row["in_band"]:
            mid_close = mk.mid()
            if not mk.book.ok:         # an empty side (no mid) is not lost data; an unknown book is
                row["complete"] = False
            row["orders"] = {n: _order_out(o, mk.first_mid.get(n), mk.after[n], mid_close)
                             for n, o in mk.orders.items()}
            row["taker"] = dict(mk.taker, mid_after={k: _rm(mk.after["taker"].get(k)) for k in CHECKS})
            if mk.hybrid is None:      # the switch time fell after the close
                j = mk.orders["join"]
                mk.hybrid = {"maker_filled": _r(j.filled), "taker_filled": 0.0, "taker_price": None, "fee": 0.0,
                             "first_fill_rt": j.fills[0][0] if j.fills else None}
            row["hybrid"] = mk.hybrid
        self.rows.append(row)


def _part(task):
    folder, size, markets, results, hours = task
    rp = Replay(folder, size, markets, results, hours)
    return rp.run(), rp.stats


def replay_with_stats(folder, size=SIZE, workers=1):
    """(rows, stats). With workers > 1 the hours are split into runs of whole hours, replayed in parallel; the rows
    are the same as with one worker."""
    whole = Replay(folder, size)
    by_hour = {}
    for t, m in whole.markets.items():
        by_hour.setdefault(_hour(m["open"]), {})[t] = m
    hours = sorted(by_hour)
    if workers <= 1 or len(hours) <= 1:
        return whole.run(), whole.stats
    k = min(len(hours), workers * 4)
    tasks = []
    for i in range(k):
        chunk = hours[i * len(hours) // k:(i + 1) * len(hours) // k]
        markets = {t: m for h in chunk for t, m in by_hour[h].items()}
        tasks.append((folder, size, markets, {t: r for t, r in whole.results.items() if t in markets}, chunk))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(_part, tasks))
    rows = sorted((r for p in parts for r in p[0]), key=lambda r: (r["mark"], r["ticker"]))
    stats = {key: sum(p[1][key] for p in parts) for key in parts[0][1]}
    stats["markets_listed"] = len(whole.markets)
    return rows, stats


def replay(folder, size=SIZE, workers=1):
    """One row per market in markets.jsonl that had a usable book at its mark (open + MARK)."""
    return replay_with_stats(folder, size, workers)[0]


# ---------------------------------------------------------------- the summary

def _get(d, k):
    if not d:
        return None
    return d[k] if k in d else d.get(str(k))


def _rate(items):
    return sum(1 for i in items if i["won"]) / len(items) if items else None


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _item(won, size, filled, cost, profit, wait, moves):
    return {"won": won, "size": size, "filled": filled, "cost": cost, "profit": profit, "wait": wait,
            "moves": moves}


def _moves(at, after):
    if at is None:
        return {}
    out = {}
    for k in CHECKS:
        v = _get(after, k)
        if v is not None:
            out[k] = v - at
    return out


def _stats(items):
    n = len(items)
    got = [i for i in items if i["filled"] > EPS]
    none = [i for i in items if i["filled"] <= EPS]
    cost = sum(i["cost"] for i in items)
    profit = sum(i["profit"] for i in items)
    contracts = sum(i["filled"] for i in items)
    waits = [i["wait"] for i in items if i["wait"] is not None]
    return {"markets": n,
            "any_fill": len(got) / n if n else None,
            "full_fill": sum(1 for i in items if i["filled"] >= i["size"] - EPS) / n if n else None,
            "win_filled": _rate(got), "win_unfilled": _rate(none), "win_taker": _rate(items),
            "cents_per_dollar": 100 * profit / cost if cost > EPS else None,
            "mid_move": {k: _mean([i["moves"][k] for i in items if k in i["moves"]]) for k in CHECKS},
            "median_wait": statistics.median(waits) if waits else None,
            "contracts": _r(contracts), "avg_price": cost / contracts if contracts > EPS else None}


def _pnl(contracts, price, won):
    return contracts * ((1 - price) if won else -price)


def summarise(rows, size=SIZE):
    """Per pretend order kind and for the taker, over in-band rows with a known result."""
    base = [r for r in rows if r.get("in_band") and r.get("won") is not None]
    out = {}
    for kind in KINDS:
        items, placed = [], 0
        for r in base:
            o = (r.get("orders") or {}).get(kind)
            sz = r.get("size", size)
            if o is None:              # couldn't be placed: no room under the ask
                items.append(_item(r["won"], sz, 0.0, 0.0, 0.0, None, {}))
                continue
            placed += 1
            L, f, first = o["L"], o["filled"], o.get("first_fill_rt")
            mark = r.get("mark", r.get("window_open", 0) + MARK)
            items.append(_item(r["won"], sz, f, f * L, _pnl(f, L, r["won"]),
                               None if first is None else first - mark, _moves(o.get("mid_at_fill"),
                                                                               o.get("mid_after"))))
        out[kind] = dict(_stats(items), placed=placed)
    items = []
    for r in base:
        h = r.get("hybrid")
        sz = r.get("size", size)
        join = (r.get("orders") or {}).get("join")
        if not h or not join:
            items.append(_item(r["won"], sz, 0.0, 0.0, 0.0, None, {}))
            continue
        mf, tf, tp = h["maker_filled"], h["taker_filled"], h.get("taker_price")
        cost = mf * join["L"] + (tf * tp if tf else 0.0)
        profit = _pnl(mf, join["L"], r["won"]) + (_pnl(tf, tp, r["won"]) - h.get("fee", 0.0) if tf else 0.0)
        first = h.get("first_fill_rt")
        mark = r.get("mark", r.get("window_open", 0) + MARK)
        items.append(_item(r["won"], sz, mf + tf, cost, profit, None if first is None else first - mark, {}))
    out["hybrid"] = _stats(items)
    items = []
    for r in base:
        t = r.get("taker")
        if not t:
            continue
        sz = r.get("size", size)
        items.append(_item(r["won"], sz, sz, sz * t["price"], _pnl(sz, t["price"], r["won"]) - t["fee"], 0.0,
                           _moves(t.get("mid_at_fill"), t.get("mid_after"))))
    out["taker"] = _stats(items)
    return out


# ---------------------------------------------------------------- the report

def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _c(x):
    return "n/a" if x is None else f"{x:+.2f}"


def _move(x):
    return "n/a" if x is None else f"{100 * x:+.2f}c"


def _price(x):
    return "n/a" if x is None else f"{100 * x:.2f}c"


def words(rows, summary, stats, out=None, size=SIZE):
    """The plain-words summary the report command prints."""
    say = []
    say.append("Maker shadow replay: what a waiting order placed at minute 8 would have got.")
    files = stats.get("files", 0)
    say.append(f"Data: {files:,} hour file{'' if files == 1 else 's'}, {stats.get('messages', 0):,} messages, "
               f"{stats.get('markets_listed', 0):,} markets listed.")
    if out:
        say.append(f"Full results: {out}")
    say.append(f"Data checks: {stats.get('gaps', 0):,} sequence gaps (messages Kalshi sent that never arrived), "
               f"{stats.get('holes', 0):,} holes (the feed went quiet for over {STALE} s, or the recorder restarted). "
               f"{stats.get('bad_lines', 0):,} lines could not be read.")
    broken = sum(1 for r in rows if r.get("in_band") and not r.get("complete", True))
    if broken:
        say.append(f"{broken:,} in-band markets lost data between minute 8 and the close. Their fills may be too "
                   "low.")
    if not rows:
        say.append("No market had a usable book at minute 8, so there is nothing to report yet.")
        return "\n".join(say)
    in_band = [r for r in rows if r.get("in_band")]
    known = [r for r in in_band if r.get("won") is not None]
    say.append("")
    say.append(f"Markets: {len(rows):,} had a usable book at minute 8. {len(in_band):,} were in the bot's band "
               "(a price range: the favourite, the likely side, had an ask of 92c to 99.9c).")
    say.append(f"{len(known):,} of those have a result. Everything below uses only those {len(known):,}.")
    if not known:
        say.append("No in-band market has a result yet, so there is nothing to score.")
        return "\n".join(say)
    t = summary["taker"]
    say.append("")
    say.append("Buying at the ask, the bot's way. This is a taker: it pays Kalshi's taker fee (Kalshi's charge for "
               "trading, biggest near 50c).")
    say.append(f"- It won {_pct(t['win_taker'])} of the time.")
    say.append(f"- Profit: {_c(t['cents_per_dollar'])} cents of profit for every dollar bet.")
    say.append(f"- Average price paid: {_price(t['avg_price'])}.")
    mm = t["mid_move"]
    say.append(f"- The favourite's mid price (halfway between its bid and ask) moved {_move(mm[CHECKS[0]])} in the "
               f"{CHECKS[0]} s after minute 8, {_move(mm[CHECKS[1]])} by {CHECKS[1]} s and {_move(mm[CHECKS[2]])} by "
               f"{CHECKS[2]} s. That is the normal drift, to compare the waiting orders with.")
    about = {
        "join": "Join: wait at the favourite's bid, behind the orders already waiting there.",
        "tick": "Tick: wait one price step above the bid (0.1c or 1c, by the market's price grid). It is first in "
                "line there.",
        "cent": "Cent: wait 1c above the bid. It is first in line there.",
        "hybrid": f"Hybrid: join for {TAKE_AFTER} s. Then buy whatever is still missing at the ask, with the taker "
                  "fee, if the ask is still in the band.",
    }
    for kind in KINDS + ("hybrid",):
        s = summary[kind]
        say.append("")
        say.append(about[kind])
        if kind in ("tick", "cent"):
            say.append(f"- It could be placed in {s['placed']:,} of {s['markets']:,} markets. In the rest the ask "
                       "was too close. Those count as unfilled.")
        say.append(f"- The fill share (how often the waiting order got any contracts) was {_pct(s['any_fill'])}.")
        say.append(f"- The full fill share (how often it got all {size} contracts) was {_pct(s['full_fill'])}.")
        say.append(f"- It won {_pct(s['win_filled'])} of the markets where it got contracts, and "
                   f"{_pct(s['win_unfilled'])} where it got none. The taker won {_pct(s['win_taker'])} of the same "
                   "markets.")
        fee = "Makers pay no fee here." if kind != "hybrid" else "The fee is paid only on the part bought at the ask."
        say.append(f"- Profit on what it got: {_c(s['cents_per_dollar'])} cents of profit for every dollar bet. "
                   f"{fee}")
        say.append(f"- Average price paid: {_price(s['avg_price'])}, against {_price(t['avg_price'])} for the "
                   "taker.")
        if kind != "hybrid":
            mm = s["mid_move"]
            say.append(f"- After its first fill, the mid price moved {_move(mm[CHECKS[0]])} by {CHECKS[0]} s, "
                       f"{_move(mm[CHECKS[1]])} by {CHECKS[1]} s and {_move(mm[CHECKS[2]])} by {CHECKS[2]} s.")
        wait = s["median_wait"]
        say.append("- Typical wait (the median, the middle value) from minute 8 to the first contract: "
                   + ("n/a." if wait is None else f"{wait:.0f} s."))
    say.append("")
    say.append("How to read this. A waiting order gets picked off (adverse selection: getting picked off by someone "
               "who knows more than you) when it fills mostly just before the favourite loses. Two signs show it: "
               "orders that got contracts win less often than the taker, and the mid price falls right after a "
               "fill.")
    return "\n".join(say)


def report(folder, out=None, size=SIZE, workers=1):
    rows, stats = replay_with_stats(folder, size, workers)
    summary = summarise(rows, size)
    out = out or os.path.join(folder, "report.json")
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    part = out + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        json.dump({"data": os.path.abspath(folder), "size": size, "stats": stats, "summary": summary,
                   "rows": rows}, fh)
    os.replace(part, out)
    print(words(rows, summary, stats, out, size))
    return rows, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Replay the maker shadow recording with pretend resting orders.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("report", help="replay a data folder, write the rows and summary as JSON, print a summary")
    rep.add_argument("--data", required=True, help="the folder the recorder wrote (hour files, markets.jsonl, ...)")
    rep.add_argument("--out", default=None, help="where to write the JSON (default: report.json in the data folder)")
    rep.add_argument("--size", type=float, default=SIZE, help=f"contracts per pretend order (default {SIZE})")
    rep.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                     help="processes replaying hours in parallel (default: half the cores; 1 = one process)")
    args = ap.parse_args(argv)
    size = int(args.size) if float(args.size).is_integer() else args.size
    report(args.data, args.out, size, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
