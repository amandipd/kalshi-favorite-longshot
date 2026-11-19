"""End to end: `make all`, against a fake Kalshi, from the first request to the dashboard.

One module-scoped fixture runs every stage in order on a synthetic market -- ingest, the horizon pass at
T-1h and T-6h, clean at both horizons, analyze, the 15-minute replication fetch and report, the eight
figures and the findings dashboard -- exactly as the Makefile chains them, through each stage's own entry
point. The tests then check each stage's output against the planted answer and against the stage before it.

The fake market is built with known defects, each of which some stage must catch and count:

    scalar settlements          dropped at parse as non_binary_result:scalar
    markets that never traded   dropped at processed as no_volume
    markets closing too early   on disk (the walk keeps a boundary page whole), dropped as close_outside_window
    no trade an hour out        recorded as an explicit null, dropped as no_trade_before_horizon
    no trade six hours out      absent from the T-6h table only, so the horizon check pairs what survives

and a favourite-longshot tilt strong enough that the backtest trades and its control loses.
"""

from __future__ import annotations

import csv
import json
import re
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from kalshi_calibration import clean, figures
from kalshi_calibration.analysis import report as analysis_report
from kalshi_calibration.clean import suffixed_path
from kalshi_calibration.config import (
    AnalysisConfig,
    CleanConfig,
    Config,
    DateRange,
    IngestConfig,
    RetryConfig,
    StrategyConfig,
    TradesConfig,
)
from kalshi_calibration.ingest.kalshi import KalshiClient
from kalshi_calibration.ingest.summary import summarize_raw
from kalshi_calibration.ingest.trades import KalshiTradesClient
from kalshi_calibration.ingest.trades_progress import measure
from kalshi_calibration.replication import report as replication_report
from kalshi_calibration.replication.fetch import ReplicationFetcher
from test_replication import BASE as COMMITTED

pytest.importorskip("pyarrow")

ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc
CATEGORIES = ("Economics", "Sports")
SERIES = {"Economics": ["KXCPI", "KXFED"], "Sports": ["KXNBA", "KXNFL"]}
PER_SERIES = 500
START, END = date(2026, 1, 1), date(2026, 6, 6)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ the fake study market


class FakeStudyMarket:
    """Serves /historical/cutoff, /series, /historical/markets and /historical/trades for the main study."""

    def __init__(self, seed: int = 11):
        rng = np.random.default_rng(seed)
        self.markets: dict[str, dict] = {}
        self.by_series: dict[str, list[dict]] = {}
        self.price: dict[str, float] = {}
        self.no_trade = {1: set(), 6: set()}
        self.planted = {"scalar": 0, "no_volume": 0, "outside": 0}
        self.requests: list[str] = []
        span = (datetime(2026, 6, 5, tzinfo=UTC) - datetime(2026, 1, 2, tzinfo=UTC)).total_seconds()

        for category in CATEGORIES:
            for series in SERIES[category]:
                rows = []
                for i in range(PER_SERIES):
                    ticker = f"{series}-{i // 3:04d}-M{i % 3}"
                    close = datetime(2026, 1, 2, tzinfo=UTC) + timedelta(seconds=float(rng.uniform(0, span)))
                    p = float(rng.uniform(0.04, 0.96))
                    truth = float(np.clip(p + 0.3 * (p - 0.5), 0.01, 0.99))
                    result, volume = ("yes" if rng.random() < truth else "no"), f"{rng.integers(1, 5000)}.00"
                    if i % 97 == 5:
                        result = "scalar"
                        self.planted["scalar"] += 1
                    elif i % 89 == 7:
                        volume = "0.00"
                        self.planted["no_volume"] += 1
                    rows.append(self._market(ticker, series, close, rng, result, volume))
                    self.price[ticker] = p
                # Two markets that closed before the window: the walk writes their page, clean drops them.
                for j in range(2):
                    old = datetime(2025, 11, 20 + j, 12, tzinfo=UTC)
                    ticker = f"{series}-OLD-{j}"
                    rows.append(self._market(ticker, series, old, rng, "yes", "10.00"))
                    self.price[ticker] = 0.5
                    self.planted["outside"] += 1
                rows.sort(key=lambda m: m["settlement_ts"], reverse=True)   # Kalshi's order: newest settled first
                self.by_series[series] = rows
                self.markets.update({m["ticker"]: m for m in rows})

        binary = [t for t, m in self.markets.items() if m["result"] in ("yes", "no")]
        picks = rng.permutation(binary)
        self.no_trade[1] = set(picks[:30])                         # no trade an hour out: none six hours out either
        self.no_trade[6] = self.no_trade[1] | set(picks[30:230])

    @staticmethod
    def _market(ticker, series, close, rng, result, volume):
        lifetime = timedelta(hours=float(rng.lognormal(3.2, 0.8)) + 2)
        return {
            "ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "series_ticker": series,
            "status": "finalized", "result": result, "title": f"{ticker}?", "volume_fp": volume,
            "open_time": iso(close - lifetime), "close_time": iso(close),
            "settlement_ts": iso(close + timedelta(minutes=10)),
            "last_price_dollars": "1.0000" if result == "yes" else "0.0000",
            "yes_bid_dollars": "0.0000", "yes_ask_dollars": "1.0000",
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, request.url.params
        self.requests.append(path)
        if path == "/historical/cutoff":
            return httpx.Response(200, json={"market_settled_ts": "2026-06-06T00:00:00Z"})
        if path == "/series":
            names = SERIES[q["category"]]
            junk = [{"ticker": f"{q['category'][:3].upper()}15M", "frequency": "fifteen_min", "volume_fp": "9e9"}]
            return httpx.Response(200, json={"series": junk + [
                {"ticker": s, "frequency": "daily", "volume_fp": str(1000 - k), "title": s} for k, s in enumerate(names)]})
        if path == "/historical/markets":
            rows = self.by_series[q["series_ticker"]]
            start = int(q.get("cursor") or 0)
            limit = int(q["limit"])
            nxt = start + limit
            return httpx.Response(200, json={"markets": rows[start:nxt], "cursor": str(nxt) if nxt < len(rows) else ""})
        if path == "/historical/trades":
            ticker = q["ticker"]
            close = datetime.fromisoformat(self.markets[ticker]["close_time"].replace("Z", "+00:00"))
            hours = round((close.timestamp() - int(q["max_ts"])) / 3600)
            if ticker in self.no_trade[hours]:
                return httpx.Response(200, json={"trades": [], "cursor": ""})
            p = self.price[ticker]
            if hours == 6:   # six hours out: a noisier reading of the same forecast
                p = float(np.clip(p + 0.08 * np.sin(zlib.crc32(ticker.encode()) % 1000), 0.01, 0.99))
            return httpx.Response(200, json={"trades": [{"ticker": ticker, "yes_price_dollars": f"{p:.4f}",
                                                         "no_price_dollars": f"{1 - p:.4f}", "count_fp": "5.00"}]})
        return httpx.Response(404)


# ------------------------------------------------------------------ the fake 15-minute market


class FakeFifteenMinute:
    """Serves the replication's endpoints: two series, a few hundred windows either side of the cutoff."""

    CUTOFF = datetime(2026, 8, 31, tzinfo=UTC)

    def __init__(self, seed: int = 5):
        rng = np.random.default_rng(seed)
        first = datetime(2026, 7, 18, tzinfo=UTC)
        slots = sorted(set(int(s) for s in rng.integers(0, (78 * 96), 260)))
        self.markets = {"KXBTC15M": [], "KXGOLD15M": []}
        self.quotes: dict[str, list[tuple[float, float, float]]] = {}
        for slot in slots:
            opened = first + timedelta(minutes=15 * slot)
            for series in self.markets:
                ticker = f"{series}-{slot}"
                mid = float(rng.choice([0.05, 0.25, 0.55, 0.8, 0.94, 0.96]))
                path = [float(np.clip(mid + rng.normal(0, 0.01), 0.02, 0.98)) for _ in range(15)]
                self.quotes[ticker] = [(round(p, 2), round(p - 0.01, 2), round(p + 0.01, 2)) for p in path]
                yes = rng.random() < min(0.99, mid + 0.02 if mid > 0.5 else mid - 0.02)
                self.markets[series].append({"ticker": ticker, "open_time": iso(opened),
                                             "result": "yes" if yes else "no", "opened": opened})
        self.markets["KXBTC15M"].append({"ticker": "KXBTC15M-LIVE", "open_time": iso(first), "result": "",
                                         "opened": first})   # never settled: not fetched

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        if path == "/historical/cutoff":
            return httpx.Response(200, json={"market_settled_ts": iso(self.CUTOFF)})
        if path == "/series":
            return httpx.Response(200, json={"series": [
                {"ticker": "KXBTC15M", "frequency": "fifteen_min", "category": "Crypto"},
                {"ticker": "KXGOLD15M", "frequency": "fifteen_min", "category": "Commodities"},
                {"ticker": "KXETHD", "frequency": "hourly", "category": "Crypto"}]})
        if path in ("/historical/markets", "/markets"):
            old = path.startswith("/historical")
            rows = [m for m in self.markets.get(q["series_ticker"], []) if (m["opened"] < self.CUTOFF) == old]
            return httpx.Response(200, json={"markets": [{k: v for k, v in m.items() if k != "opened"} for m in rows],
                                             "cursor": ""})
        if path == "/markets/candlesticks":
            start = int(q["start_ts"])
            return httpx.Response(200, json={"markets": [
                {"market_ticker": t, "candlesticks": self._candles(t, start, live=True)}
                for t in q["market_tickers"].split(",")]})
        match = re.fullmatch(r"/historical/markets/(.+)/candlesticks", path)
        if match:
            return httpx.Response(200, json={"candlesticks": self._candles(match.group(1), int(q["start_ts"]), live=False)})
        return httpx.Response(404)

    def _candles(self, ticker, start, live):
        key = "close_dollars" if live else "close"
        return [{"end_period_ts": start + 60 * k, "price": {key: str(p)}, "yes_bid": {key: str(b)},
                 "yes_ask": {key: str(a)}} for k, (p, b, a) in enumerate(self.quotes[ticker], 1) if k != 3]


# ------------------------------------------------------------------ the run


def pipeline_config(root: Path) -> Config:
    replication = COMMITTED.replication.model_copy(update={
        "data_dir": str(root / "data" / "replication"), "rate_limit_per_second": 1e6, "workers": 2})
    return Config(
        date_range=DateRange(start=START, end=END),
        categories=list(CATEGORIES),
        kalshi_base_url="https://example.test",
        rate_limit_per_second=1e6,
        retry=RetryConfig(max_attempts=2, initial_backoff_seconds=0.01, max_backoff_seconds=0.02,
                          jitter_seconds=0.0, timeout_seconds=5.0),
        ingest=IngestConfig(raw_dir=str(root / "data" / "raw"), top_n_series_per_category=2, page_limit=200,
                            subdaily_frequencies=frozenset({"hourly", "fifteen_min"}),
                            trades=TradesConfig(trades_dir=str(root / "data" / "raw_trades"), horizons_hours=[1, 6])),
        clean=CleanConfig(price_method="horizon_trade", price_horizon_hours=1,
                          interim_path=str(root / "data" / "interim" / "contracts.parquet"),
                          processed_path=str(root / "data" / "processed" / "contracts.parquet")),
        analysis=AnalysisConfig(n_buckets=10, confidence=0.95, cluster_on="event_ticker", bootstrap_reps=200,
                                bootstrap_seed=20260901, fdr_alpha=0.05, segment_n_buckets=5,
                                min_events_per_bucket=30),
        strategy=StrategyConfig(train_fraction=0.6, fee_coefficient=0.07, fee_ceiling_per_contract=False,
                                min_net_edge=0.0, kelly_fraction=0.5, max_position_fraction=0.02,
                                max_daily_deployment=1.0, slippage_per_contract=0.0),
        replication=replication,
    )


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("study")
    config = pipeline_config(root)
    study, fifteen = FakeStudyMarket(), FakeFifteenMinute()
    out: dict = {"root": root, "config": config, "fake": study, "fifteen": fifteen}

    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(root)
        for module in (clean, replication_report):
            mp.setattr(module, "get_config", lambda: config)
            mp.setattr(module.logging, "basicConfig", lambda **kw: None)

        # make ingest, make ingest-trades
        with KalshiClient(config, transport=httpx.MockTransport(study.handler)) as client:
            out["ingest"] = client.fetch_settled_markets()
        with KalshiTradesClient(config, transport=httpx.MockTransport(study.handler)) as client:
            out["trades"] = {s.horizon_hours: s for s in client.fetch_all_horizons()}
        out["raw_summary"] = summarize_raw(config.ingest.raw_dir)
        out["progress"] = measure(config.ingest.raw_dir, config.ingest.trades.trades_dir, [1, 6])

        # make clean, make analyze
        clean.main([])
        clean.main(["--horizon", "6"])
        analysis_report.run(config)

        # make replicate-data, make replicate
        with ReplicationFetcher(config, transport=httpx.MockTransport(fifteen.handler)) as fetcher:
            out["replication_fetch"] = fetcher.run()
        replication_report.main()

        # make figures
        mp.setattr(figures, "FIGURES_DIR", root / "reports" / "figures")
        out["figures"] = figures.build_all()

        # a rerun of the two downloads must fetch nothing
        before = len(study.requests)
        with KalshiClient(config, transport=httpx.MockTransport(study.handler)) as client:
            out["rerun"] = client.fetch_settled_markets()
        with KalshiTradesClient(config, transport=httpx.MockTransport(study.handler)) as client:
            out["rerun_trades"] = client.fetch_all_horizons()
        out["rerun_requests"] = study.requests[before:]
    return out


def summary(run) -> dict:
    return json.loads((run["root"] / "reports" / "summary.json").read_text(encoding="utf-8"))


def replication(run) -> dict:
    return json.loads((run["root"] / "reports" / "replication.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ ingest


def test_ingest_walks_the_top_series_and_skips_the_subdaily_one(run):
    stats, fake = run["ingest"], run["fake"]
    assert stats.series_walked == 4
    assert stats.markets_seen == len(fake.markets)
    selection = json.loads((Path(run["config"].ingest.raw_dir) / "kalshi" / "Sports" / "_series.json").read_text())
    assert [s["ticker"] for s in selection["selected"]] == SERIES["Sports"]
    assert [s["ticker"] for s in selection["excluded_subdaily"]] == ["SPO15M"]


def test_the_raw_layer_holds_every_market_once(run):
    raw = run["raw_summary"]
    assert raw.markets == raw.unique_tickers == len(run["fake"].markets)
    assert raw.duplicate_tickers == 0 and raw.empty_pages == 0
    assert raw.results["scalar"] == run["fake"].planted["scalar"]
    assert raw.settlement_min.year == 2025 and raw.settlement_max <= END
    assert raw.cutoff == {"market_settled_ts": "2026-06-06T00:00:00Z"}


def test_the_horizon_pass_prices_every_binary_market_at_both_horizons(run):
    fake = run["fake"]
    binary = sum(1 for m in fake.markets.values() if m["result"] in ("yes", "no"))
    for hours, stats in run["trades"].items():
        assert stats.markets_total == stats.fetched == binary and stats.errors == 0
        assert stats.no_trade == len(fake.no_trade[hours])
    assert run["progress"].remaining == 0 and all(h.complete for h in run["progress"].horizons)


def test_a_rerun_of_both_downloads_fetches_nothing(run):
    assert run["rerun"].pages_fetched == 0 and run["rerun"].pages_skipped > 0
    assert all(s.fetched == 0 and s.skipped_cached == s.markets_total for s in run["rerun_trades"])
    assert set(run["rerun_requests"]) <= {"/historical/cutoff"}, "only the cutoff is re-read"


# ------------------------------------------------------------------ clean


def in_study(fake, hours) -> set[str]:
    """The tickers that belong in the processed table at a horizon: binary, traded, closed inside the
    window, and with a trade that far out."""
    return {
        t for t, m in fake.markets.items()
        if m["result"] in ("yes", "no") and t not in fake.no_trade[hours] and float(m["volume_fp"]) > 0
        and START <= datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).date() <= END
    }


def test_the_processed_table_is_exactly_the_markets_that_belong_in_the_study(run):
    fake, config = run["fake"], run["config"]
    processed = pd.read_parquet(config.clean.processed_path)
    expected = in_study(fake, 1)
    assert set(processed["ticker"]) == expected and processed["ticker"].is_unique
    assert processed["implied_price"].between(0, 1, inclusive="neither").all()
    row = processed.set_index("ticker").loc[next(iter(expected))]
    assert row["implied_price"] == pytest.approx(round(fake.price[row.name], 4))
    assert row["outcome"] == (1 if fake.markets[row.name]["result"] == "yes" else 0)


def test_the_six_hour_table_is_written_beside_the_primary(run):
    config, fake = run["config"], run["fake"]
    early = pd.read_parquet(suffixed_path(config.clean.processed_path, 6))
    primary = pd.read_parquet(config.clean.processed_path)
    assert set(early["ticker"]) == in_study(fake, 6)
    assert set(early["ticker"]) < set(primary["ticker"])
    assert not np.allclose(early.set_index("ticker")["implied_price"].sort_index(),
                           primary.set_index("ticker").loc[early["ticker"], "implied_price"].sort_index())


# ------------------------------------------------------------------ analyze


def test_the_summary_describes_the_processed_table(run):
    s, processed = summary(run), pd.read_parquet(run["config"].clean.processed_path)
    assert s["data"]["contracts"] == len(processed)
    assert s["data"]["events"] == processed["event_ticker"].nunique()
    assert s["data"]["categories"] == processed["category"].value_counts().to_dict()
    assert s["data"]["base_rate"] == pytest.approx(processed["outcome"].mean())
    assert sum(r["n"] for r in s["calibration"]) == len(processed)


def test_the_planted_tilt_is_found(run):
    s = summary(run)
    assert s["logistic"]["slope"] > 1 and s["logistic"]["slope_ci"][0] > 1
    assert s["shape"]["below_overpriced"] >= s["shape"]["below"] - 1
    assert s["shape"]["above_underpriced"] >= s["shape"]["above"] - 1
    assert any(r["significant"] for r in s["calibration"])


def test_the_horizon_check_pairs_the_contracts_priced_at_both(run):
    h = summary(run)["horizon"]
    early = pd.read_parquet(suffixed_path(run["config"].clean.processed_path, 6))
    assert (h["late_hours"], h["early_hours"]) == (1, 6)
    assert sum(r["n"] for r in h["late"]) == sum(r["n"] for r in h["early"]) == len(early)
    assert h["regression"]["n"] == len(early)
    assert h["regression"]["both"]["late"]["coef"] > h["regression"]["both"]["early"]["coef"]


def test_the_backtest_trades_out_of_sample_and_its_control_loses(run):
    bt = summary(run)["backtest"]
    assert bt["strategy"]["trades"] > 0 and bt["control"]["trades"] > 0
    assert bt["control"]["roi"] < 0 < bt["strategy"]["roi"]
    ledger = pd.read_csv(run["root"] / "reports" / "backtest_ledger.csv")
    assert len(ledger) == bt["strategy"]["trades"]
    split = pd.Timestamp(bt["split"], tz="UTC")
    assert (pd.to_datetime(ledger["settle_ts"], utc=True) >= split).all()


# ------------------------------------------------------------------ replication


def test_the_replication_reads_each_side_of_the_cutoff_once(run):
    counts, fifteen = run["replication_fetch"], run["fifteen"]
    settled = sum(1 for ms in fifteen.markets.values() for m in ms if m["result"])
    assert counts["markets"] == counts["written"] == settled and counts["failed_windows"] == 0
    with (Path(run["config"].replication.data_dir) / "minutes.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == settled and len({r["ticker"] for r in rows}) == settled
    assert all(r["p3"] == r["p2"] for r in rows), "the missing minute 3 carries minute 2 forward"


def test_the_replication_report_covers_both_regimes(run):
    r = replication(run)
    assert r["markets"] == run["replication_fetch"]["written"]
    assert r["favourites"] > 0 and r["regime"]["before"]["bets"] > 0 and r["regime"]["after"]["bets"] > 0
    assert [k["scenario"] for k in r["kelly"]] == ["recorded", "live", "stress"]
    assert r["kelly"][0]["cost"] < r["kelly"][1]["cost"] < r["kelly"][2]["cost"]


# ------------------------------------------------------------------ figures and dashboard


def test_all_eight_figures_are_drawn_from_this_runs_reports(run):
    assert [p.name for p in run["figures"]] == [
        "fig1_calibration.png", "fig2_bias_by_band.png", "fig3_bias_by_segment.png", "fig4_horizon.png",
        "fig5_out_of_sample.png", "fig6_robustness.png", "fig7_replication.png", "fig8_kelly_and_stops.png"]
    for path in run["figures"]:
        assert path.parent == run["root"] / "reports" / "figures"
        with Image.open(path) as im:
            assert im.width >= 1200 and im.height >= 900


def test_the_dashboard_serves_this_runs_reports_and_reads_only_fields_they_carry(run):
    import sys
    sys.path.insert(0, str(ROOT / "dashboard"))
    import server

    sources = {"study": run["root"] / "reports" / "summary.json",
               "replication": run["root"] / "reports" / "replication.json"}
    findings = server.findings(sources)
    assert findings["missing"] == {}
    assert findings["study"] == summary(run) and findings["replication"] == replication(run)

    page = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    script = page[page.index("<script>"):page.rindex("</script>")]
    for var, report in (("S", findings["study"]), ("R", findings["replication"])):
        used = set(re.findall(rf"\b{var}\.(\w+)", script))
        assert used <= set(report), (var, used - set(report))
