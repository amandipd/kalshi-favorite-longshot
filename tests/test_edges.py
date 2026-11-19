"""The error paths and rare branches the other suites leave unexercised.

Each is a promise in a docstring -- an empty input is refused rather than averaged into a NaN, a segment
column with nothing in it is an error, a trading rule with no edge places no bet -- checked once here so a
refactor that drops the guard fails a test instead of shipping a silent NaN.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from kalshi_calibration.analysis import summary
from kalshi_calibration.analysis.calibration import brier_score, logistic_calibration
from kalshi_calibration.analysis.segmentation import segment_calibration
from kalshi_calibration.analysis.statistics import cluster_bootstrap_ci, cluster_robust_se
from kalshi_calibration.clean import load_horizon_trades, parse_raw_to_interim
from kalshi_calibration.ingest import kalshi as kalshi_module
from kalshi_calibration.ingest import trades as trades_module
from kalshi_calibration.ingest.summary import summarize_raw
from kalshi_calibration.ingest.trades import KalshiTradesClient
from kalshi_calibration.ingest.trades_progress import CategoryProgress, HorizonProgress, SeriesProgress
from kalshi_calibration.strategy.backtest import YES, _ledger, time_split
from test_backtest import strategy_config
from test_calibration import frame, make_config
from test_clean import make_config as clean_config
from test_clean import raw_market, write_page, write_trades
from test_ingest_trades import make_config as trades_config
from test_ingest_trades import market, trade, write_market_page

ROOT = Path(__file__).resolve().parent.parent
CONFIG = make_config()


# ------------------------------------------------------------------ empty inputs are refused


def test_a_standard_error_of_nothing_is_refused():
    with pytest.raises(ValueError, match="zero observations"):
        cluster_robust_se(np.array([]), np.array([]))


def test_the_bootstrap_refuses_a_vector_and_zero_replicates():
    with pytest.raises(ValueError, match="2-D"):
        cluster_bootstrap_ci(np.ones(4), np.arange(4), reps=10, seed=0)
    with pytest.raises(ValueError, match="at least 1"):
        cluster_bootstrap_ci(np.ones((4, 1)), np.arange(4), reps=0, seed=0)


def test_scoring_or_fitting_zero_contracts_is_refused():
    empty = frame([], [])
    with pytest.raises(ValueError, match="zero contracts"):
        brier_score(empty)
    with pytest.raises(ValueError, match="zero contracts"):
        logistic_calibration(empty, CONFIG)


def test_a_segment_column_with_nothing_in_it_is_refused():
    df = frame([0.2, 0.8], [0, 1]).assign(segment=[np.nan, np.nan])
    with pytest.raises(ValueError, match="no non-empty segments"):
        segment_calibration(df, "segment", config=CONFIG)


def test_the_encompassing_fit_needs_contracts_priced_at_both_horizons():
    late = pd.DataFrame({"ticker": ["A"], "event_ticker": ["E"], "implied_price": [0.4], "outcome": [1]})
    early = pd.DataFrame({"ticker": ["B"], "implied_price": [0.5]})
    assert summary.encompassing_regression(late, early, CONFIG) is None


@pytest.mark.parametrize("column", ["close_ts", "settle_ts", "implied_price", "outcome"])
def test_the_split_needs_its_columns(column):
    df = pd.DataFrame({"close_ts": ["2026-01-01"], "settle_ts": ["2026-01-01"], "implied_price": [0.5],
                       "outcome": [1]}).drop(columns=column)
    with pytest.raises(KeyError, match=column):
        time_split(df, strategy_config())


def test_the_split_refuses_an_empty_corpus():
    df = pd.DataFrame({"close_ts": [], "settle_ts": [], "implied_price": [], "outcome": []})
    with pytest.raises(ValueError, match="empty"):
        time_split(df, strategy_config())


# ------------------------------------------------------------------ the trading loop's skips


def test_the_ledger_skips_untraded_buckets_degenerate_prices_and_zero_kelly():
    config = strategy_config()
    rules = pd.DataFrame({
        "bucket": [1, 5, 9], "train_bias": [-0.05, 0.0, 0.03], "side": ["no", YES, YES],
        "trade": [False, True, True],
    })
    test = pd.DataFrame({
        "ticker": ["untraded", "no-rule", "zero-edge", "certain", "taken"],
        "implied_price": [0.15, 0.35, 0.55, 1.0, 0.93],
        "outcome": [0, 0, 1, 1, 1],
        "settle_ts": pd.to_datetime(["2026-05-01"] * 5, utc=True),
        "category": "Sports",
    })
    ledger = _ledger(test, rules, config)
    assert list(ledger["ticker"]) == ["taken"]
    assert ledger.loc[0, "side"] == YES and ledger.loc[0, "won"]


# ------------------------------------------------------------------ raw-layer readers


def test_a_market_with_an_unreadable_volume_is_dropped_and_counted(tmp_path):
    write_page(tmp_path / "raw", "Economics", "KXFED", [raw_market("KXFED-1-A", volume="lots")])
    write_trades(tmp_path / "trades", "Economics", "KXFED", [("KXFED-1-A", "0.3")])
    df, log = parse_raw_to_interim(tmp_path / "raw", tmp_path / "trades", tmp_path / "o.parquet",
                                   clean_config(tmp_path))
    assert df.empty and log.reasons == {"unparsable_volume": 1}


def test_trades_for_a_horizon_never_fetched_are_empty(tmp_path):
    assert load_horizon_trades(tmp_path, 6) == {}


def test_a_market_without_a_ticker_is_counted_but_not_as_a_duplicate(tmp_path):
    page = tmp_path / "kalshi" / "Sports" / "S" / "page_0001.json"
    page.parent.mkdir(parents=True)
    page.write_text(json.dumps({"markets": [{"ticker": ""}, {"result": "yes"}, {"ticker": "A"}]}), encoding="utf-8")
    s = summarize_raw(tmp_path)
    assert (s.markets, s.unique_tickers, s.duplicate_tickers) == (3, 1, 0)


def test_both_clients_build_from_the_loaded_config(monkeypatch, tmp_path):
    monkeypatch.setattr(kalshi_module, "get_config", lambda: trades_config(tmp_path))
    monkeypatch.setattr(trades_module, "get_config", lambda: trades_config(tmp_path))
    with kalshi_module.KalshiClient.from_config(raw_dir=tmp_path / "r") as k:
        assert k.venue_dir == tmp_path / "r" / "kalshi"
    with KalshiTradesClient.from_config() as t:
        assert t.raw_dir == tmp_path / "raw" and t.horizon_dir(6).name == "T6h"


def test_the_horizon_pass_flushes_to_disk_every_2000_markets(tmp_path, monkeypatch):
    write_market_page(tmp_path / "raw", "Economics", "KXCPI", [market(f"M{i}") for i in range(2001)])
    synced = []
    monkeypatch.setattr(trades_module.os, "fsync", lambda fd: synced.append(fd))
    client = KalshiTradesClient(trades_config(tmp_path),
                                transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"trades": [trade()]})))
    stats = client.fetch_horizon(1.0)
    assert stats.fetched == 2001 and len(synced) == 1


# ------------------------------------------------------------------ progress rollups


def test_rollups_report_what_is_left_and_the_no_trade_count():
    h = HorizonProgress(horizon_hours=1, series=[SeriesProgress("C", "A", expected=5, done=2, no_trade=1),
                                                 SeriesProgress("C", "B", expected=3, done=3, no_trade=2)])
    assert (h.remaining, h.no_trade) == (3, 3)
    cat = h.by_category()["C"]
    assert (cat.expected, cat.done, cat.remaining, cat.no_trade) == (8, 5, 3, 3)
    assert CategoryProgress(expected=2, done=5).remaining == 0


# ------------------------------------------------------------------ the findings server's command line


def test_the_findings_server_starts_on_the_port_asked_and_stops_cleanly(monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "dashboard"))
    import server

    made = []

    class Stub:
        def __init__(self, address, handler):
            self.server_address = address
            self.closed = False
            made.append(self)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            self.closed = True

    monkeypatch.setattr(server, "ThreadingHTTPServer", Stub)
    server.main(["--port", "9123", "--host", "0.0.0.0"])
    assert made[0].server_address == ("0.0.0.0", 9123) and made[0].closed
    assert "http://localhost:9123" in capsys.readouterr().out
