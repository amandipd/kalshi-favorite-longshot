"""The eight candidate entry filters from FILTER_SEARCH_PREREG.md, pinned against hand-worked values.

Every feature must be computable at the end of the entry minute from that minute and earlier ONLY. A feature
that can see minute 9, or the settlement, would score beautifully and be worthless live, so each test builds
a market whose later minutes contradict its earlier ones and checks the feature ignores them.
"""

from __future__ import annotations

import pytest


def mkt(quotes, yes=True, series="KXBTC15M"):
    """A market quoted {minute: (yes bid, yes ask)}; minutes left out have no quote."""
    return {"ticker": "T", "series": series, "group": "crypto", "yes": yes, "q": dict(quotes)}


def flat(bid, ask, lo=1, hi=15):
    return {k: (bid, ask) for k in range(lo, hi + 1)}


# ---------------------------------------------------------------- the spread family


def test_mean_spread_over_minutes_five_to_eight(study):
    fs = study.filter_search
    q = {**flat(0.50, 0.52), 5: (0.94, 0.95), 6: (0.94, 0.95), 7: (0.93, 0.95), 8: (0.93, 0.95)}
    # spreads 1c, 1c, 2c, 2c -> mean 1.5c
    assert fs.mean_spread_5_8(mkt(q), "yes", 8) == pytest.approx(0.015)


def test_the_spread_family_reads_the_favourites_own_quote(study):
    """On the NO side the quote turns round, but the gap is the same width either way."""
    fs = study.filter_search
    q = {**flat(0.05, 0.06), 5: (0.05, 0.06), 6: (0.05, 0.06), 7: (0.05, 0.07), 8: (0.05, 0.07)}
    assert fs.mean_spread_5_8(mkt(q), "no", 8) == pytest.approx(0.015)


def test_spread_trend_is_narrowing_when_negative(study):
    fs = study.filter_search
    q = {**flat(0.50, 0.52), 5: (0.90, 0.95), 8: (0.94, 0.95)}
    assert fs.spread_trend(mkt(q), "yes", 8) == pytest.approx(0.01 - 0.05)


def test_relative_spread_divides_by_the_series_normal(study):
    fs = study.filter_search
    q = {**flat(0.50, 0.52), 8: (0.93, 0.95)}
    medians = {"KXBTC15M": 0.01, "KXZEC15M": 0.04}
    assert fs.rel_spread(mkt(q, series="KXBTC15M"), "yes", 8, medians) == pytest.approx(2.0)
    assert fs.rel_spread(mkt(q, series="KXZEC15M"), "yes", 8, medians) == pytest.approx(0.5)


def test_relative_spread_without_a_median_for_that_series(study):
    fs = study.filter_search
    q = {**flat(0.50, 0.52), 8: (0.93, 0.95)}
    assert fs.rel_spread(mkt(q), "yes", 8, {}) is None


# ---------------------------------------------------------------- the settled family


def test_favourite_minutes_counts_the_whole_path(study):
    """The YES side leads only from minute 6, so three of the first eight minutes."""
    fs = study.filter_search
    q = {**{k: (0.40, 0.42) for k in range(1, 6)}, 6: (0.90, 0.92), 7: (0.93, 0.95), 8: (0.94, 0.95)}
    assert fs.fav_minutes(mkt(q), "yes", 8) == 3


def test_favourite_minutes_ignores_what_happens_after_entry(study):
    """Minutes 9-15 lead the other way; the feature must not see them."""
    fs = study.filter_search
    q = {**{k: (0.94, 0.95) for k in range(1, 9)}, **{k: (0.02, 0.03) for k in range(9, 16)}}
    assert fs.fav_minutes(mkt(q), "yes", 8) == 8


def test_travel_adds_up_every_step(study):
    fs = study.filter_search
    q = {1: (0.49, 0.51), 2: (0.59, 0.61), 3: (0.49, 0.51), 4: (0.49, 0.51),
         5: (0.49, 0.51), 6: (0.49, 0.51), 7: (0.49, 0.51), 8: (0.49, 0.51)}
    assert fs.travel(mkt(q), "yes", 8) == pytest.approx(0.20)   # up 10c then back down 10c


def test_a_price_that_sat_still_has_no_travel(study):
    fs = study.filter_search
    assert fs.travel(mkt(flat(0.94, 0.95)), "yes", 8) == pytest.approx(0.0)


def test_worst_dip_measures_the_fall_below_the_entry_mid(study):
    fs = study.filter_search
    q = {**flat(0.94, 0.95), 4: (0.70, 0.72)}
    assert fs.worst_dip(mkt(q), "yes", 8) == pytest.approx(0.945 - 0.71)


def test_minutes_since_the_last_coin_flip(study):
    fs = study.filter_search
    q = {**flat(0.94, 0.95), 6: (0.44, 0.46)}
    assert fs.since_coinflip(mkt(q), "yes", 8) == 2
    assert fs.since_coinflip(mkt(flat(0.94, 0.95)), "yes", 8) == 8, "never a coin flip"


# ---------------------------------------------------------------- staleness


def test_staleness_counts_unchanged_minutes_up_to_entry(study):
    fs = study.filter_search
    q = {**flat(0.90, 0.93), 6: (0.94, 0.95), 7: (0.94, 0.95), 8: (0.94, 0.95)}
    assert fs.staleness(mkt(q), "yes", 8) == 3


def test_a_quote_that_just_moved_is_not_stale(study):
    fs = study.filter_search
    q = {**flat(0.90, 0.93), 8: (0.94, 0.95)}
    assert fs.staleness(mkt(q), "yes", 8) == 1


# ---------------------------------------------------------------- missing quotes


@pytest.mark.parametrize("name", ["mean_spread_5_8", "spread_trend", "fav_minutes", "travel",
                                  "worst_dip", "since_coinflip", "staleness"])
def test_a_market_with_no_quotes_returns_none_rather_than_crashing(study, name):
    fs = study.filter_search
    assert getattr(fs, name)(mkt({}), "yes", 8) is None


def test_gaps_in_the_path_are_skipped_not_guessed(study):
    """Minutes 2-7 never quoted: travel has only one step to measure, and it is from minute 1."""
    fs = study.filter_search
    q = {1: (0.49, 0.51), 8: (0.94, 0.95)}
    assert fs.travel(mkt(q), "yes", 8) == pytest.approx(0.445)
    assert fs.fav_minutes(mkt(q), "yes", 8) == 1


# ---------------------------------------------------------------- the registry


def test_every_preregistered_feature_is_present(study):
    """FILTER_SEARCH_PREREG.md lists eight; the registry must hold exactly those, no more."""
    fs = study.filter_search
    assert sorted(fs.FEATURES) == sorted([
        "mean_spread_5_8", "rel_spread", "spread_trend",
        "fav_minutes", "travel", "worst_dip", "since_coinflip", "staleness"])


def test_each_feature_says_which_side_of_its_threshold_keeps_a_bet(study):
    """A feature is useless without knowing whether high or low values are the warning sign."""
    fs = study.filter_search
    for name, spec in fs.FEATURES.items():
        assert spec["worse"] in ("high", "low"), name
