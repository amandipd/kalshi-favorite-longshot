"""Fast entry on paper (the "fast shadow"): what an order sent at minute 8 exactly would have bought, measured without
real money.

Terms: the mark is minute 8 exactly, 480.0 s into the window on Kalshi's clock. The live bot's orders land a median
2.4 s after it, by when other traders have taken much of what was offered at its limit. A background thread, the reader
(fast_entry.MarkReader), reads every order book of the window at the mark; books(window_open) hands the bot
{ticker: (raw book, when it answered on Kalshi's clock)}. Once the window's real orders are out (and after the paper +1c
rows), fast_shadow() pairs each real order with a paper twin: an instant immediate-or-cancel order on the mark's book.
Its ask is the cheapest offer at the mark on the real order's side (1 - the other side's best bid, kept as `seen`), its
limit comes from limit_for (the live rule), and it buys the offers up to that limit, cheapest first, in whole contracts,
up to the contracts the real order asked for: the **extra**, their cost and their share of Kalshi's taker fee
(unrounded). The row goes in the `shadow` table as kind 'fast', beside what the real order filled (its bet's contracts)
and the **lag** (how many seconds after minute 8 the mark's book answered). When the market settles, the row gets its
P&L as if those contracts had been bought.

What must hold: a new Bot has no reader, and only main() --live gives it one, through start_reader(), which imports
fast_entry inside itself (bot.py must still load in a folder holding only bot.py and kalshi.py); edge_series() is the
traded groups' series, which window_markets lists and the reader reads; fast_shadow() runs once a window, right after
shadow(), with the same reads; no reader or no reads records nothing; a missing, unreadable or garbled book, or a reader
that raises, gives an 'unread' row and never an exception; an empty side, or an ask outside 92-99.9c, gives an 'open'
row that bought nothing; a row is never overwritten or committed here, and no order, bet, fill or decision is touched;
settle() settles 'fast' rows like any other. conftest.py swaps start_reader for a stub that does nothing unless a test
is marked real_reader, so no test starts a thread that asks NTP servers or Kalshi. Nothing here touches the network or
an account.

    python -m pytest tests/test_fast_shadow.py -q
"""
import ast
import inspect
import os
import sqlite3
import sys
import types

import pytest

from kalshi_bot import bot
from kalshi_bot import fast_entry
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, start_ledger
from test_cli import NOW, cli, exits, out  # noqa: F401 (cli is a fixture)
from test_day_drop import open_bet
from test_flow import BTC, ETH, GOLD, NO98, YES96, Settling, bets, book, bot_for, mk, slept  # noqa: F401 (slept: no sleeps)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around.
    The live limit at the ask it saw (LIMIT_UP 0), as it was until Oct 20, so the paper +1c rows run beside the fast ones;
    the live +1c is test_with_limit_up_set_the_paper_limit_follows_limit_for's."""
    monkeypatch.setattr(bot, "LIMIT_UP", 0.0)
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


MARK = W + bot.MINUTE * 60     # minute 8 exactly: 480.0 s into the window, on Kalshi's clock
IGNORED = object()             # a read's fifth item (shadow()'s book read, a future): fast_shadow never looks at it


@pytest.fixture(autouse=True)
def fast_entry_off(monkeypatch):
    """The paper fast entry as it runs while live fast entry is off (fast_entry.START None): since Oct 14 fast_entry
    ships with START set, and then main() starts no reader and a fast window pairs its orders with its own books at
    the mark instead (test_fast_live.py)."""
    monkeypatch.setattr(fast_entry, "START", None)


def raw(yes=(), no=()):
    """A book as GET /markets/{t}/orderbook answers it: YES bids and NO bids, [price, size] as strings."""
    return {"orderbook_fp": {"yes_dollars": [[f"{p:.4f}", f"{q:g}"] for p, q in yes],
                             "no_dollars": [[f"{p:.4f}", f"{q:g}"] for p, q in no]}}


# The books at the mark. Buying YES walks the NO bids (YES offered at 1 - each): YES at 96c x2 (the ask at the mark),
# 96.5c x1.9 (one whole contract), 97c x5 and 97.1c x5.
YES_MARK = raw(yes=[(0.95, 100)], no=[(0.04, 2), (0.035, 1.9), (0.03, 5), (0.029, 5)])
# Buying NO walks the YES bids: NO at 98c x3 (the ask at the mark), 98.5c x4 and 99c x100.
NO_MARK = raw(yes=[(0.02, 3), (0.015, 4), (0.01, 100)], no=[(0.97, 40)])


def at_mark(answer, after=0.25):
    """A book the reader read: (the raw book, when it answered on Kalshi's clock), `after` seconds past minute 8."""
    return answer, MARK + after


class Reader:
    """Stands in for fast_entry.MarkReader: books(window_open) gives a copy of the books the test put in `store` (or
    raises `raises`), and notes each window it was asked for."""

    def __init__(self, books=None, raises=None):
        self.store, self.raises, self.calls = dict(books or {}), raises, []

    def books(self, window_open):
        self.calls.append(window_open)
        if self.raises is not None:
            raise self.raises
        return dict(self.store)


def paper_bot(db, books=None, raises=None, live=True):
    """A bot with the catalog loaded and a reader holding these books."""
    b = bot_for(FakeKalshi(), db, live)
    b.reader = Reader(books, raises)
    return b


def kalshi_fee(levels, mult=1.0):
    """Kalshi's taker fee on these (contracts, price) levels, unrounded: 0.07 x mult x q x p x (1 - p) each."""
    return sum(0.07 * mult * q * p * (1 - p) for q, p in levels)


def fee_of(levels, mult=1.0):
    return pytest.approx(kalshi_fee(levels, mult), rel=1e-9, abs=1e-12)


def rows(db, kind="fast"):
    return {r["ticker"]: dict(r) for r in db.execute("SELECT * FROM shadow WHERE kind=? ORDER BY id", (kind,))}


def row(db, ticker, kind="fast"):
    return rows(db, kind)[ticker]


def fields(r):
    """A row without its id."""
    return {k: v for k, v in r.items() if k != "id"}


def expect(m, side, asked, filled, seen, limit, lag, extra, cost, fee, status):
    """The whole 'fast' row for this market, as fast_shadow writes it at ENTRY for the window W, before it settles."""
    return {"kind": "fast", "ticker": m["ticker"], "ts": ENTRY, "window_open": W, "close_ts": m["close"],
            "series": m["series"], "side": side, "seen": seen, "limit_price": limit, "asked": asked, "filled": filled,
            "lag": lag, "extra": extra, "cost": cost, "fee": fee, "status": status, "result": None, "pnl": None,
            "settled_ts": None}


def committed_rows(path):
    """What another program (the dashboard) sees in the ledger: only what has been committed."""
    other = sqlite3.connect(path)
    try:
        return other.execute("SELECT COUNT(*) FROM shadow").fetchone()[0]
    finally:
        other.close()


def snapshot(db):
    return {t: [tuple(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY id")] for t in ("bets", "orders", "decisions", "fills")}


class Watch:
    """Stands in for Kalshi where nothing should be called: notes any call."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a, **kw: self.calls.append(name)


# ------------------------------------------------------------------ the reader's slot and the series it reads
@pytest.mark.parametrize("live, halts", [(True, True), (False, True), (False, False)])
def test_a_new_bot_has_no_reader(env, live, halts):
    """Only main() gives it one, and only for --live: a dry run, a paper account and every test's bot have none."""
    assert bot.Bot(FakeKalshi(), env, live, halts=halts).reader is None


def test_edge_series_are_the_traded_groups_series_in_the_catalogs_order(env):
    b = bot.Bot(FakeKalshi(), env, True)
    b.universe = {"KXEURUSD15M": {"group": "fx", "fee": 1.0}, "KXWTI15M": {"group": "energy", "fee": 1.0},
                  "KXBTC15M": {"group": "crypto", "fee": 1.0}, "KXCRYPTOLEAD15M": {"group": "coin race", "fee": 1.0},
                  "KXGOLD15M": {"group": "metals", "fee": 1.0}, "KXINX15M": {"group": "stock index", "fee": 1.0}}
    assert b.edge_series() == ["KXWTI15M", "KXBTC15M", "KXGOLD15M"]


def test_edge_series_is_empty_before_the_catalog_loads(env):
    assert bot.Bot(FakeKalshi(), env, True).edge_series() == []


def test_edge_series_follows_the_catalog_as_it_changes(env):
    """The reader asks for it every window, so a series the hourly catalog adds or drops shows up there at once."""
    b = bot_for(FakeKalshi(), env, True)
    assert b.edge_series() == ["KXBTC15M", "KXGOLD15M", "KXETH15M"]      # not the Coin Race series
    b.universe["KXSOL15M"] = {"group": "crypto", "fee": 1.0}
    del b.universe["KXGOLD15M"]
    assert b.edge_series() == ["KXBTC15M", "KXETH15M", "KXSOL15M"]


class Listing(FakeKalshi):
    """FakeKalshi noting each series it was asked to list."""

    def __init__(self):
        super().__init__()
        self.listed = []

    def markets(self, **p):
        if "series_ticker" in p:
            self.listed.append(p["series_ticker"])
        return super().markets(**p)


def test_window_markets_lists_the_edge_series_as_before(env):
    fake = Listing()
    b = bot_for(fake, env, True)
    got = b.window_markets(W)
    assert sorted(fake.listed) == sorted(b.edge_series()) == ["KXBTC15M", "KXETH15M", "KXGOLD15M"]
    assert [m["ticker"] for m in got] == [BTC, GOLD, ETH]              # in the catalog's order
    assert all(m["book"] is not None for m in got)


def test_window_markets_lists_whatever_edge_series_says(env):
    """window_markets asks edge_series(), so the bot and its reader can never disagree on which markets to read."""
    fake = Listing()
    b = bot_for(fake, env, True)
    b.edge_series = lambda: ["KXGOLD15M"]
    assert [m["ticker"] for m in b.window_markets(W)] == [GOLD] and fake.listed == ["KXGOLD15M"]


# ------------------------------------------------------------------ when it runs
def spy_on_both(b, fake):
    """Note each call to the bot's shadow() (which still runs) and fast_shadow() (which doesn't), with how many real
    orders had gone out by then."""
    events, real_shadow = [], b.shadow

    def shadow(now, window_open, reads):
        events.append(("shadow", now, window_open, list(reads), len(fake.orders)))
        return real_shadow(now, window_open, reads)

    def fast_shadow(now, window_open, reads):
        events.append(("fast", now, window_open, list(reads), len(fake.orders)))
    b.shadow, b.fast_shadow = shadow, fast_shadow
    return events


@pytest.mark.parametrize("live, tied_up, sent", [
    (True, False, [(BTC, "yes", 0.96, 3), (GOLD, "no", 0.98, 3)]),    # two real orders out
    (False, False, []),                                                # a dry run: no reads
    (True, True, []),                                                  # live, but every order skipped for want of cash
])
def test_fast_shadow_runs_once_right_after_shadow_with_the_same_reads(env, live, tied_up, sent):
    if tied_up:
        open_bet(env, "KXBTC15M-OLD", W - 900, contracts=200, cost=199.0)   # 95c of cash left: not enough for 3 at 96c
    fake = FakeKalshi()
    b = bot_for(fake, env, live)
    events = spy_on_both(b, fake)
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert [e[0] for e in events] == ["shadow", "fast"]
    assert events[1][1:] == events[0][1:]                  # the same now, window, reads, and every order already out
    _, now, window_open, reads, orders_out = events[1]
    assert (now, window_open, orders_out) == (ENTRY, W, len(sent))
    assert [(r[0]["ticker"], r[1], r[2], r[3]) for r in reads] == sent


def test_a_window_that_stops_early_runs_neither(env):
    """A halted window logs its favourites and returns before any order: no shadow(), so no fast_shadow() either."""
    bot.set_halt(ENTRY - 60, "checking")
    fake = FakeKalshi()
    b = bot_for(fake, env, True)
    events = spy_on_both(b, fake)
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert events == [] and decisions(env)[BTC][0] == "halted"


# ------------------------------------------------------------------ no reader, no reads: nothing
def test_with_no_reader_a_live_window_writes_no_fast_rows(env):
    """Only the paper +1c rows: a bot with no reader (every test's bot, a dry run, a paper account, or a live bot
    started without fast_entry.py beside it)."""
    bot_for(FakeKalshi(), env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert sorted(rows(env, "limitup")) == [BTC, GOLD] and rows(env) == {}


def test_fast_shadow_with_no_reader_does_nothing(env):
    b = bot_for(FakeKalshi(), env, True)
    b.k = Watch()
    before = env.total_changes
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED)])
    assert env.total_changes == before and not env.in_transaction and b.k.calls == [] and rows(env) == {}


def test_fast_shadow_with_no_reads_does_nothing_and_never_asks_the_reader(env):
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    before = env.total_changes
    b.fast_shadow(ENTRY, W, [])
    assert b.reader.calls == [] and env.total_changes == before and not env.in_transaction


def test_a_dry_run_with_a_reader_records_nothing(env):
    """A dry run sends no real orders, so there's nothing to pair (and main() never gives one a reader anyway)."""
    b = paper_bot(env, {BTC: at_mark(YES_MARK), GOLD: at_mark(NO_MARK)}, live=False)
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert sorted(bets(env)) == [BTC, GOLD] and b.reader.calls == [] and rows(env) == {}


# ------------------------------------------------------------------ what an instant order at the mark would have bought
def test_a_yes_order_is_paired_with_what_an_instant_order_at_the_mark_would_have_bought(env):
    """The real order: 3 at the 96c it saw, of which 1 filled. At the mark YES was offered at 96c x2 (the best NO bid
    4c), then 96.5c and 97c: an instant order with the live limit (the ask itself, LIMIT_UP being 0) gets the 2 at 96c.
    The book answered a quarter of a second after minute 8 (the bot itself decided 5 s after it). The fee is Kalshi's
    unrounded: on a real order it would be rounded up to the cent."""
    open_bet(env, BTC, W, contracts=1, cost=0.96, fee=0.01)
    b = paper_bot(env, {BTC: at_mark(YES_MARK, 0.25)})
    m = mk(BTC, YES96)
    b.fast_shadow(ENTRY, W, [(m, "yes", 0.96, 3, IGNORED)])
    r = row(env, BTC)
    assert fields(r) == expect(m, "yes", asked=3, filled=1, seen=0.96, limit=0.96, lag=pytest.approx(0.25), extra=2,
                               cost=pytest.approx(1.92), fee=fee_of([(2, 0.96)]), status="open")
    assert r["fee"] < bot.taker_fee(2, 0.96)
    assert b.reader.calls == [W]                           # the window's books, asked for once


def test_a_no_order_with_no_bet_is_paired_too(env):
    """The real order: 5 NO at 98c, nothing filled (so no bet: filled is 0). At the mark NO was offered at 98c x3 (the
    best YES bid 2c), then 98.5c and 99c: the instant order gets the 3 at 98c."""
    b = paper_bot(env, {GOLD: at_mark(NO_MARK, 0.125)})
    m = mk(GOLD, NO98)
    b.fast_shadow(ENTRY, W, [(m, "no", 0.98, 5, IGNORED)])
    assert fields(row(env, GOLD)) == expect(m, "no", asked=5, filled=0.0, seen=0.98, limit=0.98, lag=pytest.approx(0.125),
                                            extra=3, cost=pytest.approx(2.94), fee=fee_of([(3, 0.98)]), status="open")


def test_every_read_gets_its_own_row_from_one_look_at_the_books(env):
    open_bet(env, GOLD, W, contracts=2, cost=1.96, side="no")
    b = paper_bot(env, {BTC: at_mark(YES_MARK, 0.25), GOLD: at_mark(NO_MARK, 1.5)})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 5, IGNORED)])
    got = {t: (r["side"], r["asked"], r["filled"], r["seen"], r["extra"], r["lag"]) for t, r in rows(env).items()}
    assert got == {BTC: ("yes", 3, 0, 0.96, 2, 0.25), GOLD: ("no", 5, 2, 0.98, 3, 1.5)}
    assert b.reader.calls == [W]


def test_the_paper_order_asks_for_every_contract_the_real_one_did(env):
    """Unlike the +1c (which only counts what the real order missed), the instant order is a whole order of its own: 1
    of the real 3 filled, and at the mark all 3 were there to take."""
    open_bet(env, BTC, W, contracts=1, cost=0.96, fee=0.01)
    b = paper_bot(env, {BTC: at_mark(raw(no=[(0.04, 5)]))})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED)])
    r = row(env, BTC)
    assert (r["asked"], r["filled"], r["extra"]) == (3, 1, 3) and r["cost"] == pytest.approx(2.88)


@pytest.mark.parametrize("side, answer, seen, extra, cost", [
    ("yes", raw(no=[(0.05, 4), (0.04, 10)]), 0.95, 3, 3 * 0.95),   # cheaper at the mark than when it decided: 95c, not 96c
    ("yes", raw(no=[(0.04, 1), (0.03, 9)]), 0.96, 1, 0.96),         # the same 96c, with only 1 left there
    ("yes", raw(no=[(0.03, 9)]), 0.97, 3, 3 * 0.97),                # dearer at the mark: 97c, still in the band
    ("yes", raw(no=[(0.03, 5), (0.04, 2)]), 0.96, 2, 2 * 0.96),     # the best bid is the highest, whatever order they came in
    ("yes", raw(no=[(0.07, 5)]), 0.93, 3, 3 * 0.93),                # 1 - 7c, rounded to 93c, not 92.99999...
    ("no", raw(yes=[(0.01, 5), (0.02, 1)]), 0.98, 1, 0.98),
    ("no", raw(yes=[(0.03, 9)], no=[(0.5, 1)]), 0.97, 3, 3 * 0.97),
])
def test_the_ask_and_the_limit_are_the_marks_own_not_the_ones_the_real_order_saw(env, side, answer, seen, extra, cost):
    t, m, top = (BTC, mk(BTC, YES96), 0.96) if side == "yes" else (GOLD, mk(GOLD, NO98), 0.98)
    b = paper_bot(env, {t: at_mark(answer)})
    b.fast_shadow(ENTRY, W, [(m, side, top, 3, IGNORED)])
    r = row(env, t)
    assert (r["seen"], r["limit_price"], r["extra"], r["status"]) == (seen, seen, extra, "open")
    assert r["cost"] == pytest.approx(cost, abs=1e-9)


@pytest.mark.parametrize("no_bids, extra, cost", [
    ([(0.04, 2.9)], 2, 2 * 0.96),        # 2 whole contracts of the 2.9
    ([(0.04, 0.5)], 0, 0.0),             # half a contract: none, though the side isn't empty
    ([(0.04, 7.99)], 7, 7 * 0.96),
])
def test_it_buys_whole_contracts_only(env, no_bids, extra, cost):
    b = paper_bot(env, {BTC: at_mark(raw(no=no_bids))})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 10, IGNORED)])
    r = row(env, BTC)
    assert (r["seen"], r["limit_price"], r["extra"], r["status"]) == (0.96, 0.96, extra, "open")
    assert r["cost"] == pytest.approx(cost, abs=1e-9) and r["fee"] == fee_of([(extra, 0.96)])


@pytest.mark.parametrize("side, top, answer, c, limit, taken", [
    # every offer up to 97c, cheapest first: 2 at 96c, 1 of the 1.9 at 96.5c, the 5 at 97c; not the 97.1c ones
    ("yes", 0.96, YES_MARK, 10, 0.97, [(2, 0.96), (1, 0.965), (5, 0.97)]),
    ("yes", 0.96, YES_MARK, 5, 0.97, [(2, 0.96), (1, 0.965), (2, 0.97)]),      # stops at the contracts asked for
    ("no", 0.98, NO_MARK, 10, 0.99, [(3, 0.98), (4, 0.985), (3, 0.99)]),
    # an ask of 99.5c: the limit is capped at 99.9c (not 100.5c); 99.5c, 99.7c and 99.9c taken, 99.95c not
    ("yes", 0.995, raw(no=[(0.005, 1), (0.003, 1), (0.001, 1), (0.0005, 5)]), 10, 0.999, [(1, 0.995), (1, 0.997), (1, 0.999)]),
])
def test_with_limit_up_set_the_paper_limit_follows_limit_for(env, monkeypatch, side, top, answer, c, limit, taken):
    """With the +1c live (LIMIT_UP = 0.01, since Oct 20), the instant order's limit follows: limit_for is the one live
    rule."""
    monkeypatch.setattr(bot, "LIMIT_UP", 0.01)
    t, m = (BTC, mk(BTC, YES96)) if side == "yes" else (GOLD, mk(GOLD, NO98))
    b = paper_bot(env, {t: at_mark(answer)})
    b.fast_shadow(ENTRY, W, [(m, side, top, c, IGNORED)])
    r = row(env, t)
    assert (r["limit_price"], r["extra"], r["status"]) == (limit, sum(q for q, _ in taken), "open")
    assert r["cost"] == pytest.approx(sum(q * p for q, p in taken), abs=1e-9) and r["fee"] == fee_of(taken)


def test_the_paper_limit_comes_from_limit_for_itself(env, monkeypatch):
    """limit_for stays the one place the live limit is set: whatever rule it holds, the paper limit is its answer for
    the ask at the mark."""
    asked = []
    monkeypatch.setattr(bot, "limit_for", lambda top: (asked.append(top), round(top + 0.005, 4))[1])
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 10, IGNORED)])
    r = row(env, BTC)
    assert asked == [0.96] and r["limit_price"] == 0.965
    assert r["extra"] == 3 and r["cost"] == pytest.approx(2 * 0.96 + 0.965)     # 2 at 96c, 1 at 96.5c; not 97c


def test_the_fee_uses_the_series_fee_multiplier(env):
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    b.universe["KXBTC15M"]["fee"] = 0.5
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED)])
    assert row(env, BTC)["fee"] == fee_of([(2, 0.96)], mult=0.5)


def test_a_series_missing_from_the_catalog_pays_the_full_fee(env):
    new = "KXNEW15M-A"
    b = paper_bot(env, {new: at_mark(YES_MARK)})
    b.fast_shadow(ENTRY, W, [(mk(new, None), "yes", 0.96, 3, IGNORED)])
    r = row(env, new)
    assert (r["series"], r["extra"]) == ("KXNEW15M", 2) and r["fee"] == fee_of([(2, 0.96)])


# ------------------------------------------------------------------ an empty side, or an ask outside the band
@pytest.mark.parametrize("side, answer", [
    ("yes", raw(yes=[(0.95, 10)], no=[])),                            # nobody selling YES (no NO bids)
    ("no", raw(yes=[], no=[(0.97, 40)])),                             # nobody selling NO (no YES bids)
    ("yes", {"orderbook_fp": {}}),                                    # a book with nothing in it
    ("no", {"orderbook_fp": {"yes_dollars": None, "no_dollars": None}}),
])
def test_an_empty_side_at_the_mark_bought_nothing(env, side, answer):
    """An instant order would have bought nothing: measured ('open'), with no ask and no limit."""
    t, m, top = (BTC, mk(BTC, YES96), 0.96) if side == "yes" else (GOLD, mk(GOLD, NO98), 0.98)
    b = paper_bot(env, {t: at_mark(answer, 0.125)})
    b.fast_shadow(ENTRY, W, [(m, side, top, 3, IGNORED)])
    assert fields(row(env, t)) == expect(m, side, asked=3, filled=0.0, seen=None, limit=None, lag=pytest.approx(0.125),
                                         extra=0.0, cost=0.0, fee=0.0, status="open")


@pytest.mark.parametrize("side, answer, seen", [
    ("yes", raw(yes=[], no=[(0.04, 5)]), 0.96),     # only offers to sell YES: all a YES order needs
    ("no", raw(yes=[(0.02, 5)], no=[]), 0.98),
])
def test_a_one_sided_book_is_enough_when_its_the_orders_side(env, side, answer, seen):
    t, m = (BTC, mk(BTC, YES96)) if side == "yes" else (GOLD, mk(GOLD, NO98))
    b = paper_bot(env, {t: at_mark(answer)})
    b.fast_shadow(ENTRY, W, [(m, side, seen, 3, IGNORED)])
    r = row(env, t)
    assert (r["seen"], r["limit_price"], r["extra"], r["status"]) == (seen, seen, 3, "open")
    assert r["cost"] == pytest.approx(3 * seen)


@pytest.mark.parametrize("side, answer, seen", [
    ("yes", raw(yes=[(0.10, 5)], no=[(0.15, 5)]), 0.85),
    ("yes", raw(no=[(0.0801, 5)]), 0.9199),          # a hundredth of a cent under 92c
    ("yes", raw(no=[(0.10, 5)]), 0.90),              # 90c: out since the floor rose to 92c on Oct 14
    ("yes", raw(no=[(0.0005, 5)]), 0.9995),          # over 99.9c
    ("no", raw(yes=[(0.15, 5)]), 0.85),
    ("no", raw(yes=[(0.081, 5)]), 0.919),            # 91.9c
    ("no", raw(yes=[(0.0004, 5)]), 0.9996),
])
def test_an_ask_outside_92_to_99_9c_at_the_mark_bought_nothing(env, side, answer, seen):
    """At the mark the bot's rule wouldn't have bought it: the ask is kept, with no limit and nothing bought."""
    t, m, top = (BTC, mk(BTC, YES96), 0.96) if side == "yes" else (GOLD, mk(GOLD, NO98), 0.98)
    b = paper_bot(env, {t: at_mark(answer, 0.125)})
    b.fast_shadow(ENTRY, W, [(m, side, top, 3, IGNORED)])
    assert fields(row(env, t)) == expect(m, side, asked=3, filled=0.0, seen=seen, limit=None, lag=pytest.approx(0.125),
                                         extra=0.0, cost=0.0, fee=0.0, status="open")


@pytest.mark.parametrize("side, answer, seen", [
    ("yes", raw(no=[(0.08, 5)]), 0.92),
    ("yes", raw(no=[(0.001, 5)]), 0.999),
    ("no", raw(yes=[(0.08, 5)]), 0.92),
    ("no", raw(yes=[(0.001, 5)]), 0.999),
])
def test_the_bands_ends_are_in_it(env, side, answer, seen):
    t, m = (BTC, mk(BTC, YES96)) if side == "yes" else (GOLD, mk(GOLD, NO98))
    b = paper_bot(env, {t: at_mark(answer)})
    b.fast_shadow(ENTRY, W, [(m, side, seen, 3, IGNORED)])
    r = row(env, t)
    assert (r["seen"], r["limit_price"], r["extra"], r["status"]) == (seen, seen, 3, "open")
    assert r["cost"] == pytest.approx(3 * seen)


# ------------------------------------------------------------------ books it couldn't read
def test_a_market_missing_from_the_marks_books_gives_an_unread_row(env):
    """The reader didn't list it, or didn't get its book: nothing at all is known about it at the mark."""
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    m = mk(GOLD, NO98)
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (m, "no", 0.98, 3, IGNORED)])
    assert fields(row(env, GOLD)) == expect(m, "no", asked=3, filled=0.0, seen=None, limit=None, lag=None, extra=None,
                                            cost=None, fee=None, status="unread")
    assert row(env, BTC)["status"] == "open" and b.reader.calls == [W]


def test_a_window_the_reader_never_read_gives_every_order_an_unread_row(env):
    """books() of a window it didn't read (it started late, or listed nothing) is {}."""
    b = paper_bot(env, {})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 3, IGNORED)])
    assert {t: (r["status"], r["lag"], r["seen"], r["extra"]) for t, r in rows(env).items()} == \
        {BTC: ("unread", None, None, None), GOLD: ("unread", None, None, None)}


@pytest.mark.parametrize("answer", [
    None,                                                          # the read failed (MarkReader's None)
    {}, {"orderbook_fp": None}, {"error": {"code": "not_found"}},  # parse_book finds no book in it
    "gateway timeout", ["not", "a", "dict"], {"orderbook_fp": "abc"},   # parsing it raises
    {"orderbook_fp": {"yes_dollars": [["abc", "1"]]}},             # a price that isn't a number
    {"orderbook_fp": {"no_dollars": [["0.04", "lots"]]}},          # a size that isn't one
    {"orderbook_fp": {"no_dollars": [["0.04"]]}},                  # a level with no size
])
def test_a_book_it_cant_read_gives_an_unread_row_that_keeps_its_lag(env, answer):
    """When the answer came is still known; what it would have bought isn't. The next order is still measured."""
    b = paper_bot(env, {BTC: at_mark(answer, 0.25), GOLD: at_mark(NO_MARK)})
    m = mk(BTC, YES96)
    b.fast_shadow(ENTRY, W, [(m, "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 3, IGNORED)])
    assert fields(row(env, BTC)) == expect(m, "yes", asked=3, filled=0.0, seen=None, limit=None, lag=pytest.approx(0.25),
                                           extra=None, cost=None, fee=None, status="unread")
    assert row(env, GOLD)["status"] == "open"


@pytest.mark.parametrize("entry", [None, (), ("x",), (YES_MARK,), (YES_MARK, MARK, "more"), "xy", 7])
def test_a_garbled_entry_from_the_reader_gives_an_unread_row_never_an_exception(env, entry):
    b = paper_bot(env, {BTC: entry, GOLD: at_mark(NO_MARK)})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 3, IGNORED)])
    r = row(env, BTC)
    assert r["status"] == "unread"
    assert (r["seen"], r["limit_price"], r["extra"], r["cost"], r["fee"]) == (None, None, None, None, None)
    assert row(env, GOLD)["status"] == "open"


@pytest.mark.parametrize("answered", [None, "soon"])
def test_an_answer_time_that_isnt_a_number_never_raises(env, answered):
    b = paper_bot(env, {BTC: (YES_MARK, answered), GOLD: at_mark(NO_MARK)})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 3, IGNORED)])
    assert sorted(rows(env)) == [BTC, GOLD] and row(env, GOLD)["status"] == "open"


@pytest.mark.parametrize("error", [RuntimeError("the reader's thread died"), KeyError(W), ValueError("odd")])
def test_a_reader_that_raises_gives_every_order_an_unread_row(env, error):
    b = paper_bot(env, raises=error)
    yes, no = mk(BTC, YES96), mk(GOLD, NO98)
    b.fast_shadow(ENTRY, W, [(yes, "yes", 0.96, 3, IGNORED), (no, "no", 0.98, 5, IGNORED)])
    assert fields(row(env, BTC)) == expect(yes, "yes", asked=3, filled=0.0, seen=None, limit=None, lag=None, extra=None,
                                           cost=None, fee=None, status="unread")
    assert fields(row(env, GOLD)) == expect(no, "no", asked=5, filled=0.0, seen=None, limit=None, lag=None, extra=None,
                                            cost=None, fee=None, status="unread")
    assert b.reader.calls == [W]


# ------------------------------------------------------------------ one row a market, never saved here, nothing real touched
def test_a_second_fast_shadow_for_the_same_market_never_overwrites(env):
    b = paper_bot(env, {})
    m = mk(BTC, YES96)
    b.fast_shadow(ENTRY, W, [(m, "yes", 0.96, 3, IGNORED)])                 # unread the first time
    b.reader.store[BTC] = at_mark(YES_MARK)
    b.fast_shadow(ENTRY + 3, W, [(m, "yes", 0.96, 3, IGNORED)])             # readable the second
    [r] = rows(env).values()
    assert (r["ts"], r["status"], r["extra"]) == (ENTRY, "unread", None)


def test_a_fast_row_and_a_limitup_row_for_the_same_market_live_side_by_side(env):
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    m = mk(BTC, YES96)
    b.record_shadow(ENTRY, "limitup", m, W, "yes", 0.96, 0.97, 3, 1, 5.0, 2, 1.935, 0.0044, "open")
    b.fast_shadow(ENTRY, W, [(m, "yes", 0.96, 3, IGNORED)])
    assert sorted((r["kind"], r["ticker"], r["extra"]) for r in env.execute("SELECT * FROM shadow")) == \
        [("fast", BTC, 2.0), ("limitup", BTC, 2.0)]
    assert row(env, BTC, "limitup")["limit_price"] == 0.97 and row(env, BTC)["limit_price"] == 0.96


def test_fast_shadow_writes_every_row_through_record_shadow(env):
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    calls, real = [], b.record_shadow

    def spy(now, kind, m, window_open, side, seen, limit_price, asked, filled, lag, extra, cost, fee, status):
        calls.append((now, kind, m["ticker"], window_open, side, status))
        return real(now, kind, m, window_open, side, seen, limit_price, asked, filled, lag, extra, cost, fee, status)
    b.record_shadow = spy
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 3, IGNORED)])
    assert calls == [(ENTRY, "fast", BTC, W, "yes", "open"), (ENTRY, "fast", GOLD, W, "no", "unread")]


def test_fast_shadow_doesnt_commit_the_step_does(env, tmp_path):
    b = paper_bot(env, {BTC: at_mark(YES_MARK)})
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED)])
    assert env.in_transaction and committed_rows(str(tmp_path / "test.db")) == 0 and len(rows(env)) == 1
    env.rollback()
    assert rows(env) == {}


def test_fast_shadow_never_touches_an_order_a_bet_a_fill_or_a_decision(env):
    open_bet(env, BTC, W, contracts=1, cost=0.96, fee=0.01)
    env.execute("INSERT INTO orders (ts, ticker, request, http_status, response) VALUES (?, ?, '{}', 201, '{}')", (ENTRY, BTC))
    env.execute("INSERT INTO fills (trade_id, order_id, ticker, side, price, count) VALUES ('t1', 'o1', ?, 'yes', 0.96, 1)", (BTC,))
    env.execute("INSERT INTO decisions (ts, ticker, action, reason) VALUES (?, ?, 'bet', 'bought YES 1 at 96.0c')", (ENTRY, BTC))
    env.commit()
    before = snapshot(env)
    b = paper_bot(env, {BTC: at_mark(YES_MARK), GOLD: at_mark(None)})
    b.k = Watch()                                       # no order placed, cancelled or looked up
    b.fast_shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, IGNORED), (mk(GOLD, NO98), "no", 0.98, 3, IGNORED),
                             (mk(ETH, None), "yes", 0.96, 3, IGNORED)])
    assert b.k.calls == [] and snapshot(env) == before and len(rows(env)) == 3


# ------------------------------------------------------------------ a live window, start to finish
def test_a_live_window_pairs_every_real_order_with_a_fast_row_after_its_limitup_row(env):
    """FakeKalshi fills both real orders in full. ETH (61c, outside the band) sends no order, so it isn't paired, though
    the reader read its book."""
    fake = FakeKalshi()
    b = bot_for(fake, env, True)
    b.reader = Reader({BTC: at_mark(YES_MARK, 0.125), GOLD: at_mark(NO_MARK, 0.25), ETH: at_mark(raw(no=[(0.39, 5)]))})
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98), mk(ETH, book(0.60, 0.61))])
    assert [o["ticker"] for o in fake.orders] == [BTC, GOLD]
    fast, plus = rows(env), rows(env, "limitup")
    assert sorted(fast) == sorted(plus) == [BTC, GOLD]
    assert max(r["id"] for r in plus.values()) < min(r["id"] for r in fast.values())   # written after the +1c rows
    got = {t: (r["side"], r["asked"], r["filled"], r["seen"], r["limit_price"], r["extra"], r["lag"], r["status"])
           for t, r in fast.items()}
    assert got == {BTC: ("yes", 3, 3, 0.96, 0.96, 2, 0.125, "open"), GOLD: ("no", 3, 3, 0.98, 0.98, 3, 0.25, "open")}
    assert b.reader.calls == [W]


def markets():
    return [mk(BTC, YES96), mk(GOLD, NO98), mk(ETH, book(0.60, 0.61))]


def no_ids(by_ticker):
    return {t: fields(dict(r)) for t, r in by_ticker.items()}


@pytest.mark.parametrize("reader", [
    lambda: Reader({BTC: at_mark(YES_MARK), GOLD: at_mark(NO_MARK)}),
    lambda: Reader(raises=RuntimeError("the reader's thread died")),
    lambda: Reader({BTC: at_mark("garbage"), GOLD: (None,)}),
])
def test_the_reader_never_changes_a_real_order_bet_or_decision(env, tmp_path, reader):
    """The same window traded twice, on two ledgers: without a reader, and with one (good books, a reader that raises,
    garbage). The real orders, bets and decisions are the same."""
    plain_db = bot.connect(str(tmp_path / "plain.db"))
    bot.set_meta(plain_db, "start", THREE_DOLLAR_START)   # the same start as env's
    plain_db.commit()
    plain, paired = FakeKalshi(), FakeKalshi()
    bot_for(plain, plain_db, True).decide_window(ENTRY, W, markets())
    b = bot_for(paired, env, True)
    b.reader = reader()
    b.decide_window(ENTRY, W, markets())
    assert paired.orders == plain.orders and len(paired.orders) == 2
    assert no_ids(bets(env)) == no_ids(bets(plain_db)) and decisions(env) == decisions(plain_db)
    assert sorted(rows(env)) == [BTC, GOLD] and rows(plain_db) == {}
    plain_db.close()


def test_the_step_loop_saves_the_fast_rows(env, tmp_path):
    b = bot_for(FakeKalshi(), env, True)
    b.reader = Reader({BTC: at_mark(YES_MARK), GOLD: at_mark(NO_MARK)})
    b.step(ENTRY)
    other = sqlite3.connect(str(tmp_path / "test.db"))
    got = sorted(other.execute("SELECT ticker, side, seen, asked, filled, extra, status FROM shadow WHERE kind='fast'"))
    other.close()
    assert got == [(BTC, "yes", 0.96, 3.0, 3.0, 2.0, "open"), (GOLD, "no", 0.98, 3.0, 3.0, 3.0, "open")]


# ------------------------------------------------------------------ settle()
def paper_row(db, ticker, kind="fast", side="yes", extra=3.0, cost=2.88, fee=0.0081, status="open", close=W + 900):
    db.execute("INSERT INTO shadow (kind, ticker, ts, window_open, close_ts, series, side, seen, limit_price, asked, filled,"
               " lag, extra, cost, fee, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (kind, ticker, ENTRY, W, close, ticker.split("-")[0], side, 0.96, 0.96, 3.0, 1.0, 0.25, extra, cost, fee, status))


def settled(db, ticker, kind="fast"):
    r = db.execute("SELECT status, result, pnl, settled_ts FROM shadow WHERE kind=? AND ticker=?", (kind, ticker)).fetchone()
    return tuple(r)


def test_settle_settles_fast_rows_as_if_the_instant_orders_contracts_were_bought(env):
    paper_row(env, "KXBTC15M-Y", side="yes", extra=3, cost=2.88, fee=0.0081)     # YES, and YES won: $1 a contract
    paper_row(env, "KXBTC15M-N", side="yes", extra=3, cost=2.88, fee=0.0081)     # YES, and NO won
    paper_row(env, "KXGOLD15M-N", side="no", extra=3, cost=2.94, fee=0.0041)     # NO, and NO won
    paper_row(env, "KXGOLD15M-Y", side="no", extra=3, cost=2.94, fee=0.0041)     # NO, and YES won
    paper_row(env, "KXBTC15M-Z", side="yes", extra=0, cost=0, fee=0)             # bought nothing at the mark
    paper_row(env, "KXBTC15M-U", extra=None, cost=None, fee=None, status="unread")   # its book couldn't be read
    fake = Settling()
    fake.answers = {t: (r, W + 905) for t, r in (("KXBTC15M-Y", "yes"), ("KXBTC15M-N", "no"), ("KXGOLD15M-N", "no"),
                                                  ("KXGOLD15M-Y", "yes"), ("KXBTC15M-Z", "no"), ("KXBTC15M-U", "yes"))}
    bot.Bot(fake, env, True).settle(W + 920)
    assert settled(env, "KXBTC15M-Y") == ("settled", "yes", pytest.approx(3 - 2.88 - 0.0081), W + 905)
    assert settled(env, "KXBTC15M-N") == ("settled", "no", pytest.approx(-2.88 - 0.0081), W + 905)
    assert settled(env, "KXGOLD15M-N") == ("settled", "no", pytest.approx(3 - 2.94 - 0.0041), W + 905)
    assert settled(env, "KXGOLD15M-Y") == ("settled", "yes", pytest.approx(-2.94 - 0.0041), W + 905)
    assert settled(env, "KXBTC15M-Z") == ("settled", "no", 0, W + 905)
    assert settled(env, "KXBTC15M-U") == ("unread", None, None, None)
    assert not any("KXBTC15M-U" in lookup for lookup in fake.lookups)       # never even looked up


# ------------------------------------------------------------------ start_reader(): the reader, started for a live run
@pytest.fixture
def mark_readers(monkeypatch):
    """fast_entry.MarkReader swapped for a stand-in that notes how it was built and whether it was started, and never
    starts a thread (the real one would ask NTP servers and Kalshi). Returns the stand-ins made."""
    made = []

    class StandIn:
        def __init__(self, *args, **kw):
            self.args, self.kw, self.started = args, kw, 0
            made.append(self)

        def start(self):
            self.started += 1

        def books(self, window_open):
            return {}
    monkeypatch.setattr(fast_entry, "MarkReader", StandIn)
    return made


@pytest.fixture
def clients(monkeypatch):
    """bot.Kalshi swapped for a recorder: each client it makes is a plain object noting its arguments."""
    made = []

    def make(*args, **kw):
        made.append(types.SimpleNamespace(args=args, kw=kw))
        return made[-1]
    monkeypatch.setattr(bot, "Kalshi", make)
    return made


def built_with(reader):
    """What a stand-in reader was given, by position or by MarkReader's own names."""
    given = dict(zip(("client", "series_fn"), reader.args))
    given.update(reader.kw)
    return given


def keyless(args, kw, env_name):
    """A client made with the environment alone: no key, since the reader only reads order books."""
    return (args, kw) in [((env_name,), {}), ((), {"env": env_name})]


@pytest.mark.real_reader
def test_start_reader_builds_a_reader_on_a_public_client_starts_it_and_hands_it_to_the_bot(env, mark_readers, clients, capsys):
    b = bot_for(FakeKalshi(), env, True)
    got = bot.start_reader(b, "prod")
    [r], [client] = mark_readers, clients
    assert keyless(client.args, client.kw, "prod")
    given = built_with(r)
    assert set(given) == {"client", "series_fn"} and given["client"] is client      # MarkReader's own defaults otherwise
    assert given["series_fn"] == b.edge_series                                     # the bot's own, bound
    assert given["series_fn"]() == ["KXBTC15M", "KXGOLD15M", "KXETH15M"]
    del b.universe["KXGOLD15M"]
    assert given["series_fn"]() == ["KXBTC15M", "KXETH15M"]                        # read afresh every window
    assert r.started == 1 and got is r and b.reader is r
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and "minute 8" in lines[0]


@pytest.mark.real_reader
def test_without_fast_entry_beside_it_start_reader_says_so_and_the_bot_carries_on(env, clients, monkeypatch, capsys):
    """As in a folder holding only bot.py and kalshi.py: `import fast_entry` raises ImportError."""
    monkeypatch.setitem(sys.modules, "kalshi_bot.fast_entry", None)
    b = bot_for(FakeKalshi(), env, True)
    assert bot.start_reader(b, "prod") is None
    assert b.reader is None and clients == []                                     # no client made either
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and "fast" in lines[0].lower()
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])                                    # and it trades as ever
    assert [o["ticker"] for o in b.k.orders] == [BTC] and rows(env) == {}


@pytest.mark.real_reader
@pytest.mark.parametrize("fails_in", ["building", "starting"])
def test_a_reader_that_fails_to_build_or_start_never_stops_a_live_start(env, clients, monkeypatch, capsys, fails_in):
    """The paper experiment must never keep real trading from starting: a MarkReader that raises as it's built or
    started is said in one line and left out, and the bot trades as ever with no reader."""
    from kalshi_bot import fast_entry

    class Broken:
        def __init__(self, *args, **kw):
            if fails_in == "building":
                raise RuntimeError("can't build")

        def start(self):
            raise RuntimeError("can't start a thread")
    monkeypatch.setattr(fast_entry, "MarkReader", Broken)
    b = bot_for(FakeKalshi(), env, True)
    assert bot.start_reader(b, "prod") is None
    assert b.reader is None
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and "fast" in lines[0].lower() and "can't" in lines[0]   # what went wrong, in its line
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert [o["ticker"] for o in b.k.orders] == [BTC] and rows(env) == {}


def source():
    with open(bot.__file__, encoding="utf-8") as fh:
        return fh.read()


def imports_in(node, into_functions):
    """The modules imported under `node`: everywhere, or (into_functions False) only what runs when the module loads,
    which leaves out function bodies."""
    found, todo = [], list(ast.iter_child_nodes(node))
    while todo:
        n = todo.pop()
        if not into_functions and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Import):
            found += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            found.append(n.module or "")
        todo.extend(ast.iter_child_nodes(n))
    return found


def test_bot_py_imports_fast_entry_only_inside_start_reader():
    """test_scripts.py and test_one_bot.py run copies of the code holding only bot.py and kalshi.py."""
    tree = ast.parse(source())
    assert not [name for name in imports_in(tree, into_functions=False) if "fast_entry" in name]
    [fn] = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "start_reader"]   # at module level
    assert "kalshi_bot.fast_entry" in imports_in(fn, into_functions=True)


def test_bot_py_loads_without_fast_entry_beside_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "kalshi_bot.fast_entry", None)      # any `import fast_entry` now raises ImportError
    ns = {"__name__": "bot_without_fast_entry", "__file__": bot.__file__}
    exec(compile(source(), bot.__file__, "exec"), ns)
    assert callable(ns["start_reader"]) and callable(ns["Bot"].fast_shadow)


# ------------------------------------------------------------------ main(): only --live starts one
@pytest.fixture
def started(monkeypatch):
    """bot.start_reader swapped for a recorder (over conftest.py's stub: a test's own patch comes after it), and each of
    Bot.step's runs noted too, in one list of ("reader", args, kwargs) and ("step", (bot, now), {}) events."""
    events = []
    monkeypatch.setattr(bot, "start_reader", lambda *a, **kw: events.append(("reader", a, kw)))
    real_step = bot.Bot.step
    monkeypatch.setattr(bot.Bot, "step", lambda self, now: (events.append(("step", (self, now), {})), real_step(self, now))[1])
    return events


@pytest.mark.parametrize("argv, env_name", [(["--live", "--once"], "demo"),
                                            (["--live", "--env", "prod", "--yes", "--once"], "prod")])
def test_a_live_start_starts_the_reader_once_with_its_bot_and_environment(cli, started, capsys, argv, env_name):
    bot.main(argv)
    assert [e[0] for e in started] == ["reader", "step"]          # before the loop's first step
    (_, args, kw), (_, (stepping, _), _) = started
    given = list(args) + list(kw.values())
    assert len(given) == 2 and given[0] is stepping and given[1] == env_name
    assert isinstance(stepping, bot.Bot) and stepping.live


def test_the_reader_starts_once_however_many_steps_run(cli, started, monkeypatch, capsys):
    slept = []

    def sleep(s):
        slept.append(s)
        if len(slept) == 3:
            raise KeyboardInterrupt
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=sleep))
    with pytest.raises(KeyboardInterrupt):
        bot.main(["--live"])
    assert [e[0] for e in started] == ["reader", "step", "step", "step"]


@pytest.mark.parametrize("argv", [["--once"], ["--paper", "--once"], ["--env", "prod", "--once"], ["--check"], ["--status"]])
def test_only_a_live_start_starts_a_reader(cli, started, capsys, argv):
    bot.main(argv)
    assert all(e[0] != "reader" for e in started)


def test_a_prod_start_you_didnt_confirm_starts_no_reader(cli, started):
    cli.answers.append("no")
    assert exits(["--live", "--env", "prod", "--once"]) == "not started"
    assert started == []


@pytest.mark.real_reader
def test_a_live_start_gives_its_bot_a_started_reader_on_a_public_client(cli, mark_readers, monkeypatch, capsys):
    bots, real_step = [], bot.Bot.step
    monkeypatch.setattr(bot.Bot, "step", lambda self, now: (bots.append(self), real_step(self, now))[1])
    bot.main(["--live", "--once"])
    [b], [r] = bots, mark_readers
    assert b.reader is r and r.started == 1
    assert len(cli.made) == 2 and cli.made[0] == (("demo", "id", "/keys/k.pem"), {})   # the bot's own client, keyed ...
    assert keyless(*cli.made[1], "demo")                                              # ... and the reader's, with no key
    given = built_with(r)
    assert given["client"] is cli.fake and given["series_fn"] == b.edge_series
    assert "minute 8" in out(capsys)


# ------------------------------------------------------------------ conftest.py: no test starts a real reader
def test_a_live_start_in_a_test_not_marked_real_reader_starts_no_reader(cli, mark_readers, monkeypatch, capsys):
    bots, real_step = [], bot.Bot.step
    monkeypatch.setattr(bot.Bot, "step", lambda self, now: (bots.append(self), real_step(self, now))[1])
    bot.main(["--live", "--once"])
    assert mark_readers == [] and bots[0].reader is None and len(cli.made) == 1


def test_in_a_test_not_marked_real_reader_start_reader_is_a_stub_that_does_nothing(env, mark_readers, clients):
    assert getattr(bot.start_reader, "__module__", None) != bot.__name__  # not bot.py's own
    b = bot_for(FakeKalshi(), env, True)
    assert bot.start_reader(b, "prod") is None
    assert b.reader is None and mark_readers == [] and clients == []


@pytest.mark.real_reader
def test_a_test_marked_real_reader_gets_bot_pys_own_start_reader():
    assert bot.start_reader.__module__ == "kalshi_bot.bot" and bot.start_reader.__name__ == "start_reader"
    assert os.path.samefile(inspect.getsourcefile(bot.start_reader), bot.__file__)


def test_the_real_reader_marker_is_registered(pytestconfig):
    """Registered in conftest.py's pytest_configure, so marking a test with it gives no unknown-mark warning."""
    assert "real_reader" in [line.split(":")[0].strip() for line in pytestconfig.getini("markers")]


# ------------------------------------------------------------------ the docs
def test_the_module_docstring_says_it_reads_every_book_at_minute_8_exactly():
    doc = " ".join(bot.__doc__.split())
    assert "minute 8 exactly" in doc and "fast entry" in doc.lower()
    assert doc.index("SHADOW_UP") < doc.index("minute 8 exactly")        # the sentence after the paper +1c one
