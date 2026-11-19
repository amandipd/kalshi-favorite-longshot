"""findings.py's halt replay: the live bot's halts at its own sizing ($100, 3% a bet, 20% a window, whole contracts).

The synthetic history never trips a halt, so each is tripped here on a short history built to trip it: a window with 8
losing favourites, a day that loses 20% in three windows, and a slow bleed of one losing bet a day, which reaches half
the start and then goes broke. Every bet is a 96c favourite, so each loss can be worked out by hand.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

T0 = 1_784_332_800  # 2026-07-18T00:00:00Z
HOUR, DAY = 3600, 86400
NARROW, WIDE = (0.95, 0.96), (0.93, 0.96)   # the favourite's own bid and ask at minute 8: a 1c and a 3c spread


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def lost(t, q8=NARROW):
    return {"t": t, "series": "KXBTC15M", "group": "crypto", "entry": 0.96, "won": False, "q": {8: q8}}


def loss(c):
    """What a losing bet of c contracts at 96c costs."""
    return c * 0.96 + fee(c, 0.96)


def replay(study, bets):
    return {r["rule"]: r for r in study.findings.halts(bets)}


TODAY, NONE, LOOSE = "Today's halts", "No halts", "24-hour rule loosened to 35%"
MONITOR = "Half the start, 8 losses, edge monitor"
SPREAD, SPREAD_MONITOR = "Spread filter and today's halts", "Spread filter, half the start, 8 losses, edge monitor"


def test_eight_losses_in_one_window_halt_every_rule_with_that_halt(study):
    rows = replay(study, [lost(T0 + HOUR) for _ in range(8)])
    # 8 bets share 20% of $100: $2.50 each, 2 whole contracts at 96c
    end = round(100 - 8 * loss(2), 2)
    for rule in (TODAY, LOOSE, MONITOR, SPREAD, SPREAD_MONITOR):
        assert rows[rule]["fromJul18"] == {"end": end, "stopped": "Jul 18", "why": "8+ losses in a window"}, rule
    assert rows[NONE]["fromJul18"] == {"end": end, "stopped": None, "why": None}
    assert all(r["fromAug24"] == {"end": 100.0, "stopped": None, "why": None} for r in rows.values()), \
        "a start on Aug 24 never sees a July window"


def test_seven_losses_in_a_window_are_not_a_halt(study):
    rows = replay(study, [lost(T0 + HOUR) for _ in range(7)])
    assert rows[TODAY]["fromJul18"]["why"] is None


def test_fed_decision_windows_are_left_out(study):
    fed = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc).timestamp()
    rows = replay(study, [lost(fed) for _ in range(8)] + [lost(fed + 4500) for _ in range(8)])
    assert rows[TODAY]["fromJul18"] == {"end": 100.0, "stopped": None, "why": None}, \
        "the bot places nothing in a window overlapping 2:00-3:30 pm ET on a Fed day"


def bad_day(start):
    """Three windows an hour apart, four losing bets each: $100 to $73 within a day."""
    return [lost(start + k * HOUR) for k in range(3) for _ in range(4)]


def test_a_20_percent_day_halts_today_but_not_at_35_percent(study):
    rows = replay(study, bad_day(T0))
    # $3 a bet buys 3 contracts; then $2.65 and $2.42 buy 2: 100 -> 88.44 -> 80.72 -> 73.00
    end = round(100 - 4 * loss(3) - 8 * loss(2), 2)
    assert end == 73.0
    assert rows[TODAY]["fromJul18"] == {"end": end, "stopped": "Jul 18", "why": "20% down in 24 hours"}
    assert rows[SPREAD]["fromJul18"]["why"] == "20% down in 24 hours"
    for rule in (LOOSE, NONE, MONITOR, SPREAD_MONITOR):
        assert rows[rule]["fromJul18"] == {"end": end, "stopped": None, "why": None}, rule


def test_the_24_hour_rule_looks_back_a_day_not_to_the_start(study):
    # the same losses, a day apart: 27% down in all, but never 20% within 24 hours
    rows = replay(study, [lost(T0 + k * DAY) for k in range(3) for _ in range(4)])
    assert rows[TODAY]["fromJul18"] == {"end": 73.0, "stopped": None, "why": None}


def test_a_35_percent_day_halts_the_loosened_rule(study):
    rows = replay(study, [lost(T0 + k * HOUR) for k in range(5) for _ in range(4)])
    assert rows[LOOSE]["fromJul18"]["why"] == "35% down in 24 hours"
    assert rows[LOOSE]["fromJul18"]["end"] <= 65.0 < rows[TODAY]["fromJul18"]["end"]
    assert rows[TODAY]["fromJul18"]["why"] == "20% down in 24 hours", "the 20% line is crossed first"


@pytest.fixture(scope="module")
def bleed(study):
    """One losing bet a day from Jul 18 to Oct 5, each with a 3c spread: too slow for the 24-hour rule."""
    return replay(study, [lost(T0 + 15 * HOUR + k * DAY, WIDE) for k in range(80)])


def stopped_on(row):
    return datetime.strptime(f"2026 {row['stopped']}", "%Y %b %d")


def test_a_slow_bleed_halts_at_half_the_start(bleed):
    for rule in (TODAY, LOOSE):
        r = bleed[rule]["fromJul18"]
        assert r["why"] == "half the start", rule
        assert 50 - loss(2) < r["end"] <= 50, "stopped on the first window at or under $50"


def test_the_edge_monitor_catches_the_bleed_before_half_the_start(bleed):
    # each losing bet adds about 0.96 to the monitor (its price, plus the fee a contract, less 0.3c allowed); 15 trips it
    r = bleed[MONITOR]["fromJul18"]
    assert (r["why"], r["stopped"]) == ("edge monitor", "Aug 02"), "the 16th losing day, Jul 18 being the first"
    assert r["end"] > 50 and stopped_on(r) < stopped_on(bleed[TODAY]["fromJul18"])


def test_with_no_halts_the_bleed_runs_until_a_bet_is_under_a_dollar(bleed):
    r = bleed[NONE]["fromJul18"]
    assert r["why"] == "broke"
    assert math.floor(r["end"] * 0.03 * 100) / 100 < 1 <= math.floor((r["end"] + loss(1)) * 0.03 * 100) / 100, \
        "broke on the first window whose 3% bet is under $1"
    assert stopped_on(r) > stopped_on(bleed[TODAY]["fromJul18"])


def test_the_spread_filter_skips_every_wide_bet(bleed):
    for rule in (SPREAD, SPREAD_MONITOR):
        assert bleed[rule]["fromJul18"] == {"end": 100.0, "stopped": None, "why": None}, rule


def test_a_bad_window_before_jul18_halts_only_the_dec10_start(study):
    jan = datetime(2026, 1, 12, 15, tzinfo=timezone.utc).timestamp()
    rows = replay(study, [lost(jan) for _ in range(8)])
    assert rows[TODAY]["fromDec10"] == {"end": round(100 - 8 * loss(2), 2), "stopped": "Jan 12", "why": "8+ losses in a window"}
    assert rows[TODAY]["fromJul18"] == rows[TODAY]["fromAug24"] == {"end": 100.0, "stopped": None, "why": None}


def test_the_earlier_fed_decisions_are_left_out_too(study):
    # Jan 28, 2026 was in Eastern winter time: 2:00 pm ET is 19:00 UTC
    fed = datetime(2026, 1, 28, 19, 0, tzinfo=timezone.utc).timestamp()
    rows = replay(study, [lost(fed) for _ in range(8)])
    assert rows[TODAY]["fromDec10"] == {"end": 100.0, "stopped": None, "why": None}
