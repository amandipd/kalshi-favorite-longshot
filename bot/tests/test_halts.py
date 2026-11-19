"""Every other halt on its exact line: half the start, 8 losses in a window, an unsettled bet, a Kalshi pause,
and the documented limits themselves. (The 35%-in-24-hours halt has its own file: test_day_drop.py.)

    python -m pytest tests/test_halts.py -q
"""
import pytest

from kalshi_bot import bot
from test_bot import ENTRY, FakeKalshi, W, decisions, env, fake_bet  # noqa: F401 (env is a fixture)
from test_day_drop import NOW, open_bet, settle_bet

DAY = 86400


def check(db, now=NOW, trading=True, empty=0):
    bot.check_halts(db, now, trading, empty=empty)
    return bot.halt_info()


def losses(db, n, window, settled, first=0, pnl=-0.01):
    for i in range(first, first + n):
        fake_bet(db, i, window, False, pnl, settled=settled)


# ------------------------------------------------------------------ the limits, as documented
def test_the_documented_limits():
    assert (bot.CAP_PCT, bot.WINDOW_CAP, bot.MIN_BET, bot.MINUTE, bot.GRACE) == (0.015, 0.10, 1.0, 8, 45)   # halved Oct 15
    assert (bot.LO, bot.HI) == (0.92, 0.999)                           # the floor rose from 90c on Oct 14 (test_floor_92.py)
    assert bot.EDGE_GROUPS == ("crypto", "metals", "energy")
    assert (bot.MAX_ORDERS_PER_WINDOW, bot.MAX_ORDERS_PER_DAY, bot.MAX_ORDER_ERRORS) == (20, 600, 3)
    assert bot.MAX_PRICE_ERRORS == 6 and bot.MAX_PRICE_ERRORS > 4   # above the four whole-cent series (test_price_steps.py)
    assert not hasattr(bot, "MAX_ORDER_DOLLARS")                       # no cap on an order's size since Oct 10
    assert (bot.HALT_DEPOSIT, bot.HALT_WINDOW_LOSSES, bot.HALT_DAY_DROP) == (0.50, 8, 0.35)
    assert bot.HALT_FLOOR == 700.0                                     # the $700 stop, live prod only (test_halt_floor.py)
    assert (bot.HALT_SETTLE_LAG, bot.HALT_PERSIST, bot.HALT_EMPTY_WINDOWS) == (1800, 300, 3)
    assert (bot.POLL, bot.STATUS_EVERY, bot.CATALOG_EVERY) == (3.0, 60.0, 3600.0)


def test_the_fed_days_are_scheduled():
    """The rest of 2026, and the Fed's 2027 calendar (tentative until each meeting before confirms it): the second
    day of each meeting, when the decision comes out."""
    assert [(b[2], b[0][:10]) for b in bot.BLACKOUTS] == [("Fed decision", d) for d in (
        "2026-10-28", "2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15",
        "2027-10-27", "2027-12-08")]


# ------------------------------------------------------------------ half the start
@pytest.mark.parametrize("loss, halts", [(10.0, False), (49.99, False), (50.0, True), (50.01, True), (90.0, True)])
def test_half_the_start_is_the_line(env, loss, halts):
    settle_bet(env, 0, -loss, NOW - 2 * DAY)   # long ago, so only this rule can be the one that fires
    h = check(env)
    assert (h is not None) is halts
    if halts:
        assert h["reason"] == f"the account is down to ${100 - loss:.2f}, half of $100.00 or less"


def test_the_floor_is_half_of_the_reference_after_a_resume(env):
    bot.set_meta(env, "halt_base", 60.0)   # what a resume at $60 leaves behind
    env.commit()
    settle_bet(env, 0, -69.0, NOW - 2 * DAY)   # $31, above half of $60
    assert check(env) is None
    settle_bet(env, 1, -1.0, NOW - 2 * DAY + 5)  # $30: exactly half of $60
    assert check(env)["reason"] == "the account is down to $30.00, half of $60.00 or less"


def test_the_floor_counts_settled_results_only(env):
    open_bet(env, "KXBTC15M-BIG", W, contracts=200, cost=99.0)   # $99 riding on one open bet
    assert check(env) is None


# ------------------------------------------------------------------ 8 losses in one window
@pytest.mark.parametrize("n, halts", [(7, False), (8, True), (9, True), (12, True)])
def test_eight_losses_in_a_window(env, n, halts):
    losses(env, n, W, NOW - 60)
    h = check(env)
    assert (h is not None) is halts
    if halts:
        assert h["reason"] == f"{n} bets lost in one window (Sep 28 12:00 ET)"


def test_wins_and_open_bets_dont_count_as_losses(env):
    losses(env, 7, W, NOW - 60)
    for i in range(20, 25):
        fake_bet(env, i, W, True, 0.05, settled=NOW - 60)
    fake_bet(env, 30, W, None, None, status="open", close=NOW + 600)
    assert check(env) is None


def test_losses_split_across_windows_dont_add_up(env):
    losses(env, 4, W, NOW - 60)
    losses(env, 4, W + 900, NOW - 60, first=10)
    assert check(env) is None


@pytest.mark.parametrize("age, halts", [(60, True), (3599, True), (3601, False), (2 * 3600, False)])
def test_only_windows_that_settled_in_the_last_hour_count(env, age, halts):
    losses(env, 8, W, NOW - age)
    assert (check(env) is not None) is halts


def test_a_resume_forgets_the_windows_before_it(env):
    losses(env, 8, W, NOW - 1800)
    assert check(env) is not None
    bot.clear_halt(NOW, [env])
    assert check(env, NOW + 1) is None            # they settled before the resume
    losses(env, 8, W + 900, NOW + 30, first=10)   # a fresh bad window does
    assert "8 bets lost in one window" in check(env, NOW + 31)["reason"]


# ------------------------------------------------------------------ an unsettled bet
def late_bet(db, closed_ago, now=NOW, i=0):
    open_bet(db, f"KXBTC15M-LATE{i}", now - closed_ago - 900, contracts=3, cost=2.88)   # its market closed `closed_ago` seconds ago


def test_an_unsettled_bet_halts_only_after_30_minutes_and_5_more_of_it(env):
    late_bet(env, 1801)
    assert check(env, NOW) is None                # first seen late
    assert check(env, NOW + 299) is None
    h = check(env, NOW + 300)                     # 5 minutes running: exactly the line
    assert h["reason"] == "1 bets still unsettled 30+ minutes after their market closed"


@pytest.mark.parametrize("closed_ago", [0, 60, 600, 1799])
def test_a_recently_closed_bet_never_halts_however_long_we_look(env, closed_ago):
    late_bet(env, closed_ago)
    for dt in (0, 100, 299, 301):                 # it isn't 30 minutes old for any of these
        assert check(env, NOW + dt) is None, (closed_ago, dt)


def test_the_5_minute_clock_starts_over_when_the_bet_settles_and_another_goes_late(env):
    late_bet(env, 1801)
    assert check(env, NOW) is None
    env.execute("UPDATE bets SET status='won', result='yes', payout=3, pnl=0.1, settled_ts=?", (NOW + 100,))
    assert check(env, NOW + 200) is None          # settled: the condition clears
    late_bet(env, 1801, now=NOW + 250, i=1)       # a different bet is late again
    assert check(env, NOW + 260) is None          # seen at NOW + 260 ...
    assert check(env, NOW + 400) is None          # ... 140 s isn't 300
    assert check(env, NOW + 560) is not None      # 300 s is


def test_bets_that_settled_late_are_not_unsettled(env):
    fake_bet(env, 0, W, True, 0.1, settled=NOW - 10)   # closed long ago but settled
    for dt in (0, 400):
        assert check(env, NOW + dt) is None


# ------------------------------------------------------------------ Kalshi pausing trading
def test_a_pause_halts_after_5_minutes_running(env):
    assert check(env, NOW, trading=False) is None
    assert check(env, NOW + 299, trading=False) is None
    assert check(env, NOW + 300, trading=False)["reason"] == "Kalshi paused trading outside its scheduled maintenance"


def test_a_pause_that_ends_resets_the_clock(env):
    check(env, NOW, trading=False)
    check(env, NOW + 200, trading=True)              # trading is back
    assert check(env, NOW + 250, trading=False) is None
    assert check(env, NOW + 500, trading=False) is None   # 250 s since it paused again
    assert check(env, NOW + 550, trading=False) is not None


def test_an_unknown_status_is_not_a_pause(env):
    for dt in (0, 300, 900, 5000):
        assert check(env, NOW + dt, trading=None) is None


def test_a_pause_during_maintenance_hours_is_expected(env):
    thursday_4am_et = bot.ts("2026-10-01T08:00:00Z")
    for dt in (0, 300, 3000):
        assert check(env, thursday_4am_et + dt, trading=False) is None


# ------------------------------------------------------------------ windows that list nothing
# Oct 24: Kalshi's status=open filter matched nothing for seven hours, every listing came back empty, and the bot
# passed over 27 windows without a word (test_listing.py). An empty listing reads like a quiet hour, so the run halts.
@pytest.mark.parametrize("n, halts", [(0, False), (1, False), (2, False), (3, True), (27, True)])
def test_a_run_of_windows_listing_no_markets_halts(env, n, halts):
    h = check(env, empty=n)
    assert (h is not None) is halts
    if halts:
        assert h["reason"] == f"{n} windows running listed no markets: nothing has been bet in {n * 15} minutes"


def test_windows_listing_nothing_while_kalshi_is_paused_dont_halt(env):
    """Nothing lists while the exchange is off. An unscheduled pause halts on its own line, not on this one."""
    assert check(env, trading=False, empty=27) is None


def test_an_empty_run_halts_once_trading_has_been_back_30_minutes(env):
    check(env, NOW, trading=False, empty=27)
    assert check(env, NOW + 1799, trading=True, empty=27) is None
    assert check(env, NOW + 1800, trading=True, empty=27)["reason"].startswith("27 windows running listed no markets")


def test_a_pause_seen_while_halted_still_counts_once_resumed(env):
    """Oct 29, live: Kalshi unreachable halted it at 03:26 ET, inside the Thursday maintenance. While halted the pause
    went unnoticed, so when it was resumed at 05:03, trading back since 05:00, the 8 windows the maintenance listed
    nothing in halted it again at once. The pause counts whether or not it's halted."""
    bot.set_halt(NOW, "Kalshi unreachable: its exchange status couldn't be read for 5 minutes")
    for dt in (0, 900, 1800, 3600, 5400):                        # the pause, seen every minute while halted
        check(env, NOW + dt, trading=False, empty=dt // 900)
    bot.clear_halt(NOW + 5580, [env])
    assert check(env, NOW + 5600, trading=True, empty=8) is None              # 3 minutes after trading came back
    assert check(env, NOW + 5400 + 1800, trading=True, empty=8)["reason"].startswith("8 windows running listed no markets")


# ------------------------------------------------------------------ Kalshi's scheduled maintenance
# Oct 22: a bet placed at 02:53 ET held a market closing at 03:00, exactly when the Thursday 3-5 am ET maintenance
# starts. Settlement stalled for 126 minutes, the unsettled tripwire fired, and the bot sat halted for 6h50m with
# nothing actually wrong. A bet cannot settle while the exchange is not trading, so the pause excuses it.
THURSDAY_3AM = bot.ts("2026-10-01T07:00:00Z")   # 3:00 am ET, when the maintenance window opens


def test_a_bet_whose_market_closed_as_maintenance_began_doesnt_halt(env):
    open_bet(env, "KXWTI15M-MAINT", THURSDAY_3AM - 900, contracts=3, cost=2.88)   # its market closes at 3:00 am
    for dt in (0, 1800, 2100, 3600, 7199):      # right through the two hours, long past 30 minutes and 5 more
        assert check(env, THURSDAY_3AM + dt, trading=False) is None, dt


def test_the_30_minutes_to_settle_start_again_when_trading_comes_back(env):
    """The part a plain "skip it while paused" misses: Kalshi settled 6 minutes after the window ended, so the
    tripwire would have fired at 5:05 am instead. The backlog gets its 30 minutes from the moment trading returns."""
    open_bet(env, "KXWTI15M-MAINT", THURSDAY_3AM - 900, contracts=3, cost=2.88)
    back = THURSDAY_3AM + 2 * 3600              # 5:00 am ET: the maintenance is over
    assert check(env, back - 1, trading=False) is None
    for dt in (0, 300, 1799):                   # Kalshi has its 30 minutes to work through what stalled
        assert check(env, back + dt) is None, dt
    assert check(env, back + 1800) is None      # the bet counts as late only from here ...
    assert check(env, back + 2100)["reason"] == "1 bets still unsettled 30+ minutes after their market closed"


def test_a_bet_stuck_while_kalshi_is_trading_still_halts(env):
    """The cover that must not be lost: no pause anywhere near it, so a stalled settlement still stops the bot."""
    late_bet(env, 1801)
    assert check(env, NOW) is None
    assert check(env, NOW + 300)["reason"] == "1 bets still unsettled 30+ minutes after their market closed"


def test_a_pause_long_over_stops_excusing_a_stuck_bet(env):
    late_bet(env, 1801)
    check(env, NOW, trading=False)              # a pause, and then trading comes back
    assert check(env, NOW + 1799) is None       # inside the 30 minutes Kalshi gets to catch up
    assert check(env, NOW + 1800) is None       # late from here, and it must last HALT_PERSIST
    assert check(env, NOW + 2100)["reason"] == "1 bets still unsettled 30+ minutes after their market closed"


def test_an_unknown_status_is_not_a_pause_and_doesnt_excuse_a_stuck_bet(env):
    late_bet(env, 1801)
    assert check(env, NOW, trading=None) is None
    assert check(env, NOW + 300, trading=None) is not None


# ------------------------------------------------------------------ a paper account (--paper)
def test_a_paper_account_bets_through_a_halt(env):
    bot.set_halt(W, "real money stopped")
    bot.Bot(FakeKalshi(), env, False, halts=False).step(ENTRY)
    got = decisions(env)
    assert got["KXBTC15M-A"][0] == "bet" and got["KXGOLD15M-A"][0] == "bet"


def test_a_paper_accounts_losses_never_halt_anything(env):
    losses(env, 11, W - 900, W, pnl=-5.0)   # 11 lost in one window, down 55%: three halts' worth
    env.commit()
    bot.Bot(FakeKalshi(), env, False, halts=False).step(ENTRY)
    assert bot.halt_info() is None
    bot.Bot(FakeKalshi(), env, False).step(ENTRY)   # the same losses halt an account that obeys halts
    assert bot.halt_info() is not None
