"""The dashboard keeps real time, internet time, not this PC's clock.

The page's clock follows a real-world clock rather than the local machine's, kept up to date. On Oct 11, four NTP servers put this
PC about 0.15 s behind real time; the bot already reads that offset with fast_entry.ntp_offset() (SNTP to three servers
at once, the median, None with no answer).

The server (dashboard.py):
- CLOCK_EVERY = 60: seconds between checks of internet time.
- clock(now=None) -> {"offset", "synced", "checked"}: offset, how many seconds real time is ahead of the PC (None before
  the first good reading); synced, whether there is one; checked, the PC time of the last good reading (None before).
  A request never waits for a check: when one is due (never done, or CLOCK_EVERY s since the last attempt, counted
  from the PC time `now`, time.time() when left out; exactly CLOCK_EVERY is due, as cached() counts) and none is
  running, it starts one on a daemon thread named "internet-clock" that calls fast_entry.ntp_offset(), and answers at
  once with what it has. A check that finds no server (None) or raises keeps the last good offset and its checked
  time, raises nothing out of its thread, and still counts as an attempt. At most one check runs at a time.
- real_now(): the PC's clock plus the offset (0 without one). state()'s "now" is that and state() sends "clock":
  clock(); every other figure in state() stays on the PC's clock, as the ledger's timestamps are the PC's (a bet
  placed 23 h 59 m ago by the PC's clock is still today's). research_live(), live_research() and the navbar balance
  (balance_now) send real_now() as their "now".
- The reading lives in one module-level object, dashboard._clock: conftest.py puts a copy of it as it was at import in
  place before each test, so nothing carries over between tests.

conftest.py's fake_ntp stands in for fast_entry.ntp_offset in every test: 0.0 s unless a test sets fake_ntp.offset
(seconds, None, or an exception to raise); hold()/release() keep a check running; wait() waits for the dashboard's
check threads to finish, which is how these tests await a check. The PC's clock is test_dashboard_more.py's `home`:
frozen at NOW (Sep 28, 2026, 3 PM ET) and moved only by the test.

The page (dashboard.html): skew and nowS() stay as they are, so with data.now real time every timer is (checked here:
the entry countdown and the board's minute move with data.now). The footer reads
"Updated <time> · refreshes every second[ · the balance up top every second] · <clock words> · times are your local
time", the clock words "clock set to internet time" when d.clock.synced and "clock from this PC" otherwise (a server
started before this sends no clock). When synced, the element holding the clock words has a title giving the offset:
"this PC's clock is 0.153 s behind" (or "ahead"), to 3 decimals. The page is dashboard.html's whole script run in
test_folds_live.py's stand-in browser in node, its /api/state answer stamped with the page's clock plus `ahead`
seconds; the node tests skip themselves without node.

    python -m pytest tests/test_real_clock.py -q
"""
import copy
import functools
import json
import os
import re
import subprocess
import threading
import time

import pytest

import conftest
from kalshi_bot.web import dashboard
from kalshi_bot import fast_entry
import test_folds_live as folds
from test_dashboard_more import NOW, add_bet, home, kalshi_stub, mode_db, order, with_cfg  # noqa: F401 (fixtures)

DAY = 86400
UNSYNCED = {"offset": None, "synced": False, "checked": None}
PROD = dict(KALSHI_ENV="prod", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")
# a check that finds no time server, one whose sockets fail, and one that breaks some other way
FAILURES = [None, OSError("no time server answered"), RuntimeError("can't start new thread")]
FAILURE_IDS = ["none", "oserror", "raises"]
no_thread_errors = pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")


@pytest.fixture
def server(home, tmp_path, monkeypatch):
    """`home` (the PC's clock frozen at NOW, Kalshi stubbed) with a live-prod ledger (home.db), an empty research folder
    and no live markets, so every route answers without the network."""
    monkeypatch.setattr(dashboard, "RESEARCH", str(tmp_path / "research"))
    monkeypatch.setattr(dashboard, "live", lambda book=None: None)
    home.db = mode_db(home, "live-prod")
    yield home
    home.db.close()


def read(fake_ntp, offset):
    """One check of internet time that answers `offset`, done: clock() starts it and the test waits for it."""
    fake_ntp.offset = offset
    dashboard.clock()
    fake_ntp.wait()


# ------------------------------------------------------------------ clock(): a reading, never a wait
def test_internet_time_is_checked_once_a_minute():
    assert dashboard.CLOCK_EVERY == 60


def test_before_any_reading_the_clock_is_unsynced_and_one_check_starts(home, fake_ntp):
    fake_ntp.hold()
    assert dashboard.clock() == UNSYNCED
    assert len(fake_ntp.checks()) == 1, "clock() didn't start one internet-clock check thread"
    fake_ntp.release()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 1


def test_the_check_runs_on_a_daemon_thread_named_internet_clock(home, fake_ntp):
    fake_ntp.hold()
    dashboard.clock()
    assert fake_ntp.called.wait(5), "clock() started no check: fast_entry.ntp_offset was never called"
    t = fake_ntp.calls[0]
    assert t is not threading.current_thread(), "the check ran on the request's own thread"
    assert (t.name, t.daemon) == ("internet-clock", True)


def test_a_request_never_waits_for_the_check(server, fake_ntp):
    """With a check still running (the time servers slow to answer), every request answers at once, on the PC's clock."""
    fake_ntp.hold()
    began = time.perf_counter()
    first = dashboard.clock()
    s = dashboard.state("live-prod")
    r = dashboard.research_live()
    took = time.perf_counter() - began
    assert took < 2 and fake_ntp.stuck == 0, f"a request waited {took:.1f} s for the check"
    assert first == UNSYNCED and s["clock"] == UNSYNCED
    assert s["now"] == NOW and r["now"] == NOW and dashboard.real_now() == NOW
    assert len(fake_ntp.checks()) == 1


def test_after_a_reading_the_clock_has_its_offset_and_is_synced(home, fake_ntp):
    read(fake_ntp, 0.153)
    assert dashboard.clock() == {"offset": 0.153, "synced": True, "checked": NOW}
    assert len(fake_ntp.calls) == 1                      # the next check is CLOCK_EVERY away


def test_each_good_reading_replaces_the_last(home, fake_ntp):
    read(fake_ntp, 0.153)
    home.clock[0] = NOW + 60
    read(fake_ntp, None)
    home.clock[0] = NOW + 120
    read(fake_ntp, -0.04)
    assert len(fake_ntp.calls) == 3
    assert dashboard.clock() == {"offset": -0.04, "synced": True, "checked": NOW + 120}


# ------------------------------------------------------------------ a check that fails
@no_thread_errors
@pytest.mark.parametrize("failure", FAILURES, ids=FAILURE_IDS)
def test_a_failed_check_keeps_the_last_good_offset_and_when_it_was_read(home, fake_ntp, failure):
    read(fake_ntp, 0.153)
    home.clock[0] = NOW + dashboard.CLOCK_EVERY
    read(fake_ntp, failure)
    assert len(fake_ntp.calls) == 2
    assert dashboard.clock() == {"offset": 0.153, "synced": True, "checked": NOW}
    assert dashboard.real_now() == pytest.approx(NOW + dashboard.CLOCK_EVERY + 0.153, abs=1e-6)


@no_thread_errors
@pytest.mark.parametrize("failure", FAILURES, ids=FAILURE_IDS)
def test_with_no_reading_yet_a_failed_check_stays_unsynced(home, fake_ntp, failure):
    read(fake_ntp, failure)
    assert len(fake_ntp.calls) == 1
    assert dashboard.clock() == UNSYNCED
    assert dashboard.real_now() == NOW


@no_thread_errors
@pytest.mark.parametrize("failure", FAILURES, ids=FAILURE_IDS)
def test_a_failed_check_still_counts_as_an_attempt(home, fake_ntp, failure):
    read(fake_ntp, failure)
    home.clock[0] = NOW + dashboard.CLOCK_EVERY - 0.5
    dashboard.clock()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 1, "a failed check was tried again at once, not CLOCK_EVERY later"
    home.clock[0] = NOW + dashboard.CLOCK_EVERY
    dashboard.clock()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 2, "no check CLOCK_EVERY after the failed one"


# ------------------------------------------------------------------ one check at a time, one a minute
def test_no_second_check_starts_while_one_is_running(home, fake_ntp):
    fake_ntp.hold()
    dashboard.clock()
    home.clock[0] = NOW + 10 * dashboard.CLOCK_EVERY    # long due by the clock, but one is still running
    for _ in range(5):
        assert dashboard.clock() == UNSYNCED
    assert len(fake_ntp.checks()) == 1
    fake_ntp.offset = 0.153
    fake_ntp.release()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 1
    assert dashboard.clock()["offset"] == 0.153


def test_many_requests_at_once_start_one_check(home, fake_ntp):
    fake_ntp.hold()
    line_up, got, errors = threading.Barrier(8), [], []

    def ask():
        try:
            line_up.wait(5)
            got.append(dashboard.clock())
        except Exception as e:
            errors.append(e)
    askers = [threading.Thread(target=ask) for _ in range(8)]
    for t in askers:
        t.start()
    for t in askers:
        t.join(5)
    assert not errors, errors[0]
    assert got == [UNSYNCED] * 8
    assert len(fake_ntp.checks()) == 1
    fake_ntp.release()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 1


def test_the_next_check_comes_only_after_clock_every(home, fake_ntp):
    read(fake_ntp, 0.153)
    for later in (1, 30, dashboard.CLOCK_EVERY - 0.001):
        home.clock[0] = NOW + later
        dashboard.clock()
        fake_ntp.wait()
    assert len(fake_ntp.calls) == 1
    home.clock[0] = NOW + dashboard.CLOCK_EVERY          # exactly CLOCK_EVERY on is due, as cached() counts
    dashboard.clock()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 2


def test_the_spacing_is_read_from_clock_every(home, fake_ntp, monkeypatch):
    monkeypatch.setattr(dashboard, "CLOCK_EVERY", 5)
    read(fake_ntp, 0.153)
    home.clock[0] = NOW + 4.9
    dashboard.clock()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 1
    home.clock[0] = NOW + 5
    dashboard.clock()
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 2


def test_clock_counts_from_the_pc_time_it_is_given(home, fake_ntp):
    """clock(now): the attempt is stamped with `now`, the PC time it was asked at, and the spacing counted from it."""
    dashboard.clock(now=NOW + 1000)
    fake_ntp.wait()
    dashboard.clock(now=NOW + 1000 + dashboard.CLOCK_EVERY - 1)
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 1
    dashboard.clock(now=NOW + 1000 + dashboard.CLOCK_EVERY)
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 2


def test_a_page_polling_every_second_asks_internet_time_once_a_minute(server, fake_ntp):
    for second in range(121):
        server.clock[0] = NOW + second
        dashboard.state("live-prod")
        fake_ntp.wait()
    assert len(fake_ntp.calls) == 3                      # at 0, 60 and 120 s


def test_each_test_starts_with_no_reading(home, fake_ntp, monkeypatch):
    """conftest.py puts a copy of dashboard._clock as it was at import (no reading, no attempt) in place before each
    test, so the dashboard keeps its whole reading there."""
    assert hasattr(dashboard, "_clock"), "dashboard keeps no module-level _clock for conftest.py to reset between tests"
    read(fake_ntp, 0.153)
    assert dashboard.clock()["synced"]
    monkeypatch.setattr(dashboard, "_clock", copy.copy(conftest.PRISTINE_CLOCK))   # what conftest.py does before a test
    assert dashboard.clock() == UNSYNCED
    fake_ntp.wait()
    assert len(fake_ntp.calls) == 2


def test_no_test_can_reach_a_real_time_server(fake_ntp):
    """fast_entry.ntp_offset is conftest.py's stub, and should anything get past it, a datagram to port 123 goes nowhere."""
    assert fast_entry.ntp_offset is fake_ntp and fake_ntp() == 0.0
    assert conftest.REAL_NTP_OFFSET(("127.0.0.1",), timeout=0.2) is None
    assert fake_ntp.reached == [("127.0.0.1", 123)]
    fake_ntp.reached.clear()                             # this test's own try: not a failure


# ------------------------------------------------------------------ state() and the other routes
def test_state_sends_real_time_and_the_clock(server, fake_ntp):
    fake_ntp.offset = 0.153
    s = dashboard.state("live-prod")
    assert (s["now"], s["clock"]) == (NOW, UNSYNCED)     # before the first reading: the PC's clock
    fake_ntp.wait()
    s = dashboard.state("live-prod")
    assert s["now"] == pytest.approx(NOW + 0.153, abs=1e-6)
    assert s["clock"] == {"offset": 0.153, "synced": True, "checked": NOW}
    assert len(fake_ntp.calls) == 1


@pytest.mark.parametrize("offset", [0.153, -0.2])
def test_real_now_is_the_pcs_clock_plus_the_offset(home, fake_ntp, offset):
    read(fake_ntp, offset)
    assert dashboard.real_now() == pytest.approx(NOW + offset, abs=1e-6)
    home.clock[0] = NOW + 10
    assert dashboard.real_now() == pytest.approx(NOW + 10 + offset, abs=1e-6)


def test_the_other_routes_send_real_now(server, kalshi_stub, monkeypatch):
    with_cfg(monkeypatch, **PROD)
    monkeypatch.setattr(dashboard, "real_now", lambda: NOW + 0.25)
    assert dashboard.research_live()["now"] == NOW + 0.25
    assert dashboard.live_research("live-prod")["now"] == NOW + 0.25
    assert dashboard.balance_now("live-prod")["now"] == NOW + 0.25


def test_after_a_reading_every_route_is_on_real_time(server, kalshi_stub, fake_ntp, monkeypatch):
    with_cfg(monkeypatch, **PROD)
    read(fake_ntp, 0.153)
    real = pytest.approx(NOW + 0.153, abs=1e-6)
    assert dashboard.state("live-prod")["now"] == real
    assert dashboard.research_live()["now"] == real
    assert dashboard.live_research("live-prod")["now"] == real
    assert dashboard.balance_now("live-prod")["now"] == real


def test_the_ledgers_last_24_hours_stay_on_the_pcs_clock(server, fake_ntp, monkeypatch):
    """The ledger's timestamps are the PC's: with the PC 2 minutes behind real time, a bet placed 23 h 59 m ago by the
    PC's clock (24 h 1 m ago by real time) is still in the last 24 hours, and so is its win, settled 30 s later."""
    read(fake_ntp, 120.0)
    placed = NOW - DAY + 60
    add_bet(server.db, "KXBTC15M-26SEP271515-15", price=0.95, contracts=3, status="won", placed=placed, settled=placed + 30)
    add_bet(server.db, "KXETH15M-26SEP271400-00", status="won", placed=NOW - DAY - 3600)   # 25 h ago: not today's either way
    order(server.db, placed, "KXBTC15M-26SEP271515-15", count="3", price="0.9500", response='{"fill_count": "3.00"}')
    server.db.commit()
    monkeypatch.setattr(dashboard, "account", lambda env: {"total": 241.5, "crypto": 241.5, "positions": 0, "held": 0.0,
                                                           "value": 241.5})
    server.curve[0] = [[NOW - DAY - 3720, 100.0, 0, "start"]]
    s = dashboard.state("live-prod")
    assert s["now"] == pytest.approx(NOW + 120, abs=1e-6)                 # real time ...
    assert s["dayBets"] == 1                                              # ... but the last 24 hours are the PC's
    assert s["day"] == pytest.approx(3 - 3 * 0.95 - 0.01)
    assert s["staked"]["day"] == pytest.approx(2.85)
    assert s["fills"]["orders"] == 1
    assert s["kalshiCurve"][-1] == [NOW, 241.5, 0, "now"]                 # the account's value now, on the PC's clock too


# ------------------------------------------------------------------ the page
needs_node = pytest.mark.skipif(not folds.NODE, reason="node isn't installed")
SYNCED, FROM_PC = "clock set to internet time", "clock from this PC"
BALANCE = {"value": 517.73, "gain": 17.73, "pct": 0.0354, "now": folds.CLOCK, "updated": None}
# test_folds_live.py's stand-in fetch stamps the /api/state answer with the page's clock; this one adds `ahead` seconds
AHEAD_DOM = folds.DOM_JS.replace("{ now: __now / 1000 }", "{ now: __now / 1000 + (a.ahead || 0) }")


@functools.lru_cache(maxsize=None)
def _page_run(payload):
    r = subprocess.run([folds.NODE, "-e", folds.RUNNER], input=payload, capture_output=True, text=True, encoding="utf-8",
                       timeout=120, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return r.stdout


def draw(state=None, now=None, ahead=0.0, balance=None):
    """The Live tab as the page draws it a second after opening (test_folds_live.py's stand-in browser), from `state`
    (the saved baseline's by default, from a server that sends no clock), its `now` the page's clock plus `ahead` s; the
    navbar balance answers `balance`, or not at all. now: the page's clock as it opens (the baseline's by default)."""
    if not folds.NODE:
        pytest.skip("node isn't installed")
    assert AHEAD_DOM != folds.DOM_JS, "test_folds_live.py's stand-in fetch changed: update AHEAD_DOM"
    g = folds.golden()
    now = g["now"] if now is None else now
    answers = {"/api/state": {"status": 200, "body": g["state"] if state is None else state, "clock": True, "ahead": ahead},
               "/api/research/live": {"status": 200, "body": {"now": now, "stamp": 0, "live": folds.board_feed(now)}}}
    if balance is not None:
        answers["/api/balance"] = {"status": 200, "body": balance}
    payload = json.dumps({"dom": AHEAD_DOM, "script": '"use strict";' + folds.SCRIPT, "body": folds.BODY, "now": now * 1000,
                          "width": folds.WIDTH, "store": {}, "answers": answers, "steps": []}, sort_keys=True)
    out = json.loads(_page_run(payload))
    assert not out["loadError"], f"dashboard.html's script didn't load:\n{out['loadError']}"
    page = folds.Page(out["steps"][0])
    assert not page.errors, f"the page threw:\n{page.errors[0]}"
    return page


def sent(clock):
    """The baseline's state with this clock ("absent": none, as from a server started before it)."""
    s = dict(folds.golden()["state"])
    s.pop("clock", None)
    if clock != "absent":
        s["clock"] = clock
    return s


def synced(offset):
    return {"offset": offset, "synced": True, "checked": folds.CLOCK - 30}


def footer_text(page):
    return page.by_id("foot").text()


def footer_like(words, balance):
    return (r"Updated .+? · refreshes every second" + (" · the balance up top every second" if balance else "")
            + f" · {re.escape(words)} · times are your local time")


def clock_words(page, words):
    """The footer's element holding just the clock words (the innermost, or the one with a title)."""
    hits = [e for e in page.by_id("foot").els() if e.text() == words]
    assert hits, f"no element in the footer holds just {words!r}: {footer_text(page)!r}"
    return next((e for e in reversed(hits) if "title" in e.attrs), hits[-1])


@needs_node
@pytest.mark.parametrize("balance", [None, BALANCE], ids=["no-balance", "balance"])
def test_the_footer_says_the_clock_is_internet_time_when_synced(balance):
    text = footer_text(draw(sent(synced(0.153)), balance=balance))
    assert re.fullmatch(footer_like(SYNCED, balance), text), text


@needs_node
@pytest.mark.parametrize("clock", [UNSYNCED, None, "absent"], ids=["unsynced", "null", "from-an-older-server"])
@pytest.mark.parametrize("balance", [None, BALANCE], ids=["no-balance", "balance"])
def test_the_footer_says_the_clock_is_this_pcs_otherwise(clock, balance):
    page = draw(sent(clock), balance=balance)
    text = footer_text(page)
    assert re.fullmatch(footer_like(FROM_PC, balance), text), text
    titles = " ".join(e.attrs.get("title", "") for e in page.by_id("foot").els())
    assert not re.search(r"behind|ahead", titles), f"an unsynced clock claims an offset: {titles!r}"


@needs_node
@pytest.mark.parametrize("offset, says", [(0.153, "0.153 s behind"), (0.1534, "0.153 s behind"), (-0.2, "0.200 s ahead"),
                                          (1.5, "1.500 s behind")])
def test_when_synced_the_clock_words_title_gives_the_offset(offset, says):
    """offset is how far real time is ahead of the PC: positive, the PC is behind."""
    el = clock_words(draw(sent(synced(offset))), SYNCED)
    title = el.attrs.get("title", "")
    assert re.search(r"this PC['’]s clock is " + re.escape(says), title, re.I), f"title={title!r}"


@needs_node
@pytest.mark.parametrize("ahead, entry, minute", [(0.0, "00:01", 8), (0.5, "Entering now", 9)])
def test_the_timers_follow_the_servers_time_not_this_pcs(ahead, entry, minute):
    """nowS() follows data.now: 0.3 s before minute 8 of the 3:00 PM window by this PC's clock, the entry countdown
    says 00:01 and the board minute 8; with the server's time 0.5 s ahead, it's already entering and minute 9."""
    t = NOW + 479.7
    page = draw({**folds.golden()["state"], "heartbeat": t - 4}, now=t - 1, ahead=ahead)   # its picture is a second in
    assert page.by_id("timer").text() == f"Next entry {entry}"
    assert f"minute {minute} of 15" in page.fold("live.board").meta, page.fold("live.board").meta
