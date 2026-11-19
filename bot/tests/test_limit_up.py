"""The +1¢ limit switch: with LIMIT_UP = 0.01 the bot's buy order reaches 1c over the ask it saw, never past 99.9c.

Live since Oct 20, 2026 (LIMIT_UP = 0.01), after the extra cent ran on paper first from Oct 12 (test_shadow.py). Every
test here sets it too, so the switch stays tested whatever bot.py says.

Why: other traders buy at minute 8 exactly and the bot's order lands about 2.4 s later, so the ask has often ticked up
by then, and only 55% of the contracts it asked for filled. The research's "+1¢ limit" experiment
(research/kalshi_15min/lab/fills.py) tests paying up to a cent more to get them.

Terms: an immediate-or-cancel (IOC) order fills what it can at once and cancels the rest, so nothing waits on the book;
its limit is the most it will pay a contract; the ask it saw (`top`) is the cheapest offer on the book when it decided.

What must hold: it still sizes the order off the ask it saw; it sends the limit (a NO buy goes out as an ask on YES at
1 - the limit); its cash must cover every contract at the limit; only a fill dearer than the limit, or larger than the
order, halts; fills that never show up are counted at the limit; a dry run takes the cheapest offers on the book up to
the limit; and every fill it counts is kept in a `fills` table, so the Live Research tab can tell the contracts the
extra cent bought from the ones the old limit would have got. Nothing here touches the network or an account.

    python -m pytest tests/test_limit_up.py -q
"""
import math
import os
import random
import sqlite3

import pytest

from kalshi_bot import bot
from layout import BOT
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, run, start_ledger
from test_day_drop import open_bet
from test_flow import BTC, GOLD, NO98, YES96, Scripted, bets, book, bot_for, fill, mk, slept  # noqa: F401 (slept: no sleeps)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


README = os.path.join(BOT, "README.md")


@pytest.fixture(autouse=True)
def limit_up(monkeypatch):
    """The +1¢ limit turned on, as setting LIMIT_UP = 0.01 in bot.py would put it live."""
    monkeypatch.setattr(bot, "LIMIT_UP", 0.01)


def start(db, amount):
    bot.set_start(db, amount)
    db.commit()


def rich(fake, dollars=10_000_000):
    """This much real cash in Crypto & Commodities (by default, so much the balance check never binds)."""
    fake.crypto_cash = f"{dollars:.4f}"
    return fake


def filled_in_full(fills):
    """Kalshi's answer to a 3-contract order that filled in full, and these fills when the bot looks them up."""
    return Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": fills})


def kfill(count, yes_price=0.96, side="yes", fee="0.0100", **ids):
    """A fill as GET /portfolio/fills gives it, with the IDs the bot keeps (trade_id, order_id, ticker, created_time)."""
    return dict(fill(count, yes_price, side, fee), **ids)


def kept(db):
    return [dict(r) for r in db.execute("SELECT trade_id, order_id, ticker, side, price, count, fee, ts FROM fills ORDER BY id")]


# ------------------------------------------------------------------ the limit
@pytest.mark.parametrize("top, limit", [
    (0.90, 0.91), (0.95, 0.96), (0.96, 0.97), (0.931, 0.941), (0.98, 0.99),
    (0.989, 0.999),                 # 99.9c exactly
    (0.99, 0.999), (0.995, 0.999),  # capped at 99.9c (HI), not 100c or 100.5c
    (0.999, 0.999),                 # already at the cap: no higher
])
def test_the_limit_is_1c_over_the_ask_it_saw_and_never_past_99_9c(top, limit):
    assert bot.limit_for(top) == limit


def test_the_limit_over_the_whole_band():
    """Every price it may buy at, LO to HI (92c to 99.9c) in tenths of a cent: never under the ask it saw, at most 1c over
    it, never past HI, and in whole hundredths of a cent (the 4 places an order's price is written with)."""
    assert bot.limit_for.__doc__
    for m in range(round(bot.LO * 1000), 1000):
        top = m / 1000
        lim = bot.limit_for(top)
        assert top <= lim <= bot.HI and lim - top <= bot.LIMIT_UP + 1e-9, top
        assert lim == round(lim, 4) and lim == pytest.approx(min(top + 0.01, 0.999)), top


# ------------------------------------------------------------------ the order it sends
@pytest.mark.parametrize("b, side, price", [
    (YES96, "bid", "0.9700"),               # a YES favourite at 96c: a bid at 97c
    (book(0.91, 0.92), "bid", "0.9300"),    # YES at 92c, the floor: a bid at 93c
    (book(0.99, 0.995), "bid", "0.9990"),   # 99.5c: capped at 99.9c
    (book(0.99, 0.999), "bid", "0.9990"),   # 99.9c: no higher (the same as before the change)
    (NO98, "ask", "0.0100"),                # NO at 98c: buying NO up to 99c is selling YES down to 1c
    (book(0.08, 0.09), "ask", "0.0700"),    # NO at 92c, limit 93c
    (book(0.069, 0.075), "ask", "0.0590"),  # NO at 93.1c, limit 94.1c: 1 - 0.941 rounded to 4 places
    (book(0.005, 0.006), "ask", "0.0010"),  # NO at 99.5c: capped at 99.9c
])
def test_the_order_goes_out_at_the_limit(env, b, side, price):
    fake = FakeKalshi()                     # fills every order in full at its own price: here, the limit itself
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, b)])
    [order] = fake.orders
    assert (order["side"], order["price"], order["count"]) == (side, price, "3")
    assert order["time_in_force"] == "immediate_or_cancel"
    assert bot.halt_info() is None          # a fill at the limit itself is normal


@pytest.mark.parametrize("b", [book(0.92, 0.93), book(0.07, 0.08)])   # YES at 93c, NO at 93c
def test_the_order_is_still_sized_off_the_ask_it_saw(env, b):
    """$30 (1.5% of $2,000) buys 32 contracts at the 93c it saw, 31 at the 94c limit: it asks for 32, as the research sized them.
    (The same as before the change: this pins that the limit didn't move the size. 93c, as 92c and its 93c limit both
    buy 32.)"""
    start(env, 2_000.0)
    fake = rich(FakeKalshi())
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, b)])
    [order] = fake.orders
    assert order["count"] == "32" and bets(env)[BTC]["contracts"] == 32


# ------------------------------------------------------------------ the cash it must have
# $10,000 is $150 a bet (1.5%): 156 contracts at the 96c it saw. Before the change it needed 156 x 96c + the fee at 96c (42c),
# $150.18. Now the worst case is every contract at the 97c limit plus the fee at the ask it saw (the fee falls as the price
# rises past 50c, so the seen ask's is the larger): 156 x 97c + 42c = $151.74. With the fee at 97c (32c) it would be $151.64.
CASH_CASES = [
    (150.50, False),   # covers the old need, not the new one
    (151.70, False),   # covers 156 at the limit with the limit's fee, not with the seen ask's
    (151.75, True),    # covers the worst case
]


@pytest.mark.parametrize("cash, placed", CASH_CASES)
def test_the_books_cash_must_cover_every_contract_at_the_limit(env, cash, placed):
    start(env, 10_000.0)
    open_bet(env, "KXBTC15M-OLD", W - 900, contracts=10000, cost=round(10_000.0 - cash, 2), fee=0.0)   # ties up the rest
    assert bot.cash(env) == pytest.approx(cash)
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, YES96)])
    if placed:
        assert decisions(env)[BTC][0] == "bet" and BTC in bets(env)
    else:
        assert decisions(env)[BTC] == ("skip", "bankroll too low") and BTC not in bets(env)


@pytest.mark.parametrize("cash, placed", CASH_CASES)
def test_the_real_cash_must_cover_every_contract_at_the_limit(env, cash, placed):
    start(env, 10_000.0)
    fake = rich(FakeKalshi(), cash)
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    if placed:
        assert [o["count"] for o in fake.orders] == ["156"]
    else:
        assert fake.orders == []
        assert decisions(env)[BTC][1].startswith(f"only ${cash:.2f} in Kalshi's Crypto & Commodities section")


def test_the_real_cash_left_for_the_next_order_drops_by_the_worst_case(env):
    fake = FakeKalshi()
    fake.crypto_cash = "5.8500"   # BTC's worst case is $2.92 (3 at 97c + 1c), leaving $2.93; GOLD's is $2.98 (3 at 99c + 1c)
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    d = decisions(env)
    assert d[BTC][0] == "bet"
    assert d[GOLD][0] == "skip" and d[GOLD][1].startswith("only $2.93 in Kalshi's Crypto & Commodities section")
    assert [o["ticker"] for o in fake.orders] == [BTC]


# ------------------------------------------------------------------ the unexpected-fill halt
@pytest.mark.parametrize("fills", [
    [fill(3, 0.965)],                                 # half a cent over the 96c it saw
    [fill(3, 0.97)],                                  # exactly the limit
    [fill(1, 0.96), fill(1, 0.965), fill(1, 0.97)],   # up the book, level by level, to the limit
])
def test_a_fill_over_the_ask_it_saw_but_within_the_limit_is_normal(env, fills):
    bot_for(filled_in_full(fills), env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bot.halt_info() is None
    r = bets(env)[BTC]
    paid = sum(float(f["count_fp"]) * float(f["yes_price_dollars"]) for f in fills)
    assert r["contracts"] == 3 and r["cost"] == pytest.approx(paid) and r["price"] == pytest.approx(paid / 3)


def test_a_no_fill_over_the_ask_it_saw_but_within_the_limit_is_normal(env):
    bot_for(filled_in_full([fill(3, 0.015, side="no")]), env, True).decide_window(ENTRY, W, [mk(GOLD, NO98)])
    assert bot.halt_info() is None and bets(env)[GOLD]["price"] == pytest.approx(0.985)   # NO at 98.5c, limit 99c


@pytest.mark.parametrize("market, fills, why", [
    (mk(BTC, YES96), [fill(3, 0.9701)], f"unexpected fill on {BTC}: 3.0 at 0.9701, asked 3 at 0.9700"),
    (mk(BTC, YES96), [fill(3, 0.98)], f"unexpected fill on {BTC}: 3.0 at 0.9800, asked 3 at 0.9700"),
    # a NO bet names its own prices, not the YES price the order was written in
    (mk(GOLD, NO98), [fill(3, 0.005, side="no")], f"unexpected fill on {GOLD}: 3.0 at 0.9950, asked 3 at 0.9900"),
    # at the cap, the limit is 99.9c
    (mk(BTC, book(0.99, 0.995)), [fill(3, 0.9995)], f"unexpected fill on {BTC}: 3.0 at 0.9995, asked 3 at 0.9990"),
])
def test_a_fill_dearer_than_the_limit_halts_and_names_the_limit(env, market, fills, why):
    bot_for(filled_in_full(fills), env, True).decide_window(ENTRY, W, [market])
    assert bot.halt_info()["reason"] == why
    assert bets(env)[market["ticker"]]["contracts"] == 3     # the position is real, so it's recorded


def test_a_fill_larger_than_the_order_halts_even_within_the_limit(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "4.00"}), fills=lambda p: {"fills": [fill(4, 0.965)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bot.halt_info()["reason"] == f"unexpected fill on {BTC}: 4.0 at 0.9650, asked 3 at 0.9700"
    assert bets(env)[BTC]["contracts"] == 4


# ------------------------------------------------------------------ fills that never show up
@pytest.mark.parametrize("amount, market, contracts, limit", [
    (200.0, mk(BTC, YES96), 3, 0.97),
    (10_000.0, mk(BTC, YES96), 156, 0.97),          # big enough that the fee at 97c (32c) isn't the fee at 96c (42c)
    (10_000.0, mk(GOLD, NO98), 153, 0.99),          # NO at 98c: 153 at the 99c limit, fee 11c (21c at 98c)
    (200.0, mk(BTC, book(0.99, 0.995)), 3, 0.999),  # at the cap
])
def test_fills_that_never_show_up_are_counted_at_the_limit(env, slept, amount, market, contracts, limit):
    start(env, amount)
    fake = rich(Scripted(order=(201, {"order_id": "o1", "fill_count": f"{contracts}.00"}), fills=lambda p: {"fills": []}))
    bot_for(fake, env, True).decide_window(ENTRY, W, [market])
    assert fake.orders[0]["count"] == str(contracts) and slept == [0.5] * 3    # it looked three times
    r = bets(env)[market["ticker"]]
    assert r["contracts"] == contracts and r["cost"] == pytest.approx(contracts * limit) and r["price"] == pytest.approx(limit)
    assert r["fee"] == bot.taker_fee(contracts, limit)
    assert bot.halt_info() is None                  # the limit itself is no surprise


# ------------------------------------------------------------------ book_fill: walking the book up to the limit
# Books as parse_book gives them: YES bids and NO bids, best first. An offer to sell YES at p is a NO bid at 1 - p, and an
# offer to sell NO at p is a YES bid at 1 - p, so buying YES walks the NO bids and buying NO walks the YES bids.
YES_UP = {"yes": [(0.95, 100.0)],                                          # (not an offer to sell YES: ignored)
          "no": [(0.04, 2.0), (0.035, 5.0), (0.03, 10.0), (0.02, 50.0)]}  # YES offered at 96c x2, 96.5c x5, 97c x10, 98c x50
NO_UP = {"yes": [(0.02, 3.0), (0.015, 4.0), (0.01, 100.0)],                # NO offered at 98c x3, 98.5c x4, 99c x100
         "no": [(0.97, 40.0)]}                                             # (not an offer to sell NO: ignored)


@pytest.mark.parametrize("b, side, limit, contracts, filled, cost", [
    (YES_UP, "yes", 0.97, 10, 10, 2 * 0.96 + 5 * 0.965 + 3 * 0.97),     # cheapest first, up the book
    (YES_UP, "yes", 0.97, 100, 17, 2 * 0.96 + 5 * 0.965 + 10 * 0.97),   # all it can up to the limit: 98c is past it
    (YES_UP, "yes", 0.96, 100, 2, 2 * 0.96),                            # a limit at the ask: the top only, the old rule
    (YES_UP, "yes", 0.95, 10, 0, 0.0),                                  # nothing offered that cheap
    (NO_UP, "no", 0.99, 10, 10, 3 * 0.98 + 4 * 0.985 + 3 * 0.99),
    (NO_UP, "no", 0.985, 100, 7, 3 * 0.98 + 4 * 0.985),
])
def test_book_fill_walks_the_offers_cheapest_first_up_to_the_limit(b, side, limit, contracts, filled, cost):
    got_filled, got_cost = bot.book_fill(b, side, limit, contracts)
    assert got_filled == filled and got_cost == pytest.approx(cost, abs=1e-9)


def test_book_fill_sorts_the_offers_itself():
    shuffled = {"yes": [], "no": [(0.03, 10.0), (0.02, 50.0), (0.04, 2.0)]}   # YES at 97c, 98c, then 96c
    filled, cost = bot.book_fill(shuffled, "yes", 0.97, 3)
    assert filled == 3 and cost == pytest.approx(2 * 0.96 + 0.97)


def test_book_fill_takes_whole_contracts_at_each_level():
    b = {"yes": [], "no": [(0.04, 2.9), (0.035, 0.5), (0.03, 3.0), (0.025, 9.0)]}   # 96c x2.9, 96.5c x0.5, 97c x3, 97.5c
    filled, cost = bot.book_fill(b, "yes", 0.97, 10)
    assert filled == 5 and cost == pytest.approx(2 * 0.96 + 3 * 0.97)                # 2 whole, none, 3, past the limit
    assert filled == int(filled)
    assert bot.book_fill({"yes": [], "no": [(0.04, 2.9999999999)]}, "yes", 0.97, 10)[0] == 3   # float noise isn't a lost contract


@pytest.mark.parametrize("contracts", [0, 1, 2, 3, 7, 17])
def test_book_fill_stops_at_the_order_size(contracts):
    offers = [0.96] * 2 + [0.965] * 5 + [0.97] * 10 + [0.98] * 50
    filled, cost = bot.book_fill(YES_UP, "yes", 0.99, contracts)
    assert filled == contracts and cost == pytest.approx(sum(offers[:contracts]), abs=1e-9)


@pytest.mark.parametrize("b, side", [
    (None, "yes"), (None, "no"),                          # no book
    ({}, "yes"), ({"yes": [], "no": []}, "no"),           # an empty one
    ({"yes": [(0.95, 100.0)], "no": []}, "yes"),          # nobody selling YES
    ({"yes": [], "no": [(0.97, 40.0)]}, "no"),            # nobody selling NO
])
def test_book_fill_on_a_missing_or_empty_book_is_nothing(b, side):
    assert bot.book_fill(b, side, 0.99, 3) == (0.0, 0.0)


@pytest.mark.parametrize("b, side, limit, filled", [
    ({"yes": [], "no": [(0.03, 5.0)]}, "yes", 0.97, 3),     # YES offered at exactly the 97c limit: taken
    ({"yes": [], "no": [(0.029, 5.0)]}, "yes", 0.97, 0),    # at 97.1c, a tenth of a cent over: not
    ({"yes": [(0.01, 5.0)], "no": []}, "no", 0.99, 3),      # NO offered at exactly 99c: taken
    ({"yes": [(0.009, 5.0)], "no": []}, "no", 0.99, 0),     # at 99.1c: not
    ({"yes": [], "no": [(0.001, 5.0)]}, "yes", 0.999, 3),   # at the 99.9c cap: taken
])
def test_book_fill_takes_an_offer_at_the_limit_but_not_a_tenth_of_a_cent_over(b, side, limit, filled):
    assert bot.book_fill(b, side, limit, 3)[0] == filled
    assert bot.book_fill(b, side, bot.limit_for(round(limit - 0.01, 4)), 3)[0] == filled   # the limit as the bot works it out


def test_book_fill_is_the_cheapest_whole_contracts_up_to_the_limit_on_any_book():
    """Brute force on random books: list every whole contract offered at or under the limit, cheapest first; the fill is
    the first `contracts` of them, and its cost their sum."""
    rng = random.Random(11)
    for _ in range(500):
        side = rng.choice(["yes", "no"])
        other = "no" if side == "yes" else "yes"
        bids = sorted(((rng.randint(1, 120) / 1000, rng.choice([0.5, 1.0, 2.0, 2.9, 7.0, 40.0]))
                       for _ in range(rng.randint(0, 6))), reverse=True)
        limit, contracts = rng.randint(900, 999) / 1000, rng.randint(1, 60)
        offers = sorted(p for bid, size in bids for p in [round(1 - bid, 4)] * math.floor(size + 1e-9) if p <= limit + 1e-9)
        filled, cost = bot.book_fill({side: [(0.5, 10.0)], other: bids}, side, limit, contracts)
        assert filled == len(offers[:contracts]) and cost == pytest.approx(sum(offers[:contracts]), abs=1e-9), (bids, limit)


# ------------------------------------------------------------------ a dry run's fills
def test_a_dry_run_fills_up_the_book_to_the_limit(env):
    """1 contract offered at the 96c it saw, 1 at 96.5c, 5 at 97c: the old rule got 1, the 97c limit gets all 3."""
    b = {"yes": [(0.95, 100.0)], "no": [(0.04, 1.0), (0.035, 1.0), (0.03, 5.0), (0.02, 50.0)]}
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    r = bets(env)[BTC]
    paid = 0.96 + 0.965 + 0.97
    assert r["contracts"] == 3 and r["cost"] == pytest.approx(paid) and r["price"] == pytest.approx(paid / 3)
    assert r["fee"] == bot.taker_fee(3, paid / 3)
    assert decisions(env)[BTC][1] == "would buy YES 3 at 96.5c ($3.00 a bet)"


def test_a_dry_run_stops_at_the_limit(env):
    b = {"yes": [(0.95, 100.0)], "no": [(0.04, 1.0), (0.03, 1.0), (0.02, 50.0)]}   # 96c, 97c, then 98c: past the limit
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    r = bets(env)[BTC]
    assert r["contracts"] == 2 and r["cost"] == pytest.approx(0.96 + 0.97)


def test_a_dry_run_no_bet_fills_up_the_book_to_the_limit(env):
    b = {"yes": [(0.02, 1.0), (0.015, 1.0), (0.01, 10.0), (0.005, 50.0)], "no": [(0.97, 40.0)]}   # NO at 98c, 98.5c, 99c, 99.5c
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(GOLD, b)])
    r = bets(env)[GOLD]
    assert (r["side"], r["contracts"]) == ("no", 3) and r["cost"] == pytest.approx(0.98 + 0.985 + 0.99)


def test_a_dry_runs_fee_is_on_the_average_price_it_paid(env):
    """156 contracts: 50 at 96c, 50 at 96.5c, 56 at 97c. Kalshi's fee on the average, 96.52c, is 37c (at 96c it would be
    42c, at 97c 32c). $150 is 1.5% of $10,000."""
    start(env, 10_000.0)
    b = {"yes": [(0.95, 100.0)], "no": [(0.04, 50.0), (0.035, 50.0), (0.03, 200.0)]}
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    r = bets(env)[BTC]
    paid = 50 * 0.96 + 50 * 0.965 + 56 * 0.97
    assert r["contracts"] == 156 and r["cost"] == pytest.approx(paid)
    assert r["fee"] == pytest.approx(0.37) and bot.taker_fee(156, paid / 156) == pytest.approx(0.37)


def test_a_dry_run_with_nothing_offered_up_to_the_limit_places_no_bet(env):
    b = {"yes": [(0.95, 100.0)], "no": [(0.04, 0.9), (0.02, 50.0)]}   # 0.9 of a contract at 96c, then 98c: past the limit
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    assert decisions(env)[BTC] == ("skip", "not filled: nobody selling at that price") and not bets(env)


@pytest.mark.parametrize("extra", [{}, {"book": None}])
def test_a_dry_run_without_a_book_fills_the_size_at_the_ask_it_saw(env, extra):
    """place() called on a market with no book falls back to the old rule: the size offered at the ask it saw."""
    m = {"ticker": BTC, "series": "KXBTC15M", "open": W, "close": W + 900, **extra}
    b = bot_for(FakeKalshi(), env, False)
    assert b.place(ENTRY, m, "yes", 0.96, 3, 3.0, 1, 2.0, 0.95, 0.96) is True   # (now, m, side, top, contracts, stake, n, top_size, yb, ya)
    r = bets(env)[BTC]
    assert r["contracts"] == 2 and r["cost"] == pytest.approx(2 * 0.96) and r["fee"] == bot.taker_fee(2, 0.96)


# ------------------------------------------------------------------ the fills table
OLD_LEDGER = """
CREATE TABLE bets (
    id INTEGER PRIMARY KEY, ticker TEXT UNIQUE, series TEXT, window_open REAL, close_ts REAL,
    side TEXT, price REAL, contracts REAL, cost REAL, fee REAL, placed_ts REAL,
    order_id TEXT, client_order_id TEXT, status TEXT, result TEXT, payout REAL, pnl REAL, settled_ts REAL);
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY, ts REAL, ticker TEXT UNIQUE, series TEXT, yes_bid REAL, yes_ask REAL,
    fav_side TEXT, fav_price REAL, action TEXT, reason TEXT);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY, ts REAL, ticker TEXT, client_order_id TEXT, request TEXT, http_status INTEGER, response TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
INSERT INTO meta VALUES ('start', '400.0');
INSERT INTO decisions (ts, ticker, action, reason) VALUES (1, 'KXBTC15M-OLD', 'bet', 'bought YES 3 at 96.0c');
"""


def columns(db, table):
    return [r[1] for r in db.execute(f"PRAGMA table_info({table})")]


def test_connect_makes_a_fills_table_one_row_per_trade(tmp_path):
    db = bot.connect(str(tmp_path / "x.db"))
    assert columns(db, "fills") == ["id", "trade_id", "order_id", "ticker", "side", "price", "count", "fee", "ts"]
    db.execute("INSERT INTO fills (trade_id) VALUES ('t1')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO fills (trade_id) VALUES ('t1')")


def test_a_ledger_from_before_the_fills_table_gains_it_on_the_next_start(tmp_path):
    path = str(tmp_path / "live-prod.db")
    old = sqlite3.connect(path)
    old.executescript(OLD_LEDGER)
    old.close()
    db = bot.connect(path)
    assert "fills" in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert bot.get_meta(db, "start") == "400.0"                                     # everything else kept
    assert db.execute("SELECT reason FROM decisions").fetchone()[0] == "bought YES 3 at 96.0c"
    db.execute("INSERT INTO fills (trade_id) VALUES ('t1')")
    db.commit()
    db.close()
    again = bot.connect(path)                                                        # and a later start keeps its rows
    assert again.execute("SELECT trade_id FROM fills").fetchall()[0][0] == "t1"
    again.close()


def test_fills_for_keeps_every_fill_it_counts_once(env):
    t = "2026-09-28T16:08:07Z"
    fake = Scripted(fills=lambda p: {"fills": [
        kfill(1, 0.96, trade_id="t1", order_id="o1", ticker=BTC, created_time=t),
        kfill(2, 0.965, fee="0.0200", trade_id="t2", order_id="o1", ticker=BTC, created_time=t)]})
    b = bot.Bot(fake, env, True)
    c, cost, fee = b.fills_for("yes", order_id="o1")
    assert (c, cost, fee) == (3.0, pytest.approx(0.96 + 1.93), pytest.approx(0.03))   # what it returns is unchanged
    want = [{"trade_id": "t1", "order_id": "o1", "ticker": BTC, "side": "yes", "price": 0.96, "count": 1.0, "fee": 0.01, "ts": bot.ts(t)},
            {"trade_id": "t2", "order_id": "o1", "ticker": BTC, "side": "yes", "price": 0.965, "count": 2.0, "fee": 0.02, "ts": bot.ts(t)}]
    assert kept(env) == want
    assert env.in_transaction                     # not committed inside: the step loop's commit saves it
    assert b.fills_for("yes", order_id="o1") == (c, cost, fee)    # the same fills read again (it looks up to 3 times) ...
    assert kept(env) == want                                      # ... add nothing


def test_fills_for_keeps_a_no_fill_at_the_no_price(env):
    fake = Scripted(fills=lambda p: {"fills": [kfill(3, 0.015, side="no", fee=None, trade_id="t1", order_id="o1", ticker=GOLD)]})
    assert bot.Bot(fake, env, True).fills_for("no", order_id="o1") == (3.0, pytest.approx(3 * 0.985), 0.0)
    assert kept(env) == [{"trade_id": "t1", "order_id": "o1", "ticker": GOLD, "side": "no", "price": 0.985, "count": 3.0,
                          "fee": 0.0, "ts": None}]     # no fee_cost: 0; no created_time: no time


def test_fills_for_keeps_only_its_own_side_and_fills_it_can_tell_apart(env):
    no_side = {k: v for k, v in kfill(1, 0.95, trade_id="t4").items() if k != "outcome_side"}
    fake = Scripted(fills=lambda p: {"fills": [
        kfill(5, 0.50, side="no", trade_id="t-other"),   # the other side: not counted, not kept
        kfill(1, 0.96),                                  # no trade_id or fill_id: counted, but nothing to key it by
        kfill(2, 0.97, fill_id="f2"),                    # a fill_id stands in for a missing trade_id
        no_side]})                                       # no outcome_side counts as its own side, so it's kept
    got = bot.Bot(fake, env, True).fills_for("yes", order_id="o1", ticker=BTC)
    assert got == (pytest.approx(4.0), pytest.approx(0.96 + 1.94 + 0.95), pytest.approx(0.03))
    assert [(r["trade_id"], r["count"], r["price"]) for r in kept(env)] == [("f2", 2.0, 0.97), ("t4", 1.0, 0.95)]


def test_fills_for_fills_in_the_order_and_market_it_asked_about(env):
    fake = Scripted(fills=lambda p: {"fills": [
        kfill(1, trade_id="t1"),                                                    # neither: the arguments
        kfill(1, trade_id="t2", order_id="o7", market_ticker="KXBTC15M-B"),         # its own order; market_ticker
        kfill(1, trade_id="t3", ticker="KXBTC15M-C", market_ticker="KXBTC15M-D")]})  # ticker before market_ticker
    bot.Bot(fake, env, True).fills_for("yes", order_id="o1", ticker=BTC)
    assert [(r["trade_id"], r["order_id"], r["ticker"]) for r in kept(env)] == [
        ("t1", "o1", BTC), ("t2", "o7", "KXBTC15M-B"), ("t3", "o1", "KXBTC15M-C")]


def test_fills_for_keeps_nothing_when_kalshi_cant_be_read(env):
    assert bot.Bot(Scripted(fills=lambda p: None), env, True).fills_for("yes", ticker=BTC) == (None, None, None)
    assert kept(env) == []


def test_a_live_orders_fills_are_kept_in_the_ledger(env):
    t = "2026-09-28T16:08:07Z"
    fills = [kfill(1, 0.96, trade_id="t1", order_id="o1", ticker=BTC, created_time=t),
             kfill(2, 0.97, trade_id="t2", order_id="o1", ticker=BTC, created_time=t)]   # one at the ask it saw, two over
    bot_for(filled_in_full(fills), env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert [(r["trade_id"], r["order_id"], r["ticker"], r["side"], r["price"], r["count"]) for r in kept(env)] == [
        ("t1", "o1", BTC, "yes", 0.96, 1.0), ("t2", "o1", BTC, "yes", 0.97, 2.0)]
    assert bot.halt_info() is None and bets(env)[BTC]["price"] == pytest.approx((0.96 + 1.94) / 3)


def test_fills_looked_up_three_times_are_kept_once(env, slept):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}),
                    fills=lambda p: {"fills": [kfill(2, 0.965, trade_id="t1", order_id="o1", ticker=BTC)]})   # 2 of 3 ever show
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert len(fake.fill_calls) == 3 and [r["trade_id"] for r in kept(env)] == ["t1"]
    assert bets(env)[BTC]["cost"] == pytest.approx(3 * 0.97)      # the order's own count, at the limit


class Traded(FakeKalshi):
    """FakeKalshi whose fills carry the IDs Kalshi's do."""

    def fills(self, order_id=None, ticker=None, limit=100):
        d = super().fills(order_id, ticker, limit)
        for f in d["fills"]:
            f.update(trade_id=f"t-{order_id}", order_id=order_id, ticker=self.orders[int(order_id[1:]) - 1]["ticker"])
        return d


def test_the_step_loop_saves_the_fills(env, tmp_path):
    run(env, Traded(), live=True)
    other = sqlite3.connect(str(tmp_path / "test.db"))          # what another program (the dashboard) would read
    got = sorted(other.execute("SELECT trade_id, ticker, side, price FROM fills").fetchall())
    other.close()
    assert got == [("t-o1", BTC, "yes", 0.97), ("t-o2", GOLD, "no", 0.99)]   # FakeKalshi fills at the limit


# ------------------------------------------------------------------ what it records
def test_the_decision_keeps_the_ask_it_saw_and_the_bet_the_price_it_paid(env):
    fills = {"o1": [fill(3, 0.97)], "o2": [fill(3, 0.01, side="no")]}
    fake = Scripted(order=lambda body, n: (201, {"order_id": f"o{n}", "fill_count": "3.00"}),
                    fills=lambda p: {"fills": fills[p["order_id"]]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert bot.halt_info() is None
    d = {r["ticker"]: r for r in env.execute("SELECT * FROM decisions")}
    assert (d[BTC]["fav_side"], d[BTC]["fav_price"], d[BTC]["yes_ask"]) == ("yes", 0.96, 0.96)
    assert (d[GOLD]["fav_side"], d[GOLD]["fav_price"]) == ("no", 0.98)
    assert bets(env)[BTC]["price"] == pytest.approx(0.97) and bets(env)[GOLD]["price"] == pytest.approx(0.99)
    assert d[BTC]["reason"] == "bought YES 3 at 97.0c ($3.00 a bet)"


# ------------------------------------------------------------------ the docs
# Live the limit is 1c over the ask it saw (LIMIT_UP is 0.01), so the docs say what the live bot does; test_shadow.py
# checks they also say the +1¢ ran on paper first.
def test_the_module_docstring_says_it_pays_at_most_1c_over_what_it_saw():
    doc = " ".join(bot.__doc__.split())
    assert "1c over the best ask it just saw" in doc and "never pays more than that limit" in doc
    assert "at the best price it just saw on the book, so it never pays more" not in doc


def test_the_readme_says_it_pays_at_most_1c_over_what_it_saw():
    if not os.path.exists(README):
        pytest.skip("README.md isn't beside the code in this copy (copy it in to run this check)")
    with open(README, encoding="utf-8") as fh:
        text = fh.read()
    safety = text.split("## Safety", 1)[1].split("\n## ", 1)[0]
    assert "Pays at most 1¢ over the ask it saw" in safety
    assert "Never pays more than it saw" not in text
