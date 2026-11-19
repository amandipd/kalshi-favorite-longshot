"""history.py, minutes.py, analyze.py, exit_timing.py and other_markets.py against the synthetic history.

history.py is what every backtest reads its markets through, so its promises get the most checks: each market
once, the first file's copy winning, only the groups asked for, and an end date that is the midnight after the
last market. The analyses are checked against independent recomputations from the same rows.
"""

from __future__ import annotations

import csv
import math

import pytest

EDGE = ("crypto", "metals", "energy")


def favourite(bid, ask):
    """The research's rule, restated: the side with the higher ask; NO costs 1 - the YES bid."""
    if bid is None or ask is None or abs(ask - (1 - bid)) < 1e-9:
        return None
    return ("yes", ask) if ask > 1 - bid else ("no", 1 - bid)


def num(x):
    return float(x) if x != "" else None


# ------------------------------------------------------------------ history


def test_groups_come_from_the_universe(study):
    g = study.history.groups()
    assert g["KXBTC15M"] == "crypto" and g["KXGOLD15M"] == "metals" and g["KX10YRRATE15M"] == "rates"


def test_each_market_comes_once_from_the_first_file_that_has_it(study):
    rows = list(study.history.each(None))
    tickers = [r["ticker"] for r in rows]
    assert len(tickers) == len(set(tickers)) == len(study.data["rows"])
    dup = study.data["first_copy"]
    assert next(r for r in rows if r["ticker"] == dup["ticker"])["resolved_yes"] == dup["resolved_yes"]


def test_each_defaults_to_the_groups_the_strategy_bets(study):
    groups = study.history.groups()
    edge = list(study.history.each())
    assert {groups[r["series"]] for r in edge} == set(EDGE)
    assert len(list(study.history.each(("fx",)))) == sum(r["series"] == "KXEURUSD15M" for r in study.data["rows"])


def test_the_history_ends_the_midnight_after_its_last_market(study):
    assert study.history.end() == "2026-10-02T00:00:00Z"


def test_strategy_prints_only_the_strategy_paragraph(study, capsys):
    study.history.strategy("Title.\n\nStrategy: buy the\n   favourite.\n\nMore.")
    study.history.strategy("No strategy here.")
    assert capsys.readouterr().out == "Strategy: buy the favourite.\n\n"


def test_snapshots_hold_every_edge_market_that_traded_by_minute_8_in_time_order(study, capsys):
    study.history.write_snapshots()
    with open("snapshots_all.csv") as fh:
        snaps = list(csv.DictReader(fh))
    expected = [r for r in study.history.each() if r["p8"] != ""]
    assert len(snaps) == len(expected) and f"{len(snaps)} markets" in capsys.readouterr().out
    assert [(s["open_time"], s["series"]) for s in snaps] == sorted((s["open_time"], s["series"]) for s in snaps)
    by_ticker = {r["ticker"]: r for r in expected}
    for s in snaps[:50]:
        r = by_ticker[s["ticker"]]
        assert (s["price_8min"], s["yes_bid"], s["yes_ask"], s["price_7"]) == (r["p8"], r["b8"], r["a8"], r["p7"])


# ------------------------------------------------------------------ minutes


def test_minutes_load_finds_each_minutes_favourite(study):
    fav = study.minutes.load()
    assert set(fav) == set(range(1, 16))
    expected = []
    for r in study.history.each():
        f = favourite(num(r["b8"]), num(r["a8"]))
        if f:
            expected.append((r["open_time"], r["series"], f[1], (f[0] == "yes") == (r["resolved_yes"] == "1")))
    assert len(fav[8]) == len(expected)
    for got, want in zip(sorted(fav[8]), sorted(expected)):
        assert got[:2] == want[:2] and got[2] == pytest.approx(want[2]) and got[3] == want[3]


def test_minutes_load_reads_a_single_file_when_asked(study):
    fav = study.minutes.load("minutes_new.csv")
    assert {s for k in fav for _, s, _, _ in fav[k]} <= {"KXEURUSD15M", "KXCRYPTOLEAD15M"}


def test_the_crypto_multiplier_applies_to_crypto_series_only(study):
    m = study.minutes
    assert m.fee(10, 0.5, "KXBTC15M", 2.0) == math.ceil(2 * 0.07 * 10 * 0.25 * 100 - 1e-9) / 100
    assert m.fee(10, 0.5, "KXGOLD15M", 2.0) == m.fee(10, 0.5, "KXGOLD15M", 1.0) == 0.18


def test_bets_at_prices_a_10_dollar_bet_at_the_ask(study):
    fav = {8: [("t1", "KXGOLD15M", 0.95, True), ("t1", "KXBTC15M", 0.92, False), ("t2", "KXBTC15M", 0.5, True),
               ("t2", "KXWTI15M", 1.0, True)]}
    bs = study.minutes.bets_at(fav, 8, 0.90, 1.01)
    assert [b["fill"] for b in bs] == [0.95, 0.92]
    c = 10 / 0.95
    assert bs[0]["pnl"] == pytest.approx(c - 10 - study.minutes.fee(c, 0.95, "KXGOLD15M", 1.0))
    assert bs[1]["pnl"] == pytest.approx(-10 - bs[1]["fee"])
    assert bs[0]["need"] == pytest.approx((10 + bs[0]["fee"]) / c)


def test_clustered_needs_30_bets_in_two_windows_and_widens_with_correlation(study):
    clustered = study.minutes.clustered
    assert clustered([[1.0] * 29]) == (None, None, None)
    assert clustered([[1.0] * 40]) == (None, None, None)
    independent = [[x] for x in [1.0, -1.0] * 20]
    lumped = [[1.0] * 10, [-1.0] * 10, [1.0] * 10, [-1.0] * 10]
    mu, lo, hi = clustered(independent)
    mu2, lo2, hi2 = clustered(lumped)
    assert mu == mu2 == 0.0 and (hi2 - lo2) > (hi - lo) > 0


def test_bankroll_skips_bets_it_cant_afford_and_stops_when_broke(study):
    m = study.minutes
    win = {"t": "a", "fee": 0.02, "pnl": 0.5}
    lose = {"t": "b", "fee": 0.02, "pnl": -10.02}
    r = m.bankroll([win, lose])
    assert r["final"] == pytest.approx(240 + 0.5 - 10.02) and r["broke"] is None and r["worst"] == pytest.approx(-10.02)
    ruin = [{"t": f"w{i:03d}", "fee": 0.02, "pnl": -10.02} for i in range(30)]
    r = m.bankroll(ruin)
    assert r["broke"] is not None and r["final"] < 10 and r["dd"] > 0.9


def test_analyse_and_report(study, capsys):
    res = study.minutes.analyse(study.minutes.load())
    assert set(res["byMult"]) == {"1.0", "1.5", "2.0"} and len(res["byMult"]["1.0"]) == 15
    assert len(res["grid"]) == 15 * len(study.minutes.BANDS)
    assert res["oos"]["m8"]["k"] == 8 and 1 <= res["oos"]["bestK"] <= 15
    # a bigger crypto fee never helps
    for a, b in zip(res["byMult"]["1.0"], res["byMult"]["2.0"]):
        if a["mu"] is not None and b["mu"] is not None:
            assert b["mu"] <= a["mu"] + 1e-12
    study.minutes.report(res)
    out = capsys.readouterr().out
    assert "90¢+ FAVORITES" in out and "FAIR TEST" in out


# ------------------------------------------------------------------ analyze


def test_analyze_wilson_matches_the_study(study):
    from kalshi_calibration.analysis.statistics import wilson_interval
    for k, n in ((0, 10), (7, 10), (95, 100), (3, 3)):
        lo, hi = study.analyze.wilson(k, n)
        ref = wilson_interval(k, n, 0.95)
        assert lo == pytest.approx(ref[0], abs=5e-4) and hi == pytest.approx(ref[1], abs=5e-4)
    assert study.analyze.wilson(0, 0) == (0.0, 0.0)


def test_analyze_calibration_bands_every_snapshot(study, capsys):
    study.history.write_snapshots()
    rows = study.analyze.load_rows()
    table = study.analyze.calibration(rows)
    assert sum(c["n"] for c in table) == len(rows)
    for c in table:
        assert c["diff"] == pytest.approx(c["actual"] - c["price"]) and c["lo"] <= c["actual"] <= c["hi"]
        assert c["low"] <= c["price"] <= c["high"] or c["band"] == 9
    study.analyze.main()
    out = capsys.readouterr().out
    assert "CALIBRATION AT THE 8-MINUTE MARK" in out and "Edge is fully eaten at taker multiplier" in out


# ------------------------------------------------------------------ exit_timing


def test_exit_timing_fee_is_per_contract_on_a_100_contract_order(study):
    assert study.exit_timing.fee(0.5) == 0.0175
    assert study.exit_timing.fee(0.99) == pytest.approx(math.ceil(0.07 * 100 * 0.99 * 0.01 * 100) / 10000)


def test_positions_are_the_minute_8_favourites_with_their_own_quotes(study):
    ps = study.exit_timing.positions()
    assert ps and all(0.90 <= p["price"] <= 0.999 for p in ps)
    for p in ps:
        bid, ask = p["q"][8]
        assert ask == pytest.approx(p["price"]) and bid <= ask
    expected = sum(1 for r in study.history.each() if (f := favourite(num(r["b8"]), num(r["a8"]))) and 0.90 <= f[1] <= 0.999)
    assert len(ps) == expected


def test_exit_timing_clustered(study):
    clustered = study.exit_timing.clustered
    assert clustered([]) == (None, None) and clustered([(1, 0.5)]) == (0.5, None)
    assert clustered([(1, 1.0), (1, 0.0)]) == (0.5, None)          # one window: no clustered error
    mu, se = clustered([(1, 1.0), (2, 0.0), (3, 1.0), (4, 0.0)])
    assert mu == 0.5 and se > 0


def test_exit_timing_main_prints_every_section(study, capsys):
    study.exit_timing.main()
    out = capsys.readouterr().out
    for heading in ("Sell or hold", "The crossing law", "Every simple rule", "Best rule:", "Buying the dip"):
        assert heading in out


# ------------------------------------------------------------------ other_markets


def test_other_markets_bets_follow_the_rule_at_every_checkpoint(study):
    om = study.other_markets
    bets = om.bets()
    assert bets and {b[3] for b in bets} <= {f"{k}min" for k in om.CHECKS["min"]} | {f"{k}h" for k in om.CHECKS["hour"]}
    assert {b[0] for b in bets} <= {"Crypto", "Financials", "Climate"}
    assert all(b[5] <= 10 / 0.9 - 10 for b in bets)        # nothing wins more than a 90c favourite pays
    assert om.fee(10, 0.5, 2.0) == 0.35 and om.num("") is None


def test_other_markets_summary_and_main(study, capsys):
    om = study.other_markets
    rows = om.bets()
    mu, se, text = om.summary(rows)
    assert mu == pytest.approx(sum(b[5] for b in rows) / len(rows)) and se > 0 and f"{len(rows):,}" in text
    om.main()
    out = capsys.readouterr().out
    assert "By category, frequency and time before close" in out and "liquid only" in out


def test_a_missing_minute_file_is_skipped_by_every_loader(study, monkeypatch):
    """A checkout without minutes_pre.csv (or any other of the four) still runs: each loader reads the files it finds."""
    before = (len(study.findings.load()), sum(len(w) for d in study.risk_rules.load() for w in d), len(study.stress_signals.load()))
    monkeypatch.setattr(study.history, "FILES", study.history.FILES + ("minutes_not_fetched.csv",))
    after = (len(study.findings.load()), sum(len(w) for d in study.risk_rules.load() for w in d), len(study.stress_signals.load()))
    assert after == before
