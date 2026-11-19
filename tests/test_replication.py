"""Tests for kalshi_calibration/replication/: the fetcher against a fake Kalshi (no network), the loader, and every statistic
against numbers worked by hand."""

from __future__ import annotations

import csv
import json
import math
from datetime import date
from urllib.parse import parse_qs

import httpx
import pytest
from statsmodels.stats.proportion import proportion_confint

from kalshi_calibration.config import RetryConfig, load_config
from kalshi_calibration.replication.dataset import Market, day_ts, load_markets
from kalshi_calibration.replication.fetch import (
    FIELDS,
    ReplicationFetcher,
    candle_close,
    group_of,
    iso_ts,
    minute_row,
    repair_tail,
)
from kalshi_calibration.replication.report import build
from kalshi_calibration.replication.stats import (
    Bet,
    calibration,
    favourite,
    favourites,
    kelly,
    order_fee,
    regime,
    stop_rule,
    wilson,
)

BASE = load_config()
FAST_RETRY = RetryConfig(max_attempts=2, initial_backoff_seconds=0.01, max_backoff_seconds=0.02,
                         jitter_seconds=0.0, timeout_seconds=5.0)
K = 0.07  # Kalshi's fee coefficient


def make_config(tmp_path, **replication):
    rep = BASE.replication.model_copy(update={"data_dir": str(tmp_path), "rate_limit_per_second": 1000.0,
                                              "workers": 1, **replication})
    return BASE.model_copy(update={"kalshi_base_url": "https://example.test", "retry": FAST_RETRY,
                                   "replication": rep})


SETTINGS = BASE.replication


# ------------------------------------------------------------------ fetch: parsing


def test_group_of_maps_tickers_to_the_groups_that_move_together():
    assert group_of("KXBTC15M", "Crypto") == "crypto"
    assert group_of("KXGOLD15M", "Commodities") == "metals"
    assert group_of("KXWTI15M", "Commodities") == "energy"
    assert group_of("KXCRYPTOLEAD15M", "Crypto") == "coin race"
    assert group_of("KXEURUSD15M", "Financials") == "fx"


def test_candle_close_reads_live_and_historical_fields():
    assert candle_close({"close_dollars": "0.9500"}) == 0.95          # live
    assert candle_close({"close": "0.8700", "previous": "0.9"}) == 0.87  # historical
    assert candle_close({"previous_dollars": "0.6100"}) == 0.61        # no trade this minute: the last one
    assert candle_close({"previous": "0.4200"}) == 0.42
    assert candle_close({"close": None, "previous": "0.4"}) is None    # a close that is null stays null
    assert candle_close(None) is None and candle_close({}) is None


def live_candle(open_ts, minute, price, bid, ask):
    return {"end_period_ts": open_ts + 60 * minute, "price": {"close_dollars": str(price)},
            "yes_bid": {"close_dollars": str(bid)}, "yes_ask": {"close_dollars": str(ask)}}


def history_candle(open_ts, minute, price, bid, ask):
    return {"end_period_ts": open_ts + 60 * minute, "price": {"close": str(price), "previous": "0.5"},
            "yes_bid": {"close": str(bid)}, "yes_ask": {"close": str(ask)}}


def test_minute_row_carries_each_quote_forward_over_empty_minutes():
    open_ts = iso_ts("2026-08-01T10:00:00Z")
    market = {"series": "KXBTC15M", "ticker": "T", "open_time": "2026-08-01T10:00:00Z", "resolved_yes": "1"}
    row = minute_row(market, open_ts, [live_candle(open_ts, 1, 0.6, 0.59, 0.61),
                                        live_candle(open_ts, 3, 0.9, 0.89, 0.91)])
    assert (row["p1"], row["b1"], row["a1"]) == (0.6, 0.59, 0.61)
    assert (row["p2"], row["b2"], row["a2"]) == (0.6, 0.59, 0.61)       # minute 2 had no candle
    assert all(row[f"a{k}"] == 0.91 for k in range(3, 16))
    assert row["resolved_yes"] == "1"
    assert minute_row(market, open_ts, []) is None


def test_minute_row_leaves_minutes_before_the_first_quote_blank():
    open_ts = iso_ts("2026-08-01T10:00:00Z")
    market = {"series": "S", "ticker": "T", "open_time": "2026-08-01T10:00:00Z", "resolved_yes": "0"}
    row = minute_row(market, open_ts, [live_candle(open_ts, 5, 0.3, 0.29, 0.31)])
    assert row["p4"] == "" and row["p5"] == 0.3


# ------------------------------------------------------------------ fetch: against a fake Kalshi

WINDOW_OLD = "2026-08-01T10:00:00Z"   # settled before the cutoff: historical side
WINDOW_NEW = "2026-09-10T14:30:00Z"   # after it: live side


class FakeKalshi:
    def __init__(self):
        self.requests: list[str] = []
        self.series = [
            {"ticker": "KXBTC15M", "frequency": "fifteen_min", "category": "Crypto"},
            {"ticker": "KXGOLD15M", "frequency": "fifteen_min", "category": "Commodities"},
            {"ticker": "KXCRYPTOLEAD15M", "frequency": "fifteen_min", "category": "Crypto"},  # coin race: not studied
            {"ticker": "KXBTCD", "frequency": "hourly", "category": "Crypto"},               # not 15-minute
            {"ticker": "KXBTC15MTEST", "frequency": "fifteen_min", "category": "Crypto"},
        ]
        self.historical = {"KXBTC15M": [
            {"ticker": "BTC-OLD", "open_time": WINDOW_OLD, "result": "yes"},
            {"ticker": "BTC-TOO-EARLY", "open_time": "2026-07-01T00:00:00Z", "result": "no"},
        ]}
        self.live = {
            "KXBTC15M": [
                {"ticker": "BTC-NEW", "open_time": WINDOW_NEW, "result": "no"},
                {"ticker": "BTC-OPEN", "open_time": WINDOW_NEW, "result": ""},              # not settled
                {"ticker": "BTC-TOO-LATE", "open_time": "2026-10-05T00:00:00Z", "result": "yes"},
            ],
            "KXGOLD15M": [{"ticker": "GOLD-NEW", "open_time": WINDOW_NEW, "result": "yes"}],
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        self.requests.append(path)
        if path == "/historical/cutoff":
            return httpx.Response(200, json={"market_settled_ts": "2026-08-07T00:00:00Z"})
        if path == "/series":
            return httpx.Response(200, json={"series": self.series})
        if path == "/historical/markets":
            return httpx.Response(200, json={"markets": self.historical.get(q["series_ticker"], []), "cursor": ""})
        if path == "/markets":
            return httpx.Response(200, json={"markets": self.live.get(q["series_ticker"], []), "cursor": ""})
        if path == "/markets/candlesticks":
            o = int(q["start_ts"])
            return httpx.Response(200, json={"markets": [
                {"market_ticker": t, "candlesticks": [live_candle(o, 8, 0.05, 0.04, 0.06)]}
                for t in q["market_tickers"].split(",")]})
        if path.startswith("/historical/markets/") and path.endswith("/candlesticks"):
            o = int(q["start_ts"])
            return httpx.Response(200, json={"candlesticks": [history_candle(o, 8, 0.95, 0.94, 0.96)]})
        return httpx.Response(404)


def run_fetch(tmp_path, fake):
    with ReplicationFetcher(make_config(tmp_path), transport=httpx.MockTransport(fake.handler)) as fetcher:
        return fetcher.run()


def read_rows(path):
    with path.open(newline="") as fh:
        return {r["ticker"]: r for r in csv.DictReader(fh)}


def test_fetch_reads_each_market_from_the_side_of_the_cutoff_that_listed_it(tmp_path):
    fake = FakeKalshi()
    counts = run_fetch(tmp_path, fake)

    rows = read_rows(tmp_path / "minutes.csv")
    assert set(rows) == {"BTC-OLD", "BTC-NEW", "GOLD-NEW"}       # settled, studied, inside the window
    assert rows["BTC-OLD"]["a8"] == "0.96" and rows["BTC-OLD"]["resolved_yes"] == "1"   # historical candle
    assert rows["BTC-NEW"]["a8"] == "0.06" and rows["BTC-NEW"]["resolved_yes"] == "0"   # live batch candle
    assert list(next(iter(rows.values())).keys()) == FIELDS
    assert fake.requests.count("/historical/markets/BTC-OLD/candlesticks") == 1
    assert fake.requests.count("/markets/candlesticks") == 1     # one batch for the live window's two markets
    assert counts == {"series": 2, "markets": 3, "already_saved": 0, "written": 3, "failed_windows": 0}
    catalog = json.loads((tmp_path / "series.json").read_text())
    assert {s["ticker"]: s["group"] for s in catalog["series"]} == {"KXBTC15M": "crypto", "KXGOLD15M": "metals"}
    assert catalog["cutoff"]["market_settled_ts"] == "2026-08-07T00:00:00Z"


def test_a_rerun_fetches_nothing_it_already_has(tmp_path):
    run_fetch(tmp_path, FakeKalshi())
    fake = FakeKalshi()
    counts = run_fetch(tmp_path, fake)
    assert counts["written"] == 0 and counts["already_saved"] == 3
    assert not [p for p in fake.requests if p.endswith("/candlesticks")]
    assert len(read_rows(tmp_path / "minutes.csv")) == 3


def test_a_half_written_last_line_is_dropped_before_resuming(tmp_path):
    path = tmp_path / "minutes.csv"
    path.write_bytes(b"series,ticker\nA,T1\nB,T2-cut-off-mid")
    repair_tail(path)
    assert path.read_bytes() == b"series,ticker\nA,T1\n"
    repair_tail(path)  # an intact file is left alone
    assert path.read_bytes() == b"series,ticker\nA,T1\n"


# ------------------------------------------------------------------ dataset


def write_dataset(folder, rows, series):
    (folder / "series.json").write_text(json.dumps({"series": series}))
    with (folder / "minutes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({**{f: "" for f in FIELDS}, **r})


def test_load_markets_keeps_studied_groups_inside_the_window_once_each(tmp_path):
    series = [{"ticker": "KXBTC15M", "group": "crypto"}, {"ticker": "KXCRYPTOLEAD15M", "group": "coin race"}]
    inside = {"series": "KXBTC15M", "open_time": "2026-08-01T10:00:00Z", "resolved_yes": "1", "a8": "0.96", "b8": "0.94"}
    write_dataset(tmp_path, [
        {**inside, "ticker": "A"},
        {**inside, "ticker": "A", "resolved_yes": "0"},                  # a duplicate: the first copy wins
        {**inside, "ticker": "B", "series": "KXCRYPTOLEAD15M"},          # a group outside the study
        {**inside, "ticker": "C", "open_time": "2026-10-04T00:00:00Z"},  # the window's end is exclusive
        {**inside, "ticker": "D", "open_time": "2026-07-18T00:00:00Z"},  # its start is not
    ], series)
    markets = load_markets(SETTINGS, tmp_path)
    assert [m.ticker for m in markets] == ["D", "A"]                     # in time order
    assert markets[1].yes is True and markets[1].ask[8] == 0.96 and markets[1].bid[7] is None


def test_load_markets_says_what_to_run_when_nothing_was_fetched(tmp_path):
    with pytest.raises(FileNotFoundError, match="make replicate-data"):
        load_markets(SETTINGS, tmp_path)


# ------------------------------------------------------------------ stats


def market(yes, *, last8=None, bid=None, ask=None, open_ts=None, group="crypto", quotes=None):
    """A market with quotes only where given: `quotes` maps minute -> (yes_bid, yes_ask)."""
    q = dict(quotes or {})
    if bid is not None:
        q[8] = (bid, ask)
    bids = (None,) + tuple(q[k][0] if k in q else None for k in range(1, 16))
    asks = (None,) + tuple(q[k][1] if k in q else None for k in range(1, 16))
    last = (None,) + tuple(last8 if k == 8 else None for k in range(1, 16))
    return Market("KXBTC15M", "T", group, open_ts or day_ts(date(2026, 9, 1)), yes, last, bids, asks)


def test_wilson_matches_statsmodels():
    for k, n in ((95, 100), (3, 40), (0, 12), (12, 12)):
        lo, hi = wilson(k, n)
        ref = proportion_confint(k, n, alpha=0.05, method="wilson")
        assert lo == pytest.approx(ref[0], abs=1e-4) and hi == pytest.approx(ref[1], abs=1e-4)
    assert wilson(0, 0) == (0.0, 0.0)


def test_calibration_bands_by_last_trade_and_skips_markets_with_none():
    markets = [market(True, last8=0.05), market(False, last8=0.07), market(True, last8=0.95),
               market(True, last8=1.0), market(False)]
    table = {row["band"]: row for row in calibration(markets, 8)}
    assert set(table) == {0, 9}                                   # a 100c trade folds into the top band
    assert table[0]["n"] == 2 and table[0]["actual"] == 0.5
    assert table[0]["price"] == pytest.approx(0.06) and table[0]["gap"] == pytest.approx(0.44)
    assert table[9]["n"] == 2 and table[9]["actual"] == 1.0


def test_favourite_is_the_side_with_the_higher_ask():
    assert favourite(0.94, 0.96) == ("yes", 0.96)
    assert favourite(0.03, 0.05) == ("no", 0.97)       # NO costs 1 - the YES bid
    assert favourite(0.49, 0.51) is None                 # both sides cost 51c
    assert favourite(None, 0.5) is None


def test_favourites_keep_the_configured_price_range_ends_included():
    markets = [market(True, bid=0.89, ask=0.90), market(True, bid=0.89, ask=0.899),
               market(False, bid=0.001, ask=0.002), market(True, bid=0.99, ask=1.0)]
    bets = favourites(markets, SETTINGS)
    assert [(b.side, b.ask, b.won) for b in bets] == [("yes", 0.90, True), ("no", 0.999, True)]


def test_order_fee_rounds_the_whole_order_up_to_the_cent():
    assert order_fee(10 / 0.95, 0.95, K) == 0.04         # 3.5 cents
    assert order_fee(100, 0.5, K) == 1.75                # exactly 175 cents stays 175
    assert order_fee(10 / 0.95, 0.95, K, multiplier=2.0) == 0.07


def bet(won, ask=0.95, group="crypto", open_ts=None, bids=None):
    quotes = (None,) + tuple((bids[k], bids[k] + 0.02) if bids and k in bids else None for k in range(1, 15))
    return Bet(open_ts or day_ts(date(2026, 9, 1)), "KXBTC15M", group, "yes", ask, won, quotes)


def test_kelly_uses_the_win_rate_against_the_all_in_cost_per_contract():
    bets = [bet(True), bet(True), bet(True), bet(False)]
    k = kelly(bets, stake=10.0, slippage=0.0, coefficient=K)
    cost = 0.95 + 0.04 / (10 / 0.95)
    assert k["win"] == 0.75 and k["cost"] == pytest.approx(cost)
    assert k["kelly"] == pytest.approx((0.75 - cost) / (1 - cost))


def test_kelly_charges_the_fee_on_the_price_actually_paid():
    k = kelly([bet(True)], stake=10.0, slippage=0.004, coefficient=K)
    fill = 0.954
    assert k["cost"] == pytest.approx(fill + order_fee(10 / fill, fill, K) / (10 / fill))


def test_the_stress_fee_multiplier_applies_to_crypto_only():
    metals = kelly([bet(True, group="metals")], 10.0, 0.0, K, crypto_multiplier=2.0)
    crypto = kelly([bet(True, group="crypto")], 10.0, 0.0, K, crypto_multiplier=2.0)
    assert metals["cost"] == pytest.approx(0.95 + 0.04 / (10 / 0.95))
    assert crypto["cost"] == pytest.approx(0.95 + 0.07 / (10 / 0.95))


def test_regime_splits_at_midnight_of_the_split_day():
    split = day_ts(SETTINGS.split)
    bets = [bet(True, open_ts=split - 900), bet(False, open_ts=split), bet(True, open_ts=split + 900)]
    r = regime(bets, SETTINGS, K)
    assert r["before"]["bets"] == 1 and r["after"]["bets"] == 2 and r["after"]["lost"] == 0.5
    fill = 0.95 + SETTINGS.slippage
    c = SETTINGS.stake / fill
    win = c - SETTINGS.stake - order_fee(c, fill, K)
    assert r["before"]["total"] == pytest.approx(win)
    assert r["before"]["per_bet_cents"] == pytest.approx(win * 100)


def test_stop_rule_sells_at_the_first_bid_at_or_under_the_level_after_entry():
    s = SETTINGS.model_copy(update={"slippage": 0.0})
    # Minute 8 is the entry, so its dip doesn't count; minute 9 is above the level; minute 10 sells at 0.88.
    winner = bet(True, bids={8: 0.50, 9: 0.91, 10: 0.88, 11: 0.20})
    loser = bet(False, bids={12: 0.90})
    untouched = bet(False, bids={9: 0.93, 14: 0.91})
    out = stop_rule([winner, loser, untouched], 0.90, s, K)

    c = 10 / 0.95
    won_change = (c * 0.88 - order_fee(c, 0.88, K)) - c          # sold at 0.88 instead of collecting $1 a contract
    lost_change = c * 0.90 - order_fee(c, 0.90, K)                # sold at 0.90 instead of collecting nothing
    assert out["sold"] == 2 and out["sold_won"] == 1
    assert out["gave_up"] == pytest.approx(-won_change)
    assert out["saved"] == pytest.approx(lost_change)
    assert out["delta"] == pytest.approx(won_change + lost_change)


def test_stop_rule_ignores_minutes_without_a_quote_and_never_sells_after_minute_14():
    s = SETTINGS.model_copy(update={"slippage": 0.0})
    quiet = Bet(day_ts(date(2026, 9, 1)), "KXBTC15M", "crypto", "yes", 0.95, False, (None,) * 15)
    assert stop_rule([quiet], 0.90, s, K)["sold"] == 0


# ------------------------------------------------------------------ report


def test_build_reports_every_section_as_plain_json():
    markets = [market(True, last8=0.95, bid=0.94, ask=0.96), market(False, last8=0.30, bid=0.29, ask=0.31),
               market(True, last8=0.97, bid=0.96, ask=0.98, open_ts=day_ts(date(2026, 8, 1)))]
    report = json.loads(json.dumps(build(markets, BASE)))
    assert report["markets"] == 3 and report["favourites"] == 2
    assert [k["scenario"] for k in report["kelly"]] == ["recorded", "live", "stress"]
    assert set(report["regime"]) == {"before", "after"}
    assert [row["level"] for row in report["stops"]] == SETTINGS.stops
    assert report["window"] == {"start": "2026-07-18", "end": "2026-10-03", "split": "2026-08-24"}
    assert not math.isnan(report["kelly"][0]["kelly"])
