"""Property-based tests for kalshi_calibration/strategy/backtest.py.

test_backtest.py proves on one planted corpus that the strategy cannot peek at an answer. The strongest
property here is the same proof over generated corpora: whatever the prices, timings and outcomes, shuffling
the out-of-sample outcomes must leave every position size byte-identical. The rest pin the fee's shape, the
Kelly algebra, the split's honesty, and the portfolio budget, on inputs nobody picked by hand.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from kalshi_calibration.strategy.backtest import (
    NO,
    YES,
    _apply_daily_budget,
    backtest_bias_strategy,
    daily_equity,
    kalshi_fee,
    kelly_fraction,
    summarise,
    time_split,
)
from test_backtest import strategy_config

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
CONFIG = strategy_config()
CEILING = strategy_config(fee_ceiling_per_contract=True)
open_unit = st.floats(0.001, 0.999)
unit = st.floats(0.0, 1.0)


# ------------------------------------------------------------------ fee


@given(unit, st.floats(0.0, 1e5))
def test_the_fee_is_symmetric_non_negative_and_peaks_at_half(price, contracts):
    fee = float(kalshi_fee(price, contracts, CONFIG))
    assert fee == pytest.approx(float(kalshi_fee(1 - price, contracts, CONFIG)), rel=1e-9, abs=1e-12)
    assert 0.0 <= fee <= 0.07 * 0.25 * contracts + 1e-12


@given(unit, st.floats(0.0, 1e4), st.floats(0.0, 1e4))
def test_the_exact_fee_is_linear_in_contracts(price, a, b):
    assert float(kalshi_fee(price, a + b, CONFIG)) == pytest.approx(
        float(kalshi_fee(price, a, CONFIG)) + float(kalshi_fee(price, b, CONFIG)), rel=1e-9, abs=1e-12)


@given(unit, st.floats(0.0, 1e4))
def test_the_per_contract_ceiling_is_never_cheaper_and_rounds_to_the_cent(price, contracts):
    exact = float(kalshi_fee(price, contracts, CONFIG))
    ceiling = float(kalshi_fee(price, 1.0, CEILING))
    assert float(kalshi_fee(price, contracts, CEILING)) >= exact - 1e-9
    assert round(ceiling * 100) == pytest.approx(ceiling * 100, abs=1e-9)


@given(hnp.arrays(np.float64, st.integers(1, 30), elements=unit))
def test_the_fee_vectorises(prices):
    np.testing.assert_allclose(kalshi_fee(prices, config=CONFIG), [float(kalshi_fee(p, config=CONFIG)) for p in prices])


# ------------------------------------------------------------------ Kelly


@given(open_unit, unit, st.sampled_from([YES, NO]))
def test_kelly_is_a_fraction_of_bankroll(price, q, side):
    assert 0.0 <= kelly_fraction(price, q, side) <= 1.0 + 1e-12


@given(open_unit, st.sampled_from([YES, NO]))
def test_no_edge_no_bet(price, side):
    assert kelly_fraction(price, price, side) == 0.0


@given(open_unit, unit)
def test_at_most_one_side_has_an_edge(price, q):
    assert kelly_fraction(price, q, YES) == 0.0 or kelly_fraction(price, q, NO) == 0.0


@given(open_unit, unit, unit)
def test_a_higher_true_probability_never_shrinks_a_yes_bet_or_grows_a_no_bet(price, q1, q2):
    low, high = sorted((q1, q2))
    assert kelly_fraction(price, low, YES) <= kelly_fraction(price, high, YES) + 1e-12
    assert kelly_fraction(price, low, NO) >= kelly_fraction(price, high, NO) - 1e-12


@given(open_unit, unit)
def test_the_two_sides_mirror_each_other(price, q):
    """Buying NO at p on probability q is buying YES at 1 - p on probability 1 - q."""
    assert kelly_fraction(price, q, NO) == pytest.approx(kelly_fraction(1 - price, 1 - q, YES), abs=1e-9)


@given(st.floats(allow_nan=False).filter(lambda p: not 0 < p < 1), unit)
def test_kelly_refuses_a_price_with_no_odds(price, q):
    with pytest.raises(ValueError):
        kelly_fraction(price, q, YES)


# ------------------------------------------------------------------ corpora


@st.composite
def corpora(draw, min_size=40, max_size=300):
    n = draw(st.integers(min_size, max_size))
    hours = np.sort(draw(hnp.arrays(np.float64, n, elements=st.floats(0, 2000))))
    lag = draw(hnp.arrays(np.float64, n, elements=st.floats(0, 48)))
    price = draw(hnp.arrays(np.float64, n, elements=st.floats(0.02, 0.98)))
    outcome = draw(hnp.arrays(np.int64, n, elements=st.integers(0, 1)))
    close = [T0 + timedelta(hours=float(h)) for h in hours]
    return pd.DataFrame({
        "ticker": [f"T{i}" for i in range(n)],
        "event_ticker": [f"E{i // 3}" for i in range(n)],
        "category": "Sports",
        "implied_price": price,
        "outcome": outcome,
        "close_ts": close,
        "settle_ts": [c + timedelta(hours=float(x)) for c, x in zip(close, lag)],
    })


@settings(max_examples=40)
@given(corpora(), st.floats(0.1, 0.9))
def test_the_split_never_trains_on_an_unsettled_market_or_trades_a_priced_one(df, fraction):
    config = strategy_config(train_fraction=fraction)
    split = time_split(df, config)
    assert (pd.to_datetime(split.train["settle_ts"], utc=True) < split.split_ts).all()
    priced = pd.to_datetime(split.test["close_ts"], utc=True) - pd.Timedelta(hours=config.clean.price_horizon_hours)
    assert (priced >= split.split_ts).all()
    assert not set(split.train["ticker"]) & set(split.test["ticker"])
    assert len(split.train) + len(split.test) + split.excluded == len(df)


@st.composite
def biased_corpora(draw):
    """A corpus with a favourite-longshot tilt, its shape drawn by Hypothesis and its rows by numpy: large
    enough for the strategy to find tradeable buckets, cheap enough to draw a dozen of."""
    seed = draw(st.integers(0, 2**31 - 1))
    n = draw(st.integers(300, 900))
    span = draw(st.floats(48, 4000))
    lag = draw(st.floats(0, 72))
    tilt = draw(st.floats(0, 0.4))
    per_event = draw(st.integers(1, 6))
    rng = np.random.default_rng(seed)
    price = rng.uniform(0.02, 0.98, n)
    close = [T0 + timedelta(hours=float(h)) for h in np.sort(rng.uniform(0, span, n))]
    return pd.DataFrame({
        "ticker": [f"T{i}" for i in range(n)],
        "event_ticker": [f"E{i // per_event}" for i in range(n)],
        "category": "Sports",
        "implied_price": price,
        "outcome": rng.binomial(1, np.clip(price + tilt * (price - 0.5), 0.01, 0.99)),
        "close_ts": close,
        "settle_ts": [c + timedelta(hours=float(x)) for c, x in zip(close, rng.uniform(0, lag, n))],
    }), seed


FAST = CONFIG.model_copy(update={"analysis": CONFIG.analysis.model_copy(update={"bootstrap_reps": 100})})


def test_a_corpus_with_nothing_settled_before_the_split_cannot_be_traded():
    """Every market closes at one instant, so none has settled by the split: there is nothing to learn from,
    and the backtest says so rather than trading on an empty rule table."""
    df = pd.DataFrame({"ticker": ["A", "B"], "event_ticker": ["E", "F"], "implied_price": [0.2, 0.8],
                       "outcome": [0, 1], "close_ts": [T0, T0], "settle_ts": [T0, T0]})
    assert time_split(df, CONFIG).train.empty
    with pytest.raises(ValueError, match="zero contracts"):
        backtest_bias_strategy(df, CONFIG)


@settings(max_examples=12)
@given(biased_corpora())
def test_shuffling_the_out_of_sample_outcomes_never_moves_a_position(case):
    df, seed = case
    ledger, _, split, _ = backtest_bias_strategy(df, FAST)

    rng = np.random.default_rng(seed + 1)
    shuffled = df.copy()
    mask = shuffled["ticker"].isin(set(split.test["ticker"])).to_numpy()
    shuffled.loc[mask, "outcome"] = rng.permutation(shuffled.loc[mask, "outcome"].to_numpy())
    again, _, _, _ = backtest_bias_strategy(shuffled, FAST)

    assert len(again) == len(ledger)
    if len(ledger):
        # The daily budget scales a day by its total cost, which is outcome-free too, so the scaled sizes
        # must match as well as the raw Kelly ones.
        for column in ("ticker", "side", "price", "estimate", "kelly_raw", "budget_scale", "stake", "contracts", "fee"):
            pd.testing.assert_series_equal(again[column], ledger[column], check_names=False)


@settings(max_examples=12)
@given(biased_corpora())
def test_no_position_exceeds_its_cap_and_no_day_exceeds_the_budget(case):
    ledger, metrics, _, _ = backtest_bias_strategy(case[0], FAST)
    if ledger.empty:
        assert metrics["trades"] == 0 and metrics["final_equity"] == 1.0
        return
    assert (ledger["stake"] <= FAST.strategy.max_position_fraction + 1e-12).all()
    day = pd.to_datetime(ledger["settle_ts"], utc=True).dt.date
    assert (ledger.groupby(day)["cost"].sum() <= FAST.strategy.max_daily_deployment + 1e-9).all()
    assert ((ledger["side"] == YES) | (ledger["side"] == NO)).all()
    assert (ledger["return_on_cost"] >= -1 - 1e-12).all()


# ------------------------------------------------------------------ the budget and the summary


@st.composite
def ledgers(draw):
    n = draw(st.integers(1, 60))
    days = draw(hnp.arrays(np.int64, n, elements=st.integers(0, 9)))
    price = draw(hnp.arrays(np.float64, n, elements=st.floats(0.02, 0.98)))
    stake = draw(hnp.arrays(np.float64, n, elements=st.floats(0.001, 0.02)))
    won = draw(hnp.arrays(np.bool_, n, elements=st.booleans()))
    contracts = stake / price
    fee = 0.07 * contracts * price * (1 - price)
    cost = stake + fee
    pnl = np.where(won, contracts, 0.0) - cost
    return pd.DataFrame({
        "settle_ts": [T0 + timedelta(days=int(d), hours=1) for d in days],
        "stake": stake, "contracts": contracts, "fee": fee, "slippage": 0.0, "cost": cost, "pnl": pnl,
        "won": won, "return_on_cost": pnl / cost,
    }).sort_values("settle_ts").reset_index(drop=True)


@given(ledgers(), st.floats(0.01, 2.0))
def test_the_budget_caps_each_day_and_keeps_every_return(ledger, budget):
    scaled = _apply_daily_budget(ledger, strategy_config(max_daily_deployment=budget))
    day = pd.to_datetime(scaled["settle_ts"], utc=True).dt.date
    assert (scaled.groupby(day)["cost"].sum() <= budget * (1 + 1e-9)).all()
    assert ((scaled["budget_scale"] > 0) & (scaled["budget_scale"] <= 1)).all()
    np.testing.assert_allclose(scaled["pnl"] / scaled["cost"], ledger["return_on_cost"], rtol=1e-9)
    # A day already under budget is untouched.
    under = ledger.groupby(pd.to_datetime(ledger["settle_ts"], utc=True).dt.date)["cost"].transform("sum") <= budget
    np.testing.assert_allclose(scaled.loc[under, "stake"], ledger.loc[under, "stake"])


@given(ledgers())
def test_the_summary_reconciles_with_its_ledger(ledger):
    ledger = _apply_daily_budget(ledger, CONFIG)
    m = summarise(ledger)
    assert m["trades"] == len(ledger)
    assert m["total_pnl"] == pytest.approx(ledger["pnl"].sum())
    assert m["gross_pnl"] == pytest.approx(m["total_pnl"] + m["fees_paid"])
    assert m["roi"] == pytest.approx(ledger["pnl"].sum() / ledger["cost"].sum())
    assert 0.0 <= m["hit_rate"] <= 1.0
    assert -1.0 <= m["max_drawdown"] <= 0.0
    assert m["final_equity"] >= 0.0
    curve = daily_equity(ledger)
    assert len(curve) == m["trading_days"]
    assert curve.iloc[-1] == pytest.approx(m["final_equity"])
    assert m["final_equity"] == pytest.approx(float(np.prod(1 + ledger.groupby(
        pd.to_datetime(ledger["settle_ts"], utc=True).dt.date)["pnl"].sum())))
