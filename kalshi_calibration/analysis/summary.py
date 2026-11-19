"""`reports/summary.json`: the key findings in one machine-readable file.

`make analyze` writes it beside the CSVs, from the same objects it prints, so
the figures (`make figures`), the findings dashboard (`dashboard/`) and the
printed report cannot disagree. The only statistics computed here rather than
passed in are the paired horizon tables and the encompassing horizon
regression, which the write-up quotes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from kalshi_calibration.analysis.calibration import OUTCOME_COL, PRICE_COL, calibration_table
from kalshi_calibration.clean import suffixed_path
from kalshi_calibration.config import Config
from kalshi_calibration.strategy.backtest import daily_equity

logger = logging.getLogger(__name__)

SUMMARY_PATH = Path("reports/summary.json")

# The horizon the study's own T-1h pricing is checked against. `python -m
# kalshi_calibration.clean --horizon 6` writes its processed table to the sibling path
# `suffixed_path` derives; without that file the horizon check is skipped.
COMPARISON_HORIZON_HOURS = 6.0


def _records(table: pd.DataFrame) -> list[dict]:
    """Rows as plain JSON values; NaN becomes null rather than an invalid token."""
    return json.loads(table.to_json(orient="records", date_format="iso"))


def _curve(ledger: pd.DataFrame) -> list[list]:
    """[[settlement day, bankroll multiple], ...] for a ledger."""
    equity = daily_equity(ledger)
    return [[str(day), float(value)] for day, value in equity.items()]


def encompassing_regression(
    late: pd.DataFrame, early: pd.DataFrame, config: Config
) -> dict | None:
    """Fit the outcome on both horizons' log-odds, alone and together.

    If the earlier price carried information the later one did not, its
    coefficient would survive with the later price in the model. A coefficient
    that collapses towards zero says the earlier price is a noisier reading of
    the same forecast. Standard errors cluster on the same key as every other
    test in the study.
    """
    merged = late[["ticker", config.analysis.cluster_on, PRICE_COL, OUTCOME_COL]].merge(
        early[["ticker", PRICE_COL]].rename(columns={PRICE_COL: "early_price"}),
        on="ticker",
    )
    if merged.empty:
        return None
    outcome = merged[OUTCOME_COL].to_numpy(dtype=float)
    groups = pd.factorize(merged[config.analysis.cluster_on])[0]

    def logit(column: str) -> np.ndarray:
        p = merged[column].to_numpy(dtype=float)
        return np.log(p / (1.0 - p))

    def fit(*columns: str) -> dict[str, dict[str, float]]:
        design = sm.add_constant(np.column_stack([logit(c) for c in columns]))
        result = sm.Logit(outcome, design).fit(
            cov_type="cluster", cov_kwds={"groups": groups}, disp=0
        )
        return {
            name: {"coef": float(result.params[i + 1]), "se": float(result.bse[i + 1])}
            for i, name in enumerate(columns)
        }

    both = fit(PRICE_COL, "early_price")
    return {
        "n": len(merged),
        "n_clusters": int(groups.max()) + 1,
        "late_alone": fit(PRICE_COL)[PRICE_COL],
        "early_alone": fit("early_price")["early_price"],
        "both": {"late": both[PRICE_COL], "early": both["early_price"]},
    }


def horizon_check(df: pd.DataFrame, config: Config) -> dict | None:
    """Calibration at T-1h and T-6h over the contracts priced at both, and the
    encompassing fit.

    The comparison is only meaningful on a paired sample. Restricting the T-1h
    table to the tickers that also carry a T-6h price stops the two differing
    because of *which contracts survived* rather than when they were priced --
    and attrition to the earlier horizon is uneven across categories, so the
    confound is real.
    """
    path = Path(suffixed_path(config.clean.processed_path, COMPARISON_HORIZON_HOURS))
    if not path.exists():
        logger.warning(
            "event=horizon_check_skipped path=%s hint=run `python -m kalshi_calibration.clean --horizon %g`",
            path, COMPARISON_HORIZON_HOURS,
        )
        return None
    early = pd.read_parquet(path)
    paired = calibration_table(df[df["ticker"].isin(set(early["ticker"]))], config=config)
    comparison = calibration_table(early, config=config)
    return {
        "late_hours": config.clean.price_horizon_hours,
        "early_hours": COMPARISON_HORIZON_HOURS,
        "late": _records(paired),
        "early": _records(comparison),
        "regression": encompassing_regression(df, early, config),
    }


def build_summary(
    df: pd.DataFrame,
    config: Config,
    *,
    decomposition: dict,
    table: pd.DataFrame,
    logistic,
    category: pd.DataFrame,
    lifetime: pd.DataFrame,
    backtest: tuple,
    control: tuple,
    train_fraction: pd.DataFrame | None = None,
    min_net_edge: pd.DataFrame | None = None,
) -> dict:
    """Everything the dashboard shows, from objects `report.run` already built."""
    ledger, metrics, split, rules = backtest
    control_ledger, control_metrics, _, _ = control
    close = pd.to_datetime(df["close_ts"], utc=True)
    below = table[table["bucket_high"] <= 0.5]
    above = table[table["bucket_low"] >= 0.5]
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": {
            "contracts": len(df),
            "events": int(df["event_ticker"].nunique()),
            "first_close": f"{close.min():%Y-%m-%d}",
            "last_close": f"{close.max():%Y-%m-%d}",
            "base_rate": float(df[OUTCOME_COL].mean()),
            "horizon_hours": config.clean.price_horizon_hours,
            "categories": {k: int(v) for k, v in df["category"].value_counts().items()},
        },
        "settings": {
            "n_buckets": config.analysis.n_buckets,
            "bootstrap_reps": config.analysis.bootstrap_reps,
            "fdr_alpha": config.analysis.fdr_alpha,
            "cluster_on": config.analysis.cluster_on,
            "confidence": config.analysis.confidence,
        },
        "brier": decomposition,
        "logistic": asdict(logistic),
        "calibration": _records(table),
        "shape": {
            "below": len(below),
            "below_overpriced": int((below["bias"] < 0).sum()),
            "above": len(above),
            "above_underpriced": int((above["bias"] > 0).sum()),
        },
        "segments": {"category": _records(category), "lifetime": _records(lifetime)},
        "horizon": horizon_check(df, config),
        "backtest": {
            "split": f"{split.split_ts:%Y-%m-%d}",
            "train": len(split.train),
            "test": len(split.test),
            "excluded": split.excluded,
            "kelly_fraction": config.strategy.kelly_fraction,
            "strategy": metrics,
            "control": control_metrics,
            "equity": {"strategy": _curve(ledger), "control": _curve(control_ledger)},
            "rules": _records(rules),
            "train_fraction": None if train_fraction is None else _records(train_fraction),
            "min_net_edge": None if min_net_edge is None else _records(min_net_edge),
        },
    }


def write_summary(summary: dict, path: Path = SUMMARY_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=1, allow_nan=False), encoding="utf-8")
    return path
