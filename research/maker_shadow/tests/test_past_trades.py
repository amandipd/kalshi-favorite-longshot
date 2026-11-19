"""Tests for past_trades.py: the best-case maker test on the bot's past markets, from Kalshi's trade history.

Pure functions only; nothing here touches the network (conftest.py refuses every socket).

    python -m pytest research/maker_shadow/tests/test_past_trades.py -q
"""
import gzip
import json
import math

import pytest

import past_trades as pt


def dec(fav_side="yes", yes_bid=0.95, yes_ask=0.96, fav_price=None, ts=1792128480.0002, ticker="KXBTC15M-X",
        series="KXBTC15M", action="bet"):
    if fav_price is None:
        fav_price = yes_ask if fav_side == "yes" else round(1 - yes_bid, 4)
    return {"ts": ts, "ticker": ticker, "series": series, "yes_bid": yes_bid, "yes_ask": yes_ask,
            "fav_side": fav_side, "fav_price": fav_price, "action": action, "reason": ""}


def raw(t, yes, count, taker, tid="x"):
    """A trade as Kalshi's REST API returns it; t is seconds after 2026-10-15T00:00:00Z."""
    whole, frac = divmod(t, 1)
    hh, rest = divmod(int(whole), 3600)
    mm, ss = divmod(rest, 60)
    stamp = f"2026-10-15T{hh:02d}:{mm:02d}:{ss:02d}.{int(round(frac * 1e6)):06d}Z"
    return {"trade_id": tid, "ticker": "T", "created_time": stamp, "yes_price_dollars": f"{yes:.4f}",
            "no_price_dollars": f"{1 - yes:.4f}", "count_fp": f"{count:.2f}", "taker_side": taker}


T0 = 1792022400.0   # 2026-10-15T00:00:00Z


# ------------------------------------------------------------------ the order and its market


def test_limit_is_the_favourites_own_bid():
    assert pt.limit_of(dec("yes", yes_bid=0.95, yes_ask=0.96)) == pytest.approx(0.95)
    # a NO favourite's bid is 1 - the YES ask
    assert pt.limit_of(dec("no", yes_bid=0.03, yes_ask=0.04)) == pytest.approx(0.96)
    assert pt.limit_of(dec("no", yes_bid=0.021, yes_ask=0.022)) == pytest.approx(0.978)


def test_limit_none_without_a_bid():
    assert pt.limit_of(dec("yes", yes_bid=0.0, yes_ask=0.96)) is None
    assert pt.limit_of(dec("yes", yes_bid=None, yes_ask=0.96, fav_price=0.96)) is None
    assert pt.limit_of(dec("no", yes_bid=0.03, yes_ask=1.0, fav_price=0.97)) is None


def test_in_band():
    assert pt.in_band(dec(fav_price=0.92))
    assert pt.in_band(dec(fav_price=0.999))
    assert not pt.in_band(dec(fav_price=0.919))
    assert not pt.in_band(dec(fav_price=1.0))
    assert not pt.in_band(dec(fav_price=None) | {"fav_price": None})


def test_close_of_is_the_end_of_the_window():
    assert pt.close_of(1792128180.0002) == 1792128600   # 480 s into the window that opened at 1792127700
    assert pt.close_of(1792128600.0) == 1792129500      # a window's first second belongs to it


def test_band_and_group():
    assert pt.band_of(0.92) == "92-95c"
    assert pt.band_of(0.949) == "92-95c"
    assert pt.band_of(0.95) == "95-98c"
    assert pt.band_of(0.979) == "95-98c"
    assert pt.band_of(0.98) == "98c+"
    assert pt.band_of(0.999) == "98c+"
    assert pt.group_of("KXBTC15M") == "crypto"
    assert pt.group_of("KXZEC15M") == "crypto"
    assert pt.group_of("KXGOLD15M") == "metals"
    assert pt.group_of("KXCOPPER15M") == "metals"
    assert pt.group_of("KXWTI15M") == "energy"
    assert pt.group_of("KXNATGAS15M") == "energy"


# ------------------------------------------------------------------ the tape


def test_parse_trade():
    t = pt.parse_trade(raw(3600.25, 0.93, 12, "no"))
    assert t[:4] == pytest.approx((T0 + 3600.25, 0.93, 0.07, 12.0))
    assert t[4] == "no"


def test_parse_trade_short_fraction():
    r = raw(10, 0.5, 1, "yes") | {"created_time": "2026-10-15T00:00:10.5173Z"}
    assert pt.parse_trade(r)[0] == pytest.approx(T0 + 10.5173)


def test_sellers_of_a_yes_favourite():
    """A taker who bought NO sold YES: that hits resting YES bids, at the trade's YES price."""
    tape = [pt.parse_trade(x) for x in (raw(5, 0.95, 3, "no"), raw(6, 0.96, 4, "yes"), raw(7, 0.94, 2, "no"))]
    s = pt.sellers(tape, "yes", T0, T0 + 900)
    assert [(round(t - T0), p, c) for t, p, c in s] == [(5, 0.95, 3.0), (7, 0.94, 2.0)]


def test_sellers_of_a_no_favourite():
    """A taker who bought YES sold NO: that hits resting NO bids, at the trade's NO price."""
    tape = [pt.parse_trade(x) for x in (raw(5, 0.05, 3, "yes"), raw(6, 0.04, 4, "no"))]
    s = pt.sellers(tape, "no", T0, T0 + 900)
    assert [(round(t - T0), round(p, 4), c) for t, p, c in s] == [(5, 0.95, 3.0)]


def test_sellers_only_after_the_mark_and_before_the_close():
    tape = [pt.parse_trade(x) for x in (raw(479.9, 0.95, 1, "no"), raw(480.5, 0.95, 2, "no"), raw(900, 0.95, 4, "no"),
                                        raw(899.9, 0.95, 8, "no"))]
    s = pt.sellers(tape, "yes", T0 + 480.0, T0 + 900)
    assert [c for _, _, c in s] == [2.0, 8.0]


def test_sellers_sorted_by_time_whatever_the_page_order():
    tape = [pt.parse_trade(x) for x in (raw(9, 0.95, 1, "no"), raw(7, 0.95, 2, "no"), raw(8, 0.95, 3, "no"))]
    assert [c for _, _, c in pt.sellers(tape, "yes", T0, T0 + 900)] == [2.0, 3.0, 1.0]


# ------------------------------------------------------------------ the two fill bounds


SELL = [(T0 + 500, 0.96, 4.0), (T0 + 510, 0.95, 5.0), (T0 + 520, 0.94, 3.0), (T0 + 530, 0.95, 20.0)]


def test_best_case_fills_at_or_below_our_price():
    f = pt.fill(SELL, 0.95, 15, strict=False)
    assert f["filled"] == pytest.approx(15.0)       # 5 + 3 + 7 of the 20
    assert f["first_ts"] == T0 + 510
    assert f["full_ts"] == T0 + 530


def test_worst_case_fills_only_below_our_price():
    f = pt.fill(SELL, 0.95, 15, strict=True)
    assert f["filled"] == pytest.approx(3.0)
    assert f["first_ts"] == T0 + 520
    assert f["full_ts"] is None


def test_fill_capped_at_size_and_none_when_nothing_trades():
    assert pt.fill(SELL, 0.95, 4, strict=False)["filled"] == pytest.approx(4.0)
    assert pt.fill(SELL, 0.95, 4, strict=False)["full_ts"] == T0 + 510
    nothing = pt.fill(SELL, 0.90, 15, strict=False)
    assert nothing == {"filled": 0.0, "first_ts": None, "full_ts": None}


def test_fill_price_tolerance_for_float_noise():
    s = [(T0 + 500, 0.95 + 1e-12, 2.0)]
    assert pt.fill(s, 0.95, 15, strict=False)["filled"] == pytest.approx(2.0)
    assert pt.fill(s, 0.95, 15, strict=True)["filled"] == 0.0
    s = [(T0 + 500, 0.95 - 1e-12, 2.0)]
    assert pt.fill(s, 0.95, 15, strict=True)["filled"] == 0.0


def test_fill_fractional_contracts():
    s = [(T0 + 500, 0.94, 0.03), (T0 + 501, 0.94, 14.5), (T0 + 502, 0.94, 3)]
    f = pt.fill(s, 0.95, 15, strict=True)
    assert f["filled"] == pytest.approx(15.0)
    assert f["full_ts"] == T0 + 502


# ------------------------------------------------------------------ what the price did next


def test_last_price_by_time():
    tape = [pt.parse_trade(x) for x in (raw(500, 0.95, 1, "no"), raw(503, 0.97, 1, "yes"), raw(540, 0.90, 1, "no"))]
    assert pt.last_price(tape, "yes", T0 + 505) == pytest.approx(0.97)
    assert pt.last_price(tape, "yes", T0 + 503) == pytest.approx(0.97)
    assert pt.last_price(tape, "yes", T0 + 502.9) == pytest.approx(0.95)
    assert pt.last_price(tape, "yes", T0 + 499) is None
    assert pt.last_price(tape, "no", T0 + 600) == pytest.approx(0.10)


def test_after_fill_lookups():
    tape = [pt.parse_trade(x) for x in (raw(500, 0.95, 1, "no"), raw(503, 0.97, 1, "yes"), raw(540, 0.90, 1, "no"),
                                        raw(899, 0.80, 1, "no"), raw(901, 0.01, 1, "no"))]
    a = pt.after_fill(tape, "yes", T0 + 500, T0 + 900)
    assert a == {"p5": pytest.approx(0.97), "p30": pytest.approx(0.97), "p60": pytest.approx(0.90),
                 "close": pytest.approx(0.80)}
    assert pt.after_fill(tape, "yes", None, T0 + 900) == {"p5": None, "p30": None, "p60": None, "close": None}


def test_after_fill_lookups_do_not_run_past_the_close():
    tape = [pt.parse_trade(x) for x in (raw(880, 0.95, 1, "no"), raw(901, 0.50, 1, "no"))]
    a = pt.after_fill(tape, "yes", T0 + 880, T0 + 900)
    assert a["p30"] == pytest.approx(0.95) and a["p60"] == pytest.approx(0.95)


# ------------------------------------------------------------------ fees and scoring


def test_taker_fee_rounds_up_to_a_hundredth_of_a_cent():
    assert pt.taker_fee(3, 0.98) == pytest.approx(0.0042)          # 0.07 * 3 * .98 * .02 = 0.004116
    assert pt.taker_fee(15, 0.95) == pytest.approx(0.0499)         # 0.049875
    assert pt.taker_fee(10, 0.5, mult=0.5) == pytest.approx(0.0875)
    assert pt.taker_fee(0, 0.95) == 0.0


def test_maker_fee_only_when_the_series_charges_one():
    assert pt.maker_fee(15, 0.95, {"fee_type": "quadratic", "fee_multiplier": 1}) == 0.0
    assert pt.maker_fee(15, 0.95, None) == 0.0
    with_fee = {"fee_type": "quadratic_with_maker_fees", "fee_multiplier": 1}
    assert pt.maker_fee(15, 0.95, with_fee) == pytest.approx(0.0125)   # 0.0175 * 15 * .95 * .05 = 0.01246875
    assert pt.maker_fee(0, 0.95, with_fee) == 0.0


def test_maker_pnl():
    assert pt.maker_pnl(15, 0.95, True) == pytest.approx(0.75)
    assert pt.maker_pnl(15, 0.95, False) == pytest.approx(-14.25)
    assert pt.maker_pnl(15, 0.95, True, fee=0.0125) == pytest.approx(0.7375)
    assert pt.maker_pnl(0, 0.95, False) == 0.0


def test_taker_pnl():
    assert pt.taker_pnl(15, 0.96, True) == pytest.approx(15 * 0.04 - pt.taker_fee(15, 0.96))
    assert pt.taker_pnl(15, 0.96, False) == pytest.approx(-15 * 0.96 - pt.taker_fee(15, 0.96))


def test_cents_per_dollar():
    assert pt.cents_per_dollar(1.16, 100.0) == pytest.approx(1.16)
    assert pt.cents_per_dollar(0.0, 0.0) is None


# ------------------------------------------------------------------ the range, counting each window once


def test_window_ratio_range_counts_each_window_once():
    # two windows: window A made 1 on 100, window B lost 1 on 100
    rows = [{"window": 1, "pnl": 0.5, "stake": 50}, {"window": 1, "pnl": 0.5, "stake": 50},
            {"window": 2, "pnl": -1.0, "stake": 100}]
    r = pt.ratio_range(rows)
    assert r["cpd"] == pytest.approx(0.0)
    # by hand: z_A = 1 - 0*100 = 1, z_B = -1; var = G/(G-1) * sum z^2 / S^2 = 2 * 2 / 200^2; se in cents = 100 * sqrt
    se = 100 * math.sqrt(2 * 2) / 200
    assert r["se"] == pytest.approx(se)
    assert r["lo"] == pytest.approx(-1.96 * se) and r["hi"] == pytest.approx(1.96 * se)
    assert r["windows"] == 2 and r["bets"] == 3


def test_window_ratio_range_empty_or_one_window():
    assert pt.ratio_range([])["cpd"] is None
    one = pt.ratio_range([{"window": 1, "pnl": 1.0, "stake": 100}])
    assert one["cpd"] == pytest.approx(1.0) and one["se"] is None


def test_paired_difference_range():
    # maker and taker on the same windows; the difference has its own range from the paired window sums
    rows = [{"window": 1, "pnl_a": 1.0, "stake_a": 100, "pnl_b": 0.0, "stake_b": 100},
            {"window": 2, "pnl_a": 3.0, "stake_a": 100, "pnl_b": 1.0, "stake_b": 100},
            {"window": 3, "pnl_a": 2.0, "stake_a": 100, "pnl_b": 2.0, "stake_b": 100}]
    d = pt.diff_range(rows)
    assert d["diff"] == pytest.approx(2.0 - 1.0)
    # z_g = (a_g - Ra s)/Sa - (b_g - Rb s)/Sb with Ra=.02, Rb=.01, S=300: (-1/300 - -1/300, 1/300 - 0, 0 - 1/300)
    z = [0.0, 1 / 300, -1 / 300]
    se = 100 * math.sqrt(3 / 2 * sum(x * x for x in z))
    assert d["se"] == pytest.approx(se)
    assert d["lo"] == pytest.approx(1.0 - 1.96 * se)


def test_paired_difference_ignores_windows_with_no_stake_on_either_side():
    rows = [{"window": 1, "pnl_a": 1.0, "stake_a": 100, "pnl_b": 0.0, "stake_b": 100},
            {"window": 2, "pnl_a": 0.0, "stake_a": 0, "pnl_b": 0.0, "stake_b": 0},
            {"window": 3, "pnl_a": 3.0, "stake_a": 100, "pnl_b": 1.0, "stake_b": 100}]
    assert pt.diff_range(rows)["windows"] == 2


# ------------------------------------------------------------------ one market, scored


def test_score_market_yes_favourite_won():
    d = dec("yes", yes_bid=0.95, yes_ask=0.96, ts=T0 + 480.0001)
    tape = [pt.parse_trade(x) for x in (raw(470, 0.95, 50, "no"), raw(481, 0.96, 10, "yes"), raw(490, 0.95, 6, "no"),
                                        raw(500, 0.94, 4, "no"), raw(560, 0.97, 1, "yes"), raw(890, 0.99, 1, "yes"))]
    m = pt.score_market(d, tape, won=True, size=15, series_info=None)
    assert m["L"] == pytest.approx(0.95)
    assert m["close"] == T0 + 900
    best, worst = m["best"], m["worst"]
    assert best["filled"] == pytest.approx(10.0)            # 6 at 95c + 4 at 94c; the 470 s trade is before the mark
    assert best["first_after"] == pytest.approx(10.0, abs=1e-3)
    assert best["pnl"] == pytest.approx(10 * 0.05)
    assert best["stake"] == pytest.approx(10 * 0.95)
    assert best["after"]["p5"] == pytest.approx(0.95)        # last trade by 495 s is the 490 s one
    assert best["after"]["p30"] == pytest.approx(0.94)       # by 520 s: the 500 s sale at 94c
    assert best["after"]["p60"] == pytest.approx(0.94)       # by 550 s: still that one (the 97c buy is at 560 s)
    assert best["after"]["close"] == pytest.approx(0.99)
    assert worst["filled"] == pytest.approx(4.0)
    assert worst["pnl"] == pytest.approx(4 * 0.05)
    assert m["sellers"] == pytest.approx(10.0)


def test_score_market_no_favourite_lost_with_maker_fee():
    d = dec("no", yes_bid=0.03, yes_ask=0.04, ts=T0 + 480.0)
    tape = [pt.parse_trade(x) for x in (raw(600, 0.04, 20, "yes"), raw(610, 0.05, 20, "yes"))]
    info = {"fee_type": "quadratic_with_maker_fees", "fee_multiplier": 1}
    m = pt.score_market(d, tape, won=False, size=15, series_info=info)
    assert m["L"] == pytest.approx(0.96)
    assert m["best"]["filled"] == pytest.approx(15.0)
    assert m["best"]["pnl"] == pytest.approx(-15 * 0.96 - pt.maker_fee(15, 0.96, info))
    assert m["worst"]["filled"] == pytest.approx(15.0)        # the 95c NO sale went through our 96c
    assert m["worst"]["first_after"] == pytest.approx(130.0)


def test_score_market_unfilled():
    d = dec("yes", yes_bid=0.95, yes_ask=0.96, ts=T0 + 480.0)
    tape = [pt.parse_trade(raw(600, 0.96, 20, "yes"))]
    m = pt.score_market(d, tape, won=True, size=15, series_info=None)
    assert m["best"]["filled"] == 0.0 and m["best"]["pnl"] == 0.0 and m["best"]["stake"] == 0.0
    assert m["best"]["first_after"] is None


# ------------------------------------------------------------------ the taker on the same market


def test_taker_side_uses_the_bots_real_bet():
    bet = {"price": 0.96, "contracts": 10.0, "cost": 9.6, "fee": 0.0269, "pnl": 0.3731, "status": "won"}
    t = pt.taker_of(dec(), bet, won=True, size=15)
    assert t == {"pnl": pytest.approx(0.3731), "stake": pytest.approx(9.6), "contracts": 10.0, "real": True}


def test_taker_side_flat_size_keeps_the_bots_price():
    bet = {"price": 0.96, "contracts": 10.0, "cost": 9.6, "fee": 0.0269, "pnl": 0.3731, "status": "won"}
    t = pt.taker_of(dec(), bet, won=True, size=15, real_size=False)
    assert t["pnl"] == pytest.approx(15 * 0.04 - pt.taker_fee(15, 0.96))
    assert t["stake"] == pytest.approx(15 * 0.96)
    assert t["contracts"] == 15 and t["real"] is True


def test_taker_side_for_a_skip_buys_the_ask_with_the_fee():
    d = dec("yes", yes_bid=0.95, yes_ask=0.96, action="skip")
    t = pt.taker_of(d, None, won=False, size=15)
    assert t["pnl"] == pytest.approx(-15 * 0.96 - pt.taker_fee(15, 0.96))
    assert t["stake"] == pytest.approx(15 * 0.96)
    assert t["real"] is False


def test_taker_side_for_an_open_bet_is_the_ask_model():
    bet = {"price": 0.96, "contracts": 10.0, "cost": 9.6, "fee": 0.0269, "pnl": None, "status": "open"}
    t = pt.taker_of(dec(), bet, won=True, size=15)
    assert t["real"] is False


# ------------------------------------------------------------------ the cache


def test_page_cache_round_trip_and_resume(tmp_path):
    root = tmp_path / "past_trades"
    assert pt.cached_pages(root, "KXBTC15M-A") == ([], None, False)
    pt.save_page(root, "KXBTC15M-A", 0, {"trades": [raw(500, 0.95, 1, "no")], "cursor": "abc"})
    pages, cursor, done = pt.cached_pages(root, "KXBTC15M-A")
    assert len(pages) == 1 and cursor == "abc" and not done
    pt.save_page(root, "KXBTC15M-A", 1, {"trades": [raw(501, 0.95, 2, "no")], "cursor": ""})
    pt.mark_done(root, "KXBTC15M-A", 2)
    pages, cursor, done = pt.cached_pages(root, "KXBTC15M-A")
    assert len(pages) == 2 and done
    assert [len(p["trades"]) for p in pages] == [1, 1]


def test_fetch_market_pages_through_the_cursor_and_caches(tmp_path):
    calls = []
    answers = [{"trades": [raw(600, 0.95, 1, "no")], "cursor": "c1"}, {"trades": [raw(500, 0.95, 2, "no")], "cursor": ""}]

    def get(path, params):
        calls.append((path, dict(params)))
        return answers[len(calls) - 1]

    tape, pages = pt.fetch_market(tmp_path, "T", 100, 200, get)
    assert pages == 2
    assert calls[0] == ("/markets/trades", {"ticker": "T", "min_ts": 100, "max_ts": 200, "limit": 1000})
    assert calls[1][1]["cursor"] == "c1"
    assert len(tape) == 2
    # second time: all from the cache, no calls
    tape2, pages2 = pt.fetch_market(tmp_path, "T", 100, 200, lambda *a: pytest.fail("should not ask Kalshi"))
    assert pages2 == 0 and len(tape2) == 2


def test_fetch_market_resumes_a_cut_short_run(tmp_path):
    pt.save_page(tmp_path, "T", 0, {"trades": [raw(600, 0.95, 1, "no")], "cursor": "c1"})
    calls = []

    def get(path, params):
        calls.append(dict(params))
        return {"trades": [raw(500, 0.95, 2, "no")], "cursor": None}

    tape, pages = pt.fetch_market(tmp_path, "T", 100, 200, get)
    assert pages == 1 and calls[0]["cursor"] == "c1" and len(tape) == 2


def test_fetch_market_stops_at_a_page_cap(tmp_path):
    def get(path, params):
        return {"trades": [raw(500, 0.95, 1, "no")], "cursor": "more"}

    tape, pages = pt.fetch_market(tmp_path, "T", 100, 200, get, max_pages=3)
    assert pages == 3
    assert not pt.cached_pages(tmp_path, "T")[2]   # not done: a later run can carry on


def test_saved_pages_are_gzipped_json(tmp_path):
    pt.save_page(tmp_path, "T", 0, {"trades": [], "cursor": ""})
    files = list((tmp_path).rglob("*.json.gz"))
    assert len(files) == 1
    with gzip.open(files[0], "rt", encoding="utf-8") as fh:
        assert json.load(fh) == {"trades": [], "cursor": ""}


# ------------------------------------------------------------------ which markets, in what order


def test_markets_in_priority_order():
    ohio = pt.OHIO
    ds = [dec(ts=ohio - 10000, ticker="LAP-BET", action="bet"),
          dec(ts=ohio + 10000, ticker="OH-SKIP", action="skip"),
          dec(ts=ohio + 20000, ticker="OH-BET", action="bet"),
          dec(ts=ohio + 30000, ticker="OH-OUT", action="skip", fav_price=0.80),
          dec(ts=ohio + 40000, ticker="OH-HALT", action="halted")]
    order = [d["ticker"] for d in pt.markets_by_priority(ds)]
    assert order == ["OH-BET", "OH-SKIP", "OH-HALT", "LAP-BET"]


def test_markets_keep_one_decision_per_ticker():
    ds = [dec(ticker="A", ts=pt.OHIO + 1), dec(ticker="A", ts=pt.OHIO + 2, action="skip")]
    assert len(pt.markets_by_priority(ds)) == 1


# ------------------------------------------------------------------ a dollar difference, counting each window once


def test_total_range_sums_by_window():
    rows = [{"window": 1, "d": 1.0}, {"window": 1, "d": 1.0}, {"window": 2, "d": -1.0}, {"window": 3, "d": 3.0}]
    r = pt.total_range(rows)
    assert r["total"] == pytest.approx(4.0)
    g = [2.0, -1.0, 3.0]
    m = sum(g) / 3
    se = math.sqrt(3 / 2 * sum((x - m) ** 2 for x in g))
    assert r["se"] == pytest.approx(se)
    assert r["lo"] == pytest.approx(4.0 - 1.96 * se) and r["hi"] == pytest.approx(4.0 + 1.96 * se)
    assert r["windows"] == 3


def test_total_range_one_window():
    r = pt.total_range([{"window": 1, "d": 2.0}])
    assert r["total"] == pytest.approx(2.0) and r["se"] is None


# ------------------------------------------------------------------ the fetch order: tiers, shuffled, BTC sampled


def test_fetch_order_samples_btc_and_keeps_the_tiers():
    ohio = pt.OHIO
    ds = [dec(ts=ohio + 900 * i, ticker=f"KXBTC15M-B{i}", series="KXBTC15M", action="bet") for i in range(10)]
    ds += [dec(ts=ohio + 900 * i, ticker=f"KXETH15M-B{i}", series="KXETH15M", action="bet") for i in range(10)]
    ds += [dec(ts=ohio + 900 * i, ticker=f"KXETH15M-S{i}", series="KXETH15M", action="skip") for i in range(5)]
    ds += [dec(ts=ohio - 900 * (i + 1), ticker=f"KXETH15M-L{i}", series="KXETH15M", action="bet") for i in range(3)]
    order = [d["ticker"] for d in pt.fetch_order(ds, every={"KXBTC15M": 5})]
    assert len(order) == len(ds)                      # nothing dropped: sampled-out markets just come later
    first = order[:12]                                # tier 1: Ohio bets, BTC 1 in 5 (2 of 10) + 10 ETH
    assert sum(t.startswith("KXBTC15M") for t in first) == 2
    assert sum(t.startswith("KXETH15M-B") for t in first) == 10
    assert all(t.startswith("KXETH15M-S") for t in order[12:17])   # tier 2: Ohio others
    assert sum(t.startswith("KXBTC15M") for t in order[17:25]) == 8  # tier 3: the rest of Ohio BTC
    assert all(t.startswith("KXETH15M-L") for t in order[25:])      # tier 4: the laptop era
    assert pt.fetch_order(ds, every={"KXBTC15M": 5}) == pt.fetch_order(list(reversed(ds)), every={"KXBTC15M": 5})


def test_fetch_order_is_spread_over_time_within_a_tier():
    ds = [dec(ts=pt.OHIO + 900 * i, ticker=f"KXETH15M-B{i}", series="KXETH15M") for i in range(200)]
    first = pt.fetch_order(ds)[:50]
    assert min(d["ts"] for d in first) < pt.OHIO + 900 * 50 and max(d["ts"] for d in first) > pt.OHIO + 900 * 150


def test_sampled_flag():
    ds = [dec(ts=pt.OHIO + 900 * i, ticker=f"KXBTC15M-B{i}", series="KXBTC15M") for i in range(10)]
    picked = [d["ticker"] for d in ds if pt.sampled(d, {"KXBTC15M": 5})]
    assert len(picked) == 2
