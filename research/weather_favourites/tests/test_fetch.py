"""Tests for fetch.py's pure parts: which markets it wants, how it batches them and how it shrinks a candle.

    python -m pytest research/weather_favourites/tests -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetch  # noqa: E402


def test_compact_reads_historical_candles():
    c = {"end_period_ts": 1787634000, "yes_bid": {"close": "0.0400", "open": "0.03"}, "yes_ask": {"close": "0.0500"}}
    assert fetch.compact(c) == [1787634000, 0.04, 0.05]


def test_compact_reads_live_candles():
    c = {"end_period_ts": 1793077200, "yes_bid": {"close_dollars": "0.9500"}, "yes_ask": {"close_dollars": "0.9600"}}
    assert fetch.compact(c) == [1793077200, 0.95, 0.96]


def test_compact_keeps_a_missing_side_as_none():
    assert fetch.compact({"end_period_ts": 5, "yes_bid": None, "yes_ask": {"close": ""}}) == [5, None, None]


@pytest.mark.parametrize("series,event,want", [
    ("KXHIGHNY", "KXHIGHNY-25JUL17", False),     # before the older part
    ("KXHIGHNY", "KXHIGHNY-25JUL18", True),
    ("KXHIGHNY", "KXHIGHNY-26AUG10", True),      # seen: fetched, reported apart
    ("KXHIGHNY", "KXHIGHNY-26OCT24", True),
    ("KXRAIN", "KXRAIN-26JUL15", True),
    ("KXLOWTNYC", "KXLOWTNYC-26OCT24", False),   # not in either family
])
def test_wanted(series, event, want):
    assert fetch.wanted({"series": series, "event": event, "result": "yes"}) is want


def test_unsettled_or_voided_markets_are_not_wanted():
    assert not fetch.wanted({"series": "KXRAIN", "event": "KXRAIN-26OCT24", "result": ""})
    assert not fetch.wanted({"series": "KXRAIN", "event": "KXRAIN-26OCT24", "result": "void"})


def test_batches_hold_at_most_20_markets_closing_within_the_same_hour():
    ms = [{"ticker": f"A{i}", "close": 1000} for i in range(25)] + [{"ticker": "B", "close": 1000 + 3600}]
    bs = fetch.batches(ms)
    assert [len(b) for b in bs] == [20, 5, 1]
    assert all(max(m["close"] for m in b) - min(m["close"] for m in b) < 3600 for b in bs)


def test_series_list_is_rain_plus_the_24_highs():
    assert fetch.SERIES[0] == "KXRAIN" and len(fetch.SERIES) == 25 and len(set(fetch.SERIES)) == 25
