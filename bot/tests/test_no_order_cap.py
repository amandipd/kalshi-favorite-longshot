"""The live bot without its $10 order cap (removed Oct 10): 1.5% a bet and 10% a window (CAP_PCT and WINDOW_CAP, halved
from 3% and 20% on Oct 15) are all that size an order.

Sizing by hand first, then big orders end to end against the fake exchange: they go out at the ask the bot saw
as immediate-or-cancel orders for the whole contracts the stake buys at that ask, the real balance still
blocks what it can't cover, the window cap and the per-window and per-day order limits still hold, a partial fill is
recorded as it came, and a fill larger than the order still halts. Then the dashboard: no cap in what the server sends or the page says, and a next bet
that grows with the bankroll. The properties over every bankroll are in test_fuzz.py.
"""

import math

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from test_bot import ENTRY, W, FakeKalshi, decisions, env, fake_bet  # noqa: F401 (env is a fixture)
from test_dashboard_more import home, mode_db  # noqa: F401 (home is a fixture)
from test_day_drop import Many
from test_flow import BTC, GOLD, NO98, YES96, Scripted, bets, book, bot_for, fill, mk, slept  # noqa: F401 (slept: no sleeps)
from test_frontend import HTML, SCRIPT


def rich(fake, dollars=10_000_000):
    """Enough real cash in Crypto & Commodities that the balance check never binds."""
    fake.crypto_cash = f"{dollars:.4f}"
    return fake


def bankroll(db, amount):
    bot.set_start(db, amount)
    db.commit()


# ------------------------------------------------------------------ sizing, by hand
@pytest.mark.parametrize("amount, n, stake", [
    (1e6, 1, 15_000.00),          # 1.5% of $1,000,000
    (1e6, 6, 15_000.00),          # six bets: 9% of the bankroll, under the 10% cap
    (1e6, 7, 14_285.71),          # seven: 10% / 7 = 1.4286%, rounded down to the cent
    (1e6, 0, 15_000.00), (1e6, -3, 15_000.00),   # an empty or negative count is one bet
    (666.66, 1, 9.99), (668.0, 1, 10.02),        # where 1.5% crosses the old $10 cap
])
def test_stake_for_without_a_dollar_cap(amount, n, stake):
    assert bot.stake_for(amount, n) == stake


# ------------------------------------------------------------------ big orders, end to end
@pytest.mark.parametrize("amount, ask, limit", [(1_000.0, 0.92, "0.9300"), (5_000.0, 0.95, "0.9600"),
                                               (12_345.67, 0.999, "0.9990"), (1e6, 0.931, "0.9410")])   # 1c over, at most 99.9c
def test_a_big_order_is_the_whole_contracts_its_stake_buys_at_the_ask_it_saw(env, amount, ask, limit):
    bankroll(env, amount)
    fake = rich(FakeKalshi())                    # fills every order in full, at its price
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, book(round(ask - 0.01, 3), ask))])
    stake = bot.stake_for(amount, 1)
    contracts = math.floor(stake / ask + 1e-9)
    [order] = fake.orders
    assert order["count"] == str(contracts) and order["price"] == limit and order["side"] == "bid"
    assert order["time_in_force"] == "immediate_or_cancel"
    assert contracts * ask > 10.0, "well past the old $10 cap"
    assert contracts * ask <= stake < (contracts + 1) * ask, "whole contracts, never more than the stake"
    assert bets(env)[BTC]["contracts"] == contracts and bot.halt_info() is None


def test_a_big_no_order_is_priced_from_the_yes_bid(env):
    bankroll(env, 10_000.0)                     # $150 a bet
    fake = rich(FakeKalshi())
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(GOLD, NO98)])
    [order] = fake.orders
    # NO at 98c: buying NO up to its 99c limit is selling YES down to 1c; sized at the 98c it saw
    assert order["side"] == "ask" and order["price"] == "0.0100" and order["count"] == str(math.floor(150.0 / 0.98 + 1e-9))


def test_the_real_balance_still_blocks_an_order_it_cant_cover(env):
    bankroll(env, 10_000.0)                     # the books say $150 a bet ...
    fake = rich(Scripted(), 120.0)              # ... but Crypto & Commodities holds $120
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC][0] == "skip" and decisions(env)[BTC][1].startswith("only $120.00 in Kalshi's Crypto & Commodities")
    assert fake.orders == [] and not bets(env)


def test_the_books_cash_still_blocks_an_order_open_bets_have_tied_up(env):
    bankroll(env, 5_000.0)
    env.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status)"
                " VALUES ('KXBTC15M-OLD', 'KXBTC15M', ?, ?, 'yes', 0.96, 5130, 4924.8, 1.0, ?, 'open')", (W - 900, W, W - 420))
    env.commit()
    fake = rich(Scripted())
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(env)[BTC] == ("skip", "bankroll too low") and fake.orders == []


def test_the_window_cap_holds_with_big_stakes(env):
    bankroll(env, 100_000.0)
    fake = rich(Many(10))
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(f"{s}-A", YES96) for s in fake.names])
    assert len(fake.orders) == 10
    stake = bot.stake_for(100_000.0, 10)
    assert stake == 1_000.0                                                       # 10% shared by ten
    assert all(int(o["count"]) == math.floor(stake / 0.96 + 1e-9) for o in fake.orders)
    assert sum(int(o["count"]) * 0.96 for o in fake.orders) <= 0.10 * 100_000.0


def test_at_most_20_orders_a_window_however_big_the_bankroll(env):
    bankroll(env, 1e6)
    fake = rich(Many(25))
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(f"{s}-A", YES96) for s in fake.names])
    d = decisions(env)
    assert len(fake.orders) == bot.MAX_ORDERS_PER_WINDOW == 20
    assert sum(r == "order limit reached" for _, r in d.values()) == 5
    assert sum(int(o["count"]) * 0.96 for o in fake.orders) <= 0.10 * 1e6     # sized for all 25, so well inside 10%


def test_at_most_600_orders_a_day_however_big_the_bankroll(env):
    bankroll(env, 1e6)
    for i in range(100, 100 + 599):               # 599 bets in the last day: room for one more
        fake_bet(env, i, W - 900, True, 0.0, settled=W - 5)
    fake = rich(Scripted())
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert decisions(env)[BTC][0] == "bet" and decisions(env)[GOLD] == ("skip", "order limit reached")
    assert len(fake.orders) == 1


def test_a_partial_fill_on_a_big_order_records_only_what_filled(env):
    bankroll(env, 10_000.0)
    fake = rich(Scripted(order=(201, {"order_id": "o1", "fill_count": "40.00", "remaining_count": "0.00"}),
                         fills=lambda p: {"fills": [fill(40)]}))
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert fake.orders[0]["count"] == "156"                                   # $150 at 96c
    r = bets(env)[BTC]
    assert r["contracts"] == 40 and r["cost"] == pytest.approx(40 * 0.96) and r["price"] == pytest.approx(0.96)
    assert bot.halt_info() is None and fake.cancels == []                      # immediate-or-cancel: nothing left resting


def test_a_fill_larger_than_a_big_order_still_halts(env):
    bankroll(env, 10_000.0)                     # $150 a bet: 156 at 96c
    fake = rich(Scripted(order=(201, {"order_id": "o1", "fill_count": "157.00"}), fills=lambda p: {"fills": [fill(157)]}))
    bot_for(fake, env, True).decide_window(ENTRY, W, [mk(BTC, YES96), mk(GOLD, NO98)])
    assert "unexpected fill on " + BTC in bot.halt_info()["reason"] and "asked 156" in bot.halt_info()["reason"]
    assert bets(env)[BTC]["contracts"] == 157                                  # the position is real, so it's recorded
    assert [o["ticker"] for o in fake.orders] == [BTC] and decisions(env)[GOLD][0] == "halted"   # nothing more goes out


def test_a_dry_run_fills_no_more_than_the_book_shows_however_big_the_bet(env):
    bankroll(env, 10_000.0)
    bot_for(Scripted(), env, False).decide_window(ENTRY, W, [mk(BTC, book(0.95, 0.96, ask_size=50.0))])
    assert bets(env)[BTC]["contracts"] == 50                                   # 156 wanted, 50 offered


# ------------------------------------------------------------------ the dashboard
def test_the_server_sends_no_order_cap(home):
    mode_db(home, "live-prod")
    limits = dashboard.state("live-prod")["limits"]
    assert "maxOrder" not in limits
    assert (limits["betPct"], limits["windowPct"], limits["ordersPerWindow"], limits["ordersPerDay"]) == (0.015, 0.10, 20, 600)


def test_the_page_states_no_dollar_cap_anywhere():
    assert "maxOrder" not in SCRIPT and "MAX_ORDER_DOLLARS" not in HTML
    for capped in ("$10 an order", "at most $10", "$10 cap", "order cap of"):
        assert capped not in SCRIPT, capped
    assert "a window's bets together at most <b>${limitPct(L.windowPct)}</b>, with no cap on an order's size;" in SCRIPT   # how it trades
    assert "of the bankroll, no cap on an order</b>" in SCRIPT                     # Bot settings: next bet


@pytest.mark.parametrize("start, next_bet", [(100.0, 1.5), (5_000.0, 75.0), (1e6, 15_000.0)])
def test_the_next_bet_is_1_5_percent_of_the_bankroll_however_big(home, start, next_bet):
    mode_db(home, "live-prod", start=start)
    assert dashboard.state("live-prod")["nextBet"] == next_bet


def test_limits_are_shown_as_set_not_rounded():
    """1.5% a bet reads "1.5%", not "2%" (pct with no decimals rounded it), and 10% a window reads "10%"."""
    import re, shutil, subprocess
    if not shutil.which("node"):
        pytest.skip("node isn't installed")
    line = re.search(r"^const limitPct = [^\n]*$", SCRIPT, re.M).group(0)
    js = line + "\nconsole.log([0.015, 0.1, 0.03, 0.2, null].map(limitPct).join(' '))"   # own line: the helper ends in a // comment
    out = subprocess.run(["node", "-e", js],
                         capture_output=True, text=True, encoding="utf-8", timeout=30).stdout.strip()
    assert out == "1.5% 10% 3% 20% —"
