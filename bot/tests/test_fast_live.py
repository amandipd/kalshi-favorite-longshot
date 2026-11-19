"""Fast entry, live, in every window (Oct 14, 2026), as fast_entry ships it: START 1791936000
(2026-10-14 00:00 UTC) and EVERY on, so every window from then on is fast, with no coin.

A fast window preps at 450 s (its markets, their minute-by-minute prices, Kalshi's cash and the housekeeping), does
nothing that could hold the mark up until then but warm its connections in the last poll before it, and at the mark
(480 s on Kalshi's clock) reads every book, builds every order under the same rules, and sends them together in batches
of at most FAST_BURST. test_fast_entry_bot.py tests the wiring with the coin (EVERY False); this file tests what went live
on Oct 14 and the concurrency rules:
1. the error halt counts failures in send order once a batch is back, a halt stops every later window, and once three
   in a row have failed no further batch goes out;
2. the books' cash and Kalshi's are both held back as each order is built: what doesn't fit is skipped before any send;
3, 4. the caps, the deadline and the book's age are settled before the batch;
5, 6. every save on the bot's own thread, the unexpected-fill halt for every order (test_fast_entry_bot.py);
7. the paper +1c still reads one book per live order, and the paper 'fast' rows come from the bot's own books at the
   mark, with the background reader left off while fast entry is on;
8. a 429 is never retried;
9. every live order, fast or not, carries an exchange_index: the market's own when Kalshi lists one, else the section.
Nothing here touches the network or an account.

    python -m pytest tests/test_fast_live.py -q
"""
import concurrent.futures
import sys
import threading
import time
import types

import pytest

from kalshi_bot import bot
from kalshi_bot import fast_entry
from test_bot import THREE_DOLLAR_START, decisions, start_ledger
from test_cli import cli  # noqa: F401 (cli is a fixture)
from test_day_drop import open_bet
from test_fast_entry_bot import HOUSEKEEPING, SOL, YES, Spy, ntp, prep_for, sends, watch  # noqa: F401 (fixtures)
from test_flow import BTC, ETH, GOLD, NO98, YES96, bets, bot_for, mk, slept  # noqa: F401 (slept: no real sleeps)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


START = fast_entry.START       # as shipped
V = START + 40 * 900           # a window on Oct 14, 2026 (10:00 UTC), after the start: fast like every other
REFUSED = {"error": {"code": "insufficient_balance", "message": "insufficient balance"}}   # as Kalshi said on Sep 28


def ok(body):
    """Kalshi's answer to an order that filled in full (Spy's own)."""
    return 201, {"order_id": f"o-{body['ticker']}", "fill_count": body["count"] + ".00", "remaining_count": "0.00"}


def many(n, refuse=(), code=None):
    """A Spy listing n YES favourites at 96c (KXT0 ... KXT<n-1>), refusing orders on the tickers in `refuse`, and the
    markets themselves (as decide_window gets them). code: the error code it refuses with, REFUSED's
    insufficient_balance by default; invalid_price is the one with its own count (bot.price_refused)."""
    names = [f"KXT{i}15M" for i in range(n)]
    answer = REFUSED if code is None else {"error": {"code": code, "message": code}}
    fake = Spy(books={s: YES for s in names},
               order=lambda body, k: (400, answer) if body["ticker"] in refuse else ok(body))
    return fake, [mk(f"{s}-A", YES96, V) for s in names]


class Listed(Spy):
    """A Spy whose listing gives some series' markets an exchange_index (Kalshi's market object carries one)."""

    def __init__(self, index, **kw):
        super().__init__(**kw)
        self.index = index

    def markets(self, **p):
        d = super().markets(**p)
        for m in (d or {}).get("markets", []):
            if m["ticker"].split("-")[0] in self.index:
                m["exchange_index"] = self.index[m["ticker"].split("-")[0]]
        return d


# ------------------------------------------------------------------ as shipped: every window from Oct 14 is fast
def test_it_ships_on_for_every_window_from_oct_14(env):
    assert (fast_entry.START, fast_entry.EVERY) == (1791936000, True)
    b = bot.Bot(Spy(), env, True)
    assert all(b.fast(START + 900 * k) for k in range(3 * 96))       # three days, no coin
    assert not b.fast(START - 900)


def test_the_constants():
    assert (bot.FAST_BURST, bot.FAST_SPACING, bot.CLOCK_SAMPLES, bot.CLOCK_KEEP) == (8, 0.1, 5, 10)


def test_every_window_preps_at_450_s_and_sends_its_orders_together_at_the_mark(env, sends):
    fake = Spy()
    b = bot.Bot(fake, env, True)
    for k in range(3):                                               # three windows in a row
        w = V + 900 * k
        fake.window, fake.suffix = w, f"W{k}"
        b.step(w + 450)
        assert list(b.prepared) == [w] and fake.names().count("candlesticks") == k + 1
        since = fake.mark()
        b.step(w + 480)
        assert not HOUSEKEEPING & set(fake.names(since))
        assert len(sends.calls) == k + 1
        assert sorted(x["ticker"] for x in sends.calls[-1]["bodies"]) == [f"KXBTC15M-W{k}", f"KXGOLD15M-W{k}"]
        assert all(x["exchange_index"] == 2 for x in sends.calls[-1]["bodies"])
        b.step(w + 483)
    assert len(bets(env)) == 6 and bot.halt_info() is None


def test_with_start_none_every_window_is_entered_as_before(env, monkeypatch, sends, watch):
    """The off switch: no prep, no warm-up, the usual 3 s poll, one order at a time."""
    monkeypatch.setattr(fast_entry, "START", None)
    fake = Spy()
    b = bot.Bot(fake, env, True)
    fake.window = V
    assert not any(b.fast(V + 900 * k) for k in range(96))
    for at in (450, 455, 477, 479):
        b.step(V + at)
    assert b.prepared == {} and "candlesticks" not in fake.names() and fake.names().count("exchange_status") == 1
    b.step(V + 482)
    assert sends.calls == [] and sorted((t, s) for t, s, _ in watch.place) == [(BTC, None), (GOLD, None)]
    assert bot.nap(V + 478.5, 0.0, lambda: V + 478.5) == pytest.approx(3.0)


def test_the_loop_wakes_for_the_prep_and_the_mark_of_every_window():
    for k in range(96):                                              # a day of windows
        w = V + 900 * k
        assert bot.nap(w + 448, 0.0, lambda: w + 448) == pytest.approx(2.0)              # the prep, 450 s
        assert bot.nap(w + 478.5, 0.0, lambda: w + 478.5) == pytest.approx(1.5)          # the mark, 480 s
        assert bot.nap(w + 477.1, 1.4, lambda: w + 477.1) == pytest.approx(1.5)          # a PC 1.4 s behind Kalshi
        assert bot.nap(w + 100, 0.0, lambda: w + 100.2) == pytest.approx(2.8)            # the rest of the poll


@pytest.mark.parametrize("at, want", [(448.0, 2.0), (478.5, 1.5), (100.0, 3.0)])
def test_the_main_loop_sleeps_until_the_prep_or_the_mark(cli, monkeypatch, at, want):
    slept = []

    def sleep(s):
        slept.append(s)
        raise KeyboardInterrupt
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: V + at, sleep=sleep))
    with pytest.raises(KeyboardInterrupt):
        bot.main([])
    assert slept == [pytest.approx(want)]


def test_between_the_prep_and_the_mark_nothing_runs_but_one_warm_up(env, sends):
    """No housekeeping between 450 s and the mark, even with all of it due: nothing can hold the mark up. In the last
    poll before the mark it opens FAST_BURST connections at once (a cheap GET each, on other threads), once."""
    fake = Spy()
    b = bot.Bot(fake, env, True)
    fake.window = V
    b.step(V + 450)
    for at in range(453, 477, 3):
        b.last_catalog = b.last_status = b.last_sweep = b.last_reconcile = 0.0
        since = fake.mark()
        b.step(V + at)
        assert fake.names(since) == []
    since = fake.mark()
    b.step(V + 477)
    concurrent.futures.wait(b.warming)
    warm = fake.calls[since:]
    assert [c.name for c in warm] == ["exchange_status"] * bot.FAST_BURST
    assert all(c.thread is not threading.current_thread() for c in warm)
    since = fake.mark()
    b.step(V + 478.2)
    b.step(V + 479.99)
    assert fake.names(since) == [] and fake.orders == []
    b.step(V + 480)
    assert len(sends.calls) == 1 and set(bets(env)) == {BTC, GOLD}


def test_a_paper_account_s_fast_window_ignores_the_halt_and_places_one_at_a_time(env, sends):
    bot.set_halt(V, "testing", "you")
    fake = Spy()
    b = bot.Bot(fake, env, False, halts=False)
    fake.window = V
    b.step(V + 450)
    b.step(V + 480)
    assert sends.calls == [] and set(bets(env)) == {BTC, GOLD} and b.done_window == V


def test_without_fast_entry_beside_it_every_window_is_normal(env, monkeypatch, watch):
    """As in a folder holding only bot.py and kalshi.py (test_scripts.py): no prep, no offset, the usual poll."""
    monkeypatch.setitem(sys.modules, "kalshi_bot.fast_entry", None)
    fake = Spy()
    b = bot.Bot(fake, env, True)
    assert b.fe is None and b.clocks is None and not b.fast(V) and b.offset == 0.0
    assert bot.nap(V + 478.5, 0.0, lambda: V + 478.5) == pytest.approx(3.0)
    fake.window = V
    b.step(V + 450)
    b.step(V + 482)
    assert b.prepared == {} and sorted((t, s) for t, s, _ in watch.place) == [(BTC, None), (GOLD, None)]
    assert all(o["exchange_index"] == 2 for o in fake.orders)


# ------------------------------------------------------------------ Kalshi's clock
def test_kalshis_clock_follows_the_last_10_order_answers(env):
    b = bot.Bot(Spy(), env, True)
    for i in range(10):
        b.clocks.add(1000.0 + i, 1000.1 + i, (1000.05 + i + 1.4) * 1000)   # the PC 1.4 s behind
    assert b.offset == pytest.approx(1.4)
    for i in range(6):
        b.clocks.add(2000.0 + i, 2000.1 + i, (2000.05 + i) * 1000)         # then its clock set right
    assert b.offset == pytest.approx(0.0, abs=1e-6)                          # within about a window's answers


def test_a_fast_windows_answers_set_kalshis_clock(env, sends):
    fake, ms = many(6)
    fake.order = None                                                        # Spy's own answers, with ts_ms
    fake.stamp = lambda body: round((time.time() + 1.4) * 1000)              # Kalshi 1.4 s ahead of this PC
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert len(b.clocks) == 6 and b.offset == pytest.approx(1.4, abs=0.05)


# ------------------------------------------------------------------ rule 1: the error halt
def test_more_orders_than_a_burst_go_in_batches_the_rest_one_every_spacing(env, sends):
    fake, ms = many(10)
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert [len(c["bodies"]) for c in sends.calls] == [8, 2]
    assert [(c["workers"], c["burst"], c["spacing"]) for c in sends.calls] == [(8, 8, 0.1), (8, 1, 0.1)]
    assert [x["ticker"] for c in sends.calls for x in c["bodies"]] == [m["ticker"] for m in ms]   # in the order built
    assert len(bets(env)) == 10 and bot.halt_info() is None


def test_failures_count_in_a_row_in_send_order_once_the_batch_is_back(env, sends):
    fake, ms = many(4, refuse={"KXT015M-A", "KXT215M-A", "KXT315M-A"})       # failed, filled, failed, failed
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert [decisions(env)[m["ticker"]][0] for m in ms] == ["error", "bet", "error", "error"]
    assert b.errors == 2 and bot.halt_info() is None                        # two in a row at the end: not three


def test_three_failures_in_a_row_halt_and_the_next_batch_never_goes_out(env, sends):
    """The first batch is in flight when its first three fail: it is all recorded (5 bets), and the halt stops the
    2 orders of the batch after it, which go out nowhere and are logged as halted."""
    fake, ms = many(10, refuse={"KXT015M-A", "KXT115M-A", "KXT215M-A"})
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert len(sends.calls) == 1 and len(fake.orders) == 8
    assert bot.halt_info()["reason"] == "3 orders failed in a row"
    assert [decisions(env)[m["ticker"]][0] for m in ms] == ["error"] * 3 + ["bet"] * 5 + ["halted"] * 2
    assert decisions(env)[ms[9]["ticker"]] == ("halted", "halted: 3 orders failed in a row")
    assert len(bets(env)) == 5


def test_failures_from_an_earlier_window_count_too(env, sends):
    fake, ms = many(10, refuse={"KXT015M-A"})
    b = bot_for(fake, env, True)
    b.errors = 2                                                             # the last two orders before failed
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert len(sends.calls) == 1 and bot.halt_info()["reason"] == "3 orders failed in a row"
    assert [decisions(env)[m["ticker"]][0] for m in ms[8:]] == ["halted", "halted"]


# A price Kalshi refused is counted on its own line, here as in place(): test_price_steps.py has why, and the
# whole-cent markets it came from. insufficient_balance is not exempt, so the tests above still halt at three.
def test_a_refused_price_does_not_count_towards_the_three(env, sends):
    """Four refusals at the end of one window: the pattern that happened on Oct 21, 22 and 26, which only missed
    halting the bot because a crypto order succeeded between them each time."""
    fake, ms = many(6, refuse={f"KXT{i}15M-A" for i in (2, 3, 4, 5)}, code="invalid_price")
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert [decisions(env)[m["ticker"]][0] for m in ms] == ["bet"] * 2 + ["error"] * 4
    assert bot.halt_info() is None
    assert b.price_errors == 4 and b.errors == 0


def test_enough_refused_prices_in_a_row_halt_on_the_fast_path_too(env, sends):
    """The backstop: if the limit were ever wrong on every market, this is what stops it, inside one window."""
    n = bot.MAX_PRICE_ERRORS + 2
    fake, ms = many(n, refuse={f"KXT{i}15M-A" for i in range(n)}, code="invalid_price")
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert bot.halt_info()["reason"] == f"{bot.MAX_PRICE_ERRORS} orders refused for their price in a row"


def test_a_refused_price_does_not_clear_a_run_of_real_failures(env, sends):
    """A refusal is not a success: it must not reset the ordinary count either."""
    fake, ms = many(3)
    fake.order = lambda body, k: ((400, {"error": {"code": "invalid_price"}}) if body["ticker"] == "KXT115M-A"
                                  else (400, REFUSED))     # fail, refused price, fail -- and nothing after
    b = bot_for(fake, env, True)
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert [decisions(env)[m["ticker"]][0] for m in ms] == ["error"] * 3
    assert b.errors == 2 and b.price_errors == 1    # the refusal sat between them and reset neither run
    assert bot.halt_info() is None                  # two real failures is not three; before the fix this halted


def test_a_halt_from_one_window_stops_every_later_window(env, sends):
    fake = Spy(books={s: YES for s in ("KXBTC15M", "KXSOL15M", "KXXRP15M")}, order=lambda body, k: (400, REFUSED))
    b = bot.Bot(fake, env, True)
    fake.window, fake.suffix = V, "A"
    b.step(V + 450)
    b.step(V + 480)
    assert bot.halt_info()["reason"] == "3 orders failed in a row" and len(fake.orders) == 3
    for k in (1, 2):
        w = V + 900 * k
        fake.window, fake.suffix = w, f"W{k}"
        b.step(w + 450)
        b.step(w + 480)
        assert {decisions(env)[f"{s}-W{k}"][0] for s in ("KXBTC15M", "KXSOL15M", "KXXRP15M")} == {"halted"}
    assert len(fake.orders) == 3 and len(sends.calls) == 1


# ------------------------------------------------------------------ rule 2: cash held back before anything is sent
def test_the_books_cash_is_held_back_as_each_order_is_built(env, sends):
    need = 3 * bot.limit_for(0.96) + bot.taker_fee(3, 0.96)
    open_bet(env, "KXBTC15M-OLD", V - 900, contracts=200, cost=round(200 - 0.05 - (2 * need + 0.5), 4))
    assert bot.cash(env) == pytest.approx(2 * need + 0.5)                   # the books: two orders and 50c
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(t, YES96, V) for t in (BTC, ETH, SOL)]
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    [call] = sends.calls
    assert [x["ticker"] for x in call["bodies"]] == [BTC, ETH] and len(fake.orders) == 2
    assert decisions(env)[SOL] == ("skip", "bankroll too low")


# ------------------------------------------------------------------ rules 3 and 4: settled before the batch
def test_a_stale_book_is_skipped_before_the_batch(env, sends):
    fake = Spy()
    b = bot_for(fake, env, True)
    b.clock, b.mark = (lambda: 100.0), 0.0                                   # 100 s into the step
    fresh, stale = dict(mk(BTC, YES96, V), read=95.0), dict(mk(GOLD, NO98, V), read=50.0)
    b.decide_window(V + 400, V, [fresh, stale], prep=prep_for(fresh, stale))   # 20 s after minute 8, by the stopwatch
    [call] = sends.calls
    assert [x["ticker"] for x in call["bodies"]] == [BTC]
    assert decisions(env)[GOLD] == ("skip", "its order book was read 50s ago, over 15s")


@pytest.mark.parametrize("at, read, why", [
    (480, 5.0, "its order book was read 17s ago, over 15s"),
    (530, 9.0, "too late: 72s after minute 8 ended, past the 60s deadline"),
], ids=["stale-book", "past-the-deadline"])
def test_a_later_batch_is_checked_again_once_the_batch_before_is_back(env, sends, at, read, why):
    """Ten orders: a batch of 8, then one of 2 once the first is back. Kalshi takes 12 s over the first batch, so by
    the time the second could go its books are over 15 s old, or the deadline has passed: it never goes out
    (test_chaos.py found this, Oct 29)."""
    fake, ms = many(10)
    ms = [dict(m, read=read) for m in ms]
    b = bot_for(fake, env, True)
    t = types.SimpleNamespace(now=10.0)
    b.clock, b.mark = (lambda: t.now), 0.0                                   # 10 s into the step
    sends.after = lambda results: setattr(t, "now", t.now + 12.0)
    b.decide_window(V + at, V, ms, prep=prep_for(*ms))
    assert [len(c["bodies"]) for c in sends.calls] == [8] and len(fake.orders) == 8
    assert all(decisions(env)[m["ticker"]] == ("skip", why) for m in ms[8:])
    assert len(bets(env)) == 8 and bot.halt_info() is None


def test_past_the_deadline_nothing_is_sent(env, sends):
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, V), mk(GOLD, NO98, V)]
    b.decide_window(V + 480 + bot.ORDER_DEADLINE + 1, V, ms, prep=prep_for(*ms))
    assert sends.calls == [] and fake.orders == []
    assert decisions(env)[BTC][1].startswith("too late: 61s after minute 8 ended")


# ------------------------------------------------------------------ rule 7: the paper experiments
@pytest.mark.parametrize("up, kinds", [(0.0, ("limitup", "fast")), (0.01, ("fast",))], ids=["limit-at-the-ask", "1c-live"])
def test_a_fast_window_keeps_the_paper_experiments_recording(env, sends, monkeypatch, up, kinds):
    """The paper +1c reads one book per live order after the answers (and records nothing once the +1c is live, as it
    is since Oct 20); the paper 'fast' rows pair each order with the book the bot itself read at the mark."""
    monkeypatch.setattr(bot, "LIMIT_UP", up)
    fake = Spy()
    b = bot.Bot(fake, env, True)
    fake.window = V
    b.step(V + 450)
    since = fake.mark()
    b.step(V + 480)
    first_order = next(i for i, c in enumerate(fake.calls[since:]) if c.name == "create_order")
    assert fake.names(since)[:first_order].count("orderbook") == 3                # the mark's books: BTC, GOLD, ETH
    assert fake.names(since)[first_order:].count("orderbook") == 2                # the +1c's: one per order
    rows = {(r["kind"], r["ticker"]): dict(r) for r in env.execute("SELECT * FROM shadow")}
    assert set(rows) == {(k, t) for k in kinds for t in (BTC, GOLD)}
    assert {r["status"] for r in rows.values()} == {"open"}
    btc = rows[("fast", BTC)]
    assert (btc["seen"], btc["limit_price"], btc["asked"], btc["filled"], btc["extra"]) == (0.96, bot.limit_for(0.96), 3, 3, 3)
    assert btc["cost"] == pytest.approx(2.88) and 0 <= btc["lag"] < 1
    assert rows[("fast", GOLD)]["seen"] == 0.98


def test_a_live_start_starts_no_paper_reader_while_fast_entry_is_on(cli, monkeypatch):
    started = []
    monkeypatch.setattr(bot, "start_reader", lambda *a, **kw: started.append(a))
    bot.main(["--live", "--once"])
    assert started == []
    monkeypatch.setattr(fast_entry, "START", None)                           # off: the reader runs as before
    bot.main(["--live", "--once"])
    assert len(started) == 1


# ------------------------------------------------------------------ rule 8: never retried
def test_a_429_is_sent_once_and_counts_as_a_failure(env, sends):
    fake = Spy(order=lambda body, k: (429, {"error": "too many requests"}) if body["ticker"] == BTC else ok(body))
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, V), mk(GOLD, NO98, V)]
    b.decide_window(V + 480, V, ms, prep=prep_for(*ms))
    assert [o["ticker"] for o in fake.orders].count(BTC) == 1
    action, why = decisions(env)[BTC]
    assert action == "error" and why.startswith("order failed (429)")
    assert set(bets(env)) == {GOLD} and b.errors == 0                         # GOLD, after it, went through


# ------------------------------------------------------------------ rule 9: the exchange_index
@pytest.mark.parametrize("listed, want", [(3, 3), (None, 5), ("3", 5), (True, 5)])
@pytest.mark.parametrize("fast", [True, False], ids=["fast", "start none"])
def test_every_live_order_carries_the_markets_own_exchange_index_else_the_section(env, sends, monkeypatch, fast, listed,
                                                                                  want):
    """The market's own, from its listing (Kalshi's docs: the authoritative source), when it is a whole number; else
    the section the exchange status gives Crypto & Commodities (5 here, to tell it from a hard-coded 2)."""
    if not fast:
        monkeypatch.setattr(fast_entry, "START", None)
    fake = Listed({"KXBTC15M": listed}, section=5)
    b = bot.Bot(fake, env, True)
    fake.window = V
    b.step(V + 450)
    b.step(V + (480 if fast else 482))
    assert len(sends.calls) == (1 if fast else 0)
    got = {o["ticker"]: o["exchange_index"] for o in fake.orders}
    assert got == {BTC: want, GOLD: 5} and all(type(x) is int for x in got.values())
