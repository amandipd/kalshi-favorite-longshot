"""fast_entry.py: the helpers for the fast-entry experiment (research/kalshi_15min/lab/fast_entry/timing.md).

Each window flips its own coin, "fast" or "normal", from sha256 of its open time (arm), so the bot and the analysis
agree without storing anything. In a fast window the loop wakes at the prep and mark events on Kalshi's clock
(next_wake), Kalshi's clock offset is the median of what each order answer's ts_ms says (ClockSync), and the orders go
out together: a burst at once, the rest spaced to stay within Kalshi's write rate limit (send_all). report() reads the
bot's ledger and compares the arms. Its primary outcome is the base share: the contracts bought at or under the ask the
bot saw (the decision's fav_price) over the contracts asked for. An order whose limit is at or under that ask bought
only base contracts; one whose limit is over it (the +1c limit) splits by its rows in the fills table, and with no
such rows, or no ask seen, its base is unknown. Then the fill share, what the bets paid over the ask seen per
contract, landing times (landing), P&L per $10, each standard error clustered by window (ratio_se), and a verdict
that follows the base share. The module never imports bot and never writes to a database. Ledgers here are built with
bot.connect in a temporary folder (one with plain sqlite3 and no fills table, as before the +1c restart); every number
is worked out by hand. The fake Kalshi clients never touch the network, and the sleeps add up to well under half a
second.

    python -m pytest tests/test_fast_entry.py -q
"""
import ast
import hashlib
import json
import math
import sqlite3
import threading
import time

import pytest
import requests

from kalshi_bot import bot
from kalshi_bot import fast_entry

S = 1791777600              # the experiment's start in the report tests: a window's open time (Oct 2026)
PAST = 1_600_000_000        # a start long ago, for arm() and next_wake(): every window here gets its coin
SHIPPED = {"START": fast_entry.START, "EVERY": fast_entry.EVERY}   # as the module ships, before any test changes them


@pytest.fixture(autouse=True)
def the_coin(monkeypatch):
    """The coin, so the tests of it and of the arms still test them: fast_entry ships with EVERY on (every window from
    START fast, no coin), and the tests of that set it themselves."""
    monkeypatch.setattr(fast_entry, "EVERY", False)


def coin(window_open, salt="fast-entry-1"):
    """The rule, worked out here with hashlib: fast when the first byte of sha256("<salt>:<window>") is odd."""
    return "fast" if hashlib.sha256(f"{salt}:{int(window_open)}".encode()).digest()[0] & 1 else "normal"


# ------------------------------------------------------------------ the module
def test_the_constants():
    assert fast_entry.SALT == "fast-entry-1"
    assert SHIPPED["START"] == 1791936000              # 2026-10-14 00:00:00 UTC: on from the first window after the restart
    assert SHIPPED["EVERY"] is True                    # every window from START fast: no coin (Oct 14)
    assert (fast_entry.PREP, fast_entry.MARK, fast_entry.MIN_WINDOWS) == (450, 480, 60)


def test_it_never_imports_bot():
    """bot.py will import fast_entry, so fast_entry can't import bot (or dashboard, which imports bot)."""
    src = open(fast_entry.__file__, encoding="utf-8").read()
    assert "import bot" not in src
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"bot", "dashboard"}


# ------------------------------------------------------------------ arm: each window's coin
def test_with_no_start_every_window_is_normal():
    for w in (S, S + 900, S + 1800, S + 2700, S + 4500):
        assert fast_entry.arm(w) == "normal"                     # START is None
        assert fast_entry.arm(w, None) == "normal"
        assert fast_entry.arm(w, start=None) == "normal"


def test_a_window_before_the_start_is_normal_whatever_its_coin_says():
    assert coin(S - 1800) == coin(S - 900) == "fast"
    assert fast_entry.arm(S - 900, start=S) == "normal"
    assert fast_entry.arm(S - 1800, start=S) == "normal"
    assert fast_entry.arm(S - 900, start=S - 899) == "normal"   # int(window_open) < start


def test_the_window_that_opens_at_the_start_gets_its_coin():
    assert coin(S) == "fast"
    assert fast_entry.arm(S, start=S) == "fast"
    assert fast_entry.arm(S - 900, start=S - 900) == coin(S - 900) == "fast"


def test_the_coin_is_the_first_byte_of_sha256_of_salt_and_window():
    windows = [S + 900 * i for i in range(40)]
    got = [fast_entry.arm(w, PAST) for w in windows]
    assert got == [coin(w) for w in windows]
    assert set(got) == {"fast", "normal"}
    # spelled out for a few, so nothing hides behind the helper above
    for w in (1791777600, 1791778500, 1791779400, 1791780300):
        odd = hashlib.sha256(f"fast-entry-1:{w}".encode()).digest()[0] & 1
        assert fast_entry.arm(w, PAST) == ("fast" if odd else "normal")
    assert [fast_entry.arm(w, PAST) for w in (1791777600, 1791778500, 1791779400, 1791780300)] == \
        ["fast", "normal", "fast", "normal"]


def test_the_default_salt_is_salt():
    for w in (S + 900 * i for i in range(20)):
        assert fast_entry.arm(w, PAST) == fast_entry.arm(w, PAST, "fast-entry-1") == \
            fast_entry.arm(w, PAST, salt=fast_entry.SALT)


def test_the_coin_is_the_same_every_time_it_is_asked():
    for w in (S + 900 * i for i in range(20)):
        assert len({fast_entry.arm(w, PAST) for _ in range(5)}) == 1


def test_a_float_open_time_gets_the_same_coin_as_its_whole_number():
    assert fast_entry.arm(1791778500.0, PAST) == fast_entry.arm(1791778500, PAST) == coin(1791778500)
    for w in (S + 900 * i for i in range(20)):
        assert fast_entry.arm(float(w), PAST) == fast_entry.arm(w, PAST)
    assert fast_entry.arm(float(S), start=S) == "fast"          # not hashed as "fast-entry-1:1791777600.0"


def test_about_half_the_windows_are_fast_in_every_quarter_hour_slot():
    """Not alternating: :00/:30 and :15/:45 behave differently (the 9:30 ET window, news at the top of the hour)."""
    windows = [S + 900 * i for i in range(4000)]
    fast = [fast_entry.arm(w, S) == "fast" for w in windows]
    assert 0.45 <= sum(fast) / len(fast) <= 0.55
    for slot in range(4):                                        # :00, :15, :30, :45
        mine = [f for w, f in zip(windows, fast) if w % 3600 == slot * 900]
        assert len(mine) == 1000
        assert 0.40 <= sum(mine) / len(mine) <= 0.60


def test_another_salt_flips_other_coins():
    windows = [S + 900 * i for i in range(40)]
    one = [fast_entry.arm(w, PAST) for w in windows]
    two = [fast_entry.arm(w, PAST, "fast-entry-2") for w in windows]
    assert one != two
    assert two == [coin(w, "fast-entry-2") for w in windows]


# ------------------------------------------------------------------ EVERY: every window fast, no coin (Oct 14)
def test_with_every_each_window_from_the_start_is_fast(monkeypatch):
    """Oct 14: every window fast, the A/B experiment dropped. Before the start, and with no start, every
    window is still normal."""
    monkeypatch.setattr(fast_entry, "EVERY", True)
    windows = [S + 900 * i for i in range(400)]                  # four days, every quarter-hour slot
    assert {coin(w) for w in windows} == {"fast", "normal"}      # (the coin would have split them)
    assert all(fast_entry.arm(w, S) == "fast" for w in windows)
    assert all(fast_entry.arm(float(w), S) == "fast" for w in windows[:20])
    assert fast_entry.arm(S - 900, S) == fast_entry.arm(S - 1, S) == "normal"
    assert all(fast_entry.arm(w, None) == "normal" for w in windows)   # START None: the off switch


def test_every_is_read_when_arm_is_called_or_given(monkeypatch):
    w = S
    while coin(w) != "normal":
        w += 900
    assert fast_entry.arm(w, S) == "normal"                       # the fixture's coin
    assert fast_entry.arm(w, S, every=True) == "fast"
    monkeypatch.setattr(fast_entry, "EVERY", True)
    assert fast_entry.arm(w, S) == "fast"
    assert fast_entry.arm(w, S, every=False) == "normal"
    assert fast_entry.arm(w, None, every=True) == "normal"


def test_as_shipped_every_window_from_oct_14_is_fast(monkeypatch):
    monkeypatch.setattr(fast_entry, "EVERY", SHIPPED["EVERY"])
    start = SHIPPED["START"]
    assert [fast_entry.arm(start + 900 * i, start) for i in range(-2, 4)] == ["normal"] * 2 + ["fast"] * 4


# ------------------------------------------------------------------ next_wake: when the loop's next step starts
def first(kind, salt="fast-entry-1", then=None):
    """The first window from S whose coin (by arm, with a start long past) is `kind`, and whose next window's is `then`."""
    w = S
    while not (fast_entry.arm(w, PAST, salt) == kind and (then is None or fast_entry.arm(w + 900, PAST, salt) == then)):
        w += 900
    return w


def at(x):
    return pytest.approx(x, abs=1e-6)


def test_in_a_normal_window_it_waits_the_usual_poll():
    w = first("normal")
    for t in (w + 0.0, w + 448, w + 449.9, w + 478.5, w + 479.9995, w + 480, w + 600):
        assert fast_entry.next_wake(t, PAST) == at(t + 3.0)


def test_in_a_fast_window_it_wakes_at_the_mark():
    w = first("fast")
    assert fast_entry.next_wake(w + 478.5, PAST) == at(w + 480)
    assert fast_entry.next_wake(w + 477.1, PAST) == at(w + 480)
    assert fast_entry.next_wake(w + 479.9995, PAST) == at(w + 480)


def test_at_the_mark_itself_it_doesnt_wake_at_the_mark_again():
    w = first("fast")
    assert fast_entry.next_wake(w + 480, PAST) == at(w + 483)
    assert fast_entry.next_wake(w + 480.0001, PAST) == at(w + 483.0001)


def test_in_a_fast_window_it_wakes_at_prep():
    w = first("fast")
    assert fast_entry.next_wake(w + 448, PAST) == at(w + 450)
    assert fast_entry.next_wake(w + 449.9, PAST) == at(w + 450)
    assert fast_entry.next_wake(w + 450, PAST) == at(w + 453)          # prep itself: not again


def test_away_from_the_events_a_fast_window_waits_the_usual_poll():
    w = first("fast", then="normal")
    for t in (w + 0.0, w + 100, w + 446.9, w + 451, w + 476, w + 476.9, w + 600, w + 896.5):
        assert fast_entry.next_wake(t, PAST) == at(t + 3.0)


def test_an_event_before_now_plus_poll_wins_and_one_at_or_after_it_doesnt():
    w = first("fast")
    assert fast_entry.next_wake(w + 476, PAST) == at(w + 479)           # 480 isn't before 476 + 3
    assert fast_entry.next_wake(w + 476, PAST, poll=5) == at(w + 480)
    assert fast_entry.next_wake(w + 450, PAST, poll=31) == at(w + 480)  # prep is past; the mark is in reach
    assert fast_entry.next_wake(w + 440, PAST, poll=60) == at(w + 450)  # both in reach: the earlier one


def test_the_poll_is_whatever_it_is_given():
    w = first("normal")
    assert fast_entry.next_wake(w + 10, PAST, poll=1.5) == at(w + 11.5)
    assert fast_entry.next_wake(w + 10, PAST, 1.5) == at(w + 11.5)


def test_the_next_windows_events_count_too():
    w = first("normal", then="fast")                  # nothing left in this window; the next one is fast
    assert fast_entry.next_wake(w + 850, PAST, poll=600) == at(w + 900 + 450)
    assert fast_entry.next_wake(w + 899.5, PAST, prep=1) == at(w + 900 + 1)
    w = first("fast", then="normal")
    assert fast_entry.next_wake(w + 899.5, PAST, prep=1) == at(w + 902.5)


def test_prep_and_mark_are_whatever_they_are_given():
    w = first("fast")
    assert fast_entry.next_wake(w + 498, PAST, mark=500) == at(w + 500)
    assert fast_entry.next_wake(w + 478.5, PAST, mark=500) == at(w + 481.5)   # 480 is no longer an event
    assert fast_entry.next_wake(w + 418, PAST, prep=420) == at(w + 420)
    assert fast_entry.next_wake(w + 448, PAST, prep=420) == at(w + 451)


def test_the_events_are_on_kalshis_clock():
    """This PC runs about 0.155 s behind Kalshi: Kalshi's 480.0 is the PC's 479.845, and that's when it wakes."""
    w = first("fast")
    assert fast_entry.next_wake(w + 478.5 - 0.155, PAST, offset=0.155) == at(w + 480 - 0.155)
    assert fast_entry.next_wake(w + 479.9, PAST, offset=0.155) == at(w + 482.9)   # already past 480 on Kalshi's clock
    assert fast_entry.next_wake(w + 448, PAST, offset=0.155) == at(w + 450 - 0.155)
    assert fast_entry.next_wake(w + 478.7, PAST, offset=-0.2) == at(w + 480.2)    # a PC ahead of Kalshi
    n = first("normal")
    assert fast_entry.next_wake(n + 478.5, PAST, offset=0.155) == at(n + 481.5)   # the poll is local time


def test_with_every_the_loop_wakes_at_the_prep_and_the_mark_of_every_window(monkeypatch):
    monkeypatch.setattr(fast_entry, "EVERY", True)
    for w in (S + 900 * i for i in range(96)):                  # a day of windows
        assert fast_entry.next_wake(w + 448, S) == at(w + 450)
        assert fast_entry.next_wake(w + 450, S) == at(w + 453)
        assert fast_entry.next_wake(w + 478.5, S) == at(w + 480)
        assert fast_entry.next_wake(w + 478.5 - 1.4, S, offset=1.4) == at(w + 480 - 1.4)   # a PC 1.4 s behind
        assert fast_entry.next_wake(w + 100, S) == at(w + 103)
    assert fast_entry.next_wake(S - 900 + 478.5, S) == at(S - 900 + 481.5)   # before the start: the usual poll
    assert fast_entry.next_wake(S + 478.5, None) == at(S + 481.5)             # no start


def test_with_no_start_it_always_waits_the_usual_poll():
    w = first("fast")
    for t in (w + 448, w + 478.5, w + 479.9995):
        assert fast_entry.next_wake(t) == at(t + 3.0)                 # START is None
        assert fast_entry.next_wake(t, None) == at(t + 3.0)
        assert fast_entry.next_wake(t, start=None, offset=0.155) == at(t + 3.0)


def test_a_window_before_the_start_waits_the_usual_poll():
    w = first("fast")
    assert fast_entry.next_wake(w + 478.5, start=w + 900) == at(w + 481.5)
    assert fast_entry.next_wake(w + 478.5, start=w) == at(w + 480)


def test_the_salt_picks_the_fast_windows():
    def where(mine, other):
        w = S
        while not (fast_entry.arm(w, PAST) == mine and fast_entry.arm(w, PAST, "other") == other):
            w += 900
        return w

    w = where("fast", "normal")
    assert fast_entry.next_wake(w + 478.5, PAST) == at(w + 480)
    assert fast_entry.next_wake(w + 478.5, PAST, salt="other") == at(w + 481.5)
    w = where("normal", "fast")
    assert fast_entry.next_wake(w + 478.5, PAST) == at(w + 481.5)
    assert fast_entry.next_wake(w + 478.5, PAST, salt="other") == at(w + 480)


# ------------------------------------------------------------------ ClockSync: Kalshi's clock offset
def test_with_no_samples_the_offset_is_zero():
    c = fast_entry.ClockSync()
    assert (len(c), c.offset()) == (0, 0.0)


def test_one_sample_is_kalshis_time_less_the_middle_of_the_round_trip():
    c = fast_entry.ClockSync()
    c.add(1000.0, 1000.2, 1000250)                    # Kalshi said 1000.25 when the PC was at 1000.1
    assert len(c) == 1
    assert c.offset() == pytest.approx(0.15)


def test_the_offset_is_the_median_of_the_samples():
    c = fast_entry.ClockSync()
    c.add(10.0, 10.2, 10250)                          # +0.15
    c.add(20.0, 20.2, 20400)                          # +0.30
    c.add(30.0, 30.2, 30000)                          # -0.10
    assert (len(c), c.offset()) == (3, pytest.approx(0.15))
    c.add(40.0, 40.2, 40300)                          # +0.20: an even count takes the mean of the middle two
    assert (len(c), c.offset()) == (4, pytest.approx((0.15 + 0.20) / 2))


def test_a_pc_ahead_of_kalshi_has_a_negative_offset():
    c = fast_entry.ClockSync()
    c.add(500.0, 500.1, 499850)                       # Kalshi 499.85, PC 500.05
    assert c.offset() == pytest.approx(-0.2)


def test_kalshis_time_may_come_as_a_whole_number_or_numeric_text():
    for server_ms in (1000250, "1000250", 1000250.0, "1000250.0"):
        c = fast_entry.ClockSync()
        c.add(1000.0, 1000.2, server_ms)
        assert (len(c), c.offset()) == (1, pytest.approx(0.15)), server_ms


@pytest.mark.parametrize("sent, received, server_ms", [
    (1000.0, 1000.2, None),                           # no ts_ms in the answer
    (1000.0, 1000.2, "abc"),                          # not a number
    (1000.0, 1000.2, ""),
    (1000.0, 1000.2, []),
    (1000.0, 1000.2, {"ts_ms": 1000250}),
    (1000.2, 1000.0, 1000250),                        # answered before it was sent: the clock jumped
    (1000.0, 1002.001, 1001150),                      # a round trip over 2 s says too little about when Kalshi stamped it
    (1000.0, 1010.0, 1005150),
])
def test_a_sample_it_cant_trust_is_skipped(sent, received, server_ms):
    c = fast_entry.ClockSync()
    c.add(sent, received, server_ms)
    assert (len(c), c.offset()) == (0, 0.0)
    c.add(1000.0, 1000.2, 1000250)                    # and it still takes good ones
    assert (len(c), c.offset()) == (1, pytest.approx(0.15))


def test_a_round_trip_of_exactly_2s_or_of_nothing_is_kept():
    c = fast_entry.ClockSync()
    c.add(100.0, 102.0, 101150)                       # 2.0 s: kept (only over 2 s is skipped)
    c.add(5.0, 5.0, 5150)                             # answered the instant it was sent
    assert len(c) == 2
    assert c.offset() == pytest.approx(0.15)


def test_it_keeps_only_the_last_keep_samples():
    c = fast_entry.ClockSync(keep=3)
    for i, ahead in enumerate((1.0, 2.0, 3.0, 10.0, 11.0)):
        c.add(float(i), float(i), i * 1000 + ahead * 1000)
    assert len(c) == 3
    assert c.offset() == pytest.approx(10.0)          # the median of 3, 10, 11


def test_by_default_it_keeps_50():
    c = fast_entry.ClockSync()
    for i in range(70):                               # 40 at +5 s, then 30 at +0.2 s
        ahead = 5.0 if i < 40 else 0.2
        c.add(float(i), float(i), i * 1000 + ahead * 1000)
    assert len(c) == 50
    assert c.offset() == pytest.approx(0.2)           # of the last 50 (20 at +5, 30 at +0.2); all 70 would say 5.0


# ------------------------------------------------------------------ send_all: every order at once
def bodies(n):
    return [{"ticker": f"KXBTC15M-26OCT111500-0{i}", "count": "10", "i": i} for i in range(n)]


class Kalshi:
    """A fake Kalshi that answers every order with a 201 (or what `answers` says, by ticker) and notes each call."""

    def __init__(self, answers=None, pause=0.0):
        self.answers, self.pause = answers or {}, pause
        self.calls, self.lock, self.active, self.most = [], threading.Lock(), 0, 0

    def create_order(self, body):
        with self.lock:
            self.calls.append(body)
            self.active += 1
            self.most = max(self.most, self.active)
        try:
            if self.pause:
                time.sleep(self.pause)
            got = self.answers.get(body["ticker"], (201, {"order_id": f"o-{body['i']}", "fill_count": "10.00"}))
            if isinstance(got, Exception):
                raise got
            return got
        finally:
            with self.lock:
                self.active -= 1


class Ticking:
    """A clock that only moves when Kalshi answers: one second per order (it raises for the tickers in `fail`)."""

    def __init__(self, fail=()):
        self.t, self.calls, self.fail = 1000.0, [], set(fail)

    def clock(self):
        return self.t

    def create_order(self, body):
        self.calls.append(body)
        self.t += 1.0
        if body["ticker"] in self.fail:
            raise requests.ConnectionError("connection reset")
        return 201, {"order_id": f"o-{body['i']}"}


def test_every_body_is_sent_once_and_answered_in_the_bodies_order():
    k, b = Kalshi(), bodies(5)
    got = fast_entry.send_all(k, b)
    assert sorted(c["i"] for c in k.calls) == [0, 1, 2, 3, 4]
    assert [r["body"] for r in got] == b
    for r, body in zip(got, b):
        assert set(r) == {"body", "status", "data", "sent", "answered"}
        assert (r["status"], r["data"]) == (201, {"order_id": f"o-{body['i']}", "fill_count": "10.00"})
        assert isinstance(r["sent"], float) and isinstance(r["answered"], float)
        assert r["sent"] <= r["answered"]


def test_sent_and_answered_come_from_the_clock_just_before_and_after_each_call():
    k = Ticking()
    got = fast_entry.send_all(k, bodies(3), workers=1, clock=k.clock)
    assert [(r["sent"], r["answered"]) for r in got] == [(1000.0, 1001.0), (1001.0, 1002.0), (1002.0, 1003.0)]
    assert [r["data"] for r in got] == [{"order_id": "o-0"}, {"order_id": "o-1"}, {"order_id": "o-2"}]


def test_a_network_error_is_status_none_and_never_retried():
    b = bodies(3)
    k = Kalshi(answers={b[1]["ticker"]: requests.ReadTimeout("no answer in 5s")})
    got = fast_entry.send_all(k, b)
    assert len(k.calls) == 3 and sorted(c["i"] for c in k.calls) == [0, 1, 2]
    assert got[1]["status"] is None
    assert isinstance(got[1]["data"], str) and got[1]["data"].startswith("network error: ")
    assert "no answer in 5s" in got[1]["data"]
    assert got[1]["body"] == b[1] and got[1]["sent"] <= got[1]["answered"]
    assert [got[0]["status"], got[2]["status"]] == [201, 201]


def test_a_network_errors_times_come_from_the_clock_too():
    b = bodies(3)
    k = Ticking(fail={b[1]["ticker"]})
    got = fast_entry.send_all(k, b, workers=1, clock=k.clock)
    assert (got[1]["status"], got[1]["sent"], got[1]["answered"]) == (None, 1001.0, 1002.0)
    assert got[1]["data"].startswith("network error: ") and "connection reset" in got[1]["data"]
    assert len(k.calls) == 3


def test_kalshis_refusals_come_back_as_they_are_and_are_never_retried():
    b = bodies(3)
    k = Kalshi(answers={b[0]["ticker"]: (400, {"error": {"code": "insufficient_balance"}}),
                        b[2]["ticker"]: (500, "internal error")})
    got = fast_entry.send_all(k, b)
    assert len(k.calls) == 3
    assert [(r["status"], r["data"]) for r in got] == [(400, {"error": {"code": "insufficient_balance"}}),
                                                         (201, {"order_id": "o-1", "fill_count": "10.00"}),
                                                         (500, "internal error")]


def test_any_other_error_is_raised():
    b = bodies(3)
    k = Kalshi(answers={b[1]["ticker"]: ValueError("a bug, not the network")})
    with pytest.raises(ValueError, match="a bug"):
        fast_entry.send_all(k, b)


def test_no_bodies_sends_nothing():
    k = Kalshi()
    assert fast_entry.send_all(k, []) == []
    assert k.calls == []


class Together:
    """A fake Kalshi whose every answer waits until `n` orders are in flight at once (2 s, then it gives up)."""

    def __init__(self, n):
        self.barrier, self.calls = threading.Barrier(n, timeout=2), []

    def create_order(self, body):
        self.calls.append(body)
        self.barrier.wait()
        return 201, {"order_id": f"o-{body['i']}"}


def test_the_orders_are_in_flight_at_the_same_time():
    k = Together(3)
    got = fast_entry.send_all(k, bodies(3), workers=3)
    assert [r["status"] for r in got] == [201, 201, 201]
    k = Together(3)
    assert len(fast_entry.send_all(k, bodies(3))) == 3                # the default, 8 workers


def test_by_default_eight_go_at_once():
    k = Together(8)
    got = fast_entry.send_all(k, bodies(8))
    assert [r["data"]["order_id"] for r in got] == [f"o-{i}" for i in range(8)]


class LastFirst:
    """A fake Kalshi that answers the orders last to first: each waits for the one after it (2 s, then it gives up)."""

    def __init__(self, n):
        self.done = [threading.Event() for _ in range(n)]

    def create_order(self, body):
        i = body["i"]
        if i + 1 < len(self.done) and not self.done[i + 1].wait(2):
            raise RuntimeError("the orders weren't sent together")
        self.done[i].set()
        return 201, {"order_id": f"o-{i}"}


def test_answers_that_come_back_out_of_order_are_returned_in_the_bodies_order():
    b = bodies(4)
    got = fast_entry.send_all(LastFirst(4), b, workers=4)
    assert [r["body"] for r in got] == b
    assert [r["data"]["order_id"] for r in got] == ["o-0", "o-1", "o-2", "o-3"]
    assert got[0]["answered"] >= got[3]["answered"]


@pytest.mark.parametrize("workers", [1, 0, -3])
def test_with_one_worker_or_fewer_the_orders_go_one_at_a_time(workers):
    k = Kalshi(pause=0.005)
    got = fast_entry.send_all(k, bodies(3), workers=workers)
    assert k.most == 1
    assert len(k.calls) == 3 and [r["status"] for r in got] == [201, 201, 201]


def test_spacing_holds_each_send_back_from_the_first():
    """Send i starts no sooner than max(0, i - burst + 1) * spacing after the first; with the default burst of 1 that
    is i * spacing. Timed with perf_counter: on this PC's Python 3.12, time.time() and time.monotonic() only tick every
    15.6 ms, too coarse to measure 30 ms (or to wait it out)."""
    got = fast_entry.send_all(Kalshi(), bodies(4), spacing=0.03, clock=time.perf_counter)
    sent = [r["sent"] for r in got]
    for i in range(1, 4):
        assert sent[i] - sent[0] >= i * 0.03 - 0.005, sent


def test_a_burst_goes_together_and_the_rest_are_spaced_after_it():
    """Kalshi's write bucket holds 10 orders and refills 10 a second, so the first `burst` orders can go at once."""
    got = fast_entry.send_all(Kalshi(), bodies(5), spacing=0.03, burst=3, clock=time.perf_counter)
    sent = [r["sent"] for r in got]
    assert max(sent[:3]) - min(sent[:3]) <= 0.025, sent           # sends 0-2: together
    assert sent[3] - sent[0] >= 1 * 0.03 - 0.005, sent             # max(0, 3 - 3 + 1) = 1 spacing
    assert sent[4] - sent[0] >= 2 * 0.03 - 0.005, sent             # max(0, 4 - 3 + 1) = 2
    assert [r["status"] for r in got] == [201] * 5


def test_a_burst_bigger_than_the_orders_sends_them_all_together():
    got = fast_entry.send_all(Kalshi(), bodies(4), spacing=0.03, burst=10, clock=time.perf_counter)
    sent = [r["sent"] for r in got]
    assert max(sent) - min(sent) <= 0.025, sent


@pytest.mark.parametrize("burst", [0, -2])
def test_a_burst_under_one_is_one(burst):
    """As with burst=1: the first goes at once and the second one spacing later (not held back further)."""
    k = Kalshi()
    called = time.perf_counter()
    got = fast_entry.send_all(k, bodies(2), 8, 0.05, burst, time.perf_counter)   # workers, spacing, burst, clock
    sent = [r["sent"] for r in got]
    assert sent[0] - called <= 0.035, (called, sent)
    assert 0.05 - 0.005 <= sent[1] - sent[0] <= 0.05 + 0.035, sent
    assert len(k.calls) == 2


# ------------------------------------------------------------------ landing: seconds after the mark, by Kalshi's ts_ms
W = 1791778500


def test_landing_is_ts_ms_less_the_mark_in_seconds():
    assert fast_entry.landing({"ts_ms": W * 1000 + 482_400}, W) == 2.4
    assert fast_entry.landing({"ts_ms": W * 1000 + 480_123}, W) == 0.123
    assert fast_entry.landing({"ts_ms": W * 1000 + 479_500}, W) == -0.5      # early
    assert fast_entry.landing({"ts_ms": W * 1000 + 480_000}, float(W)) == 0.0


def test_landing_is_rounded_to_the_millisecond():
    assert fast_entry.landing({"ts_ms": W * 1000 + 482_400.4}, W) == 2.4
    assert fast_entry.landing({"ts_ms": W * 1000 + 482_400}, W + 0.0004) == 2.4
    assert fast_entry.landing({"ts_ms": W * 1000 + 482_400}, W + 0.0006) == 2.399


def test_landing_reads_the_answer_as_the_ledger_stores_it():
    assert fast_entry.landing(json.dumps({"order_id": "o-1", "fill_count": "3.00", "ts_ms": W * 1000 + 482_400}), W) == 2.4
    assert fast_entry.landing({"ts_ms": str(W * 1000 + 482_400)}, W) == 2.4         # ts_ms as numeric text
    assert fast_entry.landing(json.dumps({"ts_ms": str(W * 1000 + 482_400)}), W) == 2.4


def test_landing_against_another_mark():
    assert fast_entry.landing({"ts_ms": W * 1000 + 482_400}, W, mark=450) == 32.4
    assert fast_entry.landing({"ts_ms": W * 1000 + 482_400}, W, 450) == 32.4


@pytest.mark.parametrize("response", [
    None,
    {},
    {"order_id": "o-1", "fill_count": "3.00"},        # no ts_ms
    {"ts_ms": None},
    {"ts_ms": "soon"},
    {"ts_ms": ""},
    "{}",
    '{"ts_ms": null}',
    '"network error: timed out"',                     # what the ledger holds when no answer came back
    "network error: timed out",                       # not JSON at all
    "<html>bad gateway</html>",
    "null",
    "[1, 2]",
])
def test_no_usable_ts_ms_is_none(response):
    assert fast_entry.landing(response, W) is None


# ------------------------------------------------------------------ ratio_se: a ratio and its standard error clustered
def test_ratio_se_by_hand():
    # R = 9/25 = 0.36; residuals 3 − 3.6 = −0.6, 5 − 3.6 = 1.4, 1 − 1.8 = −0.8; squares sum to 2.96
    r, se = fast_entry.ratio_se([(3, 10), (5, 10), (1, 5)])
    assert r == pytest.approx(0.36)
    assert se == pytest.approx(math.sqrt(3 / 2 * 2.96) / 25)          # 0.0842852...
    assert se == pytest.approx(0.0842852, abs=1e-7)


def test_ratio_se_with_two_clusters():
    assert fast_entry.ratio_se([(2, 4), (4, 4)]) == pytest.approx((0.75, 0.25))    # residuals ∓1: √(2·2)/8
    assert fast_entry.ratio_se([(-2, 4), (1, 4)]) == pytest.approx((-0.125, 0.375))  # a loss: residuals ∓1.5: √(2·4.5)/8


def test_clusters_in_proportion_have_no_spread():
    assert fast_entry.ratio_se([(1, 2), (2, 4), (3, 6)]) == pytest.approx((0.5, 0.0))


def test_one_cluster_has_a_ratio_but_no_standard_error():
    r, se = fast_entry.ratio_se([(3, 4)])
    assert r == pytest.approx(0.75) and se is None


@pytest.mark.parametrize("pairs", [[], [(0, 0)], [(0, 0), (0, 0)], [(1, 0)], [(2, 0), (-1, 0)]])
def test_nothing_to_divide_by_is_none_and_none(pairs):
    assert fast_entry.ratio_se(pairs) == (None, None)


# ------------------------------------------------------------------ report: the experiment from the bot's ledger
def ledger(tmp_path, name="live.db"):
    return bot.connect(str(tmp_path / name))


def buy(db, ts, ticker, count, status=201, response=None, side="bid", price="0.9600"):
    """One buy order as bot.place() records it. A dict response is stored as JSON, as the bot stores Kalshi's answer;
    a str is stored as it is (the bot writes json.dumps("network error: …") when no answer came back); None is NULL.
    The price is on the YES side, as bot.order_body sends it: a bid buys YES with its limit at the price, an ask buys
    NO with its limit at 1 - the price."""
    body = {"ticker": ticker, "client_order_id": bot.client_order_id(ticker), "side": side, "count": count,
            "price": price, "time_in_force": "immediate_or_cancel"}
    stored = json.dumps(response) if isinstance(response, dict) else response
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, body["client_order_id"], json.dumps(body), status, stored))


def cancel(db, ts, ticker, order_id, status=200):
    """A cancel the bot sent: the orders table holds these too, as {"cancel": order id}."""
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, bot.client_order_id(ticker), json.dumps({"cancel": order_id}), status,
                json.dumps({"order": {"order_id": order_id, "status": "canceled"}})))


def bet(db, ticker, window, status, cost, pnl=None, contracts=None):
    """The bet an order's contracts made: `contracts` of them (by default cost / 95c, rounded) for `cost` in all."""
    contracts = round(cost / 0.95) if contracts is None else contracts
    db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts,"
               " status, pnl, settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (ticker, ticker.split("-")[0], window, window + 900, "yes", 0.95, contracts, cost, 0.01,
                window + 481, status, None if status == "open" else pnl, None if status == "open" else window + 908))


def saw(db, ticker, price, side="yes", action="bet"):
    """The decision the bot logged for a market: the ask it saw on the favourite's side (fav_price; None is NULL)."""
    db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
               (S, ticker, ticker.split("-")[0], side, price, action, "test"))


def fill(db, order_id, ticker, count, price, side="yes"):
    """One fill as bot.fills_for() keeps it: Kalshi's order ID (None is NULL), and its price on the side it bought."""
    n = db.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
    db.execute("INSERT INTO fills (trade_id, order_id, ticker, side, price, count, fee, ts) VALUES (?,?,?,?,?,?,?,?)",
               (f"t-{n}", order_id, ticker, side, price, count, 0.0, S))


# The hand-built ledger's windows. B is before S (its coin says fast, but it opened before the start); F1 opens at S.
B, F1, N1, F2, N2, F3, F4 = S - 900, S, S + 900, S + 1800, S + 2700, S + 4500, S + 8100


def ms(window, after):
    """Kalshi's ts_ms for an order it stamped `after` seconds into `window`."""
    return window * 1000 + round(after * 1000)


@pytest.fixture
def hand(tmp_path):
    assert [coin(w) for w in (B, F1, N1, F2, N2, F3, F4)] == ["fast", "fast", "normal", "fast", "normal", "fast", "fast"]
    db = ledger(tmp_path)
    # Every buy is YES with its limit at 96c unless it says otherwise. The ask it saw is the decision's price.
    # before: one order, 4 of 10 filled, landed 2.5 s after the mark; its bet won. Limit 96c over the 94c it saw:
    # 2 contracts at 94c are base, 2 at 96c aren't. Paid 3.80 for 4, 4c over 4 at 94c.
    saw(db, "KXBTC15M-B", 0.94)
    buy(db, B + 482.1, "KXBTC15M-B", "10", 201, {"order_id": "o-b", "fill_count": "4.00", "ts_ms": ms(B, 482.5)})
    fill(db, "o-b", "KXBTC15M-B", 2, 0.94)
    fill(db, "o-b", "KXBTC15M-B", 2, 0.96)
    bet(db, "KXBTC15M-B", B, "won", 3.80, 0.18)
    # F1 (fast): two filled, one refused, and the cancel of an order; a bet with no order of its own
    saw(db, "KXBTC15M-F1", 0.95)                                      # 10 at 95c: all base, paid exactly 10 at 95c
    buy(db, F1 + 480.3, "KXBTC15M-F1", "10", 201, {"order_id": "o-f1", "fill_count": "10.00", "ts_ms": ms(F1, 480.2)})
    fill(db, "o-f1", "KXBTC15M-F1", 10, 0.95)
    saw(db, "KXETH15M-F1", 0.94)                                      # 5 at 95c: none base, 5c over 5 at 94c
    buy(db, F1 + 480.3, "KXETH15M-F1", "20", 201, {"order_id": "o-f1e", "fill_count": "5.00", "ts_ms": ms(F1, 480.4)})
    fill(db, "o-f1e", "KXETH15M-F1", 5, 0.95)
    fill(db, "o-other", "KXETH15M-F1", 3, 0.90)                       # another order's fill in that market: not its own
    saw(db, "KXSOL15M-F1", 0.93, action="error")
    buy(db, F1 + 480.3, "KXSOL15M-F1", "8", 400, {"error": {"code": "insufficient_balance"}})
    cancel(db, F1 + 481.0, "KXETH15M-F1", "o-f1e")
    bet(db, "KXBTC15M-F1", F1, "won", 9.50, 0.40)
    bet(db, "KXETH15M-F1", F1, "lost", 4.75, -4.80)
    saw(db, "KXBNB15M-F1", 0.90)
    bet(db, "KXBNB15M-F1", F1, "won", 9.00, 0.45)                     # reconciled, no order row: not counted
    # F2 (fast): nothing filled (and no ask seen: its base is still 0), no answer at all (its bet came from its fills),
    # and one with no ts_ms whose bet is open: over the 94c it saw with no fills rows, so its base is unknown, but it
    # paid 5.70 for 6, 6c over 6 at 94c
    buy(db, F2 + 480.5, "KXXRP15M-F2", "6", 201, {"order_id": "o-f2x", "fill_count": "0.00", "ts_ms": ms(F2, 480.6)})
    saw(db, "KXDOGE15M-F2", 0.95, action="error")
    buy(db, F2 + 480.5, "KXDOGE15M-F2", "4", None, '"network error: timed out"')
    saw(db, "KXBTC15M-F2", 0.94)
    buy(db, F2 + 480.5, "KXBTC15M-F2", "10", 201, {"order_id": "o-f2b", "fill_count": "6.00"})
    fill(db, None, "KXBTC15M-F2", 2, 0.90)                            # a fill kept with no order ID: no order's
    bet(db, "KXDOGE15M-F2", F2, "lost", 2.90, -3.00)                  # its order wasn't accepted: not counted
    bet(db, "KXBTC15M-F2", F2, "open", 5.70)
    # F3 (fast): one, filled, won. A NO buy, an ask at 4c: its limit is 96c on NO, the ask it saw, so all 5 are base
    # with no fills rows; it paid 4.70 for 5, 10c under 5 at 96c
    saw(db, "KXSOL15M-F3", 0.96, side="no")
    buy(db, F3 + 481.2, "KXSOL15M-F3", "5", 201, {"order_id": "o-f3", "fill_count": "5.00", "ts_ms": ms(F3, 481.0)},
        side="ask", price="0.0400")
    bet(db, "KXSOL15M-F3", F3, "won", 4.70, 0.20)
    # F4 (fast): only a refused order, so not a window with orders
    buy(db, F4 + 480.5, "KXETH15M-F4", "10", 429, {"error": {"code": "too_many_requests"}})
    # N1 (normal): a 200, an answer without fill_count (nothing filled: base 0), and a 201 whose answer isn't JSON
    saw(db, "KXBTC15M-N1", 0.94)                                      # 4 of its 8 at 94c; paid 7.60, 8c over 8 at 94c
    buy(db, N1 + 482.4, "KXBTC15M-N1", "10", 200, {"order_id": "o-n1", "fill_count": "8.00", "ts_ms": ms(N1, 482.0)})
    fill(db, "o-n1", "KXBTC15M-N1", 4, 0.94)
    fill(db, "o-n1", "KXBTC15M-N1", 4, 0.96)
    saw(db, "KXETH15M-N1", 0.95, action="skip")
    buy(db, N1 + 482.4, "KXETH15M-N1", "10", 201, {"order_id": "o-n1e", "ts_ms": ms(N1, 483.0)})
    buy(db, N1 + 482.4, "KXXRP15M-N1", "5", 201, "<html>bad gateway</html>")
    bet(db, "KXBTC15M-N1", N1, "won", 7.60, 0.30)
    # N2 (normal): a lost bet, a count given as a number and ts_ms as text, and a 500. The lost one is a NO buy at its
    # 95c limit, the ask it saw: all 10 base, paid exactly 10 at 95c. The one with a number for its count has no
    # decision row, so no ask seen: its base is unknown and its bet isn't in the paid-over figure.
    saw(db, "KXSOL15M-N2", 0.95, side="no")
    buy(db, N2 + 482.6, "KXSOL15M-N2", "10", 201, {"order_id": "o-n2", "fill_count": "10.00", "ts_ms": ms(N2, 482.5)},
        side="ask", price="0.0500")
    buy(db, N2 + 482.6, "KXDOGE15M-N2", 4, 201, {"order_id": "o-n2d", "fill_count": "2.00", "ts_ms": str(ms(N2, 484.0))})
    buy(db, N2 + 482.6, "KXHYPE15M-N2", "3", 500, {"error": "internal"})
    bet(db, "KXSOL15M-N2", N2, "lost", 9.50, -9.60)
    bet(db, "KXDOGE15M-N2", N2, "won", 1.88, 0.10)
    db.commit()
    return db


# Its groups, by hand. Landing times: before 2.5; fast 0.2, 0.4, 0.6, 1.0 (F2's BTC order has no ts_ms); normal
# 2.0, 3.0, 2.5, 4.0. p10/p90 interpolate in the sorted list at q·(n − 1).
# The base share counts only orders whose base is known, by window (base, asked):
#   fast   F1 (10 + 0, 10 + 20), F2 (0, 6) (its BTC order is unknown), F3 (5, 5)
#   normal N1 (4 + 0, 10 + 10), N2 (10, 10) (its DOGE order is unknown)
# Paid over the ask it saw counts the bets of accepted orders with an ask seen, settled or open, by window
# (Σ(cost − contracts × seen), Σcontracts):
#   fast   F1 (0.00 + 0.05, 10 + 5), F2 (0.06, 6) (the open bet), F3 (−0.10, 5)
#   normal N1 (0.08, 8), N2 (0.00, 10)
FAST_OVER, NORMAL_OVER = 0.01 / 26, 0.08 / 18
BEFORE = {"orders": 1, "errors": 0, "windows": 1, "asked": 10, "filled": 4, "fillShare": 4 / 10, "fillShareSe": None,
          "anyShare": 1 / 1, "none": 0, "landing": {"median": 2.5, "p10": 2.5, "p90": 2.5},
          "settled": 1, "won": 1, "pnl": 0.18, "cost": 3.80, "perTen": 1000 * 0.18 / 3.80, "perTenSe": None,
          "baseShare": 2 / 10, "baseShareSe": None, "unknown": 0,     # one window: no standard errors
          "overPaid": (3.80 - 4 * 0.94) / 4, "overPaidSe": None}
FAST = {"orders": 5, "errors": 3, "windows": 3,                    # errors: the 400, the unanswered one, the 429
        "asked": 10 + 20 + 6 + 10 + 5, "filled": 10 + 5 + 0 + 6 + 5, "fillShare": 26 / 51,
        # by window (filled, asked): F1 (15, 30), F2 (6, 16), F3 (5, 5); R = 26/51; residuals −15/51, −110/51, +125/51
        "fillShareSe": math.sqrt(3 / 2 * (15 ** 2 + 110 ** 2 + 125 ** 2)) / 51 / 51,
        "anyShare": 4 / 5, "none": 1,
        "landing": {"median": (0.4 + 0.6) / 2, "p10": 0.2 + 0.3 * (0.4 - 0.2), "p90": 0.6 + 0.7 * (1.0 - 0.6)},
        "settled": 3, "won": 2, "pnl": 0.40 - 4.80 + 0.20, "cost": 9.50 + 4.75 + 4.70,
        "perTen": 1000 * (0.40 - 4.80 + 0.20) / (9.50 + 4.75 + 4.70),
        # settled windows (P&L, cost): F1 (−4.40, 14.25), F3 (0.20, 4.70); F2's bet is open. With two clusters the
        # residuals are ±(n₂d₁ − n₁d₂)/D, so se = 2·|n₂d₁ − n₁d₂| / D²
        "perTenSe": 1000 * 2 * abs(0.20 * 14.25 - (-4.40) * 4.70) / (14.25 + 4.70) ** 2,
        # R = 15/41; residuals 10 − 30R = −40/41, 0 − 6R = −90/41, 5 − 5R = +130/41
        "baseShare": 15 / 41, "baseShareSe": math.sqrt(3 / 2 * (40 ** 2 + 90 ** 2 + 130 ** 2)) / 41 / 41,
        "unknown": 1,
        "overPaid": FAST_OVER,
        "overPaidSe": math.sqrt(3 / 2 * ((0.05 - 15 * FAST_OVER) ** 2 + (0.06 - 6 * FAST_OVER) ** 2
                                         + (-0.10 - 5 * FAST_OVER) ** 2)) / 26}
NORMAL = {"orders": 4, "errors": 2, "windows": 2,                  # errors: the 201 that isn't JSON, the 500
          "asked": 10 + 10 + 10 + 4, "filled": 8 + 0 + 10 + 2, "fillShare": 20 / 34,
          "fillShareSe": 2 * abs(12 * 20 - 8 * 14) / 34 ** 2,      # N1 (8, 20), N2 (12, 14)
          "anyShare": 3 / 4, "none": 1,
          "landing": {"median": (2.5 + 3.0) / 2, "p10": 2.0 + 0.3 * (2.5 - 2.0), "p90": 3.0 + 0.7 * (4.0 - 3.0)},
          "settled": 3, "won": 2, "pnl": 0.30 - 9.60 + 0.10, "cost": 7.60 + 9.50 + 1.88,
          "perTen": 1000 * (0.30 - 9.60 + 0.10) / (7.60 + 9.50 + 1.88),
          "perTenSe": 1000 * 2 * abs((-9.60 + 0.10) * 7.60 - 0.30 * (9.50 + 1.88)) / (7.60 + 9.50 + 1.88) ** 2,
          "baseShare": 14 / 30, "baseShareSe": 2 * abs(10 * 20 - 4 * 10) / 30 ** 2,   # N1 (4, 20), N2 (10, 10)
          "unknown": 1,
          "overPaid": NORMAL_OVER, "overPaidSe": 2 * abs(0.00 * 8 - 0.08 * 10) / 18 ** 2}   # N1 (0.08, 8), N2 (0, 10)
FILL_DIFF, FILL_SE = 26 / 51 - 20 / 34, math.sqrt(FAST["fillShareSe"] ** 2 + NORMAL["fillShareSe"] ** 2)
TEN_DIFF, TEN_SE = FAST["perTen"] - NORMAL["perTen"], math.sqrt(FAST["perTenSe"] ** 2 + NORMAL["perTenSe"] ** 2)
BASE_DIFF, BASE_SE = 15 / 41 - 14 / 30, math.sqrt(FAST["baseShareSe"] ** 2 + NORMAL["baseShareSe"] ** 2)
OVER_DIFF, OVER_SE = FAST_OVER - NORMAL_OVER, math.sqrt(FAST["overPaidSe"] ** 2 + NORMAL["overPaidSe"] ** 2)
DIFF = {"fillShare": FILL_DIFF, "fillShareSe": FILL_SE, "fillShareZ": FILL_DIFF / FILL_SE,
        "perTen": TEN_DIFF, "perTenSe": TEN_SE, "perTenZ": TEN_DIFF / TEN_SE,
        "baseShare": BASE_DIFF, "baseShareSe": BASE_SE, "baseShareZ": BASE_DIFF / BASE_SE,
        "overPaid": OVER_DIFF, "overPaidSe": OVER_SE, "overPaidZ": OVER_DIFF / OVER_SE}
EMPTY = {"orders": 0, "errors": 0, "windows": 0, "asked": 0, "filled": 0, "fillShare": None, "fillShareSe": None,
         "anyShare": None, "none": 0, "landing": {"median": None, "p10": None, "p90": None},
         "settled": 0, "won": 0, "pnl": 0, "cost": 0, "perTen": None, "perTenSe": None,
         "baseShare": None, "baseShareSe": None, "unknown": 0, "overPaid": None, "overPaidSe": None}
GROUP_KEYS = set(EMPTY)
DIFF_KEYS = {"fillShare", "fillShareSe", "fillShareZ", "perTen", "perTenSe", "perTenZ",
             "baseShare", "baseShareSe", "baseShareZ", "overPaid", "overPaidSe", "overPaidZ"}
NO_DIFF = dict.fromkeys(DIFF)


def close(got, want, path="report"):
    """got has exactly want's keys, numbers within 1e-9, None still None, text equal."""
    if isinstance(want, dict):
        assert isinstance(got, dict), f"{path}: {got!r} isn't a dict"
        assert set(got) == set(want), f"{path}: keys {sorted(got)} aren't {sorted(want)}"
        for key in want:
            close(got[key], want[key], f"{path}.{key}")
    elif want is None:
        assert got is None, f"{path}: {got!r} should be None"
    elif isinstance(want, str):
        assert got == want, f"{path}: {got!r} != {want!r}"
    else:
        assert isinstance(got, (int, float)) and not isinstance(got, bool), f"{path}: {got!r} isn't a number"
        assert got == pytest.approx(want, rel=1e-9, abs=1e-9), f"{path}: {got!r} != {want!r}"


def test_the_summary_says_what_it_was_run_with(hand):
    r = fast_entry.report(hand, start=S)
    assert set(r) == {"start", "salt", "mark", "minWindows", "groups", "diff", "verdict", "primary"}
    assert (r["start"], r["salt"], r["mark"], r["minWindows"]) == (S, "fast-entry-1", 480, 60)
    assert set(r["groups"]) == {"before", "fast", "normal"}
    assert all(set(g) == GROUP_KEYS for g in r["groups"].values())
    assert set(r["diff"]) == DIFF_KEYS


@pytest.mark.parametrize("start", [None, S, S + 10 ** 6])
def test_the_primary_outcome_is_the_base_share(hand, start):
    assert fast_entry.report(hand, start=start)["primary"] == "baseShare"


def test_the_orders_before_the_start(hand):
    close(fast_entry.report(hand, start=S)["groups"]["before"], BEFORE)


def test_the_fast_windows(hand):
    close(fast_entry.report(hand, start=S)["groups"]["fast"], FAST)


def test_the_normal_windows(hand):
    close(fast_entry.report(hand, start=S)["groups"]["normal"], NORMAL)


def test_fast_less_normal_with_standard_errors_and_z(hand):
    r = fast_entry.report(hand, start=S)
    close(r["diff"], DIFF)
    assert r["verdict"] == "too early"                 # 3 fast windows and 2 normal ones, of the 60 each needs


def test_fast_less_normal_in_base_share_and_paid_over(hand):
    d = fast_entry.report(hand, start=S)["diff"]
    assert d["baseShare"] == pytest.approx(15 / 41 - 14 / 30)                  # −0.1008: fast's base share is lower
    assert d["baseShareSe"] == pytest.approx(math.hypot(math.sqrt(1.5 * 26600) / 1681, 320 / 900))
    assert d["baseShareZ"] == pytest.approx(d["baseShare"] / d["baseShareSe"])
    assert d["overPaid"] == pytest.approx(0.01 / 26 - 0.08 / 18)               # dollars a contract
    assert d["overPaidSe"] == pytest.approx(math.hypot(FAST["overPaidSe"], 1.6 / 324))
    assert d["overPaidZ"] == pytest.approx(d["overPaid"] / d["overPaidSe"])


def test_with_no_start_every_order_is_before_and_it_hasnt_started(hand):
    for r in (fast_entry.report(hand, None), fast_entry.report(hand, start=None)):   # (START ships set since Oct 14)
        before = r["groups"]["before"]
        assert (before["orders"], before["errors"], before["windows"]) == (1 + 5 + 4, 0 + 3 + 2, 1 + 3 + 2)
        assert (before["asked"], before["filled"]) == (10 + 51 + 34, 4 + 26 + 20)
        assert (before["settled"], before["won"]) == (1 + 3 + 3, 1 + 2 + 2)
        assert before["pnl"] == pytest.approx(0.18 - 4.20 - 9.20)
        assert before["cost"] == pytest.approx(3.80 + 18.95 + 18.98)
        assert before["baseShare"] == pytest.approx((2 + 15 + 14) / (10 + 41 + 30)) and before["unknown"] == 2
        assert before["overPaid"] == pytest.approx((0.04 + 0.01 + 0.08) / (4 + 26 + 18))
        close(r["groups"]["fast"], EMPTY)
        close(r["groups"]["normal"], EMPTY)
        close(r["diff"], NO_DIFF)
        assert (r["start"], r["verdict"]) == (None, "not started")


def test_a_window_opening_before_the_start_is_before_even_if_its_orders_came_after(hand):
    r = fast_entry.report(hand, start=S + 1)           # F1 opened 1 s before the start; its orders came 480 s after
    g = r["groups"]
    assert (g["before"]["orders"], g["before"]["errors"], g["before"]["windows"]) == (1 + 2, 1, 2)
    assert (g["fast"]["orders"], g["fast"]["errors"], g["fast"]["windows"]) == (3, 2, 2)
    close(g["normal"], NORMAL)


def test_a_window_before_the_start_is_never_given_its_coin(hand):
    r = fast_entry.report(hand, start=B)               # now B is in the experiment, and its coin says fast
    g = r["groups"]
    close(g["before"], EMPTY)
    assert (g["fast"]["orders"], g["fast"]["errors"], g["fast"]["windows"]) == (1 + 5, 3, 1 + 3)
    close(g["normal"], NORMAL)


def test_a_start_after_every_order_leaves_both_arms_empty_and_too_early(hand):
    r = fast_entry.report(hand, start=S + 10 ** 6)
    assert r["groups"]["before"]["orders"] == 10
    close(r["groups"]["fast"], EMPTY)
    close(r["groups"]["normal"], EMPTY)
    close(r["diff"], NO_DIFF)
    assert r["verdict"] == "too early"


def test_the_salt_decides_which_windows_are_fast(hand):
    assert [coin(w, "fast-entry-2") for w in (F1, N1, F2, N2, F3, F4)] == \
        ["normal", "fast", "normal", "normal", "fast", "normal"]
    r = fast_entry.report(hand, start=S, salt="fast-entry-2")
    g = r["groups"]
    assert r["salt"] == "fast-entry-2"
    close(g["before"], BEFORE)
    assert (g["fast"]["orders"], g["fast"]["errors"], g["fast"]["windows"]) == (2 + 1, 1, 2)            # N1, F3
    assert (g["normal"]["orders"], g["normal"]["errors"], g["normal"]["windows"]) == (2 + 2 + 2, 4, 3)  # F1, F2, N2 (+F4)
    assert (g["fast"]["asked"], g["fast"]["filled"]) == (10 + 10 + 5, 8 + 0 + 5)


def test_the_mark_moves_every_landing_time(hand):
    r = fast_entry.report(hand, start=S, mark=450)
    assert r["mark"] == 450
    close(r["groups"]["before"]["landing"], {"median": 32.5, "p10": 32.5, "p90": 32.5})
    close(r["groups"]["fast"]["landing"], {"median": 30.5, "p10": 30.26, "p90": 30.88})
    close(r["groups"]["normal"]["landing"], {"median": 32.75, "p10": 32.15, "p90": 33.7})
    close(r["diff"], DIFF)                             # nothing else moves


@pytest.mark.parametrize("status, response, accepted", [
    (200, {"fill_count": "1.00"}, True),
    (201, {"fill_count": "1.00"}, True),
    (299, {"fill_count": "1.00"}, True),
    (201, {}, True),                                   # a dict, even with nothing in it
    (199, {"fill_count": "1.00"}, False),
    (300, {"fill_count": "1.00"}, False),
    (400, {"error": {"code": "invalid_order"}}, False),
    (429, {"error": {"code": "too_many_requests"}}, False),
    (None, '"network error: timed out"', False),       # no answer came back
    (None, {"fill_count": "1.00"}, False),             # no status, whatever the answer says
    (201, '"ok"', False),                              # JSON, but not a dict
    (201, "[1, 2]", False),
    (201, "null", False),
    (201, "<html>bad gateway</html>", False),          # not JSON
    (201, None, False),                                # NULL
])
def test_which_answers_count_as_accepted(tmp_path, status, response, accepted):
    db = ledger(tmp_path)
    buy(db, S + 481, "KXBTC15M-X", "10", status, response)
    db.commit()
    before = fast_entry.report(db)["groups"]["before"]
    assert (before["orders"], before["errors"]) == ((1, 0) if accepted else (0, 1))
    assert before["windows"] == (1 if accepted else 0)


def test_cancels_are_left_out(tmp_path):
    db = ledger(tmp_path)
    cancel(db, S + 481, "KXBTC15M-X", "o-1")
    cancel(db, S + 482, "KXETH15M-X", "o-2", status=None)
    cancel(db, S + 483, "KXSOL15M-X", "o-3", status=404)
    db.commit()
    for start in (None, S):
        r = fast_entry.report(db, start=start)
        for name in ("before", "fast", "normal"):
            close(r["groups"][name], EMPTY)


def test_an_empty_ledger(tmp_path):
    r = fast_entry.report(ledger(tmp_path), start=S)
    for name in ("before", "fast", "normal"):
        close(r["groups"][name], EMPTY)
    close(r["diff"], NO_DIFF)
    assert r["verdict"] == "too early"
    assert fast_entry.report(ledger(tmp_path, "other.db"), start=None)["verdict"] == "not started"


def test_bets_count_only_once_settled(tmp_path):
    db = ledger(tmp_path)
    w = first("fast")
    buy(db, w + 481, "KXBTC15M-A", "10", 201, {"fill_count": "10.00"})
    buy(db, w + 481, "KXETH15M-A", "10", 201, {"fill_count": "10.00"})
    bet(db, "KXBTC15M-A", w, "won", 9.50, 0.40)
    bet(db, "KXETH15M-A", w, "open", 9.60)
    db.commit()
    g = fast_entry.report(db, start=PAST)["groups"]["fast"]
    assert (g["settled"], g["won"], g["pnl"], g["cost"]) == (1, 1, pytest.approx(0.40), pytest.approx(9.50))
    assert g["perTen"] == pytest.approx(1000 * 0.40 / 9.50)
    assert g["perTenSe"] is None                       # one settled window


# ------------------------------------------------------------------ report: the base share and what was paid over
def order(db, window, ticker, asked, filled, limit=0.96, side="yes", seen=None, fills=(), answer=None):
    """One accepted buy order 480.5 s into `window`, as bot.place() records it: its decision with the ask it saw
    (seen; None: no decision row), the order with its limit on its side (a NO buy is an ask at 1 - limit, as
    bot.order_body sends it), Kalshi's answer (by default with order ID "o-<ticker>"), and that order's fills
    [(count, price)] on its side."""
    oid = "o-" + ticker
    if seen is not None:
        saw(db, ticker, seen, side)
    answer = {"order_id": oid, "fill_count": f"{filled:.2f}", "ts_ms": ms(window, 480.6)} if answer is None else answer
    buy(db, window + 480.5, ticker, str(asked), 201, answer, side="bid" if side == "yes" else "ask",
        price=f"{limit if side == 'yes' else 1 - limit:.4f}")
    for count, price in fills:
        fill(db, oid, ticker, count, price, side)


def before(db):
    """With no start every order is "before": the base share's rules are the same in every group."""
    return fast_entry.report(db)["groups"]["before"]


def test_a_limit_at_or_under_the_ask_it_saw_buys_only_base_contracts_with_no_fills_needed(tmp_path):
    db = ledger(tmp_path)
    order(db, S, "KXBTC15M-1", 10, 7, limit=0.96, seen=0.96)                     # YES at the ask it saw
    order(db, S, "KXETH15M-1", 10, 10, limit=0.95, seen=0.96)                    # YES under it
    order(db, S, "KXSOL15M-1", 4, 4, limit=0.96, seen=0.96 - 5e-10)              # over it by float noise: inside 1e-9
    order(db, S, "KXXRP15M-1", 10, 6, limit=0.93, side="no", seen=0.93)          # NO: an ask at 7c, 1 - 0.07 ≈ 0.93
    order(db, S, "KXDOGE15M-1", 5, 5, limit=0.96, side="no", seen=0.96)          # NO: an ask at 4c
    # The limit is the price on the side it bought: a YES bid at 96c is over a 95c ask, and so is a NO ask at 4c
    # (96c on NO), whatever 1 - 96c or the 4c it sends would say. Over the ask with no fills rows: unknown.
    order(db, S, "KXBNB15M-1", 10, 8, limit=0.96, seen=0.95)
    order(db, S, "KXHYPE15M-1", 10, 9, limit=0.96, side="no", seen=0.95)
    db.commit()
    assert json.loads(db.execute("SELECT request FROM orders WHERE ticker='KXXRP15M-1'").fetchone()[0])["side"] == "ask"
    g = before(db)
    assert (g["asked"], g["filled"]) == (59, 49)
    assert g["baseShare"] == pytest.approx((7 + 10 + 4 + 6 + 5) / (10 + 10 + 4 + 10 + 5))
    assert g["baseShareSe"] is None                                              # one window
    assert g["unknown"] == 2


def test_over_the_ask_it_saw_the_base_is_what_its_fills_bought_at_or_under_it(tmp_path):
    db = ledger(tmp_path)
    order(db, S, "KXBTC15M-1", 12, 11, limit=0.94, seen=0.93, fills=[
        (3, 0.93),                   # exactly the ask it saw: base
        (2, 1 - 0.07),               # 0.9299999999999999: base
        (2, 0.93 + 1e-10),           # float noise over it, inside 1e-9: base
        (1, 0.9301),                 # a hundredth of a cent over it: the old limit wouldn't have bought it
        (3, 0.94)])
    order(db, S, "KXETH15M-1", 10, 5, limit=0.96, side="no", seen=0.95, fills=[(4, 0.95), (1, 0.96)])   # NO prices
    fill(db, "o-elsewhere", "KXBTC15M-1", 5, 0.90)     # another order's fill in the same market: not its own
    fill(db, None, "KXETH15M-1", 3, 0.90)              # a fill kept with no order ID: no order's
    db.commit()
    g = before(db)
    assert g["baseShare"] == pytest.approx((3 + 2 + 2 + 4) / (12 + 10))
    assert g["unknown"] == 0


def test_a_base_it_cant_know_is_unknown_and_left_out_of_the_base_share(tmp_path):
    db = ledger(tmp_path)
    order(db, S, "KXBTC15M-1", 10, 6, limit=0.96, seen=0.96)                     # known: 6 base of 10
    order(db, S, "KXETH15M-1", 10, 3, limit=0.95)                                # filled, no decision row: no ask seen
    order(db, S, "KXSOL15M-1", 10, 3, limit=0.95)
    saw(db, "KXSOL15M-1", None)                                                  # ... or a decision with no price
    order(db, S, "KXXRP15M-1", 10, 3, limit=0.96, seen=0.95)                     # over the ask, no fills rows ...
    fill(db, "o-elsewhere", "KXXRP15M-1", 3, 0.95)                               # ... of its own
    order(db, S, "KXDOGE15M-1", 10, 3, limit=0.96, seen=0.95, answer={"fill_count": "3.00"})   # no order ID to match
    db.commit()
    g = before(db)
    assert g["unknown"] == 4
    assert g["baseShare"] == pytest.approx(6 / 10)                               # not 6 / 50: unknown asks don't count
    assert (g["asked"], g["filled"], g["fillShare"]) == (50, 18, pytest.approx(18 / 50))   # but they still filled


def test_an_order_that_filled_nothing_has_a_base_of_0(tmp_path):
    db = ledger(tmp_path)
    order(db, S, "KXBTC15M-1", 10, 8, limit=0.96, seen=0.96)                     # known: 8 base of 10
    order(db, S, "KXETH15M-1", 10, 0, limit=0.96)                                # no ask seen
    order(db, S, "KXSOL15M-1", 10, 0, limit=0.96, seen=0.95)                     # over the ask, no fills rows
    order(db, S, "KXXRP15M-1", 10, 0, limit=0.96, seen=0.95, answer={"order_id": "o-KXXRP15M-1"})   # no fill_count
    saw(db, "KXDOGE15M-1", None)
    order(db, S, "KXDOGE15M-1", 10, 0, limit=0.96, side="no")                    # a decision with no price
    db.commit()
    g = before(db)
    assert (g["unknown"], g["none"]) == (0, 4)
    assert g["baseShare"] == pytest.approx(8 / 50)


OLD_TABLES = """
CREATE TABLE bets (
    id INTEGER PRIMARY KEY, ticker TEXT UNIQUE, series TEXT, window_open REAL, close_ts REAL,
    side TEXT, price REAL, contracts REAL, cost REAL, fee REAL, placed_ts REAL,
    order_id TEXT, client_order_id TEXT, status TEXT, result TEXT, payout REAL, pnl REAL, settled_ts REAL);
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY, ts REAL, ticker TEXT UNIQUE, series TEXT, yes_bid REAL, yes_ask REAL,
    fav_side TEXT, fav_price REAL, action TEXT, reason TEXT);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY, ts REAL, ticker TEXT, client_order_id TEXT, request TEXT, http_status INTEGER, response TEXT);
"""


def test_a_ledger_from_before_the_fills_table_still_works(tmp_path):
    """A ledger from before the +1c restart has no fills table: what's known without fills rows still counts."""
    path = tmp_path / "old.db"
    db = sqlite3.connect(str(path))
    db.executescript(OLD_TABLES)
    order(db, S, "KXBTC15M-1", 10, 9, limit=0.95, seen=0.95)                     # at the ask it saw: 9 base
    order(db, S, "KXETH15M-1", 5, 5, limit=0.96, side="no", seen=0.96)           # NO at the ask it saw: 5 base
    order(db, S, "KXSOL15M-1", 10, 4, limit=0.96, seen=0.95)                     # over it: unknown
    order(db, S, "KXXRP15M-1", 10, 0, limit=0.96, seen=0.95)                     # over it, nothing filled: 0 base
    bet(db, "KXBTC15M-1", S, "won", 8.55, 0.45, contracts=9)                     # paid exactly 9 at 95c
    bet(db, "KXSOL15M-1", S, "open", 3.84, contracts=4)                          # 4 at 96c: 4c over 4 at 95c
    db.commit()
    db.close()
    ro = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        g = fast_entry.report(ro)["groups"]["before"]
        assert ro.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='fills'").fetchone()[0] == 0
    finally:
        ro.close()
    assert g["baseShare"] == pytest.approx((9 + 5 + 0) / (10 + 5 + 10)) and g["unknown"] == 1
    assert g["overPaid"] == pytest.approx(0.04 / (9 + 4))
    assert (g["orders"], g["asked"], g["filled"]) == (4, 35, 18)


def test_the_base_shares_standard_error_is_clustered_by_window(tmp_path):
    """Orders in one window count as one draw: (base, asked) are summed per window, then the residuals squared."""
    db = ledger(tmp_path)
    order(db, S, "KXBTC15M-1", 10, 3, seen=0.96)
    order(db, S, "KXETH15M-1", 10, 5, seen=0.96)                                 # S: (8, 20)
    order(db, S + 900, "KXBTC15M-2", 10, 2, seen=0.96)                           # (2, 10)
    order(db, S + 1800, "KXBTC15M-3", 10, 9, seen=0.96)                          # (9, 10)
    order(db, S + 2700, "KXBTC15M-4", 10, 4)                                     # only an unknown order: no window
    db.commit()
    g = before(db)
    r = 19 / 40
    want = math.sqrt(3 / 2 * ((8 - 20 * r) ** 2 + (2 - 10 * r) ** 2 + (9 - 10 * r) ** 2)) / 40
    assert want == pytest.approx(0.1616565, abs=1e-7)                           # the hand arithmetic, checked once
    assert g["baseShare"] == pytest.approx(r)
    assert g["baseShareSe"] == pytest.approx(want)
    per_order = math.sqrt(4 / 3 * sum((b - 10 * r) ** 2 for b in (3, 5, 2, 9))) / 40
    assert g["baseShareSe"] != pytest.approx(per_order)                         # not one draw per order


def test_paid_over_the_ask_it_saw_is_per_contract_over_settled_and_open_bets_clustered_by_window(tmp_path):
    db = ledger(tmp_path)
    # S: 10 for 9.54 against 95c (4c over) and 5 NO for 4.68 against 93c (3c over)
    order(db, S, "KXBTC15M-1", 10, 10, limit=0.96, seen=0.95, fills=[(6, 0.95), (4, 0.96)])
    bet(db, "KXBTC15M-1", S, "won", 9.54, 0.46, contracts=10)
    order(db, S, "KXETH15M-1", 5, 5, limit=0.94, side="no", seen=0.93, fills=[(2, 0.93), (3, 0.94)])
    bet(db, "KXETH15M-1", S, "lost", 4.68, -4.68, contracts=5)
    # S + 900: 8 for 7.70 against 97c, still open: 6c under
    order(db, S + 900, "KXSOL15M-2", 8, 8, limit=0.97, seen=0.97)
    bet(db, "KXSOL15M-2", S + 900, "open", 7.70, contracts=8)
    # S + 1800: its base is unknown (no fills rows), but what it paid is known: 6 for 5.73 against 95c, 3c over
    order(db, S + 1800, "KXXRP15M-3", 10, 6, limit=0.96, seen=0.95)
    bet(db, "KXXRP15M-3", S + 1800, "open", 5.73, contracts=6)
    # left out: a bet with no order of its own, one whose order was refused, and one with no ask seen
    saw(db, "KXBNB15M-1", 0.80)
    bet(db, "KXBNB15M-1", S, "won", 9.00, 0.90, contracts=9)
    saw(db, "KXHYPE15M-1", 0.80, action="error")
    buy(db, S + 480.5, "KXHYPE15M-1", "10", 400, {"error": {"code": "insufficient_balance"}})
    bet(db, "KXHYPE15M-1", S, "won", 9.50, 0.50, contracts=10)
    order(db, S, "KXDOGE15M-1", 4, 4, limit=0.96)
    bet(db, "KXDOGE15M-1", S, "won", 3.84, 0.16, contracts=4)
    db.commit()
    g = before(db)
    # by window (Σ(cost − contracts × seen), Σcontracts): S (0.04 + 0.03, 15), S + 900 (−0.06, 8), S + 1800 (0.03, 6)
    r = (0.07 - 0.06 + 0.03) / 29
    assert g["overPaid"] == pytest.approx(r)                                    # dollars a contract: 0.14c
    assert g["overPaidSe"] == pytest.approx(
        math.sqrt(3 / 2 * ((0.07 - 15 * r) ** 2 + (-0.06 - 8 * r) ** 2 + (0.03 - 6 * r) ** 2)) / 29)
    assert g["settled"] == 3                                                    # the P&L still counts settled bets only


def test_one_window_of_bets_has_paid_over_but_no_standard_error(tmp_path):
    db = ledger(tmp_path)
    order(db, S, "KXBTC15M-1", 10, 10, limit=0.96, seen=0.95, fills=[(10, 0.96)])
    bet(db, "KXBTC15M-1", S, "open", 9.60, contracts=10)
    db.commit()
    g = before(db)
    assert g["overPaid"] == pytest.approx(0.01) and g["overPaidSe"] is None


# ------------------------------------------------------------------ report: the verdict
def experiment(tmp_path, fast, normal, n_fast=60, n_normal=60, refused_fast=0, fast_base=None, normal_base=None):
    """A ledger from S on with n_fast fast and n_normal normal windows, one accepted order of 10 in each, its limit at
    96c: the k-th window of an arm fills fast[k % len(fast)] (or normal[...]) contracts. With no base list for an arm
    the ask it saw was 96c too, so every contract is base; with one, it saw 95c, and the k-th window's fills rows put
    fast_base[k % len(fast_base)] (or normal_base[...]) contracts at 95c and the rest at 96c. refused_fast more fast
    windows have only a refused order."""
    db = ledger(tmp_path)
    want, base = {"fast": n_fast, "normal": n_normal}, {"fast": fast_base, "normal": normal_base}
    seen, extra, w = {"fast": 0, "normal": 0}, 0, S
    while seen["fast"] < n_fast or seen["normal"] < n_normal or extra < refused_fast:
        kind = coin(w)
        if seen[kind] < want[kind]:
            k, ticker, oid = seen[kind], f"KXBTC15M-{w}", f"o-{w}"
            fills = (fast if kind == "fast" else normal)[k % len(fast if kind == "fast" else normal)]
            buy(db, w + 480.5, ticker, "10", 201, {"order_id": oid, "fill_count": f"{fills}.00", "ts_ms": ms(w, 480.6)})
            if base[kind] is None:
                saw(db, ticker, 0.96)
            else:
                at_seen = base[kind][k % len(base[kind])]
                saw(db, ticker, 0.95)
                for count, price in ((at_seen, 0.95), (fills - at_seen, 0.96)):
                    if count:
                        fill(db, oid, ticker, count, price)
            seen[kind] += 1
        elif kind == "fast" and extra < refused_fast:
            buy(db, w + 480.5, f"KXBTC15M-{w}", "10", 400, {"error": {"code": "insufficient_balance"}})
            extra += 1
        w += 900
    db.commit()
    return db


def test_fast_fills_more(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[9, 10], normal=[4, 5]), start=S)
    assert (r["groups"]["fast"]["windows"], r["groups"]["normal"]["windows"]) == (60, 60)
    assert r["diff"]["fillShare"] == pytest.approx(0.95 - 0.45)
    assert r["diff"]["fillShareZ"] >= 2
    assert r["diff"]["baseShare"] == pytest.approx(0.95 - 0.45)        # every contract at the ask it saw: base
    assert r["diff"]["baseShareZ"] >= 2
    assert r["verdict"] == "fast fills more"


def test_fast_fills_less(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[4, 5], normal=[9, 10]), start=S)
    assert r["diff"]["fillShare"] == pytest.approx(0.45 - 0.95)
    assert r["diff"]["fillShareZ"] <= -2
    assert r["diff"]["baseShare"] == pytest.approx(0.45 - 0.95)
    assert r["diff"]["baseShareZ"] <= -2
    assert r["verdict"] == "fast fills less"


def test_sixty_windows_each_is_enough(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[9, 10], normal=[4, 5], n_fast=60, n_normal=60), start=S)
    assert (r["groups"]["fast"]["windows"], r["groups"]["normal"]["windows"]) == (60, 60)
    assert r["verdict"] == "fast fills more"


@pytest.mark.parametrize("n_fast, n_normal, refused_fast", [(59, 60, 0), (60, 59, 0), (59, 59, 0), (59, 60, 5), (50, 50, 0)])
def test_too_early_until_each_arm_has_60_windows_with_accepted_orders(tmp_path, n_fast, n_normal, refused_fast):
    db = experiment(tmp_path, fast=[9, 10], normal=[4, 5], n_fast=n_fast, n_normal=n_normal, refused_fast=refused_fast)
    r = fast_entry.report(db, start=S)
    assert (r["groups"]["fast"]["windows"], r["groups"]["normal"]["windows"]) == (n_fast, n_normal)
    assert r["groups"]["fast"]["errors"] == refused_fast      # windows with only refused orders don't count
    assert r["diff"]["fillShareZ"] >= 2                        # however clear the difference
    assert r["diff"]["baseShareZ"] >= 2
    assert r["verdict"] == "too early"


@pytest.mark.parametrize("fast, normal", [([2, 10], [1, 9]), ([1, 9], [2, 10])])
def test_a_difference_under_two_standard_errors_is_no_clear_difference(tmp_path, fast, normal):
    # 60 windows each, alternating: 0.6 vs 0.5 of 10 a window, every window ±4 contracts off its arm's share, so each
    # arm's se is √(60/59·60·4²)/600 and z = ±0.1 / (√2 · that) ≈ ±1.36. Every contract is base, so the base share
    # says the same.
    r = fast_entry.report(experiment(tmp_path, fast, normal, n_fast=60, n_normal=60), start=S)
    arm_se = math.sqrt(60 / 59 * 60 * 4 ** 2) / 600
    sign = 1 if fast == [2, 10] else -1
    for key in ("fillShare", "baseShare"):
        assert r["groups"]["fast"][key + "Se"] == pytest.approx(arm_se)
        assert r["diff"][key] == pytest.approx(sign * 0.1)
        assert r["diff"][key + "Se"] == pytest.approx(math.sqrt(2) * arm_se)
        assert r["diff"][key + "Z"] == pytest.approx(sign * 0.1 / (math.sqrt(2) * arm_se))
    assert r["verdict"] == "no clear difference"


def test_the_same_fills_in_both_arms_is_no_clear_difference(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[4, 6], normal=[4, 6]), start=S)
    for key in ("fillShare", "baseShare"):
        assert r["diff"][key] == pytest.approx(0.0, abs=1e-12)
        assert r["diff"][key + "Se"] > 0
        assert r["diff"][key + "Z"] == pytest.approx(0.0, abs=1e-9)
    assert r["verdict"] == "no clear difference"


def test_no_spread_at_all_has_no_z_and_no_clear_difference(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[5], normal=[5]), start=S)
    for key in ("fillShare", "baseShare"):
        assert (r["groups"]["fast"][key + "Se"], r["groups"]["normal"][key + "Se"]) == (0.0, 0.0)
        assert r["diff"][key] == pytest.approx(0.0, abs=1e-12)
        assert r["diff"][key + "Se"] == 0.0
        assert r["diff"][key + "Z"] is None            # a z over a zero standard error means nothing
    assert r["verdict"] == "no clear difference"


def test_the_verdict_follows_the_base_share_when_the_fill_share_says_the_opposite(tmp_path):
    """Fast fills less in all (65% against 95%), but more at or under the ask it saw (65% against 25%)."""
    r = fast_entry.report(experiment(tmp_path, fast=[6, 7], normal=[9, 10], fast_base=[6, 7], normal_base=[2, 3]),
                          start=S)
    assert (r["groups"]["fast"]["fillShare"], r["groups"]["normal"]["fillShare"]) == (pytest.approx(0.65), pytest.approx(0.95))
    assert (r["groups"]["fast"]["baseShare"], r["groups"]["normal"]["baseShare"]) == (pytest.approx(0.65), pytest.approx(0.25))
    assert r["diff"]["fillShareZ"] <= -2 and r["diff"]["baseShareZ"] >= 2
    assert r["verdict"] == "fast fills more"


def test_the_verdict_says_fast_fills_less_on_the_base_share_even_when_it_fills_more_in_all(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[9, 10], normal=[6, 7], fast_base=[2, 3], normal_base=[6, 7]),
                          start=S)
    assert r["diff"]["fillShare"] == pytest.approx(0.95 - 0.65) and r["diff"]["fillShareZ"] >= 2
    assert r["diff"]["baseShare"] == pytest.approx(0.25 - 0.65) and r["diff"]["baseShareZ"] <= -2
    assert r["verdict"] == "fast fills less"


def test_a_clear_difference_in_fill_share_alone_is_no_clear_difference(tmp_path):
    """The same base share in both arms (half of what was asked): the extra contracts fast buys don't decide it."""
    r = fast_entry.report(experiment(tmp_path, fast=[9, 10], normal=[4, 6], fast_base=[4, 6], normal_base=[4, 6]),
                          start=S)
    assert r["diff"]["fillShareZ"] >= 2
    assert r["diff"]["baseShare"] == pytest.approx(0.0, abs=1e-12)
    assert r["diff"]["baseShareZ"] == pytest.approx(0.0, abs=1e-9)
    assert r["verdict"] == "no clear difference"


def test_with_no_bets_the_pnl_comparison_is_empty(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[9, 10], normal=[4, 5]), start=S)
    assert (r["diff"]["perTen"], r["diff"]["perTenSe"], r["diff"]["perTenZ"]) == (None, None, None)
    assert r["groups"]["fast"]["perTen"] is None and r["groups"]["fast"]["perTenSe"] is None
    assert (r["diff"]["overPaid"], r["diff"]["overPaidSe"], r["diff"]["overPaidZ"]) == (None, None, None)
    assert r["groups"]["fast"]["overPaid"] is None and r["groups"]["fast"]["overPaidSe"] is None


def test_one_arm_without_orders_has_no_difference(tmp_path):
    r = fast_entry.report(experiment(tmp_path, fast=[9, 10], normal=[4, 5], n_normal=0), start=S)
    close(r["groups"]["normal"], EMPTY)
    close(r["diff"], NO_DIFF)
    assert r["verdict"] == "too early"


# ------------------------------------------------------------------ report: read only, and ready for JSON
def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_it_only_reads(hand, tmp_path):
    path = str(tmp_path / "live.db")
    changes, before = hand.total_changes, digest(path)
    fast_entry.report(hand, start=S)
    fast_entry.report(hand)
    assert hand.total_changes == changes
    assert not hand.in_transaction
    hand.commit()
    assert digest(path) == before
    assert hand.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 16     # the connection is still open


def test_it_works_on_a_read_only_connection_with_or_without_rows_by_name(hand, tmp_path):
    want = fast_entry.report(hand, start=S)
    hand.close()
    for rows_by_name in (True, False):
        ro = sqlite3.connect((tmp_path / "live.db").as_uri() + "?mode=ro", uri=True)
        if rows_by_name:
            ro.row_factory = sqlite3.Row
        try:
            assert fast_entry.report(ro, start=S) == want
        finally:
            ro.close()


def test_the_summary_is_ready_for_json(hand, tmp_path):
    for r in (fast_entry.report(hand, start=S), fast_entry.report(hand), fast_entry.report(hand, start=S + 10 ** 6),
              fast_entry.report(experiment(tmp_path / "x", fast=[5], normal=[5]), start=S)):
        assert json.loads(json.dumps(r, allow_nan=False)) == r
