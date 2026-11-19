"""fair_value.py's pure pieces: the settlement-aware horizon, the model probability, volatility without look-ahead, spot
alignment to the decision minute, the two trading filters, the logistic fit and threshold picking on the train half."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fair_value as F  # noqa: E402


def test_tau_counts_minutes_to_the_closing_average():
    # at the end of minute 8 the closing 60-second average runs over minute 15: 6 minutes away, then 1/3 of a minute
    # of variance for averaging over it
    assert F.tau_eff(8) == pytest.approx(6 + 1 / 3)
    assert F.tau_eff(12) == pytest.approx(2 + 1 / 3)


def test_p_yes_is_a_normal_cdf_of_the_scaled_move():
    sig, m = 1e-3, 8
    assert F.p_yes(np.array([0.0]), np.array([sig]), m)[0] == pytest.approx(0.5)
    x = sig * math.sqrt(F.tau_eff(m))
    assert F.p_yes(np.array([x]), np.array([sig]), m)[0] == pytest.approx(0.841345, abs=1e-5)
    assert F.p_yes(np.array([-x]), np.array([sig]), m)[0] == pytest.approx(1 - 0.841345, abs=1e-5)
    # a wider scale pulls toward a coin flip
    assert F.p_yes(np.array([x]), np.array([sig]), m, k=2.0)[0] < 0.8413


def test_realized_sigma_uses_only_returns_up_to_the_index():
    rng = np.random.default_rng(0)
    logc = np.cumsum(rng.normal(0, 1e-3, 500))
    s = F.realized_sigma(logc, 60)
    r = np.diff(logc)
    i = 300                                   # returns into minutes 241..300 inclusive
    assert s[i] == pytest.approx(math.sqrt(np.mean(r[i - 60:i] ** 2)))
    assert np.isnan(s[30])                    # not enough history yet
    logc2 = logc.copy()
    logc2[i + 1:] += 5.0                      # a jump after i changes nothing at i
    assert F.realized_sigma(logc2, 60)[i] == pytest.approx(s[i])


def test_ewma_sigma_settles_on_a_constant_move():
    logc = np.arange(2000) * 2e-4
    assert F.ewma_sigma(logc, 30)[-1] == pytest.approx(2e-4, rel=1e-6)


def test_spot_features_line_up_with_the_decision_minute():
    t0 = 1_000_000 - 1_000_000 % 60
    n = 5000
    grid = {"t0": t0, "close": np.arange(n, dtype=float) + 1000.0, "avg": np.arange(n, dtype=float) + 0.5 + 1000.0}
    opens = np.array([t0 + 60 * 100, t0 + 60 * 400])
    f = F.spot_features(grid, opens, 8)
    # S: the candle that closes at open + 8 min starts at open + 7 min
    assert list(f["S"]) == [1107.0, 1407.0]
    # K: the minute before the open; F: minute 15 (starts at open + 14 min)
    assert list(f["K"]) == [1099.5, 1399.5]
    assert list(f["F"]) == [1114.5, 1414.5]
    assert list(F.spot_features(grid, opens, 8, lag=1)["S"]) == [1106.0, 1406.0]
    off = F.spot_features(grid, np.array([t0 - 60 * 50, t0 + 60 * (n + 5)]), 8)
    assert np.isnan(off["S"]).all()


def test_fav_filter_skips_when_the_model_is_below_the_ask_plus_margin():
    p_fav = np.array([0.95, 0.90, 0.80])
    top = np.array([0.93, 0.93, 0.93])
    assert list(F.fav_keep(p_fav, top, 0.0)) == [True, False, False]
    assert list(F.fav_keep(p_fav, top, -0.05)) == [True, True, False]
    assert list(F.fav_keep(np.array([np.nan]), np.array([0.93]), 0.0)) == [True]   # no model: the live rule stands


def test_model_pick_buys_the_side_the_model_says_is_cheap():
    p = np.array([0.70, 0.30, 0.52, 0.90])
    ask = np.array([0.60, 0.40, 0.50, np.nan])
    bid = np.array([0.58, 0.38, 0.49, np.nan])  # NO's ask = 1 - bid
    m, side_yes, price, edge = F.model_pick(p, ask, bid, 0.05)
    assert list(m) == [True, True, False, False]
    assert list(side_yes[:2]) == [True, False]   # YES worth 0.70 at 0.60; NO worth 0.70 at 0.62
    assert price[0] == pytest.approx(0.60) and price[1] == pytest.approx(0.62)
    assert edge[0] == pytest.approx(0.10) and edge[1] == pytest.approx(0.08)


def test_logit_fit_recovers_coefficients():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(20000, 2))
    beta = np.array([0.3, 1.5, -0.8])
    y = rng.random(20000) < 1 / (1 + np.exp(-(beta[0] + X @ beta[1:])))
    assert F.logit_fit(X, y) == pytest.approx(beta, abs=0.08)


def test_pick_uses_the_train_values_only():
    train = {"none": 10.0, 0.0: 25.0, -0.05: 18.0}
    assert F.pick(train) == 0.0
    assert F.pick({"none": 30.0, 0.0: 25.0}) == "none"


def test_p_yes_with_fat_tails():
    sig, m = 1e-3, 8
    x = np.array([3 * sig * math.sqrt(F.tau_eff(m))])   # a 3-sigma move
    normal = F.p_yes(x, np.array([sig]), m)[0]
    t3 = F.p_yes(x, np.array([sig]), m, nu=3)[0]
    assert t3 < normal                                   # fatter tails: a big lead is less sure
    assert F.p_yes(np.array([0.0]), np.array([sig]), m, nu=3)[0] == pytest.approx(0.5)
    assert F.p_yes(x, np.array([sig]), m, nu=None)[0] == pytest.approx(normal)
