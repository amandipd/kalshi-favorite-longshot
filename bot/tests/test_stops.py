"""When the bot stops: how long anything may take before it gives up on a bet, what it does with an order left
queued on the book, and what happens when Kalshi goes down. Nothing here touches the network or an account.

    python -m pytest tests/test_stops.py -q
"""
import json
import threading

import pytest
import requests

from kalshi_bot import bot
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, start_ledger
from test_flow import BTC, GOLD, NO98, YES96, Scripted, bets, bot_for, mk, slept  # noqa: F401 (slept: no real sleeps)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


class Clock:
    """The bot's stopwatch, moved by hand (or by a slow fake Kalshi)."""

    def __init__(self):
        self.t, self.lock = 1000.0, threading.Lock()

    def __call__(self):
        return self.t

    def add(self, s):
        with self.lock:
            self.t += s


def timed(fake, db, live=True, trading=True):
    """A bot mid-step, on a clock the test controls."""
    b = bot_for(fake, db, live, trading)
    b.clock = Clock()
    b.mark = b.clock()
    return b


def markets(n, w=W):
    return [mk(f"KXBTC15M-{i}", YES96, w) for i in range(n)]


class SlowOrders(FakeKalshi):
    """Every order takes `per` seconds to come back."""

    def __init__(self, per):
        super().__init__()
        self.per, self.clock = per, None

    def create_order(self, body):
        self.clock.add(self.per)
        return super().create_order(body)


def halt_reason():
    h = bot.halt_info()
    return h and h["reason"]


# ------------------------------------------------------------------ the entry deadline
def test_no_order_goes_out_past_the_end_of_minute_9(env):
    """Orders take 25s each. Entering 5s after minute 8: orders at 5s, 30s, 55s go; the 4th would be at 80s."""
    fake = SlowOrders(25)
    b = timed(fake, env)
    fake.clock = b.clock
    b.decide_window(W + 485, W, markets(5))
    assert len(fake.orders) == 3
    d = decisions(env)
    assert d["KXBTC15M-3"] == ("skip", "too late: 80s after minute 8 ended, past the 60s deadline")
    assert d["KXBTC15M-4"] == d["KXBTC15M-3"] and len(bets(env)) == 3   # a skip sends nothing, so the clock stood still


@pytest.mark.parametrize("entered, orders", [(480, 1), (539, 1), (541, 0)])
def test_the_deadline_is_60s_after_minute_8_to_the_second(env, entered, orders):
    fake = FakeKalshi()
    timed(fake, env).decide_window(W + entered, W, markets(1))
    assert len(fake.orders) == orders


def test_a_listing_so_slow_it_ends_past_the_deadline_orders_nothing(env):
    """Kalshi takes 70s to hand over the order books: by then every price is a minute stale."""
    class SlowBooks(FakeKalshi):
        def orderbook(self, ticker):
            b.clock.add(25)
            return super().orderbook(ticker)
    fake = SlowBooks()
    b = bot.Bot(fake, env, True)
    b.clock = Clock()
    b.step(ENTRY)
    d = decisions(env)
    assert fake.orders == [] and d[BTC][1].startswith("too late") and d[GOLD][1].startswith("too late")


def test_slow_history_counts_toward_the_deadline_too(env):
    class SlowCandles(FakeKalshi):
        def candlesticks(self, tickers, start_ts, end_ts):
            b.clock.add(70)
            return super().candlesticks(tickers, start_ts, end_ts)
    fake = SlowCandles()
    b = timed(fake, env)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert fake.orders == [] and decisions(env)[BTC][1].startswith("too late: 75s")


# ------------------------------------------------------------------ a stale order book
def test_no_order_on_a_book_read_more_than_15s_before(env):
    """Books read at the start; orders take 8s each: the third would go on a book 16s old."""
    fake = SlowOrders(8)
    b = timed(fake, env)
    fake.clock = b.clock
    ms = markets(4)
    for m in ms:
        m["read"] = 0.0
    b.decide_window(ENTRY, W, ms)
    assert len(fake.orders) == 2
    assert decisions(env)["KXBTC15M-2"] == ("skip", "its order book was read 16s ago, over 15s")


def test_each_book_remembers_when_in_the_step_it_was_read(env):
    class SlowBooks(FakeKalshi):
        def orderbook(self, ticker):
            b.clock.add(1)
            return super().orderbook(ticker)
    b = timed(SlowBooks(), env, live=False)
    ms = b.window_markets(W)
    assert all(0 < m["read"] <= 3 for m in ms)


def test_outside_a_step_the_stopwatch_reads_zero(env):
    b = bot.Bot(FakeKalshi(), env, False)
    assert b.mark is None and b.elapsed() == 0.0
    b.step(W + 100)
    assert b.mark is None   # cleared when the step ends


# ------------------------------------------------------------------ an order left queued on the book
def resting_reply(left="2.00", filled="1.00"):
    return lambda body, i: (201, {"order_id": f"o{i}", "fill_count": filled, "remaining_count": left})


def test_an_order_kalshi_leaves_resting_is_cancelled_at_once_and_the_bot_halts(env):
    fake = Scripted(order=resting_reply())
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert fake.cancels == [("o1", BTC)]
    assert halt_reason() == f"order on {BTC} came back with 2 contracts resting on the book; cancelled it"
    assert bets(env)[BTC]["contracts"] == 1                  # the part that filled is still a bet
    assert decisions(env)[GOLD][0] == "halted"               # and nothing more goes out
    row = env.execute("SELECT * FROM orders WHERE request LIKE ?", ('{"cancel"%',)).fetchone()
    assert json.loads(row["request"]) == {"cancel": "o1"} and row["http_status"] == 200


def test_an_order_with_nothing_left_is_not_cancelled(env):
    fake = Scripted(order=resting_reply(left="0.00", filled="3.00"))
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert fake.cancels == [] and bot.halt_info() is None


@pytest.mark.parametrize("answer, said", [((500, {"error": "x"}), "HTTP 500"), ((404, {"error": "gone"}), "HTTP 404")])
def test_a_cancel_kalshi_refuses_still_halts_and_says_so(env, answer, said):
    class Refuses(Scripted):
        def cancel_order(self, order_id, ticker):
            self.cancels.append((order_id, ticker))
            return answer
    fake = Refuses(order=resting_reply())
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert halt_reason() == (f"order on {BTC} came back with 2 contracts resting on the book; couldn't cancel it ({said}):"
                             " it tries again every 15s; check kalshi.com")


def test_a_cancel_that_gets_no_answer_still_halts(env):
    class Down(Scripted):
        def cancel_order(self, order_id, ticker):
            raise requests.ConnectionError("down")
    bot_for(Down(order=resting_reply()), env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert "couldn't cancel it (no answer from Kalshi)" in halt_reason()
    row = env.execute("SELECT * FROM orders WHERE request LIKE ?", ('{"cancel"%',)).fetchone()
    assert row["http_status"] is None and "network error: down" in row["response"]


# ------------------------------------------------------------------ the sweep: its own orders resting, found and cancelled
def mine(ticker, oid="r1"):
    return {"order_id": oid, "ticker": ticker, "client_order_id": bot.client_order_id(ticker)}


class Watched(FakeKalshi):
    def __init__(self):
        super().__init__()
        self.listed = 0

    def list_orders(self, **p):
        self.listed += 1
        assert p == {"status": "resting", "limit": 200}
        return super().list_orders(**p)


def test_the_sweep_cancels_its_own_resting_order_and_halts(env):
    fake = Watched()
    fake.resting = [mine(BTC)]
    bot.Bot(fake, env, True).step(W + 100)
    assert fake.cancels == [("r1", BTC)] and fake.resting == []
    assert halt_reason() == f"order on {BTC} was left resting on the book; cancelled it"


def test_the_sweep_leaves_orders_it_didnt_place_alone(env):
    fake = Watched()
    fake.resting = [{"order_id": "m1", "ticker": BTC, "client_order_id": "placed-by-hand"}, {"order_id": "m2", "ticker": GOLD}]
    bot.Bot(fake, env, True).step(W + 100)
    assert fake.cancels == [] and bot.halt_info() is None


def test_the_sweep_runs_every_15_seconds(env):
    fake = Watched()
    b = bot.Bot(fake, env, True)
    for t in (100, 103, 114, 115, 116):
        b.step(W + t)
    assert fake.listed == 2   # at 100 and 115


def test_the_sweep_runs_while_halted_so_nothing_stays_queued(env):
    bot.set_halt(W, "by hand", "you")
    fake = Watched()
    fake.resting = [mine(GOLD)]
    bot.Bot(fake, env, True).step(W + 100)
    assert fake.cancels == [("r1", GOLD)] and bot.halt_info()["reason"] == "by hand"   # the first halt stands


def test_a_cancel_that_fails_is_tried_again_on_the_next_sweep(env):
    class Stubborn(Watched):
        tries = 0

        def cancel_order(self, order_id, ticker):
            self.tries += 1
            if self.tries == 1:
                return 503, {"error": "busy"}
            return super().cancel_order(order_id, ticker)
    fake = Stubborn()
    fake.resting = [mine(BTC)]
    b = bot.Bot(fake, env, True)
    b.step(W + 100)
    assert fake.resting and "couldn't cancel it (HTTP 503)" in halt_reason()
    b.step(W + 116)
    assert fake.resting == [] and fake.tries == 2


def test_an_unreadable_order_list_is_no_crash_and_no_halt(env):
    class Blind(Watched):
        def list_orders(self, **p):
            self.listed += 1
            return None
    fake = Blind()
    b = bot.Bot(fake, env, True)
    b.step(W + 100)
    b.step(W + 116)
    assert fake.listed == 2 and bot.halt_info() is None


def test_a_dry_run_or_paper_account_never_looks_for_resting_orders(env):
    fake = Watched()
    fake.resting = [mine(BTC)]
    bot.Bot(fake, env, False).step(W + 100)
    bot.Bot(fake, env, False, halts=False).step(W + 200)
    assert fake.listed == 0 and fake.cancels == []


# ------------------------------------------------------------------ an order that hangs
def test_an_order_that_times_out_is_checked_by_its_fills_and_counted_as_failed(env):
    fake = Scripted(raises=requests.ReadTimeout("no answer in 5s"), fills={"fills": []})
    b = bot_for(fake, env, True)
    b.decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert b.errors == 1 and not bets(env) and decisions(env)[BTC][0] == "error"
    assert fake.fill_calls == [{"ticker": BTC, "limit": 100}]


def test_three_orders_that_time_out_in_a_row_halt(env):
    fake = Scripted(raises=requests.ReadTimeout("no answer"), fills={"fills": []})
    bot_for(fake, env, True).decide_window(ENTRY, W, markets(5))
    assert len(fake.orders) == 3 and halt_reason() == "3 orders failed in a row"


# ------------------------------------------------------------------ Kalshi down
class Down(FakeKalshi):
    """Kalshi's exchange status can't be read at all while `down`."""

    def __init__(self):
        super().__init__()
        self.down = True

    def exchange_status(self):
        return None if self.down else super().exchange_status()


def test_kalshi_unreachable_for_5_minutes_halts(env):
    fake = Down()
    b = bot.Bot(fake, env, True)
    for t in range(100, 400, 61):          # status re-read every minute: unreadable each time
        b.step(W + t)
    assert bot.halt_info() is None         # 4 minutes and 4 seconds in
    b.step(W + 405)
    assert halt_reason() == "Kalshi unreachable: its exchange status couldn't be read for 5 minutes"


def test_kalshi_back_within_5_minutes_is_no_halt(env):
    fake = Down()
    b = bot.Bot(fake, env, True)
    b.step(W + 100)
    b.step(W + 200)
    fake.down = False
    b.step(W + 300)
    b.step(W + 500)
    assert bot.halt_info() is None and b.reachable is True and b.trading is True


def test_no_entry_while_kalshi_cant_be_reached(env):
    fake = Down()
    b = bot.Bot(fake, env, True)
    b.step(ENTRY)
    assert fake.orders == [] and b.reachable is False and b.trading is None
    why = ("skip", "couldn't confirm Kalshi is trading: its exchange status is unreadable")
    assert decisions(env)[BTC] == decisions(env)[GOLD] == why


def test_a_paper_account_never_halts_when_kalshi_goes_down(env):
    fake = Down()
    b = bot.Bot(fake, env, False, halts=False)
    for t in range(100, 800, 61):
        b.step(W + t)
    assert bot.halt_info() is None


def test_kalshi_down_everywhere_is_no_crash_no_order_and_ends_in_a_halt(env):
    """Every call fails: no catalog, no status, no markets, no orders listed. The bot keeps stepping and halts."""
    class Gone(FakeKalshi):
        def series(self): return None
        def exchange_status(self): return None
        def markets(self, **p): return None
        def list_orders(self, **p): return None
    fake = Gone()
    b = bot.Bot(fake, env, True)
    for t in range(0, 600, 3):
        b.step(W + t)
    assert fake.orders == [] and "Kalshi unreachable" in halt_reason()


def test_the_halt_waits_for_the_outage_to_last(env):
    bot.check_halts(env, W, True, reachable=False)
    bot.check_halts(env, W + 299, True, reachable=False)
    assert bot.halt_info() is None
    bot.check_halts(env, W + 300, True, reachable=False)
    assert "unreachable" in halt_reason()


def test_reachable_defaults_to_true_for_callers_that_dont_say(env):
    for t in (0, 400, 800):
        bot.check_halts(env, W + t, True)
    assert bot.halt_info() is None
