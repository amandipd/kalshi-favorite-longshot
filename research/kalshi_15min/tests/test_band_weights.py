"""Band-weighted sizing: betting more at some prices than others, inside the same caps.

The measured edge falls as the favourite gets dearer (+0.82, +0.48, +0.27, +0.20 cents per $1 from
92c to 99c), but so does the loss rate (5.45% down to 0.73%), so the risk-adjusted answer is not
obvious. These tests pin the mechanism only -- that a weighting redistributes a window's budget
without breaking either cap -- so the replay can compare weightings on the real history.
"""

from __future__ import annotations

import pytest

EDGE = ["crypto", "metals", "energy"]
T0 = 1_784_332_800  # 2026-07-18T00:00:00Z


def market(yes=True, q8=(0.94, 0.96), series="KXBTC15M", group="crypto"):
    return {"ticker": f"{series}-{q8}-{yes}", "series": series, "group": group, "yes": yes,
            "q": {k: q8 for k in range(1, 16)}}


# ---------------------------------------------------------------- the weight lookup


def test_the_band_of_a_quote(study):
    sb = study.strategies_backtest
    assert sb.band_of(0.92) == 92 and sb.band_of(0.9399) == 92
    assert sb.band_of(0.94) == 94 and sb.band_of(0.96) == 96
    assert sb.band_of(0.98) == 98 and sb.band_of(0.999) == 98


def test_no_weights_means_every_bet_keeps_the_flat_stake(study):
    """An account with no bandWeights must size exactly as it does today."""
    sb = study.strategies_backtest
    quotes = [0.92, 0.95, 0.97, 0.99]
    assert sb.band_stakes({"sizing": "capped"}, 5.0, len(quotes), 1000.0, quotes) == [5.0] * 4


def test_weights_redistribute_the_window_budget(study):
    """Twice the weight, twice the bet -- and the window's total is unchanged."""
    sb = study.strategies_backtest
    strat = {"sizing": "capped", "bandWeights": {92: 2.0, 98: 1.0}}
    out = sb.band_stakes(strat, 10.0, 2, 1e6, [0.92, 0.99])
    assert sum(out) == pytest.approx(20.0, abs=0.02)      # 2 bets x $10 budget
    assert out[0] == pytest.approx(2 * out[1], abs=0.02)  # twice the weight


def test_a_zero_weight_skips_that_band(study):
    sb = study.strategies_backtest
    strat = {"sizing": "capped", "bandWeights": {92: 1.0, 98: 0.0}}
    out = sb.band_stakes(strat, 10.0, 2, 1e6, [0.92, 0.99])
    assert out[1] == 0.0
    assert out[0] == pytest.approx(20.0, abs=0.02), "the whole budget goes to the band that is kept"


def test_the_per_bet_cap_still_binds(study):
    """No bet may exceed CAP_PCT of the bankroll, however heavy its weight."""
    sb = study.strategies_backtest
    strat = {"sizing": "capped", "bandWeights": {92: 50.0, 98: 1.0}}
    bal = 1000.0
    out = sb.band_stakes(strat, 10.0, 2, bal, [0.92, 0.99])
    assert out[0] <= bal * sb.CAP_PCT + 1e-9
    assert out[0] == pytest.approx(bal * sb.CAP_PCT, abs=0.02)


def test_the_window_cap_still_binds(study):
    sb = study.strategies_backtest
    strat = {"sizing": "capped", "bandWeights": {92: 3.0, 98: 1.0}}
    bal = 1000.0
    quotes = [0.92] * 10 + [0.99] * 10
    out = sb.band_stakes(strat, sb.stake_for(strat, bal, len(quotes)), len(quotes), bal, quotes)
    assert sum(out) <= bal * sb.WINDOW_CAP + 0.02

def test_every_stake_is_floored_to_the_cent(study):
    sb = study.strategies_backtest
    strat = {"sizing": "capped", "bandWeights": {92: 1.0, 94: 1.7320508}}
    out = sb.band_stakes(strat, 7.0, 2, 1e6, [0.92, 0.95])
    assert all(round(x * 100) == pytest.approx(x * 100, abs=1e-6) for x in out), out


# ---------------------------------------------------------------- end to end through run()


def wide_window(n=10):
    """A window with n cheap and n dear markets, enough bets that the window cap binds, not the per-bet one."""
    out = []
    for i in range(n):
        out.append(market(yes=True, q8=(0.92, 0.925), series=f"KXC{i}15M"))
        out.append(market(yes=True, q8=(0.985, 0.99), series=f"KXD{i}15M"))
    return out


def test_a_weighted_account_bets_more_in_the_favoured_band(study):
    """With the window cap binding, a 3:1 weighting really does stake 3:1 between the bands."""
    sb = study.strategies_backtest
    strat = {"id": "bw", "minute": 8, "sizing": "capped", "groups": EDGE, "start": 10_000.0,
             "bandWeights": {92: 3.0, 98: 1.0}}
    r = sb.run(strat, {T0: wide_window()}, 0.0, T0, 2)
    assert r["bets"] == 20
    cheap = next(g for g in r["byBand"] if g["key"].startswith("92"))
    dear = next(g for g in r["byBand"] if g["key"].startswith("98"))
    assert cheap["staked"] == pytest.approx(dear["staked"] * 3, rel=0.02), (cheap["staked"], dear["staked"])


def test_with_few_bets_a_weighting_can_only_shrink_stakes(study):
    """The behaviour that decides whether this is worth doing at all.

    Under about 7 bets a window the PER-BET cap binds, not the window cap, so every bet is already at
    CAP_PCT. A weight above 1 cannot lift a bet past that cap, so a weighting there only ever takes money
    off the lighter bands -- it never adds to the heavier one. The live bot averages about 3 bets a window,
    so this is the case that matters."""
    sb = study.strategies_backtest
    bal = 10_000.0
    quotes = [0.92, 0.99]
    flat = sb.band_stakes({"sizing": "capped"}, sb.stake_for({"sizing": "capped"}, bal, 2), 2, bal, quotes)
    strat = {"sizing": "capped", "bandWeights": {92: 3.0, 98: 1.0}}
    tilted = sb.band_stakes(strat, sb.stake_for(strat, bal, 2), 2, bal, quotes)
    assert flat == [bal * sb.CAP_PCT] * 2, "both bets already sit at the per-bet cap"
    assert tilted[0] == pytest.approx(bal * sb.CAP_PCT), "the favoured band cannot go above the cap"
    assert tilted[1] < flat[1], "so the tilt only takes money off the other band"
    assert sum(tilted) < sum(flat), "and the window stakes less overall"


def test_weighting_changes_no_bet_count(study):
    """Weights move money between bets; they never add or remove one."""
    sb = study.strategies_backtest
    base = {"id": "b", "minute": 8, "sizing": "capped", "groups": EDGE, "start": 10_000.0}
    windows = {T0: [market(yes=True, q8=(0.92, 0.925), series="KXBTC15M"),
                    market(yes=True, q8=(0.985, 0.99), series="KXETH15M")]}
    flat = sb.run(dict(base), windows, 0.0, T0, 2)
    weighted = sb.run({**base, "bandWeights": {92: 3.0, 98: 1.0}}, windows, 0.0, T0, 2)
    assert flat["bets"] == weighted["bets"] == 2
