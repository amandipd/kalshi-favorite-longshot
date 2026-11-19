"""fast_entry.MarkReader: the paper fast entry's order-book reader (research/kalshi_15min/lab/fast_entry/timing.md,
Round 3).

Real orders keep today's timing. The bot also wants to know what an instant order could have bought at exactly minute 8
(the mark, 480.0 s into the window) on Kalshi's clock. MarkReader is a daemon thread (one that never keeps the program
alive) that does only HTTP, on a public Kalshi client of its own:
- at list_at (470 s) it lists the window's markets;
- at the mark it reads every listed market's order book at once, up to 8 at a time;
- it keeps {ticker: (raw book, when it answered on Kalshi's clock)} for the bot to pick up with books(window_open).
Kalshi's clock is the PC's plus an offset from NTP (Network Time Protocol: asking time servers what time it is). The
offset is refreshed every ntp_every s, but never from 10 s before list_at to 5 s after the mark.

How: a fake clock whose sleep() moves it on at once, so no test waits for minute 8, and a fake Kalshi that notes each
call with the fake clock's time, so a test can see when it listed and when it read. Nothing touches the network or
SQLite, and the real sleeping adds up to about a tenth of a second.

    python -m pytest tests/test_mark_reader.py -q
"""
import ast
import inspect
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone

import pytest
import requests

from kalshi_bot import fast_entry

W = 1791777600              # a window's open time (Oct 2026): the 15-minute windows open on multiples of 900 s
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M"]


class Runaway(BaseException):
    """Raised by the fakes when a loop runs on far past where its test meant it to stop. `except Exception` lets it
    through, so a stop that doesn't work fails the test instead of hanging it."""


class Clock:
    """A fake PC clock. sleep(s) moves it on by s at once and notes s (by at most `most` s, like a sleep that ends
    early); advance(s) is time passing inside a call to Kalshi. A lock makes it safe to read from the reading threads."""

    def __init__(self, t, most=None, limit=None):
        self.t, self.most = float(t), most
        self.limit = self.t + 50 * 900 if limit is None else limit
        self.sleeps, self.lock = [], threading.Lock()

    def __call__(self):
        with self.lock:
            return self.t

    def sleep(self, s):
        with self.lock:
            self.sleeps.append(s)
            self.t += s if self.most is None else min(s, self.most)
            if self.t > self.limit:
                raise Runaway(f"the fake clock passed {self.limit}: the loop never stopped")

    def advance(self, s):
        with self.lock:
            self.t += s


def iso(t):
    """A time as Kalshi writes it, which bot.ts parses: "2026-10-12T04:00:00Z", with milliseconds when it has them."""
    spec = "seconds" if t == int(t) else "milliseconds"
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec=spec).replace("+00:00", "Z")


def ticker(series, opens):
    return f"{series}-{int(opens)}"


def tickers(w, series=SERIES):
    return {ticker(s, w) for s in series}


def mk(t, opens):
    return {"ticker": t, "open_time": iso(opens), "close_time": iso(opens + 900)}


def book(t):
    """A raw order book as Kalshi sends it, naming its ticker so a test can tell whose it is."""
    return {"orderbook_fp": {"yes_dollars": [["0.0400", "120.00"]], "no_dollars": [["0.9300", "75.00"]]}, "ticker": t}


class Kalshi:
    """A fake public Kalshi on the fake clock that notes each call with the clock's time.

    markets() answers a series with its market in the window the clock is in and the next window's (which the reader
    must leave out), unless `listing` gives that series' answer: a dict, None, or an exception to raise. Each listing
    takes `list_lag` s. orderbook() answers book(ticker), unless `answers` gives that ticker's (None or an exception);
    `on_book(ticker)` runs inside each read, and each read takes `lag` s."""

    def __init__(self, clock, listing=None, answers=None, on_book=None, lag=0.0, list_lag=0.0):
        self.clock, self.listing, self.answers = clock, listing or {}, answers or {}
        self.on_book, self.lag, self.list_lag = on_book, lag, list_lag
        self.listed, self.read, self.lock = [], [], threading.Lock()

    def markets(self, **params):
        now = self.clock()
        with self.lock:
            self.listed.append((now, params))
        if self.list_lag:
            self.clock.advance(self.list_lag)
        s = params.get("series_ticker")
        if s in self.listing:
            got = self.listing[s]
        else:
            w = now - now % 900
            got = {"markets": [mk(ticker(s, w), w), mk(ticker(s, w + 900), w + 900)], "cursor": ""}
        if isinstance(got, Exception):
            raise got
        return got

    def orderbook(self, t):
        with self.lock:
            self.read.append((self.clock(), t))
        if self.on_book:
            self.on_book(t)
        if self.lag:
            self.clock.advance(self.lag)
        got = self.answers.get(t, book(t))
        if isinstance(got, Exception):
            raise got
        return got


def make(k, clock, series=SERIES, ntp=lambda: None, **kw):
    """A MarkReader on the fakes. `series` is the list series_fn answers, or series_fn itself."""
    fn = series if callable(series) else (lambda: list(series))
    return fast_entry.MarkReader(k, fn, clock=clock, sleep=clock.sleep, ntp=ntp, **kw)


@pytest.fixture
def printed(monkeypatch):
    """Every print while the test runs: (its text, its keyword arguments)."""
    lines = []
    monkeypatch.setattr("builtins.print", lambda *a, **kw: lines.append((" ".join(map(str, a)), kw)))
    return lines


def logged(printed, words):
    """Whether `words` were printed, and flushed straight away."""
    return any(words in text and kw.get("flush") for text, kw in printed)


# ------------------------------------------------------------------ the thread
def test_the_constructor_and_its_defaults():
    params = inspect.signature(fast_entry.MarkReader).parameters
    assert list(params) == ["client", "series_fn", "list_at", "mark", "ntp_every", "clock", "sleep", "ntp", "keep"]
    defaults = {n: p.default for n, p in params.items() if p.default is not inspect.Parameter.empty}
    assert defaults == {"list_at": 470, "mark": fast_entry.MARK, "ntp_every": 900, "clock": time.time,
                        "sleep": time.sleep, "ntp": None, "keep": 4}


def test_it_is_a_daemon_thread_named_mark_reader_that_waits_to_be_started():
    c, asked = Clock(W + 100), []
    k = Kalshi(c)
    r = make(k, c, ntp=lambda: asked.append(1))
    assert isinstance(r, threading.Thread)
    assert r.daemon is True and r.name == "mark-reader"
    assert not r.is_alive()
    assert r.offset == 0.0 and isinstance(r.offset, float)
    assert isinstance(r.stop, threading.Event) and not r.stop.is_set()
    assert (k.listed, k.read, asked, c.sleeps) == ([], [], [], [])          # building it does nothing yet


def test_by_default_it_asks_fast_entry_ntp_offset(monkeypatch):
    monkeypatch.setattr(fast_entry, "ntp_offset", lambda: 0.42, raising=False)
    c = Clock(W + 100)
    r = fast_entry.MarkReader(Kalshi(c), lambda: SERIES, clock=c, sleep=c.sleep)
    assert r.refresh_clock(W + 100) is True
    assert r.offset == 0.42


def test_it_never_imports_or_touches_sqlite(monkeypatch):
    """It runs off the bot's thread, and the bot's ledger is SQLite, used on the bot's own thread only."""
    src = open(fast_entry.__file__, encoding="utf-8").read()
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "sqlite3" not in imported
    assert "sqlite" not in inspect.getsource(fast_entry.MarkReader).lower()

    def no_sqlite(*a, **kw):
        raise AssertionError("the mark reader opened a database")

    monkeypatch.setattr(sqlite3, "connect", no_sqlite)
    c = Clock(W + 100)
    r = make(Kalshi(c), c)
    assert set(r.run_window(W)) == tickers(W)


# ------------------------------------------------------------------ refresh_clock: Kalshi's time from NTP
def test_the_first_refresh_asks_ntp_and_takes_its_offset():
    c, asked = Clock(W + 470), []      # the PC's clock: refresh_clock goes by the Kalshi time it's given, not this
    r = make(Kalshi(c), c, ntp=lambda: asked.append(1) or 0.155)
    assert r.refresh_clock(W + 100) is True
    assert asked == [1] and r.offset == 0.155


@pytest.mark.parametrize("every", [900, 60])
def test_it_refreshes_again_only_once_ntp_every_has_passed(every):
    c, asked = Clock(W + 100), []
    answers = iter([0.155, 0.16, 0.17])

    def ntp():
        asked.append(1)
        return next(answers)

    r = make(Kalshi(c), c, ntp=ntp, **({} if every == 900 else {"ntp_every": every}))
    assert r.refresh_clock(W + 100) is True
    assert r.refresh_clock(W + 100 + every - 0.5) is False
    assert (len(asked), r.offset) == (1, 0.155)
    assert r.refresh_clock(W + 100 + every) is True                         # at least ntp_every: exactly is enough
    assert (len(asked), r.offset) == (2, 0.16)
    assert r.refresh_clock(W + 100 + every + 1) is False


@pytest.mark.parametrize("into", [460, 465, 470, 475, 480, 485])
def test_it_never_refreshes_from_10s_before_list_at_to_5s_after_the_mark(into):
    c, asked = Clock(W + into), []
    r = make(Kalshi(c), c, ntp=lambda: asked.append(1) or 0.155)
    assert r.refresh_clock(W + into) is False
    assert asked == [] and r.offset == 0.0


@pytest.mark.parametrize("into", [0, 459.5, 485.5, 899.5])
def test_outside_that_stretch_the_first_refresh_goes_ahead(into):
    c, asked = Clock(W + into), []
    r = make(Kalshi(c), c, ntp=lambda: asked.append(1) or 0.155)
    assert r.refresh_clock(W + into) is True
    assert asked == [1] and r.offset == 0.155


@pytest.mark.parametrize("into, refreshes", [(389.5, True), (390, False), (425, False), (425.5, True)])
def test_the_stretch_follows_list_at_and_the_mark(into, refreshes):
    c = Clock(W + into)
    r = make(Kalshi(c), c, ntp=lambda: 0.155, list_at=400, mark=420)
    assert r.refresh_clock(W + into) is refreshes
    assert r.offset == (0.155 if refreshes else 0.0)


def test_a_none_from_ntp_keeps_the_old_offset():
    c = Clock(W + 100)
    answers = iter([0.155, None])
    r = make(Kalshi(c), c, ntp=lambda: next(answers), ntp_every=60)
    assert r.refresh_clock(W + 100) is True and r.offset == 0.155
    assert r.refresh_clock(W + 160) is True                                 # it asked; no answer
    assert r.offset == 0.155


def test_a_none_from_the_first_ntp_leaves_the_offset_at_zero():
    c = Clock(W + 100)
    r = make(Kalshi(c), c, ntp=lambda: None)
    assert r.refresh_clock(W + 100) is True
    assert r.offset == 0.0


def test_an_offset_of_zero_or_below_is_still_an_offset():
    c = Clock(W + 100)
    answers = iter([0.155, 0.0, -0.3])
    r = make(Kalshi(c), c, ntp=lambda: next(answers), ntp_every=60)
    r.refresh_clock(W + 100)
    assert r.refresh_clock(W + 160) is True and r.offset == 0.0
    assert r.refresh_clock(W + 220) is True and r.offset == -0.3            # a PC ahead of Kalshi


# ------------------------------------------------------------------ run_window: when it lists and reads
def test_it_lists_at_list_at_and_reads_every_listed_book_at_the_mark():
    c = Clock(W + 100)
    k = Kalshi(c)
    r = make(k, c)
    r.run_window(W)
    assert sorted(p["series_ticker"] for _, p in k.listed) == sorted(SERIES)          # each series once
    assert all(p == {"series_ticker": p["series_ticker"], "min_close_ts": W + 899, "max_close_ts": W + 901,
                     "limit": 50} for _, p in k.listed)   # by close time, not the status filter (test_listing.py)
    assert all(t == W + 470 for t, _ in k.listed)
    assert sorted(tk for _, tk in k.read) == sorted(tickers(W))                       # each listed market once
    assert all(t == W + 480 for t, _ in k.read)                                       # at the mark, not before
    assert all(s >= 0 for s in c.sleeps) and sum(c.sleeps) == pytest.approx(380)


@pytest.mark.parametrize("offset", [0.155, -0.2])
def test_the_offset_moves_every_wake_time(offset):
    """Kalshi's time is the PC's plus the offset: with the PC 0.155 s behind, Kalshi's minute 8 is 480 − 0.155 s into
    the window on the PC's clock."""
    c = Clock(W + 100)
    k = Kalshi(c)
    r = make(k, c)
    r.offset = offset
    r.run_window(W)
    assert k.listed and all(t == pytest.approx(W + 470 - offset, abs=1e-6) for t, _ in k.listed)
    assert k.read and all(t == pytest.approx(W + 480 - offset, abs=1e-6) for t, _ in k.read)
    assert all(a == pytest.approx(W + 480, abs=1e-6) for _, a in r.books(W).values())   # answered, Kalshi's time


def test_it_keeps_sleeping_until_the_clock_gets_there():
    """A sleep may end early (here none lasts over 60 s): it sleeps again until the clock reaches the time."""
    c = Clock(W, most=60)
    k = Kalshi(c)
    make(k, c).run_window(W)
    assert len(c.sleeps) > 2
    assert k.listed and all(t == pytest.approx(W + 470, abs=1e-6) for t, _ in k.listed)
    assert k.read and all(t == pytest.approx(W + 480, abs=1e-6) for t, _ in k.read)


def test_started_between_list_at_and_the_mark_it_lists_at_once_and_still_waits_for_the_mark():
    c = Clock(W + 475)
    k = Kalshi(c)
    got = make(k, c).run_window(W)
    assert all(t == W + 475 for t, _ in k.listed)
    assert all(t == W + 480 for t, _ in k.read) and set(got) == tickers(W)
    assert all(s >= 0 for s in c.sleeps)


def test_list_at_and_the_mark_are_whatever_they_are_given():
    c = Clock(W + 100)
    k = Kalshi(c)
    make(k, c, list_at=440, mark=450).run_window(W)
    assert k.listed and all(t == W + 440 for t, _ in k.listed)
    assert k.read and all(t == W + 450 for t, _ in k.read)


def test_it_asks_series_fn_afresh_at_each_windows_list_at():
    """The bot's universe of series can change between windows."""
    c, asked = Clock(W + 100), []
    lists = iter([["KXBTC15M"], ["KXETH15M", "KXXRP15M"]])

    def series_fn():
        asked.append(c())
        return next(lists)

    r = make(Kalshi(c), c, series=series_fn)
    r.run_window(W)
    r.run_window(W + 900)
    assert asked == [W + 470, W + 1370]
    assert set(r.books(W)) == {ticker("KXBTC15M", W)}
    assert set(r.books(W + 900)) == {ticker("KXETH15M", W + 900), ticker("KXXRP15M", W + 900)}


# ------------------------------------------------------------------ run_window: what it keeps
def test_it_stores_each_listed_markets_raw_book_and_when_it_answered_on_kalshis_clock():
    c = Clock(W + 100)
    k = Kalshi(c, lag=0.25)                                 # the read takes 0.25 s
    r = make(k, c, series=["KXBTC15M"])
    r.offset = 0.155
    got = r.run_window(W)
    t = ticker("KXBTC15M", W)
    assert set(got) == {t} and isinstance(got[t], tuple)
    raw, answered = got[t]
    assert raw == book(t)
    assert answered == pytest.approx(W + 480.25, abs=1e-6)  # sent at 480 Kalshi time, answered 0.25 s later
    assert r.books(W) == got


def test_it_keeps_only_the_markets_opening_within_1s_of_the_window():
    c = Clock(W + 100)
    listing = {"KXBTC15M": {"markets": [mk("ON", W), mk("HALF-LATE", W + 0.5), mk("HALF-EARLY", W - 0.5),
                                        mk("2S-LATE", W + 2), mk("1.5S-EARLY", W - 1.5), mk("NEXT", W + 900),
                                        mk("LAST", W - 900)]}}
    k = Kalshi(c, listing=listing)
    got = make(k, c, series=["KXBTC15M", "KXETH15M"]).run_window(W)
    assert set(got) == {"ON", "HALF-LATE", "HALF-EARLY", ticker("KXETH15M", W)}
    assert {tk for _, tk in k.read} == set(got)


def test_a_market_whose_open_time_is_missing_or_unreadable_is_left_out():
    c = Clock(W + 100)
    listing = {"KXBTC15M": {"markets": [{"ticker": "NO-TIME"}, {"ticker": "NULL-TIME", "open_time": None},
                                        {"ticker": "BAD-TIME", "open_time": "soon"}, mk("ON", W)]}}
    k = Kalshi(c, listing=listing)
    got = make(k, c, series=["KXBTC15M"]).run_window(W)
    assert set(got) == {"ON"}
    assert [tk for _, tk in k.read] == ["ON"]


def test_a_none_empty_or_failing_listing_skips_only_that_series():
    c = Clock(W + 100)
    series = SERIES + ["KXXRP15M", "KXDOGE15M"]
    listing = {"KXBTC15M": None, "KXETH15M": {}, "KXSOL15M": RuntimeError("listing broke"),
               "KXXRP15M": {"markets": []}}
    k = Kalshi(c, listing=listing)
    got = make(k, c, series=series).run_window(W)
    assert sorted(p["series_ticker"] for _, p in k.listed) == sorted(series)
    assert set(got) == {ticker("KXDOGE15M", W)}


@pytest.mark.parametrize("series, listing", [([], {}), (SERIES, {s: None for s in SERIES})])
def test_with_no_markets_listed_it_reads_and_stores_nothing(series, listing):
    c = Clock(W + 100)
    k = Kalshi(c, listing=listing)
    r = make(k, c, series=series)
    assert r.run_window(W) is None
    assert k.read == [] and r.books(W) == {}


def test_a_book_read_that_fails_or_answers_none_is_kept_as_none_with_its_time():
    c = Clock(W + 100)
    series = SERIES + ["KXXRP15M"]
    btc, eth, sol, xrp = (ticker(s, W) for s in series)
    k = Kalshi(c, answers={btc: RuntimeError("bad gateway"), eth: requests.ConnectionError("reset"), sol: None})
    got = make(k, c, series=series).run_window(W)
    assert set(got) == {btc, eth, sol, xrp}
    for t in (btc, eth, sol):
        raw, answered = got[t]
        assert raw is None and answered == pytest.approx(W + 480, abs=1e-6)
    assert got[xrp][0] == book(xrp)


def test_the_books_are_read_at_the_same_time():
    """Each read waits until all three are in flight (2 s, then it gives up and the read fails)."""
    c = Clock(W + 100)
    barrier = threading.Barrier(3, timeout=2)
    k = Kalshi(c, on_book=lambda t: barrier.wait())
    got = make(k, c).run_window(W)
    assert set(got) == tickers(W) and all(raw is not None for raw, _ in got.values())


def test_eight_books_are_read_at_the_same_time():
    c = Clock(W + 100)
    series = [f"KXS{i}15M" for i in range(8)]
    barrier = threading.Barrier(8, timeout=2)
    k = Kalshi(c, on_book=lambda t: barrier.wait())
    got = make(k, c, series=series).run_window(W)
    assert set(got) == tickers(W, series) and all(raw is not None for raw, _ in got.values())


def test_never_more_than_eight_books_are_read_at_once():
    c = Clock(W + 100)
    series = [f"KXS{i}15M" for i in range(10)]
    lock, now, most = threading.Lock(), [0], [0]

    def on_book(t):
        with lock:
            now[0] += 1
            most[0] = max(most[0], now[0])
        try:
            time.sleep(0.05)        # real time, long enough for every reading thread there is to start a read
        finally:
            with lock:
                now[0] -= 1

    got = make(Kalshi(c, on_book=on_book), c, series=series).run_window(W)
    assert most[0] <= 8
    assert set(got) == tickers(W, series) and all(raw is not None for raw, _ in got.values())


# ------------------------------------------------------------------ run_window: too late for the mark
def test_started_more_than_2s_after_the_mark_it_skips_the_window():
    c = Clock(W + 482.5)
    k = Kalshi(c)
    r = make(k, c)
    assert r.run_window(W) is None
    assert k.read == [] and r.books(W) == {}


@pytest.mark.parametrize("into", [480, 481.5, 482])
def test_up_to_2s_after_the_mark_it_still_reads_at_once(into):
    c = Clock(W + into)
    k = Kalshi(c)
    got = make(k, c).run_window(W)
    assert set(got) == tickers(W)
    assert all(t == W + into for t, _ in k.read)
    assert all(s >= 0 for s in c.sleeps)


@pytest.mark.parametrize("pc, offset, reads", [(481.6, 0.6, False), (482.4, -0.6, True)])
def test_late_is_judged_on_kalshis_clock(pc, offset, reads):
    """481.6 on the PC is 482.2 on Kalshi's clock with the PC 0.6 s behind: too late. 482.4 with it 0.6 s ahead is
    481.8: in time."""
    c = Clock(W + pc)
    k = Kalshi(c)
    r = make(k, c)
    r.offset = offset
    got = r.run_window(W)
    assert (got is not None, bool(k.read), bool(r.books(W))) == (reads, reads, reads)


def test_a_listing_that_runs_past_the_mark_skips_the_window():
    c = Clock(W + 100)
    k = Kalshi(c, list_lag=13)                  # listed at 470, done at 483
    r = make(k, c, series=["KXBTC15M"])
    assert r.run_window(W) is None
    assert k.read == [] and r.books(W) == {}


def test_an_error_from_series_fn_comes_out_of_run_window_and_nothing_is_listed_or_kept():
    c = Clock(W + 100)
    k = Kalshi(c)

    def series_fn():
        raise RuntimeError("no universe yet")

    r = make(k, c, series=series_fn)
    with pytest.raises(RuntimeError, match="no universe yet"):
        r.run_window(W)
    assert (k.listed, k.read, r.books(W)) == ([], [], {})


# ------------------------------------------------------------------ books() and the store
def test_books_hands_out_a_copy_and_an_empty_dict_for_a_window_it_does_not_have():
    c = Clock(W + 100)
    r = make(Kalshi(c), c)
    r.run_window(W)
    got = r.books(W)
    want = dict(got)
    assert set(want) == tickers(W)
    got.clear()
    got["X"] = (None, 0.0)
    assert r.books(W) == want
    other = r.books(W + 900)
    assert other == {}
    other["X"] = (None, 0.0)
    assert r.books(W + 900) == {}


@pytest.mark.parametrize("keep", [None, 1, 2])
def test_it_keeps_only_the_last_keep_windows(keep):
    c = Clock(W + 100)
    r = make(Kalshi(c), c, **({} if keep is None else {"keep": keep}))
    windows = [W + 900 * i for i in range((4 if keep is None else keep) + 1)]       # 4 by default
    for w in windows:
        r.run_window(w)
    assert r.books(windows[0]) == {}
    for w in windows[1:]:
        assert set(r.books(w)) == tickers(w)


def test_a_window_it_keeps_nothing_for_pushes_no_older_one_out():
    c = Clock(W + 100)
    lists = iter([SERIES, [], SERIES])
    r = make(Kalshi(c), c, series=lambda: next(lists), keep=1)
    r.run_window(W)
    assert r.run_window(W + 900) is None                    # no markets listed
    c.advance(W + 1800 + 483 - c())
    assert r.run_window(W + 1800) is None                   # 3 s after the mark
    assert set(r.books(W)) == tickers(W)


def test_a_lock_guards_the_store():
    assert re.search(r"\b(R?Lock|Condition)\(", inspect.getsource(fast_entry.MarkReader))


def test_books_can_be_read_from_other_threads_while_windows_are_stored():
    c = Clock(W)
    series = SERIES + ["KXXRP15M", "KXDOGE15M"]
    r = make(Kalshi(c), c, series=series, keep=3)
    windows = [W + 900 * i for i in range(10)]
    done, errors, looks = threading.Event(), [], [0]

    def store():
        try:
            for w in windows:
                r.run_window(w)
        except BaseException as e:
            errors.append(e)
        finally:
            done.set()

    def look():
        try:
            while not done.is_set():
                for w in windows:
                    got = r.books(w)
                    assert set(got) <= tickers(w, series)
                    for t, (raw, answered) in got.items():
                        assert raw == book(t) and answered == pytest.approx(w + 480, abs=1e-6)
                    got.clear()                             # the copy is the caller's to change
                    got["X"] = (None, 0.0)
                    looks[0] += 1
        except BaseException as e:
            errors.append(e)

    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-5)                             # switch threads often, so a missing lock would show
    try:
        threads = [threading.Thread(target=store)] + [threading.Thread(target=look) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
    finally:
        sys.setswitchinterval(old)
    assert errors == [] and looks[0] > 0
    for w in windows[:-3]:
        assert r.books(w) == {}
    for w in windows[-3:]:
        assert set(r.books(w)) == tickers(w, series)


# ------------------------------------------------------------------ run(): the loop
@pytest.mark.parametrize("into, offset, window", [
    (100, 0.0, W), (469, 0.0, W), (470.5, 0.0, W + 900), (479, 0.0, W + 900), (600, 0.0, W + 900),
    (899, 0.0, W + 900), (467, 2.0, W), (469, 2.0, W + 900)])
def test_run_refreshes_the_clock_then_does_the_next_window_whose_list_at_has_not_passed(into, offset, window):
    """On Kalshi's clock: 469 s on the PC is 471 on Kalshi's with the PC 2 s behind, past this window's list_at."""
    c = Clock(W + into)
    r = make(Kalshi(c), c)
    r.offset = offset
    events = []

    def refresh_clock(*a, **kw):
        events.append(("refresh", (list(a) + list(kw.values()))[0]))
        return False

    def run_window(w):
        events.append(("window", w))
        r.stop.set()
        if len(events) > 40:
            raise Runaway("run() never stopped")

    r.refresh_clock, r.run_window = refresh_clock, run_window
    r.run()
    kind, now = events[0]
    assert kind == "refresh" and now == pytest.approx(W + into + offset, abs=1e-6)     # Kalshi's time
    assert [e for e in events if e[0] == "window"][0] == ("window", window)


def test_run_takes_the_offset_from_ntp_then_reads_window_after_window():
    c, asked = Clock(W + 100), []

    def ntp():
        asked.append(c())
        return 0.155

    k = Kalshi(c, on_book=lambda t: r.stop.set() if c() > W + 1800 else None)
    r = make(k, c, ntp=ntp)
    r.run()
    assert asked[0] == W + 100 and r.offset == 0.155        # at the start, before anything was listed
    assert min(t for t, _ in k.listed) > asked[0]
    for w in (W, W + 900, W + 1800):
        assert set(r.books(w)) == tickers(w)
        reads = [t for t, tk in k.read if tk in tickers(w)]
        assert reads and all(t == pytest.approx(w + 480 - 0.155, abs=1e-6) for t in reads)


def test_run_keeps_refreshing_the_clock_between_windows_not_only_at_the_start():
    """The PC's clock drifts (about 0.5 s a day), so the offset is refreshed every ntp_every s. run_window returns just
    after the mark, inside the stretch where refreshing is off, so a loop that only refreshed right after it would
    never refresh again: run() has to give refresh_clock a turn outside that stretch."""
    c, asked, used = Clock(W + 100), [], []
    answers = iter([0.1, 0.12, 0.14, 0.16, 0.18, 0.2, 0.22, 0.24])

    def ntp():
        asked.append((c() + r.offset) % 900)                # seconds into the window, on Kalshi's clock
        return next(answers)

    def on_book(t):
        used.append((c(), t, r.offset))
        if c() > W + 2700:
            r.stop.set()

    k = Kalshi(c, on_book=on_book)
    r = make(k, c, ntp=ntp, series=["KXBTC15M"])
    r.run()
    assert len(asked) >= 2
    assert all(not 460 <= into <= 485 for into in asked)
    for w in (W, W + 900, W + 1800, W + 2700):
        assert set(r.books(w)) == tickers(w, ["KXBTC15M"])
    for when, t, offset in used:                            # each window read at the mark by the offset of the day
        assert when == pytest.approx(int(t.rsplit("-", 1)[1]) + 480 - offset, abs=1e-6)
    assert len({offset for *_, offset in used}) >= 2        # a later window used a refreshed offset


def test_an_error_in_a_turn_is_logged_and_the_loop_goes_on_after_1s(printed):
    c, events = Clock(W + 100), []
    r = fast_entry.MarkReader(Kalshi(c), lambda: SERIES, clock=c, ntp=lambda: None,
                              sleep=lambda s: (events.append(("sleep", s)), c.sleep(s)))

    def run_window(w):
        events.append(("window", w))
        n = sum(e[0] == "window" for e in events)
        if n == 1:
            raise RuntimeError("boom")
        r.stop.set()
        if n > 40:
            raise Runaway("run() never stopped")

    r.run_window = run_window
    r.run()
    turns = [i for i, e in enumerate(events) if e[0] == "window"]
    assert len(turns) >= 2
    assert ("sleep", 1) in events[turns[0] + 1:turns[1]]
    assert logged(printed, "boom")


def test_an_error_from_series_fn_in_run_loses_only_that_window(printed):
    c, calls = Clock(W + 100), []

    def series_fn():
        calls.append(c())
        if len(calls) == 1:
            raise RuntimeError("no universe yet")
        return SERIES

    k = Kalshi(c, on_book=lambda t: r.stop.set())
    r = make(k, c, series=series_fn)
    r.run()
    assert logged(printed, "no universe yet")
    assert r.books(W) == {}
    assert set(r.books(W + 900)) == tickers(W + 900)


def test_an_error_from_ntp_in_run_is_logged_and_the_window_is_still_read(printed):
    c, calls = Clock(W + 100), []

    def ntp():
        calls.append(c())
        if len(calls) == 1:
            raise OSError("ntp down")
        return 0.155

    k = Kalshi(c, on_book=lambda t: r.stop.set())
    r = make(k, c, ntp=ntp)
    r.run()
    assert logged(printed, "ntp down")
    assert set(r.books(W)) == tickers(W)


def test_with_stop_set_run_returns_at_once_having_done_nothing():
    c, asked = Clock(W + 100), []
    k = Kalshi(c)
    r = make(k, c, ntp=lambda: asked.append(1))
    r.stop.set()
    r.run()
    assert (asked, k.listed, k.read, c.sleeps) == ([], [], [], [])


def test_started_as_a_thread_it_reads_the_books_and_ends_when_stop_is_set():
    c = Clock(W + 100)
    k = Kalshi(c, on_book=lambda t: r.stop.set())
    r = make(k, c)
    r.start()
    r.join(2)
    assert not r.is_alive()
    assert set(r.books(W)) == tickers(W)
