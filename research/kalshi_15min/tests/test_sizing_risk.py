"""sizing.py (how big each bet should be) and risk_rules.py (taking profit out, stops and pauses).

Both replay bankrolls window by window, so the hand-built cases check the bookkeeping -- whole contracts, the
window cap, the broke rule, what a stop does to the state -- and the `main()`s run on the synthetic history
with their resampling cut to a handful of paths (the real runs resample hundreds in a process pool).
"""

from __future__ import annotations

import json
from datetime import date
import math
import random
from concurrent.futures import ThreadPoolExecutor

import pytest


def fee(c, p, mult=1.0):
    return math.ceil(mult * 0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


# ------------------------------------------------------------------ sizing


def test_sizing_fee_multiplies_only_crypto(study):
    sz = study.sizing
    assert sz.fee(10, 0.95, True, 2.0) == fee(10, 0.95, 2.0)
    assert sz.fee(10, 0.95, False, 2.0) == fee(10, 0.95) == 0.04


def test_a_flat_bet_buys_whole_contracts_at_the_ask(study):
    final, dd, worst, broke = study.sizing.run([[[(0.95, True, False)]]], None, 0.0, 1.0)
    assert final == pytest.approx(240 + 10 * 0.05 - fee(10, 0.95)) and dd == 0 and not broke


def test_a_loss_is_the_stake_and_the_fee(study):
    final, dd, worst, _ = study.sizing.run([[[(0.95, False, False)]]], None, 0.0, 1.0)
    assert final == pytest.approx(240 - 9.5 - fee(10, 0.95))
    assert worst == pytest.approx((-9.5 - fee(10, 0.95)) / 240) and dd == pytest.approx(1 - final / 240)


def test_the_window_cap_shrinks_every_bet_in_a_busy_window(study):
    window = [(0.95, True, False)] * 10
    capped, *_ = study.sizing.run([[window]], 0.06, 0.0, 1.0, wcap=0.20)    # 20% of $240 over 10 bets: $4.80
    c = math.floor(4.8 / 0.95)
    assert capped == pytest.approx(240 + 10 * (c * 0.05 - fee(c, 0.95)))


def test_slippage_and_a_tiny_percentage_break_the_account(study):
    assert study.sizing.run([[[(0.95, True, False)]]], 0.001, 0.0, 1.0) == (0.0, 1.0, 0.0, True)
    slipped, *_ = study.sizing.run([[[(0.95, True, False)]]], None, 0.004, 1.0)
    assert slipped == pytest.approx(240 + 10 * (1 - 0.954) - fee(10, 0.954))


def test_quantile_and_labels(study):
    sz = study.sizing
    assert sz.quantile([5, 1, 3, 2, 4], 0.5) == 3 and sz.quantile([1, 2], 0.99) == 2
    assert sz.label(None) == "flat $10" and sz.label(1 / 24) == "1/24"
    assert sz.label(0.03, 0.2) == "3%, window<=20%" and sz.label(0.015) == "1.5%"


def test_one_bet_kelly_by_hand(study):
    days = [[[(0.95, True, False), (0.95, True, False), (0.95, False, False)]]]
    q, cost, k = study.sizing.kelly_single(days, 0.0, 1.0)
    c = 10 / 0.95
    assert q == pytest.approx(2 / 3) and cost == pytest.approx(0.95 + fee(c, 0.95) / c)
    assert k == pytest.approx((q - cost) / (1 - cost))


def test_days_of_windows_groups_the_90c_favourites_by_day(study):
    days = study.sizing.days_of_windows()
    assert 1 <= len(days) <= 76 + 14      # the 76 days from Jul 18 and the 14 before it
    for day in days:
        for window in day:
            assert window and all(0.90 <= ask < 0.9991 for ask, _, _ in window)


def test_study_resamples_whole_days(study, monkeypatch):
    monkeypatch.setattr(study.sizing, "PATHS", 20)
    days = study.sizing.days_of_windows()
    r = study.sizing.study((days, 0.03, "realistic", 0.2, 30))
    assert r["p10"] <= r["p50"] <= r["p90"] and 0 <= r["broke"] <= r["dd50"] + r["broke"] <= 2
    assert r["hist"] == study.sizing.run(days, 0.03, 0.004, 1.0, 0.2)


def test_sizing_main_writes_every_rule_and_scenario(study, monkeypatch, capsys):
    monkeypatch.setattr(study.sizing, "PATHS", 3)
    monkeypatch.setattr(study.sizing, "ProcessPoolExecutor", ThreadPoolExecutor)
    study.sizing.main()
    with open("sizing.json", encoding="utf-8") as fh:
        rows = json.load(fh)
    rules = 1 + len(study.sizing.PCTS) + len(study.sizing.WINDOW_CAPS)
    assert len(rows) == rules * 3 + rules * 2      # 30 days in all three scenarios, 90 days in two
    assert {r["scenario"] for r in rows} == set(study.sizing.SCENARIOS)
    assert "one-bet Kelly" in capsys.readouterr().out


# ------------------------------------------------------------------ risk_rules


def window(*bets, stake=10.0):
    """A window as risk_rules.load builds it: (bets, $10 pnl, $10 losses, cash needed)."""
    bets = list(bets)
    pnl, losses = study_play(bets, stake)
    need = sum(stake + fee(stake / p, p) for p, _ in bets)
    return (bets, pnl, losses, need)


def study_play(bets, stake):
    pnl = losses = 0
    for price, won in bets:
        c = stake / price
        pnl += (c if won else 0.0) - stake - fee(c, price)
        losses += not won
    return pnl, losses


def test_play_skips_bets_the_cash_cant_cover(study):
    rr = study.risk_rules
    pnl, losses = rr.play([(0.95, False), (0.95, False)], 10.0, 15.0)
    assert losses == 1 and pnl == pytest.approx(-10 - fee(10 / 0.95, 0.95))
    assert rr.cents(1.239) == 1.23 and rr.cents(2.0) == 2.0


def test_load_keeps_every_window_even_without_a_bet(study):
    rr = study.risk_rules
    days = rr.load()
    windows = [w for d in days for w in d]
    # one entry per UTC day from Dec 10, 2025 to Oct 1, 2026; markets on the 14 days before Jul 18 and the 76 from it
    assert len(windows) == (14 + 76) * 8 and sum(1 for d in days if d) == 14 + 76
    assert len(days) == (date(2026, 10, 1) - date(2025, 12, 10)).days + 1
    assert len(rr.since(days, study.history.JUL18)) == 76 and rr.since(days, study.history.FIRST) == days
    assert rr.since(days, "2026-08-24T00:00:00Z") == days[-39:]
    assert any(not w[0] for w in windows) and any(w[0] for w in windows)
    for bets, pnl, losses, need in windows:
        assert losses == sum(not won for _, won in bets)
        assert all(price <= 0.999 for price, _ in bets)


def test_a_flat_run_without_rules_adds_up_the_windows(study):
    days = [[window((0.95, True)), window((0.95, False))], [window((0.96, True))]]
    r = study.risk_rules.simulate(days)
    expected = 240 + sum(w[1] for d in days for w in d)
    assert r == {"home": pytest.approx(expected), "taken": 0.0, "state": "on", "bets": 3}


def test_taking_profit_above_a_line_moves_it_out_of_the_account(study):
    days = [[window(*[(0.95, True)] * 20)] for _ in range(3)]
    r = study.risk_rules.simulate(days, take=(1, "above:240"))
    assert r["taken"] > 0 and r["home"] == pytest.approx(240 + sum(d[0][1] for d in days))
    half = study.risk_rules.simulate(days, take=(1, "half"))
    assert 0 < half["taken"] < r["taken"]


@pytest.mark.parametrize("stop,state", [(("loss", 5), "stopped"), (("dd", 0.01), "stopped"), (("day", 5), "paused"),
                                        (("trail", 5), "paused"), (("cluster", 1, 1), "on")])
def test_each_stop_rule(study, stop, state):
    losing = [[window((0.95, False)), window((0.95, False)), window((0.95, True))] for _ in range(2)]
    r = study.risk_rules.simulate(losing, stop=stop)
    assert r["state"] == state
    assert r["bets"] <= 6


def test_a_day_pause_lifts_at_the_next_utc_day(study):
    losing = [[window((0.95, False)), window((0.95, False)), window((0.95, True))] for _ in range(2)]
    assert study.risk_rules.simulate(losing, stop=("day", 5))["bets"] == 2      # the first window of each day


def test_a_paused_rule_bets_less_than_no_rule(study):
    losing = [[window((0.95, False)), window((0.95, False)), window((0.95, True))] for _ in range(2)]
    assert study.risk_rules.simulate(losing, stop=("cluster", 1, 1))["bets"] < study.risk_rules.simulate(losing)["bets"]


def test_capped_and_floor_sizing_run(study):
    days = [[window(*[(0.95, True)] * 4)] for _ in range(5)]
    capped = study.risk_rules.simulate(days, sizing="capped")
    floor = study.risk_rules.simulate(days, sizing=("floor", 0.5, 0.06, 0.40))
    assert capped["home"] > 240 and floor["home"] > 240 and capped["state"] == floor["state"] == "on"


def test_a_tiny_account_goes_broke(study):
    days = [[window((0.95, False))] for _ in range(40)]
    assert study.risk_rules.simulate(days)["state"] == "broke"


def test_block_paths_and_quantile(study, monkeypatch):
    rr = study.risk_rules
    monkeypatch.setattr(rr, "RUNS", 7)
    monkeypatch.setattr(rr, "HORIZON", 12)
    days = [[i] for i in range(20)]
    paths = list(rr.block_paths(days, random.Random(1)))
    assert len(paths) == 7 and all(len(p) == 12 for p in paths)
    for p in paths:   # whole blocks of consecutive days
        assert p[1][0] == p[0][0] + 1
    assert rr.quantile([3, 1, 2], 0.0) == 1


def test_worst_drop_is_peak_to_trough_in_dollars(study):
    days = [[([], 5.0, 0, 0), ([], -8.0, 0, 0)], [([], 2.0, 0, 0), ([], -4.0, 0, 0)]]
    assert study.risk_rules.worst_drop(days) == 10.0


def test_risk_rules_main_prints_every_table(study, monkeypatch, capsys):
    monkeypatch.setattr(study.risk_rules, "RUNS", 3)
    monkeypatch.setattr(study.risk_rules, "HORIZON", 10)
    study.risk_rules.main()
    out = capsys.readouterr().out
    for heading in ("DO LOSSES COME IN RUNS?", "TAKING PROFIT OUT", "COMBINED", "STOPS", "FLOOR THAT RISES"):
        assert heading in out


def test_risk_rules_reports_each_rule_from_every_start(study, monkeypatch, capsys):
    monkeypatch.setattr(study.risk_rules, "RUNS", 3)
    monkeypatch.setattr(study.risk_rules, "HORIZON", 10)
    days = study.risk_rules.load()
    study.risk_rules.report(days, [("none", {})])
    head = capsys.readouterr().out.splitlines()[1]
    assert head.index("from Dec 10") < head.index("from Jul 18") < head.index("from Aug 24")
