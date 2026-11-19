"""Tests for kalshi_calibration/clean.py's command line and the helpers test_clean.py does not reach.

`make clean` runs `python -m kalshi_calibration.clean` and then `python -m kalshi_calibration.clean --horizon 6`. The second run must
write beside the first, never over it: every reported result is computed from the T-1h parquet, and a
sensitivity run that silently replaced it would invalidate them all (ADR 003, decision 2).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from kalshi_calibration import clean
from kalshi_calibration.clean import DropLog, _as_float, interim_to_processed, suffixed_path
from test_clean import make_config, raw_market, write_page, write_trades


def two_horizon_config(tmp_path):
    config = make_config(tmp_path)
    return config.model_copy(update={"ingest": config.ingest.model_copy(update={
        "trades": config.ingest.trades.model_copy(update={"horizons_hours": [1.0, 6.0]})})})


def seed(tmp_path):
    markets = [raw_market(f"KXFED-26MAR-T{i}", result="yes" if i % 2 else "no") for i in range(4)]
    write_page(tmp_path / "raw", "Economics", "KXFED", markets)
    write_trades(tmp_path / "trades", "Economics", "KXFED", [(m["ticker"], "0.3000") for m in markets])
    write_trades(tmp_path / "trades", "Economics", "KXFED", [(m["ticker"], "0.6000") for m in markets[:3]],
                 horizon="T6h")


# ------------------------------------------------------------------ helpers


@pytest.mark.parametrize("value,expected", [("0.4200", 0.42), (3, 3.0), (None, None), ("", None),
                                            ("abc", None), ([1], None)])
def test_as_float_reads_kalshis_decimal_strings(value, expected):
    assert _as_float(value) == expected


@pytest.mark.parametrize("hours,expected", [
    (6, "data/processed/contracts_t6h.parquet"),
    (0.5, "data/processed/contracts_t0.5h.parquet"),
    (24.0, "data/processed/contracts_t24h.parquet"),
])
def test_suffixed_path_names_the_horizon(hours, expected):
    assert suffixed_path("data/processed/contracts.parquet", hours) == str(Path(expected))


def test_droplog_with_nothing_seen():
    assert DropLog().format() == "nothing seen"


def test_droplog_keeps_the_first_example_per_reason():
    log = DropLog()
    log.drop("no_volume", "Sports", "FIRST")
    log.drop("no_volume", "Sports", "SECOND")
    log.drop("no_volume", "Economics")
    assert log.examples == {"no_volume": "FIRST"}
    assert log.by_reason_category["no_volume"] == {"Sports": 2, "Economics": 1}
    assert (log.dropped, log.seen) == (3, 3)


def test_droplog_logs_one_line_per_reason(caplog):
    log = DropLog(kept=5)
    log.drop("a")
    log.drop("b")
    log.drop("b")
    with caplog.at_level(logging.INFO, logger="kalshi_calibration.clean"):
        log.log("step")
    assert "event=step_complete kept=5 dropped=3" in caplog.text
    assert "reason=b count=2" in caplog.text and "reason=a count=1" in caplog.text


def test_args_default_to_none():
    args = clean._parse_args([])
    assert (args.horizon, args.interim_out, args.out) == (None, None, None)


def test_args_parse_the_horizon_as_a_number():
    assert clean._parse_args(["--horizon", "6", "--out", "x.parquet"]).horizon == 6.0


# ------------------------------------------------------------------ interim -> processed edge cases


def test_an_empty_interim_layer_writes_an_empty_processed_one(tmp_path):
    pd.DataFrame().to_parquet(tmp_path / "interim.parquet")
    kept, log = interim_to_processed(tmp_path / "interim.parquet", tmp_path / "out" / "p.parquet",
                                     make_config(tmp_path))
    assert kept.empty and log.seen == 0 and (tmp_path / "out" / "p.parquet").exists()


def test_a_row_without_an_event_ticker_is_a_bug_not_a_drop(tmp_path):
    pd.DataFrame({"ticker": ["A", "B"], "event_ticker": ["E", None], "close_ts": ["2026-03-01"] * 2,
                  "volume": [1.0, 1.0], "category": ["x", "x"]}).to_parquet(tmp_path / "i.parquet")
    with pytest.raises(ValueError, match="cannot be clustered"):
        interim_to_processed(tmp_path / "i.parquet", tmp_path / "p.parquet", make_config(tmp_path))


# ------------------------------------------------------------------ main


def run_main(monkeypatch, config, argv):
    monkeypatch.setattr(clean, "get_config", lambda: config)
    monkeypatch.setattr(clean.logging, "basicConfig", lambda **kw: None)
    clean.main(argv)


def test_main_writes_the_primary_horizon_to_the_configured_paths(tmp_path, monkeypatch, capsys):
    seed(tmp_path)
    config = two_horizon_config(tmp_path)
    run_main(monkeypatch, config, [])
    out = capsys.readouterr().out
    assert "horizon T-1h" in out and "wrote 4 rows (1 events)" in out
    processed = pd.read_parquet(config.clean.processed_path)
    assert len(processed) == 4 and set(processed["implied_price"]) == {0.3}


def test_a_sensitivity_horizon_writes_beside_the_primary_never_over_it(tmp_path, monkeypatch, capsys):
    seed(tmp_path)
    config = two_horizon_config(tmp_path)
    run_main(monkeypatch, config, [])
    run_main(monkeypatch, config, ["--horizon", "6"])

    primary = pd.read_parquet(config.clean.processed_path)
    early = pd.read_parquet(suffixed_path(config.clean.processed_path, 6))
    assert set(primary["implied_price"]) == {0.3} and len(primary) == 4
    assert set(early["implied_price"]) == {0.6} and len(early) == 3
    assert "horizon T-6h" in capsys.readouterr().out
    assert config.clean.price_horizon_hours == 1.0, "main must not mutate the shared config"


def test_the_primary_horizon_named_explicitly_uses_the_primary_paths(tmp_path, monkeypatch):
    seed(tmp_path)
    config = two_horizon_config(tmp_path)
    run_main(monkeypatch, config, ["--horizon", "1"])
    assert (tmp_path / "processed.parquet").exists()
    assert not (tmp_path / "processed_t1h.parquet").exists()


def test_a_horizon_that_was_never_ingested_stops_the_run(tmp_path, monkeypatch):
    seed(tmp_path)
    with pytest.raises(SystemExit, match="never ingested"):
        run_main(monkeypatch, two_horizon_config(tmp_path), ["--horizon", "24"])


def test_explicit_output_paths_win(tmp_path, monkeypatch):
    seed(tmp_path)
    run_main(monkeypatch, two_horizon_config(tmp_path),
             ["--interim-out", str(tmp_path / "i2.parquet"), "--out", str(tmp_path / "p2.parquet")])
    assert len(pd.read_parquet(tmp_path / "p2.parquet")) == 4
    assert (tmp_path / "i2.parquet").exists() and not (tmp_path / "processed.parquet").exists()


def test_main_with_an_empty_raw_layer_reports_zero_rows(tmp_path, monkeypatch, capsys):
    run_main(monkeypatch, make_config(tmp_path), [])
    out = capsys.readouterr().out
    assert "nothing seen" in out and "wrote 0 rows (0 events)" in out
