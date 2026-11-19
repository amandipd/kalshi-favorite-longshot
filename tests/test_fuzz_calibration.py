"""Property-based tests for kalshi_calibration/analysis/calibration.py and segmentation.py.

The calibration table is the study's headline, so these check its bookkeeping holds on any corpus: every
contract lands in exactly one bucket, the Murphy identity closes, `bias` is realized minus price and nothing
else, and segmenting never loses or invents a contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from kalshi_calibration.analysis.calibration import assign_buckets, brier_decomposition, brier_score, calibration_table
from kalshi_calibration.analysis.segmentation import bias_by_lifetime, lifetime_hours, segment_calibration
from test_calibration import make_config

CONFIG = make_config(bootstrap_reps=100)
unit = st.floats(0.0, 1.0)


@st.composite
def corpora(draw, min_size=1, max_size=120, interior=False):
    n = draw(st.integers(min_size, max_size))
    prices = st.floats(0.001, 0.999) if interior else unit
    price = draw(hnp.arrays(np.float64, n, elements=prices))
    outcome = draw(hnp.arrays(np.int64, n, elements=st.integers(0, 1)))
    event = draw(hnp.arrays(np.int64, n, elements=st.integers(0, max(1, n // 3))))
    return pd.DataFrame({"implied_price": price, "outcome": outcome, "event_ticker": [f"E{e}" for e in event]})


# ------------------------------------------------------------------ buckets


@given(hnp.arrays(np.float64, st.integers(0, 200), elements=unit), st.integers(2, 50))
def test_every_price_lands_in_the_bucket_that_contains_it(prices, k):
    buckets = assign_buckets(prices, k)
    assert buckets.shape == prices.shape
    assert np.all((buckets >= 0) & (buckets < k))
    inside = prices < 1.0
    assert np.all(buckets[inside] * (1.0 / k) <= prices[inside] + 1e-12)
    assert np.all(prices[inside] < (buckets[inside] + 1) * (1.0 / k) + 1e-12)
    assert np.all(buckets[~inside] == k - 1)


@given(unit, unit, st.integers(2, 50))
def test_buckets_are_monotone_in_price(a, b, k):
    low, high = sorted((a, b))
    assert assign_buckets([low], k)[0] <= assign_buckets([high], k)[0]


@given(st.floats(allow_nan=False).filter(lambda x: x < 0 or x > 1), st.integers(2, 20))
def test_a_price_outside_the_unit_interval_is_refused(price, k):
    with pytest.raises(ValueError):
        assign_buckets([0.5, price], k)


# ------------------------------------------------------------------ Brier and Murphy


@given(corpora())
def test_brier_is_a_mean_squared_error_in_the_unit_interval(df):
    score = brier_score(df)
    assert 0.0 <= score <= 1.0
    assert score == pytest.approx(float(np.mean((df["implied_price"] - df["outcome"]) ** 2)))


@given(corpora(), st.integers(2, 30))
def test_the_murphy_identity_closes_on_the_binned_score_for_any_corpus(df, k):
    parts = brier_decomposition(df, n_buckets=k, config=CONFIG)
    assert parts["binned_brier"] == pytest.approx(
        parts["reliability"] - parts["resolution"] + parts["uncertainty"], abs=1e-12)
    assert parts["brier"] - parts["binned_brier"] == pytest.approx(parts["binning_residual"], abs=1e-15)
    assert parts["reliability"] >= 0 and parts["resolution"] >= 0
    assert 0 <= parts["uncertainty"] <= 0.25 + 1e-15
    assert parts["n"] == len(df) and parts["n_buckets"] == k


@given(corpora(), st.integers(2, 30))
def test_the_binning_residual_is_within_bucket_spread_less_twice_its_covariance_with_the_outcome(df, k):
    """Raw minus binned Brier, expanded per bucket with p the price, f the bucket's mean price, o the outcome:
    sum (p - f)^2 - 2 (p - f) o, over N. It can take either sign -- binning is not a least-squares fit to the
    outcomes -- so this pins its value rather than a direction."""
    parts = brier_decomposition(df, n_buckets=k, config=CONFIG)
    p, o = df["implied_price"].to_numpy(), df["outcome"].to_numpy()
    f = pd.Series(p).groupby(assign_buckets(p, k)).transform("mean").to_numpy()
    expected = float(np.sum((p - f) ** 2 - 2 * (p - f) * o)) / len(p)
    assert parts["binning_residual"] == pytest.approx(expected, abs=1e-12)


# ------------------------------------------------------------------ the table


@settings(max_examples=25)
@given(corpora(min_size=2))
def test_the_table_accounts_for_every_contract_once(df):
    table = calibration_table(df, config=CONFIG)
    assert table["n"].sum() == len(df)
    assert list(table["bucket"]) == sorted(table["bucket"]) and table["bucket"].is_unique
    yes = table["realized_freq"] * table["n"]
    assert yes.sum() == pytest.approx(df["outcome"].sum())


@settings(max_examples=25)
@given(corpora(min_size=2))
def test_bias_is_realized_minus_price_and_every_rate_is_a_probability(df):
    table = calibration_table(df, config=CONFIG)
    np.testing.assert_allclose(table["bias"], table["realized_freq"] - table["mean_price"], atol=1e-12)
    for column in ("realized_freq", "mean_price", "wilson_low", "wilson_high", "ci_low", "ci_high"):
        assert table[column].between(0, 1).all(), column
    assert (table["ci_low"] <= table["ci_high"]).all()
    assert (table["wilson_low"] <= table["realized_freq"] + 1e-12).all()
    assert (table["realized_freq"] <= table["wilson_high"] + 1e-12).all()
    assert table["p_value"].between(0, 1).all()
    assert (table["n_events"] <= table["n"]).all()


@settings(max_examples=15)
@given(corpora(min_size=2))
def test_the_table_is_reproducible(df):
    pd.testing.assert_frame_equal(calibration_table(df, config=CONFIG), calibration_table(df, config=CONFIG))


# ------------------------------------------------------------------ segmentation

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@settings(max_examples=20)
@given(corpora(min_size=4, max_size=80), st.lists(st.sampled_from(["A", "B", "C"]), min_size=80, max_size=80))
def test_segments_partition_the_corpus_and_share_one_correction_family(df, labels):
    df = df.assign(segment=labels[: len(df)])
    out = segment_calibration(df, "segment", config=CONFIG)
    assert out["n"].sum() == len(df)
    assert out.groupby("segment")["n"].sum().to_dict() == df["segment"].value_counts().to_dict()
    assert out.loc[out["underpowered"], "q_value"].isna().all()
    assert not out.loc[out["underpowered"], "significant"].any()
    tested = out.loc[~out["underpowered"]]
    assert (tested["q_value"] >= tested["p_value"] - 1e-15).all()


@given(st.lists(st.floats(0, 5000), min_size=1, max_size=40))
def test_lifetime_is_close_minus_open_in_hours(hours):
    df = pd.DataFrame({"open_ts": [T0] * len(hours), "close_ts": [T0 + timedelta(hours=h) for h in hours]})
    np.testing.assert_allclose(lifetime_hours(df).to_numpy(), hours, atol=1e-6)


@settings(max_examples=15)
@given(corpora(min_size=8, max_size=80), st.data())
def test_lifetime_buckets_cover_every_contract(df, data):
    hours = data.draw(hnp.arrays(np.float64, len(df), elements=st.floats(0.5, 2000)))
    df = df.assign(open_ts=[T0] * len(df), close_ts=[T0 + timedelta(hours=float(h)) for h in hours])
    if np.unique(hours).size < 2:
        with pytest.raises(ValueError, match="same lifetime"):
            bias_by_lifetime(df, config=CONFIG)
        return
    out = bias_by_lifetime(df, config=CONFIG)
    assert out["n"].sum() == len(df)
    assert 1 <= out["segment"].nunique() <= 4
