"""The plan's pass test in other_markets.py (PLAN_OTHER_MARKETS.md, "What counts as a pass").

Rules are chosen on the first half of the history (closes before SPLIT, Sep 1) and tested once on the second, so the
main promise here is that the second half can't leak into the choice. The new functions take bet tuples, so most rows
are built by hand: (category, frequency, series, checkpoint, close ts, pnl on $10, liquid).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

UTC = timezone.utc
CHOOSE_FROM = datetime(2026, 7, 19, tzinfo=UTC)     # where the hand-built choosing half starts
TEST_FROM = datetime(2026, 9, 1, tzinfo=UTC)        # SPLIT: a close at or after it is in the test half
WINS = [0.5] * 19 + [-1.0]                          # +42.5c a bet, with a range well above zero

A = ("Crypto", "hourly", "10min")
B = ("Climate", "daily", "3h")
C = ("Financials", "hourly", "5min")


def ts(when) -> float:
    """A close time the way other_markets keeps it, a UTC timestamp, from an ISO string or a datetime."""
    if isinstance(when, str):
        when = datetime.fromisoformat(when.replace("Z", "+00:00"))
    return when.timestamp()


def bet(close, pnl, key=A, series="KXBTCD", liquid=True):
    cat, freq, checkpoint = key
    return (cat, freq, series, checkpoint, ts(close), pnl, liquid)


def run(n, key=A, start=CHOOSE_FROM, hours=3, pnls=WINS, series="KXBTCD", liquid=True):
    """n bets closing `hours` apart from `start`, their profits cycling through `pnls`."""
    return [bet(start + timedelta(hours=hours * i), pnls[i % len(pnls)], key, series, liquid) for i in range(n)]


def good(**changes):
    """stats() of a half that meets every condition, with `changes` applied."""
    s = {"bets": 1500, "mu": 0.05, "lo": 0.01, "hi": 0.09, "series": 6, "days": 25, "worst": 0.10}
    s.update(changes)
    return s


# ------------------------------------------------------------------ the plan's numbers


def test_the_plans_thresholds(study):
    om = study.other_markets
    assert (om.BANK, om.EDGE, om.MIN_TEST, om.MIN_SERIES, om.MIN_DAYS, om.WORST, om.MIN_CHOOSE) == (
        240, 0.02, 1000, 5, 20, 0.30, 200)
    assert str(om.ET) == "America/New_York"
    assert om.SPLIT == ts(TEST_FROM)


# ------------------------------------------------------------------ clustered


def test_clustered_counts_bets_that_close_together_as_one(study):
    om = study.other_markets
    rows = [bet("2026-08-01T10:00Z", 1.0), bet("2026-08-01T10:00Z", 1.0, series="KXETHD"),
            bet("2026-08-01T11:00Z", -1.0), bet("2026-08-01T12:00Z", 0.0)]
    mu, se = om.clustered(rows)
    # the mean is 0.25; the three close times' deviations are 0.75 + 0.75, -1.25 and -0.25
    assert mu == pytest.approx(0.25)
    assert se == pytest.approx(math.sqrt((1.5 ** 2 + 1.25 ** 2 + 0.25 ** 2) * 3 / 2) / 4)
    apart = rows[:1] + [bet("2026-08-01T10:30Z", 1.0, series="KXETHD")] + rows[2:]
    assert om.clustered(apart)[1] < se           # the same bets at different times: their errors no longer add up


def test_clustered_has_no_range_with_one_close_time(study):
    mu, se = study.other_markets.clustered([bet("2026-08-01T10:00Z", 0.4), bet("2026-08-01T10:00Z", -0.2, series="KXETHD")])
    assert mu == pytest.approx(0.1) and math.isnan(se)


def test_summary_reports_what_clustered_gives(study):
    om = study.other_markets
    rows = om.bets()
    assert om.summary(rows)[:2] == tuple(om.clustered(rows))
    one = [bet("2026-08-01T10:00Z", 0.4)]
    mu, se, _ = om.summary(one)
    assert mu == om.clustered(one)[0] and math.isnan(se)


# ------------------------------------------------------------------ stats


def test_stats_of_no_bets_is_none(study):
    assert study.other_markets.stats([]) is None


def test_stats_counts_bets_series_and_eastern_days(study):
    om = study.other_markets
    rows = [bet("2026-09-01T12:00Z", 0.5),                       # Sep 1 in New York
            bet("2026-09-02T03:30Z", 0.5, series="KXETHD"),      # 11:30 pm Sep 1 (EDT, UTC-4), though Sep 2 in UTC
            bet("2026-09-02T04:30Z", -1.0, series="KXETHD"),     # 12:30 am Sep 2
            bet("2026-12-01T15:00Z", 0.3, series="KXSOLD"),      # Dec 1
            bet("2026-12-02T04:30Z", 0.2, series="KXSOLD")]      # 11:30 pm Dec 1: winter time is UTC-5
    s = om.stats(rows)
    mu, se = om.clustered(rows)
    assert s["bets"] == 5 and s["series"] == 3 and s["days"] == 3
    assert s["mu"] == pytest.approx(0.1) == pytest.approx(mu)
    assert s["lo"] == pytest.approx(mu - 1.96 * se) and s["hi"] == pytest.approx(mu + 1.96 * se)


def test_worst_day_adds_up_each_eastern_day_as_a_share_of_240(study):
    om = study.other_markets
    rows = [bet("2026-09-01T15:00Z", -10.0), bet("2026-09-01T16:00Z", -10.0),
            bet("2026-09-02T02:00Z", -10.0), bet("2026-09-02T03:30Z", -10.0),   # Sep 1 in New York: -$40
            bet("2026-09-02T15:00Z", -10.0), bet("2026-09-02T16:00Z", 0.5),     # Sep 2: -$9.50
            bet("2026-09-03T15:00Z", 0.5)]                                     # Sep 3: up
    # Days by UTC date would give -$20, -$29.50 and +$0.50, so a worst of 29.5 / 240.
    assert om.stats(rows)["worst"] == pytest.approx(40 / 240)


def test_worst_day_is_zero_when_no_day_loses(study):
    rows = [bet("2026-09-01T15:00Z", -10.0), bet("2026-09-01T16:00Z", 10.5),   # a loss, but the day ends up
            bet("2026-09-02T15:00Z", 0.5)]
    assert study.other_markets.stats(rows)["worst"] == 0.0


def test_stats_with_one_close_time_has_no_range(study):
    s = study.other_markets.stats([bet("2026-09-01T15:00Z", 0.5)])
    assert (s["bets"], s["series"], s["days"]) == (1, 1, 1) and math.isnan(s["lo"]) and math.isnan(s["hi"])


# ------------------------------------------------------------------ candidates


def test_a_group_needs_200_choosing_bets(study):
    om = study.other_markets
    assert om.candidates(run(200)) == [A]
    assert om.candidates(run(199)) == []
    assert om.candidates(run(199) + [bet(TEST_FROM, 0.5)]) == []      # one at exactly SPLIT is a test-half bet


def test_a_group_under_2c_or_with_a_range_touching_zero_is_left_out(study):
    om = study.other_markets
    assert om.candidates(run(200, pnls=[0.01])) == []
    assert om.candidates(run(200, pnls=[0.02])) == [A]               # exactly +2c is enough
    assert om.candidates(run(200, pnls=[0.03])) == [A]
    noisy = run(200, pnls=[1.05, -1.0])
    s = om.stats(noisy)
    assert s["mu"] >= om.EDGE and s["lo"] <= 0 and om.candidates(noisy) == []


def test_a_range_starting_at_exactly_zero_is_not_above_it(study, monkeypatch):
    """Bets can't be made to land on lo == 0.0 exactly, so candidates() gets its group's stats from a stand-in."""
    om = study.other_markets
    rows = run(200)
    for lo, want in ((0.0, []), (1e-12, [A]), (float("nan"), [])):
        monkeypatch.setattr(om, "stats", lambda rs, lo=lo: good(bets=len(rs), lo=lo))
        assert om.candidates(rows) == want


def test_illiquid_bets_never_count(study):
    om = study.other_markets
    later = CHOOSE_FROM + timedelta(minutes=30)
    assert om.candidates(run(200, liquid=False)) == []
    assert om.candidates(run(150) + run(100, start=later, liquid=False)) == []
    assert om.candidates(run(200) + run(200, start=later, pnls=[-10.0], liquid=False)) == [A]


def test_groups_are_category_frequency_and_checkpoint(study):
    om = study.other_markets
    later = CHOOSE_FROM + timedelta(minutes=30)
    assert om.candidates(run(100) + run(100, start=later, series="KXETHD")) == [A]    # series don't split a group
    assert om.candidates(run(100) + run(100, key=("Crypto", "hourly", "5min"), start=later)) == []
    assert om.candidates(run(100) + run(100, key=("Crypto", "daily", "10min"), start=later)) == []


def test_candidates_come_sorted_by_key(study):
    rows = (run(200, key=C) + run(200, key=A, start=CHOOSE_FROM + timedelta(minutes=20))
            + run(200, key=B, start=CHOOSE_FROM + timedelta(minutes=40)))
    assert study.other_markets.candidates(rows) == sorted([A, B, C]) == [B, A, C]


def test_the_test_half_has_no_say_in_the_choice(study):
    om = study.other_markets
    base = run(200) + run(199, key=B, start=CHOOSE_FROM + timedelta(minutes=30))
    later = (run(1000, start=TEST_FROM) + run(1000, key=B, start=TEST_FROM + timedelta(minutes=30))
             + run(500, key=C, start=TEST_FROM, pnls=[0.5]))
    assert om.candidates(base) == [A]
    for test_half in (later,
                      [x[:5] + (-10.0, x[6]) for x in later],        # every test bet loses
                      [x[:6] + (not x[6],) for x in later],          # liquidity flipped
                      later[::2],                                    # half of them gone
                      [bet(TEST_FROM, 0.5, B)]):                     # B's 200th, at exactly SPLIT
        assert om.candidates(base + test_half) == [A]
        assert om.candidates(test_half + base) == [A]


# ------------------------------------------------------------------ verdict


def test_a_candidate_that_meets_every_condition_passes(study):
    assert study.other_markets.verdict(good(), good()) == []


def test_no_test_half_is_the_only_reason_given(study):
    om = study.other_markets
    assert om.verdict(good(), None) == ["no test-half bets"]
    assert om.verdict(good(mu=-0.5), None) == ["no test-half bets"]


@pytest.mark.parametrize("choose, test, reason", [
    (good(mu=0.0199), good(), "choosing half under +2c"),
    (good(), good(mu=0.0199), "test half under +2c"),
    (good(), good(lo=0.0), "test range not above zero"),
    (good(), good(lo=-0.01), "test range not above zero"),
    (good(), good(lo=float("nan"), hi=float("nan")), "test range not above zero"),
    (good(), good(bets=999), "under 1,000 test bets"),
    (good(), good(series=4, days=19), "under 5 series and under 20 days"),
    (good(), good(worst=0.30), "worst day 30%+"),
    (good(), good(worst=0.95), "worst day 30%+"),
])
def test_each_condition_alone(study, choose, test, reason):
    assert study.other_markets.verdict(choose, test) == [reason]


@pytest.mark.parametrize("choose, test", [
    (good(mu=0.02), good(mu=0.02)),               # exactly +2c passes, in either half
    (good(), good(lo=1e-9)),
    (good(), good(bets=1000)),
    (good(), good(series=5, days=1)),             # 5 series or 20 days, either will do
    (good(), good(series=1, days=20)),
    (good(), good(worst=0.2999)),
    (good(), good(worst=0.0)),
    (good(lo=-0.5), good()),                      # only the test half's range is a condition
])
def test_boundaries_that_pass(study, choose, test):
    assert study.other_markets.verdict(choose, test) == []


def test_reasons_come_in_the_plans_order(study):
    test = good(mu=0.0, lo=-0.1, bets=10, series=1, days=2, worst=0.5)
    assert study.other_markets.verdict(good(mu=0.0), test) == [
        "choosing half under +2c", "test half under +2c", "test range not above zero", "under 1,000 test bets",
        "under 5 series and under 20 days", "worst day 30%+"]


# ------------------------------------------------------------------ pass_test and main


def plan_rows():
    """A passes. B is a good choice with too few test bets, on too few days, from one series. C is chosen but its
    test-half bets are all illiquid. The 20-minute group has too few bets to be chosen."""
    return (run(200) + run(1000, start=TEST_FROM, hours=1)
            + run(200, key=B, start=CHOOSE_FROM + timedelta(minutes=20))
            + run(300, key=B, start=TEST_FROM + timedelta(minutes=20), hours=1)
            + run(200, key=C, start=CHOOSE_FROM + timedelta(minutes=40))
            + run(300, key=C, start=TEST_FROM, liquid=False)
            + run(50, key=("Crypto", "hourly", "20min"), start=CHOOSE_FROM + timedelta(minutes=10)))


def test_pass_test_scores_each_candidate_on_the_test_half(study, capsys):
    om = study.other_markets
    rows = plan_rows()
    result = om.pass_test(rows)
    assert [r[0] for r in result] == om.candidates(rows) == [B, A, C]
    liquid = [x for x in rows if x[6]]
    for key, choose, test, reasons in result:
        mine = [x for x in liquid if (x[0], x[1], x[3]) == key]
        assert choose == om.stats([x for x in mine if x[4] < om.SPLIT])
        assert test == om.stats([x for x in mine if x[4] >= om.SPLIT])
        assert reasons == om.verdict(choose, test)
    by = {r[0]: r for r in result}
    assert by[A][3] == []
    assert by[B][3] == ["under 1,000 test bets", "under 5 series and under 20 days"]
    assert by[C][2] is None and by[C][3] == ["no test-half bets"]


def test_pass_test_prints_a_line_per_candidate(study, capsys):
    om = study.other_markets
    om.pass_test(plan_rows())
    lines = capsys.readouterr().out.splitlines()
    assert any("The plan's pass test" in line for line in lines)
    at = {key: next(i for i, line in enumerate(lines) if all(part in line for part in key)) for key in (A, B, C)}
    assert at[B] < at[A] < at[C]                                     # in the candidates' order
    assert "PASS" in lines[at[A]]
    assert "under 1,000 test bets; under 5 series and under 20 days" in lines[at[B]] and "PASS" not in lines[at[B]]
    assert "no test-half bets" in lines[at[C]] and "PASS" not in lines[at[C]]
    assert "1 of 3 candidates passed." in lines


def test_a_bet_at_the_split_is_tested_not_chosen(study):
    (key, choose, test, reasons), = study.other_markets.pass_test(run(200) + [bet(TEST_FROM, 0.5)])
    assert key == A and choose["bets"] == 200 and test["bets"] == 1
    assert "no test-half bets" not in reasons and "under 1,000 test bets" in reasons


def test_pass_test_with_no_candidates(study, capsys):
    om = study.other_markets
    for rows in ([], run(199), run(500, start=TEST_FROM)):
        assert om.pass_test(rows) == []
        out = capsys.readouterr().out
        assert "The plan's pass test" in out and "No group qualified on the choosing half." in out


def test_main_prints_the_pass_test_after_the_tables(study, capsys, monkeypatch):
    om = study.other_markets
    om.main()
    out = capsys.readouterr().out
    assert out.index("By series and checkpoint") < out.index("The plan's pass test")
    assert "No group qualified on the choosing half." in out or "candidates passed." in out
    seen = []
    monkeypatch.setattr(om, "pass_test", lambda rows: seen.append(rows) or [])
    om.main()
    assert seen == [om.bets()]
