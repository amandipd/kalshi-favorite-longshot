"""The Bot, decision by decision: every reason it skips, every way an order can come back, settlement, and
the step loop's timing. Nothing here touches the network or an account.

    python -m pytest tests/test_flow.py -q
"""
import collections
import json

import pytest
import requests

from kalshi_bot import bot
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, fake_bet, start_ledger
from test_day_drop import Many, open_bet


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


BTC, GOLD, ETH = "KXBTC15M-A", "KXGOLD15M-A", "KXETH15M-A"


@pytest.fixture(autouse=True)
def slept(monkeypatch):
    """No test waits on the clock: sleeps are recorded, not slept."""
    calls = []
    monkeypatch.setattr(bot.time, "sleep", lambda s: calls.append(s))
    return calls


def book(yes_bid, yes_ask, ask_size=50.0, bid_size=100.0):
    """An order book with this YES bid and ask (the ask is the best NO bid seen from the other side)."""
    return {"yes": [(yes_bid, bid_size)], "no": [(round(1 - yes_ask, 4), ask_size)]}


def mk(ticker, b, w=W):
    return {"ticker": ticker, "series": ticker.split("-")[0], "open": w, "close": w + 900, "book": b}


YES96 = book(0.95, 0.96)   # a YES favourite at 96c
NO98 = book(0.02, 0.03)    # a NO favourite at 98c


def bot_for(fake, db, live, trading=True):
    b = bot.Bot(fake, db, live)
    b.load_catalog()
    b.trading = trading
    return b


def bets(db):
    return {r["ticker"]: r for r in db.execute("SELECT * FROM bets")}


class Scripted(FakeKalshi):
    """A fake whose order responses and fills a test writes out itself."""

    def __init__(self, order=None, fills=None, raises=None, **kw):
        super().__init__(**kw)
        self.order, self.fills_data, self.raises, self.fill_calls = order, fills, raises, []

    def create_order(self, body):
        self.orders.append(body)
        if self.raises:
            raise self.raises
        if self.order is None:  # by default, fill in full
            return 201, {"order_id": f"o{len(self.orders)}", "fill_count": body["count"] + ".00"}
        return self.order(body, len(self.orders)) if callable(self.order) else self.order

    def fills(self, **p):
        self.fill_calls.append(p)
        return self.fills_data(p) if callable(self.fills_data) else self.fills_data


def fill(count, yes_price=0.96, side="yes", fee="0.0100"):
    return {"outcome_side": side, "count_fp": f"{count}.00", "yes_price_dollars": f"{yes_price:.4f}",
            "no_price_dollars": f"{1 - yes_price:.4f}", "fee_cost": fee}


# ------------------------------------------------------------------ what it skips, and why
def test_a_market_without_a_book_is_skipped(env):
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, None)])
    assert decisions(env)[BTC] == ("skip", "order book unavailable") and not bets(env)


@pytest.mark.parametrize("b", [{"yes": [], "no": []}, {"yes": [(0.9, 1.0)], "no": []}, {"yes": [], "no": [(0.1, 1.0)]}])
def test_a_one_sided_or_empty_book_has_no_quotes(env, b):
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    assert decisions(env)[BTC] == ("skip", "no quotes")


@pytest.mark.parametrize("b, action", [
    (book(0.91, 0.92), "bet"),       # exactly 92c: in
    (book(0.91, 0.919), "skip"),     # 91.9c: out
    (book(0.89, 0.90), "skip"),      # 90c: out since the floor rose to 92c on Oct 14
    (book(0.99, 0.999), "bet"),      # exactly 99.9c: in
    (book(0.99, 0.9991), "skip"),    # 99.91c: out
    (book(0.08, 0.09), "bet"),       # a NO favourite at 92c: in
    (book(0.081, 0.09), "skip"),     # a NO favourite at 91.9c: out
    (book(0.10, 0.11), "skip"),      # a NO favourite at 90c: out
    (book(0.50, 0.51), "skip"),      # a coin flip
])
def test_the_92_to_99_9_cent_band(env, b, action):
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, b)])
    assert decisions(env)[BTC][0] == action
    if action == "skip":
        assert "outside 92-99.9c" in decisions(env)[BTC][1]


def test_a_market_it_already_decided_is_left_alone(env):
    fake = FakeKalshi()
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    b.decide_window(ENTRY + 5, W, [mk(BTC, YES96)])
    assert len(fake.orders) == 1
    assert env.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1


def test_a_halt_logs_bets_as_halted_but_still_notes_the_rest(env):
    bot.set_halt(ENTRY - 60, "testing", "you")
    fake = FakeKalshi()
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(ETH, book(0.60, 0.61))])
    assert decisions(env) == {BTC: ("halted", "halted: testing"), ETH: ("skip", "favorite at 61.0c is outside 92-99.9c")}
    assert fake.orders == []


def test_a_fed_blackout_places_nothing_even_live(env):
    w = bot.ts("2026-10-28T18:30:00Z")
    fake = FakeKalshi()
    bot_for(fake, env, True).decide_window(w + 485, w, [mk(BTC, YES96, w)])
    assert decisions(env)[BTC] == ("skip", "Fed decision blackout") and fake.orders == []


def test_paused_or_unknown_trading_status_skips_the_window(env):
    fake = FakeKalshi()
    bot_for(fake, env, True, trading=False).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "Kalshi has trading paused") and fake.orders == []
    bot_for(fake, env, True, trading=None).decide_window(ENTRY, W, [mk(GOLD, NO98)])  # couldn't tell: Kalshi may be down
    assert decisions(env)[GOLD] == ("skip", "couldn't confirm Kalshi is trading: its exchange status is unreadable")
    assert fake.orders == []


def test_a_bet_under_a_dollar_is_skipped(env):
    bot.set_start(env, 20.0)
    env.commit()
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "bet size $0.30 is under the $1 minimum")   # 1.5% of $20


def test_live_needs_a_readable_balance_but_a_dry_run_doesnt(env):
    class NoBalance(FakeKalshi):
        def balance(self):
            return None
    fake = NoBalance()
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "couldn't read the account balance") and fake.orders == []
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(GOLD, NO98)])
    assert decisions(env)[GOLD][0] == "bet"


def test_at_most_20_orders_a_window(env):
    bot.set_start(env, 1000.0)
    env.commit()
    fake = Many(25)
    b = bot_for(fake, env, False)
    b.decide_window(ENTRY, W, [mk(f"{s}-A", YES96) for s in fake.names])
    d = decisions(env)
    assert sum(a == "bet" for a, _ in d.values()) == bot.MAX_ORDERS_PER_WINDOW == 20
    assert sum(r == "order limit reached" for _, r in d.values()) == 5


def test_at_most_600_orders_a_day(env):
    for i in range(100, 100 + 599):   # 599 bets in the last day: room for exactly one more
        fake_bet(env, i, W - 900, False, 0.0, settled=W - 5)
    b = bot_for(FakeKalshi(), env, False)
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert decisions(env)[BTC][0] == "bet" and decisions(env)[GOLD] == ("skip", "order limit reached")


def test_bets_older_than_a_day_dont_count_toward_the_daily_limit(env):
    for i in range(100, 100 + 600):
        fake_bet(env, i, W - 2 * 86400, False, 0.0, settled=W - 86400 - 5)
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC][0] == "bet"


def test_cash_tied_up_in_open_bets_isnt_bet_again(env):
    open_bet(env, "KXBTC15M-OLD", W - 900, contracts=206, cost=198.0, fee=0.01)   # $1.99 of $200 left
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "bankroll too low") and not [t for t in bets(env) if t == BTC]


def test_the_real_section_cash_runs_out_mid_window(env):
    fake = FakeKalshi()
    fake.crypto_cash = "3.5000"   # enough for BTC (2.92: 3 at its 97c limit + 1c fee) but not then GOLD (2.98: 3 at 99c + 1c)
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    d = decisions(env)
    assert d[BTC][0] == "bet"
    assert d[GOLD][0] == "skip" and d[GOLD][1].startswith("only $0.58 in Kalshi's Crypto & Commodities section")
    assert [o["ticker"] for o in fake.orders] == [BTC]


@pytest.mark.parametrize("n, capped", [(6, False), (7, True)])
def test_the_log_says_when_the_window_cap_shrank_the_bets(env, n, capped):
    fake = Many(n)
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(f"{s}-A", YES96) for s in fake.names])
    assert all(("window cap" in r) is capped for a, r in decisions(env).values() if a == "bet")


def test_every_qualifier_shares_the_window_cap_even_if_it_then_skips(env):
    """Bets are sized by how many qualified, not how many end up placed: 10 qualifiers, $2 each."""
    fake = Many(10)
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(f"{s}-A", YES96) for s in fake.names])
    assert {round(r["cost"], 2) for r in bets(env).values()} == {1.92}  # 2 contracts at 96c, from a $2.00 stake


# ------------------------------------------------------------------ a dry run's fills
@pytest.mark.parametrize("ask_size, contracts", [(50.0, 3), (3.0, 3), (2.9, 2), (1.0, 1)])
def test_a_dry_run_fills_no_more_than_the_book_offers(env, ask_size, contracts):
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, book(0.95, 0.96, ask_size=ask_size))])
    assert bets(env)[BTC]["contracts"] == contracts


def test_a_dry_run_that_the_book_cant_fill_places_no_bet(env):
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(BTC, book(0.95, 0.96, ask_size=0.9))])
    assert decisions(env)[BTC] == ("skip", "not filled: nobody selling at that price") and not bets(env)


def test_a_dry_run_bet_is_recorded_in_full(env):
    bot_for(FakeKalshi(), env, False).decide_window(ENTRY, W, [mk(GOLD, NO98)])
    r = bets(env)[GOLD]
    assert (r["side"], r["contracts"], r["status"], r["order_id"]) == ("no", 3, "open", None)
    assert r["price"] == pytest.approx(0.98) and r["cost"] == pytest.approx(2.94) and r["fee"] == bot.taker_fee(3, 0.98)
    assert (r["window_open"], r["close_ts"], r["placed_ts"]) == (W, W + 900, ENTRY)
    assert r["client_order_id"] == bot.client_order_id(GOLD)
    assert decisions(env)[GOLD][1] == "would buy NO 3 at 98.0c ($3.00 a bet)"


def test_the_live_log_says_bought(env):
    bot_for(FakeKalshi(), env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC][1] == "bought YES 3 at 97.0c ($3.00 a bet)"   # the fake fills at the order's limit: 97c


# ------------------------------------------------------------------ every way a live order can come back
def test_the_request_and_the_response_are_saved_for_every_order(env):
    fake = FakeKalshi()
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    row = env.execute("SELECT * FROM orders").fetchone()
    assert (row["ticker"], row["http_status"], row["ts"]) == (BTC, 201, ENTRY)
    assert json.loads(row["request"]) == fake.orders[0] and json.loads(row["response"])["order_id"] == "o1"


def test_a_refused_order_is_logged_and_counted_not_retried(env):
    fake = Scripted(order=(400, {"error": {"code": "insufficient_balance"}}))
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    a, why = decisions(env)[BTC]
    assert a == "error" and "order failed (400)" in why and "insufficient_balance" in why
    assert len(fake.orders) == 1 and b.errors == 1 and not bets(env)
    assert env.execute("SELECT http_status FROM orders").fetchone()[0] == 400


def test_a_success_resets_the_failed_order_count(env):
    fake = Scripted(order=lambda body, n: (400, {"error": "x"}) if n == 1 else (201, {"order_id": f"o{n}", "fill_count": "3.00"}),
                    fills=lambda p: {"fills": [fill(3)]})
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, book(0.95, 0.96))])
    assert b.errors == 0 and list(bets(env)) == [GOLD] and bot.halt_info() is None


@pytest.mark.parametrize("data", ["gateway timeout", None, ["not", "a", "dict"]])
def test_a_success_status_with_a_body_that_isnt_an_order_is_a_failure(env, data):
    fake = Scripted(order=(201, data))
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC][0] == "error" and b.errors == 1 and not bets(env)


def test_status_200_is_as_good_as_201(env):
    fake = Scripted(order=(200, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": [fill(3)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bets(env)[BTC]["contracts"] == 3


def test_an_immediate_or_cancel_order_that_fills_nothing_is_a_skip_not_a_failure(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "0.00"}))
    b = bot_for(fake, env, True)
    b.errors = 2                                      # two failures already in a row ...
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "not filled: nobody selling at that price")
    assert not bets(env) and fake.fill_calls == [] and b.errors == 0  # ... but this wasn't one, and needed no fills lookup
    assert bot.halt_info() is None


def test_a_partial_fill_records_only_what_filled(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "2.00"}), fills=lambda p: {"fills": [fill(2)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    r = bets(env)[BTC]
    assert r["contracts"] == 2 and r["cost"] == pytest.approx(1.92) and r["order_id"] == "o1"
    assert bot.halt_info() is None


def test_fills_are_averaged_across_prices_and_fees_add_up(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}),
                    fills=lambda p: {"fills": [fill(1, 0.95, fee="0.0100"), fill(2, 0.96, fee="0.0150")]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    r = bets(env)[BTC]
    assert r["contracts"] == 3 and r["cost"] == pytest.approx(0.95 + 2 * 0.96) and r["fee"] == pytest.approx(0.025)
    assert r["price"] == pytest.approx((0.95 + 1.92) / 3)


def test_a_fill_cheaper_than_the_limit_is_fine_and_recorded_at_the_real_price(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": [fill(3, 0.95)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bot.halt_info() is None and bets(env)[BTC]["price"] == pytest.approx(0.95)


def test_a_no_bet_reads_the_no_price_of_the_fill(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": [fill(3, 0.02, side="no")]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(GOLD, NO98)])
    r = bets(env)[GOLD]
    assert r["side"] == "no" and r["price"] == pytest.approx(0.98) and bot.halt_info() is None


def test_a_fill_bigger_than_the_order_halts_but_is_still_recorded(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "4.00"}), fills=lambda p: {"fills": [fill(4)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert "unexpected fill" in bot.halt_info()["reason"] and bets(env)[BTC]["contracts"] == 4  # the position is real


@pytest.mark.parametrize("price", [0.9701, 0.98, 0.99])   # the limit is 1c over the 96c it saw (LIMIT_UP; test_limit_up.py)
def test_any_fill_dearer_than_the_limit_halts(env, price):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": [fill(3, price)]})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert "unexpected fill" in bot.halt_info()["reason"]


def test_late_fills_are_polled_three_times_then_counted_at_the_limit_price(env, slept):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: {"fills": [fill(2)]})  # never shows all 3
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert len(fake.fill_calls) == 3 and slept == [0.5] * 3
    r = bets(env)[BTC]   # at the limit: 1c over the 96c it saw
    assert r["contracts"] == 3 and r["cost"] == pytest.approx(3 * 0.97) and r["fee"] == bot.taker_fee(3, 0.97)


def test_fills_that_show_up_on_the_second_look_end_the_wait(env, slept):
    seen = []
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}),
                    fills=lambda p: (seen.append(p), {"fills": [] if len(seen) == 1 else [fill(3, 0.955, fee="0.0200")]})[1])
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert len(seen) == 2 and slept == [0.5]
    assert bets(env)[BTC]["price"] == pytest.approx(0.955) and bets(env)[BTC]["fee"] == pytest.approx(0.02)


def test_fills_that_cant_be_read_fall_back_to_the_orders_own_count(env):
    fake = Scripted(order=(201, {"order_id": "o1", "fill_count": "3.00"}), fills=lambda p: None)
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bets(env)[BTC]["contracts"] == 3 and bot.halt_info() is None


# ------------------------------------------------------------------ a dropped connection mid-order
def dropped(fills):
    return Scripted(raises=requests.ConnectionError("connection reset"), fills=fills)


def test_a_dropped_connection_whose_order_filled_is_still_recorded(env):
    fake = dropped(lambda p: {"fills": [fill(3)]})
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert bets(env)[BTC]["contracts"] == 3            # the money is spent, so the books show it
    assert fake.fill_calls[0]["ticker"] == BTC and "order_id" not in fake.fill_calls[0]  # found by market: it has no order ID
    row = env.execute("SELECT http_status, response FROM orders").fetchone()
    assert row["http_status"] is None and "connection reset" in json.loads(row["response"])
    assert b.errors == 1                               # but it counts toward the three-in-a-row halt


def test_a_dropped_connection_whose_order_never_arrived_places_no_bet(env):
    fake = dropped(lambda p: {"fills": []})
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert not bets(env) and decisions(env)[BTC][0] == "error" and b.errors == 1


def test_a_dropped_connection_and_unreadable_fills_places_no_bet(env):
    fake = dropped(lambda p: None)
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert not bets(env) and decisions(env)[BTC][0] == "error"


def test_a_market_that_errored_is_never_ordered_again(env):
    fake = dropped(lambda p: {"fills": []})
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    b.decide_window(ENTRY + 3, W, [mk(BTC, YES96)])
    assert len(fake.orders) == 1


def test_three_dropped_connections_in_a_row_halt(env):
    fake = dropped(lambda p: {"fills": []})
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(f"KXBTC15M-{i}", YES96) for i in range(5)])
    assert len(fake.orders) == bot.MAX_ORDER_ERRORS and "3 orders failed in a row" in bot.halt_info()["reason"]


# ------------------------------------------------------------------ fills_for
def test_fills_for_looks_up_by_order_before_market_and_sums_one_side(env):   # a ledger: it keeps the fills it counts
    fake = Scripted(fills=lambda p: {"fills": [fill(1, 0.95), fill(2, 0.96, fee="0.0200"), fill(5, 0.50, side="no"),
                                              {"count_fp": "1.00", "yes_price_dollars": "0.9700", "no_price_dollars": "0.0300"}]})
    b = bot.Bot(fake, env, True)
    c, cost, fee = b.fills_for("yes", order_id="o9", ticker="T")
    assert (c, cost, fee) == (pytest.approx(4.0), pytest.approx(0.95 + 1.92 + 0.97), pytest.approx(0.03))  # no outcome_side counts as ours
    assert fake.fill_calls == [{"order_id": "o9", "limit": 100}]
    b.fills_for("yes", ticker="T")
    assert fake.fill_calls[-1] == {"ticker": "T", "limit": 100}


def test_fills_for_prices_a_no_bet_at_the_no_price(env):
    fake = Scripted(fills=lambda p: {"fills": [fill(2, 0.02, side="no", fee=None)]})
    c, cost, fee = bot.Bot(fake, env, True).fills_for("no", ticker="T")
    assert (c, cost, fee) == (2.0, pytest.approx(2 * 0.98), 0.0)


def test_fills_for_says_none_when_kalshi_cant_be_read(env):
    assert bot.Bot(Scripted(fills=lambda p: None), env, True).fills_for("yes", ticker="T") == (None, None, None)
    assert bot.Bot(Scripted(fills=lambda p: {}), env, True).fills_for("yes", ticker="T") == (0.0, 0.0, 0.0)


# ------------------------------------------------------------------ settlement
class Settling(FakeKalshi):
    """Answers the bot's settlement lookups from `results`: ticker -> (result, settlement time or None)."""

    def __init__(self):
        super().__init__()
        self.lookups, self.answers = [], {}

    def markets(self, **p):
        self.lookups.append(p["tickers"].split(","))
        return {"markets": [{"ticker": t, "result": r, "settlement_ts": None if s is None else bot.iso(s)}
                            for t, (r, s) in self.answers.items() if t in p["tickers"].split(",")]}


def test_settle_pays_winners_and_loses_losers_including_fees(env):
    open_bet(env, "KXBTC15M-Y", W, contracts=3, cost=2.88, fee=0.01)
    open_bet(env, "KXBTC15M-N", W, contracts=3, cost=2.88, fee=0.01)
    open_bet(env, "KXGOLD15M-Y", W, contracts=3, cost=2.94, fee=0.02, side="no")
    open_bet(env, "KXGOLD15M-N", W, contracts=3, cost=2.94, fee=0.02, side="no")
    fake = Settling()
    fake.answers = {"KXBTC15M-Y": ("yes", W + 905), "KXBTC15M-N": ("no", W + 905),
                    "KXGOLD15M-Y": ("yes", W + 905), "KXGOLD15M-N": ("no", W + 905)}
    bot.Bot(fake, env, False).settle(W + 920)
    got = bets(env)
    assert (got["KXBTC15M-Y"]["status"], got["KXBTC15M-Y"]["payout"]) == ("won", 3.0)
    assert got["KXBTC15M-Y"]["pnl"] == pytest.approx(3 - 2.88 - 0.01) and got["KXBTC15M-Y"]["result"] == "yes"
    assert (got["KXBTC15M-N"]["status"], got["KXBTC15M-N"]["payout"]) == ("lost", 0.0)
    assert got["KXBTC15M-N"]["pnl"] == pytest.approx(-2.89)
    assert got["KXGOLD15M-N"]["status"] == "won" and got["KXGOLD15M-N"]["pnl"] == pytest.approx(3 - 2.94 - 0.02)
    assert got["KXGOLD15M-Y"]["status"] == "lost" and got["KXGOLD15M-Y"]["pnl"] == pytest.approx(-2.96)
    assert got["KXBTC15M-Y"]["settled_ts"] == W + 905


@pytest.mark.parametrize("answer", [("", None), (None, None), ("void", None), ("scalar", None)])
def test_a_market_without_a_yes_or_no_result_stays_open(env, answer):
    open_bet(env, "KXBTC15M-Y", W, 3, 2.88)
    fake = Settling()
    fake.answers = {"KXBTC15M-Y": answer}
    bot.Bot(fake, env, False).settle(W + 920)
    assert bets(env)["KXBTC15M-Y"]["status"] == "open"


def test_a_market_kalshi_doesnt_return_stays_open(env):
    open_bet(env, "KXBTC15M-Y", W, 3, 2.88)
    bot.Bot(Settling(), env, False).settle(W + 920)
    assert bets(env)["KXBTC15M-Y"]["status"] == "open"


def test_bets_still_running_arent_looked_up(env):
    open_bet(env, "KXBTC15M-Y", W, 3, 2.88)          # closes at W + 900
    fake = Settling()
    bot.Bot(fake, env, False).settle(W + 901)          # inside the two-second margin
    assert fake.lookups == []
    bot.Bot(fake, env, False).settle(W + 902)
    assert fake.lookups == [["KXBTC15M-Y"]]


def test_settled_bets_arent_looked_up_or_changed_again(env):
    fake_bet(env, 0, W, True, 0.5, settled=W + 905)
    fake = Settling()
    fake.answers = {"T-0": ("no", W + 999)}
    bot.Bot(fake, env, False).settle(W + 2000)
    assert fake.lookups == [] and bets(env)["T-0"]["status"] == "won" and bets(env)["T-0"]["pnl"] == 0.5


def test_settlement_time_falls_back_to_now_and_never_precedes_the_bet(env):
    open_bet(env, "KXBTC15M-A", W, 3, 2.88)
    open_bet(env, "KXBTC15M-B", W, 3, 2.88)
    fake = Settling()
    fake.answers = {"KXBTC15M-A": ("yes", None), "KXBTC15M-B": ("yes", W - 5000)}   # no time given / a time before the bet
    bot.Bot(fake, env, False).settle(W + 950)
    assert bets(env)["KXBTC15M-A"]["settled_ts"] == W + 950
    assert bets(env)["KXBTC15M-B"]["settled_ts"] == W + 480       # not before it was placed


def test_settle_asks_for_50_markets_at_a_time(env):
    for i in range(120):
        open_bet(env, f"KXBTC15M-{i:03d}", W, 3, 2.88)
    fake = Settling()
    fake.answers = {f"KXBTC15M-{i:03d}": ("yes", W + 905) for i in range(120)}
    bot.Bot(fake, env, False).settle(W + 920)
    assert [len(x) for x in fake.lookups] == [50, 50, 20]
    assert env.execute("SELECT COUNT(*) FROM bets WHERE status='won'").fetchone()[0] == 120


def test_settle_survives_kalshi_being_unreachable(env):
    open_bet(env, "KXBTC15M-Y", W, 3, 2.88)

    class Down(FakeKalshi):
        def markets(self, **p):
            return None
    bot.Bot(Down(), env, False).settle(W + 920)
    assert bets(env)["KXBTC15M-Y"]["status"] == "open"


# ------------------------------------------------------------------ the catalog and a window's markets
class Series(FakeKalshi):
    def __init__(self, listing):
        super().__init__()
        self.listing = listing

    def series(self):
        return self.listing


def test_the_catalog_keeps_only_15_minute_series_and_groups_them():
    b = bot.Bot(FakeKalshi(), None, False)
    assert b.load_catalog() is True
    assert b.universe == {"KXBTC15M": {"group": "crypto", "fee": 1.0}, "KXGOLD15M": {"group": "metals", "fee": 1.0},
                          "KXETH15M": {"group": "crypto", "fee": 1.0}, "KXCRYPTOLEAD15M": {"group": "coin race", "fee": 1.0}}


def test_the_catalog_drops_other_frequencies_test_series_and_reads_fee_multipliers():
    listing = {"series": [
        {"ticker": "KXBTC15M", "frequency": "fifteen_min", "category": "Crypto", "fee_multiplier": "0.5"},
        {"ticker": "KXBTCD", "frequency": "daily", "category": "Crypto"},
        {"ticker": "KXBTC15MTEST", "frequency": "fifteen_min", "category": "Crypto"},
        {"ticker": "KXWTI15M", "frequency": "fifteen_min", "category": None, "fee_multiplier": None},
    ]}
    b = bot.Bot(Series(listing), None, False)
    b.load_catalog()
    assert b.universe == {"KXBTC15M": {"group": "crypto", "fee": 0.5}, "KXWTI15M": {"group": "energy", "fee": 1.0}}


def test_a_failed_catalog_call_changes_nothing():
    b = bot.Bot(Series(None), None, False)
    b.universe = {"KXBTC15M": {"group": "crypto", "fee": 1.0}}
    assert b.load_catalog() is False and b.universe == {"KXBTC15M": {"group": "crypto", "fee": 1.0}}


def test_window_markets_lists_this_windows_traded_series_with_their_books(env):
    fake = FakeKalshi()
    ms = bot_for(fake, env, False).window_markets(W)
    assert sorted(m["ticker"] for m in ms) == [BTC, ETH, GOLD]      # not the coin race, which it never trades
    btc = next(m for m in ms if m["ticker"] == BTC)
    assert (btc["open"], btc["close"], btc["series"]) == (W, W + 900, "KXBTC15M")
    assert btc["book"] == {"yes": [(0.95, 100.0)], "no": [(0.04, 50.0)]}


def test_window_markets_ignores_other_windows(env):
    fake = FakeKalshi()
    fake.window = W + 900
    assert bot_for(fake, env, False).window_markets(W) == []


def test_window_markets_keeps_a_market_whose_book_wont_load(env):
    class NoBooks(FakeKalshi):
        def orderbook(self, ticker):
            return None
    ms = bot_for(NoBooks(), env, False).window_markets(W)
    assert len(ms) == 3 and all(m["book"] is None for m in ms)


def test_window_markets_survives_series_that_fail_to_list(env):
    class Flaky(FakeKalshi):
        def markets(self, **p):
            return None if p.get("series_ticker") == "KXGOLD15M" else super().markets(**p)
    assert sorted(m["ticker"] for m in bot_for(Flaky(), env, False).window_markets(W)) == [BTC, ETH]


# ------------------------------------------------------------------ the step loop
class Counting(FakeKalshi):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = collections.Counter()

    def series(self):
        self.calls["series"] += 1
        return super().series()

    def exchange_status(self):
        self.calls["status"] += 1
        return super().exchange_status()

    def orderbook(self, ticker):
        self.calls["book"] += 1
        return super().orderbook(ticker)


def test_the_catalog_is_fetched_once_an_hour(env):
    fake = Counting()
    b = bot.Bot(fake, env, False)
    b.step(W + 100)
    b.step(W + 200)
    b.step(W + 100 + bot.CATALOG_EVERY - 1)
    assert fake.calls["series"] == 1
    b.step(W + 100 + bot.CATALOG_EVERY + 1)
    assert fake.calls["series"] == 2


def test_a_failed_catalog_is_retried_on_the_next_step(env):
    class Late(Counting):
        def series(self):
            self.calls["series"] += 1
            return None if self.calls["series"] == 1 else FakeKalshi.series(self)
    fake = Late()
    b = bot.Bot(fake, env, False)
    b.step(W + 100)
    assert b.universe == {}
    b.step(W + 103)
    assert fake.calls["series"] == 2 and "KXBTC15M" in b.universe


def test_exchange_status_is_checked_every_minute(env):
    fake = Counting()
    b = bot.Bot(fake, env, False)
    b.step(W + 100)
    b.step(W + 130)
    assert fake.calls["status"] == 1 and b.trading is True
    b.step(W + 161)
    assert fake.calls["status"] == 2


def test_the_section_follows_the_status_and_survives_a_failed_check(env):
    class Moved(Counting):
        down = False

        def exchange_status(self):
            if self.down:
                return None
            s = super().exchange_status()
            s["exchange_index_statuses"][1]["exchange_index"] = 5
            return s
    fake = Moved()
    b = bot.Bot(fake, env, False)
    b.step(W + 100)
    assert b.section == 5
    fake.down = True
    b.step(W + 200)
    assert b.trading is None and b.section == 5   # unknown status: trading unknown, section kept


@pytest.mark.parametrize("second, enters", [(479, False), (480, True), (500, True), (525, True), (526, False), (0, False), (899, False)])
def test_it_only_enters_between_minute_8_and_45_seconds_after(env, second, enters):
    fake = Counting()
    bot.Bot(fake, env, False).step(W + second)
    assert (fake.calls["book"] > 0) is enters


def test_it_enters_each_window_once(env):
    fake = Counting()
    b = bot.Bot(fake, env, False)
    b.step(ENTRY)
    books = fake.calls["book"]
    assert books > 0
    b.step(ENTRY + 3)
    b.step(ENTRY + 6)
    assert fake.calls["book"] == books and env.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 2
    fake.window, fake.suffix = W + 900, "B"
    b.step(ENTRY + 900)
    assert fake.calls["book"] > books


def test_an_empty_listing_is_retried_within_the_entry_minute(env):
    fake = Counting()
    fake.window = W + 900                # nothing listed for the window it's asking about
    b = bot.Bot(fake, env, False)
    b.step(ENTRY)
    assert b.done_window is None and not bets(env)
    fake.window = W                      # Kalshi catches up
    b.step(ENTRY + 3)
    assert b.done_window == W and len(bets(env)) == 2


def test_the_step_writes_a_heartbeat_every_time(env):
    b = bot.Bot(FakeKalshi(), env, False)
    b.step(W + 100)
    assert float(bot.get_meta(env, "heartbeat")) == W + 100
    b.step(W + 103)
    assert float(bot.get_meta(env, "heartbeat")) == W + 103
    assert env.in_transaction is False   # committed: anything reading the database sees it


def test_the_step_settles_bets_before_it_decides(env):
    open_bet(env, "KXBTC15M-OLD", W - 900, 3, 2.88)
    fake = FakeKalshi()
    fake.results = {"KXBTC15M-OLD": "yes"}
    bot.Bot(fake, env, False).step(W + 50)
    assert bets(env)["KXBTC15M-OLD"]["status"] == "won"


def test_no_catalog_at_all_is_no_crash_and_no_orders(env):
    fake = Series(None)
    b = bot.Bot(fake, env, True)
    b.step(ENTRY)
    assert fake.orders == [] and b.universe == {} and b.done_window is None


def test_a_new_bot_starts_with_nothing_known(env):
    b = bot.Bot(FakeKalshi(), env, True)
    assert (b.universe, b.trading, b.section, b.errors, b.done_window) == ({}, None, 2, 0, None)
    assert b.live is True and bot.Bot(FakeKalshi(), env, False).live is False


def test_log_prints_one_line_per_decision(env, capsys):
    b = bot.Bot(FakeKalshi(), env, False)
    b.log(ENTRY, mk(BTC, None), "skip", "because", yb=0.5, ya=0.6)
    out = capsys.readouterr().out.strip()
    assert out.startswith(bot.iso(ENTRY)) and BTC in out and out.endswith("skip    because")
    row = env.execute("SELECT * FROM decisions").fetchone()
    assert (row["ticker"], row["yes_bid"], row["yes_ask"], row["action"]) == (BTC, 0.5, 0.6, "skip")
