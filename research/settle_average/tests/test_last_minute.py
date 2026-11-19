"""last_minute.py: do favourites bought in a 15-minute crypto market's last 100 seconds win more often than their price?

A trade is [unix ts, YES price, contracts, taker side]. The taker bought the side named, at the YES price for "yes" and
1 minus it for "no". A bet at a checkpoint is the last favourite buy (paid over 50c) in the FRESH seconds up to it.
"""
import math

import pytest

import last_minute as lm

CLOSE = 1_800_000_000


def tr(left, yes, side, n=1.0):
    """A trade `left` seconds before CLOSE."""
    return [CLOSE - left, yes, n, side]


# ------------------------------------------------------------------ prices and profit


def test_fee_is_kalshis_taker_formula_per_contract():
    assert lm.fee(0.5) == pytest.approx(0.0175)
    assert lm.fee(0.9) == pytest.approx(0.0063)
    assert lm.fee(0.999) == pytest.approx(0.07 * 0.999 * 0.001)


def test_bought_gives_the_side_and_the_price_its_buyer_paid():
    assert lm.bought(tr(5, 0.95, "yes")) == ("yes", 0.95)
    assert lm.bought(tr(5, 0.97, "no")) == ("no", pytest.approx(0.03))
    assert lm.bought(tr(5, 0.08, "no")) == ("no", pytest.approx(0.92))


def test_profit_is_win_less_price_less_fee():
    assert lm.profit("yes", 0.9, "yes") == pytest.approx(1 - 0.9 - 0.0063)
    assert lm.profit("no", 0.9, "yes") == pytest.approx(-0.9 - 0.0063)


@pytest.mark.parametrize("p,label", [(0.51, "50-80c"), (0.80, "80-90c"), (0.899, "80-90c"), (0.90, "90-95c"),
                                     (0.95, "95-98c"), (0.98, "98-99c"), (0.99, "99c+"), (0.999, "99c+")])
def test_band_edges_belong_to_the_band_above(p, label):
    assert lm.band(p) == label


def test_band_is_none_for_an_underdog_price():
    assert lm.band(0.5) is None
    assert lm.band(0.3) is None


# ------------------------------------------------------------------ the bet at a checkpoint


def test_bet_takes_the_latest_favourite_buy_at_or_before_the_checkpoint():
    trades = [tr(38, 0.90, "yes"), tr(33, 0.93, "yes"), tr(30, 0.94, "yes"), tr(29, 0.97, "yes")]
    assert lm.bet_at(trades, CLOSE, 30) == ("yes", 0.94)


def test_bet_skips_underdog_buys():
    trades = [tr(35, 0.92, "yes"), tr(31, 0.92, "no")]          # the No buyer paid 8c
    assert lm.bet_at(trades, CLOSE, 30) == ("yes", 0.92)


def test_bet_reads_a_no_favourite():
    trades = [tr(32, 0.06, "no")]
    assert lm.bet_at(trades, CLOSE, 30) == ("no", pytest.approx(0.94))


def test_bet_skips_a_price_older_than_fresh():
    assert lm.bet_at([tr(41, 0.92, "yes")], CLOSE, 30, fresh=10) is None
    assert lm.bet_at([tr(39, 0.92, "yes")], CLOSE, 30, fresh=10) == ("yes", 0.92)


def test_bet_never_reads_past_the_checkpoint_and_needs_no_sorting():
    trades = [tr(10, 0.99, "yes"), tr(35, 0.91, "yes"), tr(20, 0.98, "yes")]
    assert lm.bet_at(trades, CLOSE, 30) == ("yes", 0.91)
    assert lm.bet_at([tr(25, 0.95, "yes")], CLOSE, 30) is None


def test_bet_skips_a_coin_flip_price():
    assert lm.bet_at([tr(32, 0.50, "yes")], CLOSE, 30) is None


# ------------------------------------------------------------------ from the tape to rows


def line(result="yes", trades=None, series="KXBTC15M", close=CLOSE):
    return {"t": "KXBTC15M-X", "s": series, "c": close, "r": result, "tr": trades or []}


def test_bets_gives_one_row_per_checkpoint_that_has_a_price():
    rows = lm.bets([line("yes", [tr(33, 0.92, "yes"), tr(12, 0.97, "yes")])], checks=(60, 30, 10))
    assert [(r["check"], r["price"], r["won"]) for r in rows] == [(30, 0.92, 1), (10, 0.97, 1)]
    assert rows[0]["coin"] == "BTC" and rows[0]["window"] == CLOSE and rows[0]["side"] == "yes"


def test_bets_scores_a_favourite_that_lost():
    rows = lm.bets([line("no", [tr(31, 0.93, "yes")])], checks=(30,))
    assert rows[0]["won"] == 0


def test_buys_lists_every_favourite_buy_in_the_last_minute_with_its_size():
    trades = [tr(70, 0.90, "yes", 5), tr(40, 0.95, "yes", 2), tr(20, 0.04, "no", 3), tr(10, 0.30, "yes", 9)]
    rows = lm.buys([line("yes", trades)], last=60)
    assert [(r["left"], r["price"], r["n"], r["won"]) for r in rows] == [(40, 0.95, 2, 1), (20, pytest.approx(0.96), 3, 0)]


# ------------------------------------------------------------------ the summary


def test_stats_reports_win_rate_edge_and_a_t_clustered_on_the_window():
    rows = [{"window": "A", "price": 0.9, "won": 1}, {"window": "A", "price": 0.9, "won": 1},
            {"window": "B", "price": 0.9, "won": 0}, {"window": "B", "price": 0.9, "won": 1}]
    s = lm.stats(rows, min_n=1)
    x = [0.0937, 0.0937, -0.9063, 0.0937]
    m = sum(x) / 4
    se = math.sqrt((x[0] + x[1] - 2 * m) ** 2 + (x[2] + x[3] - 2 * m) ** 2) / 4
    assert s["n"] == 4 and s["windows"] == 2
    assert s["price"] == pytest.approx(0.9) and s["won"] == pytest.approx(0.75)
    assert s["edge_c"] == pytest.approx(m * 100)
    assert s["per_dollar_c"] == pytest.approx(sum(x) / 3.6 * 100)
    assert s["t"] == pytest.approx(m / se)


def test_stats_weights_by_contracts_when_asked():
    rows = [{"window": "A", "price": 0.9, "won": 1, "n": 3}, {"window": "B", "price": 0.9, "won": 0, "n": 1}]
    s = lm.stats(rows, min_n=1, weight="n")
    assert s["won"] == pytest.approx(0.75)
    assert s["edge_c"] == pytest.approx((3 * 0.0937 - 0.9063) / 4 * 100)
    assert s["contracts"] == 4 and s["dollars"] == pytest.approx(3.6)


def test_stats_says_too_few_under_min_n():
    assert lm.stats([{"window": "A", "price": 0.9, "won": 1}], min_n=30) == {"n": 1, "too_few": True}


# ------------------------------------------------------------------ the fetch


class Fake:
    """Stands in for get(): serves pages of a market listing or a trade tape, newest first, by cursor."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        i = int(params.get("cursor") or 0)
        body = dict(self.pages[path][i])
        if i + 1 < len(self.pages[path]):
            body["cursor"] = str(i + 1)
        return body


def trade(t, yes, n, side):
    from datetime import datetime, timezone
    iso = datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")
    return {"created_time": iso, "yes_price_dollars": f"{yes:.4f}", "count_fp": f"{n:.2f}", "taker_side": side}


def test_tape_follows_the_cursor_and_returns_trades_oldest_first():
    fake = Fake({"/markets/trades": [{"trades": [trade(CLOSE - 2, 0.99, 4, "yes"), trade(CLOSE - 5, 0.97, 1, "yes")]},
                                     {"trades": [trade(CLOSE - 50, 0.09, 2, "no")]}]})
    out = lm.tape("T", CLOSE, get=fake)
    assert out == [[CLOSE - 50, 0.09, 2.0, "no"], [CLOSE - 5, 0.97, 1.0, "yes"], [CLOSE - 2, 0.99, 4.0, "yes"]]
    assert fake.calls[0] == ("/markets/trades", {"ticker": "T", "min_ts": CLOSE - lm.SPAN, "max_ts": CLOSE,
                                                 "limit": 1000})
    assert fake.calls[1][1]["cursor"] == "1"


def test_tape_falls_back_to_the_historical_endpoint_when_the_live_one_is_empty():
    fake = Fake({"/markets/trades": [{"trades": []}],
                 "/historical/trades": [{"trades": [trade(CLOSE - 3, 0.95, 1, "yes")]}]})
    assert lm.tape("T", CLOSE, get=fake) == [[CLOSE - 3, 0.95, 1.0, "yes"]]


def test_settled_lists_markets_that_closed_in_range_with_a_result():
    m = lambda tk, close, r: {"ticker": tk, "close_time": close, "result": r, "floor_strike": 100.5,
                              "expiration_value": "101.25"}
    fake = Fake({"/markets": [{"markets": [m("A", "2026-10-01T00:15:00Z", "yes")]},
                              {"markets": [m("B", "2026-10-01T00:30:00Z", "no"), m("C", "2026-10-01T00:45:00Z", "")]}]})
    out = lm.settled("KXBTC15M", 1000, 2000, get=fake)
    assert [(x["t"], x["r"]) for x in out] == [("A", "yes"), ("B", "no")]
    assert out[0]["c"] == 1790813700 and out[0]["k"] == 100.5 and out[0]["v"] == 101.25 and out[0]["s"] == "KXBTC15M"
    assert fake.calls[0] == ("/markets", {"series_ticker": "KXBTC15M", "status": "settled", "min_close_ts": 1000,
                                          "max_close_ts": 2000, "limit": 1000})


# ------------------------------------------------------------------ the fresh test on older data (PREREG_FRESH.md)


def hist_market(tk, close, r="yes"):
    return {"ticker": tk, "close_time": close, "result": r, "floor_strike": 1.0, "expiration_value": "2.0"}


def test_settled_old_pages_the_historical_listing_and_keeps_the_range():
    # /historical/markets ignores close-time filters and serves newest first, so the range is kept here
    fake = Fake({"/historical/markets": [
        {"markets": [hist_market("D", "2026-08-30T00:00:00Z"), hist_market("C", "2026-03-01T00:15:00Z")]},
        {"markets": [hist_market("B", "2026-03-01T00:00:00Z", ""), hist_market("A", "2026-02-27T00:00:00Z")]}]})
    lo, hi = lm.ts("2026-02-28T00:00:00Z"), lm.ts("2026-08-01T00:00:00Z")
    out = lm.settled_old("KXBTC15M", lo, hi, get=fake)
    assert [x["t"] for x in out] == ["C"]
    assert fake.calls[0] == ("/historical/markets", {"series_ticker": "KXBTC15M", "limit": 200})  # 1000 draws a 429


def test_settled_old_stops_once_a_page_is_older_than_the_range():
    fake = Fake({"/historical/markets": [{"markets": [hist_market("B", "2026-03-01T00:00:00Z"),
                                                       hist_market("A", "2026-01-01T00:00:00Z")]},
                                         {"markets": [hist_market("Z", "2025-12-01T00:00:00Z")]}]})
    lm.settled_old("KXBTC15M", lm.ts("2026-02-01T00:00:00Z"), lm.ts("2026-04-01T00:00:00Z"), get=fake)
    assert len(fake.calls) == 1


def test_markets_between_takes_old_markets_from_history_and_new_ones_live_without_doubles():
    fake = Fake({"/historical/markets": [{"markets": [hist_market("B", "2026-08-26T00:00:00Z"),
                                                       hist_market("A", "2026-08-20T00:00:00Z")]}],
                 "/markets": [{"markets": [hist_market("C", "2026-08-30T00:00:00Z"),
                                           hist_market("B", "2026-08-26T00:00:00Z")]}]})
    out = lm.markets_between(["KXBTC15M"], lm.ts("2026-08-01T00:00:00Z"), lm.ts("2026-09-01T00:00:00Z"),
                             cutoff=lm.ts("2026-08-27T00:00:00Z"), get=fake)
    assert [x["t"] for x in out] == ["A", "B", "C"]


def test_tape_asks_history_first_for_an_old_market():
    fake = Fake({"/historical/trades": [{"trades": [trade(CLOSE - 3, 0.95, 1, "yes")]}],
                 "/markets/trades": [{"trades": []}]})
    assert lm.tape("T", CLOSE, get=fake, old=True) == [[CLOSE - 3, 0.95, 1.0, "yes"]]
    assert [c[0] for c in fake.calls] == ["/historical/trades"]


def row(check=30, price=0.9, won=1, window="A", day="2026-06-01", coin="BTC"):
    return {"check": check, "price": price, "won": won, "window": window, "day": day, "coin": coin}


def test_rule_is_80_to_98c_at_45_30_20_and_10_seconds():
    rows = [row(45, 0.80), row(30, 0.979), row(20, 0.98), row(10, 0.799), row(60, 0.9), row(5, 0.9), row(10, 0.9)]
    assert [(r["check"], r["price"]) for r in lm.rule(rows)] == [(45, 0.80), (30, 0.979), (10, 0.9)]


def test_before_the_minute_is_the_same_band_at_90_seconds():
    rows = [row(90, 0.85), row(90, 0.99), row(60, 0.85), row(90, 0.80)]
    assert [(r["check"], r["price"]) for r in lm.before_minute(rows)] == [(90, 0.85), (90, 0.80)]


def test_verdict_follows_the_pass_bar():
    ok = {"edge_c": 2.0, "t": 2.5}
    assert lm.verdict(ok, {"edge_c": 1.0, "t": 1.2}, {"edge_c": 0.5, "t": 0.4}, {"edge_c": 1.8, "t": 2.1}) == "pass"
    assert lm.verdict(ok, {"edge_c": -0.1, "t": -0.1}, ok, ok) == "in between"      # a half below zero
    assert lm.verdict(ok, ok, ok, {"edge_c": -0.2, "t": -0.2}) == "in between"     # gone without the best day
    assert lm.verdict({"edge_c": 1.0, "t": 1.5}, ok, ok, ok) == "in between"
    assert lm.verdict({"edge_c": 1.0, "t": 0.9}, ok, ok, ok) == "fail"
    assert lm.verdict({"edge_c": -0.5, "t": -3.0}, ok, ok, ok) == "fail"
    assert lm.verdict({"n": 3, "too_few": True}, ok, ok, ok) == "too few"


def test_by_month_groups_rows_by_calendar_month():
    rows = [row(day="2026-05-31"), row(day="2026-06-01", window="B"), row(day="2026-06-30", window="C")]
    out = lm.by_month(rows, min_n=1)
    assert list(out) == ["2026-05", "2026-06"] and out["2026-06"]["n"] == 2


def test_market_list_is_built_once_and_then_read_from_disk(tmp_path):
    calls = []

    def build():
        calls.append(1)
        return [{"t": "A", "s": "KXBTC15M", "c": CLOSE, "r": "yes", "k": 1.0, "v": 2.0}]

    first = lm.market_list(str(tmp_path), build)
    second = lm.market_list(str(tmp_path), build)
    assert first == second == build() and len(calls) == 2      # build() ran once inside, once here


def test_from_strikes_reads_the_saved_listing_for_the_series_and_range(tmp_path):
    # research/kalshi_15min/lab/spot/strikes.npz (fetch_strikes.py, Oct 11): every settled 15-minute market's ticker,
    # open time, opening average (strike), closing average (settle) and 1 if YES won
    import numpy as np
    path = str(tmp_path / "strikes.npz")
    np.savez(path, ticker=np.array(["KXBTC15M-A", "KXETH15M-A", "KXSOL15M-A", "KXBTC15M-B", "KXBTC15M-C"]),
             open_ts=np.array([CLOSE - 900, CLOSE - 900, CLOSE - 900, CLOSE, CLOSE + 900]),
             strike=np.array([1.0, 2.0, 3.0, 4.0, 5.0]), settle=np.array([1.5, np.nan, 3.5, 4.5, 5.5]),
             yes=np.array([1, 0, 1, 0, 1]))
    out = lm.from_strikes(path, ("KXBTC15M", "KXETH15M"), CLOSE, CLOSE + 900)
    assert [(m["t"], m["s"], m["c"], m["r"]) for m in out] == [
        ("KXBTC15M-A", "KXBTC15M", CLOSE, "yes"), ("KXETH15M-A", "KXETH15M", CLOSE, "no"),
        ("KXBTC15M-B", "KXBTC15M", CLOSE + 900, "no")]
    assert out[0]["k"] == 1.0 and out[0]["v"] == 1.5 and math.isnan(out[1]["v"])


def test_get_waits_out_a_long_busy_spell_instead_of_giving_up(monkeypatch):
    # the shared request limit can stay busy for an hour (other jobs on the laptop); a long fetch must not die of it
    class Reply:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": 1}

    replies = [Reply(429)] * (lm.TRIES + 10) + [Reply(200)]
    monkeypatch.setattr(lm._s, "get", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(lm.time, "sleep", lambda s: None)
    assert lm.get("/markets/trades", {"ticker": "T"}) == {"ok": 1}
    assert not replies


def test_get_still_gives_up_on_a_busy_spell_that_never_ends(monkeypatch):
    class Reply:
        status_code = 429
    monkeypatch.setattr(lm._s, "get", lambda *a, **k: Reply())
    monkeypatch.setattr(lm.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        lm.get("/markets/trades", {"ticker": "T"})
