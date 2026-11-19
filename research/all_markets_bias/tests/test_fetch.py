"""fetch.py helpers: which markets are kept, which series they belong to, and which trade requests each needs."""
import pytest

import core
import fetch

H = 3600
CUT = core.ts("2026-08-29T00:00:00Z")


def raw_market(**kw):
    m = {"ticker": "KXCPI-26SEP-T0.3", "event_ticker": "KXCPI-26SEP", "open_time": "2026-09-01T00:00:00Z",
         "close_time": "2026-10-15T12:30:00Z", "result": "yes", "market_type": "binary", "volume_fp": "1234.00",
         "status": "finalized", "rules_primary": "long text we do not keep"}
    m.update(kw)
    return m


def test_series_of_uses_the_ticker_prefix_when_it_is_a_known_series():
    assert fetch.series_of("KXCPI-26SEP", {"KXCPI"}) == "KXCPI"


def test_series_of_adds_kx_for_old_style_event_tickers():
    assert fetch.series_of("CPI-21JUN", {"KXCPI"}) == "KXCPI"


def test_series_of_falls_back_to_the_prefix():
    assert fetch.series_of("ZZZ-1", {"KXCPI"}) == "ZZZ"


def test_compact_market_keeps_only_what_scoring_needs():
    m = fetch.compact_market(raw_market(), "KXCPI")
    assert m == {"ticker": "KXCPI-26SEP-T0.3", "event_ticker": "KXCPI-26SEP", "series": "KXCPI",
                 "open_time": "2026-09-01T00:00:00Z", "close_time": "2026-10-15T12:30:00Z", "result": "yes",
                 "market_type": "binary", "volume": 1234.0, "mve": False}


def test_compact_market_marks_combos():
    assert fetch.compact_market(raw_market(mve_collection_ticker="KXMVECROSSCATEGORY-R"), "X")["mve"] is True


@pytest.mark.parametrize("change,kept", [
    ({}, True),
    ({"result": "no"}, True),
    ({"result": ""}, False),
    ({"result": "void"}, False),
    ({"market_type": "scalar"}, False),
    ({"mve_collection_ticker": "KXMVE-R"}, False),
    ({"close_time": "2025-10-01T00:00:00Z"}, False),
    ({"close_time": "2026-10-28T00:00:00Z"}, False),
])
def test_keep_market(change, kept):
    assert fetch.keep_market(fetch.compact_market(raw_market(**change), "KXCPI")) is kept


def test_page_coverage_is_complete_when_the_page_is_short():
    trades = [[CUT + 5 * H, 90, 1, "yes"], [CUT + 6 * H, 91, 1, "yes"]]
    cov = fetch.page_coverage(trades, "live", t_max=CUT + 20 * H, limit=1000, cursor="abc", cutoff=CUT)
    assert cov == (CUT, CUT + 20 * H, True)


def test_page_coverage_of_a_full_page_starts_at_its_oldest_trade():
    trades = [[CUT + 5 * H + i, 90, 1, "yes"] for i in range(3)]
    cov = fetch.page_coverage(trades, "live", t_max=CUT + 20 * H, limit=3, cursor="abc", cutoff=CUT)
    assert cov == (CUT + 5 * H, CUT + 20 * H, False)


def test_page_coverage_of_an_empty_cursor_is_complete_even_if_full():
    trades = [[CUT - 5 * H + i, 90, 1, "yes"] for i in range(3)]
    cov = fetch.page_coverage(trades, "historical", t_max=CUT - H, limit=3, cursor="", cutoff=CUT)
    assert cov[2] is True and cov[0] == float("-inf")


def cps(*labels, close=CUT + 100 * H):
    hours = dict(core.CHECKPOINTS)
    return [(lab, close - hours[lab] * H) for lab in labels]


def test_targets_skip_checkpoints_the_first_page_covers():
    page = ("live", (CUT, CUT + 99 * H, True))
    assert fetch.targets(cps("1h", "2h", "4h"), page, CUT, stage=1) == []
    assert fetch.targets(cps("1h", "2h", "4h"), page, CUT, stage=2) == []


def test_stage_one_asks_only_for_half_and_1h():
    page = ("live", (CUT + 98.5 * H, CUT + 99 * H, False))     # a busy market: the page reaches back 30 minutes
    assert fetch.targets(cps("1h", "2h", "4h"), page, CUT, stage=1) == ["1h"]
    assert fetch.targets(cps("1h", "2h", "4h"), page, CUT, stage=2) == ["2h", "4h"]


def test_a_checkpoint_on_the_other_side_of_the_archive_line_needs_its_own_request():
    close = CUT + 30 * H
    page = ("live", (CUT, close - H, True))
    got = fetch.targets(cps("1h", "24h", "2d", close=close), page, CUT, stage=2)
    assert got == ["2d"]


def test_a_window_straddling_the_archive_line_always_gets_its_own_request():
    close = CUT + 24.5 * H
    page = ("live", (CUT, close - H, True))
    assert fetch.targets(cps("24h", close=close), page, CUT, stage=2) == ["24h"]


def test_no_first_page_means_every_checkpoint_in_the_stage_is_asked_for():
    assert fetch.targets(cps("1h", "2h"), None, CUT, stage=2) == ["2h"]


def test_in_windows_keeps_trades_in_the_hour_up_to_any_checkpoint():
    points = [("1h", 10 * H), ("4h", 7 * H)]
    trades = [[10 * H, 1, 1, "yes"], [9 * H, 2, 1, "yes"], [9 * H - 1, 3, 1, "yes"], [6.5 * H, 4, 1, "yes"],
              [6 * H - 1, 5, 1, "yes"], [10 * H + 1, 6, 1, "yes"]]
    assert [x[1] for x in fetch.in_windows(trades, points)] == [1, 2, 4]


def test_request_params_for_each_endpoint():
    assert fetch.trade_request("live", "T", CUT + 5 * H + 0.5, CUT, 200) == (
        "/markets/trades", {"ticker": "T", "max_ts": int(CUT + 5 * H) + 1, "limit": 200})
    assert fetch.trade_request("historical", "T", CUT + 0.25 * H, CUT, 200) == (
        "/historical/trades", {"ticker": "T", "max_ts": int(CUT), "limit": 200})


class FakeResp:
    def __init__(self, code, body=None):
        self.status_code = code
        self._body = body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, codes):
        self.codes = list(codes)

    def get(self, *a, **k):
        code = self.codes.pop(0)
        return FakeResp(code, {"ok": True} if code == 200 else None)


def quiet(monkeypatch, codes):
    slept = []
    monkeypatch.setattr(fetch.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(fetch.PACER, "wait", lambda: None)
    monkeypatch.setattr(fetch._local, "s", FakeSession(codes), raising=False)
    return slept


def test_get_waits_out_a_long_run_of_429s_with_pauses_capped_at_60_seconds(monkeypatch):
    slept = quiet(monkeypatch, [429] * 40 + [200])
    assert fetch.get("/x", {}) == {"ok": True}
    assert max(slept) <= 60
    assert sum(slept) > 30 * 60          # rode out more than half an hour of refusals


def test_get_gives_up_on_429s_after_about_four_hours(monkeypatch):
    quiet(monkeypatch, [429] * 1000)
    with pytest.raises(RuntimeError):
        fetch.get("/x", {})


def test_get_gives_up_on_server_errors_after_twelve_tries(monkeypatch):
    quiet(monkeypatch, [500] * 12 + [200])
    with pytest.raises(RuntimeError):
        fetch.get("/x", {})
