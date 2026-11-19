"""Unit tests for the ingest layer's small pieces the per-module suites leave out.

The per-module files (test_ingest_base.py, test_ingest_kalshi.py, ...) drive whole runs through a fake
Kalshi. These pin the helpers those runs lean on -- timestamp and Retry-After parsing, the atomic writer,
the run summaries -- plus each module's command-line entry point, which is what `make ingest`,
`make ingest-trades`, `make ingest-summary` and `make trades-progress` actually call.
"""

from __future__ import annotations

import io
import json
import logging
import sys
from datetime import date, datetime, timezone

import httpx
import pytest

from kalshi_calibration.ingest import kalshi as kalshi_module
from kalshi_calibration.ingest import summary as summary_module
from kalshi_calibration.ingest import trades as trades_module
from kalshi_calibration.ingest import trades_progress as progress
from kalshi_calibration.ingest.base import APIClient, RetryableHTTPError, _parse_retry_after, _RateLimiter
from kalshi_calibration.ingest.kalshi import IngestStats, KalshiClient, _parse_ts, _read_json, _write_json
from kalshi_calibration.ingest.summary import CategorySummary, RawSummary, summarize_raw
from kalshi_calibration.ingest.trades import KalshiTradesClient, TradeStats, _load_done
from test_ingest_base import FAST_RETRY as BASE_RETRY
from test_ingest_kalshi import FakeKalshi
from test_ingest_kalshi import make_config as kalshi_config
from test_ingest_trades import make_config as trades_config
from test_ingest_trades import market, trade, write_market_page

UTC = timezone.utc


# ------------------------------------------------------------------ base: Retry-After and errors


def response(headers=None) -> httpx.Response:
    return httpx.Response(429, headers=headers or {}, request=httpx.Request("GET", "https://example.test/x"))


@pytest.mark.parametrize("raw,expected", [("3", 3.0), ("0.25", 0.25), ("0", 0.0)])
def test_retry_after_reads_seconds(raw, expected):
    assert _parse_retry_after(response({"Retry-After": raw})) == expected


def test_retry_after_absent_is_none():
    assert _parse_retry_after(response()) is None


def test_retry_after_as_an_http_date_is_treated_as_absent(caplog):
    """The date form is legal but not what Kalshi sends; a guessed parse could mean sleeping for hours."""
    with caplog.at_level(logging.WARNING):
        assert _parse_retry_after(response({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})) is None
    assert "retry_after_unparsed" in caplog.text


def test_retryable_error_carries_the_status_and_the_wait():
    err = RetryableHTTPError(503, 2.5, "https://example.test/x")
    assert (err.status_code, err.retry_after) == (503, 2.5)
    assert "503" in str(err) and "retry_after=2.5" in str(err) and "https://example.test/x" in str(err)


def test_the_client_closes_its_connection_on_exit():
    with APIClient("https://example.test", 1000.0, BASE_RETRY,
                   transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as client:
        assert client.get("/x") == {}
    assert client._client.is_closed


def test_a_request_sends_its_params_and_headers():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = APIClient("https://example.test/v2", 1000.0, BASE_RETRY, headers={"User-Agent": "study"},
                       transport=httpx.MockTransport(handler))
    assert client.request("GET", "/markets", {"limit": 5}) == {"ok": True}
    assert seen[0].url.params["limit"] == "5" and seen[0].headers["User-Agent"] == "study"


def test_the_rate_limiter_sleeps_only_when_called_too_soon(monkeypatch):
    clock = {"now": 100.0}
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("kalshi_calibration.ingest.base.time.monotonic", lambda: clock["now"])
    monkeypatch.setattr("kalshi_calibration.ingest.base.time.sleep", sleep)
    limiter = _RateLimiter(rate_per_second=4)  # 0.25s apart

    limiter.acquire()          # first call: never waits
    clock["now"] += 0.1
    limiter.acquire()          # 0.1s later: waits the other 0.15s
    clock["now"] += 1.0
    limiter.acquire()          # well after: no wait
    assert sleeps == [pytest.approx(0.15)]


# ------------------------------------------------------------------ kalshi: parsing and writing


@pytest.mark.parametrize("raw,expected", [
    ("2026-03-01T12:00:00Z", datetime(2026, 3, 1, 12, tzinfo=UTC)),
    ("2026-03-01T07:00:00-05:00", datetime(2026, 3, 1, 12, tzinfo=UTC)),
    ("2026-03-01T12:00:00.250Z", datetime(2026, 3, 1, 12, 0, 0, 250000, tzinfo=UTC)),
])
def test_timestamps_parse_to_utc(raw, expected):
    parsed = _parse_ts(raw)
    assert parsed == expected and parsed.tzinfo == UTC


@pytest.mark.parametrize("raw", [None, "", "yesterday", "2026-13-01T00:00:00Z"])
def test_a_missing_or_malformed_timestamp_is_none_not_a_crash(raw):
    assert _parse_ts(raw) is None


def test_write_json_creates_folders_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "a" / "b" / "page_0001.json"
    _write_json(path, {"markets": [1, 2], "cursor": "c"})
    assert _read_json(path) == {"markets": [1, 2], "cursor": "c"}
    assert [p.name for p in path.parent.iterdir()] == ["page_0001.json"]


def test_write_json_replaces_an_existing_file_whole(tmp_path):
    path = tmp_path / "x.json"
    _write_json(path, {"long": "x" * 1000})
    _write_json(path, {"short": 1})
    assert _read_json(path) == {"short": 1}


def test_a_crashed_write_never_leaves_a_half_page_at_the_real_path(tmp_path, monkeypatch):
    """The resume logic trusts any page file that exists, so the rename must be the only way one appears."""
    path = tmp_path / "page_0001.json"

    def fail(src, dst):
        raise OSError("killed mid-rename")

    monkeypatch.setattr(kalshi_module.os, "replace", fail)
    with pytest.raises(OSError):
        _write_json(path, {"markets": []})
    assert not path.exists()


def test_ingest_stats_summary_names_every_counter():
    stats = IngestStats(pages_fetched=3, pages_skipped=2, markets_seen=40, series_walked=5,
                        markets_per_category={"Sports": 40})
    assert stats.summary() == ("series=5 pages_fetched=3 pages_skipped=2 markets=40 "
                               "by_category={'Sports': 40}")


def test_a_series_without_a_ticker_is_skipped_not_walked(tmp_path):
    catalog = [{"ticker": None, "volume_fp": "999", "frequency": "daily"},
               {"ticker": "KXCPI", "volume_fp": "10", "frequency": "monthly"}]
    fake = FakeKalshi(catalog, {"KXCPI": [[{"ticker": "M1", "settlement_ts": "2026-03-01T00:00:00Z"}]]})
    client = KalshiClient(kalshi_config(tmp_path), transport=httpx.MockTransport(fake.handler))
    stats = client.fetch_settled_markets()
    assert stats.series_walked == 1 and stats.markets_seen == 1


def test_a_run_defaults_to_the_configured_window_and_categories(tmp_path):
    fake = FakeKalshi([], {})
    client = KalshiClient(kalshi_config(tmp_path), transport=httpx.MockTransport(fake.handler))
    stats = client.fetch_settled_markets()
    assert stats.markets_per_category == {"Economics": 0}
    assert (tmp_path / "kalshi" / "_cutoff.json").exists()


def test_the_raw_dir_defaults_to_the_configured_one(tmp_path):
    client = KalshiClient(kalshi_config(tmp_path))
    assert client.venue_dir == tmp_path / "kalshi"
    client.close()


def test_kalshi_main_runs_the_configured_ingest_and_prints_the_summary(monkeypatch, capsys, tmp_path):
    fake = FakeKalshi([], {})
    monkeypatch.setattr(kalshi_module, "get_config", lambda: kalshi_config(tmp_path))
    monkeypatch.setattr(KalshiClient, "from_config",
                        classmethod(lambda cls, **kw: cls(kalshi_config(tmp_path),
                                                          transport=httpx.MockTransport(fake.handler))))
    kalshi_module.main()
    assert "series=0 pages_fetched=0" in capsys.readouterr().out


# ------------------------------------------------------------------ trades


def test_trade_stats_summary_reports_the_no_trade_share_of_what_was_fetched():
    stats = TradeStats(horizon_hours=6, markets_total=10, fetched=8, skipped_cached=2, no_trade=2, errors=0)
    assert "horizon=T6h" in stats.summary() and "no_trade=2 (25.0% of fetched)" in stats.summary()


def test_trade_stats_summary_with_nothing_fetched_is_zero_percent():
    assert "(0.0% of fetched)" in TradeStats(horizon_hours=1).summary()


def test_load_done_skips_blank_lines_and_records_without_a_ticker(tmp_path):
    path = tmp_path / "S.jsonl"
    path.write_text('{"ticker": "A"}\n\n   \n{"trade": null}\n{"ticker": "B"}\n', encoding="utf-8")
    assert _load_done(path) == {"A", "B"}


def test_a_market_with_an_unreadable_close_time_is_an_error_not_a_request(tmp_path):
    requests = []
    write_market_page(tmp_path / "raw", "Economics", "KXCPI",
                      [market("A", close="not a time"), market("B")])

    def handler(request):
        requests.append(request.url.params["ticker"])
        return httpx.Response(200, json={"trades": [trade()]})

    client = KalshiTradesClient(trades_config(tmp_path), transport=httpx.MockTransport(handler))
    stats = client.fetch_horizon(1.0)
    assert (stats.errors, stats.fetched) == (1, 1) and requests == ["B"]


def test_fetch_all_horizons_runs_each_configured_horizon_in_order(tmp_path):
    write_market_page(tmp_path / "raw", "Economics", "KXCPI", [market("A")])
    client = KalshiTradesClient(trades_config(tmp_path, horizons=(6.0, 1.0)),
                                transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"trades": []})))
    assert [s.horizon_hours for s in client.fetch_all_horizons()] == [6.0, 1.0]
    assert [s.horizon_hours for s in client.fetch_all_horizons([24.0])] == [24.0]


def test_the_trade_request_asks_for_one_trade_at_or_before_the_cutoff(tmp_path):
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"trades": None})

    client = KalshiTradesClient(trades_config(tmp_path), transport=httpx.MockTransport(handler))
    cutoff = datetime(2026, 3, 1, 17, tzinfo=UTC)
    assert client.fetch_last_trade("T", cutoff) is None
    assert seen == [{"ticker": "T", "limit": "1", "max_ts": str(int(cutoff.timestamp()))}]


def test_trades_main_passes_the_horizon_flags_through(monkeypatch, capsys, tmp_path):
    asked = []

    class Stub:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def fetch_all_horizons(self, horizons):
            asked.append(horizons)
            return [TradeStats(horizon_hours=h) for h in horizons or [1.0]]

    monkeypatch.setattr(KalshiTradesClient, "from_config", classmethod(lambda cls, **kw: Stub()))
    monkeypatch.setattr(sys, "argv", ["trades", "--horizon", "6", "--horizon", "24"])
    trades_module.main()
    assert asked == [[6.0, 24.0]]
    out = capsys.readouterr().out
    assert "horizon=T6h" in out and "horizon=T24h" in out


# ------------------------------------------------------------------ summary


def test_raw_summary_format_lists_anomalies_and_the_cutoff():
    s = RawSummary(venue="kalshi", page_files=2, metadata_files=1, markets=4, unique_tickers=3,
                   duplicate_tickers=1, settlement_min=date(2026, 1, 1), settlement_max=date(2026, 1, 3),
                   unparsed_settlements=2, total_volume=1234.0, empty_pages=1,
                   cutoff={"market_settled_ts": "2026-06-06T00:00:00Z"})
    s.results.update({"yes": 2, "": 2})
    s.categories["Sports"] = CategorySummary(series=1, pages=2, markets=4)
    text = s.format()
    assert "2026-01-01 -> 2026-01-03 (3 days)" in text
    assert "1 duplicate tickers" in text and "2 markets with a missing or unparsable" in text
    assert "1 pages holding zero markets" in text
    assert "(empty -- voided?)" in text and "50.0%" in text
    assert "historical cutoff at ingest time: 2026-06-06T00:00:00Z" in text


def test_raw_summary_without_settlements_has_an_unknown_span_and_no_anomaly_block():
    s = RawSummary(venue="kalshi", page_files=1, markets=0)
    text = s.format()
    assert "settlement span   unknown" in text and "anomalies" not in text and "cutoff" not in text


def test_summarize_raw_tolerates_an_unparsable_volume(tmp_path):
    page = tmp_path / "kalshi" / "Sports" / "S" / "page_0001.json"
    page.parent.mkdir(parents=True)
    page.write_text(json.dumps({"markets": [
        {"ticker": "A", "volume_fp": "n/a", "settlement_ts": "2026-01-01T00:00:00Z", "result": "yes"},
        {"ticker": "B", "volume_fp": "2.5", "settlement_ts": None, "result": "no"},
    ]}), encoding="utf-8")
    s = summarize_raw(tmp_path)
    assert s.total_volume == 2.5 and s.unparsed_settlements == 1 and s.markets == 2


def test_summary_main_reads_the_raw_dir_flag(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["summary", "--raw-dir", str(tmp_path)])
    summary_module.main()
    assert "is empty" in capsys.readouterr().out


def test_summary_main_defaults_to_the_configured_raw_dir(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["summary"])
    monkeypatch.setattr(summary_module, "get_config", lambda: kalshi_config(tmp_path))
    summary_module.main()
    assert "venue=kalshi is empty" in capsys.readouterr().out


# ------------------------------------------------------------------ trades_progress


def test_a_legacy_console_gets_an_ascii_bar(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="ascii"))
    assert not progress._supports_unicode()
    assert progress._bar(0.5, 4) == "[##--]"


def test_a_utf8_console_gets_block_characters(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="utf-8"))
    assert progress._bar(0.5, 4) == "[██░░]"


def test_an_unknown_encoding_falls_back_to_ascii(monkeypatch):
    class Odd:
        encoding = "no-such-codec"

    monkeypatch.setattr(sys, "stdout", Odd())
    assert not progress._supports_unicode()


@pytest.mark.parametrize("rate", [0.0, -1.0])
def test_a_rate_of_zero_or_less_reads_as_stalled(rate):
    assert progress._rate_line(rate, 100).startswith("stalled")


def test_rate_line_states_the_rate_and_eta():
    assert progress._rate_line(10.0, 3600) == "10.0 markets/sec, ETA 6m00s for 3,600 remaining"


@pytest.mark.parametrize("seconds,expected", [(0, "0s"), (59.4, "59s"), (60, "1m00s"), (3599, "59m59s"),
                                              (3600, "1h00m"), (90061, "25h01m")])
def test_durations(seconds, expected):
    assert progress._format_duration(seconds) == expected


def test_an_empty_series_counts_as_done_but_an_empty_horizon_is_not_complete():
    assert progress.SeriesProgress("C", "S", expected=0).fraction == 1.0
    assert progress.CategoryProgress().fraction == 1.0
    h = progress.HorizonProgress(horizon_hours=1)
    assert h.fraction == 1.0 and not h.complete


def test_the_report_truncates_the_incomplete_series_list():
    h = progress.HorizonProgress(horizon_hours=1, series=[
        progress.SeriesProgress("C", f"S{i}", expected=10, done=i) for i in range(4)])
    p = progress.TradesProgress(venue="kalshi", horizons=[h], markets_available=40)
    text = p.format(top_series=2)
    assert "4 series incomplete" in text and "... and 2 more" in text
    assert "series incomplete" not in p.format(top_series=0)


def test_the_overall_rate_line_explains_that_horizons_run_in_turn():
    h = progress.HorizonProgress(horizon_hours=1, series=[progress.SeriesProgress("C", "S", expected=10, done=5)])
    text = progress.TradesProgress(venue="kalshi", horizons=[h], markets_available=10).format(rate=2.0)
    assert "2.0 markets/sec" in text and "each runs in turn" in text


def raw_and_trades(tmp_path, done: int, total: int = 3):
    write_market_page(tmp_path / "raw", "Economics", "KXCPI", [market(f"M{i}") for i in range(total)])
    out = tmp_path / "trades" / "kalshi" / "T1h" / "Economics" / "KXCPI.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps({"ticker": f"M{i}", "trade": None}) + "\n" for i in range(done)),
                   encoding="utf-8")


def test_progress_main_prints_one_report(monkeypatch, capsys, tmp_path):
    raw_and_trades(tmp_path, done=1)
    monkeypatch.setattr(sys, "argv", ["progress", "--raw-dir", str(tmp_path / "raw"),
                                      "--trades-dir", str(tmp_path / "trades"), "--horizon", "1"])
    progress.main()
    out = capsys.readouterr().out
    assert "binary markets in raw layer" in out and "1 / 3" in out


def test_progress_watch_stops_once_every_horizon_is_complete(monkeypatch, capsys, tmp_path):
    raw_and_trades(tmp_path, done=3)
    monkeypatch.setattr(sys, "argv", ["progress", "--raw-dir", str(tmp_path / "raw"),
                                      "--trades-dir", str(tmp_path / "trades"), "--horizon", "1", "--watch", "0"])
    monkeypatch.setattr(progress, "get_config", lambda: trades_config(tmp_path))
    progress.main()
    out = capsys.readouterr().out
    assert "all configured horizons complete" in out and "rate/ETA after 60s" in out


def test_progress_watch_redraws_until_interrupted(monkeypatch, capsys, tmp_path):
    raw_and_trades(tmp_path, done=1)
    ticks = []

    def sleep(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(sys, "argv", ["progress", "--raw-dir", str(tmp_path / "raw"),
                                      "--trades-dir", str(tmp_path / "trades"), "--horizon", "1", "--watch", "7"])
    monkeypatch.setattr(progress.time, "sleep", sleep)
    progress.main()
    assert ticks == [7.0, 7.0]
    assert "stopped watching; the pull is unaffected" in capsys.readouterr().out


def test_progress_watch_shows_the_running_horizons_own_rate_once_it_has_a_minute_of_samples(monkeypatch, capsys,
                                                                                           tmp_path):
    raw_and_trades(tmp_path, done=1)
    clock = iter(range(0, 10_000, 30))     # each rate sample is 30 s after the last: two samples a redraw

    def sleep(seconds):
        if (tmp_path / "frames").exists():
            raise KeyboardInterrupt
        (tmp_path / "frames").touch()
        raw_and_trades(tmp_path, done=2)  # the pull fetched one more market between redraws

    monkeypatch.setattr(sys, "argv", ["progress", "--raw-dir", str(tmp_path / "raw"),
                                      "--trades-dir", str(tmp_path / "trades"), "--horizon", "1", "--watch", "5"])
    monkeypatch.setattr(progress.time, "sleep", sleep)
    monkeypatch.setattr(progress.time, "monotonic", lambda: next(clock))
    progress.main()
    first, second = capsys.readouterr().out.split("\033[H\033[2J")[1:]
    assert "markets/sec" not in first, "one sample is no rate"
    # 1 market in 60 s, for the whole pass and again under the T-1h line, with its own ETA
    rate = "0.0 markets/sec, ETA 1m00s for 1 remaining"
    assert second.count(rate) == 2 and f"in progress\n         {rate}" in second
