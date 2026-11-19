"""Tests for the forward paper test: forward.py (the recorder), keep_running.py (its watchdog) and forward_report.py."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import forward as F  # noqa: E402
import forward_report as R  # noqa: E402
import keep_running as K  # noqa: E402

T0 = 1_794_000_000   # a window start (multiple of 300)
H = 3600


def pts(m1, m2, m3, m4):
    """History points stamped 0, 60, 120, 180 (the ends of minutes 1-4) from (yes_ask, yes_bid) pairs; None = missing."""
    out = []
    for k, q in enumerate((m1, m2, m3, m4)):
        if q is not None:
            out.append([k * 60, q[0], round(1 - q[1], 4)])
    return out


CLEAN_YES = pts((0.70, 0.66), (0.90, 0.88), (0.96, 0.95), (0.99, 0.98))


# ------------------------------------------------------------------ reading what a bot could see


def test_server_time_reads_the_date_header():
    assert F.server_time({"Date": "Fri, 13 Nov 2026 05:00:00 GMT"}) == pytest.approx(1794546000)
    assert F.server_time({"date": "Fri, 13 Nov 2026 05:00:00 GMT"}) == pytest.approx(1794546000)
    assert F.server_time({}) is None
    assert F.server_time({"Date": "not a date"}) is None


def test_visible_takes_the_latest_poll_at_or_before_3_58():
    polls = [{"sw": 226, "pts": [[0, 0.1, 0.9]]}, {"sw": 234, "pts": [[0, 0.2, 0.8]]},
             {"sw": 239, "pts": [[0, 0.3, 0.7]]}]
    assert F.visible(polls)["sw"] == 234
    assert F.visible([{"sw": 238, "pts": []}])["sw"] == 238


def test_visible_is_none_without_a_poll_in_time():
    assert F.visible([{"sw": 239, "pts": []}, {"sw": 400, "pts": []}]) is None
    assert F.visible([]) is None
    assert F.visible([{"sw": None, "pts": []}]) is None   # no Date header: can't prove it was in time


def test_decide_bets_a_clean_99c_favourite_at_minute_4():
    d = F.decide(CLEAN_YES)
    assert d == {"bet": True, "side": "yes", "top": pytest.approx(0.99), "why": "bet"}


def test_decide_bets_the_no_side_when_it_is_the_favourite():
    # Yes ask/bid -> No ask = 1 - Yes bid
    p = pts((0.30, 0.34 - 0.04), (0.12, 0.10), (0.06, 0.04), (0.02, 0.01))
    d = F.decide(p)
    assert d["bet"] and d["side"] == "no" and d["top"] == pytest.approx(0.99)


@pytest.mark.parametrize("p,why", [
    (pts((0.70, 0.66), (0.90, 0.88), (0.96, 0.95), (0.99, 0.97)), "spread 2c"),
    (pts((0.70, 0.66), (0.90, 0.88), (0.86, 0.85), (0.99, 0.98)), "up 12.5c in minute 4"),
    (pts((0.70, 0.66), (0.52, 0.48), (0.91, 0.90), (0.93, 0.92)), "coin flip at minute 2"),
    (pts((0.70, 0.66), (0.90, 0.88), (0.89, 0.88), (0.89, 0.88)), "under 90c"),
])
def test_decide_skips_the_warning_signs_and_the_floor(p, why):
    assert F.decide(p)["bet"] is False, why


def test_decide_without_a_minute_4_point_is_no_bet():
    d = F.decide(pts((0.70, 0.66), (0.90, 0.88), (0.96, 0.95), None))
    assert d == {"bet": False, "side": None, "top": None, "why": "no minute-4 price"}


def test_decide_with_no_points_is_no_bet():
    assert F.decide([])["bet"] is False


# ------------------------------------------------------------------ when to stop


def test_stop_needs_72_hours_and_1000_bets():
    assert not F.should_stop(T0 + 71 * H, T0, 5000)
    assert not F.should_stop(T0 + 73 * H, T0, 999)
    assert F.should_stop(T0 + 72 * H, T0, 1000)


def test_stop_at_7_days_whatever_the_count():
    assert not F.should_stop(T0 + 7 * 24 * H - 1, T0, 10)
    assert F.should_stop(T0 + 7 * 24 * H, T0, 10)


def test_poll_schedule_is_in_server_time():
    # the laptop clock runs 2 s behind the server (skew = server - local = +2): poll 2 s earlier by the laptop clock
    sched = F.schedule(T0, skew=2.0)
    assert sched == [("poll", T0 + 226 - 2.0), ("book", T0 + 230 - 2.0), ("poll", T0 + 234 - 2.0)]


def test_skew_estimate_uses_the_middle_of_each_request_and_half_a_second():
    # the Date header floors to the second, so +0.5 is its expected value
    samples = [(100.0, 100.2, 101.0), (200.0, 200.4, 201.0)]   # (sent, received, server date)
    assert F.skew(samples) == pytest.approx(((101.5 - 100.1) + (201.5 - 200.2)) / 2)
    assert F.skew([]) == 0.0


# ------------------------------------------------------------------ the watchdog


def test_watchdog_starts_only_when_needed():
    assert K.decide(T0, is_running=False, done=False) == "start"
    assert K.decide(T0, is_running=True, done=False) == "running"
    assert K.decide(T0, is_running=False, done=True) == "over"
    assert K.decide(K.HARD_END, is_running=False, done=False) == "over"


# ------------------------------------------------------------------ the report


@pytest.mark.parametrize("s,v", [
    ({"bets": 1200, "c_per_1": 0.8, "lo": 0.1, "hi": 1.5}, "PASS"),
    ({"bets": 1200, "c_per_1": 0.8, "lo": -0.1, "hi": 1.5}, "UNCLEAR"),
    ({"bets": 1200, "c_per_1": 0.4, "lo": 0.1, "hi": 0.7}, "UNCLEAR"),
    ({"bets": 1200, "c_per_1": 0.0, "lo": -0.5, "hi": 0.5}, "FAIL"),
    ({"bets": 1200, "c_per_1": 0.3, "lo": 0.1, "hi": 0.45}, "FAIL"),
    ({"bets": 0, "c_per_1": None, "lo": None, "hi": None}, "UNCLEAR"),
])
def test_forward_verdict(s, v):
    assert R.verdict(s) == v
