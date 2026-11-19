"""The warning signs the bot skips (the research's "skip both" rule): each sign on its exact line, the minute-by-minute
prices it reads them from, and what the bot does when it can't check them. Nothing here touches the network or an account.

    python -m pytest tests/test_screen.py -q
"""
import pytest

from kalshi_bot import bot
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, run, start_ledger
from test_flow import BTC, ETH, GOLD, NO98, YES96, bets, book, bot_for, mk, slept  # noqa: F401 (slept: no real sleeps)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


def q(mid):
    """A YES quote 1c wide around this mid."""
    return (round(mid - 0.005, 4), round(mid + 0.005, 4))


# ------------------------------------------------------------------ the spread
@pytest.mark.parametrize("bid, ask, skipped", [
    (0.95, 0.96, False),    # 1c
    (0.941, 0.96, False),   # 1.9c
    (0.94, 0.96, True),     # 2c exactly: skipped
    (0.90, 0.96, True),     # 6c
])
def test_a_spread_of_2c_or_more_is_a_warning_sign(bid, ask, skipped):
    why = bot.warning("yes", bid, ask, {})
    assert (why is not None) is skipped
    if skipped:
        assert why.startswith("warning sign: its ask is") and "over its bid (2c or more)" in why


def test_the_spread_is_the_same_seen_from_the_no_side():
    assert bot.warning("no", 0.02, 0.04, {}) == "warning sign: its ask is 2.0c over its bid (2c or more)"
    assert bot.warning("no", 0.02, 0.03, {}) is None


# ------------------------------------------------------------------ the late favourite
@pytest.mark.parametrize("minute, mid, skipped", [
    (6, 0.50, True),        # 50c exactly at minute 6
    (7, 0.50, True),        # ... or at minute 7
    (6, 0.505, False),      # just over
    (7, 0.30, True),
    (5, 0.30, False),       # minute 5 isn't read
    (8, 0.30, False),       # nor minute 8's history: the live book is minute 8
])
def test_a_favorite_at_50c_or_under_at_minute_6_or_7_is_late(minute, mid, skipped):
    why = bot.warning("yes", 0.955, 0.965, {minute: q(mid)})
    assert (why is not None and "only just the favorite" in why) is skipped


def test_late_is_measured_on_the_favorites_own_side():
    # NO is the favourite now. A YES mid of 55.5c at minute 7 is NO at 44.5c: late.
    assert bot.warning("no", 0.03, 0.04, {7: q(0.555)}) == "warning sign: it was 44.5c at minute 7, only just the favorite"
    # NO steady near 96.5c all along: fine.
    assert bot.warning("no", 0.03, 0.04, {6: q(0.035), 7: q(0.035)}) is None


# ------------------------------------------------------------------ the jump in minute 8
@pytest.mark.parametrize("before, skipped", [
    (0.86, True),           # 96c now, 86c at minute 7: up exactly 10c
    (0.861, False),         # up 9.9c
    (0.70, True),
    (0.97, False),          # it fell: not a jump
])
def test_a_favorite_up_10c_or_more_in_minute_8_jumped(before, skipped):
    why = bot.warning("yes", 0.955, 0.965, {7: q(before)})
    assert (why is not None and "jumped" in why) is skipped


def test_the_jump_reads_minute_7_only():
    assert bot.warning("yes", 0.955, 0.965, {6: q(0.80)}) is None


def test_the_first_sign_found_is_the_one_logged():
    assert "over its bid" in bot.warning("yes", 0.90, 0.96, {6: q(0.3), 7: q(0.6)})
    assert "minute 6" in bot.warning("yes", 0.955, 0.965, {6: q(0.3), 7: q(0.3)})


# ------------------------------------------------------------------ a minute with no quote can't trigger a check
@pytest.mark.parametrize("history", [{}, {6: (None, None), 7: (None, None)}, {6: (0.2, None), 7: (None, 0.3)}])
def test_a_minute_with_no_quote_is_no_warning_sign(history):
    assert bot.warning("yes", 0.955, 0.965, history) is None


@pytest.mark.parametrize("side, quote, mid", [
    ("yes", (0.95, 0.96), 0.955), ("no", (0.03, 0.04), 0.965), ("yes", None, None), ("yes", (None, 0.5), None), ("no", (0.5, None), None),
])
def test_own_mid(side, quote, mid):
    assert bot.own_mid(side, quote) == mid


# ------------------------------------------------------------------ reading the candles
def candle(minute, bid=None, ask=None, key="close_dollars"):
    block = lambda v: {} if v is None else {key: f"{v:.4f}"}
    return {"end_period_ts": W + minute * 60, "yes_bid": block(bid), "yes_ask": block(ask)}


@pytest.mark.parametrize("raw", [None, [], "error"])
def test_unreadable_candles_are_none(raw):
    assert bot.minute_quotes(raw, W) is None


def test_candles_become_quotes_by_minute_carrying_the_last_one_forward():
    raw = {"markets": [
        {"market_ticker": "A", "candlesticks": [candle(1, 0.90, 0.92), candle(3, 0.93, None), candle(4, None, 0.97)]},
        {"market_ticker": "EMPTY", "candlesticks": []},     # no candles at all: left out, so the bot skips it
        {"market_ticker": "NONE"},
    ]}
    assert bot.minute_quotes(raw, W) == {"A": {1: (0.90, 0.92), 2: (0.90, 0.92), 3: (0.93, 0.92), 4: (0.93, 0.97)}}


def test_a_candle_without_a_close_falls_back_to_the_previous_price():
    raw = {"markets": [{"market_ticker": "A", "candlesticks": [candle(1, 0.4, 0.5, key="previous_dollars")]}]}
    assert bot.minute_quotes(raw, W) == {"A": {1: (0.4, 0.5)}}


def test_a_market_with_no_quote_yet_has_none_until_one_comes():
    raw = {"markets": [{"market_ticker": "A", "candlesticks": [candle(1), candle(2, 0.5, 0.6)]}]}
    assert bot.minute_quotes(raw, W) == {"A": {1: (None, None), 2: (0.5, 0.6)}}


def test_markets_key_missing_is_an_empty_history():
    assert bot.minute_quotes({}, W) == {}


# ------------------------------------------------------------------ the bot, screening a window
def test_it_asks_for_the_qualifying_markets_from_the_open_to_the_end_of_minute_8(env):
    fake = FakeKalshi()
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98), mk(ETH, book(0.60, 0.62))])
    assert fake.candle_calls == [((BTC, GOLD), W, W + 480)]   # not ETH: at 62c it never qualified


def test_nothing_qualifying_asks_for_no_history(env):
    fake = FakeKalshi()
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(ETH, book(0.60, 0.62))])
    assert fake.candle_calls == []


def test_a_late_favorite_is_skipped_and_the_rest_still_bet(env):
    fake = FakeKalshi()
    fake.history = {BTC: {6: q(0.45), 7: q(0.92)}}
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert decisions(env)[BTC] == ("skip", "warning sign: it was 45.0c at minute 6, only just the favorite")
    assert decisions(env)[GOLD][0] == "bet" and [o["ticker"] for o in fake.orders] == [GOLD]


def test_a_wide_spread_is_skipped_before_any_order(env):
    fake = FakeKalshi()
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, book(0.93, 0.96))])
    assert decisions(env)[BTC] == ("skip", "warning sign: its ask is 3.0c over its bid (2c or more)") and fake.orders == []


def test_a_jump_in_minute_8_is_skipped(env):
    fake = FakeKalshi()
    fake.history = {BTC: {7: q(0.80)}}
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "warning sign: it jumped 15.5c in minute 8") and not bets(env)


def test_unreadable_history_skips_every_qualifier_rather_than_bet_unchecked(env):
    class NoCandles(FakeKalshi):
        def candlesticks(self, tickers, start_ts, end_ts):
            return None
    fake = NoCandles()
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    why = "couldn't read its minute-by-minute prices to check the warning signs"
    assert decisions(env) == {BTC: ("skip", why), GOLD: ("skip", why)} and fake.orders == []


def test_a_market_missing_from_the_history_is_skipped(env):
    class Partial(FakeKalshi):
        def candlesticks(self, tickers, start_ts, end_ts):
            d = super().candlesticks(tickers, start_ts, end_ts)
            d["markets"] = [m for m in d["markets"] if m["market_ticker"] != BTC]
            return d
    fake = Partial()
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert decisions(env)[BTC] == ("skip", "no minute-by-minute prices to check the warning signs")
    assert decisions(env)[GOLD][0] == "bet"


def test_the_window_cap_counts_only_the_favorites_that_passed(env):
    """8 qualify, 2 show a warning sign: the 6 left share the 10% cap, $3.00 each (1.5% of $200), not 10% / 8 = $2.50."""
    fake = FakeKalshi()
    tickers = [f"KXBTC15M-{i}" for i in range(8)]
    fake.history = {tickers[0]: {7: q(0.40)}, tickers[1]: {6: q(0.40)}}
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(t, YES96) for t in tickers])
    placed = bets(env)
    assert sorted(placed) == tickers[2:]
    assert {r["contracts"] for r in placed.values()} == {3}    # $3.00 at 96c; $2.50 would buy 2


def test_seven_qualifiers_less_one_flagged_is_no_longer_capped(env):
    fake = FakeKalshi()
    tickers = [f"KXBTC15M-{i}" for i in range(7)]
    fake.history = {tickers[0]: {7: q(0.40)}}
    bot_for(fake, env, False).decide_window(ENTRY, W, [mk(t, YES96) for t in tickers])
    assert all("window cap" not in r for _, r in decisions(env).values())


def test_a_warning_sign_is_logged_as_such_even_while_halted(env):
    bot.set_halt(ENTRY, "testing")
    fake = FakeKalshi()
    fake.history = {BTC: {6: q(0.45)}}
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert decisions(env)[BTC][1].startswith("warning sign") and decisions(env)[GOLD] == ("halted", "halted: testing")


def test_a_whole_step_screens_too(env):
    fake = FakeKalshi()
    fake.history = {"KXBTC15M-A": {7: q(0.50)}}
    run(env, fake, False)
    assert decisions(env)["KXBTC15M-A"][0] == "skip" and decisions(env)["KXGOLD15M-A"][0] == "bet"
