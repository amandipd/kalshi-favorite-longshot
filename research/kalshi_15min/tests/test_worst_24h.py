"""strategies_backtest.run()'s worst 24 hours: the deepest fall from a high within any 24 hours.

The Research tab's Strategies view shows it beside the deepest fall over the whole history, because it's what the
live bot's halt watches: bot.check_halts stops trading once the account is down 35% or more from its high within the
last 24 hours. Every run carries three fields:

    worst24hPct   the fall as a share of the high it fell from (0.0 or less)
    worst24h      the same fall in dollars, to the cent (0.0 or less)
    worst24hAt    when it bottomed: the close of that window, as an ISO time (None if it never fell)

A window's bets all settle at its close, so the bankroll moves once a window: the high counts every bankroll held in
the 24 hours up to that close, including the one held when those 24 hours began. The fields are checked on hand-built
windows whose bankroll can be worked out by hand, then against a brute force over every pair of moments on random
histories, then on main()'s strategies.json.

    python -m pytest research/kalshi_15min/tests/test_worst_24h.py -q
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone

import pytest

EDGE = ["crypto", "metals", "energy"]
T0 = 1_784_332_800  # 2026-07-18T00:00:00Z, a Saturday
DAY = 86400
C = 10 / 0.96       # contracts a $10 bet buys at a 96c ask


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


WIN, LOSS = C - 10 - fee(C, 0.96), -10 - fee(C, 0.96)   # one $10 bet at 96c, won or lost


def market(yes=True):
    """A crypto market quoted 94-96c on Yes all window, settling Yes or No."""
    return {"series": "KXBTC15M", "group": "crypto", "yes": yes, "q": {k: (0.94, 0.96) for k in range(1, 16)}}


def flat(**extra):
    return {"id": "t", "name": "test", "minute": 8, "sizing": "flat", "groups": EDGE, **extra}


def run(study, windows, strat=None, t0=T0):
    hours = int((max(windows, default=t0) + 900 - t0) // 3600) + 1
    return study.strategies_backtest.run(strat or flat(), windows, 0.0, t0, hours)


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


# ------------------------------------------------------------------ by hand


def test_no_windows_never_fell(study):
    r = run(study, {})
    assert (r["worst24hPct"], r["worst24h"], r["worst24hAt"]) == (0.0, 0.0, None)


def test_only_wins_never_fell(study):
    r = run(study, {T0: [market()], T0 + 900: [market(), market()]})
    assert (r["worst24hPct"], r["worst24h"], r["worst24hAt"]) == (0.0, 0.0, None)


def test_one_lost_window(study):
    r = run(study, {T0: [market(yes=False)]})
    assert r["worst24hPct"] == pytest.approx((240 + LOSS) / 240 - 1)
    assert r["worst24h"] == round(LOSS, 2)
    assert r["worst24hAt"] == iso(T0 + 900)                         # it bottoms when the window closes


def test_losses_within_24_hours_add_up(study):
    # two lost windows 23 hours apart: one fall from $240 to $240 + 2 losses
    r = run(study, {T0: [market(yes=False)], T0 + 23 * 3600: [market(yes=False)]})
    assert r["worst24hPct"] == pytest.approx((240 + 2 * LOSS) / 240 - 1)
    assert r["worst24h"] == round(2 * LOSS, 2) and r["worst24hAt"] == iso(T0 + 23 * 3600 + 900)


def test_losses_more_than_24_hours_apart_dont(study):
    # 25 hours apart: the first loss's high has left the 24 hours by the second, so each falls on its own, and the
    # second, from a lower high, is the deeper share
    r = run(study, {T0: [market(yes=False)], T0 + 25 * 3600: [market(yes=False)]})
    after_one = 240 + LOSS
    assert r["worst24hPct"] == pytest.approx((after_one + LOSS) / after_one - 1)
    assert r["worst24h"] == round(LOSS, 2) and r["worst24hAt"] == iso(T0 + 25 * 3600 + 900)


def test_the_fall_is_from_the_high_not_from_where_the_24_hours_began(study):
    # it wins three windows, then loses two, all within a few hours: the fall runs from the high after the wins
    w = {T0 + k * 900: [market()] for k in range(3)}
    w.update({T0 + 3 * 900: [market(yes=False)], T0 + 4 * 900: [market(yes=False)]})
    r = run(study, w)
    high = 240 + 3 * WIN
    assert r["worst24hPct"] == pytest.approx((high + 2 * LOSS) / high - 1)
    assert r["worst24h"] == round(2 * LOSS, 2) and r["worst24hAt"] == iso(T0 + 4 * 900 + 900)


def test_a_high_older_than_24_hours_doesnt_count(study):
    # a high, then a slow fall: a loss every 10 hours. Any 24 hours hold at most three of the losses, so the deepest
    # fall is three losses from the bankroll before them, never all five from the old high.
    w = {T0: [market(), market(), market()]}
    w.update({T0 + 3600 + k * 10 * 3600: [market(yes=False)] for k in range(5)})
    r = run(study, w)
    falls = []
    for k in range(3):   # three losses in a row, starting at the k-th
        high = 240 + 3 * WIN + k * LOSS
        falls.append((high + 3 * LOSS) / high - 1)
    assert r["worst24hPct"] == pytest.approx(min(falls))
    assert r["worst24hPct"] > (240 + 3 * WIN + 5 * LOSS) / (240 + 3 * WIN) - 1   # not the five-loss fall
    assert r["worst24h"] == round(3 * LOSS, 2)


def test_a_tie_keeps_the_earliest(study):
    # a lost window, then two windows with no favourite: the bankroll sits at the same low for three closes, so
    # the fall is the same at each, and the first is the one it reports
    r = run(study, {T0: [market(yes=False)], T0 + 900: [], T0 + 1800: []})
    assert r["worst24hPct"] == pytest.approx((240 + LOSS) / 240 - 1) and r["worst24hAt"] == iso(T0 + 900)


def test_skipped_windows_change_nothing(study):
    # a Fed-decision blackout window places nothing, so its loss never happens
    w = {T0: [market()], T0 + 900: [market(yes=False)], T0 + 1800: [market()]}
    blackout = flat(blackouts=[(T0 + 900, T0 + 1800)])
    r = run(study, w, blackout)
    assert r["bets"] == 2 and (r["worst24hPct"], r["worst24h"], r["worst24hAt"]) == (0.0, 0.0, None)


def test_a_broke_account_falls_all_the_way(study):
    # $12 can afford one $10 bet: it loses, and the next window it can't bet, so it's broke
    r = run(study, {T0: [market(yes=False)], T0 + 900: [market()]}, flat(start=12.0))
    assert r["broke"] == iso(T0 + 900)
    assert r["worst24hPct"] == pytest.approx((12 + LOSS) / 12 - 1)
    assert r["worst24h"] == round(LOSS, 2) and r["worst24hAt"] == iso(T0 + 900)


def test_it_is_the_measure_the_live_bot_halts_on(study):
    from kalshi_bot import bot
    # three losing windows within the day, at the live bot's own sizing: 3% a bet, from $100 in whole contracts
    live = {"id": "t", "name": "t", "minute": 8, "sizing": "capped", "groups": EDGE, "start": 100.0, "whole": True}
    w = {T0 + k * 3600: [market(yes=False)] * 4 for k in range(6)}
    r = run(study, w, live)
    assert r["worst24hPct"] == pytest.approx(r["final"] / 100 - 1)   # every bet lost: the high is the start
    assert (r["worst24hPct"] <= -bot.HALT_DAY_DROP) == (r["final"] <= 100 * (1 - bot.HALT_DAY_DROP))


# ------------------------------------------------------------------ against a brute force


def brute(windows, start):
    """Flat $10 bets at 96c, every market of every window: the deepest fall from a high within 24 hours, checked over
    every pair of moments. Returns (share, dollars, the close it bottomed at) or (0.0, 0.0, None)."""
    held = []   # (close, bankroll before the window, bankroll after)
    bal = start
    for t in sorted(windows):
        before = bal
        bal += sum(WIN if m["yes"] else LOSS for m in windows[t])
        held.append((t + 900, before, bal))
    best = (0.0, 0.0, None)
    for j, (cj, _, aj) in enumerate(held):
        high = max(b for ck, b, _ in held[:j + 1] if ck > cj - DAY)
        fall = aj / high - 1
        if fall < best[0] - 1e-12:
            best = (fall, round(aj - high, 2), cj)
    return best


@pytest.mark.parametrize("seed", range(12))
def test_matches_a_brute_force_on_random_histories(study, seed):
    rng = random.Random(seed)
    w, t = {}, T0
    for _ in range(rng.randint(5, 220)):
        t += 900 * rng.choice([1, 1, 1, 2, 4, 40, 96, 97, 100])   # windows close together, and gaps around a day
        w[t] = [market(yes=rng.random() < 0.8) for _ in range(rng.randint(0, 4))]
    r = run(study, w, flat(start=5000.0))
    share, dollars, at = brute(w, 5000.0)
    assert r["worst24hPct"] == pytest.approx(share, abs=1e-12)
    assert r["worst24h"] == pytest.approx(dollars, abs=0.011)
    assert r["worst24hAt"] == (iso(at) if at is not None else None)


# ------------------------------------------------------------------ main()


@pytest.fixture(scope="module")
def strategies(study):
    study.strategies_backtest.main()
    with open("strategies.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_every_run_in_strategies_json_carries_it(strategies):
    runs = [r for start in strategies["starts"].values() for rows in start.values() for r in rows.values()]
    assert runs
    for r in runs:
        assert r["worst24hPct"] <= 0 and r["worst24h"] <= 0
        assert (r["worst24hAt"] is None) == (r["worst24hPct"] == 0)
        assert r["worst24hPct"] >= -1.0 and r["maxDD"] >= -r["worst24hPct"] - 1e-9   # never deeper than the deepest fall
    assert any(r["worst24hPct"] < 0 for r in runs)
