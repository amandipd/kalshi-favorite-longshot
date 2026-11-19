"""Tests for score.py, the frozen favourite rule of PREREG.md on daily rain and daily highs.

No test touches the network. Candles are the compact form fetch.py saves: [end_ts, yes_bid, yes_ask], prices in
dollars, None where Kalshi gave no value.

    python -m pytest research/weather_favourites/tests -q
"""
import math
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import score  # noqa: E402

CLOSE = 1793077200          # 2026-10-26 05:00 UTC, local standard midnight in New York
H = 3600


def candles(*quotes, last=CLOSE):
    """Hourly candles ending at last, last - 1h, ... one per (bid, ask), the last quote first."""
    return [[last - i * H, b, a] for i, (b, a) in enumerate(quotes)][::-1]


def market(cs, result="no", close=CLOSE, event="KXHIGHNY-26OCT25", series="KXHIGHNY"):
    return {"series": series, "ticker": event + "-B60.5", "event": event, "close": close, "result": result, "candles": cs}


# --- the quote at the checkpoint -------------------------------------------------------------------------------

def test_quote_is_the_last_candle_ending_at_or_before_the_checkpoint():
    cs = [[CLOSE - 8 * H, 0.10, 0.12], [CLOSE - 6 * H, 0.04, 0.05], [CLOSE - 5 * H, 0.50, 0.52]]
    assert score.quote_at(cs, CLOSE - 6 * H) == (0.04, 0.05)


def test_no_quote_before_the_first_candle():
    assert score.quote_at([[CLOSE - 5 * H, 0.04, 0.05]], CLOSE - 6 * H) is None


def test_open_needs_a_candle_ending_after_the_checkpoint():
    assert score.open_after([[CLOSE - 7 * H, 0.04, 0.05], [CLOSE - 5 * H, 0.04, 0.05]], CLOSE - 6 * H)
    assert not score.open_after([[CLOSE - 7 * H, 0.04, 0.05], [CLOSE - 6 * H, 0.04, 0.05]], CLOSE - 6 * H)


# --- the rule ---------------------------------------------------------------------------------------------------

def test_no_favourite_is_bought_at_one_minus_the_bid():
    b = score.bet(market(candles(*[(0.04, 0.05)] * 10), result="no"), 6)
    assert b["side"] == "no" and b["price"] == pytest.approx(0.96)


def test_yes_favourite_is_bought_at_the_ask():
    b = score.bet(market(candles(*[(0.95, 0.96)] * 10), result="yes"), 6)
    assert b["side"] == "yes" and b["price"] == pytest.approx(0.96)


def test_a_market_closed_before_the_checkpoint_is_skipped():
    # a rain market that closed early at 8 hours before the scheduled close: its last quote must not be carried
    cs = [[CLOSE - 10 * H, 0.02, 0.03], [CLOSE - 9 * H, 0.02, 0.03], [CLOSE - 8 * H, 0.02, 0.03]]
    assert score.bet(market(cs, result="yes", series="KXRAIN", event="KXRAIN-26OCT25"), 6) is None


def test_spread_of_exactly_three_cents_passes_and_four_does_not():
    assert score.bet(market(candles(*[(0.94, 0.97)] * 10), result="yes"), 6) is not None
    assert score.bet(market(candles(*[(0.93, 0.97)] * 10), result="yes"), 6) is None


@pytest.mark.parametrize("bid,ask", [(0.88, 0.899), (0.0, 0.02), (0.98, 1.0), (None, 0.95), (0.95, None)])
def test_no_bet_outside_90_to_99_9_or_without_a_two_sided_quote(bid, ask):
    assert score.bet(market(candles(*[(bid, ask)] * 10)), 6) is None


def test_a_99_9c_favourite_is_still_bought():
    assert score.bet(market(candles(*[(0.998, 0.999)] * 10), result="yes"), 6) is not None


def test_no_bet_when_both_sides_cost_the_same():
    assert score.bet(market(candles(*[(0.50, 0.50)] * 10)), 6) is None


def test_two_hour_checkpoint_reads_a_later_quote():
    cs = candles(*([(0.40, 0.42)] * 3 + [(0.95, 0.96)] * 7))   # candles ending 0, 1 and 2 hours before close: 40/42
    assert score.bet(market(cs, result="yes"), 6)["price"] == pytest.approx(0.96)
    assert score.bet(market(cs, result="yes"), 2) is None


# --- payoff ------------------------------------------------------------------------------------------------------

def test_fee_rounds_up_to_the_cent():
    assert score.fee(10 / 0.954, 0.954) == pytest.approx(0.04)


def test_win_and_loss_pay_ten_dollar_bets_with_the_fill_gap_and_fee():
    win = score.bet(market(candles(*[(0.94, 0.95)] * 10), result="yes"), 6)
    lose = score.bet(market(candles(*[(0.94, 0.95)] * 10), result="no"), 6)
    c = 10 / 0.954
    assert win["pnl"] == pytest.approx(c - 10 - 0.04)
    assert lose["pnl"] == pytest.approx(-10 - 0.04)
    assert win["won"] and not lose["won"]


def test_bet_carries_its_band_date_and_city():
    b = score.bet(market(candles(*[(0.94, 0.95)] * 10), result="yes"), 6)
    assert b["band"] == "95-97" and b["date"] == date(2026, 10, 25) and b["city"] == "KXHIGHNY"


def test_rain_city_comes_from_the_ticker():
    m = market(candles(*[(0.04, 0.05)] * 10), series="KXRAIN", event="KXRAIN-26OCT25")
    m["ticker"] = "KXRAIN-26OCT25-WPB"
    assert score.bet(m, 6)["city"] == "KXRAIN-WPB"


@pytest.mark.parametrize("price,band", [(0.90, "90-95"), (0.9499, "90-95"), (0.95, "95-97"), (0.97, "97-99"),
                                        (0.99, "99-99.9"), (0.999, "99-99.9")])
def test_bands(price, band):
    assert score.band(price) == band


# --- dates and parts ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("event,day", [("KXHIGHNY-26OCT24", date(2026, 10, 24)), ("KXRAIN-26JUL15", date(2026, 7, 15)),
                                       ("KXHIGHTSFO-25DEC01", date(2025, 12, 1))])
def test_climate_date_comes_from_the_event_ticker(event, day):
    assert score.climate_date(event) == day


@pytest.mark.parametrize("day,part", [(date(2025, 7, 17), None), (date(2025, 7, 18), "older"), (date(2026, 7, 17), "older"),
                                      (date(2026, 7, 18), "seen"), (date(2026, 9, 29), "seen"), (date(2026, 9, 30), "recent")])
def test_parts(day, part):
    assert score.part(day) == part


# --- statistics ----------------------------------------------------------------------------------------------------

def rows(*pnl_by_date):
    """Bets as score.bet returns them, from (date, pnl) pairs."""
    return [{"date": d, "pnl": p, "band": "95-97", "city": "X", "price": 0.95, "won": p > 0} for d, p in pnl_by_date]


def test_clustered_mean_and_error_treat_a_date_as_one_draw():
    d1, d2, d3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)
    rs = rows((d1, 1.0), (d1, 1.0), (d2, -1.0), (d3, 2.0))
    mu, se = score.clustered(rs)
    assert mu == pytest.approx(0.75)
    # cluster sums of (pnl - mu): d1 0.5, d2 -1.75, d3 1.25 -> sqrt(sum sq * g / (g - 1)) / n
    assert se == pytest.approx(math.sqrt((0.25 + 3.0625 + 1.5625) * 3 / 2) / 4)


def test_verdict_is_not_enough_data_under_1000_bets_or_20_dates():
    few = rows(*[(date(2026, 10, 1 + i % 25), 0.5) for i in range(999)])
    assert score.verdict(few)["verdict"] == "not enough data yet"
    narrow = rows(*[(date(2026, 10, 1 + i % 19), 0.5) for i in range(2000)])
    assert score.verdict(narrow)["verdict"] == "not enough data yet"


def test_verdict_fails_when_profit_is_under_two_cents_a_bet():
    rs = rows(*[(date(2026, 1 + i % 10, 1 + i % 25), 0.01) for i in range(2000)])
    v = score.verdict(rs)
    assert v["verdict"] == "fail" and "under +2c a $10 bet" in v["why"]
