"""Unit tests for the parts of kalshi_calibration/replication/ that test_replication.py leaves out.

That file drives a fetch against a fake Kalshi and checks each statistic against a hand computation.
These cover the rest: the empty and boundary cases of each statistic (no bets, a period with nothing in it,
a fill that would cost more than Kalshi's top tick), the fetcher's failure handling, and the two command-line
entry points, `make replicate-data` and `make replicate`.
"""

from __future__ import annotations

import csv
import json
from datetime import date

import httpx
import pytest

from kalshi_calibration.replication import fetch as fetch_module
from kalshi_calibration.replication import report as report_module
from kalshi_calibration.replication.dataset import _num, day_ts, parse_row
from kalshi_calibration.replication.fetch import FIELDS, ReplicationFetcher, group_of, iso_ts, repair_tail, saved_tickers
from kalshi_calibration.replication.stats import (
    MAX_PRICE,
    Bet,
    fill_price,
    held,
    kelly,
    kelly_table,
    order_fee,
    own_quotes,
    periods,
    regime,
    stop_rule,
    stop_table,
)
from test_replication import BASE, SETTINGS, FakeKalshi, bet, make_config, market, run_fetch

K = 0.07


# ------------------------------------------------------------------ fetch helpers


@pytest.mark.parametrize("ticker,category,group", [
    ("KXCRYPTOCOMP15M", "Crypto", "coin race"),
    ("KXSILVER15M", "", "metals"), ("KXPLATINUM15M", "", "metals"), ("KXCOPPER15M", "", "metals"),
    ("KXNATGAS15M", "", "energy"), ("KXOIL15M", "", "energy"),
    ("KXUSDJPY15M", "", "fx"), ("KXGBPUSD15M", "", "fx"),
    ("KXRATE15M", "", "rates"), ("KXINX15M", "", "stock index"), ("KXNDQ15M", "", "stock index"),
    ("KXSOL15M", "Crypto", "crypto"), ("KXWEATHER15M", "Climate", "climate"), ("KXFOO15M", "", "other"),
    ("kxgold15m", "", "metals"),
])
def test_group_of_every_group(ticker, category, group):
    assert group_of(ticker, category) == group


def test_iso_ts_reads_the_z_suffix_as_utc():
    assert iso_ts("2026-07-18T00:15:00Z") == day_ts(date(2026, 7, 18)) + 900
    assert iso_ts("2026-07-18T02:15:00+02:00") == iso_ts("2026-07-18T00:15:00Z")


def test_repair_tail_leaves_a_missing_or_empty_file_alone(tmp_path):
    repair_tail(tmp_path / "absent.csv")
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    repair_tail(empty)
    assert not (tmp_path / "absent.csv").exists() and empty.read_bytes() == b""


def test_repair_tail_on_a_header_cut_mid_line_empties_the_file(tmp_path):
    path = tmp_path / "m.csv"
    path.write_bytes(b"series,tick")
    repair_tail(path)
    assert path.read_bytes() == b""


def test_saved_tickers(tmp_path):
    assert saved_tickers(tmp_path / "absent.csv") == set()
    path = tmp_path / "m.csv"
    path.write_text("series,ticker\nS,A\nS,B\nS,A\n", encoding="utf-8")
    assert saved_tickers(path) == {"A", "B"}


def test_the_fetcher_needs_a_replication_section():
    with pytest.raises(ValueError, match="replication"):
        ReplicationFetcher(BASE.model_copy(update={"replication": None}))


def test_series_come_back_sorted_with_their_group_and_fee_multiplier(tmp_path):
    fake = FakeKalshi()
    fake.series = [{"ticker": "KXZEC15M", "frequency": "fifteen_min", "category": "Crypto", "fee_multiplier": 2},
                   {"ticker": "KXBTC15M", "frequency": "fifteen_min", "category": "Crypto"}]
    with ReplicationFetcher(make_config(tmp_path), transport=httpx.MockTransport(fake.handler)) as f:
        series = f.series()
    assert [s["ticker"] for s in series] == ["KXBTC15M", "KXZEC15M"]
    assert series[1]["fee_multiplier"] == 2 and series[0]["group"] == "crypto"


def test_a_market_listed_on_both_sides_is_read_from_the_live_one(tmp_path):
    fake = FakeKalshi()
    fake.historical["KXBTC15M"].append({"ticker": "BTC-NEW", "open_time": "2026-09-10T14:30:00Z", "result": "no"})
    with ReplicationFetcher(make_config(tmp_path), transport=httpx.MockTransport(fake.handler)) as f:
        found = f.markets([{"ticker": "KXBTC15M"}])
    assert found["BTC-NEW"]["source"] == "live" and found["BTC-OLD"]["source"] == "historical"
    assert "BTC-TOO-EARLY" not in found and "BTC-OPEN" not in found


def test_a_window_with_no_candles_writes_no_row(tmp_path):
    fake = FakeKalshi()
    original = fake.handler

    def handler(request):
        if request.url.path == "/markets/candlesticks":
            return httpx.Response(200, json={"markets": []})
        return original(request)

    with ReplicationFetcher(make_config(tmp_path), transport=httpx.MockTransport(handler)) as f:
        rows = f.window_rows("2026-09-10T14:30:00Z", [{"series": "S", "ticker": "X", "open_time":
                                                       "2026-09-10T14:30:00Z", "resolved_yes": "1",
                                                       "source": "live"}])
    assert rows == []


def test_a_failed_window_is_counted_and_retried_on_the_next_run(tmp_path):
    fake = FakeKalshi()
    original = fake.handler

    def flaky(request):
        if request.url.path == "/markets/candlesticks":
            return httpx.Response(400)          # a client error: not retried, the window fails
        return original(request)

    with ReplicationFetcher(make_config(tmp_path), transport=httpx.MockTransport(flaky)) as f:
        counts = f.run()
    assert counts["failed_windows"] == 1 and counts["written"] == 1   # the historical window still landed

    counts = run_fetch(tmp_path, FakeKalshi())
    assert counts["already_saved"] == 1 and counts["written"] == 2 and counts["failed_windows"] == 0
    with (tmp_path / "minutes.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3 and list(rows[0]) == FIELDS


@pytest.mark.parametrize("failed", [1, 0])
def test_fetch_main_prints_the_counts_and_says_to_rerun_only_after_a_failure(monkeypatch, capsys, failed):
    class Stub:
        def __init__(self, config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def run(self):
            return {"series": 2, "markets": 1500, "already_saved": 0, "written": 1500 - failed, "failed_windows": failed}

    monkeypatch.setattr(fetch_module, "ReplicationFetcher", Stub)
    monkeypatch.setattr(fetch_module.logging, "basicConfig", lambda **kw: None)
    fetch_module.main()
    out = capsys.readouterr().out
    assert "markets 1,500" in out and f"failed windows {failed}" in out
    assert ("run it again" in out) == bool(failed)


# ------------------------------------------------------------------ dataset


def test_num_reads_blank_as_none():
    assert _num("") is None and _num("0.5") == 0.5 and _num("0") == 0.0


def test_day_ts_is_midnight_utc():
    assert day_ts(date(1970, 1, 2)) == 86400


def test_parse_row_indexes_minutes_from_one():
    row = {f: "" for f in FIELDS}
    row.update(series="KXBTC15M", ticker="T", open_time="2026-08-01T10:00:00Z", resolved_yes="0",
               p1="0.5", b15="0.91", a15="0.93")
    m = parse_row(row, "crypto")
    assert m.yes is False and m.group == "crypto" and m.open_ts == iso_ts("2026-08-01T10:00:00Z")
    assert len(m.last) == len(m.bid) == len(m.ask) == 16 and m.last[0] is None
    assert (m.last[1], m.bid[15], m.ask[15], m.last[2]) == (0.5, 0.91, 0.93, None)


# ------------------------------------------------------------------ stats: boundaries


def test_own_quotes_flip_the_book_for_a_no_position():
    assert own_quotes("yes", 0.94, 0.96) == (0.94, 0.96)
    assert own_quotes("no", 0.03, 0.05) == (0.95, 0.97)
    assert own_quotes("no", None, 0.05) is None and own_quotes("yes", 0.9, None) is None


def test_a_fill_never_costs_more_than_the_top_tick():
    assert fill_price(bet(True, ask=0.998), 0.004) == MAX_PRICE
    assert fill_price(bet(True, ask=0.95), 0.004) == pytest.approx(0.954)


def test_held_pays_a_dollar_a_contract_on_a_win_and_nothing_on_a_loss():
    c = 10 / 0.95
    fee = order_fee(c, 0.95, K)
    assert held(bet(True), 0.95, 10.0, K) == pytest.approx(c - 10 - fee)
    assert held(bet(False), 0.95, 10.0, K) == pytest.approx(-10 - fee)
    assert held(bet(False), 0.95, 10.0, K, multiplier=2.0) == pytest.approx(-10 - order_fee(c, 0.95, K, 2.0))


def test_kelly_with_no_bets_is_empty_not_a_division_by_zero():
    assert kelly([], 10.0, 0.0, K) == {"bets": 0, "win": None, "cost": None, "kelly": None}
    assert all(row["kelly"] is None for row in kelly_table([], SETTINGS, K))


def test_kelly_table_labels_each_scenario_from_the_settings():
    rows = kelly_table([bet(True)], SETTINGS, K)
    assert [r["slippage"] for r in rows] == [0.0, SETTINGS.slippage, SETTINGS.slippage]
    assert [r["crypto_fee_multiplier"] for r in rows] == [1.0, 1.0, SETTINGS.stress_fee_multiplier]
    assert "0.4¢" in rows[1]["label"] and "2×" in rows[2]["label"]


def test_an_empty_period_reports_no_loss_rate_rather_than_zero():
    r = regime([], SETTINGS, K)
    assert r["before"] == {"bets": 0, "lost": None, "total": 0, "per_bet_cents": None}


def test_periods_partition_the_bets():
    split = day_ts(SETTINGS.split)
    bets = [bet(True, open_ts=split + d) for d in (-1, 0, 1, -900)]
    p = periods(bets, SETTINGS)
    assert len(p["before"]) == 2 and len(p["after"]) == 2


def test_selling_at_a_zero_bid_pays_no_exit_fee():
    s = SETTINGS.model_copy(update={"slippage": 0.0})
    out = stop_rule([bet(False, bids={9: 0.0})], 0.10, s, K)
    c = 10 / 0.95
    # Sold for nothing and no fee, against a loss that would have paid out nothing either: no change.
    assert out["sold"] == 1 and out["delta"] == pytest.approx(0.0) and out["saved"] == pytest.approx(0.0)
    assert c > 0


def test_stop_table_has_a_row_per_level_with_both_periods():
    split = day_ts(SETTINGS.split)
    rows = stop_table([bet(False, open_ts=split, bids={9: 0.5}), bet(True, open_ts=split - 1)], SETTINGS, K)
    assert [r["level"] for r in rows] == SETTINGS.stops
    for r in rows:
        assert set(r) == {"level", "before", "after"}
        assert r["before"]["sold"] == 0
    by_level = {r["level"]: r["after"]["sold"] for r in rows}
    assert by_level[0.9] == 1 and by_level[0.5] == 1 and by_level[0.3] == 0


def test_a_no_favourite_is_sold_on_its_own_bid():
    """A NO position's bid is 1 - the YES ask, which own_quotes builds when the bets are made."""
    no_bet = Bet(day_ts(date(2026, 9, 1)), "KXBTC15M", "crypto", "no", 0.95, True,
                 (None,) * 9 + (own_quotes("no", 0.80, 0.85),) + (None,) * 5)
    out = stop_rule([no_bet], 0.20, SETTINGS.model_copy(update={"slippage": 0.0}), K)
    assert out["sold"] == 1 and out["sold_won"] == 1


# ------------------------------------------------------------------ report


def test_print_report_lists_every_section(capsys):
    markets = [market(True, last8=0.95, bid=0.94, ask=0.96), market(False, last8=0.30, bid=0.29, ask=0.31),
               market(True, last8=0.97, bid=0.96, ask=0.98, open_ts=day_ts(date(2026, 8, 1)))]
    report_module.print_report(report_module.build(markets, BASE))
    out = capsys.readouterr().out
    assert "3 markets priced at minute 8, 2026-07-18 to 2026-10-03" in out
    assert "Favourites at 90-99.9c: 2" in out
    assert "Recorded prices" in out and "either side of 2026-08-24" in out
    assert out.count("would have won") == 2 * len(SETTINGS.stops)


def both_periods():
    return [market(True, last8=0.95, bid=0.94, ask=0.96),
            market(False, last8=0.96, bid=0.95, ask=0.97, open_ts=day_ts(date(2026, 8, 1)))]


def test_report_main_writes_strict_json(tmp_path, monkeypatch, capsys):
    markets = both_periods()
    monkeypatch.setattr(report_module, "REPORT_PATH", tmp_path / "out" / "replication.json")
    monkeypatch.setattr(report_module, "load_markets", lambda settings: markets)
    monkeypatch.setattr(report_module.logging, "basicConfig", lambda **kw: None)
    report_module.main()
    data = json.loads((tmp_path / "out" / "replication.json").read_text(encoding="utf-8"))
    assert data["markets"] == 2 and data["favourites"] == 2
    assert "wrote" in capsys.readouterr().out


@pytest.mark.xfail(strict=True, raises=TypeError,
                   reason="bug: print_report formats regime's None loss rate for an empty period, so `make "
                          "replicate` crashes before writing replication.json")
def test_a_period_without_favourites_still_prints_and_writes(capsys):
    report_module.print_report(report_module.build([market(True, last8=0.95, bid=0.94, ask=0.96)], BASE))
    assert "before" in capsys.readouterr().out


@pytest.mark.xfail(strict=True, raises=TypeError,
                   reason="bug: print_report formats kelly's None fields when no market had a favourite in range")
def test_a_window_without_any_favourite_still_prints(capsys):
    report_module.print_report(report_module.build([market(True, last8=0.5, bid=0.49, ask=0.52)], BASE))
    assert "Favourites" in capsys.readouterr().out
