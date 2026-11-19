"""Property-based tests: the rules the research shares with the live bot and the main study must agree.

The same few rules are written out in several places -- the taker fee, which side is the favourite, which group a
series belongs to, the Wilson interval, bet sizing, the "skip both" warning signs. The bot trades on its copy and
the research measured on its own, so a disagreement between copies means the bot is not running the strategy the
research tested. Hypothesis generates the inputs; each property compares every copy on them.

The one known disagreement, an exact 10c jump, is pinned as a strict xfail in test_strategies_backtest.py; the
warning-sign property here keeps clear of that floating-point boundary.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from kalshi_bot import bot
from kalshi_calibration.replication import fetch as rep_fetch
from kalshi_calibration.replication import stats as rep_stats
from kalshi_calibration.strategy.backtest import kalshi_fee

settings.register_profile("research", max_examples=200, deadline=None)
settings.load_profile("research")

thousandths = st.integers(1, 999).map(lambda m: m / 1000)
tickers = st.one_of(
    st.sampled_from(["KXBTC15M", "KXGOLD15M", "KXSILVER15M", "KXWTI15M", "KXNATGAS15M", "KXEURUSD15M", "KXUSDJPY15M",
                     "KXCRYPTOLEAD15M", "KXCRYPTOCOMP15M", "KX10YRRATE15M", "KXINX15M", "KXNDQ15M", "kxoil15m"]),
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", max_size=14).map(lambda s: "KX" + s),
)
categories = st.sampled_from(["Crypto", "Commodities", "Financials", "Climate", "", "Economics"])


@given(tickers, categories)
def test_every_copy_of_the_group_mapping_agrees(study, ticker, category):
    groups = {study.fetch_all15.group_of(ticker, category), bot.group_of(ticker, category),
              rep_fetch.group_of(ticker, category)}
    assert len(groups) == 1, (ticker, category, groups)


@given(st.floats(0, 2000), thousandths)
def test_every_copy_of_the_taker_fee_agrees(study, contracts, price):
    fees = {
        "bot": bot.taker_fee(contracts, price),
        "backtest": study.strategies_backtest.fee(contracts, price),
        "minutes": study.minutes.fee(contracts, price, "KXGOLD15M", 2.0),     # not crypto: no multiplier
        "sizing": study.sizing.fee(contracts, price, False, 2.0),
        "other": study.other_markets.fee(contracts, price, 1.0),
        "replication": rep_stats.order_fee(contracts, price, 0.07),
    }
    assert len(set(fees.values())) == 1, fees
    exact = float(kalshi_fee(price, contracts, config=_study_config()))
    assert exact - 1e-9 <= fees["bot"] < exact + 0.01 + 1e-9


def _study_config():
    from kalshi_calibration.config import load_config
    return load_config()


@given(st.floats(0, 2000), thousandths, st.floats(1, 3))
def test_the_crypto_multiplier_is_applied_the_same_way(study, contracts, price, mult):
    assert study.minutes.fee(contracts, price, "KXBTC15M", mult) == study.sizing.fee(contracts, price, True, mult) \
        == bot.taker_fee(contracts, price, mult) == rep_stats.order_fee(contracts, price, 0.07, mult)


@given(thousandths, thousandths)
def test_every_copy_of_the_favourite_rule_agrees(study, a, b):
    bid, ask = min(a, b), max(a, b)
    research = study.strategies_backtest.favourite(bid, ask)
    assert research == bot.favourite(bid, ask)
    replication = rep_stats.favourite(bid, ask)
    assert replication == (None if research == (None, None) else research)


@given(st.integers(1, 3000).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_the_wilson_intervals_agree(study, kn):
    k, n = kn
    assert study.analyze.wilson(k, n) == pytest.approx(rep_stats.wilson(k, n), abs=1e-12)


@given(st.floats(0, 1e5), st.integers(1, 60))
def test_the_bot_sizes_exactly_like_the_3_percent_account(study, bankroll, n):
    research = study.strategies_backtest.stake_for({"sizing": "capped"}, bankroll, n)
    assert bot.stake_for(bankroll, n) == pytest.approx(research)   # no $10 cap on the bot's orders since Oct 10


@given(st.floats(0, 1e7), st.integers(1, 60))
def test_the_live_replays_size_like_the_bot_and_their_capped_copies_at_most_10_dollars(study, bankroll, n):
    sb = study.strategies_backtest
    accounts = {s["id"]: s for s in sb.STRATS}
    for sid in ("live", "live500"):                  # the bot as it trades since Oct 10, however big the bankroll
        assert sb.stake_for(accounts[sid], bankroll, n) == pytest.approx(bot.stake_for(bankroll, n))
    for sid in ("livecap", "live500cap"):            # as it traded until then
        assert sb.stake_for(accounts[sid], bankroll, n) == pytest.approx(min(bot.stake_for(bankroll, n), 10.0))


cents = st.integers(2, 98).map(lambda c: c / 100)


@settings(max_examples=400)
@given(st.sampled_from(["yes", "no"]), cents, st.integers(1, 3), cents, cents, cents, cents)
def test_the_bot_skips_exactly_the_favourites_the_backtest_skipped(study, side, bid8, spread, b6, b7, s6, s7):
    """"Skip both" in strategies_backtest.py against bot.warning, on quotes in whole cents (spreads of 1-3c), away
    from the exact-10c boundary where float rounding decides (see the xfail in test_strategies_backtest.py)."""
    ask8 = round(bid8 + spread / 100, 2)
    assume(ask8 < 1)
    q6 = (b6, round(min(b6 + s6 / 10, 0.99), 2))
    q7 = (b7, round(min(b7 + s7 / 10, 0.99), 2))
    mid = lambda q: (q[0] + q[1]) / 2 if side == "yes" else 1 - (q[0] + q[1]) / 2   # noqa: E731
    assume(abs(abs(mid((bid8, ask8)) - mid(q7)) - 0.10) > 1e-6)
    market = {"q": {k: (bid8, ask8) for k in range(1, 16)}}
    market["q"].update({6: q6, 7: q7})
    research = study.strategies_backtest.skipped({"minute": 8, "skip": ["spread", "late"]}, market, side)
    live = bot.warning(side, bid8, ask8, {6: q6, 7: q7})
    assert research == (live is not None), (side, bid8, ask8, q6, q7, live)


@given(st.sampled_from(["yes", "no"]), cents, cents, cents)
def test_findings_signs_match_the_backtests_skip_rule(study, side, bid8, b5, b7):
    """findings.py measured the warning signs on its own copy of them; the backtest's accounts skip on theirs."""
    ask8 = round(bid8 + 0.01, 2)
    assume(ask8 < 1)
    own = lambda b, a: (b, a) if side == "yes" else (round(1 - a, 4), round(1 - b, 4))   # noqa: E731
    q = {m: own(bid8, ask8) for m in range(1, 15)}
    q[5], q[7] = own(b5, round(b5 + 0.01, 2)), own(b7, round(b7 + 0.01, 2))
    bet = {"q": q}
    market = {"q": {k: (bid8, ask8) for k in range(1, 16)}}
    market["q"].update({5: (b5, round(b5 + 0.01, 2)), 7: (b7, round(b7 + 0.01, 2))})
    signs = study.findings.SIGNS
    for name in ("spread", "slow"):
        assert signs[name][1](bet) == study.strategies_backtest.skipped({"minute": 8, "skip": [name]}, market, side)
    mids = [(x[0] + x[1]) / 2 for x in (q[8], q[7])]
    assume(not math.isclose(mids[0] - mids[1], 0.10, abs_tol=1e-6))
    assert signs["late"][1](bet) == study.strategies_backtest.skipped({"minute": 8, "skip": ["late"]}, market, side)
