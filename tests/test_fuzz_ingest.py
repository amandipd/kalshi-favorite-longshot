"""Property-based tests for the ingest layer: pagination, backoff, and resuming an interrupted run.

The ingestion runs for hours against a rate-limited API, so the properties that matter are the ones a long
run leans on: every page is yielded once and in order, no backoff ever exceeds its ceiling, and a run killed
at *any* page resumes into exactly the files an uninterrupted run would have written, without re-fetching
what it already has.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kalshi_calibration.config import RetryConfig
from kalshi_calibration.ingest.base import APIClient, RetryableHTTPError
from kalshi_calibration.ingest.kalshi import KalshiClient
from kalshi_calibration.ingest.trades import horizon_dirname, iter_binary_markets
from kalshi_calibration.ingest.trades_progress import BAR_WIDTH, RateTracker, _bar, expected_by_series
from test_ingest_kalshi import FakeKalshi, make_config


def client_for(handler, retry=None) -> APIClient:
    retry = retry or RetryConfig(max_attempts=3, initial_backoff_seconds=0.01, max_backoff_seconds=0.02,
                                 jitter_seconds=0.0, timeout_seconds=5.0)
    return APIClient("https://example.test", 1e6, retry, transport=httpx.MockTransport(handler))


# ------------------------------------------------------------------ pagination


@given(st.lists(st.lists(st.integers(), max_size=5), min_size=1, max_size=12), st.integers(1, 15) | st.none())
def test_paginate_yields_every_page_once_in_order(pages, max_pages):
    seen_cursors = []

    def handler(request):
        cursor = request.url.params.get("cursor")
        seen_cursors.append(cursor)
        index = 0 if cursor is None else int(cursor)
        nxt = str(index + 1) if index + 1 < len(pages) else ""
        return httpx.Response(200, json={"items": pages[index], "cursor": nxt})

    with client_for(handler) as client:
        got = list(client.paginate("/x", {"limit": 5}, max_pages=max_pages))
    expected = len(pages) if max_pages is None else min(len(pages), max_pages)
    assert [n for n, _ in got] == list(range(1, expected + 1))
    assert [p["items"] for _, p in got] == pages[:expected]
    assert seen_cursors == [None] + [str(i) for i in range(1, expected)]


# ------------------------------------------------------------------ backoff


@settings(max_examples=40)
@given(st.integers(2, 6), st.floats(0.01, 5), st.floats(0.01, 60), st.floats(0, 2),
       st.none() | st.floats(0, 300))
def test_every_backoff_stays_inside_its_schedule(attempts, initial, ceiling, jitter, retry_after):
    ceiling = max(ceiling, initial)
    retry = RetryConfig(max_attempts=attempts, initial_backoff_seconds=initial, max_backoff_seconds=ceiling,
                        jitter_seconds=jitter, timeout_seconds=5.0)
    headers = {} if retry_after is None else {"Retry-After": str(retry_after)}
    sleeps = []
    client = client_for(lambda r: httpx.Response(503, headers=headers), retry)
    client._sleep = sleeps.append
    with pytest.raises(RetryableHTTPError):
        client.get("/x")
    assert len(sleeps) == attempts - 1
    for i, slept in enumerate(sleeps):
        base = min(retry_after if retry_after is not None else initial * 2**i, ceiling)
        assert base - 1e-9 <= slept <= base + jitter + 1e-9
        assert slept <= ceiling + jitter + 1e-9


@given(st.integers(400, 499).filter(lambda s: s != 429))
def test_a_client_error_is_never_retried(status):
    calls = []
    client = client_for(lambda r: calls.append(1) or httpx.Response(status))
    client._sleep = lambda s: pytest.fail("slept on a client error")
    with pytest.raises(httpx.HTTPStatusError):
        client.get("/x")
    assert len(calls) == 1


# ------------------------------------------------------------------ resuming an interrupted run


def page_files(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8")
            for p in sorted(root.rglob("page_*.json"))}


@st.composite
def series_pages(draw):
    """One or two series, each a list of pages of markets settling newest-first inside the window."""
    out = {}
    for name in draw(st.lists(st.sampled_from(["KXA", "KXB"]), min_size=1, max_size=2, unique=True)):
        n_pages = draw(st.integers(1, 5))
        pages, day = [], 200
        for p in range(n_pages):
            size = draw(st.integers(1, 3))
            markets = []
            for m in range(size):
                day -= 1
                markets.append({"ticker": f"{name}-{p}-{m}",
                                "settlement_ts": f"2026-{1 + day // 31 % 5:02d}-{1 + day % 28:02d}T12:00:00Z",
                                "result": "yes"})
            pages.append(markets)
        out[name] = pages
    return out


@settings(max_examples=30)
@given(series_pages(), st.integers(0, 12))
def test_a_run_killed_at_any_page_resumes_into_the_same_files(tmp_path_factory, pages, kill_after):
    catalog = [{"ticker": t, "volume_fp": str(100 - i), "frequency": "daily"} for i, t in enumerate(pages)]
    total_pages = sum(len(v) for v in pages.values())

    whole = tmp_path_factory.mktemp("whole")
    KalshiClient(make_config(whole, top_n=2, page_limit=3),
                 transport=httpx.MockTransport(FakeKalshi(catalog, pages).handler)).fetch_settled_markets()

    resumed = tmp_path_factory.mktemp("resumed")
    config = make_config(resumed, top_n=2, page_limit=3)
    first = FakeKalshi(catalog, pages)

    def dies(request):
        if request.url.path == "/historical/markets" and first.market_requests() >= kill_after:
            raise httpx.ConnectError("killed")
        return first.handler(request)

    try:
        KalshiClient(config, transport=httpx.MockTransport(dies)).fetch_settled_markets()
    except httpx.ConnectError:
        pass
    fetched_before = first.market_requests()

    second = FakeKalshi(catalog, pages)
    stats = KalshiClient(config, transport=httpx.MockTransport(second.handler)).fetch_settled_markets()

    assert page_files(resumed) == page_files(whole)
    assert second.market_requests() == total_pages - fetched_before, "a cached page is never fetched again"
    assert stats.pages_fetched + stats.pages_skipped == total_pages
    assert not list(resumed.rglob("*.tmp"))


# ------------------------------------------------------------------ the horizon pass's inputs


@given(st.floats(0.01, 1000, allow_nan=False), st.floats(0.01, 1000, allow_nan=False))
def test_horizon_directories_are_distinct_for_distinct_horizons(a, b):
    assert (horizon_dirname(a) == horizon_dirname(b)) == (a == b)


markets = st.fixed_dictionaries({
    "ticker": st.sampled_from(["A", "B", "C", "D", "", None]),
    "result": st.sampled_from(["yes", "no", "", "scalar", None]),
    "close_time": st.sampled_from(["2026-03-01T18:00:00Z", "", None]),
})


@settings(max_examples=40)
@given(st.dictionaries(st.tuples(st.sampled_from(["Econ", "Sports"]), st.sampled_from(["S1", "S2"])),
                       st.lists(st.lists(markets, max_size=4), min_size=1, max_size=3), max_size=4))
def test_the_horizon_pass_prices_each_settled_binary_market_once(tmp_path_factory, layout):
    root = tmp_path_factory.mktemp("raw")
    for (category, series), pages in layout.items():
        for i, page in enumerate(pages, 1):
            path = root / "kalshi" / category / series / f"page_{i:04d}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"markets": page}), encoding="utf-8")

    got = list(iter_binary_markets(root))
    tickers = [m["ticker"] for m in got]
    assert len(tickers) == len(set(tickers))
    every = {m["ticker"] for pages in layout.values() for page in pages for m in page
             if m["ticker"] and m["result"] in ("yes", "no") and m["close_time"]}
    assert set(tickers) == every
    assert sum(expected_by_series(root).values()) == len(got)


# ------------------------------------------------------------------ the progress dashboard


@given(st.floats(-2, 3, allow_nan=False), st.integers(1, 60))
def test_the_bar_has_a_fixed_width_and_is_full_only_when_done(fraction, width):
    bar = _bar(fraction, width)
    assert len(bar) == width + 2 and bar[0] == "[" and bar[-1] == "]"
    full = sum(ch in "█#" for ch in bar[1:-1])
    assert (full == width) == (fraction >= 1.0)
    assert len(_bar(fraction)) == BAR_WIDTH + 2


@given(st.lists(st.tuples(st.floats(0.1, 30), st.integers(0, 50)), min_size=1, max_size=40))
def test_the_rate_is_withheld_until_the_samples_span_a_minute_then_matches_the_window(steps):
    tracker = RateTracker(window_seconds=180, min_elapsed_seconds=60)
    now, done, history = 0.0, 0, []
    for gap, delta in steps:
        now += gap
        done += delta
        history.append((now, done))
        rate = tracker.update(done, now)
        kept = list(tracker._samples)
        assert kept[-1] == (now, done)
        if rate is None:
            assert len(kept) < 2 or kept[-1][0] - kept[0][0] < 60
        else:
            (t0, d0), (t1, d1) = kept[0], kept[-1]
            assert t1 - t0 >= 60 and rate == pytest.approx((d1 - d0) / (t1 - t0)) and rate >= 0
