"""Tests for kalshi_calibration/analysis/report.py: `make analyze`.

The formatters are checked against hand-built rows, and `run()` end to end on a synthetic corpus with a
planted favourite-longshot bias -- long shots overpriced, favourites underpriced -- so the printed verdicts
have a known right answer. The run writes into a temporary working directory, and the test checks that
every CSV and summary.json it leaves agree with each other, since the figures and dashboard read one and
a reader reads the other.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from kalshi_calibration.analysis import report
from test_backtest import strategy_config

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def study_frame(n=4000, tilt=0.12, seed=3) -> pd.DataFrame:
    """Contracts whose true probability is the price pushed away from 50c by `tilt`: the bias the study
    looks for. Lifetimes and categories vary so every segmentation has something to split."""
    rng = np.random.default_rng(seed)
    price = rng.uniform(0.04, 0.96, n)
    truth = np.clip(price + tilt * (price - 0.5) * 2, 0.005, 0.995)
    outcome = rng.binomial(1, truth)
    close = [T0 + timedelta(hours=float(h)) for h in np.sort(rng.uniform(0, 3000, n))]
    lifetime = rng.lognormal(3.2, 0.8, n)
    return pd.DataFrame({
        "ticker": [f"T{i}" for i in range(n)],
        "event_ticker": [f"E{i // 2}" for i in range(n)],
        "category": rng.choice(["Sports", "Economics"], n, p=[0.8, 0.2]),
        "implied_price": price,
        "outcome": outcome,
        "open_ts": [c - timedelta(hours=float(h)) for c, h in zip(close, lifetime)],
        "close_ts": close,
        "settle_ts": [c + timedelta(minutes=20) for c in close],
    })


# ------------------------------------------------------------------ formatters


@pytest.mark.parametrize("q,significant,expected", [
    (0.0001, True, "***"), (0.005, True, "**"), (0.03, True, "*"), (0.0001, False, ""), (math.nan, False, ""),
])
def test_stars_read_the_corrected_q_value(q, significant, expected):
    assert report._stars(q, significant) == expected


def table_row(**overrides):
    row = dict(bucket=1, bucket_low=0.1, bucket_high=0.2, n=1234, n_events=567, mean_price=0.15,
               realized_freq=0.12, bias=-0.03, ci_low=0.11, ci_high=0.13, design_effect=1.4,
               q_value=0.0004, significant=True, underpowered=False, segment="Sports")
    row.update(overrides)
    return row


def test_format_table_shows_the_clustered_interval_and_stars_not_the_wilson_one():
    text = report.format_table(pd.DataFrame([table_row(wilson_low=0.0, wilson_high=0.99)]))
    header, rule, line = text.splitlines()
    assert "95% CI (clustered)" in header and set(rule) == {"-"}
    assert "0.10-0.20" in line and "1,234" in line and "-0.0300" in line
    assert "[0.1100, 0.1300]" in line and line.endswith("***")
    assert "0.9900" not in text


def test_format_table_leaves_an_insignificant_bucket_unstarred():
    line = report.format_table(pd.DataFrame([table_row(q_value=0.4, significant=False)])).splitlines()[-1]
    assert not line.endswith("*")


def test_format_decomposition_shows_every_term_and_the_residual():
    parts = dict(brier=0.2, reliability=0.001, resolution=0.05, uncertainty=0.249, base_rate=0.47,
                 binned_brier=0.2001, binning_residual=-0.0001, n_buckets=10)
    text = report.format_decomposition(parts)
    for label in ("Brier score", "reliability", "resolution", "uncertainty", "binned Brier", "binning residual"):
        assert label in text
    assert "base rate 0.4700" in text and "-0.000100" in text and "the 10 buckets" in text


@dataclass
class Fit:
    slope: float
    slope_ci: tuple = (0.9, 1.1)
    slope_z: float = 2.0
    slope_p: float = 0.04
    intercept: float = 0.01
    intercept_ci: tuple = (-0.01, 0.03)
    intercept_z: float = 1.0
    intercept_p: float = 0.3
    joint_chi2: float = 5.0
    joint_df: int = 2
    joint_p: float = 0.08
    n: int = 1000
    n_clusters: int = 400
    pseudo_r2: float = 0.3


def test_format_logistic_reads_a_steep_slope_as_the_favourite_longshot_direction():
    text = report.format_logistic(Fit(slope=1.08))
    assert "slope > 1" in text and "longshots overpriced" in text
    assert "1,000 contracts, 400 clusters" in text and "on 2 df" in text


def test_format_logistic_reads_a_shallow_slope_as_the_reverse():
    text = report.format_logistic(Fit(slope=0.9))
    assert "slope < 1" in text and "reverse of the hypothesis" in text


def test_format_segments_marks_thin_cells_instead_of_testing_them():
    table = pd.DataFrame([
        table_row(segment="Economics", underpowered=True, q_value=math.nan, significant=False),
        table_row(segment="Economics", bucket_low=0.2, bucket_high=0.4, underpowered=False, q_value=0.02),
        table_row(segment="Sports", underpowered=False, q_value=0.5, significant=False),
    ])
    lines = report.format_segments(table, "category").splitlines()[2:]
    assert lines[0].strip().startswith("Economics") and lines[0].endswith("(thin)")
    assert not lines[1].strip().startswith("Economics"), "a segment's name is printed once"
    assert lines[1].endswith("*") and "2.00e-02" in lines[1]
    assert lines[2].strip().startswith("Sports") and not lines[2].endswith("*")


METRICS = dict(trades=10, roi=0.05, hit_rate=0.6, total_pnl=0.3, gross_pnl=0.35, fees_paid=0.05,
               final_equity=1.3, max_drawdown=-0.1, sharpe_like=1.2, trading_days=4, breakeven_slippage=0.012)


def backtest_text(main_roi, control_roi):
    split = SimpleNamespace(split_ts=pd.Timestamp("2026-04-20", tz="UTC"), train=[0] * 600, test=[0] * 400,
                            excluded=3)
    rules = pd.DataFrame([{"mean_price": 0.15, "side": "no", "gross_edge": 0.03, "fee": 0.009,
                           "net_edge": 0.021, "trade": True},
                          {"mean_price": 0.55, "side": "yes", "gross_edge": 0.002, "fee": 0.017,
                           "net_edge": -0.015, "trade": False}])
    return report.format_backtest({**METRICS, "roi": main_roi}, {**METRICS, "roi": control_roi}, split, rules)


def test_format_backtest_puts_the_control_beside_the_strategy():
    text = backtest_text(0.05, -0.2)
    assert "Split 2026-04-20: 600 contracts to estimate on, 400 to trade, 3 dropped" in text
    assert "STRATEGY" in text and "CONTROL" in text
    assert "Breakeven slippage: 1.20c per contract." in text
    lines = text.splitlines()
    assert any(line.rstrip().endswith("YES") for line in lines) and any(line.rstrip().endswith("no") for line in lines)


def test_format_backtest_claims_falsification_only_when_the_control_loses_and_the_strategy_wins():
    assert "Falsification" in backtest_text(0.05, -0.2)
    assert "Falsification" not in backtest_text(0.05, 0.01)
    assert "Falsification" not in backtest_text(-0.01, -0.2)


# ------------------------------------------------------------------ run(), end to end


@pytest.fixture(scope="module")
def analyzed(tmp_path_factory):
    folder = tmp_path_factory.mktemp("analyze")
    config = strategy_config()
    config = config.model_copy(update={"clean": config.clean.model_copy(
        update={"processed_path": str(folder / "contracts.parquet")})})
    study_frame().to_parquet(config.clean.processed_path, index=False)
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(folder)
        table = report.run(config)
    return folder, config, table


def test_run_writes_every_report(analyzed):
    folder, _, _ = analyzed
    for name in ("calibration_table.csv", "bias_by_category.csv", "bias_by_lifetime.csv",
                 "backtest_ledger.csv", "backtest_rules.csv", "summary.json"):
        assert (folder / "reports" / name).stat().st_size > 0, name


def test_run_finds_the_planted_shape(analyzed):
    _, _, table = analyzed
    below, above = table[table["bucket_high"] <= 0.5], table[table["bucket_low"] >= 0.5]
    assert (below["bias"] < 0).mean() >= 0.8 and (above["bias"] > 0).mean() >= 0.8
    assert table["significant"].any()


def test_the_summary_agrees_with_the_csvs_and_is_strict_json(analyzed):
    folder, config, table = analyzed
    raw = (folder / "reports" / "summary.json").read_text(encoding="utf-8")
    assert "NaN" not in raw and "Infinity" not in raw
    s = json.loads(raw)

    csv = pd.read_csv(folder / "reports" / "calibration_table.csv")
    assert [r["bias"] for r in s["calibration"]] == pytest.approx(csv["bias"].tolist())
    assert [r["bias"] for r in s["calibration"]] == pytest.approx(table["bias"].tolist())
    assert s["data"]["contracts"] == 4000 and s["data"]["events"] == 2000
    assert s["logistic"]["slope"] > 1, "the planted tilt is the favourite-longshot direction"
    assert s["settings"]["bootstrap_reps"] == config.analysis.bootstrap_reps
    assert s["horizon"] is None, "no T-6h table was built, so the horizon check is skipped"
    assert len(s["backtest"]["train_fraction"]) == 5 and len(s["backtest"]["min_net_edge"]) == 6

    ledger = pd.read_csv(folder / "reports" / "backtest_ledger.csv")
    assert len(ledger) > 0, "the planted bias is strong enough to trade"
    assert s["backtest"]["strategy"]["trades"] == len(ledger)
    assert s["backtest"]["strategy"]["total_pnl"] == pytest.approx(ledger["pnl"].sum())
    assert s["backtest"]["equity"]["strategy"][-1][1] == pytest.approx(s["backtest"]["strategy"]["final_equity"])
    assert s["backtest"]["control"]["roi"] < 0 < s["backtest"]["strategy"]["roi"]


def test_the_segment_csvs_carry_one_correction_family_each(analyzed):
    folder, _, _ = analyzed
    category = pd.read_csv(folder / "reports" / "bias_by_category.csv")
    lifetime = pd.read_csv(folder / "reports" / "bias_by_lifetime.csv")
    assert set(category["segment"]) == {"Economics", "Sports"}
    assert lifetime["segment"].nunique() == 4
    for frame in (category, lifetime):
        assert frame.loc[frame["underpowered"], "q_value"].isna().all()
        assert not frame.loc[frame["underpowered"], "significant"].any()


def test_run_is_deterministic(analyzed, tmp_path, monkeypatch):
    folder, config, table = analyzed
    monkeypatch.chdir(tmp_path)
    again = report.run(config)
    pd.testing.assert_frame_equal(again, table)


def test_main_runs_the_configured_study(monkeypatch):
    calls = []
    monkeypatch.setattr(report, "run", lambda: calls.append(True))
    monkeypatch.setattr(report.logging, "basicConfig", lambda **kw: None)
    report.main()
    assert calls == [True]
