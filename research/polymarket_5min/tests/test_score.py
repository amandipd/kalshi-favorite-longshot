"""Tests for score.py: reading Polymarket US price history into minute quotes, its fee, bet sizing and the rule."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import score  # noqa: E402

T0 = 1_793_000_100   # a window start (multiple of 300)


def rec(points, yes=True, coin="btc", start=T0):
    return {"slug": f"x-{coin}-{start}", "coin": coin, "start": start, "status": "MARKET_STATUS_RESOLVED",
            "yes": yes, "h": points}


# ------------------------------------------------------------ quotes


def test_quotes_read_the_point_a_minute_before_with_the_default_offset():
    # stamp (k-1)*60 holds the book at the end of minute k
    pts = [[0, 0.60, 0.45], [60, 0.80, 0.25], [120, 0.95, 0.06], [180, 0.97, 0.04], [240, 0.99, 0.02]]
    bid, ask = score.quotes(pts, offset=60)
    assert ask[0] == pytest.approx(0.60) and bid[0] == pytest.approx(0.55)   # end of minute 1 = stamp 0
    assert ask[2] == pytest.approx(0.95) and bid[2] == pytest.approx(0.94)   # end of minute 3 = stamp 120
    assert len(bid) == len(ask) == 5


def test_quotes_with_no_offset_read_the_stamp_at_the_minute_end():
    pts = [[60, 0.70, 0.35], [180, 0.96, 0.05]]
    bid, ask = score.quotes(pts, offset=0)
    assert ask[0] == pytest.approx(0.70)          # end of minute 1 = stamp 60
    assert ask[2] == pytest.approx(0.96)          # end of minute 3 = stamp 180
    assert math.isnan(ask[1]) and math.isnan(bid[1])   # no stamp 120


def test_quotes_take_a_point_within_5_seconds_but_not_further():
    bid, ask = score.quotes([[123, 0.95, 0.06], [180 + 9, 0.97, 0.04]], offset=60)
    assert ask[2] == pytest.approx(0.95)
    assert math.isnan(ask[3])


def test_quotes_outside_0_to_1_are_missing():
    # a longPrice of 1 (no Yes ask) or a shortPrice of 1 (no Yes bid) is no quote
    bid, ask = score.quotes([[0, 1.0, 0.03], [60, 0.97, 1.0], [120, 0.0, 1.0]], offset=60)
    assert math.isnan(ask[0]) and not math.isnan(bid[0])
    assert math.isnan(bid[1]) and not math.isnan(ask[1])
    assert math.isnan(ask[2]) and math.isnan(bid[2])


# ------------------------------------------------------------ fee and bet


def test_fee_rounds_to_the_nearest_cent_half_to_even():
    # 100 contracts at 0.90 and 0.0695: 0.6255 -> 0.63 (the fee page's example: $0.63)
    assert score.fee(100, 0.90, 0.0695) == pytest.approx(0.63)
    # 100 at 0.99: 0.068805 -> 0.07 (the fee page: $0.07)
    assert score.fee(100, 0.99, 0.0695) == pytest.approx(0.07)
    # exactly half a cent goes to the even cent: 0.125 -> 0.12
    assert score.fee(1, 0.5, 0.5) == pytest.approx(0.12)
    # a small order can round to zero
    assert score.fee(1, 0.99, 0.095) == 0.0


def test_bet_buys_fractional_contracts_floored_to_a_hundredth():
    pnl, cost, c = score.bet(np.array([0.95]), np.array([True]), theta=0.085)
    assert c[0] == pytest.approx(10.52)            # 10 / 0.95 = 10.526 -> 10.52
    assert cost[0] == pytest.approx(10.52 * 0.95)
    f = score.fee(10.52, 0.95, 0.085)               # 0.0425 -> 0.04
    assert f == pytest.approx(0.04)
    assert pnl[0] == pytest.approx(10.52 - 10.52 * 0.95 - 0.04)


def test_a_losing_bet_loses_its_cost_and_fee():
    pnl, cost, _ = score.bet(np.array([0.92]), np.array([False]), theta=0.085)
    assert pnl[0] == pytest.approx(-cost[0] - score.fee(10.86, 0.92, 0.085))


def test_slip_raises_the_price_but_never_past_99c():
    _, cost, c = score.bet(np.array([0.99]), np.array([True]), theta=0.085, slip=0.01)
    assert cost[0] / c[0] == pytest.approx(0.99)
    _, cost, c = score.bet(np.array([0.95]), np.array([True]), theta=0.085, slip=0.01)
    assert cost[0] / c[0] == pytest.approx(0.96)


# ------------------------------------------------------------ loading and the rule


def path(pts_list):
    """Points for one market from five (yes_ask, yes_bid) pairs: the ends of minutes 1-5."""
    return [[(k) * 60, a, round(1 - b, 4)] for k, (a, b) in enumerate(pts_list)]


def test_build_skips_missing_and_unresolved_markets_and_counts_them():
    good = rec(path([(0.6, 0.55), (0.9, 0.88), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)]))
    missing = {"slug": "m", "coin": "btc", "start": T0, "missing": True}
    open_ = dict(rec(path([(0.6, 0.55)] * 5)), yes=None)
    d, counts = score.build([good, missing, open_], offset=60)
    assert len(d["yes"]) == 1
    assert counts == {"markets": 1, "missing": 1, "unresolved": 1}
    assert d["ask"].shape == (1, 5)


def test_the_rule_bets_a_clean_92c_plus_favourite_at_minute_3():
    good = rec(path([(0.6, 0.55), (0.9, 0.88), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)]))
    d, _ = score.build([good], offset=60)
    m, side_yes, top = score.rule(d, M=3)
    assert m.tolist() == [True] and side_yes.tolist() == [True] and top[0] == pytest.approx(0.95)


def test_the_rule_bets_the_no_side_when_it_is_the_favourite():
    # Yes ask 6c, Yes bid 5c -> No ask 95c, No bid 94c
    no_fav = rec(path([(0.4, 0.38), (0.11, 0.09), (0.06, 0.05), (0.03, 0.02), (0.01, 0.0)]), yes=False)
    d, _ = score.build([no_fav], offset=60)
    m, side_yes, top = score.rule(d, M=3)
    assert m.tolist() == [True] and side_yes.tolist() == [False] and top[0] == pytest.approx(0.95)
    assert score.won(d, side_yes).tolist() == [True]


@pytest.mark.parametrize("pts,why", [
    ([(0.6, 0.55), (0.9, 0.88), (0.95, 0.93), (0.97, 0.96), (0.99, 0.98)], "spread 2c"),
    ([(0.6, 0.55), (0.82, 0.80), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)], "jump 13.5c in minute 3"),
    ([(0.6, 0.55), (0.51, 0.49), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)], "coin flip at minute 2"),
    ([(0.5, 0.48), (0.9, 0.88), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)], "coin flip at minute 1"),
    ([(0.6, 0.55), (0.9, 0.88), (0.91, 0.90), (0.97, 0.96), (0.99, 0.98)], "under 92c"),
])
def test_the_rule_skips_the_kalshi_warning_signs(pts, why):
    d, _ = score.build([rec(path(pts))], offset=60)
    m, _, _ = score.rule(d, M=3)
    assert m.tolist() == [False], why


def test_the_late_sign_at_m_minus_1_only_ignores_minute_1():
    pts = [(0.5, 0.48), (0.9, 0.88), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)]
    d, _ = score.build([rec(pts and path(pts))], offset=60)
    assert score.rule(d, M=3, late="m1").__getitem__(0).tolist() == [True]
    assert score.rule(d, M=3, late=None).__getitem__(0).tolist() == [True]


def test_fed_blackout_covers_windows_overlapping_oct_28_2pm_to_330pm_et():
    t = score.FED[0][0]                      # 2:00 PM ET, Oct 28 2026
    good = path([(0.6, 0.55), (0.9, 0.88), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)])
    d, _ = score.build([rec(good, start=t - 300), rec(good, start=t - 299 + 299), rec(good, start=t + 5400 - 300),
                        rec(good, start=t + 5400)], offset=60)
    m, _, _ = score.rule(d, M=3)
    assert m.tolist() == [True, False, False, True]


def test_window_cluster_is_the_window_start():
    good = path([(0.6, 0.55), (0.9, 0.88), (0.95, 0.94), (0.97, 0.96), (0.99, 0.98)])
    d, _ = score.build([rec(good, coin="btc"), rec(good, coin="eth")], offset=60)
    assert d["open_ts"].tolist() == [T0, T0]
    assert d["coin"].tolist() == ["btc", "eth"]
