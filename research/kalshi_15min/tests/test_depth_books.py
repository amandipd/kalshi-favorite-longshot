"""The depth check's live half, depth_books.py: a week of order books at the passed groups' checkpoints, and its report.

other_markets.py's pass test found four liquid groups that paid in both halves (other_markets_findings.md): hourly
temperature 30 and 10 minutes before the close, and the daily gas (and SOFR, ERCOT) markets 2 and 1 hours before it.
Their backtest assumes a full $10 fills at the recorded ask plus 0.4c. depth_books.py records the real books at those
moments for a week, so the report can say how much $10, $25, $50 and $100 would really have bought, and what the bets
made at the book against the backtest's assumption. Spec: depth_books.py's own docstring.

Everything here is offline: Kalshi is faked (depth_books.get monkeypatched, or requests' Session.request under get()
itself), the clock and sleep are injected, and an autouse guard makes any real socket connection fail the test.

Readings of the spec (the contract where it leaves a choice):

- `get(path, params)` takes a path relative to BASE ("/markets/X/orderbook") and sends GET BASE + path through
  requests (requests.get or a Session: both end in Session.request, which the tests fake). It reads the clock through
  the `time` module (time.time, or time.monotonic for spacing) and waits with time.sleep, as fetch_other.get does. A
  404 is None at once, with no retry; 429, 5xx and connection errors are retried (at least 5 tries) and then raise.
- `row(rec)["fill"]` is {10: share, 25: share, 50: share, 100: share} with int keys; `row(rec)["fill_1c"]` is one
  float, the $10 share at a limit one cent higher. `at_ask` and the fills are in dollars and shares of the stake.
- `walk` buys the levels in the order given (ladder's, cheapest first); the last level taken is taken in part, so
  cost equals the dollars whenever the book is deep enough.
- `summarise` has an entry for every (family, k) that has records; the four STAKES shares, `full10_1c` and
  `median_at_ask` are over its bets, `pnl_book` and `pnl_backtest` over its settled bets (None when none).
- `record` uses only the injected now/sleep (time.sleep is made to fail here), never sleeps more than 5 s at a time,
  lists markets at the start and then again each time REFRESH seconds have passed, and a book that fails is logged
  with its ticker (to LOG, or printed) and leaves no line. A checkpoint more than GRACE seconds past at the start is
  missed, not read.
- `results(tickers, cache)` returns the settled ones among `tickers`; a market Kalshi doesn't know (None) is left out.
- `main()` reads sys.argv: `record [days]` calls record() with until = now + days (None, or a week, without days);
  `report` reads OUT, asks results() for its tickers and prints the summary, one line per (family, k) naming the
  family as FAMILIES does ("temp", "econ").

    python -m pytest research/kalshi_15min/tests/test_depth_books.py -q
"""

from __future__ import annotations

import importlib
import itertools
import json
import socket
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

UTC = timezone.utc
TEMP = {"KXTEMPMIAH", "KXTEMPLAXH", "KXTEMPLAXHS", "KXTEMPNYCH", "KXTEMPNYCHS", "KXTEMPAUSH", "KXTEMPCHIH",
        "KXTEMPCHIHS", "KXTEMPDCH"}
STATES = "TX CA NJ IL FL NY OH WA NC GA PA TN MI VA AZ MA SC OR CO MD MN NV CT IN".split()
ECON = {"KXAAAGASD", "KXSOFRD", "KXTXERCOTPEAKD"} | {f"KXAAAGASD{s}" for s in STATES}
Q = 1_789_999_200                     # a quarter hour (divisible by 900): Sep 21 2026, 14:00 UTC
CLOSE = Q + 3 * 3600                  # a close a few hours later, for hand-built markets


@pytest.fixture(scope="module")
def dbk(study):
    """depth_books, imported with the synthetic study as the working directory (other_markets reads from there)."""
    return importlib.import_module("depth_books")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here may reach Kalshi: a fake that misses a request fails it instead of going out."""
    def refuse(*args, **kwargs):
        raise OSError("the depth_books tests never use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def book(yes=(), no=()):
    """An orderbook_fp as Kalshi sends it: each side's resting bids as [price, size] strings, ascending by price."""
    side = lambda levels: [[f"{p:.4f}", f"{s:.2f}"] for p, s in sorted(levels)]
    return {"yes_dollars": side(yes), "no_dollars": side(no)}


# YES the favourite: YES bid 96c, YES ask 98c (NO bids at 1c and 2c), 30 contracts offered at 98c and 100 at 99c.
DEEP = book(yes=[(0.95, 20), (0.96, 40)], no=[(0.01, 100), (0.02, 30)])
# The same quote with only 5 contracts at 98c: $10 at the ask + 0.4c gets $4.90, one more cent gets the rest at 99c.
THIN = book(yes=[(0.96, 40)], no=[(0.01, 100), (0.02, 5)])
# NO the favourite: YES bid 2c and ask 3c, so NO costs 98c (25 offered, from the YES bid at 2c) and 99c (50).
NO_FAV = book(yes=[(0.01, 50), (0.02, 25)], no=[(0.96, 10), (0.97, 5)])
WIDE = book(yes=[(0.93, 40)], no=[(0.02, 30)])          # YES at 98c, but a 5c spread: not liquid
CHEAP = book(yes=[(0.59, 40)], no=[(0.40, 30)])         # YES the favourite at 60c: liquid, out of the 90-99.9c band
EMPTY = {"yes_dollars": [], "no_dollars": None}


def market(ticker, close=CLOSE, family=None):
    series = ticker.split("-")[0]
    family = family or ("temp" if series in TEMP else "econ")
    return {"ticker": ticker, "series": series, "family": family, "close": close}


class Clock:
    """A fake clock: now() reads it, sleep() moves it on at once, and every sleep is kept. With `yield_`, each sleep
    also lets the other threads run for a moment, as a real one would."""

    def __init__(self, t, yield_=None):
        self.t, self.sleeps, self.yield_ = float(t), [], yield_

    def now(self):
        return self.t

    def sleep(self, s):
        assert s >= -1e-9, f"slept a negative {s}"
        self.sleeps.append(s)
        assert len(self.sleeps) < 2_000_000, "the loop never ended"
        self.t += max(s, 0.0)
        if self.yield_:
            self.yield_(0.0005)


def iso(ts):
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ constants


def test_the_families_are_the_four_passed_groups(dbk):
    assert set(dbk.FAMILIES) == {"temp", "econ"}
    temp, econ = dbk.FAMILIES["temp"], dbk.FAMILIES["econ"]
    assert len(temp["series"]) == 9 and set(temp["series"]) == TEMP
    assert len(econ["series"]) == 27 and set(econ["series"]) == ECON
    assert tuple(temp["checks"]) == (30, 10) and temp["unit"] == 60
    assert tuple(econ["checks"]) == (2, 1) and econ["unit"] == 3600


def test_the_recorders_settings(dbk, study):
    assert dbk.BASE == study.backtest_large.BASE
    assert tuple(dbk.STAKES) == (10, 25, 50, 100)
    assert dbk.RATE == 4.0
    assert tuple(dbk.QUIET) == (470, 560)
    assert (dbk.GRACE, dbk.REFRESH) == (180, 300)
    assert (dbk.OUT, dbk.LOG) == ("depth_books.jsonl", "depth_books.log")
    assert dbk.LIQUID == 0.03


# ------------------------------------------------------------------ ladder, quote, favourite


def test_buying_yes_takes_the_no_bids_cheapest_first(dbk):
    assert dbk.ladder(DEEP, "yes") == [(0.98, 30.0), (0.99, 100.0)]


def test_buying_no_takes_the_yes_bids_cheapest_first(dbk):
    assert dbk.ladder(DEEP, "no") == [(0.04, 40.0), (0.05, 20.0)]
    assert dbk.ladder(NO_FAV, "no") == [(0.98, 25.0), (0.99, 50.0)]


def test_sizes_can_be_fractional(dbk):
    assert dbk.ladder({"yes_dollars": [], "no_dollars": [["0.0200", "50.80"]]}, "yes") == [(0.98, 50.8)]


@pytest.mark.parametrize("b", [{"yes_dollars": [], "no_dollars": []}, {"yes_dollars": None, "no_dollars": None}, {}])
def test_an_empty_or_missing_side_has_no_ladder(dbk, b):
    assert dbk.ladder(b, "yes") == [] and dbk.ladder(b, "no") == []


def test_quote_is_the_best_yes_bid_and_one_minus_the_best_no_bid(dbk):
    assert dbk.quote(DEEP) == (0.96, 0.98)
    assert dbk.quote(NO_FAV) == (0.02, 0.03)


def test_quote_has_none_for_an_empty_side(dbk):
    assert dbk.quote(book(no=[(0.02, 5)])) == (None, 0.98)
    assert dbk.quote(book(yes=[(0.96, 5)])) == (0.96, None)
    assert dbk.quote(EMPTY) == (None, None)
    assert dbk.quote({}) == (None, None)


def test_the_favourite_yes(dbk):
    assert dbk.favourite(DEEP) == {"side": "yes", "ask": 0.98, "bid": 0.96, "spread": 0.02}


def test_the_favourite_no_costs_one_minus_the_yes_bid_and_its_bid_is_one_minus_the_yes_ask(dbk):
    assert dbk.favourite(NO_FAV) == {"side": "no", "ask": 0.98, "bid": 0.97, "spread": 0.01}


def test_a_tie_has_no_favourite(dbk):
    assert dbk.favourite(book(yes=[(0.40, 1)], no=[(0.40, 1)])) is None     # YES 60c, NO 60c


@pytest.mark.parametrize("b", [book(no=[(0.02, 5)]), book(yes=[(0.96, 5)]), EMPTY,
                               book(yes=[(0.0, 5)], no=[(0.02, 5)]),          # a YES bid of 0
                               book(yes=[(0.5, 5)], no=[(0.0, 5)])])          # a YES ask of 1
def test_no_favourite_without_a_real_bid_and_ask(dbk, b):
    assert dbk.favourite(b) is None


def test_the_favourite_has_no_price_band(dbk):
    assert dbk.favourite(CHEAP) == {"side": "yes", "ask": 0.6, "bid": 0.59, "spread": 0.01}


def test_the_favourite_is_other_markets_rule(dbk):
    """For every bid and ask on a grid, the same side and price as other_markets.bets() would take."""
    for b, a in itertools.product([0.01, 0.02, 0.05, 0.3, 0.5, 0.7, 0.9, 0.95, 0.97], [0.03, 0.1, 0.5, 0.6, 0.92, 0.98, 0.99]):
        if a <= b:
            continue
        yes, no = a, round(1 - b, 4)
        want = None if abs(yes - no) < 1e-9 else ("yes", yes) if yes > no else ("no", no)
        got = dbk.favourite(book(yes=[(b, 10)], no=[(round(1 - a, 4), 10)]))
        assert (got and (got["side"], got["ask"])) == (want or None), (b, a)
        if got:
            assert got["spread"] == round(a - b, 4)


# ------------------------------------------------------------------ walk


def test_walk_stops_when_the_dollars_are_spent_taking_the_last_level_in_part(dbk):
    c, cost = dbk.walk([(0.98, 30.0), (0.99, 100.0)], 10, 0.984)
    assert c == pytest.approx(10 / 0.98) and cost == pytest.approx(10.0)


def test_walk_climbs_the_levels_under_the_limit(dbk):
    c, cost = dbk.walk([(0.98, 5.0), (0.99, 100.0)], 10, 0.994)
    assert c == pytest.approx(5 + 5.1 / 0.99) and cost == pytest.approx(10.0)


def test_walk_never_pays_over_the_limit(dbk):
    c, cost = dbk.walk([(0.98, 5.0), (0.99, 100.0)], 10, 0.984)
    assert c == pytest.approx(5.0) and cost == pytest.approx(4.9)


def test_walk_takes_what_there_is_when_the_book_runs_out(dbk):
    c, cost = dbk.walk([(0.98, 5.0), (0.99, 5.0)], 100, 0.999)
    assert c == pytest.approx(10.0) and cost == pytest.approx(9.85)


def test_a_level_at_the_limit_counts_despite_float_noise(dbk):
    limit = 0.7 + 0.1 + 0.004                      # 0.8039999999999999
    c, cost = dbk.walk([(0.804, 100.0)], 10, limit)
    assert cost == pytest.approx(10.0) and c == pytest.approx(10 / 0.804)


def test_walk_with_nothing_to_buy(dbk):
    assert dbk.walk([], 10, 0.99) == (0.0, 0.0)
    assert dbk.walk([(0.99, 5.0)], 10, 0.98) == (0.0, 0.0)


def test_walk_exactly_enough(dbk):
    c, cost = dbk.walk([(0.5, 20.0)], 10, 0.5)
    assert c == pytest.approx(20.0) and cost == pytest.approx(10.0)


# ------------------------------------------------------------------ checkpoints and due


def test_checkpoints_count_back_from_the_close(dbk):
    assert dbk.checkpoints("temp", CLOSE) == [(30, CLOSE - 1800), (10, CLOSE - 600)]
    assert dbk.checkpoints("econ", CLOSE) == [(2, CLOSE - 7200), (1, CLOSE - 3600)]


def test_a_checkpoint_is_due_from_its_time_until_grace_runs_out(dbk):
    m = market("KXTEMPMIAH-A")
    ts = CLOSE - 600
    assert dbk.due([m], ts - 1, set()) == []
    assert dbk.due([m], ts, set()) == [(m, 10)]
    assert dbk.due([m], ts + dbk.GRACE - 1, set()) == [(m, 10)]
    assert dbk.due([m], ts + dbk.GRACE, set()) == []


def test_a_checkpoint_already_read_isnt_due(dbk):
    m = market("KXTEMPMIAH-A")
    assert dbk.due([m], CLOSE - 600, {("KXTEMPMIAH-A", 10)}) == []
    assert dbk.due([m], CLOSE - 600, {("KXTEMPMIAH-A", 30)}) == [(m, 10)]


def test_due_checkpoints_come_oldest_first_across_families(dbk):
    gas = market("KXAAAGASD-G", close=CLOSE + 3600 - 50)       # its 1 h checkpoint: CLOSE - 50
    hot = market("KXTEMPNYCH-H", close=CLOSE + 1800 - 100)     # its 30 min checkpoint: CLOSE - 100
    late = market("KXTEMPMIAH-L", close=CLOSE + 600 - 10)      # its 10 min checkpoint: CLOSE - 10
    assert dbk.due([late, gas, hot], CLOSE, set()) == [(hot, 30), (gas, 1), (late, 10)]


def test_snap_keeps_the_market_and_the_raw_book(dbk):
    m = market("KXTEMPMIAH-A")
    assert dbk.snap(m, 10, THIN, CLOSE - 590) == {"t": "KXTEMPMIAH-A", "s": "KXTEMPMIAH", "f": "temp", "k": 10,
                                                   "close": CLOSE, "at": CLOSE - 590, "book": THIN}


# ------------------------------------------------------------------ row


def rec(b, ticker="KXTEMPMIAH-A", k=10, late=7, close=CLOSE):
    """A recorded book, `late` seconds after its checkpoint (as depth_books.snap writes it)."""
    m = market(ticker, close)
    unit = 60 if m["family"] == "temp" else 3600
    return {"t": ticker, "s": m["series"], "f": m["family"], "k": k, "close": close, "at": close - k * unit + late, "book": b}


def test_row_of_a_thin_book(dbk):
    r = dbk.row(rec(THIN))
    assert {k: r[k] for k in ("t", "s", "f", "k", "close", "side")} == {
        "t": "KXTEMPMIAH-A", "s": "KXTEMPMIAH", "f": "temp", "k": 10, "close": CLOSE, "side": "yes"}
    assert r["at"] == CLOSE - 600 + 7 and r["late"] == pytest.approx(7)
    assert r["ask"] == 0.98 and r["spread"] == 0.02
    assert r["liquid"] is True and r["band"] is True
    assert r["at_ask"] == pytest.approx(4.9)                    # 5 contracts at 98c; the 99c ones are over ask + 0.4c
    assert r["fill"] == pytest.approx({10: 0.49, 25: 0.196, 50: 0.098, 100: 0.049})
    assert r["fill_1c"] == pytest.approx(1.0)                   # one more cent reaches the 99c offers


def test_row_of_a_deep_book(dbk):
    r = dbk.row(rec(DEEP))
    assert r["at_ask"] == pytest.approx(29.4)
    assert r["fill"] == pytest.approx({10: 1.0, 25: 1.0, 50: 29.4 / 50, 100: 29.4 / 100})
    assert r["fill_1c"] == pytest.approx(1.0)


def test_row_of_a_no_favourite_walks_the_yes_bids(dbk):
    r = dbk.row(rec(NO_FAV, ticker="KXAAAGASD-G", k=1, late=30))
    assert (r["side"], r["ask"], r["spread"], r["late"]) == ("no", 0.98, 0.01, pytest.approx(30))
    assert r["f"] == "econ" and r["at"] == CLOSE - 3600 + 30
    assert r["at_ask"] == pytest.approx(24.5)
    assert r["fill"] == pytest.approx({10: 1.0, 25: 0.98, 50: 0.49, 100: 0.245})


@pytest.mark.parametrize("yes_bid,liquid", [(0.95, True), (0.94, False)])     # spreads of 3c and 4c on a 98c ask
def test_liquid_means_a_spread_of_3c_or_less(dbk, yes_bid, liquid):
    assert dbk.row(rec(book(yes=[(yes_bid, 10)], no=[(0.02, 10)])))["liquid"] is liquid


@pytest.mark.parametrize("no_bid,band", [(0.11, False), (0.10, True), (0.001, True)])   # asks of 89c, 90c, 99.9c
def test_the_band_is_90_to_99_9c(dbk, no_bid, band):
    ask = round(1 - no_bid, 4)
    r = dbk.row(rec(book(yes=[(round(ask - 0.01, 4), 10)], no=[(no_bid, 10)])))
    assert r["ask"] == ask and r["band"] is band


def test_no_row_without_a_favourite(dbk):
    assert dbk.row(rec(EMPTY)) is None
    assert dbk.row(rec(book(yes=[(0.40, 1)], no=[(0.40, 1)]))) is None


# ------------------------------------------------------------------ pnl


def test_pnl_at_the_book_buys_only_what_the_book_had(dbk, study):
    fee = study.other_markets.fee
    r = rec(THIN)                                               # $4.90 buys 5 contracts at 98c
    assert dbk.pnl(r, True, 1) == pytest.approx(5 - 4.9 - fee(5.0, 0.98, 1))
    assert dbk.pnl(r, False, 1) == pytest.approx(-4.9 - fee(5.0, 0.98, 1))
    assert dbk.pnl(r, True, 0) == pytest.approx(0.1)


def test_pnl_at_the_book_of_a_smaller_stake(dbk, study):
    c = 4 / 0.98
    assert dbk.pnl(rec(THIN), True, 1, stake=4) == pytest.approx(c - 4 - study.other_markets.fee(c, 0.98, 1))


def test_pnl_is_zero_when_nothing_fills(dbk):
    assert dbk.pnl(rec(book(yes=[(0.96, 40)], no=[(0.02, 0)])), True, 1) == 0.0     # the best offer has 0 contracts


def test_pnl_backtest_is_other_markets_assumption(dbk, study):
    fee = study.other_markets.fee
    c = 10 / 0.984
    assert dbk.pnl_backtest(rec(THIN), True, 1) == pytest.approx(c - 10 - fee(c, 0.984, 1))
    assert dbk.pnl_backtest(rec(THIN), False, 0.5) == pytest.approx(-10 - fee(c, 0.984, 0.5))
    top = rec(book(yes=[(0.998, 10)], no=[(0.001, 10)]))         # a 99.9c ask: priced at 99.9c, not 100.3c
    assert dbk.pnl_backtest(top, True, 1) == pytest.approx(10 / 0.999 - 10 - fee(10 / 0.999, 0.999, 1))


# ------------------------------------------------------------------ summarise


def test_summarise(dbk, study):
    fee = study.other_markets.fee
    records = [
        rec(THIN, "KXTEMPMIAH-A"),                    # a bet: $4.90 of $10 at the ask, all of it with a cent more
        rec(DEEP, "KXTEMPNYCH-B"),                    # a bet: the full $10 and $25
        rec(EMPTY, "KXTEMPAUSH-C"),                   # a snap with no favourite
        rec(WIDE, "KXTEMPDCH-D"),                     # not liquid
        rec(CHEAP, "KXTEMPCHIH-E"),                   # out of the band
        rec(DEEP, "KXTEMPMIAH-A", k=30),              # the first market again, at its other checkpoint
        rec(NO_FAV, "KXTEMPAUSH-F", k=30),            # a NO favourite that won: the market settled NO
        rec(NO_FAV, "KXAAAGASD-G", k=1),              # a bet that hasn't settled
    ]
    results = {"KXTEMPMIAH-A": "yes", "KXTEMPNYCH-B": "no", "KXTEMPDCH-D": "yes", "KXTEMPCHIH-E": "no", "KXTEMPAUSH-F": "no"}
    s = dbk.summarise(records, results, {"KXTEMPNYCH": 0.5})
    assert {("temp", 10), ("temp", 30), ("econ", 1)} <= set(s)
    assert all(v["snaps"] == 0 for k, v in s.items() if k not in {("temp", 10), ("temp", 30), ("econ", 1)})

    t10 = s[("temp", 10)]
    assert (t10["snaps"], t10["bets"], t10["settled"]) == (5, 2, 2)
    assert (t10["full10"], t10["full25"], t10["full50"], t10["full100"], t10["full10_1c"]) == pytest.approx(
        (0.5, 0.5, 0.0, 0.0, 1.0))
    assert t10["median_at_ask"] == pytest.approx(statistics.median([4.9, 29.4]))
    won_thin = 5 - 4.9 - fee(5.0, 0.98, 1)                   # YES won, at the book
    lost_deep = -10 - fee(10 / 0.98, 0.98, 0.5)              # YES lost, its series at half the fee
    assert t10["pnl_book"] == pytest.approx((won_thin + lost_deep) / 2)
    c = 10 / 0.984
    assert t10["pnl_backtest"] == pytest.approx(((c - 10 - fee(c, 0.984, 1)) + (-10 - fee(c, 0.984, 0.5))) / 2)

    t30 = s[("temp", 30)]
    assert (t30["snaps"], t30["bets"], t30["settled"]) == (2, 2, 2)
    won_full = 10 / 0.98 - 10 - fee(10 / 0.98, 0.98, 1)     # both bought $10 at 98c, and both won
    assert t30["pnl_book"] == pytest.approx(won_full)
    assert t30["pnl_backtest"] == pytest.approx(c - 10 - fee(c, 0.984, 1))

    e1 = s[("econ", 1)]
    assert (e1["snaps"], e1["bets"], e1["settled"]) == (1, 1, 0)
    assert e1["full10"] == pytest.approx(1.0) and e1["median_at_ask"] == pytest.approx(24.5)
    assert e1["pnl_book"] is None and e1["pnl_backtest"] is None


def test_a_full_fill_is_99_9_percent_of_the_stake_or_more(dbk):
    just = {"yes_dollars": [["0.9600", "40.00"]], "no_dollars": [["0.0200", "10.1990"]]}    # $9.995 at 98c
    short = {"yes_dollars": [["0.9600", "40.00"]], "no_dollars": [["0.0200", "10.1837"]]}   # $9.98 at 98c
    s = dbk.summarise([rec(just, "KXTEMPMIAH-A"), rec(short, "KXTEMPMIAH-B")], {}, {})
    assert s[("temp", 10)]["full10"] == pytest.approx(0.5)
    assert s[("temp", 10)]["settled"] == 0 and s[("temp", 10)]["pnl_book"] is None


# ------------------------------------------------------------------ get


class Kalshi:
    """requests faked at Session.request: answers from a script, and notes when (on the fake clock) each came."""

    def __init__(self, clock, script):
        self.clock, self.script, self.calls = clock, list(script), []

    def __call__(self, method, url, params=None, **kwargs):     # a class attribute that isn't a function: no self
        self.calls.append((self.clock.t, method.upper(), url, dict(params or {})))
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.ok = status, body, status < 400
        self.text = json.dumps(body)
        self.headers = {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


_quarters = itertools.count(1)
_real_sleep = time.sleep          # kept before any test fakes it


@pytest.fixture
def http(monkeypatch):
    """A fake clock each test (a later quarter hour each time, so no wait is left over from the last one) and a way
    to script Kalshi's answers."""
    clock = Clock(Q + 900 * 10 * next(_quarters) + 100, yield_=_real_sleep)
    monkeypatch.setattr(time, "time", clock.now)
    monkeypatch.setattr(time, "monotonic", clock.now)
    monkeypatch.setattr(time, "sleep", clock.sleep)

    def script(*answers):
        k = Kalshi(clock, answers)
        monkeypatch.setattr(requests.Session, "request", k)
        return k
    script.clock = clock
    return script


def test_get_asks_base_plus_the_path(dbk, http):
    k = http(Resp(200, {"orderbook_fp": DEEP}))
    assert dbk.get("/markets/KXTEMPMIAH-A/orderbook") == {"orderbook_fp": DEEP}
    assert [(m, u) for _, m, u, _ in k.calls] == [("GET", dbk.BASE + "/markets/KXTEMPMIAH-A/orderbook")]


def test_get_passes_the_params(dbk, http):
    k = http(Resp(200, {"markets": [], "cursor": ""}))
    dbk.get("/markets", {"series_ticker": "KXAAAGASD", "status": "open"})
    assert k.calls[0][3] == {"series_ticker": "KXAAAGASD", "status": "open"}


def test_get_is_none_for_a_404_without_asking_again(dbk, http):
    k = http(Resp(404, {"error": "not found"}))
    assert dbk.get("/markets/NOPE") is None
    assert len(k.calls) == 1


def test_get_retries_429_5xx_and_connection_errors(dbk, http):
    k = http(Resp(429), Resp(503), requests.ConnectionError("reset"), Resp(500), Resp(200, {"ok": 1}))
    assert dbk.get("/markets/X") == {"ok": 1}
    times = [t for t, *_ in k.calls]
    assert len(times) == 5 and all(b > a for a, b in zip(times, times[1:]))     # it waited before each retry


@pytest.mark.parametrize("answer", [Resp(500), Resp(429), requests.ConnectionError("down")])
def test_get_gives_up_after_at_least_5_tries(dbk, http, answer):
    k = http(answer)
    with pytest.raises(Exception):
        dbk.get("/markets/X")
    assert len(k.calls) >= 5


def test_get_waits_out_the_quiet_seconds(dbk, http):
    k = http(Resp(200, {"ok": 1}))
    clock = http.clock
    clock.t = clock.t - clock.t % 900 + 500                     # 500 s into the quarter hour: the live bot is ordering
    assert dbk.get("/markets/X") == {"ok": 1}
    at = k.calls[0][0] % 900
    assert not 470 <= at <= 560 and at > 560


def test_get_goes_at_once_outside_the_quiet_seconds(dbk, http):
    k = http(Resp(200, {"ok": 1}))
    start = http.clock.t                                        # 100 s into a quarter hour
    dbk.get("/markets/X")
    assert k.calls[0][0] - start < 1


def test_get_never_asks_more_than_rate_a_second(dbk, http):
    k = http(Resp(200, {"ok": 1}))
    for _ in range(9):
        dbk.get("/markets/X")
    times = [t for t, *_ in k.calls]
    assert all(b - a >= 1 / dbk.RATE - 1e-9 for a, b in zip(times, times[1:]))


def test_get_never_asks_more_than_rate_a_second_across_threads(dbk, http):
    k = http(Resp(200, {"ok": 1}))
    threads = [threading.Thread(target=lambda: [dbk.get("/markets/X") for _ in range(3)]) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    times = sorted(t for t, *_ in k.calls)
    assert len(times) == 12
    assert all(b - a >= 1 / dbk.RATE - 1e-9 for a, b in zip(times, times[1:]))


# ------------------------------------------------------------------ open_markets


def test_open_markets_lists_every_series_and_follows_the_cursor(dbk, monkeypatch):
    asked = []

    def get(path, params=None):
        path = path.replace(dbk.BASE, "")
        assert path == "/markets"
        p = dict(params or {})
        asked.append(p)
        assert len(asked) < 500, "the listing never ended: is the cursor passed on?"
        s = p["series_ticker"]
        if s == "KXTEMPMIAH" and not p.get("cursor"):
            return {"markets": [{"ticker": "KXTEMPMIAH-A", "close_time": iso(CLOSE)},
                                {"ticker": "KXTEMPMIAH-B", "close_time": iso(CLOSE + 3600)}], "cursor": "page2"}
        if s == "KXTEMPMIAH":
            assert p["cursor"] == "page2"
            return {"markets": [{"ticker": "KXTEMPMIAH-C", "close_time": iso(CLOSE + 7200)}], "cursor": ""}
        if s == "KXAAAGASDTX":
            return {"markets": [{"ticker": "KXAAAGASDTX-G", "close_time": "2026-10-13T04:00:00Z"}], "cursor": ""}
        return {"markets": [], "cursor": ""}

    monkeypatch.setattr(dbk, "get", get)
    got = sorted(({k: m[k] for k in ("ticker", "series", "family", "close")} for m in dbk.open_markets()),
                 key=lambda m: m["ticker"])
    gas_close = int(datetime(2026, 10, 13, 4, tzinfo=UTC).timestamp())
    assert got == [{"ticker": "KXAAAGASDTX-G", "series": "KXAAAGASDTX", "family": "econ", "close": gas_close},
                   {"ticker": "KXTEMPMIAH-A", "series": "KXTEMPMIAH", "family": "temp", "close": CLOSE},
                   {"ticker": "KXTEMPMIAH-B", "series": "KXTEMPMIAH", "family": "temp", "close": CLOSE + 3600},
                   {"ticker": "KXTEMPMIAH-C", "series": "KXTEMPMIAH", "family": "temp", "close": CLOSE + 7200}]
    assert all(isinstance(m["close"], int) for m in got)
    assert {p["series_ticker"] for p in asked} == TEMP | ECON
    assert all(p.get("status") == "open" for p in asked)


# ------------------------------------------------------------------ record


S0 = Q + 100


class World:
    """Kalshi for record(): the markets open at the fake clock's time (each from `shows`, if given, until its close),
    each market's book, and tickers whose book requests fail. Notes every request."""

    def __init__(self, dbk, clock, markets, books=None, fail=(), shows=None, path=None):
        self.dbk, self.clock, self.markets = dbk, clock, markets
        self.books, self.fail, self.shows, self.path = books or {}, set(fail), shows or {}, path
        self.calls, self.lines_seen = [], []

    def __call__(self, path, params=None):
        path = path.replace(self.dbk.BASE, "")
        self.calls.append((self.clock.t, path, dict(params or {})))
        if path == "/markets":
            s = params["series_ticker"]
            live = [m for m in self.markets if m["series"] == s and self.shows.get(m["ticker"], 0) <= self.clock.t < m["close"]]
            return {"markets": [{"ticker": m["ticker"], "close_time": iso(m["close"]), "status": "open"} for m in live],
                    "cursor": ""}
        if path.endswith("/orderbook"):
            t = path.split("/")[2]
            if self.path is not None:
                self.lines_seen.append(len(Path(self.path).read_text(encoding="utf-8").splitlines())
                                       if Path(self.path).exists() else 0)
            if t in self.fail:
                raise requests.ConnectionError(f"{t}: down")
            return {"orderbook_fp": self.books.get(t, THIN)}
        raise AssertionError(f"unexpected request {path}")

    def book_reads(self, ticker):
        return [c for c in self.calls if c[1] == f"/markets/{ticker}/orderbook"]


@pytest.fixture
def world(dbk, monkeypatch, tmp_path):
    """record()'s Kalshi and clock; time.sleep fails, so only the injected sleep may wait."""
    def real_sleep(s):
        raise AssertionError("record() must wait with the sleep it was given")
    monkeypatch.setattr(time, "sleep", real_sleep)
    clock = Clock(S0)
    path = tmp_path / "books.jsonl"

    def make(markets, **kw):
        w = World(dbk, clock, markets, path=path, **kw)
        monkeypatch.setattr(dbk, "get", w)
        return w
    make.clock, make.path = clock, path
    return make


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


SCENE = [
    market("KXTEMPMIAH-A", close=S0 + 1800 + 50),     # 30 min checkpoint 50 s after the start, 10 min at +1250
    market("KXTEMPLAXH-L", close=S0 + 1800 - 100),    # 30 min checkpoint 100 s before the start: still read
    market("KXTEMPNYCH-M", close=S0 + 1800 - 200),    # 30 min checkpoint 200 s before the start: missed
    market("KXAAAGASD-G", close=S0 + 7200 + 30),      # 2 h checkpoint at +30, 1 h at +3630
]


def test_record_reads_each_due_book_once_and_writes_a_snap_line(dbk, world):
    w = world(SCENE, books={"KXAAAGASD-G": NO_FAV, "KXTEMPMIAH-A": DEEP})
    dbk.record(path=str(world.path), until=S0 + 4000, now=world.clock.now, sleep=world.clock.sleep)
    got = lines(world.path)
    assert sorted((x["t"], x["k"]) for x in got) == sorted([
        ("KXTEMPMIAH-A", 30), ("KXTEMPMIAH-A", 10), ("KXTEMPLAXH-L", 30), ("KXTEMPLAXH-L", 10),
        ("KXTEMPNYCH-M", 10), ("KXAAAGASD-G", 2), ("KXAAAGASD-G", 1)])
    by = {m["ticker"]: m for m in SCENE}
    for x in got:
        m = by[x["t"]]
        cp = dict(dbk.checkpoints(m["family"], m["close"]))[x["k"]]
        assert x == dbk.snap(m, x["k"], x["book"], x["at"])
        assert cp <= x["at"] < cp + dbk.GRACE
        if cp >= S0:
            assert x["at"] - cp <= 5 + 1e-6                     # read within a few seconds of its checkpoint
        assert x["book"] == {"KXAAAGASD-G": NO_FAV, "KXTEMPMIAH-A": DEEP}.get(x["t"], THIN)
    assert len(w.book_reads("KXTEMPNYCH-M")) == 1               # only its 10 min book: the 30 min one was missed


def test_record_flushes_each_line_at_once(dbk, world):
    w = world(SCENE)
    dbk.record(path=str(world.path), until=S0 + 4000, now=world.clock.now, sleep=world.clock.sleep)
    assert w.lines_seen == list(range(len(w.lines_seen)))      # every earlier book already on disk at each new read
    assert len(w.lines_seen) == 7


def test_record_sleeps_at_most_5_seconds_and_stops_at_until(dbk, world):
    world(SCENE)
    dbk.record(path=str(world.path), until=S0 + 4000, now=world.clock.now, sleep=world.clock.sleep)
    assert world.clock.sleeps and max(world.clock.sleeps) <= 5 + 1e-9
    assert S0 + 4000 <= world.clock.t < S0 + 4000 + 6


def test_record_runs_a_week_by_default(dbk, world):
    world([])
    dbk.record(path=str(world.path), now=world.clock.now, sleep=world.clock.sleep)
    assert S0 + 7 * 86400 <= world.clock.t < S0 + 7 * 86400 + 6


def test_record_resumes_without_reading_a_book_twice(dbk, world):
    first = dbk.snap(SCENE[0], 30, DEEP, S0 + 51)
    world.path.write_text(json.dumps(first) + "\n", encoding="utf-8")
    w = world(SCENE)
    dbk.record(path=str(world.path), until=S0 + 4000, now=world.clock.now, sleep=world.clock.sleep)
    got = lines(world.path)
    assert got[0] == first                                       # kept, and appended to
    assert [(x["t"], x["k"]) for x in got].count(("KXTEMPMIAH-A", 30)) == 1
    assert len(w.book_reads("KXTEMPMIAH-A")) == 1                # only its 10 min book
    assert len(got) == 7


def test_a_failed_book_is_logged_and_skipped(dbk, world, capsys):
    world(SCENE, fail={"KXTEMPLAXH-L"})
    dbk.record(path=str(world.path), until=S0 + 4000, now=world.clock.now, sleep=world.clock.sleep)
    got = lines(world.path)
    assert "KXTEMPLAXH-L" not in {x["t"] for x in got}
    assert len(got) == 5                                         # everything else still read
    out = capsys.readouterr()
    log = Path(dbk.LOG).read_text(encoding="utf-8") if Path(dbk.LOG).exists() else ""
    assert "KXTEMPLAXH-L" in log + out.out + out.err


def test_record_relists_every_refresh_and_reads_new_markets(dbk, world):
    new = market("KXTEMPCHIH-N", close=S0 + 700 + 1800)          # listed from +400; 30 min checkpoint at +700
    w = world(SCENE + [new], shows={"KXTEMPCHIH-N": S0 + 400})
    dbk.record(path=str(world.path), until=S0 + 1000, now=world.clock.now, sleep=world.clock.sleep)
    assert ("KXTEMPCHIH-N", 30) in {(x["t"], x["k"]) for x in lines(world.path)}
    rounds = [t for t, p, q in w.calls if p == "/markets" and q.get("series_ticker") == "KXTEMPMIAH"]
    assert len(rounds) == 4                                      # at the start, then about +300, +600, +900
    assert all(b - a >= dbk.REFRESH - 1e-6 for a, b in zip(rounds, rounds[1:]))


# ------------------------------------------------------------------ results


def test_results_asks_each_market_once_and_caches_the_settled_ones(dbk, monkeypatch, tmp_path):
    state = {"A": ("finalized", "yes"), "B": ("finalized", "no"), "C": ("active", ""), "E": None}
    asked = []

    def get(path, params=None):
        t = path.replace(dbk.BASE, "").split("/")[2]
        asked.append(t)
        s = state.get(t)
        return None if s is None else {"market": {"ticker": t, "status": s[0], "result": s[1]}}

    monkeypatch.setattr(dbk, "get", get)
    cache = tmp_path / "results.json"
    assert dbk.results(["A", "B", "C", "E"], cache=str(cache)) == {"A": "yes", "B": "no"}
    assert sorted(asked) == ["A", "B", "C", "E"] and cache.exists()

    asked.clear()
    state.update({"C": ("finalized", "yes"), "D": ("finalized", "no")})
    assert dbk.results(["A", "B", "C", "D"], cache=str(cache)) == {"A": "yes", "B": "no", "C": "yes", "D": "no"}
    assert sorted(asked) == ["C", "D"]                           # A and B came from the cache

    asked.clear()
    assert dbk.results(["A"], cache=str(cache)) == {"A": "yes"}
    assert asked == []


# ------------------------------------------------------------------ main


def called_until(args, kwargs):
    return kwargs["until"] if "until" in kwargs else args[1] if len(args) > 1 else None


def test_main_record_for_some_days(dbk, monkeypatch):
    calls = []
    monkeypatch.setattr(dbk, "record", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(sys, "argv", ["depth_books.py", "record", "2"])
    dbk.main()
    [(args, kwargs)] = calls
    assert called_until(args, kwargs) == pytest.approx(time.time() + 2 * 86400, abs=120)


def test_main_record_defaults_to_a_week(dbk, monkeypatch):
    calls = []
    monkeypatch.setattr(dbk, "record", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(sys, "argv", ["depth_books.py", "record"])
    dbk.main()
    [(args, kwargs)] = calls
    until = called_until(args, kwargs)
    assert until is None or until == pytest.approx(time.time() + 7 * 86400, abs=120)


def test_main_report_reads_the_books_and_their_results(dbk, study, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other_markets.json").write_text((study.dir / "other_markets.json").read_text(encoding="utf-8"),
                                                 encoding="utf-8")
    recs = [rec(DEEP, "KXTEMPMIAH-A"), rec(THIN, "KXTEMPNYCH-B"), rec(NO_FAV, "KXAAAGASD-G", k=1)]
    (tmp_path / dbk.OUT).write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    asked = []

    def get(path, params=None):
        t = path.replace(dbk.BASE, "").split("/")[2]
        asked.append(t)
        return {"market": {"ticker": t, "status": "finalized", "result": "yes"}}

    monkeypatch.setattr(dbk, "get", get)
    monkeypatch.setattr(sys, "argv", ["depth_books.py", "report"])
    dbk.main()
    out = capsys.readouterr().out
    assert set(asked) == {"KXTEMPMIAH-A", "KXTEMPNYCH-B", "KXAAAGASD-G"}
    assert "temp" in out and "econ" in out
