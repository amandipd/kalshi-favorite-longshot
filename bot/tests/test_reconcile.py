"""Its own orders that bought contracts but never reached its records, found in Kalshi's record of the account's
orders and added: an order whose answer was lost (a timeout) and that filled anyway, or a crash between an order and
saving it. Missing, such a bet is invisible to the P&L, the 10% window cap and every halt. Live only, every
RECONCILE_EVERY seconds looking back RECONCILE_BACK, and a day back on its first look after a start.

    python -m pytest tests/test_reconcile.py -q
"""
import pytest
import requests

from kalshi_bot import bot
from test_bot import ENTRY, W, decisions, env  # noqa: F401 (env is a fixture)
from test_flow import BTC, GOLD, Scripted, bets, bot_for, slept  # noqa: F401 (slept: no real sleeps)


def record(ticker, side="yes", count=3, price=0.96, fee=0.01, created=ENTRY, ours=True):
    """One order as Kalshi's GET /portfolio/orders shows it (the fields the live API returned on Oct 11)."""
    return {"order_id": f"k-{ticker}", "client_order_id": bot.client_order_id(ticker) if ours else "typed-on-kalshi.com",
            "ticker": ticker, "outcome_side": side, "status": "executed" if count else "canceled", "type": "limit",
            "fill_count_fp": f"{count:.2f}", "initial_count_fp": "3.00", "remaining_count_fp": "0.00",
            "taker_fill_cost_dollars": f"{count * price:.6f}", "taker_fees_dollars": f"{fee:.6f}",
            "maker_fill_cost_dollars": "0.000000", "maker_fees_dollars": "0.000000", "created_time": bot.iso(created)}


class Recorded(Scripted):
    """Kalshi with its own record of the account's orders, and each market's times for the bot to look up."""

    def __init__(self, record=(), pages=None, times=True, **kw):
        super().__init__(**kw)
        self.order_record, self.pages, self.times, self.history_calls, self.lookups = list(record), pages, times, [], []

    def order_history(self, min_ts, cursor=None):
        self.history_calls.append((min_ts, cursor))
        if self.pages is not None:
            return self.pages(cursor)
        return {"orders": list(self.order_record), "cursor": ""}

    def markets(self, **p):
        if "tickers" not in p:
            return super().markets(**p)
        wanted = p["tickers"].split(",")
        self.lookups.append(wanted)
        if not self.times:
            return None
        found = []
        for t in wanted:
            m = {"ticker": t, "open_time": bot.iso(W), "close_time": bot.iso(W + 900)}
            if t in self.results:
                m.update(result=self.results[t], settlement_ts=bot.iso(W + 908))
            found.append(m)
        return {"markets": found}


def test_how_often_and_how_far_back():
    assert (bot.RECONCILE_EVERY, bot.RECONCILE_BACK) == (60, 7200)


def test_an_order_whose_answer_timed_out_but_filled_is_recorded_from_kalshis_record(env, capsys):
    """Both orders time out and Kalshi shows no fill yet when asked, so neither is recorded. A minute later Kalshi's
    record shows BTC's order bought 3 (GOLD's bought nothing): BTC's bet goes in, at what it really cost, and then
    settles like any other."""
    fake = Recorded(raises=requests.ReadTimeout("no answer in 5s"), fills={"fills": []})
    b = bot_for(fake, env, True)
    b.step(ENTRY)
    assert len(fake.orders) == 2 and bets(env) == {}
    fake.order_record = [record(BTC), record(GOLD, side="no", count=0, price=0.98)]
    b.step(ENTRY + bot.RECONCILE_EVERY)
    assert set(bets(env)) == {BTC}
    got = bets(env)[BTC]
    assert (got["side"], got["contracts"], got["cost"], got["fee"], got["price"]) == \
        ("yes", 3.0, pytest.approx(2.88), pytest.approx(0.01), pytest.approx(0.96))
    assert (got["series"], got["window_open"], got["close_ts"], got["placed_ts"], got["status"]) == ("KXBTC15M", W, W + 900, ENTRY, "open")
    assert (got["order_id"], got["client_order_id"]) == (f"k-{BTC}", bot.client_order_id(BTC))
    assert decisions(env)[BTC] == ("bet", "bought 3 YES at 96.0c: found in Kalshi's record of its orders, missing from its own")
    assert decisions(env)[GOLD][0] == "error"
    assert "found in Kalshi's record of its orders" in capsys.readouterr().out
    fake.results[BTC] = "yes"
    b.step(W + 920)
    assert bets(env)[BTC]["status"] == "won" and bets(env)[BTC]["pnl"] == pytest.approx(3 - 2.88 - 0.01)


def test_after_a_start_it_looks_a_day_back_then_two_hours_once_a_minute(env):
    """A crash between an order and saving it: the restarted bot finds the bet, even hours later."""
    fake = Recorded(record=[record(BTC, created=W - 5 * 3600)])
    b = bot.Bot(fake, env, True)
    now = W + 100
    b.step(now)
    assert fake.history_calls == [(now - 86400, None)] and BTC in bets(env)
    b.step(now + 3)
    b.step(now + 59)
    b.step(now + 60)
    assert fake.history_calls[1:] == [(now + 60 - 7200, None)]


def test_a_restart_inside_the_entry_minute_records_the_lost_bet_before_deciding_again(env):
    """It crashed after BTC's order filled but before saving anything: the restarted bot finds the bet first, so it
    doesn't send BTC's order again (Kalshi would refuse the repeated order ID, a failure toward the 3-in-a-row halt)."""
    fake = Recorded(record=[record(BTC)])
    bot.Bot(fake, env, True).step(ENTRY + 10)
    assert [o["ticker"] for o in fake.orders] == [GOLD]
    assert bets(env)[BTC]["contracts"] == 3.0 and decisions(env)[BTC][0] == "bet"


def test_a_restart_never_sends_again_an_order_that_bought_nothing(env, capsys):
    """It crashed after both orders went out and before saving either; BTC's bought nothing (immediate-or-cancel,
    nobody selling). The restarted bot finds both in Kalshi's record: GOLD's bet goes in, and BTC's market is marked
    decided, so it isn't sent a second order: one order per market, ever (test_chaos.py found this, Oct 29)."""
    fake = Recorded(record=[record(BTC, count=0), record(GOLD, side="no", price=0.98)])
    bot.Bot(fake, env, True).step(ENTRY + 10)
    assert fake.orders == [] and set(bets(env)) == {GOLD}
    assert decisions(env)[BTC] == ("skip", "an order already went out on it and bought nothing: found in Kalshi's"
                                           " record of its orders, missing from its own")
    assert "an order already went out on it" in capsys.readouterr().out


def test_after_a_start_no_window_is_entered_until_kalshis_record_of_its_orders_is_read(env, capsys):
    """It crashed after BTC's order filled and before saving it, and came back inside the window with Kalshi's record of
    its orders unreadable: BTC's order may already be out, so nothing is sent, and it says so once a window. A minute on
    the record reads, BTC's bet goes in, and the next window is entered as usual (test_chaos.py found this, Oct 29)."""
    fake = Recorded(record=[record(BTC)], pages=lambda cursor: None)
    b = bot.Bot(fake, env, True)
    b.step(ENTRY + 10)
    b.step(ENTRY + 13)
    assert fake.orders == [] and bets(env) == {} and decisions(env) == {}
    assert capsys.readouterr().out.count("Kalshi's record of its orders hasn't been read since it started") == 1
    fake.pages = None
    b.step(ENTRY + 70)
    assert set(bets(env)) == {BTC} and fake.orders == []
    fake.window, fake.suffix = W + 900, "B"
    b.step(ENTRY + 900)
    assert sorted(o["ticker"] for o in fake.orders) == ["KXBTC15M-B", "KXGOLD15M-B"]


def test_a_fast_window_isnt_entered_either_until_the_record_is_read(env, monkeypatch):
    """The same at a fast window's mark: a start at 300 s with the record unreadable through the prep, so the mark is
    skipped, and once the record reads (a minute after the prep) the window is entered inside its grace."""
    from kalshi_bot import fast_entry
    monkeypatch.setattr(fast_entry, "START", W - 900)
    fake = Recorded(pages=lambda cursor: None)
    b = bot.Bot(fake, env, True)
    for at in (300, 450, 480, 483):
        b.step(W + at)
    assert fake.orders == []
    fake.pages = None
    b.step(W + 510)
    assert sorted(o["ticker"] for o in fake.orders) == [BTC, GOLD]


@pytest.mark.parametrize("o", [
    record(BTC, ours=False),                   # placed by hand on kalshi.com: not the bot's
    record(BTC, count=0),                      # bought nothing (immediate-or-cancel, nobody selling)
    record(BTC, side=None),                    # no side to record
    {**record(BTC), "created_time": None},     # no time to record
])
def test_orders_that_arent_missing_bets_are_left_alone(env, o):
    fake = Recorded(record=[o])
    bot.Bot(fake, env, True).step(W + 100)
    assert bets(env) == {} and fake.lookups == []


def test_a_bet_already_in_its_records_is_left_as_it_is(env):
    fake = Recorded()
    b = bot_for(fake, env, True)
    b.step(ENTRY)
    before = {t: dict(r) for t, r in bets(env).items()}
    assert set(before) == {BTC, GOLD}
    fake.order_record = [record(BTC, price=0.95), record(GOLD, side="no", price=0.97)]
    b.step(ENTRY + 60)
    assert {t: dict(r) for t, r in bets(env).items()} == before and fake.lookups == []


@pytest.mark.parametrize("halts", [True, False])
def test_a_dry_run_or_paper_account_never_reads_the_accounts_orders(env, halts):
    fake = Recorded(record=[record(BTC)])
    bot.Bot(fake, env, False, halts=halts).step(W + 100)
    assert fake.history_calls == [] and bets(env) == {}


def test_an_unreadable_order_record_is_no_crash_and_the_day_back_look_is_tried_again(env):
    fake = Recorded(pages=lambda cursor: None)
    b = bot.Bot(fake, env, True)
    b.step(W + 100)
    b.step(W + 160)
    assert [t for t, _ in fake.history_calls] == [W + 100 - 86400, W + 160 - 86400]   # never got a look: still a day
    assert bot.halt_info() is None and bets(env) == {}


def test_a_bet_whose_market_cant_be_looked_up_waits_for_the_next_look(env):
    fake = Recorded(record=[record(BTC)], times=False)
    b = bot.Bot(fake, env, True)
    b.step(W + 100)
    assert bets(env) == {} and fake.lookups == [[BTC]]
    fake.times = True
    b.step(W + 160)
    assert BTC in bets(env)


def test_a_restart_whose_market_lookup_fails_still_never_orders_that_market_again(env, capsys):
    """It crashed after BTC's order filled and before saving it; restarted inside the window, it reads Kalshi's record
    but can't look BTC's market up yet. BTC is marked decided all the same, so only GOLD's order goes out; a minute on
    the lookup works and BTC's bet goes in (test_chaos.py found this, Oct 29)."""
    fake = Recorded(record=[record(BTC)], times=False)
    b = bot.Bot(fake, env, True)
    b.step(ENTRY + 10)
    assert [o["ticker"] for o in fake.orders] == [GOLD] and BTC not in bets(env)
    assert decisions(env)[BTC] == ("skip", "an order of its own already bought here (found in Kalshi's record of its"
                                           " orders): its bet goes in once its market can be looked up")
    fake.times = True
    b.step(ENTRY + 70)
    assert bets(env)[BTC]["contracts"] == 3.0 and decisions(env)[BTC][0] == "bet"
    assert [o["ticker"] for o in fake.orders] == [GOLD]


def test_it_reads_every_page_of_the_record(env):
    pages = {None: {"orders": [], "cursor": "p2"}, "p2": {"orders": [record(BTC)], "cursor": "p3"},
             "p3": {"orders": [record(GOLD, side="no", price=0.98)], "cursor": ""}}
    fake = Recorded(pages=lambda c: pages[c])
    bot.Bot(fake, env, True).step(W + 100)
    assert [c for _, c in fake.history_calls] == [None, "p2", "p3"] and set(bets(env)) == {BTC, GOLD}
    assert bets(env)[GOLD]["cost"] == pytest.approx(2.94) and bets(env)[GOLD]["side"] == "no"


def test_it_stops_after_25_pages(env):
    fake = Recorded(pages=lambda c: {"orders": [], "cursor": "more"})
    bot.Bot(fake, env, True).step(W + 100)
    assert len(fake.history_calls) == 25


def test_bets_it_found_count_toward_the_halts(env):
    tickers = [f"KXBTC15M-{i}" for i in range(8)]
    fake = Recorded(record=[record(t) for t in tickers])
    fake.results.update({t: "no" for t in tickers})
    b = bot.Bot(fake, env, True)
    b.step(W + 920)
    b.step(W + 923)
    assert "8 bets lost in one window" in bot.halt_info()["reason"]


def test_it_looks_while_halted_too(env):
    bot.set_halt(W, "testing", "you")
    fake = Recorded(record=[record(BTC)])
    bot.Bot(fake, env, True).step(W + 100)
    assert BTC in bets(env)
