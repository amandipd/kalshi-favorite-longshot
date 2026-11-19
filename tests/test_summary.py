"""Tests for kalshi_calibration/analysis/summary.py: the file the figures and the dashboard read."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from kalshi_calibration.analysis import summary
from kalshi_calibration.config import load_config

BASE = load_config()


def test_encompassing_regression_finds_a_noisy_earlier_price_redundant():
    """Built so the early price is the late one plus noise: alone it carries signal, beside the late
    price it should carry almost none, and the late price's weight should stay near 1."""
    rng = np.random.default_rng(7)
    n = 20_000
    z = rng.normal(0, 1.5, n)
    sig = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731
    late = pd.DataFrame({
        "ticker": np.arange(n).astype(str), "event_ticker": np.arange(n).astype(str),
        "implied_price": sig(z + rng.normal(0, 0.05, n)), "outcome": rng.random(n) < sig(z),
    })
    early = pd.DataFrame({"ticker": late["ticker"], "implied_price": sig(z + rng.normal(0, 1.2, n))})
    config = SimpleNamespace(analysis=SimpleNamespace(cluster_on="event_ticker"))

    fit = summary.encompassing_regression(late, early, config)

    assert fit["n"] == n and fit["n_clusters"] == n
    assert 0.3 < fit["early_alone"]["coef"] < 0.85
    assert abs(fit["both"]["early"]["coef"]) < 0.1
    assert fit["both"]["late"]["coef"] == pytest.approx(1.0, abs=0.1)


def test_records_turn_nan_into_null():
    assert summary._records(pd.DataFrame({"a": [1.0, np.nan]})) == [{"a": 1.0}, {"a": None}]


def test_write_summary_refuses_nan(tmp_path):
    with pytest.raises(ValueError):
        summary.write_summary({"x": float("nan")}, tmp_path / "s.json")


def test_horizon_check_is_skipped_when_the_six_hour_table_was_never_built(tmp_path):
    config = BASE.model_copy(update={"clean": BASE.clean.model_copy(
        update={"processed_path": str(tmp_path / "contracts.parquet")})})
    assert summary.horizon_check(pd.DataFrame({"ticker": []}), config) is None


@dataclass(frozen=True)
class Fit:
    slope: float
    slope_ci: tuple[float, float]


def test_build_summary_carries_the_counts_curves_and_split(monkeypatch):
    monkeypatch.setattr(summary, "horizon_check", lambda df, config: None)
    df = pd.DataFrame({
        "close_ts": pd.to_datetime(["2026-01-02", "2026-03-04", "2026-05-06"], utc=True),
        "event_ticker": ["E1", "E1", "E2"], "outcome": [1, 0, 1], "category": ["Sports", "Sports", "Economics"],
    })
    edges = np.round(np.arange(0, 1.0, 0.1), 1)
    table = pd.DataFrame({"bucket_low": edges, "bucket_high": np.round(edges + 0.1, 1),
                          "bias": [-0.01] * 5 + [0.01, -0.01, 0.02, 0.02, 0.01]})
    ledger = pd.DataFrame({"settle_ts": ["2026-04-21T10:00:00Z", "2026-04-21T11:00:00Z", "2026-04-22T10:00:00Z"],
                           "pnl": [0.01, 0.01, -0.02]})
    split = SimpleNamespace(split_ts=pd.Timestamp("2026-04-20 20:08", tz="UTC"), train=[1, 2, 3], test=[4, 5],
                            excluded=1)
    empty = pd.DataFrame({"x": []})

    out = summary.build_summary(
        df, BASE, decomposition={"brier": 0.12}, table=table, logistic=Fit(1.04, (1.02, 1.06)),
        category=empty, lifetime=empty, backtest=(ledger, {"roi": 0.01}, split, empty),
        control=(ledger.assign(pnl=-ledger["pnl"]), {"roi": -0.1}, split, empty),
    )

    assert out["data"]["contracts"] == 3 and out["data"]["events"] == 2
    assert out["data"]["base_rate"] == pytest.approx(2 / 3)
    assert out["data"]["categories"] == {"Sports": 2, "Economics": 1}
    assert out["shape"] == {"below": 5, "below_overpriced": 5, "above": 5, "above_underpriced": 4}
    assert out["backtest"]["split"] == "2026-04-20"
    assert (out["backtest"]["train"], out["backtest"]["test"], out["backtest"]["excluded"]) == (3, 2, 1)
    assert out["backtest"]["equity"]["strategy"] == [["2026-04-21", pytest.approx(1.02)],
                                                     ["2026-04-22", pytest.approx(1.02 * 0.98)]]
    assert out["logistic"] == {"slope": 1.04, "slope_ci": (1.02, 1.06)}
    assert out["horizon"] is None and out["backtest"]["train_fraction"] is None
    json.dumps(out, allow_nan=False)  # what write_summary will do
