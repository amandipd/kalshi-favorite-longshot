"""Tests for kalshi_calibration/ingest/open_trades.py.

Same shape as tests/test_ingest_trades.py: an `httpx.MockTransport` over a
`tmp_path` layout, no network.

What is different here, and what most of these tests are about: the T-1h pass
asks for one row because `/historical/trades` returns **newest-first**, so the
first row *is* the last trade before the cutoff. This pass wants the opposite
end -- the *first* trade after a market opened -- and newest-first means the
trade we want is the **last** row of the **last** page. So the paging, and
knowing whether we actually reached the bottom, is the whole job. A page that
came back full means there are older trades we have not seen, and the oldest
row we hold is therefore *not* the opening trade; that market is recorded as
incomplete rather than quietly mispriced.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

from kalshi_calibration.config import (
    AnalysisConfig,
    CleanConfig,
    Config,
    DateRange,
    IngestConfig,
    OpenTradesConfig,
    RetryConfig,
    StrategyConfig,
    TradesConfig,
)
from kalshi_calibration.ingest.open_trades import (
    FIRST_TRADE_DIR,
    KalshiOpenTradesClient,
    window_dirname,
)
from kalshi_calibration.ingest.trades import iter_binary_markets

FAST_RETRY = RetryConfig(
    max_attempts=3,
    initial_backoff_seconds=0.01,
    max_backoff_seconds=0.02,
    jitter_seconds=0.0,
    timeout_seconds=5.0,
)

ANALYSIS = AnalysisConfig(
    n_buckets=10,
    confidence=0.95,
    cluster_on="event_ticker",
    bootstrap_reps=100,
    bootstrap_seed=1,
    fdr_alpha=0.05,
    segment_n_buckets=5,
    min_events_per_bucket=30,
)

STRATEGY = StrategyConfig(
    train_fraction=0.6,
    fee_coefficient=0.07,
    fee_ceiling_per_contract=False,
    min_net_edge=0.0,
    kelly_fraction=0.5,
    max_position_fraction=0.02,
    max_daily_deployment=1.0,
    slippage_per_contract=0.0,
)

OPEN_AT = "2026-03-01T12:00:00Z"
CLOSE_AT = "2026-03-01T18:00:00Z"


def make_config(
    tmp_path,
    windows=(1.0,),
    request_limit=3,
    max_pages=3,
    keep=5,
    ladder=(0.25, 1.0, 6.0, 24.0),
    ladder_start=1.0,
) -> Config:
    return Config(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 6, 6)),
        categories=["Economics"],
        kalshi_base_url="https://example.test",
        polymarket_base_url="https://poly.test",
        rate_limit_per_second=1000.0,
        retry=FAST_RETRY,
        ingest=IngestConfig(
            raw_dir=str(tmp_path / "raw"),
            top_n_series_per_category=2,
            page_limit=2,
            subdaily_frequencies=frozenset(),
            trades=TradesConfig(
                trades_dir=str(tmp_path / "trades"),
                horizons_hours=[1.0],
            ),
            open_trades=OpenTradesConfig(
                open_trades_dir=str(tmp_path / "open_trades"),
                window_hours=list(windows),
                request_limit=request_limit,
                max_pages=max_pages,
                keep_trades=keep,
                ladder_hours=list(ladder),
                ladder_start_hours=ladder_start,
            ),
        ),
        analysis=ANALYSIS,
        strategy=STRATEGY,
        clean=CleanConfig(
            price_method="horizon_trade",
            price_horizon_hours=1.0,
            interim_path=str(tmp_path / "interim.parquet"),
            processed_path=str(tmp_path / "processed.parquet"),
        ),
    )


def write_market_page(root: Path, category: str, series: str, markets: list[dict]) -> None:
    path = root / "kalshi" / category / series / "page_0001.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"markets": markets, "cursor": ""}), encoding="utf-8")


def market(ticker: str, result: str = "yes", open_at=OPEN_AT, close: str = CLOSE_AT) -> dict:
    return {
        "ticker": ticker,
        "result": result,
        "open_time": open_at,
        "close_time": close,
    }


def trade(price: str, created: str) -> dict:
    return {
        "ticker": "T",
        "yes_price_dollars": price,
        "no_price_dollars": "0.5000",
        "count_fp": "10.00",
        "created_time": created,
        "trade_id": f"id-{created}",
    }


def make_client(tmp_path, handler, **kw) -> KalshiOpenTradesClient:
    cfg = make_config(tmp_path, **kw)
    return KalshiOpenTradesClient(cfg, transport=httpx.MockTransport(handler))


# -- naming ----------------------------------------------------------------


@pytest.mark.parametrize(
    "hours,expected",
    [(1.0, "OPEN1h"), (6, "OPEN6h"), (24.0, "OPEN24h"), (0.5, "OPEN0.5h")],
)
def test_window_dirname_is_stable(hours, expected):
    # The directory name IS the resume key, so an int and a float spelling of
    # the same window must not produce two directories.
    assert window_dirname(hours) == expected


# -- the shared market iterator now has to carry open_time -----------------


def test_iter_binary_markets_yields_open_time(tmp_path):
    raw = tmp_path / "raw"
    write_market_page(raw, "Economics", "KXFED", [market("A")])

    (got,) = list(iter_binary_markets(raw))

    assert got["open_time"] == OPEN_AT


def test_iter_binary_markets_still_yields_markets_with_no_open_time(tmp_path):
    # The T-1h pass must not lose sample because this pass needs a new field,
    # so a missing open_time is passed through as None and skipped downstream.
    raw = tmp_path / "raw"
    write_market_page(raw, "Economics", "KXFED", [market("A", open_at=None)])

    (got,) = list(iter_binary_markets(raw))

    assert got["ticker"] == "A"
    assert got["open_time"] is None


# -- the window bounds -----------------------------------------------------


def test_request_is_bounded_below_by_open_time_and_above_by_the_window(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["min_ts"] = int(request.url.params["min_ts"])
        seen["max_ts"] = int(request.url.params["max_ts"])
        return httpx.Response(200, json={"trades": [], "cursor": ""})

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler, windows=(6.0,)) as client:
        client.fetch_window(6.0)

    # min_ts is the open itself; max_ts is open + 6h. Both bounds matter: the
    # lower one is what makes the backward walk terminate at the open.
    assert datetime.fromtimestamp(seen["min_ts"], tz=timezone.utc) == datetime(
        2026, 3, 1, 12, 0, tzinfo=timezone.utc
    )
    assert datetime.fromtimestamp(seen["max_ts"], tz=timezone.utc) == datetime(
        2026, 3, 1, 18, 0, tzinfo=timezone.utc
    )


# -- finding the opening trade in a newest-first feed ----------------------


def test_opening_trade_is_the_oldest_row_of_a_short_page(tmp_path):
    # One page, not full => we reached the bottom, so the oldest row is the
    # genuine first trade of the market's life.
    def handler(request):
        return httpx.Response(
            200,
            json={
                "trades": [
                    trade("0.6000", "2026-03-01T12:40:00Z"),
                    trade("0.5500", "2026-03-01T12:10:00Z"),
                ],
                "cursor": "",
            },
        )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler) as client:
        stats = client.fetch_window(1.0)

    out = tmp_path / "open_trades" / "kalshi" / "OPEN1h" / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rec["first_trade"]["yes_price_dollars"] == "0.5500"
    assert rec["complete"] is True
    assert rec["trades_seen"] == 2
    assert stats.fetched == 1
    assert stats.incomplete == 0


def test_a_full_page_is_followed_backwards_until_a_short_one(tmp_path):
    # request_limit=3, so a 3-row page means older trades exist. The walk must
    # keep going, and the opening trade is on the LAST page.
    pages = [
        {
            "trades": [
                trade("0.9000", "2026-03-01T12:50:00Z"),
                trade("0.8000", "2026-03-01T12:40:00Z"),
                trade("0.7000", "2026-03-01T12:30:00Z"),
            ],
            "cursor": "c1",
        },
        {"trades": [trade("0.6000", "2026-03-01T12:05:00Z")], "cursor": ""},
    ]
    calls = []

    def handler(request):
        calls.append(request.url.params.get("cursor"))
        return httpx.Response(200, json=pages[len(calls) - 1])

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler, request_limit=3) as client:
        stats = client.fetch_window(1.0)

    out = tmp_path / "open_trades" / "kalshi" / "OPEN1h" / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert calls == [None, "c1"]
    assert rec["first_trade"]["yes_price_dollars"] == "0.6000"
    assert rec["complete"] is True
    assert rec["trades_seen"] == 4
    assert stats.incomplete == 0


def test_trades_are_stored_oldest_first_and_capped(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "trades": [
                    trade("0.9000", "2026-03-01T12:50:00Z"),
                    trade("0.8000", "2026-03-01T12:40:00Z"),
                ],
                "cursor": "",
            },
        )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler, keep=1) as client:
        client.fetch_window(1.0)

    out = tmp_path / "open_trades" / "kalshi" / "OPEN1h" / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    # keep_trades=1 keeps the OLDEST, because this pass is about the open.
    assert [t["yes_price_dollars"] for t in rec["trades"]] == ["0.8000"]
    assert rec["trades_seen"] == 2


def test_hitting_max_pages_marks_the_market_incomplete(tmp_path):
    # Every page comes back full, so we never reach the open. The oldest row we
    # hold is NOT the opening trade, and the record must say so rather than
    # letting a wrong price into the study.
    def handler(request):
        return httpx.Response(
            200,
            json={
                "trades": [
                    trade("0.9000", "2026-03-01T12:50:00Z"),
                    trade("0.8000", "2026-03-01T12:40:00Z"),
                    trade("0.7000", "2026-03-01T12:30:00Z"),
                ],
                "cursor": "more",
            },
        )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler, request_limit=3, max_pages=2) as client:
        stats = client.fetch_window(1.0)

    out = tmp_path / "open_trades" / "kalshi" / "OPEN1h" / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rec["complete"] is False
    assert rec["first_trade"] is None
    assert stats.incomplete == 1


# -- the exclusions, each counted -----------------------------------------


def test_no_trade_in_the_window_is_an_explicit_null(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"trades": [], "cursor": ""})

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler) as client:
        stats = client.fetch_window(1.0)

    out = tmp_path / "open_trades" / "kalshi" / "OPEN1h" / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    # Recorded, not absent: a re-run must not ask again, and the prereg owes a
    # retention number that can only be counted if the misses are on disk.
    assert rec["first_trade"] is None
    assert rec["trades"] == []
    assert rec["complete"] is True
    assert stats.no_trade == 1
    assert stats.no_trade_per_category["Economics"] == 1


def test_a_market_with_no_open_time_is_skipped_and_counted(tmp_path):
    def handler(request):  # pragma: no cover -- must never be called
        raise AssertionError("should not fetch a market with no open_time")

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A", open_at=None)])
    with make_client(tmp_path, handler) as client:
        stats = client.fetch_window(1.0)

    assert stats.no_open_time == 1
    assert stats.fetched == 0


def test_a_resumed_run_does_not_refetch(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"trades": [trade("0.5000", OPEN_AT)], "cursor": ""})

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A"), market("B")])
    with make_client(tmp_path, handler) as client:
        client.fetch_window(1.0)
        first = len(calls)
        stats = client.fetch_window(1.0)

    assert first == 2
    assert len(calls) == 2, "second run must hit the cache, not the API"
    assert stats.skipped_cached == 2


# -- the climbing ladder ---------------------------------------------------
#
# A fixed window cannot win. Narrow, and most markets have not traded yet;
# wide, and a busy market buries the open under thousands of newer trades the
# page cap cannot walk back through (measured: 39 pages for one ITF tennis
# market at 24h, 80+ for an NCAA game). The ladder climbs instead: it stops at
# the first window holding any trades, and that window is always quiet, because
# trading has only just started there.
#
# Two failure directions, so the ladder moves both ways:
#   nothing in this window      -> widen
#   too busy to reach the open  -> narrow


def ladder_handler(by_window, seen=None):
    """Serve a canned response per window width, in hours."""

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        width = (int(p["max_ts"]) - int(p["min_ts"])) / 3600.0
        if seen is not None:
            seen.append(width)
        return httpx.Response(200, json=by_window.get(width, {"trades": [], "cursor": ""}))

    return handler


def rungs(seen):
    """Distinct windows tried, in the order they were first tried."""
    return list(dict.fromkeys(seen))


def page(trades, cursor=""):
    return {"trades": trades, "cursor": cursor}


BUSY_PAGE = {
    "trades": [
        {
            "ticker": "T",
            "yes_price_dollars": "0.9000",
            "no_price_dollars": "0.1000",
            "count_fp": "10.00",
            "created_time": "2026-03-01T12:55:00Z",
            "trade_id": "b1",
        },
        {
            "ticker": "T",
            "yes_price_dollars": "0.8900",
            "no_price_dollars": "0.1100",
            "count_fp": "10.00",
            "created_time": "2026-03-01T12:54:00Z",
            "trade_id": "b2",
        },
        {
            "ticker": "T",
            "yes_price_dollars": "0.8800",
            "no_price_dollars": "0.1200",
            "count_fp": "10.00",
            "created_time": "2026-03-01T12:53:00Z",
            "trade_id": "b3",
        },
    ],
    "cursor": "more",
}


def test_ladder_stops_at_the_first_window_holding_trades(tmp_path):
    # Starts at 1h and finds trades there, so 6h and 24h are never asked for.
    seen = []
    handler = ladder_handler(
        {
            1.0: page(
                [
                    trade("0.8800", "2026-03-01T12:50:00Z"),
                    trade("0.8500", "2026-03-01T12:20:00Z"),
                ]
            )
        },
        seen,
    )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler) as client:
        stats = client.fetch_ladder()

    out = tmp_path / "open_trades" / "kalshi" / FIRST_TRADE_DIR / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rungs(seen) == [1.0]
    assert rec["first_trade"]["yes_price_dollars"] == "0.8500"
    assert rec["window_hours_used"] == 1.0
    assert rec["complete"] is True
    assert stats.fetched == 1
    assert stats.no_trade == 0


def test_ladder_widens_while_the_market_has_not_traded_yet(tmp_path):
    # Empty at 1h and 6h, trades at 24h. The quiet-market case, and the reason
    # a narrow fixed window throws away most of the sample.
    seen = []
    handler = ladder_handler({24.0: page([trade("0.7000", "2026-03-02T09:00:00Z")])}, seen)

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler) as client:
        client.fetch_ladder()

    out = tmp_path / "open_trades" / "kalshi" / FIRST_TRADE_DIR / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rungs(seen) == [1.0, 6.0, 24.0]
    assert rec["first_trade"]["yes_price_dollars"] == "0.7000"
    assert rec["window_hours_used"] == 24.0


def test_ladder_narrows_when_the_window_is_too_busy_to_reach_the_open(tmp_path):
    # 1h always returns a FULL page with a cursor, so the open is never reached
    # there. Widening would be worse, so the ladder must step DOWN to 0.25h.
    seen = []
    handler = ladder_handler(
        {1.0: BUSY_PAGE, 0.25: page([trade("0.6500", "2026-03-01T12:02:00Z")])},
        seen,
    )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler, request_limit=3, max_pages=2) as client:
        stats = client.fetch_ladder()

    out = tmp_path / "open_trades" / "kalshi" / FIRST_TRADE_DIR / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rungs(seen) == [1.0, 0.25], "must narrow, never widen, when too busy"
    assert rec["first_trade"]["yes_price_dollars"] == "0.6500"
    assert rec["window_hours_used"] == 0.25
    assert rec["complete"] is True
    assert stats.incomplete == 0


def test_record_says_how_long_after_the_open_the_first_trade_landed(tmp_path):
    # The point of storing this: once the delay is on disk, every window in the
    # prereg's sweep is a comparison on it, not another fetch.
    handler = ladder_handler({1.0: page([trade("0.8200", "2026-03-01T12:45:00Z")])})

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler) as client:
        client.fetch_ladder()

    out = tmp_path / "open_trades" / "kalshi" / FIRST_TRADE_DIR / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rec["seconds_after_open"] == 45 * 60


def test_a_market_that_never_traded_is_counted_not_guessed(tmp_path):
    # Empty on every rung. Recorded as an explicit miss, which is the retention
    # number the prereg owes before any edge number.
    seen = []
    handler = ladder_handler({}, seen)

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler) as client:
        stats = client.fetch_ladder()

    out = tmp_path / "open_trades" / "kalshi" / FIRST_TRADE_DIR / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rungs(seen) == [1.0, 6.0, 24.0], "widens to the top before giving up"
    assert rec["first_trade"] is None
    assert rec["seconds_after_open"] is None
    assert rec["complete"] is True
    assert stats.no_trade == 1
    assert stats.no_trade_per_category["Economics"] == 1


def test_busy_on_every_rung_is_incomplete_and_never_priced(tmp_path):
    # Full pages at every width, including the narrowest. We cannot see the
    # open, so there is no price -- a wrong price contaminates the study
    # quietly, a missing one is counted.
    seen = []
    handler = ladder_handler(
        {0.25: BUSY_PAGE, 1.0: BUSY_PAGE, 6.0: BUSY_PAGE, 24.0: BUSY_PAGE}, seen
    )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A")])
    with make_client(tmp_path, handler, request_limit=3, max_pages=2) as client:
        stats = client.fetch_ladder()

    out = tmp_path / "open_trades" / "kalshi" / FIRST_TRADE_DIR / "Economics" / "KXFED.jsonl"
    (rec,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]

    assert rec["first_trade"] is None
    assert rec["complete"] is False
    assert stats.incomplete == 1
    assert stats.no_trade == 0, "busy is not the same exclusion as never traded"


def test_the_ladder_pass_resumes_without_refetching(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(
            200, json=page([trade("0.5000", "2026-03-01T12:30:00Z")])
        )

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A"), market("B")])
    with make_client(tmp_path, handler) as client:
        client.fetch_ladder()
        first = len(calls)
        stats = client.fetch_ladder()

    assert first == 2
    assert len(calls) == 2, "second run must hit the cache, not the API"
    assert stats.skipped_cached == 2


def test_a_market_with_no_open_time_is_skipped_by_the_ladder_too(tmp_path):
    def handler(request):  # pragma: no cover -- must never be called
        raise AssertionError("should not fetch a market with no open_time")

    write_market_page(tmp_path / "raw", "Economics", "KXFED", [market("A", open_at=None)])
    with make_client(tmp_path, handler) as client:
        stats = client.fetch_ladder()

    assert stats.no_open_time == 1
    assert stats.fetched == 0


# -- sampling and sharding -------------------------------------------------
#
# Two separate needs that both live in fetch_ladder.
#
# SAMPLE: the primary test needs about 27,000 markets, not all 143,143, so the
# run is staged. The sample must be drawn at random across everything and be
# reproducible from a seed, because a sample picked by category, by series, or
# by how a market later turned out would leak the answer into the data.
#
# SHARD: the fetch is bound by network round-trips, not by the rate limit, so
# one process idles at about 9 requests a second against a ceiling near 20.
# Two processes halve the wall clock. Shards are assigned by SERIES rather than
# by market, so each worker owns whole output files and two of them never
# append to the same JSONL.


def many_markets(n, series="KXFED"):
    return [market(f"{series}-{i:04d}") for i in range(n)]


def ok_handler(request):
    return httpx.Response(
        200, json={"trades": [trade("0.8500", "2026-03-01T12:30:00Z")], "cursor": ""}
    )


def fetched_tickers(root):
    out = root / "open_trades" / "kalshi" / FIRST_TRADE_DIR
    return sorted(
        json.loads(line)["ticker"]
        for f in out.rglob("*.jsonl")
        for line in f.read_text(encoding="utf-8").splitlines()
    )


def test_sample_fetches_only_that_many_markets(tmp_path):
    write_market_page(tmp_path / "raw", "Economics", "KXFED", many_markets(40))
    with make_client(tmp_path, ok_handler) as client:
        stats = client.fetch_ladder(sample=10, seed=1)

    assert stats.fetched == 10
    assert len(fetched_tickers(tmp_path)) == 10


def test_the_same_seed_draws_the_same_sample(tmp_path):
    write_market_page(tmp_path / "raw", "Economics", "KXFED", many_markets(40))
    with make_client(tmp_path, ok_handler) as client:
        first = client.fetch_ladder(sample=10, seed=7)
    got_a = fetched_tickers(tmp_path)

    shutil.rmtree(tmp_path / "open_trades")
    with make_client(tmp_path, ok_handler) as client:
        client.fetch_ladder(sample=10, seed=7)
    got_b = fetched_tickers(tmp_path)

    assert first.fetched == 10
    assert got_a == got_b, "a seeded sample must be reproducible"


def test_a_different_seed_draws_a_different_sample(tmp_path):
    write_market_page(tmp_path / "raw", "Economics", "KXFED", many_markets(60))
    with make_client(tmp_path, ok_handler) as client:
        client.fetch_ladder(sample=10, seed=1)
    got_a = fetched_tickers(tmp_path)

    shutil.rmtree(tmp_path / "open_trades")
    with make_client(tmp_path, ok_handler) as client:
        client.fetch_ladder(sample=10, seed=2)
    got_b = fetched_tickers(tmp_path)

    assert got_a != got_b


def test_no_sample_means_every_market(tmp_path):
    write_market_page(tmp_path / "raw", "Economics", "KXFED", many_markets(12))
    with make_client(tmp_path, ok_handler) as client:
        stats = client.fetch_ladder()

    assert stats.fetched == 12


def test_a_sample_larger_than_the_universe_is_not_an_error(tmp_path):
    write_market_page(tmp_path / "raw", "Economics", "KXFED", many_markets(5))
    with make_client(tmp_path, ok_handler) as client:
        stats = client.fetch_ladder(sample=500, seed=1)

    assert stats.fetched == 5


def test_shards_split_the_work_with_no_overlap_and_nothing_lost(tmp_path):
    raw = tmp_path / "raw"
    for i, s in enumerate(["KXAAA", "KXBBB", "KXCCC", "KXDDD"]):
        write_market_page(raw, "Economics", s, many_markets(6, series=s))

    seen = {}
    for shard in (0, 1):
        root = tmp_path / f"w{shard}"
        root.mkdir()
        cfg_root = tmp_path  # same raw layer
        with make_client(cfg_root, ok_handler) as client:
            client.venue_dir = root / "kalshi"
            stats = client.fetch_ladder(shard=(shard, 2))
        seen[shard] = sorted(
            json.loads(line)["ticker"]
            for f in (root / "kalshi" / FIRST_TRADE_DIR).rglob("*.jsonl")
            for line in f.read_text(encoding="utf-8").splitlines()
        )
        assert stats.fetched > 0, f"shard {shard} got nothing to do"

    assert not set(seen[0]) & set(seen[1]), "shards must not overlap"
    assert len(set(seen[0]) | set(seen[1])) == 24, "together they must cover everything"


def test_a_shard_owns_whole_series_so_workers_never_share_a_file(tmp_path):
    # This is what makes two processes safe: they append to different files.
    raw = tmp_path / "raw"
    for s in ["KXAAA", "KXBBB", "KXCCC", "KXDDD"]:
        write_market_page(raw, "Economics", s, many_markets(6, series=s))

    files = {}
    for shard in (0, 1):
        root = tmp_path / f"w{shard}"
        root.mkdir()
        with make_client(tmp_path, ok_handler) as client:
            client.venue_dir = root / "kalshi"
            client.fetch_ladder(shard=(shard, 2))
        files[shard] = {
            f.name for f in (root / "kalshi" / FIRST_TRADE_DIR).rglob("*.jsonl")
        }

    assert files[0] and files[1]
    assert not files[0] & files[1], "two shards wrote the same series file"


def test_extending_a_sample_refetches_nothing(tmp_path):
    # The staged plan depends on this: if the small batch is promising, growing
    # it must cost only the new markets.
    calls = []

    def handler(request):
        calls.append(1)
        return ok_handler(request)

    write_market_page(tmp_path / "raw", "Economics", "KXFED", many_markets(40))
    with make_client(tmp_path, handler) as client:
        client.fetch_ladder(sample=10, seed=3)
        after_small = len(calls)
        stats = client.fetch_ladder(sample=25, seed=3)

    assert after_small == 10
    assert stats.skipped_cached >= 10, "the first 10 must come from cache"
    assert len(calls) < 35, "a bigger sample must not refetch the smaller one"
