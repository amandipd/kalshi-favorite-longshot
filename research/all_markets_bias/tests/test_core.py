"""core.py: the pure rules of the all-markets favourite map, exactly as PREREG.md fixes them.

A trade is [unix ts, YES price in cents, contracts, taker side]. The taker bought the side named: at the YES price
for "yes", at 100 minus it for "no".
"""
import math
import random

import pytest

import core

H = 3600
CLOSE = 1_790_000_000


def tr(ago, yes, side, n=1.0, at=CLOSE - H):
    """A trade `ago` seconds before the moment `at` (default: the 1-hour checkpoint)."""
    return [at - ago, yes, n, side]


# ---------- fee and returns ----------

def test_fee_is_seven_percent_of_p_times_one_minus_p():
    assert core.fee_cents(50, 1) == pytest.approx(1.75)
    assert core.fee_cents(90, 1) == pytest.approx(0.63)
    assert core.fee_cents(99.5, 1) == pytest.approx(0.07 * 99.5 * 0.5 / 100)


def test_fee_scales_with_the_series_multiplier():
    assert core.fee_cents(90, 0.5) == pytest.approx(0.315)
    assert core.fee_cents(90, 0) == 0


def test_profit_per_contract_is_payout_less_price_less_fee():
    assert core.profit_cents(90, True, 1) == pytest.approx(100 - 90 - 0.63)
    assert core.profit_cents(90, False, 1) == pytest.approx(-90 - 0.63)


def test_return_per_dollar_divides_by_price_plus_fee():
    assert core.return_per_dollar(90, True, 1) == pytest.approx((100 - 90.63) / 90.63)
    assert core.return_per_dollar(90, False, 1) == pytest.approx(-1.0)


# ---------- checkpoints ----------

def test_checkpoints_inside_a_30_hour_life():
    got = core.checkpoints(CLOSE - 30 * H, CLOSE)
    assert [label for label, _ in got] == ["1h", "2h", "4h", "8h", "12h", "24h"]
    assert dict(got)["24h"] == CLOSE - 24 * H


def test_a_checkpoint_on_the_open_itself_is_dropped():
    got = core.checkpoints(CLOSE - 24 * H, CLOSE)
    assert "24h" not in dict(got)


def test_a_15_minute_market_gets_only_its_midpoint():
    assert core.checkpoints(CLOSE - 900, CLOSE) == [("half", CLOSE - 450)]


def test_a_90_minute_market_gets_1h_and_its_midpoint():
    got = dict(core.checkpoints(CLOSE - 90 * 60, CLOSE))
    assert set(got) == {"1h", "half"}
    assert got["half"] == CLOSE - 45 * 60


def test_a_year_long_market_gets_all_eleven():
    got = core.checkpoints(CLOSE - 400 * 24 * H, CLOSE)
    assert [label for label, _ in got] == ["1h", "2h", "4h", "8h", "12h", "24h", "2d", "3d", "7d", "14d", "30d"]


# ---------- favourite and entry price ----------

def test_yes_favourite_bought_by_a_yes_buyer():
    e = core.entry_at([tr(600, 85, "yes")], CLOSE - H)
    assert e["side"] == "yes" and e["price"] == 85 and e["age"] == 600


def test_no_favourite_is_priced_at_100_minus_the_yes_price():
    e = core.entry_at([tr(900, 14, "yes"), tr(300, 13, "no")], CLOSE - H)
    assert e["side"] == "no" and e["price"] == 87


def test_entry_is_the_last_price_a_favourite_buyer_paid_not_the_last_trade():
    # The last trade is a No buyer at Yes 85 (they paid 15c). The favourite is Yes; its buyer last paid 84.
    e = core.entry_at([tr(1200, 84, "yes"), tr(60, 85, "no")], CLOSE - H)
    assert e["side"] == "yes" and e["price"] == 84 and e["age"] == 1200


def test_a_favourite_buy_over_60_minutes_old_is_no_bet():
    assert core.entry_at([tr(3601, 85, "yes"), tr(60, 85, "no")], CLOSE - H) is None


def test_a_buy_exactly_60_minutes_old_still_counts():
    assert core.entry_at([tr(3600, 85, "yes")], CLOSE - H)["price"] == 85


def test_a_last_trade_at_exactly_50_is_no_bet():
    assert core.entry_at([tr(600, 70, "yes"), tr(60, 50, "yes")], CLOSE - H) is None


def test_trades_after_the_checkpoint_are_ignored():
    trades = [tr(600, 85, "yes"), tr(-60, 10, "no")]
    e = core.entry_at(trades, CLOSE - H)
    assert e["side"] == "yes" and e["price"] == 85


def test_a_trade_on_the_checkpoint_itself_counts():
    assert core.entry_at([tr(0, 91, "yes")], CLOSE - H)["price"] == 91


def test_no_trades_is_no_bet():
    assert core.entry_at([], CLOSE - H) is None


def test_input_order_does_not_matter():
    trades = [tr(60, 85, "no"), tr(1200, 84, "yes"), tr(2400, 80, "yes")]
    assert core.entry_at(trades, CLOSE - H) == core.entry_at(list(reversed(trades)), CLOSE - H)


def test_tenths_of_a_cent_survive():
    e = core.entry_at([tr(60, 0.4, "no")], CLOSE - H)
    assert e["side"] == "no" and e["price"] == pytest.approx(99.6)


def test_money_near_entry_counts_favourite_buyers_up_to_1c_over_the_entry_in_the_last_hour():
    trades = [
        tr(3700, 85, "yes", 100),   # too old
        tr(3000, 86, "yes", 10),    # 1c over the entry: counts
        tr(2000, 87, "yes", 10),    # 2c over: no
        tr(1000, 85, "no", 50),     # a No buyer: no
        tr(500, 85, "yes", 20),     # the entry itself
    ]
    e = core.entry_at(trades, CLOSE - H)
    assert e["price"] == 85
    assert e["money_near"] == pytest.approx(10 * 0.86 + 20 * 0.85)


# ---------- parsing a Kalshi trade ----------

def test_parse_trade_reads_dollar_strings():
    raw = {"created_time": "2026-10-20T05:59:24.543975Z", "yes_price_dollars": "0.9990", "count_fp": "11.00",
           "taker_side": "no"}
    ts, yes, n, side = core.parse_trade(raw)
    assert ts == pytest.approx(1792475964.543975)
    assert yes == pytest.approx(99.9) and n == 11 and side == "no"


def test_parse_trade_reads_the_old_integer_fields():
    raw = {"created_time": "2026-03-01T21:51:52Z", "yes_price": 1, "count": 93, "taker_side": "yes"}
    assert core.parse_trade(raw)[1:] == [1.0, 93.0, "yes"]


# ---------- bands, halves ----------

@pytest.mark.parametrize("price,band", [
    (50.5, "50-60"), (69.9, "60-70"), (70, "70-80"), (79.99, "70-80"), (80, "80-90"), (90, "90-95"),
    (94.9, "90-95"), (95, "95-99"), (98.9, "95-99"), (99, "99+"), (99.9, "99+"), (49, None),
])
def test_band_of(price, band):
    assert core.band_of(price) == band


def test_main_bands_are_70_to_99():
    assert core.MAIN_BANDS == ("70-80", "80-90", "90-95", "95-99")


def test_half_of_splits_on_1_august():
    assert core.half_of(core.ts("2025-11-01T00:00:00Z")) == "train"
    assert core.half_of(core.ts("2026-07-31T23:59:59Z")) == "train"
    assert core.half_of(core.ts("2026-08-01T00:00:00Z")) == "test"
    assert core.half_of(core.ts("2026-10-27T23:59:59Z")) == "test"
    assert core.half_of(core.ts("2026-10-28T00:00:00Z")) is None
    assert core.half_of(core.ts("2025-10-31T23:59:59Z")) is None


# ---------- sampling ----------

def markets(series="S", n_events=100, per_event=8, half_close="2026-03-01T00:00:00Z", result="yes"):
    out = []
    for e in range(n_events):
        for k in range(per_event):
            out.append({"ticker": f"{series}-E{e}-M{k}", "event_ticker": f"{series}-E{e}", "series": series,
                        "close_time": half_close, "result": result})
    return out


def test_sample_caps_events_and_markets_per_event():
    got = core.sample(markets(), seed=20261029)
    events = {m["event_ticker"] for m in got}
    assert len(events) == 40
    per = {e: sum(1 for m in got if m["event_ticker"] == e) for e in events}
    assert max(per.values()) == 5


def test_sample_takes_everything_from_a_small_series():
    got = core.sample(markets(n_events=3, per_event=2), seed=20261029)
    assert len(got) == 6


def test_sample_caps_each_half_separately():
    both = markets(half_close="2026-03-01T00:00:00Z") + [
        dict(m, ticker=m["ticker"] + "T", event_ticker=m["event_ticker"] + "T", close_time="2026-09-01T00:00:00Z")
        for m in markets()]
    got = core.sample(both, seed=20261029)
    by_half = {h: {m["event_ticker"] for m in got if core.half_of(core.ts(m["close_time"])) == h}
               for h in ("train", "test")}
    assert len(by_half["train"]) == 40 and len(by_half["test"]) == 40


def test_sample_never_reads_results_and_ignores_input_order():
    a = markets(result="yes")
    b = markets(result="no")
    random.Random(1).shuffle(b)
    assert sorted(m["ticker"] for m in core.sample(a, seed=7)) == sorted(m["ticker"] for m in core.sample(b, seed=7))


def test_sample_changes_with_the_seed():
    assert {m["ticker"] for m in core.sample(markets(), 1)} != {m["ticker"] for m in core.sample(markets(), 2)}


def test_sample_drops_markets_outside_the_window():
    assert core.sample(markets(half_close="2025-06-01T00:00:00Z"), seed=1) == []


def test_two_pass_sample_picks_exactly_the_same_markets():
    ms = (markets("S", n_events=90, per_event=7) + markets("T", n_events=12, per_event=9)
          + [dict(m, ticker=m["ticker"] + "x", close_time="2026-09-03T00:00:00Z") for m in markets("S", 70, 6)]
          + markets("U", n_events=5, half_close="2025-01-01T00:00:00Z"))
    random.Random(3).shuffle(ms)
    for cap in (40, 25):
        want = core.sample(ms, seed=11, max_events=cap)
        got = core.sample_two_pass(lambda: iter(ms), seed=11, max_events=cap)
        assert [m["ticker"] for m in got] == [m["ticker"] for m in want]


def test_two_pass_sample_keeps_the_first_copy_of_a_repeated_ticker():
    ms = markets("S", n_events=2, per_event=1)
    dup = dict(ms[0], result="no")
    got = core.sample_two_pass(lambda: iter(ms + [dup]), seed=1)
    assert len(got) == 2 and [m["result"] for m in got if m["ticker"] == ms[0]["ticker"]] == ["yes"]


def test_sample_event_cap_is_a_parameter():
    assert len({m["event_ticker"] for m in core.sample(markets(), 1, max_events=25)}) == 25


# ---------- which trade requests a market needs ----------

CUT = core.ts("2026-08-29T00:00:00Z")


def test_endpoints_for_a_window_after_the_archive_line():
    assert core.endpoints_for(CUT + 10 * H, CUT) == ["live"]


def test_endpoints_for_a_window_before_the_archive_line():
    assert core.endpoints_for(CUT - 2, CUT) == ["historical"]


def test_endpoints_for_a_window_that_straddles_the_archive_line():
    assert core.endpoints_for(CUT + 1800, CUT) == ["live", "historical"]


def test_a_complete_live_page_covers_back_to_the_archive_line_only():
    cov = core.coverage(oldest=CUT + 5 * H, t_max=CUT + 20 * H, complete=True, endpoint="live", cutoff=CUT)
    assert core.covers(cov, CUT + 2 * H)        # window CUT+1h..CUT+2h
    assert not core.covers(cov, CUT + 0.5 * H)  # window reaches before the line


def test_a_complete_historical_page_covers_everything_before_its_top():
    cov = core.coverage(oldest=CUT - 100 * H, t_max=CUT - H, complete=True, endpoint="historical", cutoff=CUT)
    assert core.covers(cov, CUT - 500 * H)
    assert not core.covers(cov, CUT)


def test_a_full_page_covers_only_after_its_oldest_trade():
    cov = core.coverage(oldest=CUT + 10 * H, t_max=CUT + 20 * H, complete=False, endpoint="live", cutoff=CUT)
    assert core.covers(cov, CUT + 12 * H)
    assert not core.covers(cov, CUT + 11 * H)   # window starts exactly at the oldest trade: maybe more there


# ---------- clustered ranges ----------

def test_one_bet_per_event_gives_the_plain_standard_error_with_the_small_sample_correction():
    vals = [1.0, 2.0, 3.0, 4.0]
    s = core.cluster_stats(vals, ["a", "b", "c", "d"])
    naive = math.sqrt(sum((v - 2.5) ** 2 for v in vals)) / 4
    assert s["mean"] == pytest.approx(2.5)
    assert s["se"] == pytest.approx(naive * math.sqrt(4 / 3))
    assert s["lo"] == pytest.approx(2.5 - 1.96 * s["se"])
    assert s["n"] == 4 and s["events"] == 4


def test_bets_on_one_event_count_as_one():
    s = core.cluster_stats([1.0, 1.0, 3.0, 3.0], ["a", "a", "b", "b"])
    # two events, each sum of deviations +-2: SE^2 = 2/1 * (4 + 4) / 16 = 1
    assert s["se"] == pytest.approx(1.0)
    assert s["events"] == 2


def test_a_single_event_has_no_range():
    s = core.cluster_stats([1.0, 2.0], ["a", "a"])
    assert math.isnan(s["se"]) and math.isnan(s["lo"])


# ---------- candidates and passes ----------

def bet(event, price=90.0, won=True, series="S", band=None, mult=1.0):
    return {"event": event, "price": price, "won": won, "series": series, "mult": mult,
            "band": band or core.band_of(price), "ret": core.return_per_dollar(price, won, mult)}


def winning_cell(n_events=200, lose_every=40, series=("S1", "S2", "S3")):
    """90-95c bets that lose 1 in `lose_every`: about +8c per $1. Spread over four bands and three series."""
    prices = [75.0, 85.0, 92.0, 96.0]
    out = []
    for i in range(n_events):
        out.append(bet(f"E{i}", price=prices[i % 4], won=(i % lose_every != 0), series=series[i % len(series)]))
    return out


def test_a_cell_needs_100_events_to_be_a_candidate():
    assert core.is_candidate(winning_cell(200))
    assert not core.is_candidate(winning_cell(99))


def test_a_losing_cell_is_not_a_candidate():
    assert not core.is_candidate([bet(f"E{i}", price=92, won=(i % 5 != 0)) for i in range(400)])


def test_a_good_test_cell_passes_every_check():
    res = core.pass_checks(winning_cell(400), category=True)
    assert res["passed"], res


def test_band_leave_one_out_fails_when_one_band_carries_everything():
    cell = [bet(f"A{i}", price=75, won=True) for i in range(150)]
    cell += [bet(f"B{i}", price=85, won=(i % 6 != 0)) for i in range(150)]
    cell += [bet(f"C{i}", price=92, won=(i % 10 != 0)) for i in range(150)]
    cell += [bet(f"D{i}", price=96, won=(i % 20 != 0)) for i in range(150)]
    res = core.pass_checks(cell, category=False)
    assert not res["band_loo"]
    assert not res["passed"]


def test_dropping_the_biggest_series_can_fail_a_category():
    cell = [bet(f"A{i}", price=[75, 85, 92, 96][i % 4], won=True, series="BIG") for i in range(300)]
    cell += [bet(f"B{i}", price=[75, 85, 92, 96][i % 4], won=(i % 4 != 0), series=f"S{i % 3}") for i in range(200)]
    res = core.pass_checks(cell, category=True)
    assert not res["drop_biggest"]
    assert not res["passed"]
    assert core.pass_checks(cell, category=False)["drop_biggest"] is None


def test_room_to_spare_needs_1c_a_contract():
    assert core.pass_checks(winning_cell(400), category=True)["room_to_spare"]
    # 98.5c and 98.8c favourites with 2 losses in 400: still a profit, but under 1c a contract
    thin = [bet(f"E{i}", price=[98.5, 98.8][i % 2], won=(i % 200 != 7)) for i in range(400)]
    res = core.pass_checks(thin, category=False)
    assert 0 < res["profit_per_contract"] < 1
    assert res["room_to_spare"] is False


def test_lonely_flag():
    assert core.lonely({"2h": 0.5, "4h": -0.1, "8h": -0.2}, "4h") is False
    assert core.lonely({"2h": -0.5, "4h": 0.3, "8h": -0.2}, "4h") is True
    assert core.lonely({"2h": -0.5, "4h": 0.3}, "4h") is True       # one neighbour only, and it is flat
    assert core.lonely({"4h": 0.3}, "4h") is False                 # no neighbours scored: not flagged


def test_order_of_checkpoints():
    assert core.CHECKPOINT_LABELS == ("half", "1h", "2h", "4h", "8h", "12h", "24h", "2d", "3d", "7d", "14d", "30d")


def test_expected_lucky_passes():
    assert core.expected_lucky_passes(200) == pytest.approx(5.0)
