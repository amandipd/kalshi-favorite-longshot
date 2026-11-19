"""Tests for check.py: Kalshi's settled values against the NWS daily climate reports.

    python -m pytest research/weather_favourites/tests -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import check  # noqa: E402


def high(ticker, value, result="no", station=None):
    return {"series": ticker.split("-")[0], "ticker": ticker, "event": ticker.rsplit("-", 1)[0], "value": value,
            "result": result, "station": station}


def rain(city, date_code, value, result, station=None):
    return {"series": "KXRAIN", "ticker": f"KXRAIN-{date_code}-{city}", "event": f"KXRAIN-{date_code}", "value": value,
            "result": result, "station": station}


def test_station_is_borrowed_from_other_markets_of_the_same_series_or_rain_city():
    ms = [high("KXHIGHNY-26OCT24-B59.5", "60.00", station="NYC"), high("KXHIGHNY-25AUG01-B80.5", "81.00"),
          rain("WPB", "26OCT24", "0.13", "yes", station="DJT"), rain("WPB", "26JUL20", "0.00", "no"),
          rain("XYZ", "26JUL20", "0.00", "no")]
    st = check.stations(ms)
    assert st["KXHIGHNY-25AUG01-B80.5"] == "NYC" and st["KXRAIN-26JUL20-WPB"] == "DJT"
    assert st["KXRAIN-26JUL20-XYZ"] is None


def test_a_high_event_is_checked_once_and_matches_the_report():
    ms = [high("KXHIGHNY-26OCT24-B59.5", "60.00", "yes", "NYC"), high("KXHIGHNY-26OCT24-T66", "60.00", "no", "NYC")]
    out = check.compare(ms, {"NYC": {"2026-10-24": {"high": 60, "precip": 0.0}}})
    assert out["highs"] == {"checked": 1, "match": 1, "mismatch": [], "no report": 0}


def test_a_high_that_differs_from_the_report_is_listed():
    ms = [high("KXHIGHNY-26OCT24-B59.5", "61.00", "no", "NYC")]
    out = check.compare(ms, {"NYC": {"2026-10-24": {"high": 60, "precip": 0.0}}})
    assert out["highs"]["mismatch"] == [("KXHIGHNY-26OCT24", 61.0, 60)]


def test_a_high_without_a_kalshi_value_is_checked_by_its_winning_bracket():
    cli = {"NYC": {"2026-01-12": {"high": 65, "precip": 0.0}}}
    ok = [high("KXHIGHNY-26JAN12-B64.5", None, "yes", "NYC"), high("KXHIGHNY-26JAN12-B62.5", None, "no", "NYC"),
          high("KXHIGHNY-26JAN12-T66", None, "no", "NYC"), high("KXHIGHNY-26JAN12-T61", None, "no", "NYC")]
    assert check.compare(ok, cli)["highs"]["match"] == 1
    top = [high("KXHIGHNY-26JAN12-B64.5", None, "no", "NYC"), high("KXHIGHNY-26JAN12-T66", None, "yes", "NYC")]
    assert check.compare(top, cli)["highs"]["mismatch"] == [("KXHIGHNY-26JAN12", "T66", 65)]
    low = [high("KXHIGHNY-26JAN12-B64.5", None, "no", "NYC"), high("KXHIGHNY-26JAN12-T61", None, "yes", "NYC")]
    assert check.compare(low, cli)["highs"]["mismatch"] == [("KXHIGHNY-26JAN12", "T61", 65)]


def test_rain_trace_counts_as_no_rain_and_missing_report_is_counted():
    ms = [rain("NYC", "26OCT24", "0.00", "no", "NYC"), rain("MIA", "26OCT24", "0.00", "no", "MIA")]
    cli = {"NYC": {"2026-10-24": {"high": 60, "precip": "T"}}}
    out = check.compare(ms, cli)
    assert out["rain"] == {"checked": 1, "match": 1, "mismatch": [], "no report": 1}


def test_rain_result_against_measurable_rain():
    ms = [rain("NYC", "26OCT24", "0.00", "no", "NYC")]
    out = check.compare(ms, {"NYC": {"2026-10-24": {"high": 60, "precip": 0.05}}})
    assert out["rain"]["mismatch"] == [("KXRAIN-26OCT24-NYC", "no", 0.05)]
