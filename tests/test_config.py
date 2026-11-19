"""Tests for kalshi_calibration/config.py: the one place config.yaml is read and validated.

The module's promise is that a typo or an impossible setting fails at load time, loudly, rather than as a
`None` deep inside an ingestion loop. So most of these feed it something wrong and assert it refuses, and
the fuzz tests at the bottom check each validator against an independent statement of its rule over
generated inputs.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from kalshi_calibration import config as config_module
from kalshi_calibration.config import (
    DEFAULT_CONFIG_PATH,
    Config,
    DateRange,
    ReplicationConfig,
    RetryConfig,
    TradesConfig,
    get_config,
    load_config,
)


def raw_config() -> dict:
    """The committed config.yaml as a plain dict, to mutate one key at a time."""
    return yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def write_yaml(tmp_path, data) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


REPLICATION = dict(
    data_dir="data/replication", start=date(2026, 7, 18), end=date(2026, 10, 4), split=date(2026, 8, 24),
    groups=["crypto"], entry_minute=8, favourite_low=0.9, favourite_high=0.999, stake=10.0, slippage=0.004,
    stress_fee_multiplier=2.0, stops=[0.9], rate_limit_per_second=5, workers=4,
)


# ------------------------------------------------------------------ the committed file


def test_the_committed_config_loads():
    cfg = load_config()
    assert cfg.date_range.start == date(2025, 12, 1)
    assert cfg.date_range.end == date(2026, 6, 6)
    assert cfg.ingest.trades.horizons_hours[0] == cfg.clean.price_horizon_hours
    assert cfg.replication is not None and cfg.replication.start < cfg.replication.split < cfg.replication.end


def test_the_committed_config_excludes_subdaily_series_by_frequency():
    assert load_config().ingest.subdaily_frequencies == frozenset({"hourly", "fifteen_min"})


def test_load_config_accepts_a_string_path(tmp_path):
    assert load_config(write_yaml(tmp_path, raw_config())) == load_config()


def test_get_config_is_read_once_and_shared():
    get_config.cache_clear()
    first = get_config()
    assert get_config() is first
    assert first == load_config()


def test_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "absent.yaml")


@pytest.mark.parametrize("section", ["date_range", "retry", "ingest", "clean", "analysis", "strategy"])
def test_a_missing_section_fails_at_load(tmp_path, section):
    data = raw_config()
    del data[section]
    with pytest.raises(ValidationError, match=section):
        load_config(write_yaml(tmp_path, data))


def test_the_replication_section_is_optional(tmp_path):
    data = raw_config()
    del data["replication"]
    assert load_config(write_yaml(tmp_path, data)).replication is None


def test_a_mistyped_value_fails_at_load(tmp_path):
    data = raw_config()
    data["retry"]["max_attempts"] = "five"
    with pytest.raises(ValidationError, match="max_attempts"):
        load_config(write_yaml(tmp_path, data))


def test_an_empty_category_list_is_refused(tmp_path):
    data = raw_config()
    data["categories"] = []
    with pytest.raises(ValidationError, match="categories"):
        load_config(write_yaml(tmp_path, data))


# ------------------------------------------------------------------ validators, by hand


def test_date_range_may_be_a_single_day():
    assert DateRange(start=date(2026, 1, 1), end=date(2026, 1, 1)).end == date(2026, 1, 1)


def test_date_range_end_before_start_is_refused():
    with pytest.raises(ValidationError, match="must be >= start"):
        DateRange(start=date(2026, 1, 2), end=date(2026, 1, 1))


def retry(**overrides) -> RetryConfig:
    settings = dict(max_attempts=5, initial_backoff_seconds=1.0, max_backoff_seconds=60.0, jitter_seconds=1.0,
                    timeout_seconds=30.0)
    settings.update(overrides)
    return RetryConfig(**settings)


def test_retry_max_backoff_below_initial_is_refused():
    with pytest.raises(ValidationError, match="max_backoff_seconds"):
        retry(initial_backoff_seconds=10.0, max_backoff_seconds=5.0)


@pytest.mark.parametrize("field,value", [
    ("max_attempts", 0), ("initial_backoff_seconds", 0.0), ("max_backoff_seconds", 0.0),
    ("jitter_seconds", -0.1), ("timeout_seconds", 0.0),
])
def test_retry_bounds(field, value):
    with pytest.raises(ValidationError, match=field):
        retry(**{field: value})


def test_zero_jitter_is_allowed():
    assert retry(jitter_seconds=0.0).jitter_seconds == 0.0


def test_the_first_horizon_is_the_primary_one():
    assert TradesConfig(trades_dir="t", horizons_hours=[6, 1, 24]).primary_horizon_hours == 6


@pytest.mark.parametrize("horizons,message", [
    ([], "at least 1"), ([0], "> 0"), ([1, -1], "> 0"), ([1, 6, 1], "unique"),
])
def test_bad_horizon_lists_are_refused(horizons, message):
    with pytest.raises(ValidationError, match=message):
        TradesConfig(trades_dir="t", horizons_hours=horizons)


@pytest.mark.parametrize("limit", [0, 1001])
def test_trades_request_limit_bounds(limit):
    with pytest.raises(ValidationError):
        TradesConfig(trades_dir="t", horizons_hours=[1], request_limit=limit)


def test_the_page_limit_is_capped_at_kalshis_maximum(tmp_path):
    data = raw_config()
    data["ingest"]["page_limit"] = 201
    with pytest.raises(ValidationError, match="page_limit"):
        load_config(write_yaml(tmp_path, data))


def test_pricing_at_a_horizon_never_ingested_is_refused(tmp_path):
    data = raw_config()
    data["clean"]["price_horizon_hours"] = 2
    with pytest.raises(ValidationError, match="never ingested"):
        load_config(write_yaml(tmp_path, data))


def test_the_horizon_check_applies_only_to_horizon_pricing(tmp_path):
    data = raw_config()
    data["clean"]["price_horizon_hours"] = 2
    data["clean"]["price_method"] = "last_trade"
    assert load_config(write_yaml(tmp_path, data)).clean.price_horizon_hours == 2


@pytest.mark.parametrize("field,value", [
    ("train_fraction", 0.0), ("train_fraction", 1.0), ("kelly_fraction", 0.0), ("kelly_fraction", 1.5),
    ("max_position_fraction", 0.0), ("max_daily_deployment", 0.0), ("fee_coefficient", -0.01),
    ("min_net_edge", -0.01), ("slippage_per_contract", -0.01),
])
def test_strategy_bounds(tmp_path, field, value):
    data = raw_config()
    data["strategy"][field] = value
    with pytest.raises(ValidationError, match=field):
        load_config(write_yaml(tmp_path, data))


@pytest.mark.parametrize("field,value", [
    ("n_buckets", 1), ("confidence", 1.0), ("confidence", 0.0), ("bootstrap_reps", 99), ("fdr_alpha", 0.0),
    ("segment_n_buckets", 1), ("min_events_per_bucket", 0),
])
def test_analysis_bounds(tmp_path, field, value):
    data = raw_config()
    data["analysis"][field] = value
    with pytest.raises(ValidationError, match=field):
        load_config(write_yaml(tmp_path, data))


def test_replication_needs_start_before_split_before_end():
    with pytest.raises(ValidationError, match="start < split < end"):
        ReplicationConfig(**{**REPLICATION, "split": REPLICATION["end"]})
    with pytest.raises(ValidationError, match="start < split < end"):
        ReplicationConfig(**{**REPLICATION, "split": REPLICATION["start"]})


def test_replication_favourite_range_must_be_ordered():
    with pytest.raises(ValidationError, match="favourite_low is above favourite_high"):
        ReplicationConfig(**{**REPLICATION, "favourite_low": 0.95, "favourite_high": 0.92})


@pytest.mark.parametrize("field,value", [
    ("entry_minute", 0), ("entry_minute", 15), ("favourite_low", 0.5), ("favourite_high", 1.0), ("stake", 0.0),
    ("stress_fee_multiplier", 0.9), ("stops", []), ("groups", []), ("workers", 0), ("rate_limit_per_second", 0),
])
def test_replication_bounds(field, value):
    with pytest.raises(ValidationError, match=field):
        ReplicationConfig(**{**REPLICATION, field: value})


def test_the_default_path_is_the_repo_root_config():
    assert config_module.DEFAULT_CONFIG_PATH.name == "config.yaml"
    assert (config_module.DEFAULT_CONFIG_PATH.parent / "kalshi_calibration" / "config.py").exists()


# ------------------------------------------------------------------ fuzz: each validator against its rule

days = st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 1, 1))


@given(days, days)
def test_fuzz_date_range_accepts_exactly_the_ordered_pairs(start, end):
    if end >= start:
        assert DateRange(start=start, end=end).end == end
    else:
        with pytest.raises(ValidationError):
            DateRange(start=start, end=end)


@given(st.lists(st.floats(min_value=-48, max_value=48, allow_nan=False), max_size=6))
def test_fuzz_horizons_must_be_positive_unique_and_present(horizons):
    valid = bool(horizons) and all(h > 0 for h in horizons) and len(set(horizons)) == len(horizons)
    if valid:
        assert TradesConfig(trades_dir="t", horizons_hours=horizons).primary_horizon_hours == horizons[0]
    else:
        with pytest.raises(ValidationError):
            TradesConfig(trades_dir="t", horizons_hours=horizons)


positive = st.floats(min_value=1e-6, max_value=1e4, allow_nan=False)


@given(positive, positive)
def test_fuzz_retry_backoff_ceiling_is_never_below_its_floor(initial, ceiling):
    if ceiling >= initial:
        assert retry(initial_backoff_seconds=initial, max_backoff_seconds=ceiling).max_backoff_seconds == ceiling
    else:
        with pytest.raises(ValidationError):
            retry(initial_backoff_seconds=initial, max_backoff_seconds=ceiling)


@given(days, st.integers(-30, 30), st.integers(-30, 30))
def test_fuzz_replication_window_must_be_strictly_ordered(start, to_split, to_end):
    split, end = start + timedelta(days=to_split), start + timedelta(days=to_end)
    fields = {**REPLICATION, "start": start, "split": split, "end": end}
    if start < split < end:
        assert ReplicationConfig(**fields).split == split
    else:
        with pytest.raises(ValidationError):
            ReplicationConfig(**fields)


@given(st.floats(0.5001, 0.9999), st.floats(0.5001, 0.9999))
def test_fuzz_replication_favourite_band(low, high):
    fields = {**REPLICATION, "favourite_low": low, "favourite_high": high}
    if low <= high:
        assert ReplicationConfig(**fields).favourite_low == low
    else:
        with pytest.raises(ValidationError):
            ReplicationConfig(**fields)


@given(st.sampled_from([1.0, 6.0, 24.0, 2.0, 0.5]), st.sampled_from(["horizon_trade", "last_trade", "close_price"]))
def test_fuzz_price_horizon_must_have_been_ingested_only_for_horizon_pricing(horizon, method):
    data = raw_config()
    data["clean"]["price_horizon_hours"] = horizon
    data["clean"]["price_method"] = method
    ingested = horizon in data["ingest"]["trades"]["horizons_hours"]
    if method != "horizon_trade" or ingested:
        assert Config.model_validate(data).clean.price_horizon_hours == horizon
    else:
        with pytest.raises(ValidationError, match="never ingested"):
            Config.model_validate(data)
