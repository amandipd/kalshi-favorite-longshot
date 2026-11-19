"""The two warning signs' thresholds, made configurable so THRESHOLD_SEARCH_PREREG.md can score them.

Three numbers were hardcoded in `skipped()`: a 2c spread cut, a 10c jump cut and a 50c coin-flip cut. Each
was chosen once in October and never scored against an alternative. These tests pin two things: that leaving
the new keys off reproduces today's behaviour exactly, and that each key moves the one decision it should and
no other.

The first of those matters most. If the defaults drifted, every number in strategies.json would shift and the
live bot's own replay would stop describing the live bot.
"""

from __future__ import annotations

import pytest

EDGE = ["crypto", "metals", "energy"]
BOTH = ("spread", "late")


def mkt(quotes, yes=True):
    """A market quoted {minute: (yes bid, yes ask)}."""
    return {"ticker": "T", "series": "KXBTC15M", "group": "crypto", "yes": yes, "q": dict(quotes)}


def steady(bid, ask):
    """A favourite that has sat still all window: no jump, never a coin flip."""
    return {k: (bid, ask) for k in range(1, 16)}


# ------------------------------------------------------------------ the defaults must not move


def test_leaving_the_keys_off_reproduces_todays_spread_cut(study):
    """2c or wider is skipped, 1.9c is not. This is the current live behaviour."""
    sb = study.strategies_backtest
    base = {"minute": 8, "skip": BOTH}
    assert sb.skipped(base, mkt(steady(0.93, 0.95)), "yes") is True, "a 2c spread is skipped"
    assert sb.skipped(base, mkt(steady(0.931, 0.95)), "yes") is False, "1.9c is kept"


def test_leaving_the_keys_off_reproduces_todays_jump_cut(study):
    """Either side of the 10c cut, kept clear of it.

    Exactly 10c is deliberately not asserted. Mids are built from float cents, so a "10c" rise can land on
    0.09999999999999998 and fall the other side of a bare >= comparison -- test_strategies_backtest.py carries
    an xfail for that boundary and test_fuzz_research.py assumes it away. Adding an epsilon to make the
    boundary firm is exactly what broke the lab cross-checks, so the comparison stays bare and the test stays
    off the edge."""
    sb = study.strategies_backtest
    base = {"minute": 8, "skip": BOTH}
    up12 = {**steady(0.94, 0.95), 7: (0.82, 0.83)}      # mid rose about 12c into minute 8
    up8 = {**steady(0.94, 0.95), 7: (0.86, 0.87)}       # ... and only about 8c
    assert sb.skipped(base, mkt(up12), "yes") is True
    assert sb.skipped(base, mkt(up8), "yes") is False


def test_leaving_the_keys_off_reproduces_todays_coin_flip_cut(study):
    sb = study.strategies_backtest
    base = {"minute": 8, "skip": BOTH}
    at50 = {**steady(0.94, 0.95), 6: (0.49, 0.51)}      # mid exactly 50c at minute 6
    at52 = {**steady(0.94, 0.95), 6: (0.51, 0.53)}
    assert sb.skipped(base, mkt(at50), "yes") is True
    assert sb.skipped(base, mkt(at52), "yes") is False


# ------------------------------------------------------------------ each key moves its own decision


@pytest.mark.parametrize("cut, spread, skipped", [
    (0.01, 0.015, True), (0.01, 0.005, False),
    (0.04, 0.03, False), (0.04, 0.045, True),
])
def test_the_spread_cut_is_configurable(study, cut, spread, skipped):
    sb = study.strategies_backtest
    ask = 0.95
    m = mkt(steady(round(ask - spread, 4), ask))
    assert sb.skipped({"minute": 8, "skip": BOTH, "spreadCut": cut}, m, "yes") is skipped


@pytest.mark.parametrize("cut, jump, skipped", [
    (0.05, 0.06, True), (0.05, 0.04, False),
    (0.20, 0.15, False), (0.20, 0.25, True),
])
def test_the_jump_cut_is_configurable(study, cut, jump, skipped):
    sb = study.strategies_backtest
    before = round(0.945 - jump, 4)
    m = mkt({**steady(0.94, 0.95), 7: (round(before - 0.005, 4), round(before + 0.005, 4))})
    assert sb.skipped({"minute": 8, "skip": BOTH, "jumpCut": cut}, m, "yes") is skipped


@pytest.mark.parametrize("cut, mid6, skipped", [
    (0.40, 0.39, True), (0.40, 0.45, False),
    (0.60, 0.55, True), (0.60, 0.65, False),
])
def test_the_coin_flip_cut_is_configurable(study, cut, mid6, skipped):
    sb = study.strategies_backtest
    m = mkt({**steady(0.94, 0.95), 6: (round(mid6 - 0.01, 4), round(mid6 + 0.01, 4))})
    assert sb.skipped({"minute": 8, "skip": BOTH, "flipCut": cut}, m, "yes") is skipped


# ------------------------------------------------------------------ switching one part off


def test_a_cut_set_to_none_turns_that_part_off(study):
    """Needed for the "off" arm of each grid in the pre-registration."""
    sb = study.strategies_backtest
    wide = mkt(steady(0.90, 0.95))                                  # a 5c spread
    assert sb.skipped({"minute": 8, "skip": BOTH}, wide, "yes") is True
    assert sb.skipped({"minute": 8, "skip": BOTH, "spreadCut": None}, wide, "yes") is False

    jumped = mkt({**steady(0.94, 0.95), 7: (0.60, 0.62)})           # a 33c jump, and a coin flip before it
    assert sb.skipped({"minute": 8, "skip": BOTH}, jumped, "yes") is True
    assert sb.skipped({"minute": 8, "skip": BOTH, "jumpCut": None, "flipCut": None}, jumped, "yes") is False


def test_turning_the_jump_off_leaves_the_coin_flip_working(study):
    """The two halves of the "late" sign are separate numbers and must stay separable."""
    sb = study.strategies_backtest
    flip = mkt({**steady(0.94, 0.95), 6: (0.44, 0.46)})
    assert sb.skipped({"minute": 8, "skip": BOTH, "jumpCut": None}, flip, "yes") is True
    assert sb.skipped({"minute": 8, "skip": BOTH, "flipCut": None}, flip, "yes") is False


def test_the_cuts_do_nothing_when_their_sign_is_not_being_skipped(study):
    """An account that does not skip on spread must ignore spreadCut entirely."""
    sb = study.strategies_backtest
    wide = mkt(steady(0.90, 0.95))
    assert sb.skipped({"minute": 8, "skip": ("late",), "spreadCut": 0.001}, wide, "yes") is False
