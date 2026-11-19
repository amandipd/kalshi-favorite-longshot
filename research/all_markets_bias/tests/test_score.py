"""score.py: turn the sample and its trades into bets, cells, candidates and the once-only test read."""
import json

import pytest

import core
import score

H = 3600
CLOSE = core.ts("2026-03-10T12:00:00Z")          # train half
CLOSE_T = core.ts("2026-09-10T12:00:00Z")        # test half


def market(ticker, event, series="S1", category="Economics", result="yes", close=CLOSE, life=30 * H, mult=1):
    return {"ticker": ticker, "event_ticker": event, "series": series, "category": category, "result": result,
            "close_time": "", "_close": close, "open_time": "", "_open": close - life, "fee_multiplier": mult,
            "cps": core.checkpoints(close - life, close)}


def test_bets_price_each_checkpoint_from_the_trades():
    m = market("A", "E1", result="yes")
    trades = {"A": [[CLOSE - H - 60, 90, 5, "yes"], [CLOSE - 2 * H - 60, 80, 5, "yes"]]}
    bets, seen = score.build_bets([m], trades, {})
    by = {b["label"]: b for b in bets}
    assert by["1h"]["price"] == 90 and by["1h"]["won"] is True
    assert by["2h"]["price"] == 80
    assert by["1h"]["ret"] == pytest.approx(core.return_per_dollar(90, True, 1))
    assert by["1h"]["half"] == "train" and by["1h"]["category"] == "Economics"
    assert seen[("Economics", "1h")] == 1 and seen[("Economics", "24h")] == 1


def test_a_no_favourite_wins_when_the_market_settles_no():
    m = market("A", "E1", result="no")
    bets, _ = score.build_bets([m], {"A": [[CLOSE - H - 60, 8, 1, "no"]]}, {})
    b = [x for x in bets if x["label"] == "1h"][0]
    assert b["side"] == "no" and b["price"] == 92 and b["won"] is True


def test_markets_without_a_usable_price_count_in_retention_only():
    m = market("A", "E1")
    bets, seen = score.build_bets([m], {"A": []}, {})
    assert bets == [] and seen[("Economics", "1h")] == 1


def test_the_series_fee_multiplier_is_used():
    m = market("A", "E1", mult=0.5)
    bets, _ = score.build_bets([m], {"A": [[CLOSE - H - 60, 90, 1, "yes"]]}, {})
    assert bets[0]["ret"] == pytest.approx(core.return_per_dollar(90, True, 0.5))


def test_only_the_labels_asked_for_are_scored():
    m = market("A", "E1")
    trades = {"A": [[CLOSE - H - 60, 90, 5, "yes"], [CLOSE - 2 * H - 60, 80, 5, "yes"]]}
    bets, seen = score.build_bets([m], trades, {}, labels={"1h"})
    assert {b["label"] for b in bets} == {"1h"}
    assert ("Economics", "2h") not in seen


def test_partial_flags_are_carried():
    m = market("A", "E1")
    bets, _ = score.build_bets([m], {"A": [[CLOSE - H - 60, 90, 5, "yes"]]}, {"A": {"1h": True}})
    assert [b["partial"] for b in bets if b["label"] == "1h"] == [True]


def many(n_events, tag="A", category="Economics", series=("S1",), close=CLOSE, lose_every=50,
         prices=(75, 85, 92, 96)):
    """One market per event, life 3 hours, a favourite buy just before the 1h and 2h checkpoints."""
    ms, trades = [], {}
    for i in range(n_events):
        t = f"{tag}-M{i}"
        ms.append(market(t, f"{tag}-E{i}", series=series[i % len(series)], category=category, close=close,
                         result="no" if i % lose_every == 0 else "yes", life=3 * H))
        p = prices[i % len(prices)]
        trades[t] = [[close - 2 * H - 60, p, 1, "yes"], [close - H - 60, p, 1, "yes"]]
    return ms, trades


def test_cells_group_by_category_and_by_series_at_each_checkpoint():
    ms, tr = many(10)
    bets, _ = score.build_bets(ms, tr, {})
    cells = score.cells(bets, "train")
    assert set(cells) == {("category", "Economics", "1h"), ("category", "Economics", "2h"),
                          ("series", "S1", "1h"), ("series", "S1", "2h")}
    assert len(cells[("category", "Economics", "1h")]) == 10
    assert score.cells(bets, "test") == {}


def test_candidates_come_from_train_only():
    ms, tr = many(150)
    ms2, tr2 = many(150, tag="B", close=CLOSE_T, series=("S2",), lose_every=2)
    bets, _ = score.build_bets(ms + ms2, {**tr, **tr2}, {})
    cand = score.candidates(bets)
    assert ("category", "Economics", "1h") in cand
    assert ("series", "S1", "1h") in cand
    assert ("series", "S2", "1h") not in cand        # only in the test half


def test_the_test_half_is_read_once(tmp_path):
    ms, tr = many(150, series=("S1", "S2", "S3"))
    ms2, tr2 = many(150, tag="B", close=CLOSE_T, series=("S1", "S2", "S3"))
    bets, _ = score.build_bets(ms + ms2, {**tr, **tr2}, {})
    cand = score.candidates(bets)
    out = tmp_path / "test_1h.json"
    res = score.read_test(bets, cand, out)
    assert res[("category", "Economics", "1h")]["passed"]
    assert json.loads(out.read_text())
    with pytest.raises(RuntimeError):
        score.read_test(bets, cand, out)


def test_lonely_uses_the_same_cell_at_other_checkpoints():
    test_means = {("category", "X", "1h"): (0.5, 200), ("category", "X", "2h"): (-0.1, 200),
                  ("category", "X", "half"): (-0.2, 150), ("category", "Y", "2h"): (0.9, 200)}
    assert score.is_lonely(test_means, ("category", "X", "1h")) is True
    assert score.is_lonely(test_means, ("category", "Y", "2h")) is False


def test_lonely_ignores_neighbours_under_100_events():
    test_means = {("category", "X", "1h"): (0.5, 200), ("category", "X", "2h"): (-0.1, 99)}
    assert score.is_lonely(test_means, ("category", "X", "1h")) is False


def test_contracts_per_day_by_series_over_the_complete_live_listing():
    rows = [{"series": "S1", "volume": 600, "close_time": "2026-09-01T00:00:00Z"},
            {"series": "S1", "volume": 600, "close_time": "2026-10-01T00:00:00Z"},
            {"series": "S2", "volume": 60, "close_time": "2026-10-01T00:00:00Z"},
            {"series": "S2", "volume": 999, "close_time": "2026-08-20T00:00:00Z"}]   # before the archive line
    got = score.contracts_per_day(rows)
    days = (core.WINDOW_END - core.ts("2026-08-29T00:00:00Z")) / 86400
    assert got == {"S1": pytest.approx(1200 / days), "S2": pytest.approx(60 / days)}


def test_calibration_rows_count_wins_by_band():
    ms, tr = many(100, lose_every=10, prices=(85,))
    bets, _ = score.build_bets(ms, tr, {})
    rows = score.calibration([b for b in bets if b["label"] == "1h"])
    r = rows[("Economics", "train", "80-90")]
    assert r["n"] == 100 and r["win_rate"] == pytest.approx(0.9) and r["mean_price"] == pytest.approx(85)


def test_spread_rows_use_markets_with_a_70_to_99c_favourite():
    now = core.ts("2026-10-29T00:00:00Z")
    rows = [
        {"ticker": "A", "event_ticker": "KXCPI-1", "close_time": "2026-10-29T01:00:00Z", "yes_bid": 90, "yes_ask": 92,
         "at": now},
        {"ticker": "B", "event_ticker": "KXCPI-2", "close_time": "2026-10-29T01:00:00Z", "yes_bid": 5, "yes_ask": 9,
         "at": now},                        # No favourite at about 93c: 4c spread
        {"ticker": "C", "event_ticker": "KXCPI-3", "close_time": "2026-10-29T01:00:00Z", "yes_bid": 40, "yes_ask": 60,
         "at": now},                        # no favourite over 70c: left out
        {"ticker": "D", "event_ticker": "KXCPI-4", "close_time": "2026-10-29T01:00:00Z", "yes_bid": 0, "yes_ask": 95,
         "at": now},                        # one side empty: left out
    ]
    got = score.spread_rows(rows, {"KXCPI": {"category": "Economics"}})
    assert sorted(r["spread"] for r in got) == [2, 4]
    assert {r["left"] for r in got} == {"1h"}


def test_time_left_label():
    assert score.left_label(30 * 60) == "half"
    assert score.left_label(1.5 * H) == "1h"
    assert score.left_label(3 * H) == "2h"
    assert score.left_label(40 * 24 * H) == "30d"


# ---------- streaming: each checkpoint is priced from the one record that fetched it ----------

CUT = core.ts("2026-08-29T00:00:00Z")


def test_streamed_bets_equal_bets_from_all_trades_merged():
    close = CUT + 100 * H
    m = market("A", "E1", close=close, life=5 * H)            # checkpoints 1h, 2h, 4h
    t1, t2, t4 = close - H, close - 2 * H, close - 4 * H
    page_trades = [[t2 - 600, 88, 1, "yes"], [t1 - 30, 91, 1, "yes"]]
    rec1 = {"ticker": "A", "stage": 1, "page": ["live", [t2 - 3700, t1, False]], "trades": page_trades,
            "targeted": [], "partial": {}}
    rec2 = {"ticker": "A", "stage": 2, "trades": [[t4 - 100, 80, 1, "yes"]], "targeted": ["4h"],
            "partial": {"4h": True}}
    got = score.stream_bets({"A": m}, [rec1], [rec2], labels=None)
    want, _ = score.build_bets([m], {"A": page_trades + rec2["trades"]}, {"A": {"4h": True}})
    key = lambda b: b["label"]
    assert sorted(got[0], key=key) == sorted(want, key=key)
    assert got[1][("Economics", "4h")] == 1


def test_streamed_bets_skip_stage_two_labels_until_asked():
    close = CUT + 100 * H
    m = market("A", "E1", close=close, life=5 * H)
    rec1 = {"ticker": "A", "stage": 1, "page": ["live", [close - 1.2 * H, close - H, False]],
            "trades": [[close - H - 30, 91, 1, "yes"]], "targeted": [], "partial": {}}
    bets, seen = score.stream_bets({"A": m}, [rec1], [], labels={"half", "1h"})
    assert [b["label"] for b in bets] == ["1h"]
    assert ("Economics", "2h") not in seen


def test_stage_one_record_labels_are_the_stage_one_points_and_whatever_the_page_covers():
    close = CUT + 100 * H
    cps = core.checkpoints(close - 30 * H, close)
    rec = {"page": ["live", [None, close - H, True]]}            # complete since the archive line
    assert score.record_labels(cps, rec, 1) == {lab for lab, _ in cps}
    rec = {"page": ["live", [close - 1.5 * H, close - H, False]]}
    assert score.record_labels(cps, rec, 1) == {"1h"}
    assert score.record_labels(cps, {"targeted": ["4h", "8h"]}, 2) == {"4h", "8h"}
