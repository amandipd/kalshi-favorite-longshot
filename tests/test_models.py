"""Tests for kalshi_calibration/models.py: the Contract schema every processed row passes through.

The model is the last gate in kalshi_calibration/clean.py -- a row it rejects is counted as `model_validation_failed`
rather than written -- so its three invariants are what keep an impossible row out of the study:
a price is a probability, an outcome is 0 or 1, and nothing settles before it opened.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from kalshi_calibration.models import Contract, Venue

T0 = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)


def contract(**overrides) -> Contract:
    fields = dict(
        venue="kalshi", ticker="KXCPI-26MAR-T0.3", event_ticker="KXCPI-26MAR", category="Economics",
        title="CPI above 0.3%?", implied_price=0.42, outcome=1, volume=1250.0,
        open_ts=T0, close_ts=T0 + timedelta(hours=24), settle_ts=T0 + timedelta(hours=26),
    )
    fields.update(overrides)
    return Contract(**fields)


def test_a_valid_contract_round_trips():
    c = contract()
    assert c.venue is Venue.KALSHI
    assert Contract(**c.model_dump()) == c


def test_venue_values_are_the_lowercase_names():
    assert {v.value for v in Venue} == {"kalshi", "polymarket"}
    assert Venue("polymarket") is Venue.POLYMARKET


def test_an_unknown_venue_is_refused():
    with pytest.raises(ValidationError, match="venue"):
        contract(venue="predictit")


@pytest.mark.parametrize("price", [0.0, 1.0, 0.001, 0.999])
def test_prices_at_and_inside_the_bounds_are_probabilities(price):
    assert contract(implied_price=price).implied_price == price


@pytest.mark.parametrize("price", [-0.001, 1.001, math.nan, math.inf, -math.inf])
def test_a_price_that_isnt_a_probability_is_refused(price):
    with pytest.raises(ValidationError, match="implied_price"):
        contract(implied_price=price)


@pytest.mark.parametrize("outcome", [2, -1, 0.5])
def test_outcome_must_be_binary(outcome):
    with pytest.raises(ValidationError, match="outcome"):
        contract(outcome=outcome)


@pytest.mark.parametrize("outcome,expected", [(0, 0), (1, 1), (True, 1), (1.0, 1), ("0", 0)])
def test_outcome_coerces_unambiguous_spellings_of_0_and_1(outcome, expected):
    assert contract(outcome=outcome).outcome == expected


def test_settling_before_opening_is_refused():
    with pytest.raises(ValidationError, match="settle_ts"):
        contract(settle_ts=T0 - timedelta(seconds=1))


def test_settling_the_instant_it_opens_is_allowed():
    assert contract(settle_ts=T0, close_ts=T0).settle_ts == T0


def test_close_after_settlement_is_not_a_model_rule():
    """Only settle >= open is enforced: close and settle are ordered by the venue, not by this schema."""
    c = contract(close_ts=T0 + timedelta(days=3), settle_ts=T0 + timedelta(days=1))
    assert c.close_ts > c.settle_ts


def test_timestamps_parse_from_iso_strings():
    c = contract(open_ts="2026-03-01T12:00:00Z", close_ts="2026-03-02T12:00:00Z", settle_ts="2026-03-02T14:00:00Z")
    assert c.open_ts == T0


@pytest.mark.parametrize("field", ["ticker", "event_ticker", "category", "title", "volume", "open_ts"])
def test_every_field_is_required(field):
    fields = contract().model_dump()
    del fields[field]
    with pytest.raises(ValidationError, match=field):
        Contract(**fields)


# ------------------------------------------------------------------ fuzz

finite = st.floats(allow_nan=True, allow_infinity=True)


@given(finite)
def test_fuzz_price_is_accepted_exactly_when_it_is_a_probability(price):
    if not math.isnan(price) and 0.0 <= price <= 1.0:
        assert contract(implied_price=price).implied_price == price
    else:
        with pytest.raises(ValidationError):
            contract(implied_price=price)


@given(st.integers(-1000, 1000))
def test_fuzz_outcome_is_accepted_exactly_when_it_is_0_or_1(outcome):
    if outcome in (0, 1):
        assert contract(outcome=outcome).outcome == outcome
    else:
        with pytest.raises(ValidationError):
            contract(outcome=outcome)


@given(st.timedeltas(min_value=timedelta(days=-400), max_value=timedelta(days=400)))
def test_fuzz_settlement_never_precedes_opening(offset):
    settle = T0 + offset
    if settle >= T0:
        assert contract(settle_ts=settle).settle_ts == settle
    else:
        with pytest.raises(ValidationError):
            contract(settle_ts=settle)


@given(st.text(max_size=40), st.text(max_size=40))
def test_fuzz_any_text_is_a_valid_ticker_and_title(ticker, title):
    """Text fields are carried verbatim: the venue's spelling, not a sanitised one."""
    c = contract(ticker=ticker, title=title)
    assert (c.ticker, c.title) == (ticker, title)
