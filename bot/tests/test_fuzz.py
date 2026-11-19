"""bot.py's pure functions and halts against generated inputs (property-based, with Hypothesis).

The example-based files pin each rule on hand-picked cases. These check what must hold for every input: a
fee rounds up to the cent and never down, a bet never breaks its own caps, an order is always priced inside
the book it was read from, a NO favourite is the mirror image of a YES one, and a halt that needs five
minutes fires after exactly five minutes of the condition and never sooner. Nothing touches the network.

    python -m pytest tests/test_fuzz.py -q                         (needs: pip install hypothesis)
    HYPOTHESIS_PROFILE=thorough python -m pytest tests/test_fuzz.py -q
"""
import math
import os
import uuid
from datetime import datetime, timezone

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from kalshi_bot import bot  # noqa: E402
from test_bot import W, env, fake_bet  # noqa: E402,F401 (env is a fixture)

settings.register_profile("default", max_examples=100, deadline=None)
settings.register_profile("thorough", max_examples=1000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
# The halt tests reset the account between examples themselves, as test_day_drop.py's brute force does.
with_db = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])

thousandths = st.integers(1, 999).map(lambda m: m / 1000)
cents = st.integers(1, 99).map(lambda c: c / 100)


def reset(db):
    db.execute("DELETE FROM bets")
    db.commit()
    try:
        os.remove(bot.halt_path())
    except FileNotFoundError:
        pass
    bot._since.clear()


# ------------------------------------------------------------------ time and money


@given(st.integers(0, 4_102_444_800))
def test_iso_and_ts_round_trip_whole_seconds(t):
    text = bot.iso(t)
    assert text.endswith("Z") and bot.ts(text) == t
    assert bot.iso(bot.ts(text)) == text


@given(st.floats(0, 1e6))
def test_floor_cents_rounds_down_to_a_whole_cent(x):
    c = bot.floor_cents(x)
    assert c * 100 == pytest.approx(round(c * 100), abs=1e-6)
    assert c <= x + 1e-6 and x - c < 0.01 + 1e-6


@given(st.integers(0, 2000), st.floats(0, 1), st.floats(1, 3))
def test_the_fee_rounds_up_to_the_cent_and_never_down(contracts, price, mult):
    exact = mult * 0.07 * contracts * price * (1 - price)
    fee = bot.taker_fee(contracts, price, mult)
    assert fee * 100 == pytest.approx(round(fee * 100), abs=1e-6)
    assert exact - 1e-9 <= fee < exact + 0.01 + 1e-9


@given(st.integers(0, 2000), st.integers(0, 2000), thousandths)
def test_the_fee_is_symmetric_and_never_falls_as_an_order_grows(a, b, price):
    small, large = sorted((a, b))
    assert bot.taker_fee(small, price) <= bot.taker_fee(large, price)
    assert bot.taker_fee(a, price) == bot.taker_fee(a, round(1 - price, 3))


@given(st.floats(0, 1e6), st.integers(1, 200))
def test_a_stake_never_breaks_any_of_its_caps(bankroll, n):
    stake = bot.stake_for(bankroll, n)
    assert 0 <= stake
    assert stake <= bankroll * bot.CAP_PCT + 1e-9
    assert n * stake <= bankroll * bot.WINDOW_CAP + 1e-6
    assert stake * 100 == pytest.approx(round(stake * 100), abs=1e-6)


@given(st.floats(0, 1e5), st.floats(0, 1e5), st.integers(1, 50), st.integers(1, 50))
def test_a_stake_grows_with_the_bankroll_and_shrinks_with_the_window(b1, b2, n1, n2):
    assert bot.stake_for(min(b1, b2), 1) <= bot.stake_for(max(b1, b2), 1)
    assert bot.stake_for(1000.0, max(n1, n2)) <= bot.stake_for(1000.0, min(n1, n2))


# With no $10 cap since Oct 10, 1.5% a bet and a window's 10% (3% and 20% until Oct 15) are all that bound a stake, at
# any bankroll.
@given(st.floats(0, 1e7), st.integers(-10, 500))
def test_a_stake_is_the_most_whole_cents_within_1_5_percent_and_the_windows_share(bankroll, n):
    limit = min(bankroll * bot.CAP_PCT, bankroll * bot.WINDOW_CAP / max(n, 1))
    stake = bot.stake_for(bankroll, n)
    assert stake <= limit + 1e-6 and stake + 0.01 > limit - 1e-6      # within the limit, with no room for another cent
    assert round(stake * 100, 6) == round(stake * 100)                # whole cents


@given(st.floats(0, 1e7), st.floats(0, 1e7), st.integers(-5, 200))
def test_a_stake_never_falls_as_the_bankroll_grows_at_any_window_size(b1, b2, n):
    lo, hi = sorted((b1, b2))
    assert bot.stake_for(lo, n) <= bot.stake_for(hi, n)


@given(st.floats(0, 1e7), st.integers(-1000, 0))
def test_an_empty_or_negative_window_is_sized_like_one_bet(bankroll, n):
    assert bot.stake_for(bankroll, n) == bot.stake_for(bankroll, 1)


@given(st.floats(1000, 1e7), st.integers(1, 200))
def test_the_window_cap_binds_from_the_seventh_bet(bankroll, n):
    """10% shared by n bets is under 1.5% each once n reaches 7 (10/7 = 1.43%); up to 6 bets, each gets its full 1.5%."""
    full = bot.floor_cents(bankroll * bot.CAP_PCT)
    stake = bot.stake_for(bankroll, n)
    if n <= 6:
        assert stake == full
    else:
        assert stake == bot.floor_cents(bankroll * bot.WINDOW_CAP / n) < full


@given(st.floats(668, 1e7))
def test_from_668_dollars_a_bet_is_over_the_old_10_dollar_cap(bankroll):
    assert bot.stake_for(bankroll, 1) > 10.0      # 1.5% of $668 is $10.02


# ------------------------------------------------------------------ books and orders

levels = st.lists(st.tuples(thousandths, st.integers(1, 5000)).map(lambda x: [f"{x[0]:.4f}", f"{x[1]}.00"]),
                  max_size=6)


@given(levels, levels)
def test_a_book_is_parsed_best_first_and_its_top_is_read_off_both_sides(yes, no):
    book = bot.parse_book({"orderbook_fp": {"yes_dollars": yes, "no_dollars": no}})
    for side, raw in (("yes", yes), ("no", no)):
        prices = [p for p, _ in book[side]]
        assert prices == sorted(prices, reverse=True) and len(book[side]) == len(raw)
    yb, ya, ask_size, no_size = bot.top_of_book(book)
    if yes and no:
        assert yb == book["yes"][0][0] and ya == pytest.approx(1 - book["no"][0][0])
        assert (ask_size, no_size) == (book["no"][0][1], book["yes"][0][1])
    else:
        assert (yb, ya, ask_size, no_size) == (None, None, 0.0, 0.0)


@given(thousandths, thousandths)
def test_a_favourite_costs_at_least_half_a_dollar_on_an_uncrossed_book(a, b):
    bid, ask = min(a, b), max(a, b)
    side, price = bot.favourite(bid, ask)
    if side is not None:
        assert price >= 0.5 and price == (ask if side == "yes" else round(1 - bid, 4))
    else:
        assert ask == pytest.approx(round(1 - bid, 4))


@given(st.text(min_size=1, max_size=30), st.sampled_from(["yes", "no"]), thousandths, st.integers(1, 500))
def test_every_order_is_priced_from_the_yes_side_and_capped_at_its_limit(ticker, side, price, contracts):
    body = bot.order_body(ticker, side, price, contracts)
    yes_price = float(body["price"])
    assert body["price"] == f"{yes_price:.4f}" and body["count"] == str(contracts)
    assert body["side"] == ("bid" if side == "yes" else "ask")
    # What the favourite's side pays per contract, read back from the YES price, is exactly its limit.
    assert (yes_price if side == "yes" else 1 - yes_price) == pytest.approx(price, abs=1e-4)
    assert body["time_in_force"] == "immediate_or_cancel"
    assert body["client_order_id"] == bot.client_order_id(ticker) and uuid.UUID(body["client_order_id"])


@given(st.text(max_size=30), st.text(max_size=30))
def test_two_markets_never_share_an_order_id(a, b):
    assert (bot.client_order_id(a) == bot.client_order_id(b)) == (a == b)


# ------------------------------------------------------------------ the warning signs


@given(thousandths, thousandths)
def test_the_two_sides_mids_add_up_to_a_dollar(a, b):
    q = (min(a, b), max(a, b))
    assert bot.own_mid("yes", q) + bot.own_mid("no", q) == pytest.approx(1.0, abs=1e-6)
    assert bot.own_mid("yes", (None, q[1])) is None and bot.own_mid("no", None) is None


quote = st.tuples(thousandths, thousandths).map(lambda q: (min(q), max(q)))
histories = st.dictionaries(st.integers(1, 8), quote | st.tuples(st.none(), thousandths) | st.tuples(thousandths, st.none()),
                            max_size=8)


def mirror(history):
    """The same market seen from the NO side: its YES (bid, ask) is (1 - ask, 1 - bid)."""
    flip = lambda v: None if v is None else round(1 - v, 3)  # noqa: E731
    return {k: (flip(a), flip(b)) for k, (b, a) in history.items()}


@given(quote, histories)
def test_a_no_favourite_is_judged_exactly_as_its_mirror_image_yes_one(q, history):
    bid, ask = q
    as_no = bot.warning("no", bid, ask, history)
    as_yes = bot.warning("yes", round(1 - ask, 3), round(1 - bid, 3), mirror(history))
    assert (as_no is None) == (as_yes is None)
    if as_no:
        assert as_no.split(":")[0] == as_yes.split(":")[0] and as_no.split(" ")[2] == as_yes.split(" ")[2]


@given(st.sampled_from(["yes", "no"]), quote, histories)
def test_a_wide_spread_is_always_the_first_warning(side, q, history):
    bid, ask = q
    w = bot.warning(side, bid, ask, history)
    if round(ask - bid, 6) >= bot.SPREAD_MAX:
        assert w is not None and "over its bid" in w
    elif w is not None:
        assert "over its bid" not in w


@given(st.sampled_from(["yes", "no"]), quote, histories)
def test_only_minutes_6_and_7_with_both_quotes_can_trigger_a_check(side, q, history):
    bid, ask = q
    if round(ask - bid, 6) >= bot.SPREAD_MAX:
        return
    full = {k: v for k, v in history.items() if k in bot.LOOKBACK and None not in v}
    assert bot.warning(side, bid, ask, history) == bot.warning(side, bid, ask, full)
    assert bot.warning(side, bid, ask, {}) is None


@given(st.sampled_from(["yes", "no"]), quote, histories)
def test_any_warning_names_a_rule_the_research_tested(side, q, history):
    w = bot.warning(side, *q, history)
    assert w is None or any(s in w for s in ("over its bid", "only just the favorite", "jumped"))


# ------------------------------------------------------------------ minute-by-minute prices

candle = st.fixed_dictionaries({
    "minute": st.integers(0, 12),
    "yes_bid": st.none() | st.fixed_dictionaries({}, optional={"close_dollars": st.none() | cents.map(str),
                                                               "previous_dollars": cents.map(str)}),
    "yes_ask": st.none() | st.fixed_dictionaries({}, optional={"close_dollars": st.none() | cents.map(str)}),
})


@given(st.dictionaries(st.sampled_from(["KXA-1", "KXB-1", "KXC-1"]), st.lists(candle, max_size=8), max_size=3))
def test_each_minute_carries_the_latest_quote_forward(markets):
    window = W
    raw = {"markets": [{"market_ticker": t, "candlesticks": [
        {**{k: v for k, v in c.items() if k != "minute"}, "end_period_ts": window + 60 * c["minute"]} for c in cs]}
        for t, cs in markets.items()]}
    out = bot.minute_quotes(raw, window)
    assert set(out) == {t for t, cs in markets.items() if cs}

    def close(block):
        v = (block or {}).get("close_dollars", (block or {}).get("previous_dollars"))
        return None if v is None else float(v)

    for t, cs in markets.items():
        if not cs:
            continue
        by_minute = {c["minute"]: c for c in cs}
        assert sorted(out[t]) == list(range(1, max(by_minute) + 1))
        last = [None, None]
        for k in range(1, max(by_minute) + 1):
            c = by_minute.get(k) or {}
            for i, key in enumerate(("yes_bid", "yes_ask")):
                if close(c.get(key)) is not None:
                    last[i] = close(c.get(key))
            assert out[t][k] == tuple(last)


@given(st.none() | st.integers() | st.text() | st.lists(st.integers()))
def test_an_unreadable_reply_is_none(raw):
    assert bot.minute_quotes(raw, W) is None


# ------------------------------------------------------------------ schedule and status


@given(st.integers(-5000, 5000).map(lambda k: W + 900 * k))
def test_a_window_is_blacked_out_exactly_when_it_overlaps_a_blackout(window):
    overlapping = [what for a, b, what in bot.BLACKOUTS if window < bot.ts(b) and window + 900 > bot.ts(a)]
    assert bot.blackout(window) == (overlapping[0] if overlapping else None)


@given(st.integers(1_767_225_600, 1_830_297_600))
def test_maintenance_is_only_ever_thursday_3_to_5_in_new_york(t):
    et = datetime.fromtimestamp(t, bot.ET)
    assert bot.scheduled_maintenance(t) == (et.weekday() == 3 and 3 <= et.hour < 5)
    if bot.scheduled_maintenance(t):
        assert datetime.fromtimestamp(t, timezone.utc).weekday() == 3


status_entries = st.lists(st.fixed_dictionaries({}, optional={
    "description": st.none() | st.sampled_from(["Crypto & Commodities", "Default", "crypto", ""]),
    "exchange_active": st.booleans(), "trading_active": st.booleans(),
    "exchange_index": st.none() | st.integers(0, 4)}),
    max_size=3)
statuses = st.none() | st.fixed_dictionaries({}, optional={
    "exchange_active": st.booleans(), "trading_active": st.booleans(), "exchange_index_statuses": st.none() | status_entries})


@given(statuses)
def test_a_status_reply_of_any_shape_reads_as_on_off_or_unknown(status):
    on = bot.trading_on(status)
    if not status:
        assert on is None
    elif status.get("exchange_active") is False or status.get("trading_active") is False:
        assert on is False
    else:
        assert on in (True, False)


@given(statuses)
def test_the_crypto_section_is_the_one_kalshi_describes_as_crypto_or_2(status):
    section = bot.crypto_section(status)
    crypto = [x for x in (status or {}).get("exchange_index_statuses") or []
              if "crypto" in (x.get("description") or "").lower()]
    # The first crypto entry that names its section; one without an index is passed over, not a crash.
    assert section == next((x["exchange_index"] for x in crypto if x.get("exchange_index") is not None), 2)


@given(st.lists(st.fixed_dictionaries({"exchange_index": st.integers(0, 3), "balance": cents.map(str)}), max_size=4),
       st.integers(0, 3), st.integers(0, 10**7))
def test_usable_cash_is_the_sections_own_balance(breakdown, section, total):
    got = bot.usable_cash({"balance": total, "balance_breakdown": breakdown}, section)
    own = [float(x["balance"]) for x in breakdown if x["exchange_index"] == section]
    if breakdown:
        assert got == (own[0] if own else 0.0)
    else:
        assert got == total / 100


# ------------------------------------------------------------------ the five-minute halts

steps = st.lists(st.tuples(st.integers(1, 200), st.booleans(), st.booleans()), min_size=1, max_size=40)


@with_db
@given(steps)
def test_a_pause_or_an_outage_halts_after_five_minutes_running_and_never_sooner(env, path):
    """A step is (seconds since the last check, trading paused?, Kalshi unreachable?). The model: each condition's
    clock starts the first step it is seen and resets the first step it is not; the bot halts at the first step
    either clock reaches HALT_PERSIST, naming the pause before the outage if both do."""
    reset(env)
    now, since, expected = W, {}, None   # W is a Monday noon in New York: never maintenance hours
    for gap, paused, down in path:
        now += gap
        bot.check_halts(env, now, trading=False if paused else True, reachable=not down)
        fired = None
        for key, on in (("paused", paused), ("down", down)):
            if not on:
                since.pop(key, None)
            elif now - since.setdefault(key, now) >= bot.HALT_PERSIST:
                fired = key
                break
        h = bot.halt_info()
        if fired:
            assert h is not None and ("paused" in h["reason"] if fired == "paused" else "unreachable" in h["reason"])
            expected = fired
            break
        assert h is None, (now - W, path)
    if expected is None:
        assert bot.halt_info() is None


windows = st.lists(st.tuples(st.integers(0, 12), st.integers(0, 4), st.integers(0, 2), st.integers(0, 7200),
                             st.integers(0, 3000)), min_size=1, max_size=4)


@with_db
@given(windows)
def test_eight_losses_settled_in_one_window_within_the_hour_halt(env, plan):
    """Each window is (losses, wins, still open, seconds before now its last bet settled, seconds its bets settled
    over). Only the eight-losses rule can fire: the floor and the day drop are switched off for this test."""
    reset(env)
    saved = bot.HALT_DEPOSIT, bot.HALT_DAY_DROP
    bot.HALT_DEPOSIT, bot.HALT_DAY_DROP = -1.0, 2.0
    try:
        now, i, expected = W + 50_000, 0, False
        for k, (lost, won, still_open, ago, spread) in enumerate(plan):
            n = lost + won
            for j in range(n):
                settled = now - ago - spread * j // max(n - 1, 1)     # the first bet settles last, `ago` before now
                fake_bet(env, i, W + 900 * k, j >= lost, -2.86 if j < lost else 0.15, settled=settled, close=now)
                i += 1
            for _ in range(still_open):
                fake_bet(env, i, W + 900 * k, False, None, status="open", close=now)   # closes now: never late
                i += 1
            expected |= n > 0 and lost >= bot.HALT_WINDOW_LOSSES and now - ago > now - 3600
        env.commit()
        bot.check_halts(env, now, True)
        h = bot.halt_info()
        assert (h is not None) == expected
        if h:
            assert "bets lost in one window" in h["reason"]
    finally:
        bot.HALT_DEPOSIT, bot.HALT_DAY_DROP = saved
