"""The +1¢ limit on paper (the "shadow"), as it ran Oct 12-20, 2026: real orders at a limit of exactly the ask the bot
saw, and the extra cent measured without real money. Since Oct 20 the +1¢ is live (LIMIT_UP = 0.01, test_limit_up.py)
and the paper one records nothing more; these tests pin LIMIT_UP at 0 to keep checking the paper run as it was.

Terms: an immediate-or-cancel (IOC) order fills what it can at once and cancels the rest, so nothing waits on the book;
its limit is the most it will pay a contract; the ask it saw (`top`, kept as `seen`) is the cheapest offer on the book
when it decided. On paper ("shadow"): after each real order the bot reads the market's order book again, in the
background, and works out what a limit 1c higher (SHADOW_UP, at most 99.9c) would have bought on top of what really
filled: the **extra contracts**, the offers dearer than the ask it saw but within that paper limit, cheapest first, in
whole contracts, up to the contracts the real order didn't get. Their cost and their share of Kalshi's taker fee
(unrounded) go in the `shadow` table, one row per market, beside the **lag** (how many seconds after minute 8 the book
answered). When the market settles, the row gets its result and its P&L as if those contracts had been bought.

What must hold: live, LIMIT_UP is 0.01, the paper one's; with LIMIT_UP at 0, the order, the cash checks, the unexpected-fill halt and the dry run are back to
the ask it saw; book_fill can skip the offers at or under a price (`above`); the table and its rows are exactly as the
contract says (a kind column, so a later paper experiment, "fast", shares it); a read that fails, times out or brings
garbage gives an 'unread' row and trading carries on; a dry run records nothing; the reads never delay a real order and
never touch SQLite off the bot's own thread; shadow() runs once, at the end of the window, writes through
record_shadow() without committing, never overwrites a row and never touches an order or a bet; settle() settles open
rows of any kind and never an unread one; and with the +1¢ live, no paper +1¢ rows at all. The live +1¢ itself is
tested in test_limit_up.py.
Nothing here touches the network or an account.

    python -m pytest tests/test_shadow.py -q
"""
import concurrent.futures
import math
import os
import random
import sqlite3
import threading

import pytest
import requests

from kalshi_bot import bot
from layout import BOT
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, run, start_ledger
from test_day_drop import open_bet
from test_flow import BTC, GOLD, NO98, YES96, Scripted, Settling, bets, book, bot_for, fill, mk, slept  # noqa: F401 (slept: no sleeps)
from test_limit_up import OLD_LEDGER
from test_stops import timed


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around.
    The live limit at the ask it saw (LIMIT_UP 0), as it was while the +1¢ ran on paper."""
    monkeypatch.setattr(bot, "LIMIT_UP", 0.0)
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


README = os.path.join(BOT, "README.md")
BTC_B = "KXBTC15M-B"   # a second BTC-series market (a YES favourite at 96c in FakeKalshi's books)


def raw(yes=(), no=()):
    """A book as GET /markets/{t}/orderbook answers it: YES bids and NO bids, [price, size] as strings."""
    return {"orderbook_fp": {"yes_dollars": [[f"{p:.4f}", f"{q:g}"] for p, q in yes],
                             "no_dollars": [[f"{p:.4f}", f"{q:g}"] for p, q in no]}}


# The book read right after a real order. Buying YES walks the NO bids (YES offered at 1 - each): here YES at 96c x1 (the
# ask it saw: the real order's to take), 96.5c x1 and 97c x5 (within the paper 97c limit), 97.1c x5 (a tenth over it).
YES_AFTER = raw(yes=[(0.95, 100)], no=[(0.04, 1), (0.035, 1), (0.03, 5), (0.029, 5)])
# Buying NO walks the YES bids: NO at 98c x2 (the ask it saw), 98.5c x1 and 99c x5 (within the paper 99c limit), 99.1c x9.
NO_AFTER = raw(yes=[(0.02, 2), (0.015, 1), (0.01, 5), (0.009, 9)], no=[(0.97, 40)])


def kalshi_fee(levels, mult=1.0):
    """Kalshi's taker fee on these (contracts, price) levels, unrounded: 0.07 x mult x q x p x (1 - p) each."""
    return sum(0.07 * mult * q * p * (1 - p) for q, p in levels)


class Exchange(FakeKalshi):
    """FakeKalshi (BTC a YES favourite at 96c, GOLD a NO favourite at 98c) whose real orders fill `filled[ticker]`
    contracts (all of them if the ticker isn't named) at the order's own price, and whose book read for a ticker in
    `after` answers that: a raw book, None (unreadable), or an exception it raises. Every book read is noted as
    (ticker, on the main thread?, orders sent by then)."""

    def __init__(self, filled=None, after=None, **kw):
        super().__init__(**kw)
        self.filled, self.after, self.reads = dict(filled or {}), dict(after or {}), []

    def create_order(self, body):
        status, data = super().create_order(body)
        if isinstance(data, dict) and body["ticker"] in self.filled:
            data["fill_count"] = f"{self.filled[body['ticker']]}.00"
        return status, data

    def fills(self, order_id=None, ticker=None, limit=100):
        d = super().fills(order_id, ticker, limit)
        n = self.filled.get(self.orders[int(order_id[1:]) - 1]["ticker"]) if order_id else None
        for f in d["fills"]:
            if n is not None:
                f["count_fp"] = f"{n}.00"
        return d

    def orderbook(self, ticker):
        self.reads.append((ticker, threading.current_thread() is threading.main_thread(), len(self.orders)))
        if ticker not in self.after:
            return super().orderbook(ticker)
        answer = self.after[ticker]
        if isinstance(answer, BaseException):
            raise answer
        return answer


class Watch:
    """Stands in for Kalshi where nothing should be called: notes any call."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a, **kw: self.calls.append(name)


def done(answer, at=0.0):
    """A book read that has answered: (raw book or None, seconds into the step when it answered), as read_book gives."""
    f = concurrent.futures.Future()
    f.set_result((answer, at))
    return f


def broke(e):
    """A book read that raised."""
    f = concurrent.futures.Future()
    f.set_exception(e)
    return f


class Hung(concurrent.futures.Future):
    """A book read that never answers. No test waits the real 10 s: result() (or exception()) gives up at once, as if
    its wait had run out, and notes how long it was told to wait."""

    def __init__(self):
        super().__init__()
        self.waits = []

    def result(self, timeout=None):
        self.waits.append(timeout)
        raise concurrent.futures.TimeoutError()

    exception = result


def rows(db, kind="limitup"):
    return {r["ticker"]: dict(r) for r in db.execute("SELECT * FROM shadow WHERE kind=? ORDER BY id", (kind,))}


def committed_rows(path):
    """What another program (the dashboard) sees in the ledger: only what has been committed."""
    other = sqlite3.connect(path)
    try:
        return other.execute("SELECT COUNT(*) FROM shadow").fetchone()[0]
    finally:
        other.close()


def snapshot(db):
    return {t: [tuple(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY id")] for t in ("bets", "orders", "decisions", "fills")}


# ------------------------------------------------------------------ the constants and the live limit
def test_live_the_limit_is_1c_over_the_ask_it_saw_as_the_paper_one_was():
    assert bot.LIMIT_UP == 0.01   # live since Oct 20, 2026, after 8 days on paper
    assert bot.SHADOW_UP == 0.01


def test_the_live_limit_is_1c_over_the_ask_it_saw_across_the_whole_band():
    """Every price it may buy at, LO to HI (92c to 99.9c) in hundredths of a cent: the limit is 1c over, at most 99.9c."""
    for m in range(round(bot.LO * 10000), 9991):
        top = m / 10000
        assert bot.limit_for(top) == min(round(top + 0.01, 4), bot.HI), top


def test_with_the_1c_live_the_paper_one_records_nothing(env, monkeypatch):
    """Once the live limit reaches the paper one (LIMIT_UP = SHADOW_UP), the real order has already tried every offer the
    paper limit would take, so there's nothing left to measure: no 'limitup' row, and the real order is as it was."""
    monkeypatch.setattr(bot, "LIMIT_UP", bot.SHADOW_UP)
    fake = Exchange(filled={BTC: 1}, after={BTC: YES_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    [order] = fake.orders
    assert (order["side"], order["price"], order["count"]) == ("bid", "0.9700", "3")    # the real order: 1c over
    assert bets(env)[BTC]["contracts"] == 1
    assert rows(env) == {}


@pytest.mark.parametrize("b, side, price", [
    (YES96, "bid", "0.9600"),               # a YES favourite at 96c: a bid at 96c
    (book(0.91, 0.92), "bid", "0.9200"),    # YES at 92c, the floor
    (book(0.99, 0.995), "bid", "0.9950"),
    (book(0.99, 0.999), "bid", "0.9990"),
    (NO98, "ask", "0.0200"),                # NO at 98c: buying NO at 98c is selling YES at 2c
    (book(0.08, 0.09), "ask", "0.0800"),    # NO at 92c
    (book(0.069, 0.075), "ask", "0.0690"),  # NO at 93.1c
    (book(0.005, 0.006), "ask", "0.0050"),  # NO at 99.5c
])
def test_a_live_order_goes_out_at_exactly_the_ask_it_saw(env, b, side, price):
    fake = FakeKalshi()                     # fills every order in full at its own price
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, b)])
    [order] = fake.orders
    assert (order["side"], order["price"], order["count"]) == (side, price, "3")
    assert order["time_in_force"] == "immediate_or_cancel" and bot.halt_info() is None


# $10,000 is $150 a bet (1.5%): 156 contracts at the 96c it saw, needing 156 x 96c + the 42c fee = $150.18 (with the +1c live
# limit it was $151.74).
@pytest.mark.parametrize("cash, placed", [(150.17, False), (150.19, True), (150.50, True)])
def test_the_books_cash_must_cover_every_contract_at_the_ask_it_saw(env, cash, placed):
    bot.set_start(env, 10_000.0)
    open_bet(env, "KXBTC15M-OLD", W - 900, contracts=10000, cost=round(10_000.0 - cash, 2), fee=0.0)   # ties up the rest
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, book(0.95, 0.96, ask_size=500.0))])
    if placed:
        assert decisions(env)[BTC][0] == "bet" and bets(env)[BTC]["contracts"] == 156
    else:
        assert decisions(env)[BTC] == ("skip", "bankroll too low") and BTC not in bets(env)


@pytest.mark.parametrize("cash, placed", [(150.17, False), (150.19, True), (150.50, True)])
def test_the_real_cash_must_cover_every_contract_at_the_ask_it_saw(env, cash, placed):
    bot.set_start(env, 10_000.0)
    fake = FakeKalshi()
    fake.crypto_cash = f"{cash:.4f}"
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    if placed:
        assert [o["count"] for o in fake.orders] == ["156"]
    else:
        assert fake.orders == [] and decisions(env)[BTC][1].startswith(f"only ${cash:.2f} in Kalshi's Crypto & Commodities")


def test_the_real_cash_left_for_the_next_order_drops_by_its_cost_at_the_ask(env):
    """$5.85: BTC takes $2.89 (3 at 96c + 1c), leaving $2.96, enough for GOLD's $2.95 (3 at 98c + 1c). With the +1c live
    limit BTC took $2.92 and GOLD needed $2.98."""
    fake = FakeKalshi()
    fake.crypto_cash = "5.8500"
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert [o["ticker"] for o in fake.orders] == [BTC, GOLD]


@pytest.mark.parametrize("market, fills, why", [
    (mk(BTC, YES96), [fill(3, 0.9601)], f"unexpected fill on {BTC}: 3.0 at 0.9601, asked 3 at 0.9600"),
    (mk(BTC, YES96), [fill(3, 0.965)], f"unexpected fill on {BTC}: 3.0 at 0.9650, asked 3 at 0.9600"),
    (mk(BTC, YES96), [fill(3, 0.97)], f"unexpected fill on {BTC}: 3.0 at 0.9700, asked 3 at 0.9600"),
    (mk(GOLD, NO98), [fill(3, 0.015, side="no")], f"unexpected fill on {GOLD}: 3.0 at 0.9850, asked 3 at 0.9800"),
])
def test_a_fill_over_the_ask_it_saw_halts_again(env, market, fills, why):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": fills})
    bot_for(fake, env, True).decide_window(ENTRY, W, [market])
    h = bot.halt_info()
    assert h is not None and h["reason"] == why
    assert bets(env)[market["ticker"]]["contracts"] == 3     # the position is real, so it's recorded


def test_a_fill_at_the_ask_it_saw_is_normal(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": [fill(3, 0.96)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bot.halt_info() is None and bets(env)[BTC]["price"] == pytest.approx(0.96)


def test_a_dry_run_fills_only_up_to_the_ask_it_saw(env):
    """1 contract offered at the 96c it saw, 1 at 96.5c, 5 at 97c: only the one at 96c (the +1c limit got all 3)."""
    b = {"yes": [(0.95, 100.0)], "no": [(0.04, 1.0), (0.035, 1.0), (0.03, 5.0)]}
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    r = bets(env)[BTC]
    assert r["contracts"] == 1 and r["cost"] == pytest.approx(0.96) and r["fee"] == bot.taker_fee(1, 0.96)
    assert decisions(env)[BTC][1] == "would buy YES 1 at 96.0c ($3.00 a bet)"


def test_fills_that_never_show_up_are_counted_at_the_ask_it_saw(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": []})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    r = bets(env)[BTC]
    assert r["cost"] == pytest.approx(3 * 0.96) and r["fee"] == bot.taker_fee(3, 0.96) and bot.halt_info() is None


# ------------------------------------------------------------------ book_fill(..., above=)
# Books as parse_book gives them. YES offered at 96c x2, 96.5c x5, 97c x10, 98c x50; NO at 98c x3, 98.5c x4, 99c x100.
YES_UP = {"yes": [(0.95, 100.0)], "no": [(0.04, 2.0), (0.035, 5.0), (0.03, 10.0), (0.02, 50.0)]}
NO_UP = {"yes": [(0.02, 3.0), (0.015, 4.0), (0.01, 100.0)], "no": [(0.97, 40.0)]}


@pytest.mark.parametrize("b, side, limit, contracts, above, filled, cost", [
    (YES_UP, "yes", 0.97, 100, 0.96, 15, 5 * 0.965 + 10 * 0.97),     # the 96c offers skipped, the rest up to the limit
    (YES_UP, "yes", 0.97, 6, 0.96, 6, 5 * 0.965 + 0.97),             # still cheapest first, still stops at the size
    (YES_UP, "yes", 0.98, 100, 0.965, 60, 10 * 0.97 + 50 * 0.98),
    (YES_UP, "yes", 0.97, 100, 0.97, 0, 0.0),                        # nothing dearer than `above` within the limit
    (YES_UP, "yes", 0.97, 100, 0.9599, 17, 2 * 0.96 + 5 * 0.965 + 10 * 0.97),   # `above` under the cheapest: all of it
    (NO_UP, "no", 0.99, 200, 0.98, 104, 4 * 0.985 + 100 * 0.99),
    (NO_UP, "no", 0.99, 3, 0.98, 3, 3 * 0.985),
])
def test_book_fill_above_skips_the_offers_at_or_under_it(b, side, limit, contracts, above, filled, cost):
    got_filled, got_cost = bot.book_fill(b, side, limit, contracts, above=above)
    assert got_filled == filled and got_cost == pytest.approx(cost, abs=1e-9)


@pytest.mark.parametrize("b, side, above, filled", [
    ({"yes": [], "no": [(0.04, 5.0)]}, "yes", 0.96, 0),            # YES offered at exactly `above`: skipped
    ({"yes": [], "no": [(0.04, 5.0)]}, "yes", 0.96 - 1e-12, 0),    # float noise under it still counts as at it
    ({"yes": [], "no": [(0.04, 5.0)]}, "yes", 0.9599, 3),          # a hundredth of a cent under it: taken
    ({"yes": [(0.02, 5.0)], "no": []}, "no", 0.98, 0),             # NO offered at exactly `above`: skipped
    ({"yes": [(0.02, 5.0)], "no": []}, "no", 0.9799, 3),
])
def test_book_fill_above_skips_an_offer_exactly_at_it(b, side, above, filled):
    assert bot.book_fill(b, side, 0.99, 3, above=above)[0] == filled


@pytest.mark.parametrize("b", [None, {}, {"yes": [], "no": []}])
def test_book_fill_above_on_a_missing_or_empty_book_is_nothing(b):
    assert bot.book_fill(b, "yes", 0.99, 3, above=0.96) == (0.0, 0.0)
    assert bot.book_fill(b, "no", 0.99, 3, above=0.96) == (0.0, 0.0)


def test_book_fill_above_is_the_cheapest_whole_contracts_between_above_and_the_limit_on_any_book():
    """Brute force on random books: every whole contract offered dearer than `above` (or any, with no `above`) and at
    or under the limit, cheapest first; the fill is the first `contracts` of them. Without `above` it's unchanged."""
    rng = random.Random(12)
    for _ in range(500):
        side = rng.choice(["yes", "no"])
        other = "no" if side == "yes" else "yes"
        bids = sorted(((rng.randint(1, 120) / 1000, rng.choice([0.5, 1.0, 2.0, 2.9, 7.0, 40.0]))
                       for _ in range(rng.randint(0, 6))), reverse=True)
        limit, contracts = rng.randint(900, 999) / 1000, rng.randint(0, 60)
        above = rng.choice([None, rng.randint(880, 999) / 1000])
        offers = sorted(p for bid, size in bids for p in [round(1 - bid, 4)] * math.floor(size + 1e-9)
                        if p <= limit + 1e-9 and (above is None or p > above + 1e-9))
        b = {side: [(0.5, 10.0)], other: bids}
        filled, cost = bot.book_fill(b, side, limit, contracts, above=above) if above is not None else \
            bot.book_fill(b, side, limit, contracts)
        assert filled == len(offers[:contracts]) and cost == pytest.approx(sum(offers[:contracts]), abs=1e-9), (bids, limit, above)
        if above is None:
            assert bot.book_fill(b, side, limit, contracts, above=None) == (filled, cost)


# ------------------------------------------------------------------ the shadow table
SHADOW_COLUMNS = [("id", "INTEGER"), ("kind", "TEXT"), ("ticker", "TEXT"), ("ts", "REAL"), ("window_open", "REAL"),
                  ("close_ts", "REAL"), ("series", "TEXT"), ("side", "TEXT"), ("seen", "REAL"), ("limit_price", "REAL"),
                  ("asked", "REAL"), ("filled", "REAL"), ("lag", "REAL"), ("extra", "REAL"), ("cost", "REAL"),
                  ("fee", "REAL"), ("status", "TEXT"), ("result", "TEXT"), ("pnl", "REAL"), ("settled_ts", "REAL")]


def unique_keys(db, table):
    """The column sets a UNIQUE constraint covers, as SQLite indexes them."""
    keys = set()
    for idx in db.execute(f"PRAGMA index_list({table})").fetchall():
        if idx[2]:
            keys.add(tuple(r[2] for r in db.execute(f"PRAGMA index_info('{idx[1]}')")))
    return keys


def test_connect_makes_the_shadow_table_one_row_per_kind_and_market(tmp_path):
    db = bot.connect(str(tmp_path / "x.db"))
    info = db.execute("PRAGMA table_info(shadow)").fetchall()
    assert [(r[1], r[2]) for r in info] == SHADOW_COLUMNS
    assert [r[1] for r in info if r[5]] == ["id"]                        # the primary key
    assert unique_keys(db, "shadow") == {("kind", "ticker")}            # (kind, ticker), not the ticker alone
    db.execute("INSERT INTO shadow (kind, ticker) VALUES ('limitup', 'T')")
    db.execute("INSERT INTO shadow (kind, ticker) VALUES ('fast', 'T')")       # the same market, another experiment
    db.execute("INSERT INTO shadow (kind, ticker) VALUES ('limitup', 'T2')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO shadow (kind, ticker) VALUES ('limitup', 'T')")
    db.close()


@pytest.mark.parametrize("with_fills", [False, True])   # a ledger from before the fills table, and one from Oct 11
def test_an_old_ledger_gains_the_shadow_table_on_the_next_start(tmp_path, with_fills):
    path = str(tmp_path / "live-prod.db")
    old = sqlite3.connect(path)
    old.executescript(OLD_LEDGER)
    if with_fills:
        old.executescript("CREATE TABLE fills (id INTEGER PRIMARY KEY, trade_id TEXT UNIQUE, order_id TEXT, ticker TEXT,"
                          " side TEXT, price REAL, count REAL, fee REAL, ts REAL);"
                          "INSERT INTO fills (trade_id, price) VALUES ('t1', 0.96);")
    old.close()
    db = bot.connect(path)
    assert [(r[1], r[2]) for r in db.execute("PRAGMA table_info(shadow)")] == SHADOW_COLUMNS
    assert bot.get_meta(db, "start") == "400.0"                                     # everything else kept
    assert db.execute("SELECT reason FROM decisions").fetchone()[0] == "bought YES 3 at 96.0c"
    if with_fills:
        assert [tuple(r) for r in db.execute("SELECT trade_id, price FROM fills")] == [("t1", 0.96)]
    db.execute("INSERT INTO shadow (kind, ticker, status) VALUES ('limitup', 'KXBTC15M-OLD', 'open')")
    db.commit()
    db.close()
    again = bot.connect(path)                                                        # and a later start keeps its rows
    assert [tuple(r) for r in again.execute("SELECT kind, ticker, status FROM shadow")] == [("limitup", "KXBTC15M-OLD", "open")]
    again.close()


# ------------------------------------------------------------------ record_shadow: the one writer
def test_record_shadow_writes_every_column(env):
    b = bot_for(FakeKalshi(), env, True)
    b.record_shadow(ENTRY, "limitup", mk(BTC, YES96), W, "yes", 0.96, 0.97, 3, 1, 7.5, 2, 1.935, 0.0044, "open")
    [r] = env.execute("SELECT * FROM shadow").fetchall()
    assert dict(r) == {"id": r["id"], "kind": "limitup", "ticker": BTC, "ts": ENTRY, "window_open": W, "close_ts": W + 900,
                       "series": "KXBTC15M", "side": "yes", "seen": 0.96, "limit_price": 0.97, "asked": 3.0, "filled": 1.0,
                       "lag": 7.5, "extra": 2.0, "cost": 1.935, "fee": 0.0044, "status": "open", "result": None,
                       "pnl": None, "settled_ts": None}


def test_record_shadow_never_overwrites_and_keeps_one_row_per_kind(env, tmp_path):
    b = bot_for(FakeKalshi(), env, True)
    m = mk(GOLD, NO98)
    b.record_shadow(ENTRY, "limitup", m, W, "no", 0.98, 0.99, 3, 0, 5.0, None, None, None, "unread")
    b.record_shadow(ENTRY + 3, "limitup", m, W, "no", 0.97, 0.98, 9, 9, 1.0, 9, 9.0, 9.0, "open")   # a repeat
    b.record_shadow(ENTRY, "fast", m, W, "no", 0.975, 0.975, 4, 0, 2.0, 4, 3.9, 0.003, "open")      # another experiment
    got = {(r["kind"], r["ticker"]): dict(r) for r in env.execute("SELECT * FROM shadow")}
    assert sorted(got) == [("fast", GOLD), ("limitup", GOLD)]
    first = got[("limitup", GOLD)]
    assert (first["ts"], first["seen"], first["asked"], first["status"]) == (ENTRY, 0.98, 3.0, "unread")   # the first kept
    assert (first["extra"], first["cost"], first["fee"]) == (None, None, None)
    assert got[("fast", GOLD)]["extra"] == 4.0
    assert env.in_transaction and committed_rows(str(tmp_path / "test.db")) == 0     # not committed inside: the step does


# ------------------------------------------------------------------ a live window's paper rows
def test_a_yes_order_gets_one_paper_row(env):
    """The real order (3 at the 96c it saw) fills 1. The book read after it: the paper 97c limit would have taken 1 more
    at 96.5c and 1 at 97c (2 left to fill), not the 97.1c ones."""
    fake = Exchange(filled={BTC: 1}, after={BTC: YES_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    [order] = fake.orders
    assert (order["side"], order["price"], order["count"]) == ("bid", "0.9600", "3")    # the real order: at the ask
    assert bets(env)[BTC]["contracts"] == 1
    r = rows(env)[BTC]
    assert r == {"id": r["id"], "kind": "limitup", "ticker": BTC, "ts": ENTRY, "window_open": W, "close_ts": W + 900,
                 "series": "KXBTC15M", "side": "yes", "seen": 0.96, "limit_price": 0.97, "asked": 3.0, "filled": 1.0,
                 "lag": pytest.approx(5.0), "extra": 2.0, "cost": pytest.approx(0.965 + 0.97),
                 "fee": pytest.approx(kalshi_fee([(1, 0.965), (1, 0.97)]), rel=1e-9, abs=1e-12), "status": "open",
                 "result": None, "pnl": None, "settled_ts": None}


def test_a_no_order_that_got_nothing_gets_one_paper_row(env):
    """The real order (3 at the 98c it saw) fills nothing: all 3 are left for the paper 99c limit, which takes 1 at 98.5c
    and 2 at exactly 99c, not the 99.1c ones."""
    fake = Exchange(filled={GOLD: 0}, after={GOLD: NO_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(GOLD, NO98)])
    [order] = fake.orders
    assert (order["side"], order["price"]) == ("ask", "0.0200")
    assert decisions(env)[GOLD] == ("skip", "not filled: nobody selling at that price") and not bets(env)
    r = rows(env)[GOLD]
    assert (r["kind"], r["side"], r["seen"], r["limit_price"], r["asked"], r["filled"]) == ("limitup", "no", 0.98, 0.99, 3, 0)
    assert r["extra"] == 3 and r["cost"] == pytest.approx(0.985 + 2 * 0.99)
    assert r["fee"] == pytest.approx(kalshi_fee([(1, 0.985), (2, 0.99)]), rel=1e-9, abs=1e-12)
    assert (r["status"], r["series"], r["close_ts"], r["lag"]) == ("open", "KXGOLD15M", W + 900, pytest.approx(5.0))


def test_a_fully_filled_order_has_no_extra(env):
    fake = Exchange(filled={BTC: 3}, after={BTC: YES_AFTER})   # offers within the paper limit, but nothing left to fill
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    r = rows(env)[BTC]
    assert (r["asked"], r["filled"], r["extra"], r["cost"], r["fee"], r["status"]) == (3, 3, 0, 0, 0, "open")


def test_the_paper_fee_uses_the_series_fee_multiplier(env):
    class HalfFee(Exchange):
        def series(self):
            d = super().series()
            for s in d["series"]:
                if s["ticker"] == "KXBTC15M":
                    s["fee_multiplier"] = "0.5"
            return d
    bot_for(HalfFee(filled={BTC: 1}, after={BTC: YES_AFTER}), env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert rows(env)[BTC]["fee"] == pytest.approx(kalshi_fee([(1, 0.965), (1, 0.97)], mult=0.5), rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("market, after, limit, extra, cost", [
    # YES at 96c, paper limit 97c: an offer at exactly 97c is taken, one a tenth of a cent over isn't
    (mk(BTC, YES96), raw(no=[(0.03, 5)]), 0.97, 3, 3 * 0.97),
    (mk(BTC, YES96), raw(no=[(0.029, 5)]), 0.97, 0, 0.0),
    # NO at 98c, paper limit 99c
    (mk(GOLD, NO98), raw(yes=[(0.01, 5)]), 0.99, 3, 3 * 0.99),
    (mk(GOLD, NO98), raw(yes=[(0.009, 5)]), 0.99, 0, 0.0),
    # YES at 99.5c: the paper limit is capped at 99.9c (not 100.5c); 99.7c and 99.9c taken, 99.95c not
    (mk(BTC, book(0.99, 0.995)), raw(no=[(0.005, 1), (0.003, 1), (0.001, 1), (0.0005, 5)]), 0.999, 2, 0.997 + 0.999),
    # YES at 99.9c: already at the cap, so the paper order can't reach past the ask it saw
    (mk(BTC, book(0.99, 0.999)), raw(no=[(0.001, 5)]), 0.999, 0, 0.0),
    # whole contracts, cheapest first: 1 of the 1.9 at 96.5c, none of the half at 96.8c, then 2 at 97c
    (mk(BTC, YES96), raw(no=[(0.03, 3), (0.032, 0.5), (0.035, 1.9)]), 0.97, 3, 0.965 + 2 * 0.97),
    # a book read fine with nothing offered: measured, with nothing extra
    (mk(BTC, YES96), {"orderbook_fp": {}}, 0.97, 0, 0.0),
])
def test_the_paper_limit_takes_offers_up_to_1c_over_and_never_past_99_9c(env, market, after, limit, extra, cost):
    fake = Exchange(filled={market["ticker"]: 0}, after={market["ticker"]: after})
    bot_for(fake, env, True).decide_window(ENTRY, W, [market])
    r = rows(env)[market["ticker"]]
    assert (r["limit_price"], r["filled"], r["extra"], r["status"]) == (limit, 0, extra, "open")
    assert r["cost"] == pytest.approx(cost, abs=1e-9)


def test_the_paper_contracts_come_from_the_book_read_after_the_order_not_the_one_before(env):
    """The book it decided on (YES96: 50 offered at 96c, nothing dearer) would give no extra; the one read after does."""
    bot_for(Exchange(filled={BTC: 0}, after={BTC: YES_AFTER}), env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert rows(env)[BTC]["extra"] == 3       # 1 at 96.5c, 2 at 97c


def test_every_order_sent_gets_a_row_and_only_those(env):
    """BTC fills 1, GOLD nothing, a third market's order is refused (HTTP 400): each was sent, so each gets a row
    (whatever place() returned). ETH (61c, outside the band) and a fourth market whose book is too old to trade on
    send nothing: no row."""
    class Refusing(Exchange):
        def create_order(self, body):
            if body["ticker"] == BTC_B:
                self.orders.append(body)
                return 400, {"error": {"code": "invalid_order"}}
            return super().create_order(body)
    fake = Refusing(filled={BTC: 1, GOLD: 0}, after={BTC: YES_AFTER, GOLD: NO_AFTER})
    stale = dict(mk("KXBTC15M-C", YES96), read=-100.0)   # its book read 100 s before: skipped, no order
    markets = [mk(BTC, YES96), mk(GOLD, NO98), mk(BTC_B, YES96), mk("KXETH15M-A", book(0.60, 0.61)), stale]
    bot_for(fake, env, True).decide_window(ENTRY, W, markets)
    assert [o["ticker"] for o in fake.orders] == [BTC, GOLD, BTC_B]
    assert decisions(env)["KXBTC15M-C"][1].startswith("its order book was read 100s ago")
    got = rows(env)
    assert sorted(got) == sorted([BTC, GOLD, BTC_B])
    assert (got[BTC]["filled"], got[BTC]["extra"]) == (1, 2) and (got[GOLD]["filled"], got[GOLD]["extra"]) == (0, 3)
    assert (got[BTC_B]["filled"], got[BTC_B]["status"]) == (0, "open")   # FakeKalshi's BTC book: 96c only, nothing extra


def test_the_lag_is_when_the_book_answered_counted_from_minute_8(env):
    """It decides 5 s after minute 8; the real order takes 1.5 s and the book read after it 2.5 s: the book answered
    9 s after minute 8."""
    class Slow(Exchange):
        def create_order(self, body):
            b.clock.add(1.5)
            return super().create_order(body)

        def orderbook(self, ticker):
            b.clock.add(2.5)
            return super().orderbook(ticker)
    fake = Slow(after={BTC: YES_AFTER})
    b = timed(fake, env)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert rows(env)[BTC]["lag"] == pytest.approx(9.0)


def test_read_book_is_the_raw_answer_and_when_it_came(env):
    class Slow(Exchange):
        def orderbook(self, ticker):
            b.clock.add(2.5)
            return super().orderbook(ticker)
    fake = Slow(after={BTC: YES_AFTER, GOLD: None})
    b = timed(fake, env)
    assert b.read_book(BTC) == (YES_AFTER, pytest.approx(2.5))
    assert b.read_book(GOLD) == (None, pytest.approx(5.0))     # an unreadable book is None, as Kalshi's client gives it


def test_read_book_only_reads_the_book(env):
    """It runs off the bot's own thread, so it must not touch the ledger: SQLite connections belong to one thread, and
    a read there would raise."""
    statements = []
    env.set_trace_callback(statements.append)
    b = bot_for(Exchange(after={BTC: YES_AFTER}), env, True)
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        assert pool.submit(b.read_book, BTC).result(5) == (YES_AFTER, 0.0)
    env.set_trace_callback(None)
    assert statements == []


# ------------------------------------------------------------------ reads that fail
@pytest.mark.parametrize("answer", [
    None,                                               # Kalshi's client: the read failed
    {}, {"orderbook_fp": None}, {"error": {"code": "not_found"}},   # parse_book finds no book in it
    "gateway timeout", ["not", "a", "dict"],            # not even a JSON object
    {"orderbook_fp": {"yes_dollars": [["abc", "1"]]}},  # a price that isn't a number
])
def test_an_unreadable_book_gives_an_unread_row_and_trading_carries_on(env, answer):
    fake = Exchange(filled={BTC: 1}, after={BTC: answer, GOLD: NO_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert [o["ticker"] for o in fake.orders] == [BTC, GOLD] and sorted(bets(env)) == [BTC, GOLD]
    got = rows(env)
    assert (got[BTC]["status"], got[BTC]["extra"], got[BTC]["cost"], got[BTC]["fee"]) == ("unread", None, None, None)
    assert (got[BTC]["kind"], got[BTC]["side"], got[BTC]["seen"], got[BTC]["limit_price"]) == ("limitup", "yes", 0.96, 0.97)
    assert (got[BTC]["asked"], got[BTC]["filled"]) == (3, 1)
    assert got[GOLD]["status"] == "open"


@pytest.mark.parametrize("error", [requests.ConnectionError("connection reset"), requests.Timeout("read timed out"),
                                   RuntimeError("something else")])
def test_a_read_that_raises_gives_an_unread_row_and_trading_carries_on(env, error):
    fake = Exchange(after={BTC: error, GOLD: NO_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert [o["ticker"] for o in fake.orders] == [BTC, GOLD] and sorted(bets(env)) == [BTC, GOLD]
    got = rows(env)
    assert (got[BTC]["status"], got[BTC]["extra"], got[BTC]["cost"], got[BTC]["fee"]) == ("unread", None, None, None)
    assert got[GOLD]["status"] == "open"


def test_a_read_that_never_answers_is_given_up_on_within_10s(env):
    b = bot_for(FakeKalshi(), env, True)
    hung = Hung()
    b.shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, hung), (mk(GOLD, NO98), "no", 0.98, 3, done(NO_AFTER))])
    assert hung.waits and all(t is not None and 0 < t <= 10 for t in hung.waits)
    got = rows(env)
    assert (got[BTC]["status"], got[BTC]["extra"], got[BTC]["cost"], got[BTC]["fee"]) == ("unread", None, None, None)
    assert got[GOLD]["status"] == "open" and got[GOLD]["extra"] == 3


@pytest.mark.parametrize("read", [lambda: broke(requests.ConnectionError("reset")), lambda: broke(ValueError("bad")),
                                  lambda: done(None), lambda: done("garbage"), lambda: done([1, 2])])
def test_shadow_never_raises_for_a_bad_read(env, read):
    b = bot_for(FakeKalshi(), env, True)
    b.shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, read())])
    assert rows(env)[BTC]["status"] == "unread"


# ------------------------------------------------------------------ shadow() on its own
def test_shadow_takes_filled_from_the_bet_and_the_rest_from_the_book(env):
    """Hand-made reads: BTC's bet holds 1 contract (2 left: 96.5c + 97c), GOLD has no bet (3 left)."""
    open_bet(env, BTC, W, contracts=1, cost=0.96, fee=0.01)
    b = bot_for(FakeKalshi(), env, True)
    b.shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, done(YES_AFTER, 2.5)),
                        (mk(GOLD, NO98), "no", 0.98, 3, done(NO_AFTER, 4.0))])
    got = rows(env)
    assert (got[BTC]["filled"], got[BTC]["extra"], got[BTC]["lag"]) == (1, 2, pytest.approx(7.5))
    assert got[BTC]["cost"] == pytest.approx(0.965 + 0.97)
    assert (got[GOLD]["filled"], got[GOLD]["extra"], got[GOLD]["lag"]) == (0, 3, pytest.approx(9.0))
    assert got[GOLD]["fee"] == pytest.approx(kalshi_fee([(1, 0.985), (2, 0.99)]), rel=1e-9, abs=1e-12)
    assert all(r["ts"] == ENTRY and r["window_open"] == W for r in got.values())


def test_shadow_measures_any_book_as_the_brute_force_does(env):
    """Random books, sides, asks, sizes and real fills (sometimes more than asked: then nothing is left): the extra is the
    whole contracts offered dearer than the ask and at most 1c over it (99.9c at most), cheapest first, up to what the
    real order didn't fill; the cost their sum; the fee 0.07 x mult x p x (1 - p) a contract, unrounded."""
    rng = random.Random(13)
    b = bot_for(FakeKalshi(), env, True)
    b.universe["KXBTC15M"]["fee"] = 0.5
    reads, want = [], {}
    for i in range(300):
        t, side = f"KXBTC15M-R{i}", rng.choice(["yes", "no"])
        top, c = rng.randint(900, 999) / 1000, rng.randint(1, 40)
        filled = rng.choice([0, 0, rng.randint(0, c), c, c + 1])
        if filled:
            open_bet(env, t, W, contracts=filled, cost=filled * top)
        prices = {round(top + rng.choice([-0.01, -0.005, 0, 0.001, 0.005, 0.009, 0.01, 0.011, 0.02]), 4) for _ in range(5)}
        levels = [(round(1 - p, 4), rng.choice([0.5, 1.0, 2.0, 2.9, 7.0, 40.0])) for p in prices if p < 1]
        answer = raw(yes=levels, no=[(0.5, 10)]) if side == "no" else raw(yes=[(0.5, 10)], no=levels)
        limit = min(round(top + 0.01, 4), 0.999)
        offers = sorted(p for bid, size in levels for p in [round(1 - float(f"{bid:.4f}"), 4)] * math.floor(size + 1e-9)
                        if top + 1e-9 < p <= limit + 1e-9)[:max(c - filled, 0)]
        want[t] = (filled, limit, len(offers), sum(offers), sum(0.07 * 0.5 * p * (1 - p) for p in offers))
        reads.append((mk(t, None), side, top, c, done(answer)))
    b.shadow(ENTRY, W, reads)
    got = rows(env)
    assert len(got) == 300
    for t, (filled, limit, extra, cost, fee) in want.items():
        r = got[t]
        assert (r["filled"], r["limit_price"], r["extra"], r["status"]) == (filled, limit, extra, "open"), t
        assert r["cost"] == pytest.approx(cost, abs=1e-9) and r["fee"] == pytest.approx(fee, abs=1e-12), t


def test_shadow_with_no_reads_does_nothing(env):
    b = bot_for(FakeKalshi(), env, True)
    b.k = Watch()
    before = env.total_changes
    b.shadow(ENTRY, W, [])
    assert env.total_changes == before and not env.in_transaction and b.k.calls == []
    assert env.execute("SELECT COUNT(*) FROM shadow").fetchone()[0] == 0


def test_a_second_shadow_for_the_same_market_never_overwrites(env):
    b = bot_for(FakeKalshi(), env, True)
    b.shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, done(None))])                    # unread the first time
    b.shadow(ENTRY + 3, W, [(mk(BTC, YES96), "yes", 0.96, 3, done(YES_AFTER, 1.0))])       # readable the second
    [r] = rows(env).values()
    assert (r["ts"], r["status"], r["extra"]) == (ENTRY, "unread", None)


def test_shadow_doesnt_commit_the_step_does(env, tmp_path):
    b = bot_for(FakeKalshi(), env, True)
    b.shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, done(YES_AFTER))])
    assert env.in_transaction and committed_rows(str(tmp_path / "test.db")) == 0
    env.commit()
    assert committed_rows(str(tmp_path / "test.db")) == 1


def test_shadow_never_touches_an_order_or_a_bet(env):
    open_bet(env, BTC, W, contracts=1, cost=0.96, fee=0.01)
    env.execute("INSERT INTO orders (ts, ticker, request, http_status, response) VALUES (?, ?, '{}', 201, '{}')", (ENTRY, BTC))
    env.execute("INSERT INTO fills (trade_id, order_id, ticker, side, price, count) VALUES ('t1', 'o1', ?, 'yes', 0.96, 1)", (BTC,))
    env.execute("INSERT INTO decisions (ts, ticker, action, reason) VALUES (?, ?, 'bet', 'bought YES 1 at 96.0c')", (ENTRY, BTC))
    env.commit()
    before = snapshot(env)
    b = bot_for(FakeKalshi(), env, True)
    b.k = Watch()                                       # no order placed, cancelled or looked up
    b.shadow(ENTRY, W, [(mk(BTC, YES96), "yes", 0.96, 3, done(YES_AFTER)), (mk(GOLD, NO98), "no", 0.98, 3, done(None)),
                        (mk(BTC_B, YES96), "yes", 0.96, 3, broke(RuntimeError("x")))])
    assert b.k.calls == [] and snapshot(env) == before and len(rows(env)) == 3


def test_shadow_writes_every_row_through_record_shadow(env):
    fake = Exchange(filled={BTC: 1}, after={BTC: YES_AFTER, GOLD: None})
    b = bot_for(fake, env, True)
    calls, real = [], b.record_shadow

    def spy(now, kind, m, window_open, side, seen, limit_price, asked, filled, lag, extra, cost, fee, status):
        calls.append((kind, m["ticker"], side, status))
        return real(now, kind, m, window_open, side, seen, limit_price, asked, filled, lag, extra, cost, fee, status)
    b.record_shadow = spy
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert sorted(calls) == [("limitup", BTC, "yes", "open"), ("limitup", GOLD, "no", "unread")]


# ------------------------------------------------------------------ when and where it runs
def test_shadow_runs_once_at_the_end_of_the_window_with_one_read_per_order(env):
    fake = Exchange()
    b = bot_for(fake, env, True)
    calls, real = [], b.shadow

    def spy(now, window_open, reads):
        calls.append((now, window_open, len(fake.orders), [(r[0]["ticker"], r[1], r[2], r[3]) for r in reads],
                      [isinstance(r[4], concurrent.futures.Future) for r in reads]))
        return real(now, window_open, reads)
    b.shadow = spy
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert calls == [(ENTRY, W, 2, [(BTC, "yes", 0.96, 3), (GOLD, "no", 0.98, 3)], [True, True])]


def test_a_dry_run_reads_nothing_and_records_nothing(env):
    fake = Exchange(after={BTC: YES_AFTER, GOLD: NO_AFTER})
    b = bot_for(fake, env, False)
    calls, real = [], b.shadow
    b.shadow = lambda now, window_open, reads: (calls.append(list(reads)), real(now, window_open, reads))[1]
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert sorted(bets(env)) == [BTC, GOLD] and calls == [[]]
    assert fake.reads == [] and env.execute("SELECT COUNT(*) FROM shadow").fetchone()[0] == 0


def test_a_dry_step_records_nothing(env):
    run(env, Exchange(), live=False)
    assert len(bets(env)) == 2 and env.execute("SELECT COUNT(*) FROM shadow").fetchone()[0] == 0


class Gated(Exchange):
    """Its book reads wait on a gate that opens only when the last of the window's `n` orders goes out. Had the bot
    waited on any read before sending its next order, that read would have given up after 5 s and said so. Each order
    also notes how many paper rows existed when it went out."""

    def __init__(self, n, db, **kw):
        super().__init__(**kw)
        self.n, self.db, self.gate, self.opened, self.rows_then = n, db, threading.Event(), [], []

    def create_order(self, body):
        self.rows_then.append(self.db.execute("SELECT COUNT(*) FROM shadow").fetchone()[0])
        out = super().create_order(body)
        if len(self.orders) == self.n:
            self.gate.set()
        return out

    def orderbook(self, ticker):
        self.opened.append((ticker, self.gate.wait(5)))
        return super().orderbook(ticker)


def test_the_reads_never_delay_a_real_order(env):
    fake = Gated(3, env, filled={BTC: 1, GOLD: 0}, after={BTC: YES_AFTER, GOLD: NO_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98), mk(BTC_B, YES96)])
    assert [o["ticker"] for o in fake.orders] == [BTC, GOLD, BTC_B]
    assert sorted(fake.opened) == sorted([(BTC, True), (GOLD, True), (BTC_B, True)])   # every read was still waiting
    assert fake.rows_then == [0, 0, 0]                  # no paper row before the last order went out
    got = rows(env)
    assert sorted(got) == sorted([BTC, GOLD, BTC_B]) and {r["status"] for r in got.values()} == {"open"}
    assert (got[BTC]["extra"], got[GOLD]["extra"]) == (2, 3)


def test_each_read_is_handed_to_the_bots_pool_right_after_its_order(env, monkeypatch):
    """The sequence on the bot's own thread: order, its read submitted (not waited on), the next order, ... The pool is
    the bot's own, at most 4 threads."""
    events, pools = [], []

    class Pool(bot.ThreadPoolExecutor):
        def __init__(self, max_workers=None, *a, **kw):
            pools.append(max_workers)
            super().__init__(max_workers, *a, **kw)

        def submit(self, fn, *args, **kw):
            events.append(("read", args[0] if args else kw.get("ticker")))
            return super().submit(fn, *args, **kw)

    class Logged(Exchange):
        def create_order(self, body):
            events.append(("order", body["ticker"]))
            return super().create_order(body)
    monkeypatch.setattr(bot, "ThreadPoolExecutor", Pool)
    fake = Logged(filled={GOLD: 0})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98), mk(BTC_B, YES96)])
    assert events == [("order", BTC), ("read", BTC), ("order", GOLD), ("read", GOLD), ("order", BTC_B), ("read", BTC_B)]
    assert pools and all(w is not None and 1 <= w <= 4 for w in pools)


def test_the_reads_run_in_the_background_and_the_rows_are_written_on_the_bots_thread(env, monkeypatch):
    statements, connects = [], []
    env.set_trace_callback(lambda s: statements.append((threading.current_thread() is threading.main_thread(), s)))
    real_connect = sqlite3.connect
    monkeypatch.setattr(bot.sqlite3, "connect", lambda *a, **kw: (connects.append(threading.current_thread()
                                                                                    is threading.main_thread()),
                                                                   real_connect(*a, **kw))[1])
    fake = Exchange(filled={BTC: 1}, after={BTC: YES_AFTER, GOLD: NO_AFTER})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    env.set_trace_callback(None)
    assert sorted(t for t, _, _ in fake.reads) == [BTC, GOLD]
    assert not any(on_main for _, on_main, _ in fake.reads)                          # the reads: off the bot's thread
    order = {o["ticker"]: i + 1 for i, o in enumerate(fake.orders)}
    assert all(sent >= order[t] for t, _, sent in fake.reads)                        # each after its own order went out
    assert all(on_main for on_main, _ in statements)                                 # every SQL statement: on its thread
    assert any("INSERT" in s.upper() and "SHADOW" in s.upper() for _, s in statements)
    assert all(connects)                                                             # no second connection in a thread
    assert {r["status"] for r in rows(env).values()} == {"open"}


def test_the_step_loop_saves_the_paper_rows(env, tmp_path):
    run(env, Exchange(), live=True)                     # FakeKalshi fills both orders in full: nothing extra
    other = sqlite3.connect(str(tmp_path / "test.db"))
    got = sorted(other.execute("SELECT kind, ticker, side, seen, limit_price, asked, filled, extra, status, lag FROM shadow"))
    other.close()
    assert [g[:-1] for g in got] == [("limitup", BTC, "yes", 0.96, 0.97, 3.0, 3.0, 0.0, "open"),
                                     ("limitup", GOLD, "no", 0.98, 0.99, 3.0, 3.0, 0.0, "open")]
    assert all(5.0 <= g[-1] < 65.0 for g in got)       # entered 5 s after minute 8; the reads answered a moment later


# ------------------------------------------------------------------ settle()
def paper_row(db, ticker, kind="limitup", side="yes", extra=2.0, cost=1.935, fee=0.0044, status="open", close=W + 900):
    db.execute("INSERT INTO shadow (kind, ticker, ts, window_open, close_ts, series, side, seen, limit_price, asked, filled,"
               " lag, extra, cost, fee, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (kind, ticker, ENTRY, W, close, ticker.split("-")[0], side, 0.96, 0.97, 3.0, 1.0, 5.0, extra, cost, fee, status))


def settled(db, ticker, kind="limitup"):
    r = db.execute("SELECT status, result, pnl, settled_ts FROM shadow WHERE kind=? AND ticker=?", (kind, ticker)).fetchone()
    return tuple(r)


def test_settle_settles_paper_rows_as_if_their_extra_contracts_were_bought(env):
    paper_row(env, "KXBTC15M-Y", side="yes", extra=2, cost=1.935, fee=0.0044)    # YES, and YES won: $1 a contract
    paper_row(env, "KXBTC15M-N", side="yes", extra=2, cost=1.935, fee=0.0044)    # YES, and NO won
    paper_row(env, "KXGOLD15M-N", side="no", extra=3, cost=2.965, fee=0.0024)    # NO, and NO won
    paper_row(env, "KXGOLD15M-Y", side="no", extra=3, cost=2.965, fee=0.0024)    # NO, and YES won
    paper_row(env, "KXBTC15M-Z", side="yes", extra=0, cost=0, fee=0)             # nothing extra: nothing won or lost
    fake = Settling()
    fake.answers = {"KXBTC15M-Y": ("yes", W + 905), "KXBTC15M-N": ("no", W + 905), "KXGOLD15M-N": ("no", W + 905),
                    "KXGOLD15M-Y": ("yes", W + 905), "KXBTC15M-Z": ("no", W + 905)}
    bot.Bot(fake, env, True).settle(W + 920)
    assert settled(env, "KXBTC15M-Y") == ("settled", "yes", pytest.approx(2 - 1.935 - 0.0044), W + 905)
    assert settled(env, "KXBTC15M-N") == ("settled", "no", pytest.approx(-1.935 - 0.0044), W + 905)
    assert settled(env, "KXGOLD15M-N") == ("settled", "no", pytest.approx(3 - 2.965 - 0.0024), W + 905)
    assert settled(env, "KXGOLD15M-Y") == ("settled", "yes", pytest.approx(-2.965 - 0.0024), W + 905)
    assert settled(env, "KXBTC15M-Z") == ("settled", "no", 0, W + 905)


def test_settle_never_settles_an_unread_row_or_looks_it_up(env):
    paper_row(env, "KXBTC15M-U", extra=None, cost=None, fee=None, status="unread")
    fake = Settling()
    fake.answers = {"KXBTC15M-U": ("yes", W + 905)}
    bot.Bot(fake, env, True).settle(W + 920)
    assert fake.lookups == [] and settled(env, "KXBTC15M-U") == ("unread", None, None, None)


@pytest.mark.parametrize("answer", [("", None), (None, None), ("void", None), ("scalar", None)])
def test_a_paper_row_whose_market_has_no_result_yet_stays_open(env, answer):
    paper_row(env, BTC)
    fake = Settling()
    fake.answers = {BTC: answer}
    bot.Bot(fake, env, True).settle(W + 920)
    assert settled(env, BTC) == ("open", None, None, None)


def test_a_paper_row_kalshi_doesnt_return_stays_open(env):
    paper_row(env, BTC)
    bot.Bot(Settling(), env, True).settle(W + 920)
    assert settled(env, BTC) == ("open", None, None, None)


def test_paper_rows_still_running_arent_looked_up(env):
    paper_row(env, BTC)                                  # closes at W + 900
    fake = Settling()
    bot.Bot(fake, env, True).settle(W + 901)             # inside the two-second margin
    assert fake.lookups == []
    bot.Bot(fake, env, True).settle(W + 902)
    assert fake.lookups == [[BTC]]


def test_a_settled_paper_row_isnt_looked_up_or_changed_again(env):
    paper_row(env, BTC, status="settled")
    env.execute("UPDATE shadow SET result='yes', pnl=0.06, settled_ts=? WHERE ticker=?", (W + 905, BTC))
    fake = Settling()
    fake.answers = {BTC: ("no", W + 999)}
    bot.Bot(fake, env, True).settle(W + 2000)
    assert fake.lookups == [] and settled(env, BTC) == ("settled", "yes", 0.06, W + 905)


def test_a_paper_rows_settlement_time_falls_back_to_now(env):
    paper_row(env, BTC)
    fake = Settling()
    fake.answers = {BTC: ("yes", None)}
    bot.Bot(fake, env, True).settle(W + 950)
    assert settled(env, BTC)[3] == W + 950


def test_paper_rows_settle_in_the_same_lookup_as_the_bets(env):
    open_bet(env, BTC, W, contracts=1, cost=0.96, fee=0.01)
    paper_row(env, BTC)                                   # the same market: its bet and its paper row
    paper_row(env, GOLD, side="no", extra=3, cost=2.965, fee=0.0024)
    fake = Settling()
    fake.answers = {BTC: ("yes", W + 905), GOLD: ("yes", W + 905)}
    bot.Bot(fake, env, True).settle(W + 920)
    assert len(fake.lookups) == 1 and set(fake.lookups[0]) == {BTC, GOLD}
    assert bets(env)[BTC]["status"] == "won" and bets(env)[BTC]["pnl"] == pytest.approx(1 - 0.96 - 0.01)
    assert settled(env, BTC)[:2] == ("settled", "yes") and settled(env, GOLD)[:2] == ("settled", "yes")


def test_bets_and_paper_rows_are_looked_up_50_at_a_time(env):
    for i in range(30):
        open_bet(env, f"KXBTC15M-B{i:02d}", W, 3, 2.88)
        paper_row(env, f"KXBTC15M-P{i:02d}")
    fake = Settling()
    fake.answers = {f"KXBTC15M-{x}{i:02d}": ("yes", W + 905) for x in "BP" for i in range(30)}
    bot.Bot(fake, env, True).settle(W + 920)
    assert [len(x) for x in fake.lookups] == [50, 10]
    assert env.execute("SELECT COUNT(*) FROM bets WHERE status='won'").fetchone()[0] == 30
    assert env.execute("SELECT COUNT(*) FROM shadow WHERE status='settled'").fetchone()[0] == 30


def test_settle_settles_a_row_of_any_kind_the_same_way(env):
    """The table is shared by every paper experiment: a 'fast' row (another experiment's) settles by the same rule."""
    paper_row(env, BTC, kind="fast", side="yes", extra=3, cost=2.88, fee=0.01)
    paper_row(env, BTC, kind="limitup", side="yes", extra=2, cost=1.935, fee=0.0044)
    paper_row(env, GOLD, kind="fast", side="yes", extra=3, cost=2.88, fee=0.01)
    fake = Settling()
    fake.answers = {BTC: ("yes", W + 905), GOLD: ("no", W + 905)}
    bot.Bot(fake, env, True).settle(W + 920)
    assert settled(env, BTC, "fast") == ("settled", "yes", pytest.approx(3 - 2.88 - 0.01), W + 905)
    assert settled(env, BTC, "limitup") == ("settled", "yes", pytest.approx(2 - 1.935 - 0.0044), W + 905)
    assert settled(env, GOLD, "fast") == ("settled", "no", pytest.approx(-2.88 - 0.01), W + 905)


def test_the_step_settles_and_saves_paper_rows(env, tmp_path):
    paper_row(env, "KXBTC15M-OLD", close=W)
    env.commit()
    fake = FakeKalshi()
    fake.results = {"KXBTC15M-OLD": "yes"}
    bot.Bot(fake, env, True).step(W + 50)
    other = sqlite3.connect(str(tmp_path / "test.db"))
    got = other.execute("SELECT status, result, pnl FROM shadow").fetchone()
    other.close()
    assert got[:2] == ("settled", "yes") and got[2] == pytest.approx(2 - 1.935 - 0.0044)


# ------------------------------------------------------------------ the docs
def test_the_module_docstring_says_the_1c_was_measured_on_paper_first():
    doc = " ".join(bot.__doc__.split())
    assert "The +1c was measured on paper first, Oct 12-20, 2026" in doc
    assert "SHADOW_UP" in doc and "shadow table" in doc


def test_limit_for_names_the_live_setting():
    assert "LIMIT_UP" in " ".join(bot.limit_for.__doc__.split())


def readme():
    if not os.path.exists(README):
        pytest.skip("README.md isn't beside the code in this copy (copy it in to run this check)")
    with open(README, encoding="utf-8") as fh:
        return fh.read()


def test_the_readme_safety_bullet_says_it_pays_at_most_1c_over_and_mentions_the_paper_run():
    safety = readme().split("## Safety", 1)[1].split("\n## ", 1)[0]
    [bullet] = [b for b in safety.split("\n- ") if "Pays at most 1¢ over the ask it saw" in b]
    assert "immediate-or-cancel" in bullet and "paper" in bullet and "1¢" in bullet


def test_the_readme_says_the_live_research_1c_ran_on_paper_then_went_live():
    [para] = [p for p in readme().split("\n\n") if p.startswith("The Live Research tab")]
    assert "paper" in para and "LIMIT_UP" in para and "Oct 20" in para


def test_the_readme_lists_this_file():
    tests = readme().split("## Tests", 1)[1].split("\n## ", 1)[0]
    assert any(line.startswith("|") and "`test_shadow.py`" in line for line in tests.splitlines())
